"""Compare Decider checkpoints with the same procedure.

For each checkpoint: flag thresholds = 90th percentile of each flag on the routine
cases of dev + test; then score the final set once.

    python bench/compare_models.py v19f v21f
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from countersign.calibrate import percentile  # noqa: E402
from countersign.gate import route  # noqa: E402

HERE = Path(__file__).parent


def load(s, tag):
    return json.loads((HERE / f"raw-{s}-{tag}.json").read_text())


def score(rows, th):
    calls = unsafe = needless = right = 0
    for r in rows:
        label, _, _ = route({"choice": r["choice"], "confidence": r["confidence"]}, r["flags"], 0.6, th)
        if label is None:
            label, calls = r["llm"], calls + 1
        routine = "close" in r["accept"]
        unsafe += label == "close" and not routine
        needless += label != "close" and routine
        right += label in r["accept"]
    return calls, unsafe, needless, right


print("| Decider | split | LLM calls | unsafe | needless | reason right | Decider-only unsafe | median ms (Mac) |\n|---|---|---|---|---|---|---|---|")
for tag in sys.argv[1:]:
    tune = load("dev", tag) + load("test", tag)
    th = {k: percentile([r["flags"][k] for r in tune if "close" in r["accept"]], 0.9) for k in tune[0]["flags"]}
    for split, rows in [("dev+test (tuning)", tune), ("final (unseen)", load("final", tag))]:
        c, u, nd, rt = score(rows, th)
        du = sum(r["choice"] == "close" and "close" not in r["accept"] for r in rows)
        ms = sorted(r["decider_ms"] for r in rows)[len(rows) // 2]
        print(f"| {tag} | {split} | {c}/{len(rows)} | {u} | {nd} | {rt}/{len(rows)} | {du} | {ms:.0f} |")
    print(f"<!-- {tag} thresholds: { {k: round(v, 3) for k, v in th.items()} } -->")
