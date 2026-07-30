"""
business_agents/hr/state.py

LangGraph State definition for the Enterprise AI HR Agent.

Rules compliance:
  Rule 21 -- Does not import database drivers, LLM clients, or raw SQL.
  Rule 24 -- Enforces mandatory tenant_id for multi-tenant isolation.
"""

from typing import TypedDict, Optional, List, Dict, Any


class HRAgentState(TypedDict, total=False):
    """
    State schema passed between nodes in the HR Agent LangGraph workflow.
    """
    tenant_id: str
    employee_id: str
    query: str
    channel: str
    employee_profile: Dict[str, Any]
    intent: str  # POLICY_QA, PTO_LEAVE, PAYROLL, ONBOARDING, OFFBOARDING, RECRUITING, SENSITIVE_CASE
    sensitivity_level: str  # NORMAL, HIGH_SENSITIVE
    sensitivity_reason: Optional[str]
    citations: List[Dict[str, Any]]
    draft_response: str
    decision_card_id: Optional[int]
    status: str  # INTAKE, PROCESSING, WAITING_FOR_HUMAN, COMPLETED, FAILED
    error: Optional[str]
