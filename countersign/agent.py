"""Countersign demo: two agents settle an agreement; humans sign only when it matters.

Our agent negotiates for its human. When it wants to commit the agreement, it
calls close_agreement. Before that call runs, the asymmetric gate asks
Decider 2B whether the agents may close it or the humans must countersign.

    python -m countersign.agent            # all demo scenarios
    python -m countersign.agent routine    # one of them
"""
from __future__ import annotations

import sys

from strands import Agent, tool
from strands.models import BedrockModel
from strands.vended_interventions.hitl import HumanInTheLoop

from countersign.gate import GateDecision, asymmetric_gate

MODEL_ID = "amazon.nova-lite-v1:0"
REGION = "us-east-1"

SYSTEM = ("You are an agent negotiating on behalf of a human with another team's agent. "
          "When you and the other side have settled on something, call close_agreement once, "
          "with a summary that states the agreement and every consequence of it: who gains, "
          "who loses, what was already promised or approved, and who has not been told yet. "
          "Do not leave consequences out. If close_agreement is not approved, do not call it "
          "again: stop and tell your human, in one or two sentences, what needs their attention.")

SCENARIOS = {
    "routine": "Our side (design) and their side (QA) agreed to move the weekly review from Tue 10:00 to Tue 14:00. Both calendars are free and both humans marked it movable. Close it.",
    "commitment": "Our side (platform) and their side (finance) agreed to move the database migration from Oct 20 to Oct 27, after finance's quarter-end. Platform loses the week of buffer its lead promised the on-call team, who have not been told. Close it.",
    "money": "Our side (support) and their side (sales) agreed that support will cover the new enterprise customer's weekend tickets starting next month, which needs one more contractor on the support budget. Close it.",
}


@tool
def close_agreement(summary: str) -> str:
    """Commit the agreement on behalf of both humans.

    Args:
        summary: The full agreement and every consequence of it, including who
            gains, who loses, what was already promised, and who has not been told yet.
    """
    return f"Agreement committed: {summary}"


def show(d: GateDecision) -> None:
    verdict = "HAND BACK to the humans" if d.hand_back else "agents may CLOSE"
    print(f"  [gate] {d.path:13s} choice={d.choice:22s} confidence={d.confidence:.2f} "
          f"{d.ms:6.0f} ms -> {verdict}")


def human_countersigns(prompt: str, **kwargs) -> str:
    print(f"  [human] asked to countersign: {prompt}")
    print("  [human] (demo: the human holds it for a conversation)")
    return "n"


def run(name: str) -> None:
    print(f"\n=== {name} ===\n  {SCENARIOS[name]}")
    agent = Agent(
        model=BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0),
        tools=[close_agreement],
        system_prompt=SYSTEM,
        interventions=[HumanInTheLoop(classifier=asymmetric_gate(on_decision=show),
                                      ask=human_countersigns)],
        callback_handler=None,
    )
    result = agent(SCENARIOS[name])
    print(f"  [agent] {str(result).strip()[:400]}")


if __name__ == "__main__":
    for name in sys.argv[1:] or SCENARIOS:
        run(name)
