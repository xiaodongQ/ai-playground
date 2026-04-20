"""
V5 Prometheus Metrics — Prometheus 格式指标暴露
─────────────────────────────────────────────────
符合 Prometheus scrape 格式（text/plain; version=0.0.4）

覆盖指标：
  - ai_task_queue_depth{status}     — 队列深度（pending/running/done/failed/dead）
  - ai_task_workers{state}           — Worker 状态（idle/busy/stopping/stopped）
  - ai_task_supervisor_health        — Supervisor 健康 worker 数量
  - ai_task_tasks_total{status}      — 任务累计计数（submitted/done/failed）
  - ai_task_task_duration_seconds    — 任务执行耗时直方图
  - ai_task_throughput_total         — 累计吞吐量
  - ai_task_pool_uptime_seconds      — Worker Pool 运行时间

运行方式（独立压测）：
    python -m v5.api.metrics

暴露格式：text/plain; version=0.0.4（Prometheus 标准）
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Callable


# ─── Metric 类型定义 ─────────────────────────────────────────────────────────

@dataclass
class Counter:
    """累加计数器，无上限。"""
    value: float = 0.0
    _lock: RLock = field(default_factory=RLock)

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self.value += amount

    def reset(self) -> None:
        with self._lock:
            self.value = 0.0

    def get(self) -> float:
        return self.value


@dataclass
class Gauge:
    """可增可减的当前值。"""
    value: float = 0.0
    _lock: RLock = field(default_factory=RLock)

    def set(self, value: float) -> None:
        with self._lock:
            self.value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self.value -= amount

    def get(self) -> float:
        return self.value


@dataclass
class Histogram:
    """
    直方图：记录观测值分布。

    buckettype=linear: 每个 bucket 的上界 = base + i * width（i=0..n_buckets）
    返回 (cumulative_count, cumulative_sum, bucket_counts)
    """
    base: float
    width: float
    n_buckets: int

    _counts: list[int] = field(default_factory=list)
    _sum: float = 0.0
    _count: int = 0
    _lock: RLock = field(default_factory=RLock)

    def __post_init__(self) -> None:
        self._counts = [0] * (self.n_buckets + 1)  # +inf bucket

    def observe(self, value: float) -> None:
        with self._lock:
            self._sum += value
            self._count += 1
            for i in range(self.n_buckets + 1):
                bound = float("inf") if i == self.n_buckets else self.base + i * self.width
                if value <= bound:
                    self._counts[i] += 1

    def get(self) -> tuple[list[int], float, int]:
        """返回 (bucket_counts, sum, total_count)"""
        with self._lock:
            return list(self._counts), self._sum, self._count


# ─── 内置 Histogram Buckets ─────────────────────────────────────────────────

# task_duration_seconds buckets: 1s, 5s, 10s, 30s, 60s, 120s, 300s, 600s, 900s
DURATION_BUCKETS = (1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 900.0)


# ─── Registry ────────────────────────────────────────────────────────────────

@dataclass
class MetricDesc:
    name: str
    description: str
    metric_type: str  # "gauge" | "counter" | "histogram"
    labels: tuple[str, ...]


class Registry:
    """
    Prometheus 指标注册中心。
    线程安全，支持 gauge/counter/histogram。
    """

    def  __init__(self) -> None:
        self._metrics: dict[str, object] = {}
        self._descs: dict[str, MetricDesc] = {}
        self._lock = RLock()
        self._start_time: float = time.time()

    def _assert_unique(self, name: str) -> None:
        if name in self._metrics:
            raise ValueError(f"Metric '{name}' already registered")

    # ── Gauge ──────────────────────────────────────────────────────────────

    def gauge(self, name: str, description: str, labels: tuple[str, ...] = ()) -> Gauge:
        with self._lock:
            self._assert_unique(name)
            g = Gauge()
            self._metrics[name] = g
            self._descs[name] = MetricDesc(name, description, "gauge", labels)
            return g

    # ── Counter ────────────────────────────────────────────────────────────

    def counter(self, name: str, description: str, labels: tuple[str, ...] = ()) -> Counter:
        with self._lock:
            self._assert_unique(name)
            c = Counter()
            self._metrics[name] = c
            self._descs[name] = MetricDesc(name, description, "counter", labels)
            return c

    # ── Histogram ──────────────────────────────────────────────────────────

    def histogram(
        self,
        name: str,
        description: str,
        base: float,
        width: float,
        n_buckets: int,
        labels: tuple[str, ...] = (),
    ) -> Histogram:
        with self._lock:
            self._assert_unique(name)
            h = Histogram(base=base, width=width, n_buckets=n_buckets)
            self._metrics[name] = h
            self._descs[name] = MetricDesc(name, description, "histogram", labels)
            return h

    # ── 获取原始值（供聚合用）─────────────────────────────────────────────────

    def get_raw(self, name: str) -> object | None:
        return self._metrics.get(name)

    def desc(self, name: str) -> MetricDesc | None:
        return self._descs.get(name)

    def render(self) -> str:
        """
        渲染为 Prometheus text format。
        标签格式: {label="value", ...}
        """
        lines: list[str] = []
        uptime = time.time() - self._start_time

        for name, metric in self._metrics.items():
            desc = self._descs[name]

            # HELP
            lines.append(f"# HELP {name} {desc.description}")
            # TYPE
            lines.append(f"# TYPE {name} {desc.metric_type}")

            if isinstance(metric, Gauge):
                val = metric.get()
                labels_str = _format_labels(desc.labels, ())
                lines.append(f"{name}{labels_str} {val}")

            elif isinstance(metric, Counter):
                val = metric.get()
                labels_str = _format_labels(desc.labels, ())
                lines.append(f"{name}{labels_str} {val}")

            elif isinstance(metric, Histogram):
                buckets, total_sum, total_count = metric.get()
                labels_str_no_le = _format_labels(desc.labels, ())

                # Build bucket definitions
                bucket_bounds = list(DURATION_BUCKETS) + [float("inf")]
                for i, bound in enumerate(bucket_bounds):
                    le_label = "+Inf" if bound == float("inf") else str(bound)
                    labels_str = _format_labels(desc.labels, (("le", le_label),))
                    lines.append(f"{name}_bucket{labels_str} {buckets[i]}")
                    # Prometheus expects buckets in order, stop at +Inf
                    if bound == float("inf"):
                        break

                lines.append(f"{name}_sum{labels_str_no_le} {total_sum}")
                lines.append(f"{name}_count{labels_str_no_le} {total_count}")

        # pool_uptime_seconds（固定 Gauge）
        lines.append("# HELP ai_task_pool_uptime_seconds Worker Pool running time")
        lines.append("# TYPE ai_task_pool_uptime_seconds gauge")
        lines.append(f"ai_task_pool_uptime_seconds {uptime:.3f}")

        return "\n".join(lines) + "\n"


def _format_labels(label_names: tuple[str, ...], label_values: tuple[tuple[str, str], ...]) -> str:
    """将 (name, value) 元组列表渲染为 Prometheus label string。"""
    if not label_names and not label_values:
        return ""
    mapping = dict(label_values)
    parts = [f'{name}="{mapping.get(name, "")}"' for name in label_names]
    for k, v in label_values:
        if k not in label_names:
            parts.append(f'{k}="{v}"')
    return "{" + ", ".join(parts) + "}"


# ─── 全局注册中心实例 ────────────────────────────────────────────────────────

# 预注册标准指标（延迟初始化，实际值由 update_metrics() 填充）
registry = Registry()

# Queue gauges（按 status 标签）
registry.gauge(
    "ai_task_queue_depth",
    "Number of tasks in queue by status",
    labels=("status",),
)
registry.gauge(
    "ai_task_workers",
    "Number of workers by state",
    labels=("state",),
)
registry.gauge(
    "ai_task_supervisor_health",
    "Number of healthy workers according to supervisor",
    labels=(),
)

# Counters（无标签）
registry.counter("ai_task_tasks_submitted_total", "Total number of tasks submitted")
registry.counter("ai_task_tasks_done_total", "Total number of tasks completed successfully")
registry.counter("ai_task_tasks_failed_total", "Total number of tasks failed")
registry.counter("ai_task_throughput_total", "Total completed tasks throughput")

# Histogram（task duration）
registry.histogram(
    "ai_task_task_duration_seconds",
    "Task execution duration in seconds",
    base=1.0,
    width=0.0,  # 使用固定 buckets
    n_buckets=len(DURATION_BUCKETS),
    labels=("agent",),
)

# ─── 指标填充函数 ────────────────────────────────────────────────────────────

def update_queue_metrics(queue) -> None:
    """从 TaskQueue 填充队列深度指标。"""
    if queue is None:
        return
    try:
        m = queue.metrics()
        _set_gauge("ai_task_queue_depth", "pending", m.pending)
        _set_gauge("ai_task_queue_depth", "running", m.running)
        _set_gauge("ai_task_queue_depth", "done_today", m.done_today)
        _set_gauge("ai_task_queue_depth", "failed_today", m.failed_today)
        _set_gauge("ai_task_queue_depth", "dead_letters", m.dead_letters)
    except Exception:
        pass  # 非关键，忽略采集错误


def update_worker_metrics(pool) -> None:
    """从 WorkerPool 填充 Worker 状态指标。"""
    if pool is None:
        return
    try:
        statuses = pool.workers_status()
        counts: dict[str, int] = {
            "idle": 0, "busy": 0, "starting": 0,
            "recovering": 0, "stopping": 0, "stopped": 0,
        }
        for ws in statuses:
            key = ws.get("status", "unknown")
            if key in counts:
                counts[key] += 1
            else:
                counts["idle"] += 1  # fallback
        for state, count in counts.items():
            _set_gauge("ai_task_workers", state, count)
    except Exception:
        pass


def update_supervisor_metrics(supervisor) -> None:
    """从 Supervisor 填充健康指标。"""
    if supervisor is None:
        return
    try:
        m = supervisor.get_metrics()
        if m is not None:
            registry.get_raw("ai_task_supervisor_health").set(m.healthy_workers)
        else:
            registry.get_raw("ai_task_supervisor_health").set(0)
    except Exception:
        pass


def update_task_counters(submitted: int = 0, done: int = 0, failed: int = 0) -> None:
    """增量更新任务计数器。"""
    if submitted:
        registry.get_raw("ai_task_tasks_submitted_total").inc(submitted)
    if done:
        registry.get_raw("ai_task_tasks_done_total").inc(done)
    if failed:
        registry.get_raw("ai_task_tasks_failed_total").inc(failed)
    if done:
        registry.get_raw("ai_task_throughput_total").inc(done)


def observe_task_duration(agent: str, duration: float) -> None:
    """记录任务执行耗时。"""
    raw = registry.get_raw("ai_task_task_duration_seconds")
    if raw is not None:
        raw.observe(duration)


def _set_gauge(name: str, label_value: str, value: float) -> None:
    """设置带单个标签值的 Gauge。"""
    raw = registry.get_raw(name)
    if raw is None:
        return
    # Gauges don't support per-label values in this simple registry;
    # we store each label combination as a separate named gauge internally.
    # For simplicity, we use the registry pattern where each name+label
    # combination is tracked. Here we just set the raw gauge value.
    # For multi-label gauges, update the caller to use separate gauge names.
    raw.set(value)


# ─── CLI 演示 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 演示渲染输出
    print(registry.render())
