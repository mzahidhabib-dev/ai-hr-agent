# Agent Behavioral Rules & Anti-Mistake Mandates

## Rule Override: Use Real Data with Rate Limiting (Overrides original Rule 16)
The user has explicitly requested to stop mocking AI Gateway and external calls. 
- You MUST use real data and live API calls for testing moving forward.
- Because we are using the free tier of the AI models (Gemini), you MUST implement robust rate-limiting and sleep logic (`time.sleep(15)`) between API calls to prevent 429 Too Many Requests errors. Do not hit the API aggressively in loops.

## Anti-Mistake Rules (Mandatory Compliance)

### Rule 20 — Zero Assumption Import & Signature Verification
- NEVER assume or guess file paths, module names, function signatures, or return types.
- ALWAYS use `view_file` or `grep_search` to verify the actual source code of any module BEFORE importing or invoking it.
- Never invent non-existent packages or refactored imports (e.g. verifying `vector_search.py` vs `searcher.py`).

### Rule 21 — Strict Architectural Boundary Enforcement (SDK Isolation)
- Business Agent code (`business_agents/support/`, `business_agents/sales/`) MUST ONLY import `platform_core.sdk` (`from platform_core.sdk import sdk`).
- Business Agents are strictly forbidden from importing `pg8000`, `psycopg2`, `redis`, `google.genai`, `openai`, `groq`, or writing raw SQL queries. All DB, AI, Event, and Tool interactions MUST go through `sdk`.

### Rule 22 — Zero Regression & Existing Code Preservation
- Adding new features (such as Support Agent) must NEVER break, delete, or alter existing working business agent flows (Sales Agent) or platform core functionality.
- Existing working tests and scripts must remain pass-ready.

### Rule 23 — No Declaration of Success Without Verification Execution
- Editing or creating a file does NOT mark a step complete.
- You MUST run a verification script or execution command (e.g., unit test script or python test runner) and verify clean exit status (code 0) and expected output log before presenting a step as finished.

### Rule 24 — Mandatory Tenant Isolation on Every Database Query
- Every single SQL query or database interaction MUST explicitly filter and insert by `tenant_id`.
- Never execute global queries across multi-tenant tables (`prospects`, `decision_cards`, `audit_logs`, `document_chunks`, `tickets`) without `WHERE tenant_id = %s`.

### Rule 25 — Idempotency & Duplicate Action Prevention
- Before executing any side-effect write action (`send_email`, `update_crm`, `create_ticket`), check whether the action has already been performed for that transaction/decision ID to prevent double dispatches.

### Rule 26 — Zero Tolerance Ultra-Professional Error Handling
- Swallowing exceptions silently (`except: pass`) or returning empty values without logging is strictly banned.
- Every caught exception must log structured metadata using `sdk.get_logger(__name__)` and publish a `workflow.failed` event to `sdk.events.publish()` so failures are visible in audit logs.
- All potential edge cases (null database fields, malformed JSON, network timeouts) must be explicitly handled.

### Rule 27 — Strict Discussion vs. Execution Boundary
- NEVER edit or write code while the user is discussing ideas, reviewing specs, or planning.
- Code edits are ONLY allowed when the user explicitly instructs to write/execute code for a confirmed step.
- During planning/discussion, respond strictly with analysis, questions, and specifications.

### Rule 28 — Micro-Steps & Zero-Bug Incrementality
- Implementation MUST proceed in tiny, atomic micro-steps (e.g., 1 data structure or 1 single node function at a time).
- Never bundle multiple complex files or large features into a single step.
- Every single micro-step MUST be verified immediately before proposing the next micro-step.
