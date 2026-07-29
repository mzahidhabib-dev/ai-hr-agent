"""
business_agents/support/attribution.py

Resolution Attribution Engine for Support Agent.

Determines the true cause of ticket resolution:
  - AI-assisted resolution
  - Human-assisted resolution
  - Incident-resolved
  - Self-resolved
  - Unknown

Rules compliance:
  Rule 24 -- Mandatory tenant isolation on all resolution attributions.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import Dict, Any, Optional
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)


@enforce_tenant
def attribute_ticket_resolution(
    tenant_id: str,
    ticket_id: str,
    ai_handled: bool = True,
    human_handled: bool = False,
    active_incident_id: Optional[str] = None,
    followup_received: bool = False,
    customer_confirmed: bool = False,
    time_to_close_seconds: float = 300.0
) -> Dict[str, Any]:
    """
    Determines resolution attribution classification for a support ticket.
    """
    logger.info("Classifying resolution attribution", extra={"tenant_id": tenant_id, "ticket_id": ticket_id, "ai_handled": ai_handled})
    
    attribution = "Unknown"
    confidence = 80.0
    
    if active_incident_id:
        attribution = "Incident-resolved"
        confidence = 95.0
    elif human_handled:
        attribution = "Human-assisted resolution"
        confidence = 90.0
    elif time_to_close_seconds < 15.0 and not followup_received:
        attribution = "Self-resolved"
        confidence = 75.0
    elif ai_handled:
        attribution = "AI-assisted resolution"
        confidence = 95.0 if customer_confirmed else 85.0
        
    return {
        "tenant_id": tenant_id,
        "ticket_id": ticket_id,
        "attribution": attribution,
        "confidence": confidence,
        "ai_handled": ai_handled,
        "human_handled": human_handled,
        "active_incident_id": active_incident_id
    }
