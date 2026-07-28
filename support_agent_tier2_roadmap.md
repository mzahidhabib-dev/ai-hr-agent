# Tier 2 Execution Roadmap — Enterprise AI Support Agent (Premium Support Intelligence)

This document contains the micro-step execution plan for **Tier 2 (Premium Support Intelligence)** of the Enterprise AI Support Agent, fully aligned with `Enterprise_AI_Support_Agent_Detailed_Brief.txt`, `rules.md`, `.agents/AGENTS.md`, and `platform_core`.

---

## Architectural Guardrails & SDK Rule Compliance
* **SDK Isolation Rule**: All support tool calls must be registered in `platform_core/tool_gateway.py` and invoked strictly via `sdk.tools.call()`.
* **Idempotency**: All write tools (`refund`, `cancel_subscription`, `resend_invoice`, `update_ticket`) must check if the action has already been performed before executing.
* **Tenant Isolation**: All tool executions and database operations must filter by `tenant_id`.

---

## Phase 5: Autonomous Support Tools & Action Guardrails Engine

### Micro-Step 5.1 — Customer Ops & Billing Tool Suite (`business_agents/support/tools/billing.py` & `platform_core/tool_gateway.py`)
* **Brief Reference**: Section 5.1 Autonomous Support Actions.
* **Tools**:
  * `lookup_customer_profile(tenant_id, customer_id)`
  * `lookup_invoice(tenant_id, invoice_id)`
  * `resend_invoice(tenant_id, invoice_id, email)`
  * `process_refund(tenant_id, invoice_id, amount, reason)` (With idempotency check)
  * `change_subscription_plan(tenant_id, customer_id, new_plan_id)`
* **Verification**: Unit test script verifying input validation, idempotency checks, and execution results.

### Micro-Step 5.2 — Technical Diagnostic & Service Check Tools (`business_agents/support/tools/diagnostics.py`)
* **Brief Reference**: Section 5.1 & Section 5.3 Troubleshooting Agent.
* **Tools**:
  * `query_api_usage_logs(tenant_id, customer_id, timeframe)`
  * `check_service_health(service_name)`
  * `run_account_config_diagnostics(tenant_id, customer_id)`
* **Verification**: Test script running diagnostic tools against test data.

### Micro-Step 5.3 — Configurable Action Policy Engine & Guardrails (`business_agents/support/graph/policies.py`)
* **Brief Reference**: Section 5.2 Policy and Action Guardrails.
* **Goal**: Build a configurable policy engine evaluating action risk:
  * Refund $\le \$50$: Autonomous
  * Refund $\$50 - \$500$: Human Review (Decision Card `PENDING_APPROVAL`)
  * Refund $> \$500$: Mandatory Human Approval
  * Delete Account / Enterprise Cancellation: Mandatory Human Approval
  * Security Incident: Immediate Escalation
* **Verification**: Verification script passing test action requests through `evaluate_action_policy()` asserting correct permission and approval status.

---

## Phase 6: Advanced Support Intelligence & Resolution Verification

### Micro-Step 6.1 — Customer Frustration & Churn Radar
* **Brief Reference**: Section 5.4 Customer Frustration Intelligence.
* **Goal**: Detect repeated questions, repeated failed solutions, anger, cancellation intent, and churn risk. Dynamically boost escalation priority in `SupportState`.
* **Verification**: Test script passing frustrated/angry customer messages asserting dynamic priority boost.

### Micro-Step 6.2 — Unified Cross-Channel Customer Memory Extension
* **Brief Reference**: Section 5.5 Unified Customer Memory.
* **Existing Code Linkage**: Reuses and extends `platform_core/memory.py`.
* **Goal**: Maintain Short-term memory (current conversation troubleshooting steps) and Long-term memory (previous issues, preferences, resolutions, known environment specs) across channels.
* **Verification**: Verification script asserting memory persistence and tenant-isolated retrieval across separate conversations.

### Micro-Step 6.3 — AI Resolution Verification Engine
* **Brief Reference**: Section 5.7 AI Resolution Verification.
* **Goal**: Track True Resolution vs Quiet Failure:
  1. Monitor customer replies after response.
  2. Detect ticket reopening within 48 hours.
  3. Detect cross-channel contact or repeat issue creation.
  4. Calculate **Verified Resolution Rate**, **False Resolution Rate**, **Reopen Rate**, and **Repeat Contact Rate**.
* **Verification**: Test script simulating reopened tickets asserting accurate calculation of Verified vs False Resolution rates.

### Micro-Step 6.4 — Knowledge Gap & Conflict Detector
* **Brief Reference**: Section 5.8 Knowledge Gap Detection.
* **Goal**: Detect unanswered questions, low-confidence search results, high escalation topics, and conflicting documentation. Generate automated documentation recommendations.
* **Verification**: Verification script running unanswerable queries asserting gap log creation.
