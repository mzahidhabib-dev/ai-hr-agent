"""
business_agents/support/incidents.py

Support Incident Intelligence & Surge Detector Engine.

Tracks incoming error signals and automatically:
  1. Correlates similar error signatures (e.g., 500_AUTH_FAIL).
  2. Auto-creates Incident object when surge threshold is reached (>=3 matching issues).
  3. Groups affected tickets under active incident.
  4. Provides unified status updates to affected customers.

Rules compliance:
  Rule 24 -- Mandatory tenant isolation on all incident tracking.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import Dict, Any, List, Optional
import time
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)

# In-memory store for error signals and active incidents
_SUPPORT_SIGNALS_STORE: List[Dict[str, Any]] = []
_ACTIVE_INCIDENTS_STORE: Dict[str, Dict[str, Any]] = {}
_SURGE_THRESHOLD: int = 3  # Threshold count to trigger an incident


@enforce_tenant
def record_inbound_support_signal(
    tenant_id: str,
    ticket_id: str,
    issue_topic: str,
    error_signature: str
) -> Optional[Dict[str, Any]]:
    """
    Records inbound ticket error signal and evaluates if incident surge threshold is triggered.
    """
    logger.info("Recording inbound support signal", extra={"tenant_id": tenant_id, "ticket_id": ticket_id, "signature": error_signature})
    
    signal = {
        "tenant_id": tenant_id,
        "ticket_id": ticket_id,
        "issue_topic": issue_topic,
        "error_signature": error_signature,
        "timestamp": time.time()
    }
    _SUPPORT_SIGNALS_STORE.append(signal)
    
    # Evaluate surge over matching error_signature for tenant within last 15 mins (900s)
    now = time.time()
    matching_signals = [
        s for s in _SUPPORT_SIGNALS_STORE
        if s["tenant_id"] == tenant_id
        and s["error_signature"] == error_signature
        and (now - s["timestamp"]) <= 900.0
    ]
    
    if len(matching_signals) >= _SURGE_THRESHOLD:
        incident_key = f"{tenant_id}:{error_signature}"
        if incident_key not in _ACTIVE_INCIDENTS_STORE:
            incident = {
                "incident_id": f"INC-{int(now)}",
                "tenant_id": tenant_id,
                "error_signature": error_signature,
                "issue_topic": issue_topic,
                "status": "OPEN",
                "affected_tickets": [s["ticket_id"] for s in matching_signals],
                "created_at": now
            }
            _ACTIVE_INCIDENTS_STORE[incident_key] = incident
            logger.warning("Automated Incident Triggered!", extra={"tenant_id": tenant_id, "incident_id": incident["incident_id"], "signature": error_signature})
            return incident
        else:
            # Append ticket to existing active incident
            incident = _ACTIVE_INCIDENTS_STORE[incident_key]
            if ticket_id not in incident["affected_tickets"]:
                incident["affected_tickets"].append(ticket_id)
            return incident
            
    return None


@enforce_tenant
def get_active_incidents(tenant_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves tenant-isolated list of active platform incidents.
    """
    logger.info("Retrieving active incidents", extra={"tenant_id": tenant_id})
    return [inc for inc in _ACTIVE_INCIDENTS_STORE.values() if inc["tenant_id"] == tenant_id and inc["status"] == "OPEN"]
