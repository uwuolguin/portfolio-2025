"""
Triggers: _SdkJsonFormatter (temporalio.* Python-side logs)
How: workflow.logger and activity.logger both route through
     logging.getLogger("temporalio.*") → hits _SdkJsonFormatter.
Expected log: {"timestamp": "...", "level": "warning", "logger": "temporalio.workflow", ...}
"""
from datetime import timedelta
from temporalio import workflow, activity


@activity.defn
async def activity_sdk_log() -> str:
    activity.logger.warning(
        "test_activity_sdk_log — this should appear as JSON via _SdkJsonFormatter"
    )
    return "activity_sdk_log_done"


@workflow.defn
class TestSdkLogsWorkflow:
    @workflow.run
    async def run(self) -> str:
        workflow.logger.warning(
            "test_workflow_sdk_log — this should appear as JSON via _SdkJsonFormatter"
        )
        result = await workflow.execute_activity(
            activity_sdk_log,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return result
