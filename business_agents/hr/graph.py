"""
business_agents/hr/graph.py

LangGraph orchestration pipeline for the Enterprise AI HR Agent.

Rules compliance:
  Rule 21 -- Only imports platform_core.sdk, state, nodes, and langgraph.
  Rule 24 -- Enforces tenant isolation.
  Rule 26 -- Zero-tolerance ultra-professional error handling.
"""

from langgraph.graph import StateGraph, START, END

from business_agents.hr.state import HRAgentState
from business_agents.hr.nodes import (
    IntakeNode,
    ClassificationNode,
    KnowledgeRAGNode,
    SensitiveEscalationNode,
    ResponseNode,
    PTOActionNode,
    PayrollIntelligenceNode,
    OnboardingOrchestratorNode,
    OffboardingOrchestratorNode,
    ResolutionVerifierNode,
)
from platform_core.sdk import sdk

logger = sdk.get_logger(__name__)


def route_after_classification(state: HRAgentState) -> str:
    """
    Conditional router after classification:
    - SENSITIVE_CASE -> SensitiveEscalationNode
    - PTO_LEAVE -> PTOActionNode
    - PAYROLL -> PayrollIntelligenceNode
    - ONBOARDING -> OnboardingOrchestratorNode
    - OFFBOARDING -> OffboardingOrchestratorNode
    - Otherwise -> KnowledgeRAGNode
    """
    intent = state.get("intent", "POLICY_QA")
    sensitivity = state.get("sensitivity_level", "NORMAL")

    if intent == "SENSITIVE_CASE" or sensitivity == "HIGH_SENSITIVE":
        logger.warning(
            "Routing to SensitiveEscalationNode",
            extra={"tenant_id": state.get("tenant_id"), "intent": intent},
        )
        return "SensitiveEscalationNode"
    elif intent == "PTO_LEAVE":
        logger.info(
            "Routing to PTOActionNode",
            extra={"tenant_id": state.get("tenant_id"), "intent": intent},
        )
        return "PTOActionNode"
    elif intent == "PAYROLL":
        logger.info(
            "Routing to PayrollIntelligenceNode",
            extra={"tenant_id": state.get("tenant_id"), "intent": intent},
        )
        return "PayrollIntelligenceNode"
    elif intent == "ONBOARDING":
        logger.info(
            "Routing to OnboardingOrchestratorNode",
            extra={"tenant_id": state.get("tenant_id"), "intent": intent},
        )
        return "OnboardingOrchestratorNode"
    elif intent == "OFFBOARDING":
        logger.warning(
            "Routing to OffboardingOrchestratorNode",
            extra={"tenant_id": state.get("tenant_id"), "intent": intent},
        )
        return "OffboardingOrchestratorNode"
    else:
        logger.info(
            "Routing to KnowledgeRAGNode",
            extra={"tenant_id": state.get("tenant_id"), "intent": intent},
        )
        return "KnowledgeRAGNode"


def create_hr_graph():
    """
    Compiles and returns the HR Agent LangGraph workflow.
    """
    builder = StateGraph(HRAgentState)

    # 1. Add Nodes
    builder.add_node("IntakeNode", IntakeNode)
    builder.add_node("ClassificationNode", ClassificationNode)
    builder.add_node("KnowledgeRAGNode", KnowledgeRAGNode)
    builder.add_node("SensitiveEscalationNode", SensitiveEscalationNode)
    builder.add_node("ResponseNode", ResponseNode)
    builder.add_node("PTOActionNode", PTOActionNode)
    builder.add_node("PayrollIntelligenceNode", PayrollIntelligenceNode)
    builder.add_node("OnboardingOrchestratorNode", OnboardingOrchestratorNode)
    builder.add_node("OffboardingOrchestratorNode", OffboardingOrchestratorNode)
    builder.add_node("ResolutionVerifierNode", ResolutionVerifierNode)

    # 2. Add Fixed Edges
    builder.add_edge(START, "IntakeNode")
    builder.add_edge("IntakeNode", "ClassificationNode")

    # 3. Add Conditional Routing
    builder.add_conditional_edges(
        "ClassificationNode",
        route_after_classification,
        {
            "SensitiveEscalationNode": "SensitiveEscalationNode",
            "PTOActionNode": "PTOActionNode",
            "PayrollIntelligenceNode": "PayrollIntelligenceNode",
            "OnboardingOrchestratorNode": "OnboardingOrchestratorNode",
            "OffboardingOrchestratorNode": "OffboardingOrchestratorNode",
            "KnowledgeRAGNode": "KnowledgeRAGNode",
        },
    )

    # 4. Action Verification Edges (Pillar 3 of Truth)
    builder.add_edge("PTOActionNode", "ResolutionVerifierNode")
    builder.add_edge("PayrollIntelligenceNode", "ResolutionVerifierNode")
    builder.add_edge("OnboardingOrchestratorNode", "ResolutionVerifierNode")
    builder.add_edge("OffboardingOrchestratorNode", "ResolutionVerifierNode")

    # 5. Terminal Edges
    builder.add_edge("KnowledgeRAGNode", "ResponseNode")
    builder.add_edge("ResponseNode", END)
    builder.add_edge("ResolutionVerifierNode", END)
    builder.add_edge("SensitiveEscalationNode", END)

    logger.info("Successfully compiled HR Agent LangGraph state machine with Phase 3 routing")
    return builder.compile()
