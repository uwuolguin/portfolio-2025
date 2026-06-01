"""
Triggers: _SdkJsonFormatter (temporalio.workflow internal logger)
How: workflow.logger is Temporal's own internal logger — routes through
     logging.getLogger("temporalio.workflow") → hits _SdkJsonFormatter.
Expected log: {"timestamp": "...", "level": "warning", "logger": "temporalio.workflow", ...}
"""

from datetime import timedelta
from temporalio import workflow, activity


@activity.defn
async def activity_core_log() -> str:  # pylint: disable=missing-function-docstring
    return "done"


@workflow.defn
class TestCoreLogsWorkflow:  # pylint: disable=too-few-public-methods,missing-class-docstring
    @workflow.run
    async def run(self) -> str:  # pylint: disable=missing-function-docstring
        workflow.logger.warning(
            "test_temporal_internal_logger — intercepted and formatted as JSON"
        )
        await workflow.execute_activity(
            activity_core_log,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return "done"
