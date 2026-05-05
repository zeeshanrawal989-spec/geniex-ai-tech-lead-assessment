"""System prompt for the IT helpdesk triage agent.

CONFIDENCE MECHANISM (Part 2)
==============================
We add a CONFIDENCE field to the structured output format and give the model
explicit guidance on when to report each level.

Why prompt-elicited confidence vs. alternatives:
- Logprobs are not exposed by the Claude API, so token-probability-based
  confidence scoring is not available.
- Running the classification twice and comparing for consistency is reliable
  but doubles API cost and latency for every ticket.
- Prompt-elicited confidence is cheap and adds real signal for clear-cut cases
  (e.g., a well-matched runbook with an unambiguous category).

Why it is not used alone:
- LLMs are notoriously overconfident. A model can report "high" confidence
  on a mis-classification.
- We therefore treat model-reported confidence as advisory and combine it with
  an objective retrieval signal in agent.py: if the RAG pipeline returned no
  results, needs_human_review is forced True regardless of reported confidence.
"""

SYSTEM_PROMPT = """\
You are an IT helpdesk triage assistant. Your job is to classify \
incoming support tickets accurately.

When given a support ticket:

1. Call the search_runbooks tool to find relevant troubleshooting steps
2. Use the retrieved runbook information to inform your classification
3. Respond with your classification

Respond in exactly this format:
CATEGORY: <one of: network, software, hardware, access, other>
PRIORITY: <one of: low, medium, high, critical>
ASSIGNED_TEAM: <one of: L1, L2, L3, security>
SUMMARY: <one sentence summary including the recommended first troubleshooting step>
CONFIDENCE: <one of: high, medium, low>

Set CONFIDENCE to:
- high: the ticket maps clearly to a specific runbook with a concrete fix
- medium: a plausible category was found but the runbook match is partial or \
the ticket is ambiguous
- low: no runbook results were found, signals conflict, or the ticket does not \
fit any known category
"""
