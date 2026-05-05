# Design Review — `decisions.md`

### Decision 1: History pruning uses naive slice deletion
**Verdict:** Disagree
**Why:** `del history_list[:-N]` can split a paired assistant tool_use block from its user tool_result block across the deletion boundary, producing a malformed message sequence that the API will reject.
**Alternative:** Prune at full turn boundaries, treating each assistant-response + tool_result pair as an atomic unit that must be kept or dropped together.

---

### Decision 2: The regex parser extracts `FIELD: value` pairs from model output
**Verdict:** Partially Agree
**Why:** The regex is reliable given the tight system prompt constraints, but raw text parsing violates AGENTS.md §2 and is brittle if the model deviates from the expected format (e.g., adds preamble, uses different punctuation, or wraps values across lines).
**Alternative:** Instruct the model to return a JSON object and parse with `json.loads`, or use a dedicated tool-call return to enforce structure at the API level.

---

### Decision 3: The system prompt is stored as a Python constant in `prompts.py`
**Verdict:** Disagree
**Why:** Hardcoding the prompt requires a full code deploy for every prompt iteration, violating AGENTS.md §4 and eliminating any ability to version or hot-swap prompts in production.
**Alternative:** Load the prompt at startup from a config service, YAML file, or environment-keyed store, enabling updates without a deploy.

---

### Decision 4: No retry logic on `messages.create()` calls
**Verdict:** Disagree
**Why:** Transient rate limits and network errors will silently drop tickets with no recovery path, which is unacceptable in a batch triage pipeline (AGENTS.md §6 mandates retry at the call site).
**Alternative:** Wrap `messages.create()` with `@retry(stop=stop_after_attempt(3), wait=wait_exponential())` from the `tenacity` library directly in `agent.py`.

---

### Decision 5: `response.content[0].text` is accessed without checking block type
**Verdict:** Disagree
**Why:** If `content[0]` is a `ToolUseBlock` (or the list is empty), this raises `AttributeError` and crashes the pipeline; AGENTS.md §7 is explicit that block type must be checked before accessing type-specific attributes.
**Alternative:** Iterate `response.content` and return the first block where `block.type == "text"`, raising `ValueError` if none exists.

---

### Decision 6: The audit log uses a module-level mutable list (`_audit_log = []`)
**Verdict:** Disagree
**Why:** Module-level mutable state is unsafe under concurrent request handling (race conditions on append) and makes the log impossible to reset between batch runs or test cases, violating AGENTS.md §8.
**Alternative:** Inject an `AuditLogger` instance into the tool handler so each batch session owns an isolated log with a clean lifecycle.
