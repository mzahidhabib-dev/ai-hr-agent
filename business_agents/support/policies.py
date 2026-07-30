"""
business_agents/support/policies.py

Configurable Action Policy Engine & Risk Guardrails for Support Agent.

Rules compliance:
  Rule 24 -- Filters policy rules by tenant_id.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import Dict, Any
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)


class ActionPolicyResult:
    def __init__(self, risk_level: str, approval_status: str, requires_decision_card: bool, reason: str):
        self.risk_level = risk_level  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
        self.approval_status = approval_status  # "AUTONOMOUS", "WAITING_FOR_HUMAN", "IMMEDIATE_ESCALATION"
        self.requires_decision_card = requires_decision_card
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "approval_status": self.approval_status,
            "requires_decision_card": self.requires_decision_card,
            "reason": self.reason
        }


@enforce_tenant
def evaluate_action_policy(tenant_id: str, action_type: str, action_params: Dict[str, Any] = None) -> ActionPolicyResult:
    """
    Evaluates action risk policy based on intent, action type, and financial thresholds.

    Rules:
      1. Refund <= $50: AUTONOMOUS (LOW risk)
      2. Refund $50 - $500: WAITING_FOR_HUMAN (MEDIUM risk - generates Decision Card)
      3. Refund > $500: WAITING_FOR_HUMAN (HIGH risk - mandatory approval)
      4. CANCELLATION / DELETE_ACCOUNT: WAITING_FOR_HUMAN (HIGH risk)
      5. SECURITY_INCIDENT / DB_OUTAGE: IMMEDIATE_ESCALATION (CRITICAL risk)
      6. GENERAL / FAQ / RESEND_INVOICE: AUTONOMOUS (LOW risk)
    """
    if action_params is None:
        action_params = {}
        
    logger.info("Evaluating action policy", extra={"tenant_id": tenant_id, "action_type": action_type, "params": action_params})
    
    action_upper = action_type.upper()
    
    # Security / Production Outage
    if action_upper in ["SECURITY_INCIDENT", "DB_OUTAGE", "INCIDENT"]:
        return ActionPolicyResult(
            risk_level="CRITICAL",
            approval_status="IMMEDIATE_ESCALATION",
            requires_decision_card=True,
            reason="Security or critical production incident requires immediate human escalation."
        )
        
    # Account Cancellation / Deletion
    new_plan = str(action_params.get("new_plan_id", "")).upper()
    if action_upper in ["CANCELLATION", "DELETE_ACCOUNT", "CANCEL_SUBSCRIPTION"] or new_plan in ["DELETE_ACCOUNT", "CANCEL_SUBSCRIPTION", "CANCEL_PLAN"]:
        return ActionPolicyResult(
            risk_level="HIGH",
            approval_status="WAITING_FOR_HUMAN",
            requires_decision_card=True,
            reason="Account deletion or enterprise subscription cancellation requires human approval."
        )
        
    # Refund Financial Threshold Evaluation
    if action_upper in ["REFUND", "PROCESS_REFUND"]:
        amount = float(action_params.get("amount", 0.0))
        if amount <= 50.0:
            return ActionPolicyResult(
                risk_level="LOW",
                approval_status="AUTONOMOUS",
                requires_decision_card=False,
                reason=f"Refund amount ${amount:.2f} is within autonomous threshold ($50 max)."
            )
        elif amount <= 500.0:
            return ActionPolicyResult(
                risk_level="MEDIUM",
                approval_status="WAITING_FOR_HUMAN",
                requires_decision_card=True,
                reason=f"Refund amount ${amount:.2f} requires Human-in-the-Loop decision card review."
            )
        else:
            return ActionPolicyResult(
                risk_level="HIGH",
                approval_status="WAITING_FOR_HUMAN",
                requires_decision_card=True,
                reason=f"Refund amount ${amount:.2f} exceeds $500 threshold and requires mandatory manager approval."
            )
            
    # Default Autonomous Policy
    return ActionPolicyResult(
        risk_level="LOW",
        approval_status="AUTONOMOUS",
        requires_decision_card=False,
        reason="Action is low-risk and authorized for autonomous resolution."
    )
