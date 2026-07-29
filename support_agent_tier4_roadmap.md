# Tier 4 Execution Roadmap — Enterprise AI Support Agent (Multi-Tenant REST API & React/TS Frontend)

This document contains the micro-step execution plan for **Tier 4 (Multi-Tenant REST API & React/TS Frontend)** of the Enterprise AI Support Agent, fully aligned with `Enterprise_AI_Support_Agent_Detailed_Brief.txt`, `rules.md`, `.agents/AGENTS.md`, and `platform_core`.

---

## Architectural Guardrails & Rules Compliance
* **Separate Directory**: The React + TypeScript application must be built in a separate root directory (`frontend/`).
* **API Boundary**: Frontend must communicate with backend strictly via REST endpoints using `platform_core.sdk` / FastAPI endpoints.
* **Tenant Isolation**: All API requests and frontend views must include `X-Tenant-ID` header.

---

## Phase 4.1 — Multi-Tenant FastAPI REST Services (`api/`)

### Micro-Step 4.1.1 — Support Agent REST Endpoints (`api/main.py`)
* **Brief Reference**: Section 1 & Section 4.6 Ticket Lifecycle.
* **Endpoints**:
  * `POST /v1/support/tickets` — Submit inbound support ticket & run LangGraph pipeline.
  * `GET /v1/support/decisions` — Fetch pending HITL Decision Cards.
  * `POST /v1/support/decisions/{id}/approve` — Approve or reject Decision Card action.
  * `GET /v1/support/handoffs` — Fetch Human Escalation Handoff Brief packages.
  * `GET /v1/support/metrics` — Fetch Support FinOps, Resolution Rates, and Cost metrics.
* **Verification**: Test script asserting HTTP 200 responses for all endpoints (`tests/test_support_api.py`).

---

## Phase 4.2 — React + TypeScript App Initialization (`frontend/`)

### Micro-Step 4.2.1 — React + TypeScript App Setup (`frontend/`)
* **Goal**: Initialize clean Vite React + TypeScript project in separate `frontend/` root folder using vanilla CSS/modern styling.
* **Verification**: Verification script asserting clean `npm run build` exit code 0.

---

## Phase 4.3 — HITL Decision Card Approval Queue (`frontend/src/components/DecisionQueue.tsx`)

### Micro-Step 4.3.1 — Decision Card Approval Queue Component
* **Goal**: Real-time operator queue displaying pending high-risk Support Decision Cards (Refunds, Plan changes, Account actions) with Approve/Reject controls.
* **Verification**: Component verification.

---

## Phase 4.4 — Context-Preserving Human Escalation Handoff Brief Viewer (`frontend/src/components/HandoffViewer.tsx`)

### Micro-Step 4.4.1 — Handoff Brief Viewer Component
* **Goal**: Human agent interface displaying 8-part handoff packages (Customer 360 context, conversation transcript, diagnostic hypotheses, recommended next action) so human agents never ask customers to repeat information.
* **Verification**: Component verification.

---

## Phase 4.5 — Live Support FinOps & Quality Analytics Dashboard (`frontend/src/components/AnalyticsDashboard.tsx`)

### Micro-Step 4.5.1 — Support FinOps & Quality Analytics Console
* **Goal**: Real-time analytics displaying Verified Resolution Rate, False Resolution Rate, 48-Hour Reopen Rate, AI Cost per Verified Resolution, and Knowledge Gap Alerts.
* **Verification**: End-to-end integration test of React + TS frontend with FastAPI backend.
