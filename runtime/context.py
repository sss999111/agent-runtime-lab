"""上下文装配与压缩策略。

四种策略：
- full：全量保留，作为基线
- window：只保留最近若干步，更早的步骤直接丢弃
- state_card：把更早的步骤压成结构化记录（工具名 + 参数 + 结果摘要）
- summary：用模型把更早的步骤压成一段摘要
"""

from __future__ import annotations

from runtime.trace import TraceLogger

SUMMARY_SYSTEM = """把下面这些 Agent 执行步骤压缩成不超过 200 字的进展摘要。
必须保留：已经确认的事实与数字、涉及的文件路径、用户的目标与约束、尚未完成的下一步。
不要复述工具调用的完整输出。只输出摘要正文，不要任何前后缀。"""


class ContextManager:
    def __init__(
        self,
        client,
        tracer: TraceLogger,
        strategy: str = "full",
        window: int = 4,
    ) -> None:
        if strategy not in {"full", "window", "state_card", "summary"}:
            raise ValueError(f"未知策略：{strategy}")
        self.client = client
        self.tracer = tracer
        self.strategy = strategy
        self.window = window
        self._summary = ""
        self._summarized_turns = 0

    def build(self, system: str, task: str, turns: list[dict]) -> list[dict]:
        """按当前策略把对话历史装配成发给模型的消息列表。"""
        head = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        if self.strategy == "full" or len(turns) <= self.window:
            return head + self._expand(turns)

        old, recent = turns[: -self.window], turns[-self.window :]
        if self.strategy == "window":
            note = {"role": "user", "content": f"（此前 {len(old)} 步历史已省略，请根据最近进展继续）"}
            return head + [note] + self._expand(recent)

        if self.strategy == "state_card":
            card = {"role": "user", "content": self._state_card(old)}
            return head + [card] + self._expand(recent)

        self._update_summary(old)
        summary = {"role": "user", "content": f"历史进展摘要：\n{self._summary}"}
        return head + [summary] + self._expand(recent)

    @staticmethod
    def _expand(turns: list[dict]) -> list[dict]:
        messages: list[dict] = []
        for turn in turns:
            messages.append({"role": "assistant", "content": turn["assistant"]})
            messages.append({"role": "user", "content": f"观察结果：\n{turn['observation'][:2000]}"})
        return messages

    @staticmethod
    def _state_card(turns: list[dict]) -> str:
        lines = ["已完成的步骤（压缩记录，原始输出已省略）："]
        for index, turn in enumerate(turns, start=1):
            args = ", ".join(f"{key}={value}" for key, value in (turn.get("args") or {}).items())
            lines.append(f"- 第 {index} 步 {turn.get('tool', '')}({args})：{turn['observation'][:120]}")
        lines.append("请基于以上记录继续完成任务，不要重复已经成功的步骤。")
        return "\n".join(lines)

    def _update_summary(self, old: list[dict]) -> None:
        if self._summarized_turns == len(old):
            return
        material = [
            f"步骤 {index}：{turn.get('tool', '')} {turn.get('args', {})}\n结果：{turn['observation'][:400]}"
            for index, turn in enumerate(old, start=1)
        ]
        if self._summary:
            material.insert(0, f"已有摘要：{self._summary}")
        reply = self.client.chat(
            [
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": "\n\n".join(material)},
            ]
        )
        self._summary = reply["content"].strip()
        self._summarized_turns = len(old)
        self.tracer.log(
            {
                "event": "compress",
                "strategy": "summary",
                "turns": len(old),
                "summary_chars": len(self._summary),
                "tokens": reply.get("usage", {}),
            }
        )
