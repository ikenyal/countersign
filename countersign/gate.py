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
# by what the agreement touches, not by how it will feel.
QUESTION = ("Two agents negotiated this agreement on behalf of their humans. "
            "Can the agents close it themselves, or must it go back to the humans?")
OPTIONS = {
    "close": "Routine. Both sides' stated constraints are met and nobody loses something they care about.",
    "breaks_commitment": "It undoes something someone was already promised, approved for, told to expect, or currently relies on.",
    "money_contract_people": "It changes money, a budget, a contract, or headcount and hiring.",
    "bigger_conflict": "The two teams disagree about more than this one item; the disagreement is about priorities or ownership.",
    "missing_info": "A constraint or fact needed to decide is unknown or not stated.",
}
REASONS = {
    "breaks_commitment": "it undoes something someone was already promised",
    "money_contract_people": "it touches money, a contract, or headcount",
    "bigger_conflict": "the teams disagree about more than this one item",
    "missing_info": "a fact needed to decide is missing",
}


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


def bedrock_llm(model_id: str = "amazon.nova-lite-v1:0", region: str = "us-east-1",
                question: str = QUESTION, options: dict[str, str] = OPTIONS) -> Callable[[str], str]:
    """The LLM second opinion: same question, same options, one key back."""
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
        return key if key in options else "missing_info"  # unparseable → hand back
    return ask


def asymmetric_gate(
    state_of: Callable[[dict], str] = lambda tool_input: tool_input.get("summary", ""),
    *,
    threshold: float = 0.6,
    close_option: str = "close",
    decider: Callable[[str], dict] = ask_decider,
    llm: Callable[[str], str] | None = None,
    reasons: dict[str, str] = REASONS,
    on_decision: Callable[[GateDecision], None] | None = None,
):
    """Build a HumanInTheLoopClassifier that asks Decider 2B first.

    state_of:     turns the tool call's input into the state Decider reads.
    threshold:    the confidence a close needs before it is trusted without the LLM.
    llm:          the second opinion; defaults to Nova Lite on Bedrock.
    on_decision:  optional hook to log or display every pass through the gate.
    """
    second_opinion = llm or bedrock_llm()

    def classify(event, **kwargs) -> ClassifierResult:
        state = state_of(event.tool_use["input"])
        t0 = time.perf_counter()
        d = decider(state)
        choice, conf = d["choice"], float(d["confidence"])

        if choice != close_option or conf >= threshold:
            hand_back = choice != close_option
            dec = GateDecision("decider", choice, conf, hand_back, (time.perf_counter() - t0) * 1000)
            if on_decision:
                on_decision(dec)
            why = reasons.get(choice, "routine")
            return ClassifierResult(hand_back, f"Decider 2B: {why} (confidence {conf:.2f})")

        label = second_opinion(state)
        hand_back = label != close_option
        dec = GateDecision("decider->llm", label, conf, hand_back, (time.perf_counter() - t0) * 1000)
        if on_decision:
            on_decision(dec)
        why = reasons.get(label, "routine")
        return ClassifierResult(hand_back, f"LLM second opinion: {why} (Decider 2B was unsure: {conf:.2f})")

    return classify
