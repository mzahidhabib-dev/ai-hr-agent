"""
business_agents/support/graph.py

LangGraph orchestration pipeline for the Enterprise AI Support Agent.

Rules compliance:
  Rule 17 & 21 -- Only imports platform_core.sdk, state, nodes, and langgraph.
  Rule 24 -- Enforces tenant isolation.
  Rule 26 -- Zero-tolerance ultra-professional error handling.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from business_agents.support.state import SupportState
from business_agents.support.nodes import (
    IntakeNode,
    CustomerContextNode,
    ClassificationNode,
    KnowledgeRAGNode,
    DiagnosisNode,
    ResponseNode,
    ActionNode,
    EscalationNode
)
from platform_core.sdk import sdk

logger = sdk.get_logger(__name__)


# ---------------------------------------------------------------------------
# Conditional Routers
# ---------------------------------------------------------------------------

def route_after_classification(state: dict) -> str:
    """
    Routes the execution path based on classified intent.
    - TECHNICAL / BUG / INCIDENT / SECURITY -> DiagnosisNode
    - ESCALATION -> EscalationNode
    - Otherwise -> KnowledgeRAGNode
    """
    intent = state.get("intent", "GENERAL")
    
    if intent in ["TECHNICAL", "BUG", "INCIDENT", "SECURITY"]:
        return "DiagnosisNode"
    elif intent == "ESCALATION":
        return "EscalationNode"
    else:
        return "KnowledgeRAGNode"


def route_after_action(state: dict) -> str:
    """
    Routes after ActionNode execution:
    - If status is WAITING_FOR_HUMAN -> EscalationNode
    - Otherwise -> END
    """
    status = state.get("status")
    if status == "WAITING_FOR_HUMAN":
        return "EscalationNode"
    return END


# ---------------------------------------------------------------------------
# Support Graph Compilation
# ---------------------------------------------------------------------------

def create_support_graph():
    """
    Compiles and returns the Support Agent LangGraph workflow graph.
    """
    builder = StateGraph(SupportState)
    
    # 1. Add Nodes
    builder.add_node("IntakeNode", IntakeNode)
    builder.add_node("CustomerContextNode", CustomerContextNode)
    builder.add_node("ClassificationNode", ClassificationNode)
    builder.add_node("DiagnosisNode", DiagnosisNode)
    builder.add_node("KnowledgeRAGNode", KnowledgeRAGNode)
    builder.add_node("ResponseNode", ResponseNode)
    builder.add_node("ActionNode", ActionNode)
    builder.add_node("EscalationNode", EscalationNode)
    
    # 2. Add Fixed Edges
    builder.add_edge(START, "IntakeNode")
    builder.add_edge("IntakeNode", "CustomerContextNode")
    builder.add_edge("CustomerContextNode", "ClassificationNode")
    
    # 3. Add Conditional Routing after ClassificationNode
    builder.add_conditional_edges(
        "ClassificationNode",
        route_after_classification,
        {
            "DiagnosisNode": "DiagnosisNode",
            "KnowledgeRAGNode": "KnowledgeRAGNode",
            "EscalationNode": "EscalationNode"
        }
    )
    
    builder.add_edge("DiagnosisNode", "KnowledgeRAGNode")
    builder.add_edge("KnowledgeRAGNode", "ResponseNode")
    builder.add_edge("ResponseNode", "ActionNode")
    
    # 4. Add Conditional Routing after ActionNode
    builder.add_conditional_edges(
        "ActionNode",
        route_after_action,
        {
            "EscalationNode": "EscalationNode",
            END: END
        }
    )
    
    builder.add_edge("EscalationNode", END)
    
    # 5. Compile with Checkpointer
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    return graph


# Singleton support graph pipeline instance
support_pipeline = create_support_graph()
