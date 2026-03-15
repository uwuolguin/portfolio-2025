"""
Triggers: _CoreJsonFormatter (Rust core logs via LogForwardingConfig)
How: activity sleeps past its start_to_close_timeout — Temporal Rust core
     emits WARN logs about the timed-out activity, forwarded via LogForwardingConfig
     into core_logger → hits _CoreJsonFormatter.
Expected log: {"level": "warn", "logger": "temporalio.core...", "event": "..."}
"""
import asyncio
from datetime import timedelta
from temporalio import workflow, activity


@activity.defn
async def activity_timeout() -> str:
    # Sleep longer than the timeout set in the workflow — core emits WARN
    await asyncio.sleep(30)
    return "never_reached"


@workflow.defn
class TestCoreLogsWorkflow:
    @workflow.run
    async def run(self) -> str:
        try:
            await workflow.execute_activity(
                activity_timeout,
                # Short timeout — activity will exceed it, triggering core WARN logs
                start_to_close_timeout=timedelta(seconds=3),
            )
        except Exception as e:
            workflow.logger.warning("activity_timed_out_as_expected", error=str(e))
        return "core_log_test_done"
