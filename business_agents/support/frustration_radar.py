"""
business_agents/support/frustration_radar.py

Customer Frustration Intelligence & Churn Radar Engine.

Rules compliance:
  Rule 24 -- Enforces tenant isolation on all customer sentiment tracking.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import List, Dict, Any
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)

ANGER_KEYWORDS = [
    "unacceptable", "furious", "terrible", "garbage", "horrible",
    "waste of time", "lawsuit", "lawyer", "ridiculous", "disaster",
    "scam", "frustrated", "angry", "broken", "useless", "absurd"
]

CANCELLATION_KEYWORDS = [
    "cancel", "cancellation", "closing account", "terminate",
    "leaving for competitor", "switch to", "unsubscribe", "stop service"
]


class FrustrationAnalysisResult:
    def __init__(self, frustration_score: float, churn_risk: bool, urgency_boost: str, reasons: List[str]):
        self.frustration_score = max(0.0, min(1.0, frustration_score))
        self.churn_risk = churn_risk
        self.urgency_boost = urgency_boost  # "NONE", "HIGH", "CRITICAL"
        self.reasons = reasons

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frustration_score": self.frustration_score,
            "churn_risk": self.churn_risk,
            "urgency_boost": self.urgency_boost,
            "reasons": self.reasons
        }


@enforce_tenant
def analyze_frustration_and_churn_risk(
    tenant_id: str,
    inbound_message: str,
    conversation_history: List[str] = None
) -> FrustrationAnalysisResult:
    """
    Analyzes inbound customer message and conversation history for frustration, anger keywords,
    repeated failed solution loops, and churn risk.
    """
    if conversation_history is None:
        conversation_history = []
        
    logger.info("Analyzing customer frustration and churn risk", extra={"tenant_id": tenant_id, "history_len": len(conversation_history)})
    
    message_lower = inbound_message.lower()
    reasons = []
    base_score = 0.10
    churn_risk = False
    urgency_boost = "NONE"
    
    # 1. Anger Keyword Analysis
    matched_anger = [kw for kw in ANGER_KEYWORDS if kw in message_lower]
    if matched_anger:
        base_score += len(matched_anger) * 0.25
        reasons.append(f"Frustration keywords detected: {', '.join(matched_anger)}")
        
    # 2. Cancellation / Churn Risk Detection
    matched_cancellation = [kw for kw in CANCELLATION_KEYWORDS if kw in message_lower]
    if matched_cancellation:
        churn_risk = True
        base_score += 0.40
        reasons.append(f"Cancellation intent detected: {', '.join(matched_cancellation)}")
        
    # 3. Repeated Question / Conversation Loop Penalty
    if len(conversation_history) >= 3:
        base_score += 0.20
        reasons.append("Multi-turn conversation without resolution detected.")
    if len(conversation_history) >= 5:
        base_score += 0.25
        reasons.append("High conversation turn count indicates persistent customer struggle.")
        
    # Cap score between 0.0 and 1.0
    final_score = round(max(0.0, min(1.0, base_score)), 2)
    
    # Calculate Urgency Boost
    if churn_risk or final_score >= 0.8:
        urgency_boost = "CRITICAL"
    elif final_score >= 0.5:
        urgency_boost = "HIGH"
        
    return FrustrationAnalysisResult(
        frustration_score=final_score,
        churn_risk=churn_risk,
        urgency_boost=urgency_boost,
        reasons=reasons
    )
