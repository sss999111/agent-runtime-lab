# Real-model run evidence (20 CSVs, 71 rows)

| Strategy | Runs | Pass | Avg Steps | Real Samples | Avg Tokens | P50 (s) | P95 (s) |
|---|---|---|---|---|---|---|---|
| full | 29 | 16/29 | 3.6 | 29 | 5510 | 10.0 | 19.0 |
| state_card | 8 | 8/8 | 5.6 | 8 | 11547 | 11.9 | 18.5 |
| summary | 2 | 2/2 | 6.5 | 2 | 13958 | 167.1 | 192.6 |
| window | 2 | 2/2 | 6.5 | 2 | 12753 | 14.9 | 18.0 |
| unknown | 30 | 28/30 | 4.3 | 30 | 3505 | 7.7 | 13.5 |

Notes:
- CSVs contain `prompt_tokens > 0` = real Volcano Ark doubao-seed-2-1-lite runs.
- `unknown` strategy = **warm-up runs** (all 19 tasks run ~1.6x each, 30 rows total, ran before the strategy parameter was standardized). Treat as smoke tests: low token count (avg 3505) and fast latency reflect early short-conversation runs. Pass rate 28/30 is comparable to `full` baseline.
- `stats.py` aggregates `logs/bench_*.csv`; Mock runs (`prompt_tokens = 0`) excluded from token/latency.
- Benchmarks from 2026-11-15; real quota hit `SetLimitExceeded` after 29 `full`-strategy samples, so `state_card` / `window` / `summary` have smaller samples — known gap.
- Log column paths in CSVs are relative: `logs/<timestamp>_task_xxx.jsonl` (the actual jsonl traces are gitignored per-run artifacts).
