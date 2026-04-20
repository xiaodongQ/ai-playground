"""
Tests for RetryExecutor - exponential backoff retry mechanism.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

import pytest
from ai_task_system.v4.core.base import TaskStatus
from ai_task_system.v4.core.retry import (
    RetryConfig,
    RetryAction,
    RetryExecutor,
    retry_summary,
)


class TestRetryConfig:
    def test_default_values(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 5.0
        assert cfg.max_delay == 120.0
        assert cfg.exponential_base == 2.0

    def test_custom_values(self):
        cfg = RetryConfig(max_retries=5, base_delay=10.0, max_delay=60.0)
        assert cfg.max_retries == 5
        assert cfg.base_delay == 10.0
        assert cfg.max_delay == 60.0

    def test_should_retry_failure_first_attempt(self):
        cfg = RetryConfig(max_retries=3)
        result = cfg.should_retry(TaskStatus.FAILED, 0)
        assert result == RetryAction.RETRY_DELAY

    def test_should_retry_failure_max_attempts(self):
        cfg = RetryConfig(max_retries=3)
        # Attempt 3 = max_retries → give up
        result = cfg.should_retry(TaskStatus.FAILED, 3)
        assert result == RetryAction.GIVE_UP

    def test_should_not_retry_success(self):
        cfg = RetryConfig(max_retries=3)
        result = cfg.should_retry(TaskStatus.SUCCESS, 0)
        assert result == RetryAction.GIVE_UP

    def test_should_retry_timeout(self):
        cfg = RetryConfig(max_retries=3)
        result = cfg.should_retry(TaskStatus.NO_OUTPUT_TIMEOUT, 1)
        assert result == RetryAction.RETRY_DELAY


class TestRetryDelay:
    def test_delay_exponential_growth(self):
        cfg = RetryConfig(base_delay=5.0, exponential_base=2.0, jitter=0.0)
        delay0 = cfg.compute_delay(0)
        delay1 = cfg.compute_delay(1)
        delay2 = cfg.compute_delay(2)
        # delay1 ≈ base × 2^1 = 10
        assert delay1 > delay0
        assert delay2 > delay1

    def test_delay_respects_max(self):
        cfg = RetryConfig(base_delay=10.0, max_delay=15.0, exponential_base=2.0, jitter=0.0)
        delay5 = cfg.compute_delay(5)  # Would be 10 × 2^5 = 320
        assert delay5 <= 15.0

    def test_delay_has_jitter(self):
        cfg = RetryConfig(base_delay=10.0, exponential_base=2.0, jitter=1.0)
        delays = [cfg.compute_delay(0) for _ in range(20)]
        # With jitter=1, delays should vary
        assert len(set(delays)) > 1


class TestRetrySummary:
    def test_summary_format(self):
        from ai_task_system.v4.core.retry import RetryState
        state = RetryState(
            task_id="test",
            attempt=2,
            total_attempts=3,
            first_attempt_at=1000.0,
            last_attempt_at=1020.0,
            last_error="error",
            history=[
                {"attempt": 0, "status": "failed", "delay": 5.0, "duration": 5.0, "error": "err1"},
                {"attempt": 1, "status": "failed", "delay": 10.0, "duration": 10.0, "error": "err2"},
                {"attempt": 2, "status": "success", "delay": 0.0, "duration": 3.5, "error": ""},
            ],
            give_up_reason=None,
        )
        summary = retry_summary(state)
        assert isinstance(summary, str)
        assert "test" in summary
        assert "3" in summary  # total attempts
