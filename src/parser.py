"""Response parsing for structured triage output.

CONFIDENCE MECHANISM (Part 2)
==============================
Two signals are combined to set needs_human_review:

1. Model-reported CONFIDENCE (parsed here):
   If the model reports "low", the ticket is flagged regardless of structural
   completeness. This catches cases where retrieval succeeded but the model
   itself is uncertain about the correct classification.

2. Structural completeness (detected here):
   If any required field (CATEGORY, PRIORITY, ASSIGNED_TEAM, SUMMARY) fell
   back to its default value, the response was structurally incomplete. An
   incomplete response is a reliable proxy for an uncertain or confused
   classification — if the model cannot fill required fields, the output
   cannot be trusted.

Why structural completeness is a trustworthy signal:
- It is purely mechanical — no LLM judgment involved.
- A field going to default means the regex found no match, which means the
  model deviated from the required format, which typically indicates the model
  was uncertain or produced an unexpected response.

The retrieval signal (whether search_runbooks returned results) is evaluated
in agent.py and can override needs_human_review to True independently.

Trade-offs:
- We do not use confidence thresholds (e.g., "medium" triggers review) to keep
  false-positive review rates manageable; only "low" is treated as a trigger.
  Operators can lower this threshold by also flagging "medium" if needed.
"""

import re

DEFAULT_VALUES = {
    "category": "other",
    "priority": "medium",
    "assigned_team": "L1",
    "summary": "Unable to parse model response",
    "confidence": "low",
}

# Fields whose default value indicates a parse failure (CONFIDENCE default
# just means the model did not report a level — handled separately).
_REQUIRED_FIELDS = ["CATEGORY", "PRIORITY", "ASSIGNED_TEAM", "SUMMARY"]


def parse_triage_response(raw_text):
    """Parse the model's structured response into a dict.

    Extracts FIELD: value pairs from the model's text output.
    Falls back to defaults for any missing field.
    Sets needs_human_review based on reported confidence and structural
    completeness.
    """
    result = {}
    used_default_on_required = False

    for field in _REQUIRED_FIELDS + ["CONFIDENCE"]:
        match = re.search(rf"{field}:\s*(.+)", raw_text)
        if match:
            result[field.lower()] = match.group(1).strip()
        else:
            result[field.lower()] = DEFAULT_VALUES[field.lower()]
            if field in _REQUIRED_FIELDS:
                used_default_on_required = True

    confidence = result.get("confidence", "low").lower()
    result["needs_human_review"] = (
        confidence == "low" or used_default_on_required
    )

    return result
