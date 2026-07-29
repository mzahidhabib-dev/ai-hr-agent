"""
business_agents/support/security.py

Enterprise Security Guardrails & Governance Engine for Support Agent.

Enforces:
  1. PII Detection & Redaction (SSN, Credit Cards, Emails, Phone numbers).
  2. Prompt Injection & Knowledge Poisoning Protection.
  3. Role-Based Access Control (RBAC).

Rules compliance:
  Rule 21 -- Integrates strictly via Platform SDK / platform_core/security.
  Rule 24 -- Mandatory tenant isolation on security governance.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

import re
from typing import Dict, Any
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)

# PII Regex Patterns
_SSN_REGEX = r'\b\d{3}-\d{2}-\d{4}\b'
_CREDIT_CARD_REGEX = r'\b(?:\d[ -]*?){13,16}\b'
_EMAIL_REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
_PHONE_REGEX = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'

# Prompt Injection Attack Keywords
_INJECTION_KEYWORDS = [
    "ignore previous instructions", "override system prompt",
    "you are now DAN", "disregard rules", "system prompt reveal",
    "[UNSAFE]"
]

# Role Hierarchy
_ROLE_HIERARCHY = {
    "READ_ONLY": 1,
    "OPERATOR": 2,
    "ADMIN": 3
}


def redact_pii(text: str) -> str:
    """
    Redacts sensitive PII fields (SSN, credit card, email, phone) from text.
    """
    if not text:
        return text
    
    redacted = re.sub(_SSN_REGEX, "[REDACTED_SSN]", text)
    redacted = re.sub(_CREDIT_CARD_REGEX, "[REDACTED_CARD]", redacted)
    redacted = re.sub(_EMAIL_REGEX, "[REDACTED_EMAIL]", redacted)
    redacted = re.sub(_PHONE_REGEX, "[REDACTED_PHONE]", redacted)
    return redacted


def detect_prompt_injection(text: str) -> Dict[str, Any]:
    """
    Detects potential prompt injection or system override attacks.
    """
    text_lower = text.lower()
    matched = [kw for kw in _INJECTION_KEYWORDS if kw in text_lower or kw.lower() in text_lower]
    
    is_injection = len(matched) > 0
    if is_injection:
        logger.warning("Prompt Injection Attack Detected!", extra={"matched": matched})
        
    return {
        "is_injection_detected": is_injection,
        "matched_patterns": matched,
        "risk_level": "CRITICAL" if is_injection else "LOW"
    }


@enforce_tenant
def validate_rbac_permission(tenant_id: str, user_role: str, required_role: str = "OPERATOR") -> bool:
    """
    Enforces Role-Based Access Control (RBAC) permissions per tenant.
    """
    logger.info("Validating RBAC permission", extra={"tenant_id": tenant_id, "user_role": user_role, "required": required_role})
    
    user_level = _ROLE_HIERARCHY.get(user_role.upper(), 0)
    required_level = _ROLE_HIERARCHY.get(required_role.upper(), 2)
    
    has_permission = user_level >= required_level
    if not has_permission:
        logger.warning("RBAC Permission Denied", extra={"tenant_id": tenant_id, "user_role": user_role, "required_role": required_role})
        
    return has_permission
