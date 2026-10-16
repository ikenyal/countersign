"""Score frozen gates with the same route() the agent runs.

    python bench/evaluate.py bench/raw-final-v19f.json

The gate in countersign/gate.py was frozen (thresholds included) in a commit made
before bench/final.json was scored for the first time.
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from countersign.gate import FLAG_THRESHOLDS, route  # noqa: E402

NO_FLAGS: dict[str, float] = {}


def predict(r, flag_thresholds):
    label, path, _ = route({"choice": r["choice"], "confidence": r["confidence"]},
                           r["flags"], 0.6, flag_thresholds)
    return (r["llm"], True) if label is None else (label, False)


def score(rows, f):
    out = [f(r) for r in rows]
    n = len(rows)
    preds = [p for p, _ in out]
    isc = lambda r: "close" in r["accept"]
    llm_rows = [r for r, (_, c) in zip(rows, out) if c]
    return {
        "llm_calls": len(llm_rows),
        "binary": sum((p == "close") == isc(r) for p, r in zip(preds, rows)) / n,
        "reason": sum(p in r["accept"] for p, r in zip(preds, rows)) / n,
        "unsafe": [r["id"] for p, r in zip(preds, rows) if p == "close" and not isc(r)],
        "needless": [r["id"] for p, r in zip(preds, rows) if p != "close" and isc(r)],
    }


def main():
    rows = json.loads(Path(sys.argv[1]).read_text())
    variants = {
        "LLM only (Nova Lite)": lambda r: (r["llm"], True),
        "Decider only": lambda r: (r["choice"], False),
        "Asymmetric gate v1 (no flags)": lambda r: predict(r, NO_FLAGS),
        "Asymmetric gate v2 (flags veto close)": lambda r: predict(r, FLAG_THRESHOLDS),
    }
    n = len(rows)
    print(f"{sys.argv[1]}: {n} cases, {sum('close' in r['accept'] for r in rows)} routine")
    print("| gate | LLM calls | close/hand-back | reason | unsafe close | needless hand-back |\n|---|---|---|---|---|---|")
    for name, f in variants.items():
        s = score(rows, f)
        print(f"| {name} | {s['llm_calls']}/{n} | {s['binary']:.0%} | {s['reason']:.0%} "
              f"| {len(s['unsafe'])} {s['unsafe']} | {len(s['needless'])} {s['needless']} |")
    print(f"median Decider ms (this machine): {statistics.median(r['decider_ms'] for r in rows):.0f}, "
          f"median LLM ms: {statistics.median(r['llm_ms'] for r in rows):.0f}")


if __name__ == "__main__":
    main()
