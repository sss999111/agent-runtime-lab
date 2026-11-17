# Real-model run evidence (20 CSVs, 71 rows)

| Strategy | Runs | Pass | Avg Steps | Real Samples | Avg Tokens | P50 (s) | P95 (s) |
|---|---|---|---|---|---|---|---|
| full | 29 | 16/29 | 3.6 | 29 | 5510 | 10.0 | 19.0 |
| state_card | 8 | 8/8 | 5.6 | 8 | 11547 | 11.9 | 18.5 |
| summary | 2 | 2/2 | 6.5 | 2 | 13958 | 167.1 | 192.6 |
| unknown | 30 | 28/30 | 4.3 | 30 | 3505 | 7.7 | 13.5 |
| window | 2 | 2/2 | 6.5 | 2 | 12753 | 14.9 | 18.0 |

Notes:
- These CSVs contain prompt_tokens > 0 = real Volcano Ark doubao-seed-2-1-lite runs
- stats.py aggregates logs/bench_*.csv; Mock runs (prompt_tokens = 0) are excluded from token/latency
- Benchmarks from 2026-11-15; real quota hit SetLimitExceeded after 29 full-strategy samples
