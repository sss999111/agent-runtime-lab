"""批量跑评测集，输出一张基准表。

用法示例：
    python bench.py
    python bench.py --strategy window --tasks task_011,task_012 --repeat 3
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from run_task import verify
from runtime.agent import Agent
from runtime.llm import LLMClient
from runtime.mock_llm import MockLLMClient
from runtime.skills import skill_registry
from runtime.trace import TraceLogger

ROOT = Path(__file__).resolve().parent
TASK_DIR = ROOT / "evals" / "tasks"
RESULT_DIR = ROOT / "logs"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="full", choices=["full", "window", "state_card", "summary"])
    parser.add_argument("--tasks", default="", help="逗号分隔的任务 id，留空则跑全部")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--window", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--reset-memory", action="store_true", help="运行前清空长期记忆和情景轨迹")
    parser.add_argument("--reset-out", action="store_true", help="运行前清空 workspace/out/，避免上一次运行的产物污染本次评测")
    parser.add_argument("--mock", action="store_true", help="用预设脚本跑，不消耗 API 额度")
    args = parser.parse_args()

    if args.reset_memory:
        from runtime.memory import memory_store

        memory_store.clear()

    if args.reset_out:
        import shutil

        out_dir = ROOT / "workspace" / "out"
        if out_dir.exists():
            shutil.rmtree(out_dir)
            print("已清空 workspace/out/")

    task_files = sorted(TASK_DIR.glob("*.json"))
    if args.tasks:
        wanted = {item.strip() for item in args.tasks.split(",") if item.strip()}
        task_files = [path for path in task_files if path.stem in wanted]
    if not task_files:
        print("没有匹配的任务")
        return 1

    client = MockLLMClient() if args.mock else LLMClient()
    rows: list[dict] = []
    started = time.perf_counter()
    total_runs = len(task_files) * args.repeat

    print(f"策略 {args.strategy}  任务 {len(task_files)} 个  重复 {args.repeat} 次  模型 {client.model_id}")
    print()
    for path in task_files:
        task = json.loads(path.read_text(encoding="utf-8"))
        for run_index in range(1, args.repeat + 1):
            tracer = TraceLogger(f"{task['id']}_r{run_index}")
            try:
                result = Agent(
                    client,
                    tracer,
                    max_steps=args.max_steps,
                    strategy=args.strategy,
                    window=args.window,
                    skill_registry=skill_registry,
                ).run(task["prompt"])
            finally:
                tracer.close()

            passed, reason = verify(task["verify"]) if result["ok"] else (False, "任务未完成")
            row = {
                "strategy": args.strategy,
                "task": task["id"],
                "run": run_index,
                "passed": passed,
                "reason": reason,
                "steps": result["steps"],
                "prompt_tokens": result["tokens"]["prompt_tokens"],
                "completion_tokens": result["tokens"]["completion_tokens"],
                "elapsed_s": round(result["elapsed_ms"] / 1000, 1),
                "log": result["log"],
            }
            rows.append(row)
            index = len(rows)
            print(
                f"[{index}/{total_runs}] {row['task']} #{run_index}  "
                f"{'通过' if passed else '未通过'}  {row['steps']} 步  "
                f"{row['prompt_tokens']}+{row['completion_tokens']} tokens  {row['elapsed_s']}s"
            )

    total_s = time.perf_counter() - started
    passed_count = sum(1 for row in rows if row["passed"])
    avg_steps = sum(row["steps"] for row in rows) / len(rows)
    avg_prompt = sum(row["prompt_tokens"] for row in rows) / len(rows)
    avg_total = sum(row["prompt_tokens"] + row["completion_tokens"] for row in rows) / len(rows)

    print()
    print(f"通过 {passed_count}/{len(rows)}  平均 {avg_steps:.1f} 步  "
          f"平均输入 {avg_prompt:.0f} tokens  平均合计 {avg_total:.0f} tokens  总耗时 {total_s:.1f}s")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULT_DIR / f"bench_{args.strategy}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"明细已写入 {csv_path}")
    return 0 if passed_count == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
