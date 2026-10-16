# Results (Decider v19, Mac CPU; gate frozen at ca8c5e3 before final was scored)

bench/raw-dev-v19f.json: 40 cases, 10 routine
| gate | LLM calls | close/hand-back | reason | unsafe close | needless hand-back |
|---|---|---|---|---|---|
| LLM only (Nova Lite) | 40/40 | 95% | 90% | 2 ['b03', 'hb02'] | 0 [] |
| Decider only | 0/40 | 78% | 75% | 8 ['u03', 'b01', 'b02', 'b03', 'm04', 'hu01', 'hu04', 'hu05'] | 1 ['hc02'] |
| Asymmetric gate v1 (no flags) | 9/40 | 95% | 88% | 1 ['b03'] | 1 ['hc02'] |
| Asymmetric gate v2 (flags veto close) | 4/40 | 95% | 90% | 0 [] | 2 ['hc01', 'hc02'] |
median Decider ms (this machine): 1507, median LLM ms: 463

bench/raw-test-v19f.json: 30 cases, 10 routine
| gate | LLM calls | close/hand-back | reason | unsafe close | needless hand-back |
|---|---|---|---|---|---|
| LLM only (Nova Lite) | 30/30 | 90% | 87% | 3 ['t14', 't22', 't24'] | 0 [] |
| Decider only | 0/30 | 73% | 70% | 8 ['t14', 't15', 't18', 't19', 't20', 't21', 't22', 't25'] | 0 [] |
| Asymmetric gate v1 (no flags) | 9/30 | 93% | 90% | 2 ['t14', 't22'] | 0 [] |
| Asymmetric gate v2 (flags veto close) | 1/30 | 87% | 80% | 0 [] | 4 ['t04', 't06', 't08', 't09'] |
median Decider ms (this machine): 1524, median LLM ms: 459

bench/raw-final-v19f.json: 30 cases, 10 routine
| gate | LLM calls | close/hand-back | reason | unsafe close | needless hand-back |
|---|---|---|---|---|---|
| LLM only (Nova Lite) | 30/30 | 97% | 97% | 1 ['v25'] | 0 [] |
| Decider only | 0/30 | 73% | 70% | 8 ['v16', 'v17', 'v19', 'v20', 'v22', 'v23', 'v24', 'v25'] | 0 [] |
| Asymmetric gate v1 (no flags) | 9/30 | 97% | 93% | 1 ['v25'] | 0 [] |
| Asymmetric gate v2 (flags veto close) | 2/30 | 90% | 87% | 0 [] | 3 ['v02', 'v04', 'v09'] |
median Decider ms (this machine): 1604, median LLM ms: 472

## Checkpoint comparison (same procedure)
| Decider | split | LLM calls | unsafe | needless | reason right | Decider-only unsafe | median ms (Mac) |
|---|---|---|---|---|---|---|---|
| v19f | dev+test (tuning) | 5/70 | 0 | 6 | 60/70 | 16 | 1516 |
| v19f | final (unseen) | 2/30 | 0 | 3 | 26/30 | 8 | 1615 |
<!-- v19f thresholds: {'breaks_commitment': 0.373, 'money_contract_people': 0.309, 'bigger_conflict': 0.346, 'missing_info': 0.635} -->
| v21f | dev+test (tuning) | 3/70 | 0 | 7 | 60/70 | 5 | 1638 |
| v21f | final (unseen) | 5/30 | 0 | 1 | 27/30 | 4 | 2676 |
<!-- v21f thresholds: {'breaks_commitment': 0.309, 'money_contract_people': 0.199, 'bigger_conflict': 0.294, 'missing_info': 0.619} -->
