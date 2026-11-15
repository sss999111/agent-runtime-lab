"""火山方舟（Ark）连通性自检：发一轮对话，打印回复、耗时与 token 用量。

用法：
    1. 在仓库根目录把 .env.example 复制为 .env，填入 ARK_API_KEY 与 ARK_MODEL_ID
    2. D:\\Trae-CN\\tools\\python\\python.exe scripts\\smoke_ark.py

只依赖标准库，装好 Python 即可运行。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> None:
    """读取简单的 KEY=VALUE 配置，已存在的环境变量优先。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_env(ROOT / ".env")

    api_key = os.environ.get("ARK_API_KEY", "").strip()
    model_id = os.environ.get("ARK_MODEL_ID", "").strip()
    missing = [name for name, value in (("ARK_API_KEY", api_key), ("ARK_MODEL_ID", model_id)) if not value]
    if missing:
        print("缺少配置：" + "、".join(missing))
        print("请复制 .env.example 为 .env 并填写后重试。")
        return 2

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "用一句话说明什么是 Agent 的上下文压缩。"}],
        "temperature": 0.3,
    }
    request = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"调用失败 HTTP {exc.code}：{detail}")
        return 1
    except urllib.error.URLError as exc:
        print(f"网络错误：{exc.reason}")
        return 1

    latency_ms = (time.perf_counter() - started) * 1000
    content = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})

    print("回复：", content.strip())
    print(f"耗时：{latency_ms:.0f} ms")
    print(
        "tokens：输入 {prompt} / 输出 {completion} / 合计 {total}".format(
            prompt=usage.get("prompt_tokens"),
            completion=usage.get("completion_tokens"),
            total=usage.get("total_tokens"),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
