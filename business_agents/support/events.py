"""
business_agents/support/events.py

Canonical Support Outcome Event Publisher for Support Agent.

Publishes the single source of truth canonical SupportOutcomeEvent payload consumed by:
  - Evaluation Engine (Answer Truth, Action Truth, Outcome Truth)
  - Quiet Failure & Silent Escalation Detector
  - AI FinOps Budget Controls
  - Automated Operations Reporter
  - Incident Intelligence Cluster Detector
  - Continuous Improvement Engine

Rules compliance:
  Rule 21 -- Integrates strictly via Platform SDK events layer.
  Rule 24 -- Mandatory tenant isolation on all outcome events.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant
from platform_core.sdk import sdk

logger = get_logger(__name__)


@enforce_tenant
def publish_support_outcome_event(
    tenant_id: str,
    ticket_id: str,
    customer_id: str,
    initial_intent: str,
    severity: str,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    ai_handled: bool = True,
    human_handled: bool = False,
    actions_taken: List[str] = None,
    escalation: bool = False,
    stated_resolution: bool = True,
    verified_resolution: bool = False,
    reopened: bool = False,
    repeat_contact: bool = False,
    resolution_attribution: str = "AI-assisted resolution",
    ai_cost: float = 0.002,
    human_intervention: bool = False,
    final_outcome: str = "RESOLVED"
) -> Dict[str, Any]:
    """
    Constructs and publishes the canonical SupportOutcomeEvent to the Event Bus.
    """
    if actions_taken is None:
        actions_taken = []
        
    trace_id = trace_id or f"tr-{uuid.uuid4().hex[:12]}"
    run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    conversation_id = conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
        
    logger.info(
        "Publishing canonical SupportOutcomeEvent",
        extra={
            "tenant_id": tenant_id,
            "ticket_id": ticket_id,
            "trace_id": trace_id,
            "run_id": run_id,
            "conversation_id": conversation_id,
            "outcome": final_outcome
        }
    )
    
    payload = {
        "ticket_id": ticket_id,
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "conversation_id": conversation_id,
        "initial_intent": initial_intent,
        "severity": severity,
        "ai_handled": ai_handled,
        "human_handled": human_handled,
        "actions_taken": actions_taken,
        "escalation": escalation,
        "stated_resolution": stated_resolution,
        "verified_resolution": verified_resolution,
        "reopened": reopened,
        "repeat_contact": repeat_contact,
        "resolution_attribution": resolution_attribution,
        "ai_cost": ai_cost,
        "human_intervention": human_intervention,
        "final_outcome": final_outcome,
        "timestamp": time.time()
    }
    
    try:
        sdk.events.publish(
            event_type="support.outcome",
            payload=payload,
            tenant_id=tenant_id
        )
        return payload
    except Exception as e:
        logger.error("Failed to publish SupportOutcomeEvent", extra={"tenant_id": tenant_id, "ticket_id": ticket_id, "error": str(e)})
        raise e
