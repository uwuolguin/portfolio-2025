from temporalio import workflow
from temporalio.workflow import ParentClosePolicy
from datetime import timedelta

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities.log_event_activity import log_event_activity
    from app.temporal.workflows.workflow_send_notification import SendNotificationWorkflow


@workflow.defn(name="AuthEventWorkflow")
class AuthEventWorkflow:
    """
    Parent workflow.
    1. Runs log_event_activity
    2. Fires SendNotificationWorkflow as a child with ABANDON policy

    Fire and forget pattern — source: docs.temporal.io/develop/python/child-workflows
      - start_child_workflow() confirms ChildWorkflowExecutionStarted is in
        event history then returns. Parent does NOT wait for child to finish.
      - ABANDON policy means child keeps running after parent completes.
    """

    @workflow.run
    async def run(self, payload: dict) -> None:
        enriched = await workflow.execute_activity(
            log_event_activity,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
        )

        await workflow.start_child_workflow(
            SendNotificationWorkflow.run,
            enriched,
            id=f"{workflow.info().workflow_id}-notification",
            parent_close_policy=ParentClosePolicy.ABANDON,
        )