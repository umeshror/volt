"""
tests/test_scheduler.py — Scheduler unit tests.
"""

import asyncio
import pytest
from volt.scheduler import Scheduler


@pytest.fixture
def scheduler():
    return Scheduler()


def test_every_registers_task(scheduler):
    """Decorated function should be added to the scheduler task list."""
    async def my_task():
        pass

    scheduler.add_every(10, my_task)
    assert len(scheduler._tasks) == 1


@pytest.mark.asyncio
async def test_every_calls_handler():
    """Handler should be called after the interval elapses."""
    scheduler = Scheduler()
    called = []

    async def my_task():
        called.append(True)

    scheduler.add_every(0.01, my_task)  # 10ms interval

    # Run the loop briefly and cancel
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)  # wait 50ms — at least 3 calls
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(called) >= 1


@pytest.mark.asyncio
async def test_when_fires_on_condition():
    """Handler should be called when condition function returns True."""
    scheduler = Scheduler()
    counter = [0]
    fired = []

    def condition():
        counter[0] += 1
        return counter[0] >= 3  # fires after 3rd poll

    async def handler():
        fired.append(True)

    scheduler.add_when(condition, handler)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.5)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(fired) >= 1


@pytest.mark.asyncio
async def test_task_error_does_not_crash_loop():
    """An exception inside a task should be caught; the loop must continue."""
    scheduler = Scheduler()
    errors = []
    successes = []

    call_count = [0]

    async def bad_task():
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("intentional error")
        successes.append(True)

    scheduler.add_every(0.01, bad_task)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # The loop should have continued and called the task again
    assert call_count[0] >= 2
    assert len(successes) >= 1


@pytest.mark.asyncio
async def test_multiple_tasks_run_concurrently():
    """Multiple tasks should run independently without blocking each other."""
    scheduler = Scheduler()
    log_a = []
    log_b = []

    async def task_a():
        log_a.append("a")

    async def task_b():
        log_b.append("b")

    scheduler.add_every(0.01, task_a)
    scheduler.add_every(0.02, task_b)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(log_a) >= 1
    assert len(log_b) >= 1
