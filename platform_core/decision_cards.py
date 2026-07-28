import json
from platform_core.logging_config import get_logger
from platform_core.db import get_connection

logger = get_logger(__name__)

def record_decision(
    tenant_id: str,
    agent_name: str,
    action: str,
    result: str = None,
    confidence: float = None,
    reason: list = None,
    sources: list = None,
    model: str = None,
    prompt_version: str = None,
    cost_usd: float = None,
    duration_seconds: float = None,
    approved: bool = None,
    approval_required: bool = None,
    replay_id: str = None,
    # Context needed for full audit log
    prompt: str = None,
    raw_output: str = None,
    validation_result: dict = None,
    prospect_id: int = None
) -> int:
    """
    Inserts a row into decision_cards and writes the corresponding full audit trail to audit_logs.
    Returns the generated decision_id.
    """
    logger.info("Recording decision", extra={"tenant_id": tenant_id, "agent_name": agent_name, "action": action})
    
    # Phase 7.1: Evaluate confidence automatically
    from platform_core.confidence import evaluate_confidence
    if confidence is not None and approval_required is None:
        approval_required = evaluate_confidence(confidence, action, tenant_id)
        
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert into decision_cards
        cursor.execute(
            """
            INSERT INTO decision_cards (
                tenant_id, agent_name, action, result, confidence, 
                reason, sources, model, prompt_version, cost_usd, 
                duration_seconds, approved, approval_required, replay_id, prospect_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING decision_id
            """,
            (
                tenant_id, agent_name, action, result, confidence,
                reason, sources, model, prompt_version, cost_usd,
                duration_seconds, approved, approval_required, replay_id, prospect_id
            )
        )
        decision_id = cursor.fetchone()[0]

        # Synchronously write to audit_logs for immediate visibility on Dashboard
        val_res_str = json.dumps(validation_result) if validation_result else "{}"
        cursor.execute(
            """
            INSERT INTO audit_logs (decision_id, tenant_id, agent_name, prompt, model, raw_output, validation_result)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (decision_id, tenant_id, agent_name, prompt or "", model or "groq-free", raw_output or result or "", val_res_str)
        )

        conn.commit()
        
        # Publish the event so the audit subscriber can pick it up
        from platform_core.events import publish
        
        publish_payload = {
            "decision_id": decision_id,
            "agent_name": agent_name,
            "prompt": prompt,
            "model": model,
            "raw_output": raw_output,
            "validation_result": validation_result
        }
        publish(tenant_id, "decision.recorded", publish_payload)
        
        # Phase 7.1 & 7.2: If approval is required, automatically request it.
        if approval_required:
            request_approval(decision_id)
            from platform_core.events import publish
            publish(tenant_id, "approval.requested", {"decision_id": decision_id, "action": action})
            
        logger.info(
            "Decision card recorded",
            extra={"tenant_id": tenant_id, "agent": agent_name, "action": action, "decision_id": decision_id, "approval_required": approval_required}
        )
        return decision_id
    except Exception as e:
        logger.error(
            "Failed to record decision card",
            extra={
                "tenant_id": tenant_id,
                "agent": agent_name,
                "action": action,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching pg8000 DB exception; rolling back and re-raising to caller"
            }
        )
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def request_approval(decision_id: int) -> None:
    """
    Updates the decision card's approval_status to 'PENDING_APPROVAL'.
    Used by the HITL Gateway when a high-risk action requires human review.
    """
    logger.info("Requesting human approval", extra={"decision_id": decision_id})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE decision_cards SET approval_status = 'PENDING_APPROVAL' WHERE decision_id = %s",
            (decision_id,)
        )
        conn.commit()
    except Exception as e:
        logger.error(
            "Failed to request approval",
            extra={"decision_id": decision_id, "exc_type": type(e).__name__, "error": str(e)}
        )
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def resolve_approval(decision_id: int, status: str, new_result: str = None) -> None:
    """
    Resolves a pending human approval.
    
    Args:
        decision_id: The ID of the decision card.
        status: One of 'APPROVED', 'REJECTED', 'EDITED', 'DISPATCHING', 'SENT', 'FAILED'.
        new_result: If 'EDITED', the human-provided new result string.
    """
    valid_statuses = {"APPROVED", "REJECTED", "EDITED", "EDITED_PENDING", "DISPATCHING", "SENT", "FAILED"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid approval status. Must be one of {valid_statuses}")
        
    logger.info(
        "Resolving human approval", 
        extra={"decision_id": decision_id, "new_status": status, "is_edited": bool(new_result)}
    )
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Idempotency check: prevent double-dispatch
        cursor.execute("SELECT approval_status FROM decision_cards WHERE decision_id = %s FOR UPDATE", (decision_id,))
        row = cursor.fetchone()
        if row:
            current_status = row[0]
            if status == "DISPATCHING" and current_status in ["DISPATCHING", "SENT"]:
                raise ValueError("Idempotency violation: This card is already dispatching or sent.")
        
        if new_result is not None:
            cursor.execute(
                "UPDATE decision_cards SET approval_status = %s, result = %s WHERE decision_id = %s",
                (status, new_result, decision_id)
            )
        else:
            cursor.execute(
                "UPDATE decision_cards SET approval_status = %s WHERE decision_id = %s",
                (status, decision_id)
            )
            
        conn.commit()
    except Exception as e:
        logger.error(
            "Failed to resolve approval",
            extra={"decision_id": decision_id, "exc_type": type(e).__name__, "error": str(e)}
        )
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def get_decision(decision_id: int) -> dict:
    """
    Fetches a decision card from the database.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT decision_id, tenant_id, agent_name, action, result, approval_status, prospect_id FROM decision_cards WHERE decision_id = %s",
            (decision_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Decision card {decision_id} not found")
            
        return {
            "decision_id": row[0],
            "tenant_id": row[1],
            "agent_name": row[2],
            "action": row[3],
            "result": row[4],
            "approval_status": row[5],
            "prospect_id": row[6]
        }
    except Exception as e:
        logger.error("Failed to fetch decision card", extra={"decision_id": decision_id, "error": str(e)})
        raise e
    finally:
        if conn:
            conn.close()
