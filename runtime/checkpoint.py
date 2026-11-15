"""任务检查点：保存和恢复执行状态，支持断点续跑。

参考 LangGraph 的 checkpointing 思路：把 turns、步数、token 统计存成 JSON，
下次启动时加载，从断点继续执行。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_DIR = ROOT / "workspace" / ".checkpoints"


class CheckpointManager:
    def __init__(self, checkpoint_dir: Path = CHECKPOINT_DIR) -> None:
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, task: str) -> Path:
        # 用任务文本的 hash 做文件名，避免特殊字符
        safe = str(abs(hash(task)))[:16]
        return self.checkpoint_dir / f"ckpt_{safe}.json"

    def save(self, task: str, step: int, turns: list[dict], tokens: dict) -> None:
        """保存当前执行状态。"""
        data = {
            "task": task[:200],
            "step": step,
            "turns": turns,
            "tokens": tokens,
            "ts": round(time.time(), 3),
        }
        self._path(task).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def load(self, task: str) -> dict | None:
        """加载断点状态，没有则返回 None。"""
        path = self._path(task)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def clear(self, task: str) -> None:
        """任务完成后清除断点。"""
        path = self._path(task)
        if path.exists():
            path.unlink()

    def has(self, task: str) -> bool:
        return self._path(task).exists()


checkpoint_manager = CheckpointManager()
