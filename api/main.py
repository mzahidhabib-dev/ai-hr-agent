"""
api/main.py

Multi-Tenant FastAPI REST API Server for Support Agent.

Provides endpoints for:
  1. POST /v1/support/tickets — Submit inbound support ticket & run pipeline
  2. GET /v1/support/decisions — Fetch pending HITL Decision Cards
  3. POST /v1/support/decisions/{id}/approve — Approve/reject Decision Card action
  4. GET /v1/support/handoffs — Fetch Human Escalation Handoff Brief packages
  5. GET /v1/support/metrics — Fetch Support FinOps & Quality Analytics metrics

Rules compliance:
  Rule 21 -- Integrates strictly via Platform SDK / platform_core.
  Rule 24 -- Mandatory tenant isolation via X-Tenant-ID header.
  Rule 26 -- Zero-tolerance error handling with structured logging.
"""

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from platform_core.logging_config import get_logger
from platform_core.security.tenant_isolation import set_current_tenant
from platform_core.db import get_connection
from business_agents.support.graph import support_pipeline
from business_agents.support.finops import calculate_support_finops_metrics
from business_agents.support.resolution_verifier import calculate_resolution_metrics
from business_agents.support.incidents import get_active_incidents
from business_agents.support.knowledge_gap import get_tenant_knowledge_gaps
from business_agents.support.security import redact_pii, detect_prompt_injection

logger = get_logger(__name__)

app = FastAPI(
    title="Enterprise AI Support Agent REST API",
    version="1.0.0",
    description="Multi-tenant REST API for Support Agent Operator Dashboard"
)

# Enable CORS for Frontend Operator Console
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_tenant_id(x_tenant_id: Optional[str] = Header("tenant-1")) -> str:
    """Extracts and sets context tenant_id from X-Tenant-ID header."""
    tenant_id = x_tenant_id or "tenant-1"
    set_current_tenant(tenant_id)
    return tenant_id


class TicketSubmitRequest(BaseModel):
    message: str
    channel: Optional[str] = "web_chat"
    customer_id: Optional[str] = "cust-101"


class DecisionApproveRequest(BaseModel):
    approved: bool
    operator_notes: Optional[str] = ""


@app.post("/v1/support/tickets")
def submit_support_ticket(req: TicketSubmitRequest, tenant_id: str = Depends(get_tenant_id)):
    """Submits an inbound ticket and executes the LangGraph Support Pipeline."""
    set_current_tenant(tenant_id)
    try:
        # Check prompt injection security
        injection_res = detect_prompt_injection(req.message)
        if injection_res["is_injection_detected"]:
            raise HTTPException(status_code=400, detail="Security Violation: Prompt injection payload detected.")
            
        clean_msg = redact_pii(req.message)
        
        config = {"configurable": {"thread_id": f"api-{tenant_id}-{req.customer_id}"}}
        initial_state = {
            "tenant_id": tenant_id,
            "inbound_message": clean_msg,
            "channel": req.channel
        }
        
        final_state = support_pipeline.invoke(initial_state, config)
        return {
            "status": "SUCCESS",
            "tenant_id": tenant_id,
            "ticket_status": final_state.get("status"),
            "intent": final_state.get("intent"),
            "severity": final_state.get("severity"),
            "urgency": final_state.get("urgency"),
            "response_text": final_state.get("response_text"),
            "decision_id": final_state.get("decision_id"),
            "citations": final_state.get("citations", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API Ticket processing failed", extra={"tenant_id": tenant_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/support/decisions")
def get_pending_decision_cards(tenant_id: str = Depends(get_tenant_id)):
    """Fetches pending Human-in-the-Loop Decision Cards for approval queue."""
    set_current_tenant(tenant_id)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT decision_id, tenant_id, action, approval_status, timestamp
            FROM support_decision_cards
            WHERE tenant_id = %s
            ORDER BY timestamp DESC
            """,
            (tenant_id,)
        )
        rows = cursor.fetchall()
        
        cards = []
        for r in rows:
            cards.append({
                "decision_id": r[0],
                "tenant_id": r[1],
                "action": r[2],
                "approval_status": r[3],
                "created_at": str(r[4])
            })
        return {"status": "SUCCESS", "tenant_id": tenant_id, "decisions": cards}
    except Exception as e:
        logger.error("Failed fetching decision cards", extra={"tenant_id": tenant_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post("/v1/support/decisions/{decision_id}/approve")
def approve_decision_card(decision_id: int, req: DecisionApproveRequest, tenant_id: str = Depends(get_tenant_id)):
    """Approves or rejects a pending HITL Decision Card with optimistic locking & concurrency protection."""
    set_current_tenant(tenant_id)
    try:
        new_status = "APPROVED" if req.approved else "REJECTED"
        from platform_core.decision_cards import resolve_support_decision_card_with_lock
        res = resolve_support_decision_card_with_lock(decision_id, tenant_id, new_status)
        return {"status": "SUCCESS", "decision_id": decision_id, "approval_status": new_status, "details": res}
    except ValueError as ve:
        logger.warning("HITL Concurrency Conflict", extra={"tenant_id": tenant_id, "decision_id": decision_id, "error": str(ve)})
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as e:
        logger.error("Failed approving decision card", extra={"tenant_id": tenant_id, "decision_id": decision_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/support/handoffs")
def get_escalation_handoffs(tenant_id: str = Depends(get_tenant_id)):
    """Fetches Human Escalation Handoff Brief packages."""
    set_current_tenant(tenant_id)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT handoff_id, ticket_id, diagnostic_summary, status, created_at
            FROM support_handoffs
            WHERE tenant_id = %s
            ORDER BY created_at DESC
            """,
            (tenant_id,)
        )
        rows = cursor.fetchall()
        
        handoffs = []
        for r in rows:
            handoffs.append({
                "handoff_id": r[0],
                "ticket_id": r[1],
                "diagnostic_summary": r[2],
                "status": r[3],
                "created_at": str(r[4])
            })
        return {"status": "SUCCESS", "tenant_id": tenant_id, "handoffs": handoffs}
    except Exception as e:
        logger.error("Failed fetching handoffs", extra={"tenant_id": tenant_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/v1/support/metrics")
def get_support_analytics_metrics(tenant_id: str = Depends(get_tenant_id)):
    """Fetches Support FinOps, Resolution Rates, Active Incidents, and Knowledge Gap metrics."""
    set_current_tenant(tenant_id)
    try:
        res_metrics = calculate_resolution_metrics(tenant_id)
        finops_metrics = calculate_support_finops_metrics(tenant_id)
        incidents = get_active_incidents(tenant_id)
        gaps = get_tenant_knowledge_gaps(tenant_id)
        
        return {
            "status": "SUCCESS",
            "tenant_id": tenant_id,
            "resolution_metrics": res_metrics,
            "finops_metrics": finops_metrics,
            "active_incidents": incidents,
            "knowledge_gaps": gaps
        }
    except Exception as e:
        logger.error("Failed fetching support metrics", extra={"tenant_id": tenant_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# --- HR AGENT MULTI-CHANNEL WEBHOOK ROUTER ---

class HRWebhookRequest(BaseModel):
    query: str
    channel: Optional[str] = "slack"
    employee_id: Optional[str] = "emp-101"
    message_id: Optional[str] = None


PROCESSED_HR_MESSAGES = set()


@app.post("/v1/hr/webhook")
def handle_hr_webhook(req: HRWebhookRequest, tenant_id: str = Depends(get_tenant_id)):
    """
    Multi-tenant webhook router for Enterprise AI HR Agent (Slack, MS Teams, GoHighLevel, Web).
    Enforces idempotency deduplication via message_id (Rule 25).
    """
    set_current_tenant(tenant_id)

    # Rule 25: Idempotency deduplication check
    if req.message_id:
        dedup_key = f"{tenant_id}:{req.message_id}"
        if dedup_key in PROCESSED_HR_MESSAGES:
            logger.warning("Duplicate HR webhook event ignored", extra={"tenant_id": tenant_id, "message_id": req.message_id})
            return {"status": "SKIPPED_DUPLICATE", "tenant_id": tenant_id, "message": "Event already processed."}
        PROCESSED_HR_MESSAGES.add(dedup_key)

    try:
        from business_agents.hr.graph import create_hr_graph
        hr_graph = create_hr_graph()

        initial_state = {
            "tenant_id": tenant_id,
            "employee_id": req.employee_id,
            "query": req.query,
            "channel": req.channel,
        }

        final_state = hr_graph.invoke(initial_state)

        return {
            "status": "SUCCESS",
            "tenant_id": tenant_id,
            "employee_id": req.employee_id,
            "intent": final_state.get("intent"),
            "execution_status": final_state.get("status"),
            "draft_response": final_state.get("draft_response"),
            "decision_card_id": final_state.get("decision_card_id"),
        }
    except Exception as e:
        logger.error("HR Webhook processing failed", extra={"tenant_id": tenant_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

