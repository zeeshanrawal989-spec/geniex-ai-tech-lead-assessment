"""Orchestrator for the IT triage agent.

CONFIDENCE MECHANISM (Part 2)
==============================
This module contributes the retrieval signal to the overall confidence
determination. Two signals together drive needs_human_review:

  Signal 1 — Model-reported confidence (parser.py):
    The model outputs CONFIDENCE: high/medium/low. "low" triggers review.
    This catches cases where retrieval succeeded but the model is genuinely
    uncertain about category assignment.

  Signal 2 — Retrieval outcome (here):
    We track whether search_runbooks was called and whether it returned
    at least one matching runbook chunk. If the tool was never called, or
    it returned "No matching runbook found", the model classified from
    parametric knowledge alone — an inherently less reliable basis.
    In that case we force needs_human_review=True regardless of the
    model's self-reported confidence.

Why retrieval outcome is the most trustworthy signal:
- It is fully objective — no LLM output is involved.
- A successful retrieval grounds the classification in curated domain
  knowledge. Its absence is a strong indicator that the ticket is outside
  the known runbook coverage and deserves human attention.

Why not alternatives:
- Logprobs: not exposed by the Claude API.
- Double-classification consistency check: reliable but doubles cost/latency.
- Retrieval score threshold: scores are embeddings-dependent and not
  meaningfully comparable across query types in this stub implementation.

Trade-offs:
- We intentionally do NOT fix other known bugs (shared history, no retry,
  no type guard on content[0]) in this diff to keep the change focused on
  the confidence mechanism as specified by the assessment.
"""

from config import client, MODEL, MAX_TOKENS, MAX_HISTORY_MESSAGES
from tools import TOOLS, execute_tool
from prompts import SYSTEM_PROMPT
from parser import parse_triage_response

_NO_RUNBOOK_SENTINEL = "No matching runbook found"


def _prune_history(history_list):
    """Keep only the most recent messages to prevent context exhaustion."""
    if len(history_list) > MAX_HISTORY_MESSAGES:
        del history_list[:-MAX_HISTORY_MESSAGES]
    return history_list


def triage_ticket(ticket_text, ticket_id, conversation_history):
    """Process a single ticket through the triage loop."""

    # Track retrieval outcome for confidence determination.
    retrieval_attempted = False
    retrieval_succeeded = False

    conversation_history.append({"role": "user", "content": ticket_text})

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=conversation_history,
    )

    while response.stop_reason == "tool_use":
        tool_block = next(b for b in response.content if b.type == "tool_use")

        tool_result = execute_tool(tool_block.name, tool_block.input)

        # Record whether the runbook search produced any usable results.
        if tool_block.name == "search_runbooks":
            retrieval_attempted = True
            retrieval_succeeded = _NO_RUNBOOK_SENTINEL not in tool_result

        conversation_history.append(
            {"role": "assistant", "content": response.content}
        )
        conversation_history.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": tool_result,
                    }
                ],
            }
        )

        _prune_history(conversation_history)

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=conversation_history,
        )

    raw_response = response.content[0].text
    conversation_history.append({"role": "assistant", "content": response.content})

    _prune_history(conversation_history)

    result = parse_triage_response(raw_response)
    result["ticket_id"] = ticket_id

    # Retrieval signal overrides: if the agent never searched, or the search
    # returned no results, the classification is ungrounded — flag for review
    # regardless of the model's self-reported confidence.
    if not retrieval_attempted or not retrieval_succeeded:
        result["needs_human_review"] = True

    return result
