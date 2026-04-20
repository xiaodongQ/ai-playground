"""
V5 Worker Supervisor - 进程监护系统

负责监控 WorkerPool 中所有 Worker 的健康状态：
- 心跳检测（heartbeat）
- 自动重启崩溃的 Worker
- 资源使用监控（CPU / Memory）
- 状态变更事件通知
- 优雅关闭协调

架构：
    Supervisor
        ├── monitors[worker_id] = WorkerMonitor
        ├── health_check_loop (每 interval 秒)
        └── recovery_policy (auto | manual)

用法：
    from v5.worker.pool import WorkerPool
    from v5.worker.supervisor import Supervisor

    pool = WorkerPool(agent_type="claude", size=2)
    pool.start()

    supervisor = Supervisor(pool, interval=5.0)
    supervisor.start()

    # 监听事件
    supervisor.on_worker_restart = lambda w: print(f"Restarted: {w.worker_id}")

    # 停止
    supervisor.stop()
"""
from __future__ import annotations

import atexit
import logging
import os
import resource
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# ─── 数据模型 ────────────────────────────────────────────────────────────────


class HealthStatus(Enum):
    HEALTHY = "healthy"       # 心跳正常
    SUSPECTED = "suspected"    # 心跳异常（可能假死）
    UNHEALTHY = "unhealthy"   # 已判定为崩溃
    RECOVERING = "recovering" # 正在重启


@dataclass
class WorkerSnapshot:
    """Worker 状态快照"""
    worker_id: str
    status: str
    pid: int | None
    session_id: str | None
    task_count: int
    error_count: int
    uptime: float
    last_output_age: float  # 距上次输出秒数
    cpu_percent: float      # CPU 使用率 %
    memory_mb: float        # 内存使用 MB


@dataclass
class SupervisorMetrics:
    """Supervisor 聚合指标"""
    total_workers: int = 0
    healthy_workers: int = 0
    unhealthy_workers: int = 0
    recovered_count: int = 0   # 本周期重启次数
    max_recovery_attempts: int = 3
    last_health_check: float = 0.0
    pool_uptime: float = 0.0


# ─── WorkerMonitor ───────────────────────────────────────────────────────────


class WorkerMonitor:
    """
    单个 Worker 的监护器

    跟踪 Worker 的心跳状态，连续 N 次检测失败则判定为崩溃。
    """

    def __init__(
        self,
        worker_id: str,
        check_interval: float = 5.0,
        max_missed_heartbeats: int = 3,
        no_output_threshold: float = 120.0,
    ):
        self.worker_id = worker_id
        self.check_interval = check_interval
        self.max_missed_heartbeats = max_missed_heartbeats
        self.no_output_threshold = no_output_threshold

        self.status = HealthStatus.HEALTHY
        self.missed_heartbeats = 0
        self.last_heartbeat = time.time()
        self.last_output_time = time.time()
        self.restart_count = 0
        self.max_restart_count = 3

        self._cpu_samples: list[float] = []
        self._mem_samples: list[float] = []

    def record_heartbeat(self) -> None:
        self.last_heartbeat = time.time()
        self.missed_heartbeats = 0
        if self.status == HealthStatus.SUSPECTED:
            self.status = HealthStatus.HEALTHY
            logger.info(f"[Supervisor] Worker {self.worker_id} recovered heartbeat")

    def record_output(self) -> None:
        self.last_output_time = time.time()

    def record_cpu_mem(self, cpu: float, mem: float) -> None:
        self._cpu_samples.append(cpu)
        self._mem_samples.append(mem)
        # 保留最近 10 个样本
        if len(self._cpu_samples) > 10:
            self._cpu_samples.pop(0)
        if len(self._mem_samples) > 10:
            self._mem_samples.pop(0)

    def avg_cpu(self) -> float:
        return sum(self._cpu_samples) / len(self._cpu_samples) if self._cpu_samples else 0.0

    def avg_mem(self) -> float:
        return sum(self._mem_samples) / len(self._mem_samples) if self._mem_samples else 0.0

    def check(self, worker_status: str = "idle") -> HealthStatus:
        """
        执行一次健康检测

        Args:
            worker_status: Worker 当前状态（idle/busy/starting/stopped）
                          非 busy 的 worker 不受无输出超时约束。

        Returns:
            HealthStatus: 当前的健康状态
        """
        now = time.time()
        elapsed_since_heartbeat = now - self.last_heartbeat
        elapsed_since_output = now - self.last_output_time

        if self.status == HealthStatus.RECOVERING:
            # 恢复中不重复检测
            return self.status

        # Startup grace period check（_started_at 由 Supervisor 在创建 monitor 时设置）
        startup_grace = 300.0  # 5分钟，让 Agent 有充足时间启动（下载模型等）
        grace_start = getattr(self, '_started_at', 0.0)
        in_startup_grace = (now - grace_start) < startup_grace

        # 检查心跳超时
        if elapsed_since_heartbeat > self.check_interval * self.max_missed_heartbeats:
            if not in_startup_grace:
                self.status = HealthStatus.UNHEALTHY
                self.missed_heartbeats += 1
            else:
                self.status = HealthStatus.HEALTHY
                self.missed_heartbeats = 0
        elif elapsed_since_heartbeat > self.check_interval:
            if not in_startup_grace:
                self.status = HealthStatus.SUSPECTED
                self.missed_heartbeats += 1
            else:
                self.status = HealthStatus.HEALTHY
                self.missed_heartbeats = 0
        else:
            self.status = HealthStatus.HEALTHY
            self.missed_heartbeats = 0

        # 无输出超时仅对忙碌 worker 检查（idle/startimg/stopped 状态没有任务输出）
        if worker_status == "busy" and elapsed_since_output > self.no_output_threshold:
            logger.warning(
                f"[Supervisor] Worker {self.worker_id} no output for "
                f"{elapsed_since_output:.0f}s (threshold={self.no_output_threshold}s)"
            )
            if self.status == HealthStatus.HEALTHY and not in_startup_grace:
                self.status = HealthStatus.UNHEALTHY

        return self.status

    def should_restart(self) -> bool:
        return (
            self.status == HealthStatus.UNHEALTHY
            and self.restart_count < self.max_restart_count
        )

    def mark_restarting(self) -> None:
        self.status = HealthStatus.RECOVERING
        self.restart_count += 1

    def mark_recovered(self) -> None:
        self.status = HealthStatus.HEALTHY
        self.missed_heartbeats = 0

    def get_snapshot(self, worker) -> WorkerSnapshot:
        """获取 Worker 状态快照"""
        pid = worker.process.pid if worker.process else None
        return WorkerSnapshot(
            worker_id=self.worker_id,
            status=worker.status.value,
            pid=pid,
            session_id=worker.session_id,
            task_count=worker.task_count,
            error_count=worker.error_count,
            uptime=time.time() - worker.started_at,
            last_output_age=time.time() - self.last_output_time,
            cpu_percent=self.avg_cpu(),
            memory_mb=self.avg_mem(),
        )


# ─── Supervisor ─────────────────────────────────────────────────────────────


class Supervisor:
    """
    WorkerPool 监护器

    使用独立的监控线程，定期检查所有 Worker 的健康状态，
    对不健康的 Worker 触发自动重启（recover）。

    事件钩子（可在外部赋值）：
        on_worker_healthy(WorkerSnapshot)
        on_worker_suspected(WorkerSnapshot)
        on_worker_unhealthy(WorkerSnapshot)
        on_worker_restart(WorkerSnapshot)
        on_metrics(SupervisorMetrics)
    """

    def __init__(
        self,
        pool,                    # WorkerPool 实例
        interval: float = 5.0,   # 健康检测间隔（秒）
        recovery_policy: str = "auto",  # "auto" | "manual"
        no_output_threshold: float = 120.0,
    ):
        self.pool = pool
        self.interval = interval
        self.recovery_policy = recovery_policy
        self.no_output_threshold = no_output_threshold

        self._monitors: dict[str, WorkerMonitor] = {}
        self._lock = threading.RLock()
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started = False
        self._started_at = 0.0  # Will be set in start(), fallback for safety
        self._total_recoveries = 0

        # 事件钩子
        self.on_worker_healthy: Callable[[WorkerSnapshot], None] | None = None
        self.on_worker_suspected: Callable[[WorkerSnapshot], None] | None = None
        self.on_worker_unhealthy: Callable[[WorkerSnapshot], None] | None = None
        self.on_worker_restart: Callable[[WorkerSnapshot], None] | None = None
        self.on_metrics: Callable[[SupervisorMetrics], None] | None = None

        # 注册 atexit 优雅关闭
        atexit.register(self._atexit_cleanup)

    # ─── 生命周期 ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """启动 Supervisor（启动监控线程）"""
        if self._started:
            logger.warning("[Supervisor] Already started")
            return

        # 为当前 pool 中的所有 worker 创建 monitor
        self._sync_monitors()

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._health_check_loop,
            name="WorkerSupervisor",
            daemon=True,
        )
        self._monitor_thread.start()
        
        # 等待首次健康检测完成（确保 workers 已真正就绪）
        # 否则 Supervisor 的首次检测可能在 workers 还在 STARTING 时运行
        deadline = time.time() + 10.0
        while not self._monitors:
            if time.time() > deadline:
                logger.warning(f"[Supervisor] Timeout waiting for monitors")
                break
            time.sleep(0.01)
        
        # _started_at 在这里设置，确保在 start() 完成后才进入 grace period
        self._started_at = time.time()
        self._started = True
        logger.info(
            f"[Supervisor] Started (interval={self.interval}s, "
            f"policy={self.recovery_policy}, "
            f"workers={len(self._monitors)})"
        )

    def stop(self, timeout: float = 10.0) -> None:
        """停止 Supervisor"""
        if not self._started:
            return

        logger.info("[Supervisor] Stopping...")
        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=timeout)

        self._started = False
        logger.info("[Supervisor] Stopped")

    def restart(self) -> None:
        """重启 Supervisor"""
        self.stop()
        self._sync_monitors()
        self.start()

    # ─── 核心逻辑 ──────────────────────────────────────────────────────────

    def _sync_monitors(self) -> None:
        """同步 WorkerPool 中的 Worker 到 Monitor 映射"""
        with self._lock:
            workers = self.pool.list_workers()
            current_ids = {w.worker_id for w in workers}

            # 移除已消失的 worker 的 monitor
            disappeared = set(self._monitors.keys()) - current_ids
            for wid in disappeared:
                del self._monitors[wid]
                logger.debug(f"[Supervisor] Removed monitor for {wid}")

            # 添加新出现的 worker 的 monitor
            for worker in workers:
                if worker.worker_id not in self._monitors:
                    monitor = WorkerMonitor(
                        worker.worker_id,
                        check_interval=self.interval,
                        no_output_threshold=self.no_output_threshold,
                    )
                    # 设置启动时间戳，启动 grace period（30秒）
                    monitor._started_at = time.time()
                    self._monitors[worker.worker_id] = monitor

    def _health_check_loop(self) -> None:
        """健康检测主循环（在独立线程中运行）"""
        while not self._stop_event.is_set():
            try:
                self._health_check()
            except Exception as e:
                logger.exception(f"[Supervisor] Health check error: {e}")

            # 等待下次检测，或等待停止信号
            self._stop_event.wait(timeout=self.interval)

    def _health_check(self) -> None:
        """执行一次健康检测并触发恢复"""
        self._sync_monitors()

        workers = self.pool.list_workers()
        worker_map = {w.worker_id: w for w in workers}
        metrics = SupervisorMetrics(
            total_workers=len(workers),
            healthy_workers=0,
            unhealthy_workers=0,
            recovered_count=0,
            last_health_check=time.time(),
            pool_uptime=time.time() - self._started_at,
        )

        for worker_id, monitor in list(self._monitors.items()):
            worker = worker_map.get(worker_id)
            if worker is None:
                continue

            # 采集资源使用
            cpu, mem = self._get_process_usage(worker)
            monitor.record_cpu_mem(cpu, mem)

            # 获取快照（用于事件回调）
            snapshot = monitor.get_snapshot(worker)

            # 执行检测（传递 worker 状态，非 busy 时跳过无输出超时）
            health = monitor.check(worker.status.value if hasattr(worker.status, 'value') else str(worker.status))

            # 更新聚合指标（心跳/output 记录仅在明确成功时）
            if health == HealthStatus.HEALTHY:
                metrics.healthy_workers += 1
                monitor.record_heartbeat()
                monitor.record_output()
                if self.on_worker_healthy:
                    self.on_worker_healthy(snapshot)
            elif health == HealthStatus.RECOVERING:
                # RECOVERING worker 下次检测应能恢复：先重置心跳
                monitor.record_heartbeat()
                monitor.record_output()
            elif health == HealthStatus.SUSPECTED:
                logger.warning(
                    f"[Supervisor] Worker {worker_id} suspected "
                    f"(missed={monitor.missed_heartbeats})"
                )
                if self.on_worker_suspected:
                    self.on_worker_suspected(snapshot)
            elif health == HealthStatus.UNHEALTHY:
                metrics.unhealthy_workers += 1
                logger.error(
                    f"[Supervisor] Worker {worker_id} unhealthy "
                    f"(missed={monitor.missed_heartbeats}, "
                    f"last_output_age={snapshot.last_output_age:.0f}s)"
                )
                if self.on_worker_unhealthy:
                    self.on_worker_unhealthy(snapshot)

                # 触发自动恢复
                if self.recovery_policy == "auto" and monitor.should_restart():
                    self._recover_worker(worker_id, monitor, worker)

        # 全局恢复计数
        metrics.recovered_count = self._total_recoveries

        # 触发指标回调
        if self.on_metrics:
            self.on_metrics(metrics)

    def _recover_worker(
        self,
        worker_id: str,
        monitor: WorkerMonitor,
        worker,
    ) -> None:
        """
        恢复一个不健康的 Worker

        流程：
        1. 标记为 RECOVERING（防止重复重启）
        2. 停止旧进程
        3. 通知 pool 启动新 Worker
        4. 重置 monitor 状态
        """
        monitor.mark_restarting()
        logger.warning(f"[Supervisor] Recovering worker {worker_id}...")

        try:
            # 停止旧进程
            worker.stop(timeout=5.0)
        except Exception as e:
            logger.warning(f"[Supervisor] Error stopping worker {worker_id}: {e}")

        # 通知 pool 重新启动
        try:
            self.pool._recover_worker(worker)
        except Exception as e:
            logger.exception(f"[Supervisor] Recovery failed for {worker_id}: {e}")

        # 重置 monitor
        monitor.last_heartbeat = time.time()
        monitor.last_output_time = time.time()
        monitor.mark_recovered()
        self._total_recoveries += 1

        snapshot = monitor.get_snapshot(worker)
        if self.on_worker_restart:
            self.on_worker_restart(snapshot)

        logger.info(
            f"[Supervisor] Worker {worker_id} recovered "
            f"(restart_count={monitor.restart_count})"
        )

    def _get_process_usage(self, worker) -> tuple[float, float]:
        """
        获取 Worker 子进程的 CPU 和内存使用

        Returns:
            (cpu_percent, memory_mb)
        """
        if worker.process is None or worker.process.poll() is not None:
            return 0.0, 0.0

        try:
            pid = worker.process.pid
            # 使用 /proc/{pid}/stat 获取 CPU times
            with open(f"/proc/{pid}/stat") as f:
                stat = f.read().split()
                utime = int(stat[13])
                stime = int(stat[14])
                total_time = utime + stime
                seconds = resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime
                # CPU 使用率估算
                cpu_fraction = total_time / (seconds * 100) if seconds > 0 else 0.0
                cpu_percent = min(cpu_fraction, 400.0)  # 4核 max

            # 内存使用（KB → MB）
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        mem_kb = int(line.split()[1])
                        mem_mb = mem_kb / 1024.0
                        return cpu_percent, mem_mb

            return cpu_percent, 0.0
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            return 0.0, 0.0
        except Exception as e:
            logger.debug(f"[Supervisor] Cannot get process usage: {e}")
            return 0.0, 0.0

    # ─── 查询 API ─────────────────────────────────────────────────────────

    def get_worker_snapshots(self) -> list[WorkerSnapshot]:
        """获取所有 Worker 的当前快照"""
        with self._lock:
            workers = self.pool.list_workers()
            worker_map = {w.worker_id: w for w in workers}
            return [
                m.get_snapshot(worker_map.get(wid, None))
                for wid, m in self._monitors.items()
                if wid in worker_map
            ]

    def get_metrics(self) -> SupervisorMetrics:
        """获取 Supervisor 聚合指标"""
        with self._lock:
            workers = self.pool.list_workers()
            snapshots = self.get_worker_snapshots()
            return SupervisorMetrics(
                total_workers=len(workers),
                healthy_workers=sum(
                    1 for s in snapshots if s.status == "idle" or s.status == "busy"
                ),
                unhealthy_workers=sum(
                    1 for s in snapshots if s.status not in ("idle", "busy", "starting")
                ),
                recovered_count=self._total_recoveries,
                last_health_check=time.time(),
                pool_uptime=time.time() - self._started_at,
            )

    def get_monitor_status(self, worker_id: str) -> HealthStatus | None:
        """获取指定 Worker 的健康状态"""
        with self._lock:
            monitor = self._monitors.get(worker_id)
            return monitor.status if monitor else None

    # ─── 工具方法 ─────────────────────────────────────────────────────────

    def _atexit_cleanup(self) -> None:
        """atexit 回调：确保 Supervisor 干净关闭"""
        try:
            self.stop(timeout=5.0)
        except Exception:
            pass

    def __repr__(self) -> str:
        return (
            f"Supervisor(workers={len(self._monitors)}, "
            f"interval={self.interval}s, policy={self.recovery_policy})"
        )


# ─── CLI 入口 ───────────────────────────────────────────────────────────────


def main():
    """Supervisor 独立运行（用于调试和演示）"""
    import argparse
    import json
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="V5 Worker Supervisor")
    parser.add_argument("--interval", type=float, default=5.0, help="Health check interval (s)")
    parser.add_argument("--policy", default="auto", choices=["auto", "manual"], help="Recovery policy")
    parser.add_argument("--no-output-threshold", type=float, default=120.0, help="No-output timeout (s)")
    parser.add_argument("--pool-size", type=int, default=2, help="Worker pool size")
    parser.add_argument("--agent", default="claude", help="Agent type")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode (no real pool)")
    args = parser.parse_args()

    if args.demo:
        # Demo 模式：创建假的 pool 对象
        class FakeWorker:
            def __init__(self, wid):
                self.worker_id = wid
                self.status = type('Status', (), {'value': 'idle'})()
                self.process = None
                self.session_id = None
                self.task_count = 0
                self.error_count = 0
                self.started_at = time.time() - 3600

        class FakePool:
            def list_workers(self):
                return [FakeWorker("w-001"), FakeWorker("w-002")]

        pool = FakePool()
        print("Demo mode: using fake pool")
    else:
        # 真实模式：创建 WorkerPool
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from v5.worker.pool import WorkerPool
        pool = WorkerPool(agent_type=args.agent, size=args.pool_size)
        pool.start()
        print(f"Created WorkerPool: agent={args.agent}, size={args.pool_size}")

    # 创建 Supervisor
    supervisor = Supervisor(
        pool,
        interval=args.interval,
        recovery_policy=args.policy,
        no_output_threshold=args.no_output_threshold,
    )

    # 设置事件回调
    supervisor.on_worker_healthy = lambda s: print(f"  ✅ {s.worker_id} healthy")
    supervisor.on_worker_suspected = lambda s: print(f"  ⚠️  {s.worker_id} suspected")
    supervisor.on_worker_unhealthy = lambda s: print(f"  ❌ {s.worker_id} unhealthy")
    supervisor.on_worker_restart = lambda s: print(f"  🔄 {s.worker_id} restarted")
    supervisor.on_metrics = lambda m: print(
        f"  📊 metrics: {m.healthy_workers}/{m.total_workers} healthy, "
        f"recovered={m.recovered_count}"
    )

    print(f"\nSupervisor: interval={args.interval}s, policy={args.policy}")
    print("Press Ctrl+C to stop\n")

    supervisor.start()

    try:
        while True:
            time.sleep(args.interval)
            # 打印当前状态
            snapshots = supervisor.get_worker_snapshots()
            print(f"\n{'='*60}")
            for s in snapshots:
                health = supervisor.get_monitor_status(s.worker_id)
                print(
                    f"  {s.worker_id}: status={s.status}, "
                    f"pid={s.pid}, tasks={s.task_count}, "
                    f"cpu={s.cpu_percent:.1f}%, mem={s.memory_mb:.1f}MB, "
                    f"health={health.value if health else '?'}"
                )
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        supervisor.stop()
        if not args.demo:
            pool.stop()
        print("Done")


if __name__ == "__main__":
    import sys
    main()
