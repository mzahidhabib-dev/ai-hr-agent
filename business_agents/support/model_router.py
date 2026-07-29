"""
business_agents/support/model_router.py

Complexity & Risk-Based Dynamic Model Router for Support Agent.

Routes tasks dynamically:
  1. Low Complexity / Simple FAQ -> Fast low-cost model (Groq Llama 3.1 8B / Gemini Flash)
  2. Technical Diagnosis / Complex Reasoning -> Reasoning model (Groq Llama 3.3 70B / Gemini Pro / GPT-4o)
  3. High-Risk Action -> Reasoning model + Mandatory HITL Approval Queue

Rules compliance:
  Rule 21 -- Connects to platform_core/ai_gateway.py via SDK.
  Rule 24 -- Mandatory tenant isolation on model routing.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import Dict, Any
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)


@enforce_tenant
def select_support_model(
    tenant_id: str,
    intent: str,
    severity: str = "LOW",
    risk_level: str = "LOW",
    prompt_token_count: int = 200
) -> Dict[str, Any]:
    """
    Selects optimal AI model and provider based on task complexity, severity, and risk level.
    """
    logger.info("Routing dynamic AI model", extra={"tenant_id": tenant_id, "intent": intent, "severity": severity, "risk": risk_level})
    
    intent_upper = intent.upper()
    severity_upper = severity.upper()
    risk_upper = risk_level.upper()
    
    requires_hitl = False
    
    # 1. High Risk / Financially Sensitive Actions
    if risk_upper in ["HIGH", "MANDATORY_HUMAN"] or intent_upper in ["REFUND", "CANCEL_ACCOUNT", "SECURITY"]:
        provider = "groq"
        model_name = "llama-3.3-70b-versatile"
        fallback_provider = "openai"
        requires_hitl = True
        tier = "HIGH_RISK_ENTERPRISE"
    # 2. Technical Diagnosis / High Complexity Reasoning
    elif intent_upper == "TECHNICAL" or severity_upper in ["HIGH", "CRITICAL"] or prompt_token_count > 1500:
        provider = "groq"
        model_name = "llama-3.3-70b-versatile"
        fallback_provider = "gemini"
        requires_hitl = False
        tier = "HIGH_REASONING"
    # 3. Simple FAQ / Low Risk Inquiries
    else:
        provider = "groq"
        model_name = "llama-3.1-8b-instant"
        fallback_provider = "gemini"
        requires_hitl = False
        tier = "FAST_LOW_COST"
        
    return {
        "tenant_id": tenant_id,
        "provider": provider,
        "model_name": model_name,
        "fallback_provider": fallback_provider,
        "requires_hitl": requires_hitl,
        "tier": tier
    }
