# Solution — Part 1, Section A

---

## Q1: Retrieval Fix

### Is increasing `top_k` from 3 to 10 effective?

No. The `retrieve_chunks` function applies the `similarity_threshold` filter **before** slicing to `top_k`:

```python
scored.sort(key=lambda x: x[1], reverse=True)
return scored[:top_k]           # top_k only limits an already-filtered list
```

If all chunks score below 0.85, `scored` is empty and `scored[:10]` is still empty. Increasing `top_k` has zero effect when the threshold is the binding constraint.

### Root cause

`embed_query` uses brittle exact-substring matching against a hardcoded lookup table:

```python
for pattern, embedding in QUERY_EMBEDDINGS.items():
    if pattern in query_lower or query_lower in pattern:
        return embedding
```

The only VPN pattern registered is `"vpn connection error"`. For TKT-001, the model is likely to generate a query like `"VPN error code 619"` or `"error 619 VPN connection"` — neither of which contains `"vpn connection error"` as a substring, nor is contained by it. The function falls through to the category fallback, which (if `"network"` is absent from the query text) returns a flat embedding `[0.25, 0.25, ...]`. That embedding yields cosine similarities of ~0.61 against all chunks — below the 0.85 threshold — so nothing is returned. The model receives `"No matching runbook found. Escalate to L2 support."` and falls back to parametric knowledge, producing generic VPN advice.

Even in the best case where the query does happen to match `"vpn connection error"`, the retrieval returns both `net-001-a` (generic steps) and `net-001-b` (error 619 specific). The system contains the right content — the routing to it is broken.

### Minimal fix — one line in `retrieval.py`

Add `"error 619"` as a recognized pattern mapped to the VPN embedding:

```python
QUERY_EMBEDDINGS = {
    "vpn connection error": [0.89, 0.10, 0.05, 0.03, 0.85, 0.12, 0.07, 0.04],
    "error 619":            [0.89, 0.10, 0.05, 0.03, 0.85, 0.12, 0.07, 0.04],  # ADD THIS
    "salesforce access":    [0.05, 0.08, 0.03, 0.88, 0.06, 0.09, 0.04, 0.85],
    "excel crash add-in":   [0.07, 0.88, 0.06, 0.04, 0.09, 0.85, 0.08, 0.05],
}
```

Any model query containing `"619"` (e.g. `"error code 619"`, `"vpn error 619"`) now matches via the `pattern in query_lower` check. Both `net-001-a` (~0.9996) and `net-001-b` (~0.9997) score above 0.85. The model sees the error 619 runbook content (`"Error 619: port 1723 is blocked — check router settings"`) and can recommend the correct fix.

---

## Q2: Code Review Triage

| # | Verdict | Reason |
|---|---------|--------|
| A | **Real bug** | `conversation_history` is shared across all tickets in the batch; TKT-002's classification is influenced by TKT-001's context, violating isolation and producing ordering-dependent results (AGENTS.md §10). |
| B | **Real bug** | `del history_list[:-N]` can sever a paired `assistant` tool_use block from its corresponding `user` tool_result block across the cut boundary, producing a malformed message sequence the API will reject with a validation error. |
| C | **Real bug** | `response.content[0].text` raises `AttributeError` if the first block is a `ToolUseBlock`; AGENTS.md §7 mandates iterating content and checking `block.type == "text"` before accessing `.text`. |
| D | **Real bug** | No retry on `messages.create()` means transient rate limits and network errors silently drop tickets with no recovery; AGENTS.md §6 mandates retry with exponential backoff at the call site, not the caller. |
| E | **Acceptable** | A one-line `if` for a single tool is not brittle in practice; the registry pattern (AGENTS.md §5) is appropriate when the tool set grows but is premature optimization here. |
| F | **Acceptable** | The Claude API guarantees required tool inputs satisfy the declared schema; `.get()` defaults are safely redundant. Pydantic validation (AGENTS.md §9) would be warranted if inputs came from an untrusted source. |
