"""What is not written down is not confirmed: a structural check, not a guess.

Decider 2B and the LLM both failed to tell, from prose, an agreement whose affected
people had confirmed it from one where nobody said so. So the agent must list who the
agreement affects and, for each, quote where that person or group agreed; and quote
where it says nothing else depends on it. Then:

  1. Code checks every quote actually appears in the conversation (no quote, no credit).
  2. Decider 2B answers one narrow yes/no per quote: does this sentence say they agreed?

Anything missing, unquoted, misquoted, or not confirmed by Decider hands the agreement
back to the humans.
"""
from __future__ import annotations

import json
import re
import urllib.request

AFFECTED_DOC = (
    "Everyone this agreement affects: each side's human by role, and anyone else it touches "
    "(attendees, readers, owners, customers, partners). Do not list the agents themselves. "
    "For each, 'evidence' is the exact sentence from the situation that says this person or "
    "group agreed or approved, copied word for word; empty if there is none."
)
DEPENDENCIES_DOC = (
    "The exact sentence from the situation that says nothing else depends on this, or that "
    "what depends on it was checked or updated, copied word for word; empty if there is none."
)

AGREED_Q = "Does this sentence say that {who} agreed to or approved the change?"
DEPENDS_Q = "Does this sentence say that nothing else depends on the change, or that whatever depends on it was checked or updated?"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().strip('"').strip("'").rstrip(".")).lower()


def quoted(evidence: str, source: str) -> bool:
    """True if the evidence is non-trivial and appears verbatim (modulo whitespace and case) in the source."""
    e = _norm(evidence or "")
    return len(e) >= 12 and e in _norm(source)


def decider_yes(question: str, sentence: str, url: str) -> float:
    body = json.dumps({"state": sentence, "questions": {"q": {"type": "noul", "instructions": question}}}).encode()
    req = urllib.request.Request(url, body, {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return float(json.load(r)["answers"]["q"]["noul"])


def unconfirmed(affected: list[dict], dependencies: str, source: str, *,
                url: str = "http://127.0.0.1:8010/v1/systemone", min_yes: float = 0.5,
                use_decider: bool = False) -> str | None:
    """Return why the agents may not close on their own, or None if every confirmation is shown."""
    # The agents' own say-so is not a confirmation, and placeholders are not people.
    affected = [a for a in affected
                if not re.match(r"\s*(agent\b|none\b|n/?a\b|nobody\b)", a.get("who", ""), re.I)]
    if not affected:
        return "nobody affected is listed"
    for a in affected:
        who, ev = a.get("who", "someone"), a.get("evidence", "")
        if not quoted(ev, source):
            return f"no quote shows that {who} agreed"
        if use_decider and decider_yes(AGREED_Q.format(who=who), ev, url) < min_yes:
            return f"the quote does not say that {who} agreed"
    if not quoted(dependencies, source):
        return "no quote shows that nothing else depends on it"
    if use_decider and decider_yes(DEPENDS_Q, dependencies, url) < min_yes:
        return "the quote does not say that nothing else depends on it"
    return None
