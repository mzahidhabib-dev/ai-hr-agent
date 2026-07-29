"""
business_agents/support/knowledge_gap.py

Knowledge Gap & Conflict Detector for Support Agent.

Rules compliance:
  Rule 24 -- Mandatory tenant isolation on all gap detection queries.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from typing import List, Dict, Any
import time
from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import enforce_tenant

logger = get_logger(__name__)

# In-memory store for detected knowledge gaps per tenant
_KNOWLEDGE_GAPS_STORE: List[Dict[str, Any]] = []


@enforce_tenant
def detect_and_log_knowledge_gap(
    tenant_id: str,
    question: str,
    search_confidence: float,
    topic: str = "GENERAL",
    low_confidence_threshold: float = 60.0
) -> Dict[str, Any]:
    """
    Detects when RAG search confidence falls below threshold or when an inquiry is unanswered,
    and logs automated documentation recommendations.
    """
    logger.info("Evaluating knowledge gap for query", extra={"tenant_id": tenant_id, "confidence": search_confidence, "topic": topic})
    
    is_gap = search_confidence <= low_confidence_threshold
    gap_record = {
        "tenant_id": tenant_id,
        "question": question,
        "search_confidence": search_confidence,
        "topic": topic,
        "is_gap_flagged": is_gap,
        "recommendation": f"Draft documentation article addressing '{question}' under topic '{topic}'." if is_gap else "No gap detected.",
        "timestamp": time.time()
    }
    
    if is_gap:
        _KNOWLEDGE_GAPS_STORE.append(gap_record)
        logger.warning(
            "Knowledge gap detected",
            extra={"tenant_id": tenant_id, "question": question, "confidence": search_confidence, "topic": topic}
        )
        
    return gap_record


@enforce_tenant
def get_tenant_knowledge_gaps(tenant_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves tenant-isolated list of identified documentation gaps and recommendations.
    """
    logger.info("Retrieving tenant knowledge gaps", extra={"tenant_id": tenant_id})
    return [gap for gap in _KNOWLEDGE_GAPS_STORE if gap["tenant_id"] == tenant_id]
