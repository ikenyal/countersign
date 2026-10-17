"""Wording variants tried for the agreement decision. Only dev, test and final are used to compare them.

    python bench/collect.py bench/dev.json --model-tag v21-ga --variant grounds
"""
from countersign import gate

BASE = {"question": gate.QUESTION, "options": dict(gate.OPTIONS), "flags": dict(gate.FLAGS)}

# "stated": routine only if the description says so (2026-10-17 10:15). Over-corrected:
# v19 never chose close.
# "grounds": routine when the description gives grounds to believe the affected people
# are fine and nothing depends on it; hand back when it gives none.
GROUNDS = {
    "question": gate.QUESTION,
    "options": {**gate.OPTIONS,
        "close": "Routine. From what the description says, the people it affects are fine with it, nothing else depends on it, and nobody loses something they care about.",
        "missing_info": "The description gives no grounds to believe that the people it affects are fine with it or that nothing else depends on it; or another fact needed to decide is unknown."},
    "flags": {**gate.FLAGS,
        "missing_info": "Does the description give no grounds to believe that the people this affects are fine with it and that nothing else depends on it, or leave another needed fact unknown?"},
}

VARIANTS = {"current": BASE, "grounds": GROUNDS}
