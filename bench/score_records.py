"""Re-score the record check from the raw answers already in the repository.

    python bench/score_records.py

No GPU, no AWS, no model call: it reads bench/records.json (the labels, committed
in 47deee8 before scoring) and bench/raw-records-v19.json (Decider 2B's answers,
collected once with the untuned gate), and counts.
"""
import json
from pathlib import Path
from statistics import median_high  # n=24: the upper of the two middle values, as first reported

HERE = Path(__file__).parent

labels = {c["id"]: c["accept"] for c in json.loads((HERE / "records.json").read_text())}
raw = {r["id"]: r for r in json.loads((HERE / "raw-records-v19.json").read_text())}
assert labels.keys() == raw.keys(), "labels and raw answers cover different cases"

conflicts = [i for i in labels if labels[i] == "conflicts"]
others = [i for i in labels if labels[i] != "conflicts"]
caught = [i for i in conflicts if raw[i]["flagged"]]
missed = [i for i in conflicts if not raw[i]["flagged"]]
false_alarms = [i for i in others if raw[i]["flagged"]]

print(f"conflicts caught {len(caught)}/{len(conflicts)} (missed: {', '.join(missed) or 'none'})")
print(f"false alarms {len(false_alarms)}/{len(others)} ({', '.join(false_alarms) or 'none'})")
print(f"median {median_high(r['ms'] for r in raw.values())} ms per record (laptop CPU, as collected)")
