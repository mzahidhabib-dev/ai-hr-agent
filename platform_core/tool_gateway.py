from platform_core.logging_config import get_logger
from platform_core.db import get_connection
import json
from platform_core.security.tenant_isolation import enforce_tenant
from business_agents.support.tools.billing import (
    lookup_customer_profile,
    lookup_invoice,
    resend_invoice,
    process_refund,
    change_subscription_plan
)
from business_agents.support.tools.diagnostics import (
    query_api_usage_logs,
    check_service_health,
    run_account_config_diagnostics
)

logger = get_logger(__name__)

# --- STUBBED TOOLS FOR PHASE 1 ---

def find_prospect(tenant_id: str, icp_config: dict) -> list:
    """Stub: Returns a fake list of prospects based on ICP."""
    logger.info("Finding prospects", extra={"tenant_id": tenant_id, "icp_industry": icp_config.get("industry")})
    return [{"company_name": "TechCorp", "domain": "techcorp.com", "prospect_id": 1}]

def find_decision_maker(tenant_id: str, prospect_id: int) -> dict:
    """Stub: Returns a fake decision maker."""
    logger.info("Finding decision maker", extra={"tenant_id": tenant_id, "prospect_id": prospect_id})
    return {"first_name": "Alice", "last_name": "Smith", "title": "CTO", "email": "alice@techcorp.com", "decision_maker_id": 1}

def research_company(tenant_id: str, domain: str) -> str:
    """Uses MCP Client to call external server. Falls back to stub if disabled."""
    logger.info("Researching company via MCP", extra={"tenant_id": tenant_id, "domain": domain})
    
    import os
    from platform_core.mcp_client import call_mcp_tool
    
    try:
        cmd = "python"
        args = ["workers/web_research_mcp.py"]
        return call_mcp_tool(cmd, args, "research_company", {"tenant_id": tenant_id, "domain": domain})
    except Exception as e:
        logger.error("MCP routing failed", extra={"error": str(e)})
        raise

def send_email(tenant_id: str, to_email: str, subject: str, body: str) -> bool:
    """Sends an email via n8n webhook. Falls back to stub if URL is missing."""
    import os
    import requests
    
    webhook_url = os.environ.get("N8N_WEBHOOK_URL")
    
    if not webhook_url:
        print(f"\n[EMAIL DISPATCH STUB] No N8N_WEBHOOK_URL in .env. Would send email to: {to_email}\n")
        logger.info("Sending email (stub - no N8N_WEBHOOK_URL configured)", extra={"tenant_id": tenant_id, "to_email": to_email, "subject": subject})
        return True
        
    print(f"\n==================================================")
    print(f"🚀 DISPATCHING EMAIL VIA N8N WEBHOOK")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"Webhook URL: {webhook_url}")
    print(f"==================================================\n")
    
    logger.info("Sending email via n8n", extra={"tenant_id": tenant_id, "to_email": to_email, "subject": subject})
    
    try:
        response = requests.post(
            webhook_url,
            json={
                "tenant_id": tenant_id,
                "to_email": to_email,
                "subject": subject,
                "body": body
            },
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ EMAIL DISPATCH SUCCESSFUL! Status Code: {response.status_code}\n")
        return True
    except Exception as e:
        print(f"❌ EMAIL DISPATCH FAILED: {e}\n")
        logger.error("Failed to send email via n8n", extra={
            "tenant_id": tenant_id, 
            "to_email": to_email, 
            "exc_type": type(e).__name__,
            "error": str(e)
        })
        raise

def check_calendar_availability(tenant_id: str) -> list:
    """Stub: Returns fake calendar slots."""
    logger.info("Checking calendar availability", extra={"tenant_id": tenant_id})
    return ["2026-07-20T10:00:00Z", "2026-07-21T14:00:00Z"]

# --- IMPLEMENTED TOOLS ---

@enforce_tenant
def update_crm(tenant_id: str, prospect_id: int, stage_id: str, value: float = 0.0) -> int:
    """
    Writes directly to Postgres `opportunities` / `pipeline_stage` tables.
    Returns the opportunity_id.
    """
    logger.info("Updating CRM", extra={"tenant_id": tenant_id, "prospect_id": prospect_id, "stage_id": stage_id})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO opportunities (tenant_id, prospect_id, stage_id, value) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, prospect_id) 
            DO UPDATE SET 
                stage_id = EXCLUDED.stage_id, 
                value = EXCLUDED.value, 
                updated_at = CURRENT_TIMESTAMP
            RETURNING opportunity_id
            """,
            (tenant_id, prospect_id, stage_id, value)
        )
        opp_id = cursor.fetchone()[0]
        conn.commit()
        return opp_id
    except Exception as e:
        logger.error(
            "Failed to update CRM",
            extra={
                "tenant_id": tenant_id,
                "prospect_id": prospect_id,
                "stage_id": stage_id,
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def record_handoff(tenant_id: str, prospect_id: int, opportunity_id: int, summary: str) -> int:
    """Writes a handoff record to the Postgres `handoffs` table."""
    logger.info("Recording human handoff", extra={"tenant_id": tenant_id, "prospect_id": prospect_id})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO handoffs (tenant_id, prospect_id, opportunity_id, summary) VALUES (%s, %s, %s, %s) RETURNING handoff_id",
            (tenant_id, prospect_id, opportunity_id, summary)
        )
        handoff_id = cursor.fetchone()[0]
        conn.commit()
        return handoff_id
    except Exception as e:
        logger.error(
            "Failed to record handoff",
            extra={
                "tenant_id": tenant_id,
                "prospect_id": prospect_id,
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def _get_or_create_default_prospect(cursor, tenant_id: str) -> int:
    """Helper to ensure a valid prospect_id exists for handoffs foreign key constraint."""
    cursor.execute("SELECT prospect_id FROM prospects WHERE tenant_id = %s LIMIT 1", (tenant_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        "INSERT INTO prospects (tenant_id, company, domain) VALUES (%s, %s, %s) RETURNING prospect_id",
        (tenant_id, "Default Support Client", "support.client.com")
    )
    return cursor.fetchone()[0]

@enforce_tenant
def record_support_handoff(tenant_id: str, conversation_id: str, handoff_package: dict) -> int:
    """Writes a support handoff record package to the Postgres `handoffs` table."""
    logger.info("Recording support human handoff", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        prospect_id = _get_or_create_default_prospect(cursor, tenant_id)
        summary_json = json.dumps({"conversation_id": conversation_id, "package": handoff_package})
        cursor.execute(
            "INSERT INTO handoffs (tenant_id, prospect_id, summary) VALUES (%s, %s, %s) RETURNING handoff_id",
            (tenant_id, prospect_id, summary_json)
        )
        handoff_id = cursor.fetchone()[0]
        conn.commit()
        return handoff_id
    except Exception as e:
        logger.error(
            "Failed to record support handoff",
            extra={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def call(tool_name: str, **kwargs):
    """Dynamically dispatches to the tool by name."""
    tools = {
        "find_prospect": find_prospect,
        "find_decision_maker": find_decision_maker,
        "research_company": research_company,
        "send_email": send_email,
        "check_calendar_availability": check_calendar_availability,
        "update_crm": update_crm,
        "record_handoff": record_handoff,
        "record_support_handoff": record_support_handoff,
        "lookup_customer_profile": lookup_customer_profile,
        "lookup_invoice": lookup_invoice,
        "resend_invoice": resend_invoice,
        "process_refund": process_refund,
        "change_subscription_plan": change_subscription_plan,
        "query_api_usage_logs": query_api_usage_logs,
        "check_service_health": check_service_health,
        "run_account_config_diagnostics": run_account_config_diagnostics
    }
    
    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")
        
    return tools[tool_name](**kwargs)
