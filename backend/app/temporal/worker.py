"""
Temporal Worker Process

Registers AuthEventWorkflow, SendNotificationWorkflow and their activities
against the "auth-queue" task queue. The Temporal server dispatches workflow
and activity tasks to this worker — it never pushes, the worker polls.

Usage:
    python -m app.temporal.worker          (local dev)
    docker-compose exec backend python -m app.temporal.worker

In Kubernetes this runs as a separate Deployment (15-temporal-worker.yaml)
using the same backend image — no separate Docker build needed.

Shutdown:
    Worker.run() handles SIGTERM gracefully by default — stops polling for
    new tasks and waits for in-flight activities to finish before exiting.
    terminationGracePeriodSeconds=60 in the manifest gives it time to drain.
"""

import asyncio
import sys

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

try:
    from app.middleware.logging import setup_logging
    setup_logging()
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)

from app.config import settings
from app.temporal.activities.log_event_activity import log_event_activity
from app.temporal.activities.send_email_activity import send_mock_email_activity
from app.temporal.workflows.workflow_logging import AuthEventWorkflow
from app.temporal.workflows.workflow_send_notification import SendNotificationWorkflow

logger = structlog.get_logger(__name__)

TASK_QUEUE = "auth-queue"


async def run_worker() -> None:
    logger.info(
        "temporal_worker_starting",
        host=settings.temporal_host,
        task_queue=TASK_QUEUE,
        workflows=["AuthEventWorkflow", "SendNotificationWorkflow"],
        activities=["log_event_activity", "send_mock_email_activity"],
    )

    client = await Client.connect(settings.temporal_host)
    logger.info("temporal_client_connected", host=settings.temporal_host)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AuthEventWorkflow, SendNotificationWorkflow],
        activities=[log_event_activity, send_mock_email_activity],
    )

    logger.info("temporal_worker_polling", task_queue=TASK_QUEUE)
    await worker.run()

    logger.info("temporal_worker_stopped", task_queue=TASK_QUEUE)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("temporal_worker_interrupted")
        sys.exit(0)


        