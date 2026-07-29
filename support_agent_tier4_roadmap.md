# Tier 4 Execution Roadmap — Enterprise AI Support Agent (Multi-Tenant REST API & React/TS Frontend)

This document contains the micro-step execution plan for **Tier 4 (Multi-Tenant REST API & React/TS Frontend)** of the Enterprise AI Support Agent, fully aligned with `Enterprise_AI_Support_Agent_Detailed_Brief.txt`, `rules.md`, `.agents/AGENTS.md`, and `platform_core`.

---

## Architectural Guardrails & Rules Compliance
* **Separate Directory**: The React + TypeScript application must be built in a separate root directory (`frontend/`).
* **API Boundary**: Frontend must communicate with backend strictly via REST endpoints using `platform_core.sdk` / FastAPI endpoints.
* **Tenant Isolation**: All API requests and frontend views must include `X-Tenant-ID` header.

---

## Phase 9: Multi-Tenant FastAPI REST Services (`api/`)

### Micro-Step 9.1 — Support Agent REST Endpoints (`api/main.py`)
* **Brief Reference**: Section 1 & Section 4.6 Ticket Lifecycle.
* **Endpoints**:
  * `POST /v1/support/tickets` — Submit inbound support ticket.
  * `GET /v1/support/decisions` — Fetch pending HITL Decision Cards.
  * `POST /v1/support/decisions/{id}/approve` — Approve or reject Decision Card action.
  * `GET /v1/support/handoffs` — Fetch Human Escalation Handoff packages.
  * `GET /v1/support/metrics` — Fetch Support FinOps, Resolution Rates, and Cost metrics.
* **Verification**: Test script asserting HTTP 200 responses for all endpoints.

---

## Phase 10: React + TypeScript Operator & Analytics Dashboard (`frontend/`)

### Micro-Step 10.1 — React + TypeScript App Initialization (`frontend/`)
* **Goal**: Initialize clean Vite React + TypeScript project in separate `frontend/` root folder using vanilla CSS/modern styling.
* **Verification**: Verification script asserting clean `npm run build` exit code 0.

### Micro-Step 10.2 — HITL Decision Card Approval Queue Component (`frontend/src/components/DecisionQueue.tsx`)
* **Goal**: Real-time operator queue displaying pending high-risk Support Decision Cards (Refunds, Plan changes, Account actions) with Approve/Reject controls.
* **Verification**: Component verification.

### Micro-Step 10.3 — Context-Preserving Human Escalation Handoff Viewer (`frontend/src/components/HandoffViewer.tsx`)
* **Goal**: Human agent interface displaying 8-part handoff packages (Customer 360 context, conversation transcript, diagnostic hypotheses, recommended next action) so human agents never ask customers to repeat information.
* **Verification**: Component verification.

### Micro-Step 10.4 — Live Support FinOps & Quality Analytics Dashboard (`frontend/src/components/AnalyticsDashboard.tsx`)
* **Goal**: Real-time analytics displaying Verified Resolution Rate, False Resolution Rate, 48-Hour Reopen Rate, AI Cost per Successful Resolution, and Knowledge Gap Alerts.
* **Verification**: End-to-end integration test of React + TS frontend with FastAPI backend.
