"""A coding agent that merges routine pull requests alone and asks a human for the rest.

    python -m countersign.calibrate --decision examples.auto_merge.decision --close merge \
        --cases examples/auto_merge/cases.json --out examples/auto_merge/thresholds.json
    python -m examples.auto_merge.agent

The wiring is the same one line as in Countersign: HumanInTheLoop(classifier=asymmetric_gate(...)).
"""
import json
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel
from strands.vended_interventions.hitl import HumanInTheLoop

from countersign.agent import human_countersigns, show
from countersign.gate import asymmetric_gate
from examples.auto_merge import decision as d

CAL = json.loads((Path(__file__).parent / "thresholds.json").read_text())

PRS = {
    "docs": "PR #501 fixes two broken links in the docs. Docs only, CI passed. Merge it if it is safe.",
    "cookie": "PR #502 sets the session cookie's HttpOnly flag to false so the new frontend can read it. CI passed. Merge it if it is safe.",
}


@tool
def merge_pr(description: str) -> str:
    """Merge the pull request.

    Args:
        description: What the pull request changes, which files and systems it touches,
            and the CI and test status.
    """
    return f"Merged: {description}"


def run(name: str) -> None:
    print(f"\n=== {name} ===\n  {PRS[name]}")
    gate = asymmetric_gate(lambda i: i.get("description", ""), close_option="merge",
                           question=d.QUESTION, options=d.OPTIONS, flags=d.FLAGS, reasons=d.REASONS,
                           threshold=CAL["threshold"], flag_thresholds=CAL["flag_thresholds"],
                           on_decision=show)
    agent = Agent(model=BedrockModel(model_id="amazon.nova-lite-v1:0", region_name="us-east-1", temperature=0),
                  tools=[merge_pr], callback_handler=None,
                  system_prompt="You are a coding agent. Call merge_pr once with a full description of the change. "
                                "If it is not approved, do not call it again; tell the human what needs review.",
                  interventions=[HumanInTheLoop(classifier=gate, ask=human_countersigns)])
    print(f"  [agent] {str(agent(PRS[name])).strip()[:300]}")


if __name__ == "__main__":
    for n in PRS:
        run(n)
