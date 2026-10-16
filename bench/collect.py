"""Collect raw answers once, so every gate variant can be scored offline.

    python bench/collect.py bench/dev.json  --model-tag v19
    python bench/collect.py bench/test.json --model-tag v19

For each case it stores Decider 2B's choice, per-option probabilities,
confidence and latency, plus the LLM's one-word answer. Nothing is tuned here.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from countersign.gate import ask_decider_all, bedrock_llm  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("--model-tag", required=True, help="label for the Decider checkpoint being served")
    ap.add_argument("--url", default="http://127.0.0.1:8010/v1/systemone")
    a = ap.parse_args()

    cases = json.loads(Path(a.cases).read_text())
    llm = bedrock_llm()
    rows = []
    for c in cases:
        t0 = time.perf_counter(); d, flags = ask_decider_all(c["state"], url=a.url); dm = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter(); l = llm(c["state"]); lm = (time.perf_counter() - t1) * 1000
        rows.append({"id": c["id"], "accept": c["accept"], "choice": d["choice"],
                     "confidence": d["confidence"], "probabilities": d.get("probabilities", {}), "flags": flags,
                     "decider_ms": round(dm, 1), "llm": l, "llm_ms": round(lm, 1)})
        ok = lambda x: "✓" if x in c["accept"] else "✗"
        print(f'{c["id"]:5s} decider={d["choice"]:22s}{ok(d["choice"])} conf={d["confidence"]:.2f} '
              f'flags={' '.join(f'{v:.2f}' for v in flags.values())}  llm={l:22s}{ok(l)}', file=sys.stderr)
    out = Path(a.cases).with_name(f"raw-{Path(a.cases).stem}-{a.model_tag}.json")
    out.write_text(json.dumps(rows, indent=1))
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
