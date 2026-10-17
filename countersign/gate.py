"""Reusable Decider 2B decision pattern: an asymmetric gate for HumanInTheLoop.

Strands' HumanInTheLoop intervention asks a classifier, before a tool call,
whether a human must approve it. The stock classifier asks an LLM every time.
This one asks Strands Decider 2B first and trusts it asymmetrically:

  - Hand-back to the humans: trusted at ANY confidence.
    A wrong hand-back costs a human one glance.
  - Close without the humans: trusted only at or above `threshold`.
    A wrong close commits something behind the humans' backs.
  - Anything else (a low-confidence close): ask the LLM, exactly as the
    stock classifier would.

Pattern: #policy. Drop it into any agent with

    HumanInTheLoop(classifier=asymmetric_gate(...), ask=...)

The threshold is not a constant to copy. Measure it for your own decision
with bench/measure.py.
"""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

from strands.vended_interventions.hitl.classifier import ClassifierResult

# The typed question and option set (taxonomy v2).
# The hand-back reasons follow how the person who signs off actually decides:
# by what the agreement touches, not by how it will feel. And what is not written
# down counts as not confirmed: an agreement is routine only when the description
# says everyone affected agreed and nothing else depends on it.
QUESTION = ("Two agents negotiated this agreement on behalf of their humans. "
            "Can the agents close it themselves, or must it go back to the humans?")
OPTIONS = {
    "close": "Routine. From what the description says, the people it affects are fine with it, nothing else depends on it, and nobody loses something they care about.",
    "breaks_commitment": "It undoes something someone was already promised, approved for, told to expect, or currently relies on.",
    "money_contract_people": "It changes money, a budget, a contract, or headcount and hiring.",
    "bigger_conflict": "The two teams disagree about more than this one item; the disagreement is about priorities or ownership.",
    "missing_info": "The description gives no grounds to believe that the people it affects are fine with it or that nothing else depends on it; or another fact needed to decide is unknown.",
}
REASONS = {
    "breaks_commitment": "it undoes something someone was already promised",
    "money_contract_people": "it touches money, a contract, or headcount",
    "bigger_conflict": "the teams disagree about more than this one item",
    "missing_info": "it gives no grounds that the people it affects are fine and nothing depends on it",
}

# One yes/no question per hand-back reason. Asked together in one request.
# A single five-way choice let "close" win whenever no single reason stood out;
# separate questions let each reason speak for itself.
FLAGS = {
    "breaks_commitment": "Does closing this undo something someone was already promised, approved for, told to expect, or currently relies on?",
    "money_contract_people": "Does this change money, a budget, a price, payment terms, a contract, or who is hired, transferred, or paid?",
    "bigger_conflict": "Do the two teams disagree about more than this one item, such as who owns something or whose priorities win?",
    "missing_info": "Does the description give no grounds to believe that the people this affects are fine with it and that nothing else depends on it, or leave another needed fact unknown?",
}

# Where each flag vetoes a close. Measured, not chosen: the 90th percentile of each flag's
# P(true) on the 22 routine cases in bench/dev.json + test.json + final.json (Decider v19),
# after the approver's label review.
# Re-measure for your own decision with bench/analyze.py.
FLAG_THRESHOLDS = {"breaks_commitment": 0.4004, "money_contract_people": 0.3118, "bigger_conflict": 0.347, "missing_info": 0.7195}


@dataclass
class GateDecision:
    """One pass through the gate, kept for logs, demos and measurement."""
    path: str              # "decider" or "decider->llm"
    choice: str
    confidence: float      # Decider's confidence in its own choice
    hand_back: bool
    ms: float


def ask_decider(state: str, url: str = "http://127.0.0.1:8010/v1/systemone",
                question: str = QUESTION, options: dict[str, str] = OPTIONS) -> dict:
    """Ask Decider 2B one typed choice question. Returns {"choice", "confidence", ...}."""
    body = json.dumps({"state": state, "questions": {"gate": {
        "type": "choice", "instructions": question, "criteria": options}}}).encode()
    req = urllib.request.Request(url, body, {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["answers"]["gate"]


def ask_decider_all(state: str, url: str = "http://127.0.0.1:8010/v1/systemone",
                    question: str = QUESTION, options: dict[str, str] = OPTIONS,
                    flags: dict[str, str] = FLAGS) -> tuple[dict, dict[str, float]]:
    """One request: the choice question plus one yes/no flag per hand-back reason.

    Returns (choice answer, {reason: P(true)}).
    """
    qs = {"gate": {"type": "choice", "instructions": question, "criteria": options}}
    qs.update({f"flag_{k}": {"type": "noul", "instructions": v} for k, v in flags.items()})
    body = json.dumps({"state": state, "questions": qs}).encode()
    req = urllib.request.Request(url, body, {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        a = json.load(r)["answers"]
    return a["gate"], {k: float(a[f"flag_{k}"]["noul"]) for k in flags}


def bedrock_llm(model_id: str = "amazon.nova-lite-v1:0", region: str = "us-east-1",
                question: str = QUESTION, options: dict[str, str] = OPTIONS,
                close_option: str = "close") -> Callable[[str], str]:
    """The LLM second opinion: same question, same options, one key back.

    An answer that is not one of the option keys counts as a hand-back (fail closed).
    """
    fallback = next(k for k in options if k != close_option)
    import boto3
    client = boto3.client("bedrock-runtime", region_name=region)
    opts = "\n".join(f"- {k}: {v}" for k, v in options.items())

    def ask(state: str) -> str:
        prompt = (f"{question}\n\nSituation: {state}\n\nOptions:\n{opts}\n\n"
                  "Answer with exactly one option key and nothing else.")
        r = client.converse(modelId=model_id,
                            messages=[{"role": "user", "content": [{"text": prompt}]}],
                            inferenceConfig={"maxTokens": 12, "temperature": 0})
        text = r["output"]["message"]["content"][0]["text"].strip().strip("`.")
        key = text.split()[0] if text else ""
        return key if key in options else fallback
    return ask


def asymmetric_gate(
    state_of: Callable[[dict], str] = lambda tool_input: tool_input.get("summary", ""),
    *,
    threshold: float = 0.6,
    flag_thresholds: dict[str, float] | None = None,
    close_option: str = "close",
    question: str = QUESTION,
    options: dict[str, str] = OPTIONS,
    flags: dict[str, str] = FLAGS,
    decider_url: str = "http://127.0.0.1:8010/v1/systemone",
    decider: Callable[[str], tuple[dict, dict[str, float]]] | None = None,
    llm: Callable[[str], str] | None = None,
    reasons: dict[str, str] = REASONS,
    on_decision: Callable[[GateDecision], None] | None = None,
):
    """Build a HumanInTheLoopClassifier that asks Decider 2B first.

    state_of:        turns the tool call's input into the state Decider reads.
    threshold:       the confidence a close needs before it is trusted without the LLM.
    flag_thresholds: per-reason P(true) at which a flag vetoes a close; defaults to FLAG_THRESHOLDS.
    question, options, flags: your own decision. `close_option` names the option that lets
                     the agent act alone; every other option is a reason to hand back.
    llm:             the second opinion; defaults to Nova Lite on Bedrock with the same question.
    on_decision:     optional hook to log or display every pass through the gate.
    """
    decider = decider or (lambda s: ask_decider_all(s, decider_url, question, options, flags))
    second_opinion = llm or bedrock_llm(question=question, options=options, close_option=close_option)
    th = FLAG_THRESHOLDS if flag_thresholds is None else flag_thresholds

    def classify(event, **kwargs) -> ClassifierResult:
        state = state_of(event.tool_use["input"])
        t0 = time.perf_counter()
        answer, raised = decider(state)
        label, path, conf = route(answer, raised, threshold, th, close_option)
        if label is None:
            label = second_opinion(state)
        hand_back = label != close_option
        if on_decision:
            on_decision(GateDecision(path, label, conf, hand_back, (time.perf_counter() - t0) * 1000))
        why = reasons.get(label, "routine")
        if path == "decider->llm":
            return ClassifierResult(hand_back, f"LLM second opinion: {why} (Decider 2B was unsure: {conf:.2f})")
        if path == "flag":
            return ClassifierResult(True, f"Decider 2B flag: {why} (P={raised[label]:.2f})")
        return ClassifierResult(hand_back, f"Decider 2B: {why} (confidence {conf:.2f})")

    return classify


def route(answer: dict, flags: dict[str, float], threshold: float,
          flag_thresholds: dict[str, float], close_option: str = "close"):
    """The whole decision, without I/O. Returns (label or None for "ask the LLM", path, confidence).

    1. Decider chose a hand-back reason        -> hand back, at any confidence.
    2. A flag is at or above its threshold     -> hand back for that flag's reason.
       Flags can only stop a close; they never close anything.
    3. Decider chose close with confidence >= threshold -> close.
    4. Otherwise                               -> ask the LLM.
    """
    choice, conf = answer["choice"], float(answer["confidence"])
    if choice != close_option:
        return choice, "decider", conf
    over = {k: p - flag_thresholds[k] for k, p in flags.items() if k in flag_thresholds and p >= flag_thresholds[k]}
    if over:
        return max(over, key=over.get), "flag", conf
    if conf >= threshold:
        return close_option, "decider", conf
    return None, "decider->llm", conf


# --- Record check: one small Decider decision per record the agent read ---------------
# One long input full of approvals drowned out a single promise. Asked one record at a
# time, Decider separated them cleanly. A record that conflicts hands back at any
# confidence, like every other hand-back reason.
RECORD_QUESTION = "How does this record relate to the proposed change?"
RECORD_OPTIONS = {
    "agrees": "Someone in this record agrees to or approves the proposed change.",
    "neutral": "The record is unrelated or only gives background.",
    "conflicts": "The record holds a promise or plan that the proposed change would break.",
}


def conflicting_records(change: str, records: dict[str, str],
                        url: str = "http://127.0.0.1:8010/v1/systemone") -> dict[str, float]:
    """Return {record id: confidence} for every record Decider says the change would conflict with."""
    found = {}
    for rid, text in records.items():
        body = json.dumps({"state": f"Proposed change: {change}\nRecord: {text}",
                           "questions": {"r": {"type": "choice", "instructions": RECORD_QUESTION,
                                               "criteria": RECORD_OPTIONS}}}).encode()
        req = urllib.request.Request(url, body, {"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            a = json.load(r)["answers"]["r"]
        if a["choice"] == "conflicts":
            found[rid] = float(a["confidence"])
    return found
