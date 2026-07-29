# Tier 3 Master Execution Roadmap — Enterprise AI Support Agent (Flagship Enterprise & FinOps)

This document contains the micro-step execution plan for **Tier 3 (Flagship Enterprise & FinOps)** of the Enterprise AI Support Agent, fully aligned with `Enterprise_AI_Support_Agent_Detailed_Brief.txt`, `rules.md`, `.agents/AGENTS.md`, and `platform_core`.

---

## Architectural Guardrails & SDK Rule Compliance
* **Canonical Support Outcome Event**: All Tier 3 subsystems (Evaluation, Quiet Failure, FinOps, Reporting, Incident Intelligence, Continuous Improvement) consume a single canonical source of truth: `SupportOutcomeEvent`.
* **North Star Metric**: **Verified Resolution Rate** (Customer-confirmed resolution backed by Answer Truth, Action Truth, and Outcome Truth).
* **SDK Isolation Rule**: Evaluation, FinOps, and Security features integrate strictly through `platform_core.sdk`.
* **Tenant Isolation**: Every event, metric, and report must be strictly scoped by `tenant_id`.

---

## Phase 3.1 — Canonical Support Outcome Event & Truth Evaluation Foundation

### Micro-Step 3.1.1 — Canonical `SupportOutcomeEvent` (`platform_core/events.py` & `business_agents/support/events.py`)
* **Goal**: Implement the canonical `SupportOutcomeEvent` published to the Event Bus (`events` table) containing:
  `{ticket_id, tenant_id, customer_id, initial_intent, severity, ai_handled, human_handled, actions_taken, escalation, stated_resolution, verified_resolution, reopened, repeat_contact, resolution_attribution, ai_cost, human_intervention, final_outcome}`.
* **Verification**: Verification script publishing a test `SupportOutcomeEvent` and asserting payload structure in event bus.

### Micro-Step 3.1.2 — Truth-Centric Evaluator Engine (`business_agents/support/evaluation/`)
* **Brief Reference**: Section 6.1 AI Evaluation Framework & Section 11 Evaluation Bar.
* **Goal**: Build LLM-as-a-Judge and deterministic evaluators for the 3 Pillars of Truth:
  1. **Answer Truth**: Correctness, Groundedness, Relevance, Completeness.
  2. **Action Truth**: Tool Chain Correctness (Correct tool selected, correct arguments, valid authorization, execution verification).
  3. **Outcome Truth & Escalation Accuracy**: Escalation Precision & Recall (*Was escalation necessary? Should un-escalated tickets have been escalated?*).
* **Verification**: Evaluation test script scoring sample interactions against golden dataset asserting Answer, Action, and Escalation scores.

---

## Phase 3.2 — Quiet Failure, Reopen & Resolution Attribution Engine

### Micro-Step 3.2.1 — Quiet Failure & Silent Escalation Detector (`business_agents/support/resolution_verifier.py`)
* **Brief Reference**: Section 6.2 Quiet Failure Detection.
* **Goal**: Detect quiet failures (AI claimed resolved, but customer reopened ticket within 48h, contacted another channel, or human solved later). Calculate **True Resolution Rate** vs **Silent Failure Rate**.
* **Verification**: Test script running simulated customer follow-up events asserting True vs Silent Failure rate calculations.

### Micro-Step 3.2.2 — Resolution Attribution Engine (`business_agents/support/attribution.py`)
* **Goal**: Determine true cause of ticket resolution:
  `AI-assisted resolution`, `Human-assisted resolution`, `Self-resolved`, `Incident-resolved`, or `Unknown`.
* **Verification**: Unit test verifying resolution attribution classification logic.

---

## Phase 3.3 — AI FinOps & Budget Controls (`platform_core/cost.py` & `business_agents/support/finops.py`)

### Micro-Step 3.3.1 — Support AI FinOps & Cost Per Verified Resolution
* **Brief Reference**: Section 6.3 AI FinOps and Cost Management.
* **Goal**: Track Total AI cost, cost per ticket, cost per resolution, and **cost per verified resolution**. Enforce tenant daily budget caps, token limits, and spend anomaly alerts.
* **Verification**: Unit test script verifying cost calculations and budget limit alert triggers.

---

## Phase 3.4 — Risk-Aware Dynamic Model Router (`platform_core/ai_gateway.py` & `business_agents/support/model_router.py`)

### Micro-Step 3.4.1 — Complexity & Risk-Based Dynamic Model Routing
* **Brief Reference**: Section 6.4 Model Routing.
* **Goal**: Route models dynamically based on task complexity, risk score, and evaluation quality:
  * Simple FAQ $\rightarrow$ Groq / Gemini Flash (Low Cost)
  * Technical Diagnosis $\rightarrow$ Claude 3.5 / GPT-4o (High Reasoning)
  * High Risk Action $\rightarrow$ Advanced Model + Mandatory HITL Validation
* **Verification**: Test script verifying model selection based on intent and risk score.

---

## Phase 3.5 — Incident Intelligence & Pattern Cluster Detector (`business_agents/support/incidents.py`)

### Micro-Step 3.5.1 — Support Incident Intelligence & Surge Detector
* **Brief Reference**: Section 6.6 Incident Intelligence.
* **Goal**: Correlate similar incoming support issues (e.g. 50 customers reporting API 500 error on same endpoint at same time). Auto-create `Incident` object, group affected tickets, alert support teams, and provide consistent status responses.
* **Verification**: Verification script simulating surge in duplicate error reports asserting automated `Incident` creation and ticket grouping.

---

## Phase 3.6 — Automated 24-Hour Support Operations Reporter (`platform_core/subscribers/daily_report.py`)

### Micro-Step 3.6.1 — Daily Support Operations Intelligence & Reporter
* **Brief Reference**: Section 6.7 Support Operations Intelligence & Section 13 Daily Activity Report Logic.
* **Goal**: Aggregates support metrics every 24h consuming `SupportOutcomeEvent`:
  * Total Volume & AI vs Human handling
  * Verified Resolutions vs Stated Resolutions
  * Escalations, SLA breaches, Customer Sentiment
  * Top Issue Categories & Incident patterns
  * AI Spend & Cost per verified resolution
  * Knowledge gaps & Knowledge Health Scores
* **Verification**: Test script running daily report subscriber asserting generated metrics report format.

---

## Phase 3.7 — Support Replay & Simulation Lab (`platform_core/replay.py` & `business_agents/support/simulation.py`)

### Micro-Step 3.7.1 — Support Historical Replay & Regression Lab
* **Brief Reference**: Section 6.9 Replay and Simulation Lab.
* **Goal**: Replay historical support ticket transcripts against new prompts, models, retrieval strategies, or policy rules to calculate regression metrics prior to production deployment.
* **Verification**: Verification script executing historical ticket replay.

---

## Phase 3.8 — Controlled Continuous Improvement Engine (`business_agents/support/continuous_improvement.py`)

### Micro-Step 3.8.1 — Continuous Improvement Recommendation & Approval Loop
* **Brief Reference**: Section 6.8 Continuous Improvement.
* **Goal**: Automatically analyze root causes of quiet failures or knowledge gaps and generate prompt/knowledge update recommendations. Require **Human Operator Approval** and automated **Replay Regression Testing** before updating production behavior.
* **Verification**: Test script submitting failure root cause asserting generated recommendation and approval workflow.

---

## Phase 3.9 — Enterprise Security & Governance (`platform_core/security/`)

### Micro-Step 3.9.1 — Enterprise Security Guardrails & Governance
* **Brief Reference**: Section 8 Security, Privacy, and Governance.
* **Goal**: Enforce Prompt Injection Detection, Knowledge Poisoning Protection, PII Redaction (`email`, `phone`, `ssn`), Role-Based Access Control (RBAC), and Execution Tracing.
* **Verification**: Unit test script testing prompt injection payloads and PII redaction.
