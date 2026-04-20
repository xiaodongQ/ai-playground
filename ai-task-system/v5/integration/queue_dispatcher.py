"""
QueueDispatcher — 桥接 TaskQueue 和 WorkerPool 的调度器。

职责：
1. 后台线程每 poll_interval 秒轮询 TaskQueue 的 PENDING 任务
2. 通过 queue.dequeue() 原子性地认领任务（DEQUEUED）
3. 提交给 WorkerPool 执行
4. 维护 _task_events 用于 wait() 支持
"""

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from v5.queue.queue import TaskQueue
    from v5.worker.pool import WorkerPool

logger = logging.getLogger(__name__)


class QueueDispatcher:
    """
    调度器：负责从 TaskQueue 取任务并派发给 WorkerPool。

    用法：
        dispatcher = QueueDispatcher(queue=q, pool=pool, poll_interval=1.0, max_concurrent=10)
        dispatcher.start()
        ...
        dispatcher.wait(task_id, timeout=60)  # 等待任务完成
        dispatcher.stop()
    """

    def __init__(
        self,
        queue: "TaskQueue",
        pool: "WorkerPool",
        poll_interval: float = 1.0,
        max_concurrent: int = 10,
    ):
        self.queue = queue
        self.pool = pool
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._task_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self):
        """启动调度器后台线程"""
        if self._thread is not None:
            logger.warning("Dispatcher already started")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="QueueDispatcher")
        self._thread.start()
        logger.info(f"QueueDispatcher started (poll_interval={self.poll_interval}s)")

    def stop(self, timeout: float = 5.0):
        """停止调度器"""
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=timeout)
        self._thread = None
        logger.info("QueueDispatcher stopped")

    def wait(self, task_id: str, timeout: float = 300) -> bool:
        """等待指定任务完成"""
        event = None
        with self._lock:
            if task_id not in self._task_events:
                self._task_events[task_id] = threading.Event()
            event = self._task_events[task_id]
        return event.wait(timeout=timeout)

    def _run_loop(self):
        """后台轮询循环"""
        while not self._stop.is_set():
            try:
                self._poll_and_dispatch()
            except Exception as e:
                logger.exception(f"Error in dispatcher loop: {e}")
            self._stop.wait(self.poll_interval)
        logger.info("[QueueDispatcher._run_loop] Stopped")

    def _poll_and_dispatch(self):
        """检查队列并派发任务"""
        # 获取当前 Running 任务数，推算可用槽位
        try:
            active_tasks = self._count_active_tasks()
        except Exception:
            active_tasks = 0

        available_slots = max(0, self.max_concurrent - active_tasks)
        if available_slots <= 0:
            logger.debug(f"[Dispatcher] No slots: active={active_tasks} max={self.max_concurrent}")
            return

        # 每次最多派发 available_slots 个任务
        # 用 dequeue(worker_id, max_wait=0) 原子性地认领 PENDING → DEQUEUED
        dispatched = 0
        for i in range(available_slots):
            task = self._try_dequeue_one(f"dispatcher-{i}")
            if task is None:
                break  # 没有更多待处理任务
            if self._dispatch_dequeued_task(task):
                dispatched += 1

        if dispatched > 0:
            logger.info(f"[Dispatcher] Dispatched {dispatched} task(s)")

    def _try_dequeue_one(self, worker_id: str) -> Any | None:
        """
        尝试原子性地从队列中认领一个任务。

        相当于 dequeue(worker_id, max_wait=0)：找到最高优先权的 PENDING 任务，
        原子性地将其状态更新为 DEQUEUED，并返回该任务。

        Returns:
            Task 对象（已认领，状态=DEQUEUED），或 None（队列为空）
        """
        try:
            task = self.queue.dequeue(worker_id=worker_id, max_wait=0.0)
            return task
        except Exception as e:
            logger.warning(f"[Dispatcher] dequeue failed: {e}")
            return None

    def _dispatch_dequeued_task(self, task: Any) -> bool:
        """
        将已认领的 DEQUEUED 任务派发给 WorkerPool。

        注意：任务已处于 DEQUEUED 状态，无需再调用 queue.start()。
        WorkerPool 任务完成后，on_task_complete 回调会处理完成状态更新。
        如果 WorkerPool 满（pool.submit 抛出"queue full"），则将任务退回 PENDING。
        """
        task_id = task.task_id

        # 从 payload 提取执行信息
        payload = task.payload if isinstance(task.payload, dict) else {}
        prompt = payload.get("prompt", "")
        agent = payload.get("agent", "claude")
        timeout = task.timeout

        try:
            # 通知队列任务已开始（DEQUEUED → RUNNING）
            try:
                self.queue.start(task_id)
            except Exception as e:
                logger.warning(f"[Dispatcher] queue.start({task_id}) failed: {e}")

            # 注册完成回调：pool 任务完成时自动更新 queue 状态
            def on_complete(pool_task_id_):
                queue_task_id_ = task_id
                try:
                    self.queue.done(queue_task_id_, result={"pool_task_id": pool_task_id_})
                    logger.info(f"[Dispatcher] Task {queue_task_id_} marked done (pool {pool_task_id_})")
                except Exception as e:
                    logger.warning(f"[Dispatcher] queue.done({queue_task_id_}) failed: {e}")
                # 触发 wait 事件
                with self._lock:
                    ev = self._task_events.get(queue_task_id_)
                    if ev:
                        ev.set()

            pool_task_id = self.pool.submit(
                prompt=prompt,
                agent_type=agent,
                timeout=timeout,
                session_id=payload.get("session_id"),
                completion_callback=on_complete,
            )
            logger.info(f"[Dispatcher] Task {task_id} → pool {pool_task_id}")

            # 注册完成事件（供 wait() 使用）
            with self._lock:
                self._task_events[task_id] = threading.Event()

            return True

        except Exception as e:
            err_str = str(e)
            logger.error(f"[Dispatcher] pool.submit({task_id}) failed: {e}")

            # pool 已满：把任务退回 PENDING 队列（稍后重试）
            if "queue full" in err_str.lower():
                try:
                    self.queue._conn().execute(
                        """
                        UPDATE tasks
                        SET status = ?, dequeued_at = NULL, worker_id = NULL
                        WHERE task_id = ? AND status = ?
                        """,
                        (0, task_id, 1),  # 0 = PENDING, 1 = DEQUEUED
                    )
                    self.queue._conn().commit()
                    logger.info(f"[Dispatcher] Task {task_id} returned to PENDING (pool full)")
                except Exception as rollback_err:
                    logger.warning(f"[Dispatcher] Rollback failed for {task_id}: {rollback_err}")
            else:
                # 其他错误：标记任务失败
                try:
                    self.queue.fail(task_id, error=err_str, retry=False)
                except Exception:
                    pass

            return False

    def _count_active_tasks(self) -> int:
        """统计当前 Running 任务数"""
        try:
            running = self.queue.list_running(limit=1000)
            return len(running)
        except Exception:
            return 0


def setup_queue_dispatcher(queue, pool, poll_interval=1.0):
    """创建并启动调度器（便捷函数）"""
    dispatcher = QueueDispatcher(queue=queue, pool=pool, poll_interval=poll_interval)
    dispatcher.start()
    return dispatcher
