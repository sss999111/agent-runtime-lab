"""三层记忆存储。

- L1 工作记忆：当前任务的步骤记录，由 context.ContextManager 负责。
- L2 情景轨迹：过去完成的任务摘要，自动写入 episodic.jsonl。
- L3 长期事实：用户偏好、稳定常量，通过 remember 工具显式写入 facts.jsonl。

长期事实支持基于字符 n-gram 向量的余弦相似度检索，替代简单的「取最近 N 条」。
"""

from __future__ import annotations

import json
import math
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEM_DIR = ROOT / "workspace" / ".memory"


def _char_ngrams(text: str, n: int = 2) -> Counter:
    """提取字符 n-gram 频次，用于轻量级语义相似度。"""
    text = text.lower()
    if len(text) < n:
        return Counter([text])
    return Counter(text[i : i + n] for i in range(len(text) - n + 1))


def _cosine_similarity(vec_a: Counter, vec_b: Counter) -> float:
    """两个频次向量的余弦相似度。"""
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


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
        """把相关的长期事实和近期任务拼成一段注入提示词的文本。

        长期事实按与任务文本的余弦相似度排序（向量检索），
        情景轨迹仍按时间倒序取最近的（近期任务参考价值更高）。
        """
        lines = ["## 相关记忆"]
        # 长期事实：按相似度排序
        if self.facts:
            task_vec = _char_ngrams(task)
            scored = [
                (_cosine_similarity(task_vec, _char_ngrams(fact["fact"])), fact)
                for fact in self.facts
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            relevant = [fact for _, fact in scored[:top_facts] if _ > 0]
            # 如果相似度都为 0，退回最近 N 条
            if not relevant:
                relevant = self.facts[-top_facts:]
            lines.append("### 长期事实")
            for fact in relevant:
                lines.append(f"- {fact['fact']}")
        # 情景轨迹：取最近的
        episodes = self.episodes[-top_episodes:]
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
