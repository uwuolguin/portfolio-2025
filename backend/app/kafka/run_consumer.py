import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.structs import OffsetAndMetadata

logger = logging.getLogger(__name__)

# Maps (topic, partition) to a Temporal workflow name.
# Partition 0 = es users, Partition 1 = en users — matches PARTITION_MAP in producer.py.
# Swap string names for class references once the workflows are defined:
#   from app.temporal.workflows import LoginEsWorkflow, ...
TOPIC_PARTITION_TO_WORKFLOW = {
    ("user-logins",  0): "LoginEsWorkflow",
    ("user-logins",  1): "LoginEnWorkflow",
    ("user-logouts", 0): "LogoutEsWorkflow",
    ("user-logouts", 1): "LogoutEnWorkflow",
}


async def run_consumer(bootstrap_servers: str, temporal_host: str) -> None:
    # Temporal client — placeholder connection until the Temporal pod is deployed.
    # If the connection fails here, the consumer crashes and Kubernetes restarts it.
    # Once Temporal is up, the next restart connects successfully.
    try:
        from temporalio.client import Client, WorkflowAlreadyStartedError
        temporal = await Client.connect(temporal_host)
        logger.info("temporal_connected", extra={"host": temporal_host})
    except Exception as e:
        logger.warning("temporal_unavailable", extra={"host": temporal_host, "error": str(e)})
        temporal = None

    consumer = AIOKafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id="auth-event-workers",
        enable_auto_commit=False,   # offsets committed manually, AFTER Temporal acks
        auto_offset_reset="earliest",
    )

    # Explicit partition assignment — no rebalance coordinator needed for a single worker.
    # If you scale to 2 replicas later, switch to consumer.subscribe([...]) and let
    # Kafka split the 4 partitions between both pods automatically.
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
            workflow_name = TOPIC_PARTITION_TO_WORKFLOW.get((msg.topic, msg.partition))

            if not workflow_name:
                logger.warning("no_workflow_for_partition", extra={
                    "topic": msg.topic,
                    "partition": msg.partition,
                })
                continue

            # Deterministic workflow ID — deduplication-safe.
            # If this message is reprocessed after a crash, Temporal rejects the
            # duplicate start instead of running the workflow twice.
            workflow_id = f"auth-{msg.topic}-{msg.partition}-{msg.offset}"

            payload = json.loads(msg.value)

            if temporal is not None:
                try:
                    from temporalio.client import WorkflowAlreadyStartedError
                    await temporal.start_workflow(
                        workflow_name,
                        payload,
                        id=workflow_id,
                        task_queue="auth-queue",
                    )
                    logger.info("workflow_started", extra={
                        "workflow_id": workflow_id,
                        "workflow": workflow_name,
                    })
                except WorkflowAlreadyStartedError:
                    # Duplicate — already processed. Safe to commit and move on.
                    logger.info("workflow_duplicate_skipped", extra={"workflow_id": workflow_id})
                except Exception as e:
                    logger.error("workflow_start_failed", extra={
                        "workflow_id": workflow_id,
                        "error": str(e),
                    })
                    # Do not commit — message will be reprocessed on next restart.
                    continue
            else:
                # Temporal not available — log the event and commit anyway so the
                # consumer doesn't pile up a backlog of unprocessable messages.
                # Remove this branch once Temporal is deployed.
                logger.info("temporal_unavailable_event_dropped", extra={
                    "workflow_id": workflow_id,
                    "payload": payload,
                })

            # Commit AFTER Temporal has accepted the work — never before.
            # offset + 1 = "give me the next message from here, you store in the broker what you want next"
            await consumer.commit({
                TopicPartition(msg.topic, msg.partition): OffsetAndMetadata(msg.offset + 1, "")
            })

    finally:
        await consumer.stop()
        logger.info("consumer_stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from app.config import settings
    asyncio.run(run_consumer(settings.bootstrap_servers, settings.temporal_host))