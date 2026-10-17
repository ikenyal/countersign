"""Let the agent's model fill in the structure for each case, as it would when closing.

    python bench/extract.py bench/dev.json

Writes bench/extract-<set>.json: {id: {"affected": [{"who", "evidence"}], "dependencies": quote}}.
"""
import json
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from countersign.structure import AFFECTED_DOC, DEPENDENCIES_DOC  # noqa: E402

TOOL = {"toolSpec": {
    "name": "close_agreement",
    "description": "Commit the agreement on behalf of both humans.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "The agreement and every consequence of it."},
            "affected": {"type": "array", "description": AFFECTED_DOC, "items": {
                "type": "object",
                "properties": {"who": {"type": "string"}, "evidence": {"type": "string"}},
                "required": ["who", "evidence"]}},
            "dependencies": {"type": "string", "description": DEPENDENCIES_DOC},
        },
        "required": ["summary", "affected", "dependencies"]}}}}


def fill(client, state: str, model_id: str = "amazon.nova-lite-v1:0") -> dict:
    r = client.converse(
        modelId=model_id,
        system=[{"text": "You negotiate for your human. Close the agreement described, filling in every field "
                         "strictly from what the situation says."}],
        messages=[{"role": "user", "content": [{"text": f"Situation: {state}\n\nClose it."}]}],
        toolConfig={"tools": [TOOL], "toolChoice": {"any": {}}},
        inferenceConfig={"temperature": 0, "maxTokens": 600})
    for block in r["output"]["message"]["content"]:
        if "toolUse" in block:
            i = block["toolUse"]["input"]
            return {"affected": i.get("affected", []), "dependencies": i.get("dependencies", "")}
    return {"affected": [], "dependencies": ""}  # no tool call: fail closed


if __name__ == "__main__":
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    path = Path(sys.argv[1])
    model = sys.argv[2] if len(sys.argv) > 2 else "amazon.nova-lite-v1:0"
    out = {c["id"]: fill(client, c["state"], model) for c in json.loads(path.read_text())}
    suffix = "" if model == "amazon.nova-lite-v1:0" else "-" + model.rsplit(".", 1)[-1].split(":")[0]
    dest = path.with_name(f"extract-{path.stem}{suffix}.json")
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {dest} ({len(out)})")
