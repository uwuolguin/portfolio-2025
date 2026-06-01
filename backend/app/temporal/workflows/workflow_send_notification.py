"""Workflow for sending notifications via email."""  # pylint: disable=missing-module-docstring

from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities.send_email_activity import send_mock_email_activity


@workflow.defn(name="SendNotificationWorkflow")
class SendNotificationWorkflow:  # pylint: disable=too-few-public-methods
    """
    Child workflow. Runs independently after parent closes.
    Only calls send_mock_email_activity.
    """

    @workflow.run
    async def run(self, payload: dict) -> None:
        # pylint: disable=missing-function-docstring
        await workflow.execute_activity(
            send_mock_email_activity,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
        )
