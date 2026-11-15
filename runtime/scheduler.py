"""调度器：并行工具调用、单步超时、重复失败强制重规划。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from runtime.tools import run_tool


def _normalize_call(call: dict) -> tuple[str, dict]:
    action = call or {}
    name = str(action.get("tool", "")).strip()
    args = action.get("args") or action.get("arguments") or action.get("parameters") or {}
    if not isinstance(args, dict):
        args = {}
    if not args:
        args = {
            key: value
            for key, value in action.items()
            if key not in {"tool", "args", "arguments", "parameters"}
        }
    return name, args


def execute_parallel(calls: list[dict], max_workers: int = 4, timeout: float = 30) -> list[str]:
    """并行执行多个工具调用，按输入顺序返回观察结果。"""
    results: list[str | None] = [None] * len(calls)
    if not calls:
        return []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(calls))) as executor:
        future_to_index = {}
        for index, call in enumerate(calls):
            name, args = _normalize_call(call)
            future = executor.submit(run_tool, name, args)
            future_to_index[future] = index
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result(timeout=timeout)
            except TimeoutError:
                results[index] = f"工具执行超时（超过 {timeout} 秒），已终止"
            except Exception as exc:
                results[index] = f"工具执行异常：{type(exc).__name__}: {exc}"
    return [str(item) for item in results]


def format_observations(calls: list[dict], observations: list[str]) -> str:
    """把并行调用的结果拼成一条观察文本。"""
    lines = ["并行工具调用结果："]
    for index, (call, observation) in enumerate(zip(calls, observations), start=1):
        name, args = _normalize_call(call)
        lines.append(f"{index}. {name}({args}) -> {observation[:300]}")
    return "\n".join(lines)


class FailureBudget:
    """同一调用签名连续失败超过阈值时，强制提示模型换方法。"""

    def __init__(self, max_repeat: int = 2) -> None:
        self.max_repeat = max_repeat
        self._counts: dict[str, int] = {}

    def check(self, signature: str, failed: bool) -> str | None:
        if failed:
            self._counts[signature] = self._counts.get(signature, 0) + 1
        else:
            self._counts.pop(signature, None)
        count = self._counts.get(signature, 0)
        if count >= self.max_repeat:
            return (
                f"注意：这个调用已经连续失败 {count} 次，继续重试没有意义。"
                "请重新阅读用户任务，换一种工具或参数。"
            )
        return None
