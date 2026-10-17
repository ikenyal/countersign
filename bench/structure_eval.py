"""Score the structural check, alone and combined with the Decider gate.

    python bench/structure_eval.py dev test final final2     # tuning sets
    python bench/structure_eval.py final3                    # only after the freeze commit

Needs bench/extract-<set>.json (bench/extract.py) and, for the gate,
bench/raw-<set>-v19-grounds.json (bench/collect.py).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from countersign.gate import FLAG_THRESHOLDS, route  # noqa: E402
from countersign.structure import unconfirmed  # noqa: E402

HERE = Path(__file__).parent
QUALITY_FLAGS = {k: v for k, v in FLAG_THRESHOLDS.items() if k != "missing_info"}


def main(sets):
    rows_all = []
    for s in sets:
        cases = {c["id"]: c for c in json.loads((HERE / f"{s}.json").read_text())}
        ex = json.loads((HERE / f"extract-{s}.json").read_text())
        raw = {r["id"]: r for r in json.loads((HERE / f"raw-{s}-v19-grounds.json").read_text())}
        for cid, c in cases.items():
            why = unconfirmed(ex[cid]["affected"], ex[cid]["dependencies"], c["state"])
            r = raw[cid]
            lab, path, _ = route({"choice": r["choice"], "confidence": r["confidence"]}, r["flags"], 0.6, QUALITY_FLAGS)
            gate = r["llm"] if lab is None else lab
            final = "missing_info" if why else gate
            rows_all.append({"id": cid, "accept": c["accept"], "why": why, "gate": gate, "final": final,
                             "llm_call": lab is None and not why, "llm": r["llm"]})
    n = len(rows_all)
    routine = lambda r: "close" in r["accept"]
    for name, key in [("LLM only", "llm"), ("Decider gate (no missing-info flag)", "gate"), ("structure + gate", "final")]:
        unsafe = [r["id"] for r in rows_all if r[key] == "close" and not routine(r)]
        needless = [r["id"] for r in rows_all if r[key] != "close" and routine(r)]
        print(f"| {name} | unsafe {len(unsafe)} {unsafe} | needless {len(needless)} {needless} |")
    print(f"LLM calls (structure + gate): {sum(r['llm_call'] for r in rows_all)}/{n}")
    for r in rows_all:
        if routine(r) and r["why"]:
            print(f"  blocked routine {r['id']}: {r['why']}")


if __name__ == "__main__":
    main(sys.argv[1:])
