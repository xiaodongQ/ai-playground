import pytest
from backend.scheduler import Scheduler

def test_scheduler_initialization():
    scheduler = Scheduler()
    assert scheduler.poll_interval == 5
    assert scheduler._running is False