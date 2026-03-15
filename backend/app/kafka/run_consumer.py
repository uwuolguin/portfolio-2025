"""
Redpanda/Kafka Consumer — routes auth events to Temporal AuthEventWorkflow.

Partition layout (mirrors producer.py PARTITION_MAP):
  user-logins  partition 0  →  login  / es
  user-logins  partition 1  →  login  / en
  user-logouts partition 0  →  logout / es
  user-logouts partition 1  →  logout / en

All four partitions submit to the same AuthEventWorkflow.
event_type + lang inside the payload drive branching inside the workflow.
"""

import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.structs import OffsetAndMetadata
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

logger = logging.getLogger(__name__)

TOPIC_PARTITION_TO_EVENT_TYPE: dict[tuple[str, int], str] = {
    ("user-logins",  0): "login",
    ("user-logins",  1): "login",
    ("user-logouts", 0): "logout",
    ("user-logouts", 1): "logout",
}

WORKFLOW_NAME = "AuthEventWorkflow"
TASK_QUEUE = "auth-queue"


async def run_consumer(bootstrap_servers: str, temporal_host: str) -> None:
    # ── Temporal client ────────────────────────────────────────────────────
    # Client.connect() has no built-in retry on initial connection.
    # If Temporal is unavailable the consumer crashes and Kubernetes restarts it.
    # The initContainer in 13-consumer.yaml ensures Temporal is up before
    # this process starts, so failure here is a hard error not a race condition.
    temporal = await Client.connect(temporal_host)
    logger.info("temporal_connected", extra={"host": temporal_host})

    # ── Kafka consumer ─────────────────────────────────────────────────────
    consumer = AIOKafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id="auth-event-workers",
        enable_auto_commit=False,   # manual commit AFTER Temporal acks
        auto_offset_reset="earliest",
    )

    # Explicit partition assignment — no rebalance coordinator needed for
    # a single worker. All four partitions are assigned to this one instance.
    partitions = [
        TopicPartition("user-logins",  0),
        TopicPartition("user-logins",  1),
        TopicPartition("user-logouts", 0),
        TopicPartition("user-logouts", 1),
    ]
    consumer.assign(partitions)

    await consumer.start()
    logger.info("consumer_started", extra={"brokers": bootstrap_servers})

    try:
        async for msg in consumer:
            event_type = TOPIC_PARTITION_TO_EVENT_TYPE.get((msg.topic, msg.partition))

            if not event_type:
                logger.warning(
                    "no_event_type_for_partition",
                    extra={"topic": msg.topic, "partition": msg.partition},
                )
                continue

            # Deterministic workflow ID — if this message is reprocessed after
            # a crash, Temporal rejects the duplicate start instead of running
            # the workflow twice.
            workflow_id = f"auth-{msg.topic}-{msg.partition}-{msg.offset}"

            # Enrich payload with Kafka provenance so the workflow has full
            # context for logging — event_type, topic, partition, and offset.
            raw_payload: dict = json.loads(msg.value)
            enriched_payload = {
                **raw_payload,
                "event_type": event_type,   # "login" | "logout"
                "topic": msg.topic,          # "user-logins" | "user-logouts"
                "partition": msg.partition,  # 0 (es) | 1 (en)
                "offset": msg.offset,        # Kafka offset for audit trail
            }

            try:
                await temporal.start_workflow(
                    WORKFLOW_NAME,
                    enriched_payload,
                    id=workflow_id,
                    task_queue=TASK_QUEUE,
                )
                logger.info(
                    "workflow_started",
                    extra={
                        "workflow_id": workflow_id,
                        "workflow": WORKFLOW_NAME,
                        "event_type": event_type,
                        "lang": raw_payload.get("lang"),
                    },
                )
            except WorkflowAlreadyStartedError:
                # Duplicate offset reprocessed after crash — already handled,
                # safe to commit and move on.
                logger.info(
                    "workflow_duplicate_skipped",
                    extra={"workflow_id": workflow_id},
                )
            except Exception as e:
                logger.error(
                    "workflow_start_failed",
                    extra={"workflow_id": workflow_id, "error": str(e)},
                )
                # Do not commit — message will be reprocessed on next restart.
                continue

            # Commit only after Temporal has accepted the work.
            # offset + 1 tells the broker where to resume on next restart.
            await consumer.commit({
                TopicPartition(msg.topic, msg.partition): OffsetAndMetadata(msg.offset + 1, "")
            })

    finally:
        await consumer.stop()
        logger.info("consumer_stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bootstrap_servers = os.environ["BOOTSTRAP_SERVERS"]
    temporal_host = os.environ.get("TEMPORAL_HOST", "temporal:7233")
    asyncio.run(run_consumer(bootstrap_servers, temporal_host))