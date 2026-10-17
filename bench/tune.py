"""Judge a wording variant on the tuning sets only (dev + test + final). Never reads final2.

    python bench/tune.py v19-grounds v21-grounds
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from countersign.calibrate import percentile  # noqa: E402
from countersign.gate import route  # noqa: E402

HERE = Path(__file__).parent
TUNING = ["dev", "test", "final"]


def score(rows, th):
    calls, unsafe, needless = 0, [], []
    for r in rows:
        lab, _, _ = route({"choice": r["choice"], "confidence": r["confidence"]}, r["flags"], 0.6, th)
        if lab is None:
            lab, calls = r["llm"], calls + 1
        routine = "close" in r["accept"]
        if lab == "close" and not routine:
            unsafe.append(r["id"])
        if lab != "close" and routine:
            needless.append(r["id"])
    return calls, unsafe, needless


def thresholds(rows, q=0.9):
    routine = [r for r in rows if "close" in r["accept"]]
    return {k: round(percentile([r["flags"][k] for r in routine], q), 4) for k in rows[0]["flags"]}


if __name__ == "__main__":
    for tag in sys.argv[1:]:
        rows = sum((json.loads((HERE / f"raw-{s}-{tag}.json").read_text()) for s in TUNING), [])
        th = thresholds(rows)
        c, u, n = score(rows, th)
        c0, u0, n0 = score(rows, {})
        llm_u = [r["id"] for r in rows if r["llm"] == "close" and "close" not in r["accept"]]
        dec_close = sum(r["choice"] == "close" for r in rows if "close" in r["accept"])
        print(f"{tag}: n={len(rows)} routine={sum('close' in r['accept'] for r in rows)} "
              f"Decider says close on {dec_close} routine")
        print(f"  gate+flags: LLM {c} unsafe {len(u)} {u} needless {len(n)}")
        print(f"  gate only : LLM {c0} unsafe {len(u0)} {u0} needless {len(n0)}")
        print(f"  LLM only  : unsafe {len(llm_u)}  | thresholds {th}")
