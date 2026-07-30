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
        
        # Insert into decision_cards for audit_logs foreign key constraint
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

        # If Support Agent, also record into support_decision_cards for HITL UI Queue
        if agent_name.startswith("Support"):
            cursor.execute(
                """
                INSERT INTO support_decision_cards (
                    tenant_id, agent_name, action, result, confidence, 
                    reason, approval_status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'WAITING_FOR_HUMAN')
                """,
                (tenant_id, agent_name, action, result or action, confidence or 100.0, reason or [])
            )

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


def resolve_support_decision_card_with_lock(
    decision_id: int,
    tenant_id: str,
    target_status: str,
    operator_id: str = "operator-1"
) -> dict:
    """
    Resolves a pending HITL Support Decision Card using explicit state transitions and optimistic locking.

    State transition flow:
        WAITING_FOR_HUMAN -> EXECUTING -> APPROVED / REJECTED

    Ensures that concurrent approvals by two operators raise a Concurrency Conflict Error.
    """
    valid_statuses = {"APPROVED", "REJECTED", "EXECUTING"}
    if target_status not in valid_statuses:
        raise ValueError(f"Invalid target status '{target_status}'. Must be one of {valid_statuses}")

    logger.info(
        "Resolving support decision card with optimistic locking",
        extra={"tenant_id": tenant_id, "decision_id": decision_id, "target_status": target_status, "operator_id": operator_id}
    )
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch current card state
        cursor.execute(
            """
            SELECT decision_id, tenant_id, approval_status
            FROM support_decision_cards
            WHERE decision_id = %s AND tenant_id = %s
            """,
            (decision_id, tenant_id)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Support decision card {decision_id} not found for tenant {tenant_id}")
            
        current_status = row[2]
        
        # 2. Concurrency Lock Validation
        if current_status in ["APPROVED", "REJECTED", "EXECUTING", "EXECUTED"]:
            raise ValueError(f"HITL Concurrency Conflict: Decision card {decision_id} is already in state '{current_status}'. Concurrent resolution blocked.")
            
        # 3. Update to target status with timestamp
        cursor.execute(
            """
            UPDATE support_decision_cards
            SET approval_status = %s
            WHERE decision_id = %s AND tenant_id = %s AND (approval_status IN ('WAITING_FOR_HUMAN', 'PENDING_APPROVAL', 'PENDING') OR approval_status IS NULL)
            """,
            (target_status, decision_id, tenant_id)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"HITL Concurrency Conflict: Race condition detected. Decision card {decision_id} was modified by another operator.")
            
        conn.commit()
        return {
            "status": "SUCCESS",
            "decision_id": decision_id,
            "tenant_id": tenant_id,
            "previous_status": current_status,
            "new_status": target_status,
            "operator_id": operator_id
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed executing optimistic lock resolution", extra={"tenant_id": tenant_id, "decision_id": decision_id, "error": str(e)})
        raise e
    finally:
        if conn:
            conn.close()

