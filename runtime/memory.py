"""三层记忆存储。

- L1 工作记忆：当前任务的步骤记录，由 context.ContextManager 负责。
- L2 情景轨迹：过去完成的任务摘要，自动写入 episodic.jsonl。
- L3 长期事实：用户偏好、稳定常量，通过 remember 工具显式写入 facts.jsonl。

当前不做向量化检索，只按最近顺序取前 N 条，作为可扩展的 MVP。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEM_DIR = ROOT / "workspace" / ".memory"


class MemoryStore:
    def __init__(self, path: Path = MEM_DIR) -> None:
        self.facts_path = path / "facts.jsonl"
        self.episodes_path = path / "episodic.jsonl"
        path.mkdir(parents=True, exist_ok=True)
        self.facts = self._load(self.facts_path)
        self.episodes = self._load(self.episodes_path)

    @staticmethod
    def _load(path: Path) -> list[dict]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def add_fact(self, content: str, source: str = "") -> dict:
        record = {"fact": content, "source": source, "ts": round(time.time(), 3)}
        self.facts.append(record)
        with self.facts_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def add_episode(self, task: str, outcome: str, summary: str, steps: int) -> dict:
        record = {
            "task": task[:120],
            "outcome": outcome,
            "summary": summary[:200],
            "steps": steps,
            "ts": round(time.time(), 3),
        }
        self.episodes.append(record)
        with self.episodes_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def build_block(self, task: str, top_facts: int = 8, top_episodes: int = 3) -> str:
        """把最近的长期事实和近期任务拼成一段注入提示词的文本。"""
        lines = ["## 相关记忆"]
        facts = self.facts[-top_facts:]
        episodes = self.episodes[-top_episodes:]
        if facts:
            lines.append("### 长期事实")
            for fact in facts:
                lines.append(f"- {fact['fact']}")
        if episodes:
            lines.append("### 近期任务")
            for episode in episodes:
                lines.append(f"- {episode['task']}（{episode['outcome']}）：{episode['summary']}")
        if len(lines) == 1:
            lines.append("（暂无记忆）")
        return "\n".join(lines)

    def clear(self) -> None:
        self.facts = []
        self.episodes = []
        self.facts_path.write_text("", encoding="utf-8")
        self.episodes_path.write_text("", encoding="utf-8")


memory_store = MemoryStore()
