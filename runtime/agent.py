"""ReAct 主循环：规划 -> 调工具 -> 看结果 -> 继续或结束。"""

from __future__ import annotations

import json
import re
import time

from runtime.checkpoint import checkpoint_manager
from runtime.context import ContextManager
from runtime.llm import LLMClient
from runtime.progress import ProgressTracker
from runtime.scheduler import FailureBudget, execute_parallel, format_observations
from runtime.skills import SkillRegistry
from runtime.tools import TOOL_SPECS, run_tool
from runtime.trace import TraceLogger

SYSTEM_PROMPT = """你是一个通用任务型 Agent，通过调用工具完成用户交代的任务。

工作区目录是 workspace/，所有工具里的路径都相对于它。

每一步只输出一个 JSON 对象，不要输出任何解释、不要用 markdown 代码块。
调用工具时：
{{"thought": "一句话说明为什么这么做", "action": {{"tool": "工具名", "args": {{"参数名": "参数值"}}}}}}
如果多个工具调用互相独立，可以一次并行执行多个：
{{"thought": "一句话说明为什么这么做", "actions": [{{"tool": "工具1", "args": {{...}}}}, {{"tool": "工具2", "args": {{...}}}}]}}
任务完成时：
{{"thought": "一句话总结", "finish": {{"answer": "给用户的结果"}}}}

可用工具：
{tools}

必须遵守：
0. 长期记忆里的事实是用户明确表达的偏好或约束，执行任务时必须遵守。
1. 先观察再行动，不要凭空猜文件里的数据。
2. 每次只调用一个工具。
3. 工具失败时阅读报错并换一种方法，不要重复同样的调用。
4. 写文件后读回确认内容正确，再结束任务。
""".format(tools="\n".join(f"- {name}：{desc}" for name, desc in TOOL_SPECS.items()))


def parse_reply(text: str) -> dict:
    """从模型输出里取出 JSON 对象，兼容模型多说了几句或加了代码块的情况。"""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("输出里没有 JSON 对象")
    return json.loads(cleaned[start : end + 1])


def _call_name_args(call: dict) -> tuple[str, dict]:
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


class Agent:
    def __init__(
        self,
        client: LLMClient,
        tracer: TraceLogger,
        max_steps: int = 8,
        strategy: str = "full",
        window: int = 4,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.client = client
        self.tracer = tracer
        self.max_steps = max_steps
        self.context = ContextManager(client, tracer, strategy=strategy, window=window)
        self.skill_registry = skill_registry

    def run(self, task: str, resume: bool = False) -> dict:
        from runtime.memory import memory_store

        turns: list[dict] = []
        tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        failure_budget = FailureBudget(max_repeat=2)
        progress = ProgressTracker()
        start_step = 1
        started = time.perf_counter()

        # 断点恢复：从 checkpoint 加载 turns 和步数
        if resume and checkpoint_manager.has(task):
            ckpt = checkpoint_manager.load(task)
            if ckpt:
                turns = ckpt["turns"]
                tokens = ckpt["tokens"]
                start_step = ckpt["step"] + 1
                # 恢复进度
                for turn in turns:
                    progress.record(turn.get("tool", ""), turn.get("observation", ""), "")
                print(f"[resume] 从第 {start_step} 步继续，已有 {len(turns)} 步历史")

        memory_block = memory_store.build_block(task)
        system_prompt = f"{memory_block}\n\n{SYSTEM_PROMPT}"

        # 注入匹配到的 skill（打法手册）
        matched_skills: list = []
        if self.skill_registry is not None:
            matched_skills = self.skill_registry.match(task)
            if matched_skills:
                skill_block = self.skill_registry.build_prompt_block(matched_skills)
                system_prompt = f"{system_prompt}\n\n{skill_block}"

        self.tracer.log(
            {
                "event": "start",
                "task": task,
                "model": self.client.model_id,
                "strategy": self.context.strategy,
                "memory_facts": len(memory_store.facts),
                "memory_episodes": len(memory_store.episodes),
                "matched_skills": [s.name for s in matched_skills],
            }
        )

        for step in range(start_step, self.max_steps + 1):
            # 每步注入当前进度（全局状态视图，对齐 Aime 的 Progress Management）
            progress_block = progress.build_block()
            step_system_prompt = f"{system_prompt}\n\n{progress_block}" if progress_block else system_prompt
            messages = self.context.build(step_system_prompt, task, turns)
            context_chars = sum(len(message["content"]) for message in messages)
            reply = self.client.chat(messages)
            usage = reply.get("usage") or {}
            tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
            tokens["completion_tokens"] += usage.get("completion_tokens", 0)

            try:
                parsed = parse_reply(reply["content"])
            except (ValueError, json.JSONDecodeError) as exc:
                self.tracer.log(
                    {
                        "event": "parse_error",
                        "step": step,
                        "error": str(exc),
                        "context_chars": context_chars,
                        "raw": reply["content"][:300],
                        "latency_ms": round(reply["latency_ms"]),
                    }
                )
                turns.append(
                    {
                        "assistant": reply["content"],
                        "tool": "",
                        "args": {},
                        "observation": "上一条输出不是合法 JSON，请只输出一个 JSON 对象。",
                    }
                )
                continue

            if "finish" in parsed:
                answer = str((parsed.get("finish") or {}).get("answer", ""))
                elapsed = (time.perf_counter() - started) * 1000
                memory_store.add_episode(task, "完成", answer, step)
                # 任务成功：记录 skill 成功率并清除检查点
                if self.skill_registry is not None and matched_skills:
                    self.skill_registry.record_outcome(
                        [s.name for s in matched_skills], success=True
                    )
                checkpoint_manager.clear(task)
                self.tracer.log(
                    {
                        "event": "finish",
                        "step": step,
                        "answer": answer,
                        "ok": True,
                        "tokens": tokens,
                        "elapsed_ms": round(elapsed),
                    }
                )
                return {
                    "ok": True,
                    "answer": answer,
                    "steps": step,
                    "tokens": tokens,
                    "elapsed_ms": elapsed,
                    "log": str(self.tracer.path),
                }

            single_action = parsed.get("action")
            multi_actions = parsed.get("actions")
            calls: list[dict] = []
            if isinstance(multi_actions, list) and multi_actions:
                calls = [item for item in multi_actions if isinstance(item, dict)]
            elif isinstance(single_action, dict):
                calls = [single_action]

            if not calls:
                turns.append(
                    {
                        "assistant": reply["content"],
                        "tool": "",
                        "args": {},
                        "observation": "没有指定要调用的工具，请输出 action 或 actions。",
                    }
                )
                continue

            observations = execute_parallel(calls) if len(calls) > 1 else [run_tool(*_call_name_args(calls[0]))]
            tool_names = [_call_name_args(c)[0] for c in calls]
            tool_args_list = [_call_name_args(c)[1] for c in calls]

            combined_obs = (
                observations[0]
                if len(calls) == 1
                else format_observations(calls, observations)
            )

            any_failed = any(
                obs.startswith(("参数不正确", "工具执行失败", "未知工具", "工具执行超时", "工具执行异常"))
                for obs in observations
            )
            budget_msg: str | None = None
            if any_failed and len(calls) == 1:
                signature = f"{tool_names[0]}:{json.dumps(tool_args_list[0], ensure_ascii=False, sort_keys=True)}"
                budget_msg = failure_budget.check(signature, True)
                if budget_msg:
                    combined_obs += f"\n{budget_msg}"

            self.tracer.log(
                {
                    "event": "step",
                    "step": step,
                    "thought": parsed.get("thought", ""),
                    "tool": ",".join(tool_names),
                    "args": tool_args_list if len(calls) > 1 else tool_args_list[0],
                    "parallel": len(calls) > 1,
                    "call_count": len(calls),
                    "raw": reply["content"][:400],
                    "observation": combined_obs[:500],
                    "context_chars": context_chars,
                    "latency_ms": round(reply["latency_ms"]),
                    "tokens": usage,
                }
            )
            turns.append(
                {
                    "assistant": reply["content"],
                    "tool": ",".join(tool_names),
                    "args": tool_args_list[0] if len(calls) == 1 else tool_args_list,
                    "observation": combined_obs,
                }
            )
            # 更新进度跟踪
            progress.record(",".join(tool_names), combined_obs, parsed.get("thought", ""))
            # 保存检查点（断点续跑）
            checkpoint_manager.save(task, step, turns, tokens)

        # 任务结束：记录 skill 成功率（无论成功失败）
        if self.skill_registry is not None and matched_skills:
            self.skill_registry.record_outcome(
                [s.name for s in matched_skills],
                success=False,  # 跑出循环说明失败
            )

        elapsed = (time.perf_counter() - started) * 1000
        memory_store.add_episode(task, "失败", "超过最大步数", self.max_steps)
        # 注意：失败时不清除 checkpoint，方便下次用 --resume 续跑
        self.tracer.log(
            {
                "event": "finish",
                "step": self.max_steps,
                "ok": False,
                "reason": "超过最大步数",
                "tokens": tokens,
                "elapsed_ms": round(elapsed),
            }
        )
        return {
            "ok": False,
            "answer": "",
            "steps": self.max_steps,
            "tokens": tokens,
            "elapsed_ms": elapsed,
            "log": str(self.tracer.path),
        }
