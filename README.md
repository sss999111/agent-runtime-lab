# agent-runtime-lab

A general-purpose task agent runtime with built-in evaluation and ablation experiments: pluggable Skills, three-layer memory, context budget compression, and an observable scheduler with failure attribution.

[中文 README](README_zh.md)

## What it does

This project builds an agent runtime from scratch (no framework, pure Python stdlib) and answers three engineering questions with reproducible numbers:

1. How much can context be compressed before critical constraints are lost?
2. On which tasks does three-layer memory actually help, and where is it pure overhead?
3. As the Skill library grows, how much do on-demand loading and self-evolution each contribute?

Every claim is backed by run traces in `logs/`. No hand-waving.

## Key results

| Module | Finding | Evidence |
|---|---|---|
| **Context compression** | `state_card` cuts input tokens by **34%** with zero success-rate drop, only +18% latency | `docs/experiments/001-context-compression.md` |
| **Three-layer memory** | With long-term memory: **4/4** tasks pass in 2.5 steps; without: **0/2** exhaust 8 steps | `docs/experiments/002-memory.md` |
| **Scheduler** | Parallel tool calls verified; `FailureBudget` stops repeated failed calls after 2 repeats | `docs/experiments/003-scheduler.md` |
| **Skills** | Manifest-based playbooks injected by trigger match; `learn_skill` self-evolves new skills to disk | `docs/experiments/004-skills.md` |

## Architecture

```
run_task.py / bench.py
        │
        ▼
   Agent (ReAct loop)
        │
        ├── ContextManager  → full / window / state_card / summary
        ├── MemoryStore     → L1 working / L2 episodic / L3 long-term facts
        ├── SkillRegistry   → match by triggers, inject playbook, hot-plug, self-evolve
        ├── Scheduler       → execute_parallel + FailureBudget
        └── Tools           → read_file / write_file / list_files / run_python / http_get / remember / learn_skill
```

## Quick start

```powershell
# 1. Paste API key & model ID (writes .env automatically)
D:\Trae-CN\tools\python\python.exe scripts\set_key.py

# 2. Connectivity self-check
D:\Trae-CN\tools\python\python.exe scripts\smoke_ark.py

# 3. Run a single task
D:\Trae-CN\tools\python\python.exe run_task.py evals\tasks\task_001.json

# 4. Run full benchmark (16 tasks)
D:\Trae-CN\tools\python\python.exe bench.py --reset-memory
```

Python is a portable install at `D:\Trae-CN\tools\python\python.exe`; no system PATH dependency.

## Zero-cost regression

All 16 tasks support `--mock` mode, which uses scripted responses instead of calling the real LLM — full pipeline coverage with **0 API tokens**:

```powershell
D:\Trae-CN\tools\python\python.exe bench.py --mock --reset-memory
# → 16/16 passed, 0 tokens, 0.3s
```

Use this for every code change; reserve real API calls for effect experiments only.

## Project structure

```
runtime/
  agent.py        ReAct main loop (action / actions / finish)
  context.py      4 context assembly strategies
  memory.py       three-layer memory (facts.jsonl / episodic.jsonl)
  scheduler.py    parallel execution + FailureBudget
  skills.py       Skill manifest loader, registry, self-evolution
  tools.py        7 tools, paths sandboxed to workspace/
  llm.py          Volcano Ark (Doubao) OpenAI-compatible client
  mock_llm.py     scripted mock LLM for zero-quota regression
  trace.py        per-step JSONL trace logger
evals/tasks/      16 auto-gradable tasks
skills/           skill manifests (each a subdir with manifest.json)
logs/             run traces (the only trusted data source)
docs/experiments/ experiment records with raw numbers
```

## Status

- [x] P0: ReAct loop + 7 tools + trace logging + 16 tasks + baseline
- [x] P1: Context compression (4 strategies), three-layer memory, scheduler (parallel + failure budget)
- [x] P2: Skill system (manifest + hot-plug + self-evolution via `learn_skill`)
- [x] P3a: English README, blog post, resume bullets, demo script
- [ ] P3b: Web console
