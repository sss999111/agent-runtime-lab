"""火山方舟模型客户端：OpenAI 兼容接口，只依赖标准库。"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ROOT = Path(__file__).resolve().parents[1]


class LLMError(RuntimeError):
    """模型调用失败。"""


def load_env(path: Path | None = None) -> None:
    """读取 .env，已存在的环境变量优先。"""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class LLMClient:
    def __init__(self, temperature: float = 0.2, max_tokens: int = 1200, retries: int = 2) -> None:
        load_env()
        self.api_key = os.environ.get("ARK_API_KEY", "").strip()
        self.model_id = os.environ.get("ARK_MODEL_ID", "").strip()
        if not self.api_key or not self.model_id:
            raise LLMError("缺少 ARK_API_KEY 或 ARK_MODEL_ID，请先运行 scripts/set_key.py")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.retries = retries

    def chat(self, messages: list[dict]) -> dict:
        """发一轮对话，返回回复文本、token 用量与耗时。"""
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            request = urllib.request.Request(
                BASE_URL,
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
                method="POST",
            )
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "usage": data.get("usage", {}),
                    "latency_ms": (time.perf_counter() - started) * 1000,
                }
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = LLMError(f"HTTP {exc.code}: {detail}")
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
            time.sleep(1 + attempt)

        raise LLMError(f"模型调用失败：{last_error}")
