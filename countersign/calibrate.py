"""Measure the gate's flag thresholds for YOUR decision, then check them on cases you held back.

    python -m countersign.calibrate \
        --decision examples.auto_merge.decision --close merge \
        --cases examples/auto_merge/cases.json --out examples/auto_merge/thresholds.json

The decision module defines QUESTION, OPTIONS, FLAGS (and optionally REASONS).
Each case is {"id", "state", "accept": [acceptable options], "split": "calibrate" | "check"}.

Thresholds come only from the routine ("close") cases in the calibrate split:
each flag's threshold is that flag's q-th percentile there. The check split is
scored once, with the thresholds already fixed.
"""
import argparse
import importlib
import json
from pathlib import Path

from countersign.gate import ask_decider_all, bedrock_llm, route


def percentile(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision", required=True)
    ap.add_argument("--close", required=True, help="the option that lets the agent act alone")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--q", type=float, default=0.9)
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--url", default="http://127.0.0.1:8010/v1/systemone")
    a = ap.parse_args()

    d = importlib.import_module(a.decision)
    cases = json.loads(Path(a.cases).read_text())
    llm = bedrock_llm(question=d.QUESTION, options=d.OPTIONS, close_option=a.close)
    for c in cases:
        ans, flags = ask_decider_all(c["state"], a.url, d.QUESTION, d.OPTIONS, d.FLAGS)
        c.update(choice=ans["choice"], confidence=ans["confidence"], flags=flags, llm=llm(c["state"]))

    routine = [c for c in cases if c["split"] == "calibrate" and a.close in c["accept"]]
    th = {k: round(percentile([c["flags"][k] for c in routine], a.q), 4) for k in d.FLAGS}
    Path(a.out).write_text(json.dumps({"threshold": a.threshold, "flag_thresholds": th,
                                       "q": a.q, "from_routine_cases": len(routine)}, indent=1))
    print(f"flag thresholds from {len(routine)} routine calibrate cases: {th}\nwrote {a.out}\n")

    check = [c for c in cases if c["split"] == "check"]
    print("| case | expected | Decider | gate (flags) | LLM only |\n|---|---|---|---|---|")
    tally = {"gate": [0, 0, 0], "llm": [0, 0, 0]}  # [llm calls, unsafe, needless]
    for c in check:
        label, path, _ = route({"choice": c["choice"], "confidence": c["confidence"]}, c["flags"],
                               a.threshold, th, a.close)
        gate = c["llm"] if label is None else label
        routine_case = a.close in c["accept"]
        for name, pred, called in [("gate", gate, label is None), ("llm", c["llm"], True)]:
            tally[name][0] += called
            tally[name][1] += pred == a.close and not routine_case
            tally[name][2] += pred != a.close and routine_case
        mark = lambda p: ("✓" if p in c["accept"] else ("✗ UNSAFE" if p == a.close else "✗"))
        print(f"| {c['id']} | {'/'.join(c['accept'])} | {c['choice']} {c['confidence']:.2f} "
              f"| {gate} ({path}) {mark(gate)} | {c['llm']} {mark(c['llm'])} |")
    n = len(check)
    for name, (calls, unsafe, needless) in tally.items():
        print(f"\n{name}: LLM calls {calls}/{n}, unsafe {unsafe}, needless hand-backs {needless}", end="")
    print()


if __name__ == "__main__":
    main()
