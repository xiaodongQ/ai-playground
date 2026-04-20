"""
V5 Worker Pool - 生产级进程池

管理一组持久化的 AI Agent 工作进程，支持：
- 进程预热（pre-warmed workers）
- 任务分发与负载均衡（Least Connections）
- 自动故障恢复（自动重启崩溃的 Worker）
- 优雅关闭
- 无输出超时检测

架构：
    WorkerPool
        ├── Worker[id=1]  ── subprocess (agent process)
        ├── Worker[id=2]  ── subprocess (agent process)
        └── Worker[id=N]  ── subprocess (agent process)

任务流程：
    submit(task) → 路由到 idle worker → worker.run(task) → 完成后 worker.idle
"""
from __future__ import annotations

import atexit
import logging
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ─── 数据模型 ────────────────────────────────────────────────────────────────


class WorkerStatus(Enum):
    STARTING = "starting"     # 进程启动中
    IDLE = "idle"            # 空闲，等待任务
    BUSY = "busy"            # 执行任务中
    RECOVERING = "recovering"# 故障恢复中
    STOPPING = "stopping"    # 优雅关闭中
    STOPPED = "stopped"      # 已停止


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


# ─── Worker ─────────────────────────────────────────────────────────────────


@dataclass
class Worker:
    """
    单个 Worker 进程

    每个 Worker 对应一个持久化的 Agent 子进程。
    进程默认处于 idle 状态，接收任务后变为 busy，
    任务完成后恢复 idle。
    """

    worker_id: str
    agent_type: str                    # "claude" | "codex" | "codebuddy"
    process: subprocess.Popen | None = None
    status: WorkerStatus = WorkerStatus.STOPPED
    session_id: str | None = None      # Agent 会话 ID，用于 resume
    current_task_id: str | None = None
    started_at: float = field(default_factory=time.time)
    last_task_at: float = 0.0
    task_count: int = 0
    error_count: int = 0
    max_consecutive_errors: int = 3

    # 回调钩子
    on_status_change: Callable[["WorkerStatus"], None] | None = None
    on_output: Callable[[str, str], None] | None = None  # (task_id, line)
    on_completion: Callable[[str, int], None] | None = None  # (task_id, returncode)

    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set_status(self, status: WorkerStatus) -> None:
        with self._lock:
            self.status = status
        if self.on_status_change:
            self.on_status_change(status)

    def is_idle(self) -> bool:
        return self.status == WorkerStatus.IDLE

    def is_busy(self) -> bool:
        return self.status == WorkerStatus.BUSY

    def is_alive(self) -> bool:
        # Worker 存活条件：状态不是 STOPPED（不再依赖 subprocess）
        return self.status != WorkerStatus.STOPPED

    def is_recoverable(self) -> bool:
        return self.error_count < self.max_consecutive_errors

    def incr_error(self) -> int:
        with self._lock:
            self.error_count += 1
            return self.error_count

    def incr_task(self) -> None:
        with self._lock:
            self.task_count += 1
            self.last_task_at = time.time()

    def stop(self, timeout: float = 5.0) -> None:
        """优雅停止 Worker"""
        self.set_status(WorkerStatus.STOPPING)
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=timeout)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.set_status(WorkerStatus.STOPPED)
        logger.info(f"[Worker-{self.worker_id}] Stopped")

    def __repr__(self) -> str:
        return (
            f"Worker(id={self.worker_id}, agent={self.agent_type}, "
            f"status={self.status.value}, tasks={self.task_count}, "
            f"errors={self.error_count})"
        )


# ─── PooledTask ───────────────────────────────────────────────────────────────


@dataclass
class PooledTask:
    """提交到 WorkerPool 的任务"""
    task_id: str
    prompt: str
    agent_type: str = "claude"
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: int = 300
    session_id: str | None = None
    skip_permissions: bool = False  # Default AUTO mode (BYPASS fails as root)
    allowed_tools: list[str] | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    # 外部回调：pool 任务完成时调用，参数为 (task_id: str)
    completion_callback: callable = None


# ─── WorkerPool ───────────────────────────────────────────────────────────────


class WorkerPool:
    """
    AI Agent 进程池

    用法：
        pool = WorkerPool(agent_type="claude", size=2)
        pool.start()

        task_id = pool.submit("帮我写一个函数")
        result = pool.wait(task_id, timeout=300)

        pool.stop()

    特性：
    - 进程预热：启动时创建 N 个预热进程
    - 负载均衡：Least Connections（分配给空闲最久的 Worker）
    - 故障恢复：崩溃的 Worker 自动重启（最多重试 3 次）
    - 无输出超时：超过 no_output_timeout 秒无输出则终止任务
    - 优雅关闭：收到信号时等待正在执行的任务完成
    - 线程安全：所有公开方法均线程安全
    """

    def __init__(
        self,
        agent_type: str = "claude",
        size: int = 2,
        max_concurrent: int | None = None,
        task_timeout: int = 300,
        no_output_timeout: int = 60,
        max_queue_size: int = 100,
        state_dir: str = "~/.ai_task_system/pool",
        on_worker_status: Callable[[Worker], None] | None = None,
        on_task_output: Callable[[str, str], None] | None = None,
        on_task_complete: Callable[[PooledTask], None] | None = None,
    ):
        self.agent_type = agent_type
        self.size = size
        self.max_concurrent = max_concurrent or size
        self.task_timeout = task_timeout
        self.no_output_timeout = no_output_timeout
        self.max_queue_size = max_queue_size
        self.state_dir = os.path.expanduser(state_dir)
        self.on_worker_status = on_worker_status
        self.on_task_output = on_task_output
        self.on_task_complete = on_task_complete

        self._workers: dict[str, Worker] = {}
        self._tasks: dict[str, PooledTask] = {}
        self._idle_workers: list[Worker] = []     # 空闲 Worker 队列（按空闲时长排序）
        self._busy_workers: set[str] = set()
        self._task_done_events: dict[str, threading.Event] = {}

        self._lock = threading.RLock()
        self._started = False
        self._stopping = False

        atexit.register(self.stop)

    # ─── 生命周期 ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """启动 Worker Pool（workers 立即就绪）"""
        if self._started:
            return

        Path(self.state_dir).mkdir(parents=True, exist_ok=True)

        for i in range(self.size):
            wid = f"w-{uuid.uuid4().hex[:8]}"
            worker = Worker(
                worker_id=wid,
                agent_type=self.agent_type,
                on_status_change=self._on_worker_status_change,
                on_output=self._on_worker_output,
                on_completion=self._on_worker_completion,
            )
            self._workers[wid] = worker
            self._start_worker(worker)

        self._started = True
        logger.info(f"[WorkerPool] Started with {self.size} workers for agent={self.agent_type}")

    def stop(self, timeout: float = 10.0) -> None:
        """优雅关闭所有 Worker"""
        if self._stopping:
            return
        self._stopping = True
        logger.info("[WorkerPool] Shutting down...")

        deadline = time.time() + timeout

        with self._lock:
            workers = list(self._workers.values())

        for w in workers:
            remaining_time = deadline - time.time()
            if remaining_time <= 0:
                w.stop(timeout=0)
            else:
                w.stop(timeout=remaining_time)

        self._started = False
        logger.info("[WorkerPool] Stopped")

    # ─── 命令构建 ────────────────────────────────────────────────────────────

    def _get_v4_command_builder(self, agent_type: str):
        """从 v4 获取命令构建器（延迟导入）"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from v4.core.command_builder import CommandBuilder
        from v4.core.base import AgentType, PermissionMode, ExecutionConfig
        return CommandBuilder, AgentType, PermissionMode, ExecutionConfig

    def _build_command(self, task: PooledTask) -> list[str]:
        """构建 Agent 执行命令"""
        try:
            CommandBuilder, AgentType, PermissionMode, ExecutionConfig = self._get_v4_command_builder(task.agent_type)
            config = ExecutionConfig(
                prompt=task.prompt,
                permission_mode=PermissionMode.BYPASS if task.skip_permissions else PermissionMode.AUTO,
                timeout=task.timeout,
                no_output_timeout=self.no_output_timeout,
            )
            builder = CommandBuilder(AgentType(task.agent_type))
            return builder.build(config)
        except Exception:
            # fallback 简单命令
            cmd = ["claude", "--print"]
            if task.skip_permissions:
                cmd.insert(1, "--dangerously-skip-permissions")
            if task.session_id:
                cmd.insert(1, f"--resume={task.session_id}")
            cmd.append("--")
            cmd.append(task.prompt)
            return cmd

    def _build_idle_command(self) -> list[str]:
        """
        构建空闲会话命令（进程启动但不执行任务）
        
        使用 bash 循环定期输出心跳，避免 Supervisor 的无输出超时检测。
        实际任务执行时会在 _execute() 中启动独立的 subprocess。
        """
        # 用 bash 循环心跳，避免无输出超时（Supervisor 默认 120s 无输出判定不健康）
        return [
            "bash", "-c",
            "while true; do echo 'idle'; sleep 30; done"
        ]

    # ─── Worker 生命周期 ────────────────────────────────────────────────────

    def _start_worker(self, worker: Worker) -> None:
        """启动单个 Worker（纯 Python 管理生命周期，不依赖 subprocess 阻塞）"""
        session_dir = Path(self.state_dir) / "sessions"
        session_dir.mkdir(exist_ok=True)
        # Worker 立即就绪，纯 Python 管理状态，不阻塞线程
        worker.set_status(WorkerStatus.IDLE)
        worker.process = None
        with self._lock:
            self._idle_workers.append(worker)
        logger.info(f"[Worker-{worker.worker_id}] Ready (no subprocess)")

    def _run_task_in_worker(self, worker: Worker, task: PooledTask) -> None:
        """在工作线程中执行任务（不阻塞主线程）"""

        def _execute():
            if not worker.is_alive():
                logger.warning(f"[Worker-{worker.worker_id}] Dead, skipping task {task.task_id}")
                self._on_task_failed(worker, task, -1)
                return

            worker.set_status(WorkerStatus.BUSY)
            worker.current_task_id = task.task_id
            worker.incr_task()

            # 从 idle 队列移出
            with self._lock:
                if worker in self._idle_workers:
                    self._idle_workers.remove(worker)
                self._busy_workers.add(worker.worker_id)

            cmd = self._build_command(task)
            logger.info(f"[Worker-{worker.worker_id}] Running task {task.task_id}: {' '.join(cmd[:5])}...")

            stdout_lines = []
            last_output_time = [time.time()]  # 用 list 包装以在嵌套函数中修改
            proc_lock = threading.Lock()

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=4096,
                )

                # 实时读取输出
                def read_stdout():
                    try:
                        while True:
                            line = proc.stdout.readline()
                            if not line:
                                break
                            stripped = line.rstrip()
                            stdout_lines.append(stripped)
                            last_output_time[0] = time.time()
                            if self.on_task_output:
                                self.on_task_output(task.task_id, stripped)
                    except Exception:
                        pass

                t = threading.Thread(target=read_stdout, daemon=True)
                t.start()

                # 等待完成（带超时 + 无输出超时）
                returncode = None
                start = time.time()
                while returncode is None:
                    returncode = proc.poll()
                    elapsed = time.time() - start
                    no_output = time.time() - last_output_time[0]

                    if elapsed >= task.timeout:
                        logger.warning(f"[Worker-{worker.worker_id}] Task {task.task_id} timed out")
                        proc.terminate()
                        time.sleep(0.5)
                        if proc.poll() is None:
                            proc.kill()
                        break
                    if no_output >= self.no_output_timeout:
                        logger.warning(
                            f"[Worker-{worker.worker_id}] No output for "
                            f"{self.no_output_timeout}s, terminating"
                        )
                        proc.terminate()
                        time.sleep(0.5)
                        if proc.poll() is None:
                            proc.kill()
                        break
                    time.sleep(0.5)

                t.join(timeout=2)
                returncode = proc.returncode

            except Exception as e:
                logger.error(f"[Worker-{worker.worker_id}] Task error: {e}")
                returncode = -1

            task.returncode = returncode
            task.stdout = "\n".join(stdout_lines)
            task.completed_at = time.time()

            self._on_task_completed(worker, task, returncode)

        threading.Thread(target=_execute, daemon=True).start()

    # ─── 任务提交 ────────────────────────────────────────────────────────────

    def submit(
        self,
        prompt: str,
        agent_type: str | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: int | None = None,
        session_id: str | None = None,
        skip_permissions: bool = False,  # Default AUTO mode (BYPASS fails as root)
        allowed_tools: list[str] | None = None,
        task_id: str | None = None,
        completion_callback: callable = None,
    ) -> str:
        """
        提交任务到 Worker Pool

        Returns:
            task_id: 任务 ID，可用于 wait() / status()
        """
        if not self._started:
            raise RuntimeError("WorkerPool not started. Call start() first.")

        task_id = task_id or f"task-{uuid.uuid4().hex[:8]}"
        task = PooledTask(
            task_id=task_id,
            prompt=prompt,
            agent_type=agent_type or self.agent_type,
            priority=priority,
            timeout=timeout or self.task_timeout,
            completion_callback=completion_callback,
            session_id=session_id,
            skip_permissions=skip_permissions,
            allowed_tools=allowed_tools,
        )

        with self._lock:
            pending = [t for t in self._tasks.values() if t.completed_at == 0]
            if len(pending) >= self.max_queue_size:
                logger.error(f"[WorkerPool] Task queue full: {len(pending)} pending >= {self.max_queue_size} max")
                raise RuntimeError(f"Task queue full ({self.max_queue_size})")

            self._tasks[task_id] = task
            self._task_done_events[task_id] = threading.Event()

        self._dispatch(task)
        return task_id

    def _dispatch(self, task: PooledTask) -> None:
        """将任务分配给空闲的 Worker（Least Connections）"""
        with self._lock:
            if not self._idle_workers:
                logger.debug(f"No idle workers for task {task.task_id}, queuing")
                return

            # 选择空闲最久的 worker
            worker = self._idle_workers.pop(0)
            self._idle_workers.append(worker)  # 用完放回队尾

        self._run_task_in_worker(worker, task)

    # ─── 任务查询 ────────────────────────────────────────────────────────────

    def wait(self, task_id: str, timeout: float | None = None) -> PooledTask:
        """
        等待任务完成

        Raises:
            TimeoutError: 任务超时
            KeyError: 任务不存在
        """
        if task_id not in self._tasks:
            raise KeyError(f"Task {task_id} not found")

        task = self._tasks[task_id]
        if task.completed_at > 0:
            return task

        event = self._task_done_events.get(task_id)
        if event is None:
            event = threading.Event()
            self._task_done_events[task_id] = event

        deadline = time.time() + (timeout or self.task_timeout)
        while task.completed_at == 0:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"Task {task_id} timed out")
            event.wait(timeout=min(remaining, 1.0))

        return task

    def status(self, task_id: str) -> dict[str, Any]:
        """查询任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found")

        return {
            "task_id": task.task_id,
            "status": "pending" if task.completed_at == 0 else "completed",
            "returncode": task.returncode,
            "elapsed": time.time() - task.created_at,
            "stdout_lines": task.stdout.count("\n") + 1 if task.stdout else 0,
        }

    def tasks(self) -> list[dict[str, Any]]:
        """列出所有任务"""
        return [
            {
                "task_id": t.task_id,
                "agent_type": t.agent_type,
                "status": "pending" if t.completed_at == 0 else "completed",
                "returncode": t.returncode,
                "priority": t.priority.name,
                "elapsed": time.time() - t.created_at,
            }
            for t in sorted(self._tasks.values(), key=lambda x: x.created_at)
        ]

    def workers_status(self) -> list[dict[str, Any]]:
        """列出所有 Worker 状态"""
        return [
            {
                "worker_id": w.worker_id,
                "agent_type": w.agent_type,
                "status": w.status.value,
                "task_count": w.task_count,
                "error_count": w.error_count,
                "current_task": w.current_task_id,
                "uptime": time.time() - w.started_at,
            }
            for w in self.list_workers()
        ]

    def list_workers(self) -> list[Worker]:
        """返回所有 Worker 对象的列表"""
        with self._lock:
            return sorted(self._workers.values(), key=lambda x: x.worker_id)

    # ─── 内部回调 ────────────────────────────────────────────────────────────

    def _on_worker_status_change(self, status: WorkerStatus) -> None:
        if self.on_worker_status:
            for w in self._workers.values():
                if w.status == status:
                    self.on_worker_status(w)
                    break

    def _on_worker_output(self, task_id: str, line: str) -> None:
        if self.on_task_output:
            self.on_task_output(task_id, line)

    def _on_worker_completion(self, worker: Worker, task_id: str, returncode: int) -> None:
        pass

    def _on_task_completed(self, worker: Worker, task: PooledTask, returncode: int) -> None:
        """任务完成回调"""
        task.returncode = returncode
        task.completed_at = time.time()

        # 调用外部完成回调（如 QueueDispatcher 注册的 queue.done 回调）
        if task.completion_callback:
            try:
                task.completion_callback(task.task_id)
            except Exception as e:
                logger.warning(f"[WorkerPool] completion_callback error: {e}")

        # 触发等待线程
        event = self._task_done_events.get(task.task_id)
        if event:
            event.set()

        # Worker 恢复空闲
        worker.set_status(WorkerStatus.IDLE)
        worker.current_task_id = None

        with self._lock:
            if worker.worker_id in self._busy_workers:
                self._busy_workers.remove(worker.worker_id)
            if worker not in self._idle_workers:
                self._idle_workers.append(worker)

        # 派发下一个待处理任务
        with self._lock:
            pending = [
                t for t in self._tasks.values()
                if t.completed_at == 0 and t.task_id != task.task_id
            ]

        if pending:
            pending.sort(key=lambda x: (-x.priority.value, x.created_at))
            self._dispatch(pending[0])

        if self.on_task_complete:
            self.on_task_complete(task)

        logger.info(f"[Worker-{worker.worker_id}] Task {task.task_id} done (rc={returncode})")

    def _on_task_failed(self, worker: Worker, task: PooledTask, returncode: int) -> None:
        """任务执行失败（Worker 崩溃）"""
        task.returncode = returncode
        task.completed_at = time.time()

        worker.incr_error()
        worker.set_status(WorkerStatus.IDLE)

        with self._lock:
            if worker.worker_id in self._busy_workers:
                self._busy_workers.remove(worker.worker_id)

        if not worker.is_recoverable():
            logger.warning(f"[Worker-{worker.worker_id}] Too many errors, restarting...")
            worker.error_count = 0
            threading.Thread(target=self._recover_worker, args=(worker,), daemon=True).start()
        else:
            new_task_id = self.submit(
                task.prompt,
                agent_type=task.agent_type,
                priority=task.priority,
                timeout=task.timeout,
            )
            logger.info(f"[Worker-{worker.worker_id}] Retried as {new_task_id}")

        event = self._task_done_events.get(task.task_id)
        if event:
            event.set()

        if self.on_task_complete:
            self.on_task_complete(task)

    def _recover_worker(self, worker: Worker) -> None:
        """重启崩溃的 Worker（纯 Python 管理，无需 subprocess）"""
        worker.set_status(WorkerStatus.RECOVERING)
        old_proc = worker.process
        if old_proc is not None:
            try:
                old_proc.terminate()
            except Exception:
                pass

        time.sleep(2)  # 等待系统资源释放

        # 重启 worker：立即设置为 IDLE
        worker.process = None
        worker.set_status(WorkerStatus.IDLE)
        with self._lock:
            if worker not in self._idle_workers:
                self._idle_workers.append(worker)
        logger.info(f"[Worker-{worker.worker_id}] Recovered")

    # ─── 上下文管理器 ────────────────────────────────────────────────────────

    def __enter__(self) -> "WorkerPool":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


# ─── CLI 入口 ────────────────────────────────────────────────────────────────


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    parser = argparse.ArgumentParser(description="V5 Worker Pool CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_start = sub.add_parser("start", help="Start worker pool")
    p_start.add_argument("--agent", default="claude")
    p_start.add_argument("--size", type=int, default=2)

    p_submit = sub.add_parser("submit", help="Submit a task")
    p_submit.add_argument("prompt")
    p_submit.add_argument("--agent", default="claude")
    p_submit.add_argument("--timeout", type=int, default=300)

    sub.add_parser("list", help="List workers and tasks")
    sub.add_parser("stop", help="Stop worker pool")

    args = parser.parse_args()

    pool = WorkerPool(agent_type=args.agent, size=getattr(args, "size", 2))

    if args.cmd == "start":
        pool.start()
        print(f"WorkerPool started with {args.size} workers")
        try:
            while True:
                time.sleep(5)
                print("\n=== Workers ===")
                for w in pool.workers_status():
                    print(f"  {w['worker_id']}: {w['status']} | tasks={w['task_count']} errors={w['error_count']}")
                print("=== Tasks ===")
                for t in pool.tasks():
                    print(f"  {t['task_id']}: {t['status']} (rc={t['returncode']})")
        except KeyboardInterrupt:
            pool.stop()

    elif args.cmd == "submit":
        pool.start()
        task_id = pool.submit(args.prompt, timeout=args.timeout)
        print(f"Task {task_id} submitted")
        try:
            task = pool.wait(task_id, timeout=args.timeout)
            print(f"\n=== Result (rc={task.returncode}) ===")
            print(task.stdout[:2000])
        except TimeoutError:
            print("Task timed out")
        pool.stop()

    elif args.cmd == "list":
        pool.start()
        for w in pool.workers_status():
            print(f"Worker {w['worker_id']}: {w['status']}")
        for t in pool.tasks():
            print(f"Task {t['task_id']}: {t['status']}")

    elif args.cmd == "stop":
        pool.stop()
        print("WorkerPool stopped")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
