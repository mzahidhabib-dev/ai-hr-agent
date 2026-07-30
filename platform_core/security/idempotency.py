"""
platform_core/security/idempotency.py

Idempotency & Duplicate-Action Protection Engine for Support Agent.

Ensures that every side-effect tool execution (refunds, plan changes, account actions)
uses a deterministic idempotency key to prevent double dispatches on retries or timeouts.

Rules compliance:
  Rule 24 -- Mandatory tenant isolation on idempotency checks.
  Rule 25 -- Idempotency & duplicate action prevention.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import Dict, Any, Optional
import time
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)

# In-memory store for idempotency keys per tenant
_IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}


def generate_idempotency_key(tenant_id: str, ticket_id: str, action_type: str, request_id: Optional[str] = None) -> str:
    """Generates a deterministic idempotency key."""
    req_str = request_id or "default"
    return f"{tenant_id}:{ticket_id}:{action_type}:{req_str}"


@enforce_tenant
def is_action_already_executed(tenant_id: str, idempotency_key: str) -> bool:
    """Checks if an action with the given idempotency key has already been executed."""
    record = _IDEMPOTENCY_STORE.get(idempotency_key)
    if record and record["tenant_id"] == tenant_id and record["status"] in ["COMPLETED", "EXECUTING"]:
        logger.warning("Duplicate action execution blocked", extra={"tenant_id": tenant_id, "key": idempotency_key})
        return True
    return False


@enforce_tenant
def record_action_execution_start(tenant_id: str, idempotency_key: str, action_type: str, action_params: Dict[str, Any]) -> None:
    """Records the start of an action execution to prevent concurrent duplicate calls."""
    if is_action_already_executed(tenant_id, idempotency_key):
        raise ValueError(f"Idempotency Conflict: Action with key '{idempotency_key}' is already in progress or completed.")
        
    _IDEMPOTENCY_STORE[idempotency_key] = {
        "tenant_id": tenant_id,
        "idempotency_key": idempotency_key,
        "action_type": action_type,
        "action_params": action_params,
        "status": "EXECUTING",
        "started_at": time.time(),
        "completed_at": None,
        "result": None
    }
    logger.info("Recorded action execution start", extra={"tenant_id": tenant_id, "key": idempotency_key})


@enforce_tenant
def record_action_execution_complete(tenant_id: str, idempotency_key: str, result: Dict[str, Any]) -> None:
    """Marks an action execution as successfully completed."""
    record = _IDEMPOTENCY_STORE.get(idempotency_key)
    if record and record["tenant_id"] == tenant_id:
        record["status"] = "COMPLETED"
        record["completed_at"] = time.time()
        record["result"] = result
        logger.info("Recorded action execution complete", extra={"tenant_id": tenant_id, "key": idempotency_key})
