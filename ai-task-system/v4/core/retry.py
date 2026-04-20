"""
V4 错误重试机制：指数退避 + 可配置策略

为 SubprocessExecutor 提供自动重试能力，
处理临时性失败（进程崩溃、网络抖动、Agent 挂起等）。
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable

from .base import AgentAdapter, ExecutionConfig, Task, TaskStatus


class RetryAction(Enum):
    """重试决策"""
    RETRY_NOW = "retry_now"       # 立即重试
    RETRY_DELAY = "retry_delay"   # 延迟后重试
    GIVE_UP = "give_up"           # 放弃


@dataclass
class RetryConfig:
    """
    重试配置

    默认策略：最多 3 次重试，指数退避 5s~60s，
    对 FAIL/NO_OUTPUT_TIMEOUT/AGENT_ERROR 类错误进行重试。
    """
    max_retries: int = 3                    # 最大重试次数（含首次）
    base_delay: float = 5.0                 # 初始延迟（秒）
    max_delay: float = 120.0                # 最大延迟上限（秒）
    exponential_base: float = 2.0            # 指数底数
    jitter: float = 1.0                     # ± jitter 秒随机抖动（避免惊群）
    retry_on: tuple[TaskStatus, ...] = field(
        default_factory=lambda: (
            TaskStatus.FAILED,
            TaskStatus.NO_OUTPUT_TIMEOUT,
            TaskStatus.TIMEOUT,
            TaskStatus.AGENT_ERROR,
        )
    )
    # 是否对可恢复的错误应用退避
    apply_backoff_on_retry: bool = True
    # 最大连续放弃次数（超过后降级 Agent 或报警）
    max_consecutive_give_up: int = 5

    def should_retry(self, status: TaskStatus, attempt: int) -> RetryAction:
        """判断是否应该重试"""
        if attempt >= self.max_retries:
            return RetryAction.GIVE_UP
        if status not in self.retry_on:
            return RetryAction.GIVE_UP
        return RetryAction.RETRY_DELAY

    def compute_delay(self, attempt: int) -> float:
        """计算退避延迟（指数 + 抖动）"""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        jitter_range = min(self.jitter, delay * 0.5)
        return delay + random.uniform(-jitter_range, jitter_range)


@dataclass
class RetryState:
    """单次任务的重试状态"""
    task_id: str
    attempt: int = 0                        # 当前尝试次数（0 = 首次）
    total_attempts: int = 0                 # 累计尝试次数（含重试）
    first_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_error: str = ""
    history: list[dict] = field(default_factory=list)  # [{attempt, status, delay, duration}]
    give_up_reason: str | None = None


class RetryExecutor:
    """
    带重试逻辑的执行器包装器

    包装 SubprocessExecutor，对失败任务自动按 RetryConfig 进行指数退避重试。
    不修改原 SubprocessExecutor 的行为。

    用法::

        from v4.core.executor import SubprocessExecutor
        from v4.core.retry import RetryExecutor, RetryConfig

        base = SubprocessExecutor()
        retry = RetryExecutor(base, RetryConfig(max_retries=3))

        task = retry.execute(config, adapter)
        # task.status 已是最终状态（SUCCESS / GIVE_UP / TIMEOUT / ...）
        # retry.last_state 包含完整的重试历史
    """

    def __init__(
        self,
        base: "SubprocessExecutor",
        config: RetryConfig | None = None,
        on_retry: Callable[[RetryState, RetryConfig], None] | None = None,
        on_give_up: Callable[[RetryState], None] | None = None,
    ):
        self._base = base
        self._config = config or RetryConfig()
        self._on_retry = on_retry
        self._on_give_up = on_give_up
        self._lock = threading.Lock()
        self.last_state: RetryState | None = None  # 最近一次执行的完整状态

    @property
    def config(self) -> RetryConfig:
        return self._config

    def execute(self, config: ExecutionConfig, adapter: AgentAdapter) -> Task:
        """
        执行任务，自动重试失败的任务。

        Returns:
            Task — 最终状态（SUCCESS / GIVE_UP / TIMEOUT / ...）
        """
        state = RetryState(task_id=f"retry-{int(time.time())}-{id(config)}")

        while True:
            state.attempt += 1
            state.total_attempts += 1
            now = datetime.now()

            if state.first_attempt_at is None:
                state.first_attempt_at = now
            state.last_attempt_at = now

            # 执行
            task = self._base.execute(config, adapter, task_id=state.task_id)
            state.last_error = self._get_error_summary(task)

            # 记录历史
            state.history.append({
                "attempt": state.attempt,
                "status": task.status.value,
                "duration": task.result.duration_seconds if task.result else 0,
                "error": state.last_error,
                "timestamp": now.isoformat(),
            })

            # 成功 → 完成
            if task.status == TaskStatus.SUCCESS:
                self.last_state = state
                return task

            # 判断是否重试
            decision = self._config.should_retry(task.status, state.attempt)

            if decision == RetryAction.GIVE_UP:
                state.give_up_reason = (
                    f"status={task.status.value}, attempt={state.attempt}, "
                    f"max_retries={self._config.max_retries}"
                )
                if self._on_give_up:
                    self._on_give_up(state)
                task.status = TaskStatus.GIVE_UP
                self.last_state = state
                return task

            # RETRY_DELAY → 计算延迟
            delay = self._config.compute_delay(state.attempt - 1)

            if self._on_retry:
                self._on_retry(state, self._config)

            time.sleep(delay)
            # 重试时复用原 task_id，但 config 中可追加标记
            config = self._with_retry_tag(config, state.attempt)

    def _with_retry_tag(self, config: ExecutionConfig, attempt: int) -> ExecutionConfig:
        """返回带重试标记的新配置（用于调试/日志）"""
        import copy
        new_config = copy.copy(config)
        new_config.env_vars = dict(config.env_vars or {})
        new_config.env_vars["AI_TASK_RETRY_ATTEMPT"] = str(attempt)
        return new_config

    def _get_error_summary(self, task: Task) -> str:
        if task.result:
            err = task.result.stderr or ""
            if len(err) > 200:
                err = err[:200] + "..."
            return err
        return f"status={task.status.value}"


# ─── CLI 辅助 ────────────────────────────────────────────────────────────────

def build_retry_executor(
    max_retries: int = 3,
    base_delay: float = 5.0,
    on_retry: Callable[[RetryState, RetryConfig], None] | None = None,
) -> RetryExecutor:
    """快捷创建 RetryExecutor（供 CLI 使用）"""
    from .executor import SubprocessExecutor

    cfg = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        retry_on=(TaskStatus.FAILED, TaskStatus.NO_OUTPUT_TIMEOUT, TaskStatus.TIMEOUT),
    )
    base = SubprocessExecutor()
    return RetryExecutor(base, cfg, on_retry=on_retry)


def retry_summary(state: RetryState) -> str:
    """生成人类可读的重试摘要"""
    lines = [
        f"Task: {state.task_id}",
        f"Total attempts: {state.total_attempts}",
    ]
    if state.give_up_reason:
        lines.append(f"Result: GIVE_UP — {state.give_up_reason}")
    else:
        lines.append("Result: SUCCESS")

    lines.append(f"Last error: {state.last_error}")
    if state.history:
        lines.append(f"Duration: {state.history[-1]['duration']:.1f}s (last)")

    for h in state.history:
        lines.append(
            f"  attempt {h['attempt']}: {h['status']} "
            f"({h['duration']:.1f}s) — {h['error'][:80]}"
        )
    return "\n".join(lines)
