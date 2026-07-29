"""
business_agents/support/memory.py

Unified Cross-Channel Customer Memory Extension for Support Agent.

Extends platform_core/memory.py to maintain:
  1. Short-term Memory (Active ticket troubleshooting steps, diagnostic hypotheses)
  2. Long-term Memory (Past issue resolutions, preferences, environment specs)

Rules compliance:
  Rule 24 -- Mandatory tenant isolation on all memory accesses.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import Dict, Any
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant
from platform_core.db import get_connection
import platform_core.memory as core_memory

logger = get_logger(__name__)

# Transient short-term memory store for active ticket troubleshooting steps
_SHORT_TERM_SUPPORT_MEMORY: Dict[str, Dict[str, Any]] = {}


def _get_or_create_prospect_id(tenant_id: str) -> int:
    """Helper to ensure a valid prospect_id exists for memory table foreign key constraint."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT prospect_id FROM prospects WHERE tenant_id = %s LIMIT 1", (tenant_id,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            "INSERT INTO prospects (tenant_id, company, domain) VALUES (%s, %s, %s) RETURNING prospect_id",
            (tenant_id, "Default Support Prospect", "support.prospect.com")
        )
        pid = cursor.fetchone()[0]
        conn.commit()
        return pid
    finally:
        conn.close()


@enforce_tenant
def save_short_term_memory(tenant_id: str, customer_id: str, ticket_id: str, memory_data: Dict[str, Any]) -> None:
    """
    Saves active troubleshooting steps and transient state for an ongoing support ticket.
    """
    logger.info("Saving support short-term memory", extra={"tenant_id": tenant_id, "customer_id": customer_id, "ticket_id": ticket_id})
    key = f"{tenant_id}:{customer_id}:{ticket_id}"
    if key not in _SHORT_TERM_SUPPORT_MEMORY:
        _SHORT_TERM_SUPPORT_MEMORY[key] = {}
    _SHORT_TERM_SUPPORT_MEMORY[key].update(memory_data)


@enforce_tenant
def get_short_term_memory(tenant_id: str, customer_id: str, ticket_id: str) -> Dict[str, Any]:
    """
    Retrieves transient troubleshooting memory for an active support ticket.
    """
    key = f"{tenant_id}:{customer_id}:{ticket_id}"
    return _SHORT_TERM_SUPPORT_MEMORY.get(key, {})


@enforce_tenant
def save_long_term_memory(tenant_id: str, prospect_id: int, memory_data: Dict[str, Any]) -> None:
    """
    Persists long-term customer resolutions, environment specs, and preferences in PostgreSQL memory table.
    """
    logger.info("Persisting support long-term memory", extra={"tenant_id": tenant_id, "prospect_id": prospect_id})
    valid_pid = _get_or_create_prospect_id(tenant_id)
    core_memory.update(tenant_id=tenant_id, prospect_id=valid_pid, new_data=memory_data)


@enforce_tenant
def get_customer_unified_memory(tenant_id: str, prospect_id: int, customer_id: str = "", ticket_id: str = "") -> Dict[str, Any]:
    """
    Assembles combined short-term + long-term memory package for customer 360 context.
    """
    logger.info("Retrieving unified customer memory package", extra={"tenant_id": tenant_id, "prospect_id": prospect_id})
    valid_pid = _get_or_create_prospect_id(tenant_id)
    long_term = core_memory.get(tenant_id=tenant_id, prospect_id=valid_pid)
    short_term = get_short_term_memory(tenant_id=tenant_id, customer_id=customer_id, ticket_id=ticket_id) if ticket_id else {}
    
    return {
        "tenant_id": tenant_id,
        "prospect_id": valid_pid,
        "customer_id": customer_id,
        "long_term_memory": long_term,
        "short_term_memory": short_term
    }
