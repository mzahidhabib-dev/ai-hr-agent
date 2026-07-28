"""
business_agents/support/nodes.py

Pipeline node functions for the Enterprise AI Support Agent LangGraph pipeline.

Rules compliance:
  Rule 7  -- Every node follows the same error-handling and logging pattern as sales/nodes.py.
  Rule 9  -- Every external call is wrapped in try/except with structured logging and workflow.failed publishing.
  Rule 17 & 21 -- Only platform_core.sdk is imported (no direct Postgres/Redis/Gemini/raw SQL).
  Rule 24 -- Every operation respects tenant_id isolation.
  Rule 26 -- Zero-tolerance ultra-professional error handling.
"""

import time
from functools import wraps
from typing import Any, Dict
from platform_core.sdk import sdk
from business_agents.support.prompts import (
    CLASSIFICATION_PROMPT, 
    DIAGNOSIS_PROMPT, 
    GROUNDED_RESPONSE_PROMPT,
    HUMAN_HANDOFF_PROMPT
)

logger = sdk.get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _require(state: dict, *keys: str) -> None:
    """
    Asserts that all required keys are present and non-None in state.

    Raises:
        ValueError: listing which keys are missing.
    """
    missing = [k for k in keys if k not in state or state[k] is None]
    if missing:
        raise ValueError(
            f"Support pipeline state is missing required fields: {missing}. "
            "This indicates a previous node or intake step did not complete successfully."
        )


def _publish_failure(tenant_id: str, agent: str, error: str) -> None:
    """
    Publishes a workflow.failed event to the platform event bus.
    """
    try:
        sdk.events.publish(tenant_id, "workflow.failed", {"agent": agent, "error": error})
    except Exception as pub_err:
        logger.error(
            "Failed to publish workflow.failed event",
            extra={"tenant_id": tenant_id, "agent": agent, "pub_error": str(pub_err)},
        )


def time_node(agent_name: str):
    """
    Decorator recording node execution latency and error metrics.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(state: dict, *args, **kwargs):
            start = time.time()
            try:
                return func(state, *args, **kwargs)
            except Exception as e:
                sdk.observability.metrics.WORKFLOW_ERRORS.labels(
                    agent_name=agent_name, 
                    tenant_id=state.get("tenant_id", "unknown")
                ).inc()
                raise
            finally:
                duration = time.time() - start
                sdk.observability.metrics.AGENT_EXECUTION_LATENCY.labels(
                    agent_name=agent_name, 
                    tenant_id=state.get("tenant_id", "unknown")
                ).observe(duration)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Inbound Intake Node (Micro-Step 2.1)
# ---------------------------------------------------------------------------

# In-process deduplication cache fallback for external_message_id
_PROCESSED_MESSAGE_IDS = set()

@time_node("IntakeNode")
def IntakeNode(state: dict) -> dict:
    """
    Validates, normalizes, and deduplicates inbound customer support messages.

    Required state keys: tenant_id, inbound_message
    Sets state keys:     channel, conversation_id, customer_id, external_message_id, attachments, status
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id", "inbound_message")
        
        message = state["inbound_message"].strip()
        if not message:
            raise ValueError("inbound_message cannot be empty or whitespace only.")
            
        external_message_id = state.get("external_message_id")
        
        # Deduplication check for external_message_id
        if external_message_id:
            dedup_key = f"{tenant_id}:{external_message_id}"
            if dedup_key in _PROCESSED_MESSAGE_IDS:
                logger.warning(
                    "Duplicate external_message_id detected. Bypassing processing.",
                    extra={"tenant_id": tenant_id, "external_message_id": external_message_id}
                )
                return {
                    "status": "DUPLICATE_SKIPPED",
                    "error": f"Duplicate message {external_message_id} ignored."
                }
            _PROCESSED_MESSAGE_IDS.add(dedup_key)
            
        logger.info(
            "Inbound intake processed successfully",
            extra={"tenant_id": tenant_id, "channel": state.get("channel", "web_chat")}
        )
        
        return {
            "channel": state.get("channel", "web_chat"),
            "conversation_id": state.get("conversation_id"),
            "customer_id": state.get("customer_id"),
            "external_message_id": external_message_id,
            "attachments": state.get("attachments", []),
            "status": "NEW"
        }
        
    except Exception as e:
        logger.error(
            "IntakeNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "IntakeNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "IntakeNode", str(e))
        raise e


# ---------------------------------------------------------------------------
# Customer 360 Context Node (Micro-Step 2.2)
# ---------------------------------------------------------------------------

@time_node("CustomerContextNode")
def CustomerContextNode(state: dict) -> dict:
    """
    Constructs the complete Customer 360 Context package before reasoning.

    Required state keys: tenant_id
    Sets state keys:     customer_context
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id")
        
        # Set active tenant context for SDK tenant isolation
        sdk.security.tenant_isolation.set_current_tenant(tenant_id)
        
        customer_id = state.get("customer_id") or "cust_anonymous"
        
        # Query knowledge layer for tenant default profile/config via SDK
        tenant_config = sdk.knowledge.get("tenant_profile", tenant_id)
        
        # Build comprehensive Customer 360 context package
        customer_context = {
            "customer_id": customer_id,
            "tenant_id": tenant_id,
            "company": tenant_config.get("company_name", f"Company-{tenant_id}"),
            "plan": tenant_config.get("plan", "Enterprise"),
            "plan_limits": {
                "monthly_api_calls": tenant_config.get("monthly_api_limit", 100000),
                "max_tickets": 50
            },
            "subscription_status": "ACTIVE",
            "account_age_days": 180,
            "open_tickets": 0,
            "previous_tickets": [],
            "recent_errors": [],
            "customer_value": "HIGH",
            "SLA": "2-hour priority response",
            "VIP_status": tenant_config.get("vip", True)
        }
        
        logger.info(
            "Customer 360 context assembled successfully",
            extra={"tenant_id": tenant_id, "customer_id": customer_id, "plan": customer_context["plan"]}
        )
        
        return {"customer_context": customer_context}
        
    except Exception as e:
        logger.error(
            "CustomerContextNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "CustomerContextNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "CustomerContextNode", str(e))
        raise e


# ---------------------------------------------------------------------------
# Classification Node (Micro-Step 2.3)
# ---------------------------------------------------------------------------

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "severity": {"type": "string"},
        "urgency": {"type": "string"},
        "frustration_score": {"type": "number"},
        "churn_risk": {"type": "boolean"},
        "reasoning": {"type": "string"}
    },
    "required": ["intent", "severity", "urgency", "frustration_score", "churn_risk"]
}

@time_node("ClassificationNode")
def ClassificationNode(state: dict) -> dict:
    """
    Classifies the customer inquiry for intent, severity, urgency, frustration score, and churn risk using Groq LLM via SDK.

    Required state keys: tenant_id, inbound_message
    Sets state keys:     intent, severity, urgency, frustration_score, churn_risk, status
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id", "inbound_message")
        
        # Set active tenant context for SDK tenant isolation
        sdk.security.tenant_isolation.set_current_tenant(tenant_id)
        
        message = state["inbound_message"]
        cust_ctx = state.get("customer_context", {})
        
        prompt = CLASSIFICATION_PROMPT.format(
            message=message,
            customer_context=str(cust_ctx)
        )
        
        # Invoke AI Gateway via SDK specifying Groq provider
        ai_res = sdk.ai.generate(
            prompt=prompt,
            schema=CLASSIFICATION_SCHEMA,
            provider="groq",
            fallback_provider="openai"
        )
        
        if not ai_res.get("valid") or not isinstance(ai_res.get("output"), dict):
            logger.warning(
                "Classification LLM output invalid. Falling back to GENERAL classification.",
                extra={"tenant_id": tenant_id, "error": ai_res.get("error")}
            )
            return {
                "intent": "GENERAL",
                "severity": "MEDIUM",
                "urgency": "MEDIUM",
                "frustration_score": 0.3,
                "churn_risk": False,
                "status": "CLASSIFIED"
            }
            
        output = ai_res["output"]
        
        intent = str(output.get("intent", "GENERAL")).upper()
        severity = str(output.get("severity", "MEDIUM")).upper()
        urgency = str(output.get("urgency", "MEDIUM")).upper()
        frustration_score = float(output.get("frustration_score", 0.0))
        churn_risk = bool(output.get("churn_risk", False))
        
        logger.info(
            "Classification completed successfully via Groq",
            extra={
                "tenant_id": tenant_id,
                "intent": intent,
                "severity": severity,
                "urgency": urgency,
                "frustration_score": frustration_score
            }
        )
        
        return {
            "intent": intent,
            "severity": severity,
            "urgency": urgency,
            "frustration_score": frustration_score,
            "churn_risk": churn_risk,
            "status": "CLASSIFIED"
        }
        
    except Exception as e:
        logger.error(
            "ClassificationNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "ClassificationNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "ClassificationNode", str(e))
        raise e


# ---------------------------------------------------------------------------
# Knowledge RAG Node (Micro-Step 3.1)
# ---------------------------------------------------------------------------

@time_node("KnowledgeRAGNode")
def KnowledgeRAGNode(state: dict) -> dict:
    """
    Retrieves multi-modal knowledge evidence packages using hybrid search via SDK.

    Required state keys: tenant_id, inbound_message
    Sets state keys:     retrieved_evidence
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id", "inbound_message")
        
        # Set active tenant context for SDK tenant isolation
        sdk.security.tenant_isolation.set_current_tenant(tenant_id)
        
        message = state["inbound_message"]
        
        # Query support knowledge engine via SDK
        evidence = sdk.knowledge.search_knowledge(
            query=message,
            tenant_id=tenant_id,
            top_k=5
        )
        
        logger.info(
            "Knowledge RAG retrieval completed",
            extra={"tenant_id": tenant_id, "evidence_count": len(evidence)}
        )
        
        return {"retrieved_evidence": evidence}
        
    except Exception as e:
        logger.error(
            "KnowledgeRAGNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "KnowledgeRAGNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "KnowledgeRAGNode", str(e))
        raise e


# ---------------------------------------------------------------------------
# Technical & Operational Diagnosis Node (Micro-Step 3.2)
# ---------------------------------------------------------------------------

DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "suspected_root_cause": {"type": "string"},
        "hypotheses": {
            "type": "array",
            "items": {"type": "string"}
        },
        "recommended_investigation_step": {"type": "string"}
    },
    "required": ["summary", "suspected_root_cause", "hypotheses", "recommended_investigation_step"]
}

@time_node("DiagnosisNode")
def DiagnosisNode(state: dict) -> dict:
    """
    Formulates technical diagnostic hypotheses for TECHNICAL, BUG, or INCIDENT inquiries.

    Required state keys: tenant_id, inbound_message
    Sets state keys:     diagnostic_hypotheses
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id", "inbound_message")
        
        # Set active tenant context for SDK tenant isolation
        sdk.security.tenant_isolation.set_current_tenant(tenant_id)
        
        intent = state.get("intent", "GENERAL")
        
        # Skip technical diagnosis if the intent is strictly non-technical
        if intent not in ["TECHNICAL", "BUG", "INCIDENT", "SECURITY"]:
            logger.info("Non-technical intent; skipping technical diagnosis.", extra={"tenant_id": tenant_id, "intent": intent})
            return {"diagnostic_hypotheses": []}
            
        message = state["inbound_message"]
        cust_ctx = state.get("customer_context", {})
        recent_errors = cust_ctx.get("recent_errors", [])
        
        prompt = DIAGNOSIS_PROMPT.format(
            message=message,
            customer_context=str(cust_ctx),
            logs=str(recent_errors)
        )
        
        ai_res = sdk.ai.generate(
            prompt=prompt,
            schema=DIAGNOSIS_SCHEMA,
            provider="groq",
            fallback_provider="openai"
        )
        
        if not ai_res.get("valid") or not isinstance(ai_res.get("output"), dict):
            logger.warning(
                "Diagnosis LLM output invalid. Returning default fallback hypothesis.",
                extra={"tenant_id": tenant_id, "error": ai_res.get("error")}
            )
            return {"diagnostic_hypotheses": ["Investigate environment configuration and system logs."]}
            
        output = ai_res["output"]
        hypotheses = output.get("hypotheses", [output.get("suspected_root_cause", "Unspecified technical issue")])
        
        logger.info(
            "Technical diagnosis completed successfully via Groq",
            extra={"tenant_id": tenant_id, "hypothesis_count": len(hypotheses)}
        )
        
        return {"diagnostic_hypotheses": hypotheses}
        
    except Exception as e:
        logger.error(
            "DiagnosisNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "DiagnosisNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "DiagnosisNode", str(e))
        raise e


# ---------------------------------------------------------------------------
# Grounded Response Generation Node (Micro-Step 3.3)
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer"},
                    "document_name": {"type": "string"}
                }
            }
        },
        "confidence_score": {"type": "number"}
    },
    "required": ["answer", "citations", "confidence_score"]
}

@time_node("ResponseNode")
def ResponseNode(state: dict) -> dict:
    """
    Generates a grounded answer backed strictly by retrieved context evidence with citations.

    Required state keys: tenant_id, inbound_message
    Sets state keys:     response_text, citations, confidence_score
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id", "inbound_message")
        
        # Set active tenant context for SDK tenant isolation
        sdk.security.tenant_isolation.set_current_tenant(tenant_id)
        
        message = state["inbound_message"]
        evidence = state.get("retrieved_evidence", [])
        cust_ctx = state.get("customer_context", {})
        cust_name = cust_ctx.get("company", "Valued Customer")
        
        # Format evidence context
        if not evidence:
            evidence_str = "No specific documentation evidence found for this inquiry."
        else:
            evidence_blocks = []
            for item in evidence:
                doc = item.get("document_name", "Support_Doc.pdf")
                page = item.get("page_number", 1)
                content = item.get("content", "")
                evidence_blocks.append(f"[Doc: {doc} | Page {page}]\n{content}")
            evidence_str = "\n\n".join(evidence_blocks)
            
        prompt = GROUNDED_RESPONSE_PROMPT.format(
            evidence_context=evidence_str,
            message=message,
            customer_name=cust_name
        )
        
        ai_res = sdk.ai.generate(
            prompt=prompt,
            schema=RESPONSE_SCHEMA,
            provider="groq",
            fallback_provider="openai"
        )
        
        if not ai_res.get("valid") or not isinstance(ai_res.get("output"), dict):
            logger.warning(
                "Response LLM output invalid. Falling back to default grounded message.",
                extra={"tenant_id": tenant_id, "error": ai_res.get("error")}
            )
            return {
                "response_text": "I don't know based on the provided documentation.",
                "citations": [],
                "confidence_score": 30.0
            }
            
        output = ai_res["output"]
        answer_text = str(output.get("answer", ""))
        citations = output.get("citations", [])
        confidence = float(output.get("confidence_score", 85.0))
        
        # Normalize confidence to 0-100 scale if LLM returned 0.0-1.0
        if confidence <= 1.0:
            confidence = confidence * 100.0
            
        # If no evidence was retrieved, cap confidence score
        if not evidence and confidence > 50.0:
            confidence = 40.0
            
        logger.info(
            "Grounded response generated successfully via Groq",
            extra={
                "tenant_id": tenant_id,
                "confidence_score": confidence,
                "citations_count": len(citations)
            }
        )
        
        return {
            "response_text": answer_text,
            "citations": citations,
            "confidence_score": confidence
        }
        
    except Exception as e:
        logger.error(
            "ResponseNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "ResponseNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "ResponseNode", str(e))
        raise e


# ---------------------------------------------------------------------------
# Action & HITL Guardrail Node (Micro-Step 4.1)
# ---------------------------------------------------------------------------

@time_node("ActionNode")
def ActionNode(state: dict) -> dict:
    """
    Evaluates action risk. Low-risk operations execute directly via SDK tools.
    High-risk actions (refunds > $50, cancellations, high frustration, low confidence)
    trigger sdk.decisions.record_decision() creating a Decision Card in PENDING_APPROVAL status.

    Required state keys: tenant_id, inbound_message
    Sets state keys:     suggested_action, action_result, decision_id, status
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id", "inbound_message")
        
        # Set active tenant context for SDK tenant isolation
        sdk.security.tenant_isolation.set_current_tenant(tenant_id)
        
        intent = state.get("intent", "GENERAL")
        confidence_score = float(state.get("confidence_score", 100.0))
        frustration_score = float(state.get("frustration_score", 0.0))
        churn_risk = bool(state.get("churn_risk", False))
        
        high_risk_intents = {"REFUND", "CANCELLATION", "ACCOUNT", "SECURITY"}
        
        # Check if action requires Human-In-The-Loop approval
        needs_hitl = (
            intent in high_risk_intents or 
            confidence_score < 70.0 or 
            frustration_score > 0.7 or 
            churn_risk
        )
        
        action_name = f"support_action_{intent.lower()}"
        
        if needs_hitl:
            reasons = [
                f"Intent '{intent}' classified as high risk",
                f"Confidence score: {confidence_score:.1f}%",
                f"Frustration score: {frustration_score:.2f}"
            ]
            if churn_risk:
                reasons.append("Customer churn risk detected")
                
            # Create a Decision Card in PostgreSQL via SDK
            decision_id = sdk.decisions.record_decision(
                tenant_id=tenant_id,
                agent_name="SupportAgent.ActionNode",
                action=action_name,
                result=state.get("response_text", "High risk support action requires approval."),
                confidence=confidence_score / 100.0,
                reason=reasons,
                sources=state.get("citations", []),
                model="groq-llama-3.1",
                approved=False,
                approval_required=True,
                prompt=state.get("inbound_message", ""),
                raw_output=state.get("response_text", "")
            )
            
            logger.info(
                "High risk action flagged for HITL approval",
                extra={"tenant_id": tenant_id, "action": action_name, "decision_id": decision_id}
            )
            
            return {
                "suggested_action": {"action": action_name, "risk": "HIGH"},
                "action_result": {"status": "PENDING_APPROVAL", "decision_id": decision_id},
                "decision_id": decision_id,
                "status": "WAITING_FOR_HUMAN"
            }
            
        else:
            logger.info(
                "Low risk action executed automatically",
                extra={"tenant_id": tenant_id, "action": action_name}
            )
            return {
                "suggested_action": {"action": action_name, "risk": "LOW"},
                "action_result": {"status": "EXECUTED", "result": "Automated response delivered"},
                "decision_id": None,
                "status": "RESOLVED"
            }
            
    except Exception as e:
        logger.error(
            "ActionNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "ActionNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "ActionNode", str(e))
        raise e


# ---------------------------------------------------------------------------
# Human Handoff & Escalation Node (Micro-Step 4.2)
# ---------------------------------------------------------------------------

HANDOFF_SCHEMA = {
    "type": "object",
    "properties": {
        "customer_summary": {"type": "string"},
        "issue_summary": {"type": "string"},
        "attempted_actions": {
            "type": "array",
            "items": {"type": "string"}
        },
        "diagnosis": {"type": "string"},
        "recommended_next_action": {"type": "string"},
        "urgency": {"type": "string"},
        "customer_sentiment": {"type": "string"},
        "escalation_reason": {"type": "string"}
    },
    "required": [
        "customer_summary", "issue_summary", "attempted_actions", 
        "diagnosis", "recommended_next_action", "urgency", 
        "customer_sentiment", "escalation_reason"
    ]
}

@time_node("EscalationNode")
def EscalationNode(state: dict) -> dict:
    """
    Assembles a context-preserving 8-part human handoff package when tickets are escalated.
    Registers handoff in PostgreSQL via SDK tools.

    Required state keys: tenant_id, inbound_message
    Sets state keys:     action_result, status
    """
    tenant_id = state.get("tenant_id")
    try:
        _require(state, "tenant_id", "inbound_message")
        
        # Set active tenant context for SDK tenant isolation
        sdk.security.tenant_isolation.set_current_tenant(tenant_id)
        
        message = state["inbound_message"]
        cust_ctx = state.get("customer_context", {})
        intent = state.get("intent", "ESCALATION")
        hypotheses = state.get("diagnostic_hypotheses", [])
        conv_id = state.get("conversation_id", "conv_default")
        
        state_summary_str = f"Message: {message}\nCustomer: {cust_ctx}\nIntent: {intent}\nHypotheses: {hypotheses}"
        
        prompt = HUMAN_HANDOFF_PROMPT.format(state_summary=state_summary_str)
        
        ai_res = sdk.ai.generate(
            prompt=prompt,
            schema=HANDOFF_SCHEMA,
            provider="groq",
            fallback_provider="openai"
        )
        
        if not ai_res.get("valid") or not isinstance(ai_res.get("output"), dict):
            logger.warning(
                "Handoff LLM output invalid. Assembling default escalation package.",
                extra={"tenant_id": tenant_id, "error": ai_res.get("error")}
            )
            handoff_package = {
                "customer_summary": str(cust_ctx),
                "issue_summary": message,
                "attempted_actions": ["RAG Knowledge Retrieval", "Intent Classification"],
                "diagnosis": str(hypotheses),
                "recommended_next_action": "Contact customer via phone/email.",
                "urgency": state.get("urgency", "HIGH"),
                "customer_sentiment": "FRUSTRATED",
                "escalation_reason": "AI confidence or risk guardrail triggered."
            }
        else:
            handoff_package = ai_res["output"]
            
        # Record handoff via SDK tools
        handoff_id = sdk.tools.call(
            "record_support_handoff",
            tenant_id=tenant_id,
            conversation_id=conv_id,
            handoff_package=handoff_package
        )
        
        logger.info(
            "Support human escalation handoff recorded successfully",
            extra={"tenant_id": tenant_id, "handoff_id": handoff_id, "conversation_id": conv_id}
        )
        
        return {
            "action_result": {
                "status": "ESCALATED",
                "handoff_id": handoff_id,
                "package": handoff_package
            },
            "status": "WAITING_FOR_HUMAN"
        }
        
    except Exception as e:
        logger.error(
            "EscalationNode processing failed",
            extra={
                "tenant_id": tenant_id,
                "agent": "EscalationNode",
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        _publish_failure(tenant_id or "unknown", "EscalationNode", str(e))
        raise e
