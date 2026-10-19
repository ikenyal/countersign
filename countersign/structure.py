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
    "group agreed or approved, copied word for word; empty if there is none. A sentence "
    "about what depends on the change is not a person: put it in 'dependencies'."
)
DEPENDENCIES_DOC = (
    "The exact sentence from the situation that says nothing else depends on this, or that "
    "what depends on it was checked or updated, copied word for word (for example 'no team "
    "relies on Monday delivery' or 'nothing else consumes it'); empty if there is none."
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
        if not quoted(ev, source) or re.search(r"\bagent\b", ev, re.I):
            return f"no quote shows that {who} agreed"
        if use_decider and decider_yes(AGREED_Q.format(who=who), ev, url) < min_yes:
            return f"the quote does not say that {who} agreed"
    if not quoted(dependencies, source):
        return "no quote shows that nothing else depends on it"
    if use_decider and decider_yes(DEPENDS_Q, dependencies, url) < min_yes:
        return "the quote does not say that nothing else depends on it"
    return None


def on_record(ev: dict, sources: dict[str, str]) -> bool:
    """True if the evidence sentence is in the record it cites and is not the agents' own words."""
    text = sources.get((ev or {}).get("source", ""), "")
    q = (ev or {}).get("evidence", "")
    return quoted(q, text) and not re.search(r"\bagent\b", q, re.I)


def names_them(ev: dict, name: str, sources: dict[str, str]) -> bool:
    """True if the record cited as someone's agreement mentions that person or group by name.

    Found while recording the demo: the agent offered a calendar note ("Nothing else is
    scheduled around the weekly review") as Kai's agreement. The sentence was real and not
    the agents' own words, so it passed. A record that says Kai agreed has to name Kai.
    """
    text = sources.get((ev or {}).get("source", ""), "")
    return name.lower() in text.lower()


def unconfirmed_by_records(affected: list[dict], dependencies: dict, sources: dict[str, str],
                           required: list[str] | None = None) -> str | None:
    """Like unconfirmed(), but each quote cites the record it came from.

    affected:     [{"who", "evidence", "source"}], one per affected person or group.
    dependencies: {"evidence", "source"}.
    sources:      record id -> text (minutes, emails, the negotiation transcript).
    required:     the names of everyone affected, as given by the negotiation (not the agent).

    A quote counts only if it appears word for word in the record it cites, and only
    if it is not the agents' own words: the agents agreeing is not anyone else agreeing.
    With `required`, the record cited for each person must also name that person.
    """
    shown = lambda ev: on_record(ev, sources)

    affected = [a for a in affected
                if not re.match(r"\s*(agent\b|none\b|n/?a\b|nobody\b)", a.get("who", ""), re.I)]
    if not affected:
        return "nobody affected is listed"
    for a in affected:
        if not shown(a):
            return f"no record shows that {a.get('who', 'someone')} agreed"
    for name in required or []:
        entry = next((a for a in affected if name.lower() in a.get("who", "").lower()), None)
        if entry is None:
            return f"nobody listed as {name}"
        if not names_them(entry, name, sources):
            return f"the record cited for {name} does not mention {name}"
    if not shown(dependencies or {}):
        return "no record shows that nothing else depends on it"
    return None
