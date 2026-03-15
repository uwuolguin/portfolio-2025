from temporalio import workflow
from datetime import timedelta

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities.send_email_activity import send_mock_email_activity


@workflow.defn(name="SendNotificationWorkflow")
class SendNotificationWorkflow:
    """
    Child workflow. Runs independently after parent closes.
    Only calls send_mock_email_activity.
    """

    @workflow.run
    async def run(self, payload: dict) -> None:
        await workflow.execute_activity(
            send_mock_email_activity,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
        )