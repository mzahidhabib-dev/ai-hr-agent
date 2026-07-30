# Phase A Roadmap — Production Hardening & Controlled Deployment Validation

This document contains the micro-step execution plan for **Phase A: Production Hardening & Controlled Deployment Validation**, fully aligned with `rules.md`, `.agents/AGENTS.md`, and client mandates.

---

## Core Architectural Principle
> **"The LLM should be intelligent, but it must never be authoritative over security, authorization, financial limits, or tenant isolation."**

---

## Phase A Execution Schedule

### Micro-Step A.1 — Idempotency & Duplicate-Action Protection Engine (`platform_core/security/idempotency.py`)
* **Goal**: Implement deterministic idempotency keys (`idempotency_key = f"{tenant_id}:{ticket_id}:{action_type}:{request_id}"`) preventing duplicate tool executions (refunds, plan changes, account actions) on retries or network timeouts.
* **Verification**: Unit test suite `tests/test_support_idempotency.py` asserting zero duplicate executions.

### Micro-Step A.2 — HITL Concurrency Safety & Optimistic Locking (`platform_core/decision_cards.py`)
* **Goal**: Add explicit state transitions (`WAITING_FOR_HUMAN` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTING` $\rightarrow$ `EXECUTED`) and optimistic locking to `support_decision_cards` table. Track `approved_by`, `approved_at`, `executed_at`.
* **Verification**: Test script `tests/test_support_hitl_concurrency.py` asserting concurrent operator approvals fail gracefully.

### Micro-Step A.3 — Authoritative Tool Gateway Policy Boundary (`business_agents/support/policies.py`)
* **Goal**: Enforce strict deterministic policy checks inside `platform_core/tool_gateway.py` before executing any side-effect tool call, ensuring natural-language prompts can never bypass financial limits or authorization.
* **Verification**: Test script `tests/test_support_policy_authority.py` asserting prompt injection attacks cannot trigger unauthorized tool calls.

### Micro-Step A.4 — Comprehensive Cross-Layer Multi-Tenant Isolation Suite (`tests/test_support_tenant_isolation_matrix.py`)
* **Goal**: Execute negative integration tests verifying Tenant A can never retrieve or mutate Tenant B data across API, LangGraph State, RAG, Memory, Database, Tools, and Events.
* **Verification**: Test script `tests/test_support_tenant_isolation_matrix.py` asserting 100% clean isolation.

### Micro-Step A.5 — Failure & Resilience Test Suite (`tests/test_support_resilience_failures.py`)
* **Goal**: Simulate LLM provider timeouts, Redis unavailability, and database connection timeouts to verify zero data loss and fallback to HITL escalation.
* **Verification**: Test script `tests/test_support_resilience_failures.py` asserting graceful degradation.
