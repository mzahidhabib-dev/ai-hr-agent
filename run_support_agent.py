"""
run_support_agent.py

Standalone CLI Test Runner for Enterprise AI Support Agent (Tier 1 & Tier 2).

Allows testing:
  - Tier 1: StateGraph, Groq AI Classification, RAG Search, Decision Cards, Escalation
  - Tier 2: Billing & Diagnostic Tools, Frustration/Churn Radar, Unified Memory, Resolution Verifier, Knowledge Gap Detector

Usage:
  python run_support_agent.py
"""

import sys
import os
import json
from dotenv import load_dotenv

# Reconfigure stdout/stderr for UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure environment variables are loaded
load_dotenv(override=True)

# Add root directory to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from platform_core.sdk import sdk
from platform_core.security.tenant_isolation import set_current_tenant
from business_agents.support.graph import support_pipeline
from business_agents.support.frustration_radar import analyze_frustration_and_churn_risk
from business_agents.support.policies import evaluate_action_policy
from business_agents.support.memory import get_customer_unified_memory, save_short_term_memory
from business_agents.support.resolution_verifier import record_ticket_resolution, record_customer_followup, calculate_resolution_metrics
from business_agents.support.knowledge_gap import detect_and_log_knowledge_gap, get_tenant_knowledge_gaps

PRESET_TEST_TICKETS = [
    {
        "title": "1. General FAQ Policy Query (Tier 1 & 2)",
        "message": "What is your refund policy and SLA response time?"
    },
    {
        "title": "2. Technical API Error & Diagnostics (Tier 2 Tools)",
        "message": "Getting 500 Internal Server Error when calling POST /api/v1/auth/login endpoint."
    },
    {
        "title": "3. High-Risk Refund & Frustration Radar (Tier 2 Guardrails)",
        "message": "I demand an immediate $500 refund for invoice 9842! Your service is terrible and unusable!"
    },
    {
        "title": "4. Critical Production Incident & Escalation",
        "message": "URGENT: Entire production database cluster is unresponsive! Escalation required!"
    }
]


def print_banner():
    print("\n==================================================================")
    print("      ENTERPRISE AI SUPPORT AGENT - CLI TEST RUNNER (TIER 1 & 2)  ")
    print("==================================================================\n")


def execute_ticket(inbound_message: str, tenant_id: str = "tenant-1"):
    set_current_tenant(tenant_id)
    print(f"\n[INBOUND TICKET] Message: {inbound_message}\n")
    
    # 1. Tier 2 Frustration & Churn Radar Analysis
    frustration_res = analyze_frustration_and_churn_risk(tenant_id, inbound_message)
    print(f"😡 Frustration Score : {frustration_res.frustration_score:.2f} (Churn Risk: {frustration_res.churn_risk})")
    if frustration_res.reasons:
        print(f"   * Sentiment Reasons: {', '.join(frustration_res.reasons)}")
        
    print("\nExecuting LangGraph Support Pipeline via Groq AI...\n")
    
    config = {"configurable": {"thread_id": "cli-session-1"}}
    initial_state = {
        "tenant_id": tenant_id,
        "inbound_message": inbound_message,
        "channel": "web_chat"
    }
    
    try:
        final_state = support_pipeline.invoke(initial_state, config)
        
        print("------------------------------------------------------------------")
        print(f"Intent Classification : {final_state.get('intent')} (Severity: {final_state.get('severity')}, Urgency: {final_state.get('urgency')})")
        
        # 2. Tier 2 Action Policy Guardrail Check
        policy_res = evaluate_action_policy(tenant_id, final_state.get("intent", "GENERAL"))
        print(f"🛡️ Action Policy Risk : {policy_res.risk_level} (Approval: {policy_res.approval_status})")
        print(f"   * Policy Reason: {policy_res.reason}")
        
        hypotheses = final_state.get("diagnostic_hypotheses", [])
        if hypotheses:
            print(f"Diagnostic Hypotheses: {json.dumps(hypotheses)}")
            
        # 3. Execute Tier 2 Diagnostic Tool via Tool Gateway
        if final_state.get("intent") == "TECHNICAL":
            diag_res = sdk.tools.call("query_api_usage_logs", tenant_id=tenant_id, customer_id="cust-enterprise-999")
            print(f"🛠️ Diagnostic Tool Log: Total Requests: {diag_res.get('total_requests')}, Error Rate: {diag_res.get('error_rate')}")
            
        evidence = final_state.get("retrieved_evidence", [])
        print(f"Knowledge RAG Chunks : {len(evidence)} evidence chunks retrieved")
        
        # 4. Tier 2 Knowledge Gap Detection
        confidence = final_state.get("confidence_score", 85.0)
        gap_res = detect_and_log_knowledge_gap(tenant_id, inbound_message, confidence)
        if gap_res.get("is_gap_flagged"):
            print(f"⚠️ Knowledge Gap Alert: {gap_res.get('recommendation')}")
            
        if final_state.get("decision_id"):
            print(f"Decision Card ID     : #{final_state.get('decision_id')} (Recorded in PostgreSQL for Human Approval)")
            
        action_res = final_state.get("action_result", {})
        if action_res.get("handoff_id"):
            print(f"Human Handoff Package : #{action_res.get('handoff_id')} recorded in PostgreSQL")
            
        print(f"Final Ticket Status  : {final_state.get('status')}")
        print("------------------------------------------------------------------")
        print("GROUNDED AI RESPONSE:")
        print(final_state.get("response_text", "No response text generated."))
        print("------------------------------------------------------------------")
        
        citations = final_state.get("citations", [])
        if citations:
            print("Source Citations:")
            for cit in citations:
                print(f"   * Page {cit.get('page')}: {cit.get('document_name')}")
            print("------------------------------------------------------------------\n")
            
    except Exception as e:
        print(f"\n[ERROR] Failed executing support pipeline: {e}\n")


def test_tier2_tools_demo():
    set_current_tenant("tenant-1")
    print("\n--- TIER 2 AUTONOMOUS TOOLS DEMO ---")
    print("1. Billing Lookup Customer Profile:")
    prof = sdk.tools.call("lookup_customer_profile", tenant_id="tenant-1", customer_id="cust-101")
    print(f"   Result: {prof}")
    
    print("\n2. Technical Diagnostics Check Service Health:")
    health = sdk.tools.call("check_service_health", service_name="all")
    print(f"   Result: {health}")
    
    print("\n3. Process Refund with Idempotency Guardrail:")
    ref1 = sdk.tools.call("process_refund", tenant_id="tenant-1", invoice_id="inv-99", amount=150.0, reason="Downtime")
    print(f"   Run 1 Result: {ref1}")
    ref2 = sdk.tools.call("process_refund", tenant_id="tenant-1", invoice_id="inv-99", amount=150.0, reason="Downtime")
    print(f"   Run 2 (Duplicate Check): {ref2}")
    
    print("\n4. Resolution Verification Engine:")
    rec = record_ticket_resolution("tenant-1", "t-99", "cust-101")
    fol = record_customer_followup("tenant-1", "t-99", "Thank you, that solved it!", 2.0)
    print(f"   Follow-up Result: {fol}")
    metrics = calculate_resolution_metrics("tenant-1")
    print(f"   Tenant Resolution Metrics: {metrics}")
    print("------------------------------------\n")


def main():
    print_banner()
    
    print("Select an option:")
    for ticket in PRESET_TEST_TICKETS:
        print(f"  {ticket['title']}")
    print("  5. Custom Support Message")
    print("  6. Run All Presets Batch Test")
    print("  7. Test Tier 2 Tools & Intelligence Direct Suite")
    print("  0. Exit\n")
    
    try:
        choice = input("Enter choice (0-7) [default: 6]: ").strip()
    except (KeyboardInterrupt, EOFError):
        choice = "0"
        
    if not choice:
        choice = "6"
        
    if choice == "1":
        execute_ticket(PRESET_TEST_TICKETS[0]["message"])
    elif choice == "2":
        execute_ticket(PRESET_TEST_TICKETS[1]["message"])
    elif choice == "3":
        execute_ticket(PRESET_TEST_TICKETS[2]["message"])
    elif choice == "4":
        execute_ticket(PRESET_TEST_TICKETS[3]["message"])
    elif choice == "5":
        try:
            msg = input("Type your custom support question: ").strip()
            if msg:
                execute_ticket(msg)
        except (KeyboardInterrupt, EOFError):
            pass
    elif choice == "6":
        print("\nRunning All 4 Presets Batch Test...\n")
        for ticket in PRESET_TEST_TICKETS:
            print(f"\n>>> Running Preset: {ticket['title']}")
            execute_ticket(ticket["message"])
    elif choice == "7":
        test_tier2_tools_demo()
    else:
        print("\nExiting Support Agent Test Runner. Goodbye!\n")


if __name__ == "__main__":
    main()
