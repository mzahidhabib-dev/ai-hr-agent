"""
platform_core/events.py

Event bus: publishes events to Redis Pub/Sub and writes to the Postgres events table.

Rules compliance:
  Rule 9  -- Both r.publish() and the DB write are wrapped in try/except.
             Redis publish failures are logged gracefully with DB fallback so local test runs don't crash when Redis isn't running.
  Rule 10 -- All log lines use structured JSON via get_logger().
"""

import json
import redis
from platform_core.logging_config import get_logger
from platform_core.security.secrets import get_secret

logger = get_logger(__name__)

REDIS_HOST = get_secret("REDIS_HOST", "localhost")
REDIS_PORT = int(get_secret("REDIS_PORT", "6379"))

# Pub/Sub Redis Client
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=2)

VALID_EVENTS = {
    "prospect.found",
    "decision_maker.found",
    "research.completed",
    "score.completed",
    "buying_signal.detected",
    "outreach.generated",
    "email.sent",
    "followup.triggered",
    "meeting.booked",
    "crm.updated",
    "approval.requested",
    "approval.granted",
    "approval.rejected",
    "workflow.failed",
    "decision.recorded"
}
from platform_core.security.tenant_isolation import enforce_tenant

@enforce_tenant
def publish(tenant_id: str, event_type: str, payload: dict) -> None:
    """
    Publish an event to Redis Pub/Sub and write to the Postgres events table.

    Args:
        tenant_id:  Tenant identifier.
        event_type: One of the VALID_EVENTS strings.
        payload:    Arbitrary dict to attach to the event.
    """
    if event_type not in VALID_EVENTS:
        logger.warning(
            "Unknown event type published",
            extra={"tenant_id": tenant_id, "event_type": event_type}
        )

    event_data = {
        "tenant_id": tenant_id,
        "event_type": event_type,
        "payload": payload
    }

    # 1. Publish to Redis Pub/Sub (with graceful fallback if Redis is offline)
    channel = f"events:{tenant_id}"
    try:
        r.publish(channel, json.dumps(event_data))
        logger.info(
            "Event published to Redis",
            extra={"tenant_id": tenant_id, "event_type": event_type, "channel": channel}
        )
    except Exception as e:
        logger.warning(
            "Redis pub/sub unavailable. Falling back to DB event store.",
            extra={
                "tenant_id": tenant_id,
                "event_type": event_type,
                "channel": channel,
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )

    # 2. Write to events table
    _write_event_to_db(tenant_id, event_type, payload)


def _write_event_to_db(tenant_id: str, event_type: str, payload: dict):
    from platform_core.db import get_connection
    import json
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (tenant_id, event_type, payload) VALUES (%s, %s, %s)",
            (tenant_id, event_type, json.dumps(payload))
        )
        conn.commit()
    except Exception as e:
        logger.error(
            "Failed to write event to DB",
            extra={
                "tenant_id": tenant_id,
                "event_type": event_type,
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def subscribe(tenant_id: str, callback):
    """
    Subscribe to the event bus and pass events to the callback.
    This blocks the thread, so it should be run in a background worker.
    """
    channel = f"events:{tenant_id}"
    pubsub = r.pubsub()
    pubsub.subscribe(channel)
    
    logger.info("Subscribed to Event Bus", extra={"channel": channel})
    
    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                callback(data)
            except Exception as e:
                logger.error(
                    "Error processing event from bus",
                    extra={
                        "channel": channel,
                        "exc_type": type(e).__name__,
                        "error": str(e)
                    }
                )
