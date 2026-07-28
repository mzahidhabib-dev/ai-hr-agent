# Tier 1 Execution Roadmap — Enterprise AI Support Agent (Production MVP)

This document contains the step-by-step, micro-step execution plan for **Tier 1 (Production MVP)** of the Enterprise AI Support Agent, fully aligned with `Enterprise_AI_Support_Agent_Detailed_Brief.txt`, `rules.md`, `.agents/AGENTS.md`, and existing platform code (`platform_core`, `annual-report-qa-bot`, `business_agents/sales`).

---

## Architectural Guardrails & SDK Rule Compliance
* **SDK Isolation Rule**: All code in `business_agents/support/` MUST ONLY import `platform_core.sdk` (`from platform_core.sdk import sdk`). Direct imports of `pg8000`, `psycopg2`, `redis`, `google.genai`, `openai`, or raw SQL queries inside business agents are strictly banned.
* **Tenant Isolation**: Every SQL query and database operation MUST explicitly filter and insert by `tenant_id`.
* **Zero Silent Failures**: All caught exceptions must log structured metadata via `sdk.get_logger(__name__)` and publish `workflow.failed` via `sdk.events.publish()`.
* **Real APIs with Rate Limiting**: Real Gemini/Groq calls will be used with mandatory `time.sleep(15)` rate-limiting padding between calls on free tier.

---

## Phase 1: Support Pipeline Foundation & State Schema

### Micro-Step 1.1 — Support State Data Schema (`business_agents/support/state.py`)
* **Brief Reference**: Section 4.1, 4.2, 4.3, 4.6.
* **Existing Code Linkage**: Follows structural TypedDict pattern from `business_agents/sales/state.py`.
* **Keys**:
  * `tenant_id: str`
  * `conversation_id: str`
  * `customer_id: str`
  * `external_message_id: str` (For webhook/inbound deduplication)
  * `inbound_message: str`
  * `channel: str`
  * `attachments: list[dict]`
  * `customer_context: dict` (Customer 360: plan, SLA, open tickets, recent errors, VIP status)
  * `intent: str` (`BILLING`, `TECHNICAL`, `ACCOUNT`, `PRODUCT`, `HOW_TO`, `BUG`, `INCIDENT`, `REFUND`, `CANCELLATION`, `SECURITY`, `LEGAL`, `GENERAL`, `ESCALATION`)
  * `severity: str` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  * `urgency: str` (`LOW`, `MEDIUM`, `HIGH`)
  * `frustration_score: float` (0.0 to 1.0)
  * `churn_risk: bool`
  * `retrieved_evidence: list[dict]` (Chunks + page numbers + metadata)
  * `diagnostic_hypotheses: list[str]`
  * `suggested_action: dict` (Tool name + params)
  * `action_result: dict`
  * `response_text: str`
  * `citations: list[dict]` (`page`, `document_name`)
  * `confidence_score: float` (0.0 to 100.0)
  * `status: str` (`NEW`, `CLASSIFIED`, `INVESTIGATING`, `WAITING_FOR_CUSTOMER`, `WAITING_FOR_HUMAN`, `RESOLVED`, `CLOSED`, `REOPENED`)
  * `decision_id: int` (HITL card ID if approval requested)
* **Verification**: Run `python -c "from business_agents.support.state import SupportState; print('State schema OK')"` confirming error-free import.

### Micro-Step 1.2 — Support Prompts & System Instructions (`business_agents/support/prompts.py`)
* **Brief Reference**: Section 4.3, 4.5, 4.7.
* **Goal**: Define immutable prompt templates for Intent & Severity Classification, Technical Diagnosis, Grounded RAG Response Generation, and Human Escalation Summarization.
* **Verification**: Unit test script verifying prompt formatting and template rendering.

---

## Phase 2: Ingestion, Context & Classification Nodes

### Micro-Step 2.1 — Inbound Intake Node (`IntakeNode` in `business_agents/support/nodes.py`)
* **Brief Reference**: Section 4.1 Omnichannel Intake.
* **Goal**: Extract, validate, and normalize inbound payloads (`tenant_id`, `channel`, `conversation_id`, `customer_id`, `external_message_id`, `message`, `timestamp`, `attachments`, `metadata`). Includes **external message ID deduplication** using Redis/Postgres via `sdk` to prevent duplicate processing.
* **Verification**: Test script passing duplicate and unique message payloads to `IntakeNode` asserting deduplication and correct state population.

### Micro-Step 2.2 — Customer 360 Context Node (`CustomerContextNode`)
* **Brief Reference**: Section 4.2 Customer 360 Context.
* **Goal**: Retrieve customer profile, account details, subscription plan, plan limits, account age, open tickets, previous tickets, recent errors, customer value, SLA, and VIP status via `sdk` to populate `customer_context`.
* **Verification**: Verification script asserting Customer 360 context package matches test database records.

### Micro-Step 2.3 — Intent, Severity & Risk Classification Node (`ClassificationNode`)
* **Brief Reference**: Section 4.3 Intent Classification.
* **Goal**: Invoke LLM via `sdk.ai.generate()` to classify intent, urgency (`LOW`, `MEDIUM`, `HIGH`), severity (`LOW` to `CRITICAL`), customer frustration level, cancellation/churn intent, and risk level.
* **Verification**: Verification script passing test customer messages (refunds, technical bugs, anger) to `ClassificationNode` verifying structured JSON outputs.

---

## Phase 3: Multi-Modal Knowledge Retrieval & Grounded Response Nodes

### Micro-Step 3.1 — Support Knowledge Ingestion & Hybrid RAG Node (`KnowledgeRAGNode`)
* **Brief Reference**: Section 4.4 Knowledge Retrieval.
* **Existing Code Linkage**: 
  * Reuses multi-modal extractors from `annual-report-qa-bot/src/ingestion/` (`text_extractor.py`, `table_extractor.py`, `image_extractor.py` Gemini Vision chart descriptions).
  * Reuses RRF Hybrid Search from `annual-report-qa-bot/src/retrieval/hybrid_search.py` (Vector `pgvector` + BM25Okapi + `self_query.py` rewriter) exposed via `sdk.knowledge`.
* **Goal**: Search help center articles, manuals, SOPs, tables, and chart captions; return structured evidence packages filtered by `tenant_id`.
* **Verification**: Verification script running hybrid queries against indexed support docs verifying result relevance and page citation metadata.

### Micro-Step 3.2 — Technical & Operational Diagnosis Node (`DiagnosisNode`)
* **Brief Reference**: Section 5.3 Troubleshooting Agent.
* **Goal**: For `TECHNICAL` or `BUG` intents, analyze symptoms, evaluate environment/logs, check system status via `sdk`, and generate testable diagnostic hypotheses.
* **Verification**: Test script passing technical error queries asserting structured diagnostic hypothesis output.

### Micro-Step 3.3 — Grounded Response Generation Node (`ResponseNode`)
* **Brief Reference**: Section 4.5 Grounded Response Generation.
* **Existing Code Linkage**: Reuses Pydantic JSON schema response pattern from `annual-report-qa-bot/src/retrieval/answer_generator.py`.
* **Goal**: Generate response strictly from retrieved evidence using `sdk.ai.generate()`, attach explicit page/doc citations `[Page X]`, calculate confidence score, and track token usage. Say "I don't know" if evidence is insufficient.
* **Verification**: Verification script verifying strict citation formatting, token cost logging, and rejection of ungrounded questions.

---

## Phase 4: Lifecycle, HITL Escalation & Workflow Graph Assembly

### Micro-Step 4.1 — Action & HITL Guardrail Node (`ActionNode`)
* **Brief Reference**: Section 4.6 Ticket Lifecycle & Section 5.2 Action Guardrails.
* **Existing Code Linkage**: Reuses `platform_core/decision_cards.py` for HITL.
* **Goal**: Check action risk. Low-risk actions execute via `sdk.tools.call()`. High-risk actions (refunds $> \$50$, subscription cancellations, account deletions) call `record_decision()` creating a decision card in `PENDING_APPROVAL` status on the dashboard. Update ticket status to `INVESTIGATING` or `WAITING_FOR_HUMAN`.
* **Verification**: Test script asserting direct execution for low-risk actions and decision card generation for high-risk actions.

### Micro-Step 4.2 — Context-Preserving Human Escalation Node (`EscalationNode`)
* **Brief Reference**: Section 4.7 Human Escalation.
* **Goal**: When confidence is low ($< 70$), knowledge conflicts exist, or risk is critical, assemble the complete **Human Handoff Package**:
  - Customer 360 summary
  - Issue summary
  - Full transcript
  - Relevant evidence
  - Attempted actions & tool results
  - Technical diagnosis
  - Recommended next action
  - Customer sentiment, urgency, SLA, and risk level.
* **Verification**: Verification script checking complete handoff package creation without forcing customer repetition.

### Micro-Step 4.3 — Support LangGraph Assembly (`business_agents/support/graph.py`)
* **Brief Reference**: Section 7 Recommended Agent Graph.
* **Existing Code Linkage**: Reuses LangGraph structure and `@time_node` timing decorator from `business_agents/sales/graph.py` and `nodes.py`.
* **Goal**: Connect all support nodes into a compiled `StateGraph` with conditional routing and checkpointing.
* **Verification**: Full end-to-end integration runner (`test_support_agent_tier1.py`) executing sample tickets across FAQ, Technical, Billing, and Escalation flows.
