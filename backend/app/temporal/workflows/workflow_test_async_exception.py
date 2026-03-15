"""
Triggers: install_async_exception_handler
How: activity fires a task without awaiting it — the task raises,
     the loop exception handler catches it.
Expected log: {"level": "error", "event": "uncaught_async_exception", ...}
"""
import asyncio
from datetime import timedelta
from temporalio import workflow, activity


@activity.defn
async def activity_fire_and_forget_bad_task() -> str:
    async def bad():
        raise RuntimeError("test async uncaught exception from activity task")

    # Fire and forget — not awaited, loop exception handler fires
    asyncio.create_task(bad())

    # Give the loop a tick to run the task
    await asyncio.sleep(0.1)
    return "fire_and_forget_done"


@workflow.defn
class TestAsyncExceptionWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            activity_fire_and_forget_bad_task,
            start_to_close_timeout=timedelta(seconds=10),
        )
