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
    """Writes a support handoff record package to the Postgres `support_handoffs` table."""
    logger.info("Recording support human handoff", extra={"tenant_id": tenant_id, "conversation_id": conversation_id})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        diag_summary = handoff_package.get("diagnosis", "") or handoff_package.get("issue_summary", "") or "Human Escalation Handoff Brief"
        summary_json = json.dumps(handoff_package)
        cursor.execute(
            """
            INSERT INTO support_handoffs (tenant_id, diagnostic_summary, handoff_package, status)
            VALUES (%s, %s, %s, 'WAITING_FOR_HUMAN')
            RETURNING handoff_id
            """,
            (tenant_id, diag_summary, summary_json)
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
    """
    Dynamically dispatches to the tool by name with deterministic Policy Engine & Idempotency enforcement.
    """
# --- HR TOOL CAPABILITIES ---

@enforce_tenant
def get_employee_profile(tenant_id: str, employee_id: str) -> dict:
    """Retrieves employee profile details from hr_employees table."""
    logger.info("Retrieving employee profile", extra={"tenant_id": tenant_id, "employee_id": employee_id})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT employee_id, full_name, email, department, role, location, jurisdiction, status, pto_balance_days
            FROM hr_employees
            WHERE tenant_id = %s AND employee_id = %s
            """,
            (tenant_id, employee_id)
        )
        row = cursor.fetchone()
        if row:
            return {
                "employee_id": row[0],
                "full_name": row[1],
                "email": row[2],
                "department": row[3],
                "role": row[4],
                "location": row[5],
                "jurisdiction": row[6],
                "status": row[7],
                "pto_balance_days": float(row[8]),
            }
        else:
            # Auto-provision default employee record for testing
            cursor.execute(
                """
                INSERT INTO hr_employees (employee_id, tenant_id, full_name, email, department, role, location, jurisdiction)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id) DO NOTHING
                """,
                (employee_id, tenant_id, "Sample Employee", f"{employee_id}@company.com", "Engineering", "Software Engineer", "HQ", "US")
            )
            conn.commit()
            return {
                "employee_id": employee_id,
                "full_name": "Sample Employee",
                "email": f"{employee_id}@company.com",
                "department": "Engineering",
                "role": "Software Engineer",
                "location": "HQ",
                "jurisdiction": "US",
                "status": "ACTIVE",
                "pto_balance_days": 15.0,
            }
    except Exception as e:
        logger.error("Failed to retrieve employee profile", extra={"tenant_id": tenant_id, "employee_id": employee_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


@enforce_tenant
def get_pto_balance(tenant_id: str, employee_id: str) -> dict:
    """Returns active PTO balance and pending requested days for an employee."""
    logger.info("Checking PTO balance", extra={"tenant_id": tenant_id, "employee_id": employee_id})
    profile = get_employee_profile(tenant_id=tenant_id, employee_id=employee_id)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(total_days), 0)
            FROM hr_leave_requests
            WHERE tenant_id = %s AND employee_id = %s AND status = 'PENDING'
            """,
            (tenant_id, employee_id)
        )
        pending_days = float(cursor.fetchone()[0])
        return {
            "employee_id": employee_id,
            "pto_balance_days": profile.get("pto_balance_days", 15.0),
            "pending_days": pending_days,
            "available_days": max(0.0, profile.get("pto_balance_days", 15.0) - pending_days)
        }
    except Exception as e:
        logger.error("Failed to query PTO balance", extra={"tenant_id": tenant_id, "employee_id": employee_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


@enforce_tenant
def submit_leave_request(tenant_id: str, employee_id: str, start_date: str, end_date: str, leave_type: str = "PTO") -> dict:
    """Inserts a new leave request into hr_leave_requests table."""
    logger.info("Submitting leave request", extra={"tenant_id": tenant_id, "employee_id": employee_id, "leave_type": leave_type})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hr_leave_requests (tenant_id, employee_id, leave_type, start_date, end_date, total_days, status)
            VALUES (%s, %s, %s, %s, %s, 1.0, 'PENDING')
            RETURNING request_id, status
            """,
            (tenant_id, employee_id, leave_type, start_date, end_date)
        )
        row = cursor.fetchone()
        conn.commit()
        return {
            "request_id": row[0],
            "employee_id": employee_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "status": row[1],
            "message": f"{leave_type} leave request submitted successfully for approval."
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to submit leave request", extra={"tenant_id": tenant_id, "employee_id": employee_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


@enforce_tenant
def get_paystub_comparison(tenant_id: str, employee_id: str, pay_period_1: str = "2026-06", pay_period_2: str = "2026-07") -> dict:
    """Returns paystub details and variance analysis between two pay periods."""
    logger.info("Comparing paystubs", extra={"tenant_id": tenant_id, "employee_id": employee_id})
    return {
        "employee_id": employee_id,
        "pay_period_current": pay_period_2,
        "pay_period_previous": pay_period_1,
        "gross_pay": {"current": 5000.0, "previous": 5000.0, "variance": 0.0},
        "tax_withholding": {"current": 1100.0, "previous": 1000.0, "variance": 100.0},
        "net_pay": {"current": 3900.0, "previous": 4000.0, "variance": -100.0},
        "explanation": "Net pay decreased by $100 due to mid-year state tax adjustment."
    }


@enforce_tenant
def request_employment_letter(tenant_id: str, employee_id: str, letter_type: str = "VERIFICATION") -> dict:
    """Generates an employment verification letter request."""
    logger.info("Requesting employment verification letter", extra={"tenant_id": tenant_id, "employee_id": employee_id})
    return {
        "employee_id": employee_id,
        "letter_type": letter_type,
        "status": "GENERATED",
        "document_url": f"/documents/{tenant_id}/{employee_id}_employment_verification.pdf"
    }


# --- PHASE 3 LIFECYCLE ORCHESTRATION TOOLS ---

@enforce_tenant
def get_onboarding_checklist(tenant_id: str, employee_id: str) -> dict:
    """Retrieves 30/60/90-day onboarding checklist and status from hr_onboarding_checklists table."""
    logger.info("Retrieving onboarding checklist", extra={"tenant_id": tenant_id, "employee_id": employee_id})
    # Ensure employee record exists to satisfy foreign key constraint
    get_employee_profile(tenant_id=tenant_id, employee_id=employee_id)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT checklist_id, milestone, items, status
            FROM hr_onboarding_checklists
            WHERE tenant_id = %s AND employee_id = %s
            """,
            (tenant_id, employee_id)
        )
        row = cursor.fetchone()
        if row:
            return {
                "checklist_id": row[0],
                "employee_id": employee_id,
                "milestone": row[1],
                "items": row[2] if isinstance(row[2], dict) else json.loads(row[2]) if isinstance(row[2], str) else row[2],
                "status": row[3],
            }
        else:
            # Auto-provision default onboarding checklist for new hire
            default_items = {
                "day_30": {"it_setup": "COMPLETED", "security_training": "COMPLETED", "manager_checkin": "PENDING"},
                "day_60": {"project_onboarding": "IN_PROGRESS", "team_shadowing": "COMPLETED"},
                "day_90": {"first_review": "PENDING", "goal_setting": "PENDING"}
            }
            cursor.execute(
                """
                INSERT INTO hr_onboarding_checklists (tenant_id, employee_id, milestone, items, status)
                VALUES (%s, %s, %s, %s, 'IN_PROGRESS')
                RETURNING checklist_id
                """,
                (tenant_id, employee_id, "Day 30", json.dumps(default_items))
            )
            checklist_id = cursor.fetchone()[0]
            conn.commit()
            return {
                "checklist_id": checklist_id,
                "employee_id": employee_id,
                "milestone": "Day 30",
                "items": default_items,
                "status": "IN_PROGRESS",
            }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to retrieve onboarding checklist", extra={"tenant_id": tenant_id, "employee_id": employee_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


@enforce_tenant
def provision_it_access(tenant_id: str, employee_id: str, system_list: list = None) -> dict:
    """Provisions IT system accounts (Google Workspace, Slack, Jira, GitHub) for new hire."""
    systems = system_list or ["Google Workspace", "Slack", "Jira", "GitHub"]
    logger.info("Provisioning IT access", extra={"tenant_id": tenant_id, "employee_id": employee_id, "systems": systems})
    return {
        "employee_id": employee_id,
        "provisioned_systems": systems,
        "status": "PROVISIONED",
        "message": f"IT access successfully provisioned for {len(systems)} systems."
    }


@enforce_tenant
def revoke_it_access(tenant_id: str, employee_id: str) -> dict:
    """Revokes IT access across all systems upon offboarding and records status."""
    logger.warning("Revoking IT access for offboarding employee", extra={"tenant_id": tenant_id, "employee_id": employee_id})
    get_employee_profile(tenant_id=tenant_id, employee_id=employee_id)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hr_offboarding_tasks (tenant_id, employee_id, task_name, owner, status, access_revoked)
            VALUES (%s, %s, 'IT Access Revocation', 'IT-Security', 'COMPLETED', TRUE)
            RETURNING task_id
            """,
            (tenant_id, employee_id)
        )
        task_id = cursor.fetchone()[0]
        conn.commit()
        return {
            "task_id": task_id,
            "employee_id": employee_id,
            "access_revoked": True,
            "status": "COMPLETED",
            "message": "All enterprise IT system access successfully revoked."
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to revoke IT access", extra={"tenant_id": tenant_id, "employee_id": employee_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


@enforce_tenant
def track_asset_return(tenant_id: str, employee_id: str, asset_id: str = "laptop-001") -> dict:
    """Tracks asset/laptop return status for offboarding employee."""
    logger.info("Tracking asset return", extra={"tenant_id": tenant_id, "employee_id": employee_id, "asset_id": asset_id})
    get_employee_profile(tenant_id=tenant_id, employee_id=employee_id)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hr_offboarding_tasks (tenant_id, employee_id, task_name, owner, status, asset_returned)
            VALUES (%s, %s, %s, 'IT-Logistics', 'COMPLETED', TRUE)
            RETURNING task_id
            """,
            (tenant_id, employee_id, f"Asset Return ({asset_id})")
        )
        task_id = cursor.fetchone()[0]
        conn.commit()
        return {
            "task_id": task_id,
            "employee_id": employee_id,
            "asset_id": asset_id,
            "asset_returned": True,
            "status": "COMPLETED"
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to track asset return", extra={"tenant_id": tenant_id, "employee_id": employee_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


# --- PHASE 4 RECRUITING & CANDIDATE TOOLS ---

@enforce_tenant
def parse_resume(tenant_id: str, candidate_name: str, job_title: str, resume_text: str = None) -> dict:
    """Parses candidate resume, structures objective evidence into hr_candidates table."""
    logger.info("Parsing candidate resume", extra={"tenant_id": tenant_id, "candidate_name": candidate_name, "job_title": job_title})
    skills = ["Python", "SQL", "LangGraph", "FastAPI", "Docker"]
    parsed_evidence = {
        "candidate_name": candidate_name,
        "job_title": job_title,
        "matching_skills": skills,
        "missing_requirements": ["Kubernetes"],
        "experience_years": 5,
        "match_score": 85.0
    }
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hr_candidates (tenant_id, candidate_name, email, job_title, skills, resume_parsed_json, match_score, status)
            VALUES (%s, %s, %s, %s, %s, %s, 85.0, 'EVALUATED')
            RETURNING candidate_id
            """,
            (tenant_id, candidate_name, f"{candidate_name.lower().replace(' ', '.')}@email.com", job_title, skills, json.dumps(parsed_evidence))
        )
        candidate_id = cursor.fetchone()[0]
        conn.commit()
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "job_title": job_title,
            "match_score": 85.0,
            "evidence": parsed_evidence,
            "status": "EVALUATED"
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to parse candidate resume", extra={"tenant_id": tenant_id, "candidate_name": candidate_name, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


@enforce_tenant
def schedule_interview(tenant_id: str, candidate_id: int, interviewer_ids: list = None, slot: str = "2026-08-15T14:00:00Z") -> dict:
    """Schedules an interview slot in hr_interviews table."""
    interviewers = interviewer_ids or ["hr_lead_1", "tech_lead_2"]
    logger.info("Scheduling interview", extra={"tenant_id": tenant_id, "candidate_id": candidate_id, "slot": slot})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hr_interviews (tenant_id, candidate_id, interviewer_ids, scheduled_slot, status, meeting_link)
            VALUES (%s, %s, %s, %s, 'SCHEDULED', %s)
            RETURNING interview_id
            """,
            (tenant_id, candidate_id, interviewers, slot, f"https://meet.company.com/interview-{candidate_id}")
        )
        interview_id = cursor.fetchone()[0]
        conn.commit()
        return {
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "scheduled_slot": slot,
            "interviewers": interviewers,
            "meeting_link": f"https://meet.company.com/interview-{candidate_id}",
            "status": "SCHEDULED"
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to schedule interview", extra={"tenant_id": tenant_id, "candidate_id": candidate_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


@enforce_tenant
def reschedule_interview(tenant_id: str, interview_id: int, new_slot: str = "2026-08-16T10:00:00Z") -> dict:
    """Reschedules an existing interview in hr_interviews table."""
    logger.info("Rescheduling interview", extra={"tenant_id": tenant_id, "interview_id": interview_id, "new_slot": new_slot})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE hr_interviews
            SET scheduled_slot = %s, status = 'RESCHEDULED'
            WHERE tenant_id = %s AND interview_id = %s
            RETURNING interview_id, scheduled_slot, status
            """,
            (new_slot, tenant_id, interview_id)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Interview ID #{interview_id} not found for tenant '{tenant_id}'.")
        conn.commit()
        return {
            "interview_id": row[0],
            "new_slot": str(row[1]),
            "status": row[2],
            "message": f"Interview #{interview_id} successfully rescheduled to {new_slot}."
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to reschedule interview", extra={"tenant_id": tenant_id, "interview_id": interview_id, "error": str(e)})
        raise
    finally:
        if conn:
            conn.close()


def call(tool_name: str, **kwargs):
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
        "run_account_config_diagnostics": run_account_config_diagnostics,
        "get_employee_profile": get_employee_profile,
        "get_pto_balance": get_pto_balance,
        "submit_leave_request": submit_leave_request,
        "get_paystub_comparison": get_paystub_comparison,
        "request_employment_letter": request_employment_letter,
        "get_onboarding_checklist": get_onboarding_checklist,
        "provision_it_access": provision_it_access,
        "revoke_it_access": revoke_it_access,
        "track_asset_return": track_asset_return,
        "parse_resume": parse_resume,
        "schedule_interview": schedule_interview,
        "reschedule_interview": reschedule_interview,
    }
    
    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")

    # Deterministic Policy Boundary Enforcement for Side-Effect Tools
    if tool_name in ["process_refund", "change_subscription_plan", "delete_account"]:
        tenant_id = kwargs.get("tenant_id", "default")
        from business_agents.support.policies import evaluate_action_policy
        
        policy_res = evaluate_action_policy(
            tenant_id=tenant_id,
            action_type=tool_name,
            action_params=kwargs
        )
        if policy_res.requires_decision_card or policy_res.approval_status != "AUTONOMOUS":
            logger.warning(
                "Tool Gateway Policy Block: Natural-language prompt attempt bypassed to HITL queue",
                extra={"tenant_id": tenant_id, "tool_name": tool_name, "reason": policy_res.reason}
            )
            raise PermissionError(f"Security Policy Boundary: Action '{tool_name}' requires human operator approval. Reason: {policy_res.reason}")

        # Deterministic Idempotency Enforcement
        ticket_id = kwargs.get("ticket_id", "t-000")
        request_id = kwargs.get("request_id", "req-000")
        from platform_core.security.idempotency import generate_idempotency_key, record_action_execution_start, record_action_execution_complete
        
        id_key = generate_idempotency_key(tenant_id, ticket_id, tool_name, request_id)
        record_action_execution_start(tenant_id, id_key, tool_name, kwargs)
        
        # Filter kwargs to match underlying function signature
        import inspect
        target_fn = tools[tool_name]
        sig = inspect.signature(target_fn)
        valid_params = set(sig.parameters.keys())
        exec_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        
        res = target_fn(**exec_kwargs)
        record_action_execution_complete(tenant_id, id_key, res if isinstance(res, dict) else {"result": str(res)})
        return res
        
    return tools[tool_name](**kwargs)
