## Rule 1 — No code without a confirmed spec

Before writing any code, you must restate back to me:
- The exact function name and signature (parameter names, types, return type)
- What it should do, step by step
- What it should do when something goes wrong (error case)

If I haven't given you one of these three things, **stop and ask me before writing code.** Do not guess a return type. Do not guess an error-handling behavior. Do not invent a parameter that wasn't specified.

## Rule 2 — One step at a time, no jumping ahead

Each step in the roadmap is self-contained. You will only write code for the **current step I tell you we're on.**

- Do not add code from a later phase "while you're at it," even if it seems related or helpful.
- Do not add retry logic, caching, logging, or extra validation beyond what the step explicitly asks for, unless I request it.
- If you think a later step's concern is relevant right now, **tell me, don't silently add it.**

## Rule 3 — Never build on an unconfirmed previous step

If the current step depends on a previous step's output (e.g. Step 1.4 depends on Step 1.1–1.3 working), you must ask:

> "Have you confirmed Step [X] is working — did the deliverable check pass?"

If I haven't confirmed it, **do not write the next step's code.** Wait for my confirmation. Code built on a broken foundation produces bugs that are hard to trace back to the real cause.

## Rule 4 — Ambiguity is a stop signal, not a guessing game

If my instruction is unclear, incomplete, or could reasonably mean two different things — **stop and ask a specific clarifying question.** Do not pick the interpretation that seems most likely and proceed. Do not fill gaps with "reasonable defaults" unless I've explicitly told you to.

Examples of what must trigger a question, not an assumption:
- A field type isn't specified (string vs enum? required vs optional?)
- An error case isn't described (what happens if this API call fails?)
- A library or version isn't named, and more than one common option exists
- The expected return shape isn't given (single object? list? wrapped in a status field?)

## Rule 5 — State exactly what changed, every time

After writing or editing code, give me a short, plain list of:
1. What files were created or changed
2. What each function now does (one line per function)
3. Anything you assumed that I should double check

No long explanations. No marketing language about how good the code is. Just the facts I need to verify it.

## Rule 6 — Don't introduce new dependencies silently

If a step requires a new library that wasn't already named in the spec, **tell me the exact package name and ask before installing it.** Do not substitute a different library than the one named in the spec (e.g. don't swap `pdfplumber` for `PyPDF2` because you think it's better — if I named a tool, use that tool).

## Rule 7 — Match existing patterns, don't reinvent them

If earlier code in this project already established a pattern (e.g. how errors are logged, how database sessions are opened, how API responses are shaped), **follow that exact pattern in new code** unless I tell you to change it. Don't introduce a second, different way of doing the same thing elsewhere in the codebase.

## Rule 8 — Tests/verification before moving on

After writing a step's code, tell me exactly how to verify it works (a command to run, an endpoint to call, what output to expect). Do not mark a step as "done" — I decide when a step is done, after I've verified it myself.

## Rule 9 — No silent failures, anywhere / Professional and gracefull error handling is compulsory

Every external call (Gemini, Gmail, Slack, database, file I/O, HTTP request) must be wrapped in proper error handling. A failure must always do at least one of these — never just disappear:
- Get logged with enough detail to debug later (what failed, what input caused it, what the actual exception message was)
- Get surfaced to the caller (raised, returned as an error response, or added to a visible error list)
- Get retried with a defined limit, if retrying is the correct behavior for that specific failure

**Banned patterns** — call these out if you see them, don't write them:
- A bare `except: pass` or `except Exception: pass` that swallows an error with no log and no re-raise
- Returning `None` or an empty list on failure with no log line explaining why
- Catching an exception just to print it and continue, with no record saved anywhere persistent
- A `try/except` so broad it catches and hides bugs that should have crashed loudly (e.g. a typo in a variable name shouldn't be silently caught as "API failed")

When you wrap something in try/except, always tell me explicitly: what specific exception(s) you're catching, why catching it is correct for that case, and what happens after (logged + skip / logged + retry / logged + raise).

## Rule 10 — Structured logging, not print statements

Once we're past throwaway test scripts, use proper logging (Python's `logging` module, or an equivalent structured logger) instead of `print()`. Every log line should make sense to someone reading it without the code open. Minimum standard per log line:
- A log level (INFO for normal events, WARNING for recoverable issues, ERROR for failures that needed handling)
- What happened, in plain language
- The relevant identifier (document_id, email_id, request_id) so one event can be traced through the whole pipeline

Tell me which logger setup you're using and where logs are written (console, file, or both) the first time you introduce logging — don't switch logging approaches partway through the project without telling me.

## Rule 11 — Frontend performance is not optional polish

This is a production-grade app, not a prototype. Apply these by default, without me having to ask each time:
- Lists of data (emails, contacts, query results) are paginated or virtualized — never render an unbounded list all at once
- API calls that can be debounced (search inputs, filters) are debounced — no firing a request on every keystroke
- Loading states and skeletons are shown during fetches — never a blank screen with no feedback
- Images and large assets are sized appropriately, not loaded at full resolution and shrunk with CSS
- No unnecessary re-renders — flag if you're about to write something that re-renders a large list/component on every keystroke or every poll tick, and propose the fix (memoization, narrower state) instead

If a performance tradeoff exists (e.g. real-time updates vs. polling interval, client-side filtering vs. server-side), tell me the tradeoff in one line and let me decide — don't pick silently.

## Rule 12 — Production-grade means explicit about failure modes, not just happy paths

For every new feature, before considering it done, you must tell me:
- What happens if the input is empty / malformed / missing a field
- What happens if an external service (Gemini, database, API) is slow or down
- What the user/caller actually sees in each of those cases (not just what the server does internally)

A feature that only handles the happy path is not done, even if the demo works.


**Rule 13 — No schema changes without confirmation**
Migrations (new table, new column, changed type) proposed as a diff first — apply nahi karna jab tak confirm na ho. Ek galat migration multi-tenant data ke saath messy ho sakta hai.

**Rule 14 — Idempotency for anything that can run twice**
Since your spec's own testing bar (§11) requires "duplicate execution" handling — every write that could re-run (send_email, update_crm, book_meeting) must check "did this already happen" before acting, not just handle errors after the fact. Gemini should state explicitly how duplicate-prevention works for that specific action.

**Rule 15 — Secrets and PII never appear in logs, ever**
Explicit ban: no API key, email content, or contact PII printed/logged in plaintext, even in debug logging. This is stricter than Rule 10 — worth calling out separately since it's easy to forget during quick debugging.

**Rule 16 — Mock external/paid or rate-limited calls during dev**
Gemini free tier has strict RPM/RPD limits. During iterative dev/testing, Gemini should default to a mock/stub for `sdk.ai.generate()` and any Tool Gateway call unless you explicitly say "use the real API for this test." Saves your rate-limit budget for actual verification runs.

**Rule 17 — Module boundaries are enforced, not just conventions**
Per your spec: Business Agent Layer can only import Platform SDK — never Postgres, Redis, or Gemini directly. If Gemini writes code that breaks this boundary "just this once," flag it, don't write it.

**Rule 18 — Destructive operations require explicit confirmation**
Any `DROP`, `DELETE`, `TRUNCATE`, or bulk overwrite — state exactly what will be deleted and wait for a yes before running it, even in a dev database.

**Rule 19 — One step, one commit**
Each roadmap step = one commit with a message referencing the step number (e.g. `Step 2.4: Tool Gateway minimum capabilities`). Makes it trivial to `git revert` a single bad step without touching others — useful given Rule 3's "don't build on unconfirmed steps."

**Rule 20 — Zero Assumption Import & Signature Verification**
NEVER assume or guess file paths, module names, function signatures, or return types. ALWAYS inspect the actual source code of any module BEFORE importing or invoking it.

**Rule 21 — Strict Architectural Boundary Enforcement (SDK Isolation)**
Business Agent code (`business_agents/support/`) MUST ONLY import `platform_core.sdk` (`from platform_core.sdk import sdk`). Direct imports of DB drivers (`pg8000`), `redis`, `google.genai`, `openai`, or raw SQL inside business agents are strictly banned.

**Rule 22 — Zero Regression & Existing Code Preservation**
Adding new features must NEVER break, delete, or alter existing working business agent flows (Sales Agent) or platform core capabilities.

**Rule 23 — No Declaration of Success Without Verification Execution**
Editing a file does NOT mark a step complete. You MUST run a verification script/command and confirm clean execution logs before declaring success.

**Rule 24 — Mandatory Tenant Isolation on Every Database Query**
Every single database query or insert MUST explicitly filter/insert by `tenant_id`.

**Rule 25 — Idempotency & Duplicate Action Prevention**
Check whether side-effect write actions (`send_email`, `update_crm`, `create_ticket`) have already been performed before executing.

**Rule 26 — Comprehensive Error Logging & Event Publishing**
Swallowing exceptions silently is banned. Catching exceptions must log structured metadata via `sdk.get_logger(__name__)` and publish `workflow.failed` via `sdk.events.publish()`.

**Rule 27 — Strict Discussion vs. Execution Boundary**
NEVER edit or write code while the user is discussing ideas, reviewing specs, or planning. Code edits are ONLY allowed when the user explicitly instructs to write/execute code for a confirmed step.

**Rule 28 — Micro-Steps & Zero-Bug Incrementality**
Implementation MUST proceed in tiny, atomic micro-steps (e.g. 1 data structure or 1 single function at a time). Never bundle multiple files into one step. Verify every micro-step immediately before proceeding.


---

### Quick checklist (for you, before sending any prompt to Gemini)

- [ ] Did I give the exact function signature / return type?
- [ ] Did I describe the error case?
- [ ] Have I confirmed the previous step actually works?
- [ ] Am I asking for exactly one step, not multiple?
- [ ] If this touches an external call, did I confirm logging + failure behavior is specified, not left to guesswork?
- [ ] If this is a frontend step involving a list, search, or live data, did I think about pagination/debouncing/loading state upfront?

If any box is unchecked, expect Gemini to stop and ask rather than proceed.

