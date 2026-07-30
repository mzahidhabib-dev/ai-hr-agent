"""
business_agents/support/state.py

The state dictionary that flows through every node of the Support Agent LangGraph pipeline.

Rules compliance:
  Rule 17 -- Only standard library typing imported. No direct DB, LLM, or external drivers.
  Rule 21 -- SDK isolation boundary enforced.
"""

from typing import TypedDict, Optional, List, Dict, Any


class SupportState(TypedDict, total=False):
    """
    The complete state object maintained throughout the Support Agent pipeline execution.
    """
    # Core Metadata & Traceability IDs
    tenant_id: str
    trace_id: Optional[str]
    run_id: Optional[str]
    conversation_id: Optional[str]
    customer_id: Optional[str]
    external_message_id: Optional[str]  # For inbound webhook message deduplication
    
    # Inbound Payload
    inbound_message: str
    channel: Optional[str]
    attachments: Optional[List[Dict[str, Any]]]
    
    # Customer 360 Context (Loaded by CustomerContextNode)
    customer_context: Optional[Dict[str, Any]]
    
    # Classification Results (Set by ClassificationNode)
    intent: Optional[str]           # BILLING, TECHNICAL, ACCOUNT, HOW_TO, BUG, INCIDENT, REFUND, etc.
    severity: Optional[str]         # LOW, MEDIUM, HIGH, CRITICAL
    urgency: Optional[str]          # LOW, MEDIUM, HIGH
    frustration_score: Optional[float]  # 0.0 to 1.0
    churn_risk: Optional[bool]
    
    # Knowledge Retrieval & Diagnosis (Set by KnowledgeRAGNode / DiagnosisNode)
    retrieved_evidence: Optional[List[Dict[str, Any]]]  # Chunks, page numbers, doc sources
    diagnostic_hypotheses: Optional[List[str]]
    
    # Action & Governance (Set by ActionNode)
    suggested_action: Optional[Dict[str, Any]]  # Tool name + parameters
    action_result: Optional[Dict[str, Any]]     # Outcome of tool execution
    decision_id: Optional[int]                  # HITL decision card ID if approval requested
    
    # Final Response & Citations (Set by ResponseNode)
    response_text: Optional[str]
    citations: Optional[List[Dict[str, Any]]]    # Explicit page numbers & document names
    confidence_score: Optional[float]            # 0.0 to 100.0
    
    # Ticket Lifecycle Status (Set by ActionNode / EscalationNode)
    # Values: NEW, CLASSIFIED, INVESTIGATING, WAITING_FOR_CUSTOMER, WAITING_FOR_HUMAN, RESOLVED, CLOSED, REOPENED
    status: Optional[str]
    
    # Error Tracking
    error: Optional[str]
