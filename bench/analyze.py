"""Score gate variants offline. Thresholds are picked on dev only, then frozen for test.

    python bench/analyze.py --tag v19
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent
LAT_LLM_MS = 348  # Nova Lite in us-east-1, median measured 2026-10-10


def is_close(r):
    return "close" in r["accept"]


def gate_conf(r, t):      # current gate: Decider's choice, close needs confidence >= t
    if r["choice"] != "close":
        return r["choice"], False
    return (r["choice"], False) if r["confidence"] >= t else (r["llm"], True)


def gate_prob(r, t):      # close needs P(close) >= t; anything else that Decider calls close goes to the LLM
    p = r["probabilities"]["close"]
    if p >= t:
        return "close", False
    if r["choice"] != "close":
        return r["choice"], False
    return r["llm"], True


def gate_3zone(r, t, lo=0.15):  # P(close) >= t: close; <= lo: hand back; between: ask the LLM
    p = r["probabilities"]["close"]
    if p >= t:
        return "close", False
    if p <= lo:
        reasons = {k: v for k, v in r["probabilities"].items() if k != "close"}
        return max(reasons, key=reasons.get), False
    return r["llm"], True


def score(rows, f):
    out = [f(r) for r in rows]
    n = len(rows)
    preds = [p for p, _ in out]
    calls = sum(c for _, c in out)
    return {
        "binary": sum((p == "close") == is_close(r) for p, r in zip(preds, rows)) / n,
        "reason": sum(p in r["accept"] for p, r in zip(preds, rows)) / n,
        "unsafe": sum(p == "close" and not is_close(r) for p, r in zip(preds, rows)),
        "needless": sum(p != "close" and is_close(r) for p, r in zip(preds, rows)),
        "llm_calls": calls,
        "avg_ms": sum(r["decider_ms"] for r in rows) / n + calls / n * LAT_LLM_MS,
    }


GRID = [round(0.40 + 0.05 * i, 2) for i in range(11)]  # 0.40 .. 0.90


def pick(dev, f):
    """Lowest threshold with the fewest unsafe closes on dev (fewest LLM calls among the safest)."""
    best = min(score(dev, lambda r: f(r, t))["unsafe"] for t in GRID)
    return next(t for t in GRID if score(dev, lambda r: f(r, t))["unsafe"] == best)


def line(name, s, n):
    return (f"| {name:30s} | {s['llm_calls']:2d}/{n} | {s['binary']:4.0%} | {s['reason']:4.0%} "
            f"| {s['unsafe']} | {s['needless']} | {s['avg_ms']:5.0f} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v19")
    a = ap.parse_args()
    dev = json.loads((HERE / f"raw-dev-{a.tag}.json").read_text())
    test = json.loads((HERE / f"raw-test-{a.tag}.json").read_text())

    variants = {
        "LLM only": lambda r: (r["llm"], True),
        "Decider only": lambda r: (r["choice"], False),
        "fixed: confidence >= 0.6": lambda r: gate_conf(r, 0.6),
    }
    for name, f in [("confidence", gate_conf), ("P(close)", gate_prob), ("3-zone P(close)", gate_3zone)]:
        t = pick(dev, f)
        variants[f"{name} >= {t} (dev-picked)"] = (lambda f, t: lambda r: f(r, t))(f, t)

    head = "| gate | LLM calls | close/hand-back | reason | unsafe close | needless hand-back | avg ms |\n|---|---|---|---|---|---|---|"
    for label, rows in [("dev (40, used to build the taxonomy and pick thresholds)", dev),
                        ("test (30, unseen)", test)]:
        print(f"\n### {label} — Decider {a.tag}\n{head}")
        for name, f in variants.items():
            print(line(name, score(rows, f), len(rows)))


if __name__ == "__main__":
    main()
