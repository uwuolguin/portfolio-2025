"""
Redpanda/Kafka Producer Module

Fire-and-forget event publisher.
Any backend endpoint can call publish_event() as a background task to publish
to any topic. The producer instance is shared across the entire application —
one connection to Redpanda, reused for every topic, every endpoint, forever.

If Redpanda is down, errors are logged and swallowed — auth and any other
endpoint that publishes events will never fail because of the event pipeline.
This swallowing behaviour serves as a manual circuit breaker: on a Kafka error
the producer is marked as dead (self._producer = None), the failed event is
discarded, and the next publish attempt triggers a lazy reconnect. If Redpanda
is still down that attempt also fails fast (request_timeout_ms=3000, retries=1)
and is discarded again. No request ever blocks waiting for a broken broker and
no thundering herd of reconnects hammers Redpanda during recovery. A proper
circuit breaker (closed/open/half-open states) would add value at high traffic
volume but is unnecessary at current scale — this pattern covers the same ground.

Partition routing is explicit — no hash involved:
  key="es" → partition 0
  key="en" → partition 1
PARTITION_MAP drives the assignment directly. Adding a new language means adding
one entry to PARTITION_MAP and creating the corresponding partition in the broker.
Keys not in PARTITION_MAP are discarded before sending.

Reuse:
  KafkaProducerClient wraps a single AIOKafkaProducer instance that lives for
  the entire process lifetime. It is not tied to any specific topic. Any future
  endpoint that needs to publish an event — orders, notifications, audit logs,
  anything — calls kafka_producer.publish_event() with a different topic name
  and reuses the same underlying connection. No new producer, no new connection,
  no extra cost.

Concurrency safety:
  start() is protected by an asyncio.Lock. Without it, two concurrent login
  requests arriving while self._producer is None (e.g. Redpanda was down at
  startup) could both enter start() simultaneously, both create an
  AIOKafkaProducer, and one would be orphaned — holding an open TCP connection
  to Redpanda that is never closed. The lock ensures only one coroutine runs
  the initialization block at a time. The double-check inside the lock
  (if self._producer is not None: return) handles the case where a second
  coroutine was waiting for the lock while the first completed initialization.
"""

import asyncio
import json
from typing import Optional
import structlog
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaError
from app.config import settings

logger = structlog.get_logger(__name__)


class KafkaProducerClient:
    """
    Wraps AIOKafkaProducer as a single shared instance for the entire process.

    Same behaviour as the module-level global pattern — Python modules are
    singletons, so kafka_producer imported anywhere in the app is the same
    object in memory. The class just makes the state and methods explicit
    instead of scattered across module-level variables.

    Use two instances of this class if you ever need two producers with
    different configs — e.g. one with acks="all" for critical events and
    one with acks=1 for fire-and-forget analytics.
    """

    # Explicit language → partition mapping. No hash, no coincidence.
    # Add new language + create matching partition in broker when scaling.
    PARTITION_MAP = {"es": 0, "en": 1}

    def __init__(self) -> None:
        self._producer: Optional[AIOKafkaProducer] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize the producer — call once during app startup."""
        async with self._lock:
            # Another coroutine may have initialized while this one waited for the lock.
            if self._producer is not None:
                return

            try:
                self._producer = AIOKafkaProducer(
                    # Initial connection point — broker responds with cluster metadata.
                    bootstrap_servers=settings.bootstrap_servers,

                    # Payload dict → JSON string → bytes.
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),

                    # Acknowledge on leader write —  it does not wait for other brokers to end writing.
                    acks=1,

                    # Fail fast — don't hang login requests waiting for a slow broker.
                    request_timeout_ms=3000,

                    # One retry on transient errors before giving up.
                    retries=1,
                )

                # Opens TCP connection, fetches cluster metadata, producer ready to send.
                await self._producer.start()
                logger.info("kafka_producer_started", brokers=settings.bootstrap_servers)

            except Exception as e:
                # Redpanda down at startup — stay None, lazy reconnect retries on next publish.
                self._producer = None
                logger.warning(
                    "kafka_producer_start_failed",
                    error=str(e),
                    message="Events will not be published until Redpanda is available",
                )

    async def stop(self) -> None:
        """Graceful shutdown — call during app shutdown."""
        async with self._lock:
            if self._producer is None:
                return

            try:
                # Flushes buffered messages, closes TCP connection, releases resources.
                await self._producer.stop()
                logger.info("kafka_producer_stopped")
            except Exception as e:
                logger.warning("kafka_producer_stop_error", error=str(e))
            finally:
                # Always clean up regardless of whether .stop() raised.
                self._producer = None

    async def publish_event(self, topic: str, key: str, payload: dict) -> None:
        """
        Publish a single event to any topic.

        topic   → the Kafka topic name, e.g. "user-logins", "user-logouts",
                  "orders", "notifications" — any topic the broker has
        key     → language key, must be in PARTITION_MAP ("es" or "en")
        payload → the event data as a Python dict — serialized to JSON automatically

        This function is safe to call as asyncio.create_task() — exceptions
        are caught and logged, never propagated to the caller.

        Reuse: this single method handles all event publishing for the entire
        backend. Add a new topic by calling publish_event() with a new topic name.
        No changes to this file needed.
        """
        # Unknown key → discard before touching the producer.
        if key not in self.PARTITION_MAP:
            logger.warning("kafka_event_discarded", topic=topic, key=key, reason="invalid_key")
            return

        # Self-healing path — retries if Redpanda was down at startup or last publish killed it.
        if self._producer is None:
            await self.start()

        if self._producer is None:
            logger.warning("kafka_event_skipped", topic=topic, reason="producer_unavailable")
            return

        try:
            # Explicit partition number — no key bytes sent, no hash involved.
            await self._producer.send_and_wait(
                topic,
                value=payload,
                partition=self.PARTITION_MAP[key],
            )
            logger.info("kafka_event_published", topic=topic, key=key, partition=self.PARTITION_MAP[key])

        except (KafkaConnectionError, KafkaError) as e:
            # Expected failure — mark producer dead so next call triggers lazy reconnect.
            logger.warning(
                "kafka_event_failed",
                topic=topic,
                key=key,
                error=str(e),
                error_type=type(e).__name__,
            )
            self._producer = None

        except Exception as e:
            # Unexpected — bug in serializer, OOM, etc. Full stack trace attached.
            logger.error(
                "kafka_event_unexpected_error",
                topic=topic,
                key=key,
                error=str(e),
                exc_info=True,
            )


# Single shared instance for the entire application.
# Import this object wherever you need to publish events.
kafka_producer = KafkaProducerClient()