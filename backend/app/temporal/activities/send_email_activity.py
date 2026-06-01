"""Activity for sending mock emails."""  # pylint: disable=missing-module-docstring

from temporalio import activity
import structlog

logger = structlog.get_logger(__name__)


@activity.defn(name="send_mock_email_activity")
async def send_mock_email_activity(
    payload: dict,
) -> bool:
    """Send a mock email (replace with real email service in production)."""
    info = activity.info()

    logger.info(
        "mock_email_sent",
        workflow_id=info.workflow_id,
        attempt=info.attempt,
        to=payload.get("email"),
        event_type=payload.get("event_type"),
        lang=payload.get("lang"),
        note="MOCK — no real email sent, replace with resend.Emails.send() in production",
    )

    return True
