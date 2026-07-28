"""
run_support_agent.py

Standalone CLI Test Runner for the Enterprise AI Support Agent.
Allows testing the compiled LangGraph pipeline interactively or via scenario presets.

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

from business_agents.support.graph import support_pipeline

PRESET_TEST_TICKETS = [
    {
        "title": "1. General FAQ Policy Query",
        "message": "What is your refund policy and SLA response time?"
    },
    {
        "title": "2. Technical API Error (Diagnosis)",
        "message": "Getting 500 Internal Server Error when calling POST /api/v1/auth/login endpoint."
    },
    {
        "title": "3. High-Risk Refund Request (HITL Decision Card)",
        "message": "I demand an immediate $500 refund for invoice 9842 because your service was down all week!"
    },
    {
        "title": "4. Critical Incident Escalation (8-Part Handoff)",
        "message": "URGENT: Entire production database cluster is unresponsive! Escalation required!"
    }
]


def print_banner():
    print("\n==================================================================")
    print("      ENTERPRISE AI SUPPORT AGENT - CLI TEST RUNNER      ")
    print("==================================================================\n")


def execute_ticket(inbound_message: str, tenant_id: str = "tenant-1"):
    print(f"\n[INBOUND TICKET] Message: {inbound_message}\n")
    print("Executing LangGraph Support Pipeline via Groq AI...\n")
    
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
        print(f"Frustration Score    : {final_state.get('frustration_score', 0.0):.2f} (Churn Risk: {final_state.get('churn_risk', False)})")
        
        hypotheses = final_state.get("diagnostic_hypotheses", [])
        if hypotheses:
            print(f"Diagnostic Hypotheses: {json.dumps(hypotheses)}")
            
        evidence = final_state.get("retrieved_evidence", [])
        print(f"Knowledge RAG Chunks : {len(evidence)} evidence chunks retrieved")
        
        print(f"Action Guardrail Risk: {final_state.get('suggested_action', {}).get('risk', 'LOW')}")
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


def main():
    print_banner()
    
    print("Select an option:")
    for ticket in PRESET_TEST_TICKETS:
        print(f"  {ticket['title']}")
    print("  5. Custom Support Message")
    print("  6. Run All Presets Batch Test")
    print("  0. Exit\n")
    
    try:
        choice = input("Enter choice (0-6) [default: 6]: ").strip()
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
    else:
        print("\nExiting Support Agent Test Runner. Goodbye!\n")


if __name__ == "__main__":
    main()
