"""进度跟踪：对齐 Aime 论文的 Progress Management 思路。

每一步记录「已完成什么 / 下一步是什么」，拼成系统提示的一部分，
让 Agent 有全局状态视图，避免重复劳动和迷失方向。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProgressTracker:
    """记录任务执行进度，生成全局状态视图。"""

    completed: list[str] = field(default_factory=list)
    next_hint: str = ""

    def record(self, action: str, result: str, thought: str = "") -> None:
        """记录一步已完成的操作。"""
        summary = thought or action
        if result:
            result_short = result.replace("\n", " ")[:80]
            self.completed.append(f"{summary} → {result_short}")
        else:
            self.completed.append(summary)

    def set_next(self, hint: str) -> None:
        """设置下一步的提示（来自模型的 thought）。"""
        self.next_hint = hint[:120]

    def build_block(self) -> str:
        """生成进度状态文本，注入系统提示。"""
        if not self.completed and not self.next_hint:
            return ""
        lines = ["## 当前进度"]
        if self.completed:
            lines.append("已完成：")
            for index, item in enumerate(self.completed[-8:], start=1):
                lines.append(f"{index}. {item}")
        if self.next_hint:
            lines.append(f"下一步计划：{self.next_hint}")
        lines.append("不要重复已经完成的步骤。")
        return "\n".join(lines)

    def reset(self) -> None:
        self.completed.clear()
        self.next_hint = ""
