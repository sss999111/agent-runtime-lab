"""轨迹日志：每一步一行 JSON，是后续所有指标的唯一数据源。"""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"


class TraceLogger:
    def __init__(self, task_id: str) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in task_id)
        self.path = LOG_DIR / f"{stamp}_{safe_id}.jsonl"
        self._file = self.path.open("a", encoding="utf-8")

    def log(self, event: dict) -> None:
        record = {"ts": round(time.time(), 3), **event}
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()
