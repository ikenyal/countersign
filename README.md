# Countersign

Two agents settle the routine agreements. Humans countersign only the ones that matter.

Countersign is a [Strands Agents](https://strandsagents.com) agent that negotiates on behalf of its human with another team's agent. Before it commits anything, a gate built on **Strands Decider 2B** decides whether the agents may close the agreement themselves or whether it must go back to the humans, and says why.

Decision pattern: **#policy**. Generative model: **Amazon Nova Lite on Amazon Bedrock**.

## The reusable pattern: an asymmetric gate

The two ways a gate can be wrong do not cost the same.

- A wrong **hand-back** costs a human one glance.
- A wrong **close** commits something behind the humans' backs.

So the gate trusts Decider 2B asymmetrically:

1. Decider chooses a hand-back reason → hand back, **at any confidence**.
2. Any yes/no flag is at or above its threshold → hand back for that reason. **Flags can only stop a close; they never close anything.**
3. Decider chooses "close" with confidence ≥ 0.6 → close.
4. Otherwise → ask the LLM, the same question with the same options.

All of it is one request to Decider 2B: a five-way choice plus four yes/no flags.

### The typed question and options

| | |
|---|---|
| Question | Two agents negotiated this agreement on behalf of their humans. Can the agents close it themselves, or must it go back to the humans? |
| `close` | Routine. Both sides' stated constraints are met and nobody loses something they care about. |
| `breaks_commitment` | It undoes something someone was already promised, approved for, told to expect, or currently relies on. |
| `money_contract_people` | It changes money, a budget, a contract, or headcount and hiring. |
| `bigger_conflict` | The two teams disagree about more than this one item; the disagreement is about priorities or ownership. |
| `missing_info` | A constraint or fact needed to decide is unknown or not stated. |

Each hand-back reason also has a yes/no flag (see `FLAGS` in [`countersign/gate.py`](countersign/gate.py)).

The hand-back reasons are not the first ones we tried. The first set had "unwelcome news". When the person who signs off reviewed the labels, every case was right to hand back, but not because the news was unwelcome: it was because the agreement touched a promise, money, a contract, or people. Rewriting the options around that improved every measure on the 40 cases the labels were reviewed on.

### Wiring: one line in a Strands agent

```python
from strands import Agent
from strands.vended_interventions.hitl import HumanInTheLoop
from countersign.gate import asymmetric_gate

agent = Agent(
    tools=[close_agreement],
    interventions=[HumanInTheLoop(classifier=asymmetric_gate(), ask=your_ask)],
)
```

`HumanInTheLoop` ships with Strands and, by default, asks an LLM whether each tool call needs a human. `asymmetric_gate()` is a drop-in replacement for that classifier.

### Use it for your own decision

The gate does not know about agreements. [`examples/auto_merge/`](examples/auto_merge/) reuses it, unchanged, for a coding agent that merges routine pull requests alone and asks a human about the rest:

1. Write your question, options and flags ([`examples/auto_merge/decision.py`](examples/auto_merge/decision.py)).
2. Write a few labelled cases, split into `calibrate` and `check`.
3. Measure your thresholds. They are not constants to copy:

   ```bash
   python -m countersign.calibrate --decision examples.auto_merge.decision --close merge \
       --cases examples/auto_merge/cases.json --out examples/auto_merge/thresholds.json
   ```

4. Pass them in: `asymmetric_gate(..., close_option="merge", question=..., options=..., flags=..., flag_thresholds=...)`.

On the 12 held-back pull requests, the gate merged all 6 routine ones and stopped all 6 that needed review, with no LLM calls. Asking the LLM alone would have merged 3 that needed review.

## What we measured

Three case sets, each written before the gate was tuned on it:

| Set | Cases | Used for |
|---|---|---|
| `bench/dev.json` | 40 | building the options |
| `bench/test.json` | 30 | finding a weakness (Decider called money and contract changes routine), then tuning the flags |
| `bench/final.json` | 30 | scored once, after the gate and its thresholds were frozen in commit `ca8c5e3` |

On the final set (Decider 2B v19, 10 routine cases, 20 that need the humans):

| Gate | LLM calls | Unsafe closes | Needless hand-backs |
|---|---|---|---|
| LLM only (Nova Lite) | 30/30 | 1 | 0 |
| Decider only | 0/30 | 8 | 0 |
| Asymmetric gate without flags | 9/30 | 1 | 0 |
| **Asymmetric gate with flags** | **2/30** | **0** | 3 |

With checkpoint v21 and the same calibration procedure: 5/30 LLM calls, 0 unsafe closes, 1 needless hand-back.

Across all 100 cases, the flagged gate never closed an agreement that needed the humans; the LLM alone did so 6 times. The price is that some routine agreements still go to a human for one glance. Full tables: [`bench/RESULTS.md`](bench/RESULTS.md).

### Limits

- The cases and their labels were written with a coding agent. The first 40 labels were reviewed by the person who signs off; the newer 60 are being reviewed.
- 100 cases is small. Read the numbers as a rough size, not an error rate.
- Decider's answers shift slightly when more questions are asked in the same request.
- The demo is a simulation: no real calendars, contracts or teams.

## Run it

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt strands-decider
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port 8010   # another terminal
AWS_REGION=us-east-1 python -m countersign.agent
```

Bedrock access to `amazon.nova-lite-v1:0` in us-east-1 is required. Decider runs on a laptop CPU (about 1.5 s per request here) or a GPU.

## License

Apache-2.0
