# Countersign

Two agents settle the routine agreements. Humans countersign only the ones that matter.

Countersign is a [Strands Agents](https://strandsagents.com) agent that negotiates for its human with another team's agent. Before it commits anything, it has to show, from the company's own records, that everyone the agreement affects has agreed. Then a gate built on **Strands Decider 2B** decides whether the agents may close it themselves, or whether it goes back to the humans with everything prepared up to the decision.

Decision pattern: **#policy**. Generative models: **Amazon Nova Pro** (the agent) and **Amazon Nova Lite** (second opinion), on Amazon Bedrock.

## What the person who signs off taught us

The rules in this gate were not designed up front. They came from the person who countersigns, reviewing 178 labelled cases:

1. **Judge by what an agreement touches, not by how it feels.** A first draft had "unwelcome news" as a reason to hand back. Every case was right to hand back, but because it broke a promise, or touched money, a contract, or people.
2. **If it is not written down, treat it as not confirmed.** "It should be fine for everyone" and "the other manager is expected to agree" are not agreement. In his words: *don't act on a guess.*
3. **Handing back is not doing nothing.** Prepare everything up to the point where only a human can decide, then hand it over.

Neither Decider 2B nor the LLM could learn rule 2 from prose: both treated an agreement whose confirmations were missing like one where they were present. So rule 2 is enforced by structure and code, not by a model. Decider does what it is good at: many small, fast judgments.

## How the gate works

When the agent calls `close_agreement`, the gate runs four checks and reports every reason it finds:

| Step | Who decides | What |
|---|---|---|
| 1. Everyone affected is listed | code | The list of affected people comes from the negotiation, not from the agent that wants to close. Anyone left out → hand back. |
| 2. Every agreement is on record | code | For each person, the agent must quote the sentence where they agreed and cite the record (minutes, email, calendar note). The quote must appear word for word in that record, and must not be the agents' own words. Same for "nothing else depends on it." |
| 3. No record contradicts it | Decider 2B, once per record | Every record the agent read is checked on its own: *agrees / neutral / conflicts*. A promise the change would break → hand back, at any confidence. |
| 4. Promise, money, conflict | Decider 2B | One request: a five-way choice plus yes/no flags. A hand-back reason is trusted at any confidence; "close" only at confidence ≥ 0.6. When Decider is unsure about a close, ask the LLM. |

If the gate hands back, the agent must call `prepare_for_humans`: what is ready, the one decision only a human can make, and a draft of who to ask.

## The reusable pieces

- **`asymmetric_gate()`** ([`countersign/gate.py`](countersign/gate.py)): a drop-in classifier for Strands' `HumanInTheLoop`. Hand-backs are trusted at any confidence; closes need confidence. Thresholds are measured, not guessed.
- **`conflicting_records()`** ([`countersign/gate.py`](countersign/gate.py)): one small Decider choice per document. Use it whenever an agent acts on a pile of documents and one of them might say "we promised otherwise."
- **`unconfirmed_by_records()`** ([`countersign/structure.py`](countersign/structure.py)): no quote, no credit.
- **`python -m countersign.calibrate`** ([`countersign/calibrate.py`](countersign/calibrate.py)): measure the thresholds for your own decision on cases you label, then check them on cases you held back.

```python
from strands import Agent
from strands.vended_interventions.hitl import HumanInTheLoop
from countersign.gate import asymmetric_gate

agent = Agent(tools=[...], interventions=[HumanInTheLoop(classifier=asymmetric_gate(), ask=your_ask)])
```

[`examples/auto_merge/`](examples/auto_merge/) reuses the gate, unchanged, for a different decision: may a coding agent merge this pull request alone?

## What we measured

Every number below comes from a case set that was committed **before** the gate it scores was frozen, and was scored once. Earlier sets were used to build and tune; each time a design changed, the next number came from a new set. Full tables and the commits: [`bench/RESULTS.md`](bench/RESULTS.md).

**The whole gate, on 30 unseen agreements** (`bench/final3.json`; gate frozen in commit `797a0c4`; 10 routine, 20 that need the humans, labels reviewed by the person who signs off):

| | Unsafe closes | Needless hand-backs | LLM calls |
|---|---|---|---|
| LLM only (Nova Lite) | 10 | 0 | 30/30 |
| Decider 2B judgment only (no evidence check) | 2 | 2 | 4/30 |
| **Countersign gate** | **1** | 3 | **4/30** |

Eight of those 20 were agreements where someone's confirmation was simply missing ("should be fine for everyone", "expected to agree"). The LLM closed all eight. The gate closed one: the agent quoted the agents' own agreement as the team's, and the version measured here did not yet reject that (it does now; that fix is not in these numbers).

**The record check, on 24 unseen record/change pairs** (`bench/records.json`, untuned, labels reviewed by the person who signs off): it caught 7 of 8 records holding a promise the change would break, with no false alarms on 16 records that agreed or were unrelated. The one it missed needed the inference "Wednesday is a weekday."

**The reused gate, on 12 unseen pull requests** (`examples/auto_merge/cases_check2.json`): one unsafe merge (a refactor "meant to change nothing", which the LLM also merged), two needless hand-backs, 2 LLM calls; the LLM alone: one unsafe merge, no needless hand-backs, 12 calls.

**Speed** (NVIDIA L4, g6.xlarge, after warm-up): the four-question judgment takes a median of 150 ms; one record check takes 74 ms. A Nova Lite call from a laptop took a median of 472 ms.

**Cost.** g6.xlarge is $0.8048 an hour on demand in us-east-1. Kept busy, that is about $0.03 per 1,000 judgments and $0.02 per 1,000 record checks. An idle GPU costs the same per hour, so at low volume a hosted LLM call is cheaper. Decider's case here is speed, many small decisions per agreement, and keeping internal records on your own instance.

## Limits

- The cases are written in English by a coding agent and describe fictional teams. The labels of 178 cases were reviewed by the person who signs off; `bench/final2.json` was not.
- The gate checks that each affected person agreed, not that they had the authority to. Reviewing the record check, the person who signs off flagged an employee's own "my manager agreed" as not enough: a transfer needs the manager or HR on record. Who may approve what is the next thing to encode.
- 30 cases per set is small. Read the numbers as a rough size, not an error rate.
- The structure check depends on the agent filling it in honestly; it fails closed (a missing or altered quote hands back), not open. Nova Lite was not accurate enough to fill it in, so the agent uses Nova Pro.
- The demo's records are simulated. In a real deployment they would come from your wiki, mail and calendar.
- In the demo, the "pushed" scenario uses Nova Lite as a deliberately less careful agent. Nova Pro refused to close even when pushed; the gate must not depend on that.

## Run it

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt strands-decider
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port 8010   # in another terminal
AWS_REGION=us-east-1 python -m countersign.agent            # routine, unconfirmed, commitment, pushed
```

You need Bedrock access to Nova Pro and Nova Lite in us-east-1. Decider runs on a laptop CPU (about 1.5 s per judgment) or a GPU.

## License

Apache-2.0
