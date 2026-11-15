"""跑单个任务并给出结果，用法：

    D:\\Trae-CN\\tools\\python\\python.exe run_task.py evals\\tasks\\task_001.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from runtime.agent import Agent
from runtime.llm import LLMClient
from runtime.mock_llm import MockLLMClient
from runtime.skills import skill_registry
from runtime.trace import TraceLogger
from runtime.tools import WORKSPACE


def verify(spec: dict) -> tuple[bool, str]:
    """按任务定义的规则判分。"""
    if spec["type"] == "memory_contains":
        from runtime.memory import memory_store

        haystack = "\n".join(fact["fact"] for fact in memory_store.facts)
        missing = [item for item in spec["expect"] if item not in haystack]
        if missing:
            return False, f"记忆中缺少：{', '.join(missing)}"
        return True, f"记忆中包含全部 {len(spec['expect'])} 项"

    path = WORKSPACE / spec["path"]
    if not path.exists():
        return False, f"没有生成 {spec['path']}"
    text = path.read_text(encoding="utf-8").strip()
    if spec["type"] == "file_number":
        try:
            value = float(text)
        except ValueError:
            return False, f"{spec['path']} 内容不是数字：{text[:60]}"
        expect = float(spec["expect"])
        tolerance = float(spec.get("tolerance", 0.01))
        if abs(value - expect) <= tolerance:
            return True, f"{value} 与预期 {expect} 一致"
        return False, f"得到 {value}，预期 {expect}"
    if spec["type"] == "file_contains_all":
        missing = [item for item in spec["expect"] if item not in text]
        if missing:
            return False, f"缺少：{', '.join(missing)}"
        return True, f"包含全部 {len(spec['expect'])} 项"
    if spec["type"] == "file_starts_with":
        expect = str(spec["expect"])
        if text.lstrip().startswith(expect):
            return True, f"以 {expect!r} 开头"
        return False, f"实际内容：{text[:60]!r}"
    return False, f"未知判分类型：{spec['type']}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_file", help="任务 JSON 路径")
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--strategy", default="full", choices=["full", "window", "state_card", "summary"])
    parser.add_argument("--mock", action="store_true", help="用预设脚本跑，不消耗 API 额度")
    args = parser.parse_args()

    task = json.loads(Path(args.task_file).read_text(encoding="utf-8"))
    tracer = TraceLogger(task["id"])
    client = MockLLMClient() if args.mock else LLMClient()
    agent = Agent(client, tracer, max_steps=args.max_steps, strategy=args.strategy, skill_registry=skill_registry)

    try:
        result = agent.run(task["prompt"])
    finally:
        tracer.close()

    passed, reason = verify(task["verify"]) if result["ok"] else (False, "任务未完成")
    tokens = result["tokens"]
    print()
    print(f"任务：{task['id']}")
    print(f"结果：{'通过' if passed else '未通过'}（{reason}）")
    print(f"步数：{result['steps']}  耗时：{result['elapsed_ms'] / 1000:.1f}s  "
          f"tokens：{tokens['prompt_tokens']} + {tokens['completion_tokens']}")
    print(f"日志：{result['log']}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
