from temporalio import activity
import structlog

logger = structlog.get_logger(__name__)


@activity.defn(name="log_event_activity")
async def log_event_activity(payload: dict) -> dict:
    info = activity.info()

    logger.info(
        "auth_event_received",
        workflow_id=info.workflow_id,
        attempt=info.attempt,
        event_type=payload.get("event_type"),
        lang=payload.get("lang"),
        user_uuid=payload.get("user_uuid"),
        email=payload.get("email"),
        topic=payload.get("topic"),
        partition=payload.get("partition"),
        offset=payload.get("offset"),
    )

    return payload