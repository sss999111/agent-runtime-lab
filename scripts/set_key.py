"""把火山方舟的 API Key 写入项目根目录的 .env。

用法：
    D:\\Trae-CN\\tools\\python\\python.exe scripts\\set_key.py

模型 ID 已在 .env 里预置，直接回车沿用即可；API Key 只需粘贴一次。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DEFAULT_MODEL_ID = "doubao-seed-2-1-lite-260915"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    current = read_env(ENV_PATH)
    current_model = current.get("ARK_MODEL_ID") or DEFAULT_MODEL_ID

    print("请先回到浏览器，在「API Key 管理」页面复制 agent-runtime-lab 那一行的 Key。")
    print("（如果列表里只有遮罩看不见值，就点「新建」再建一个，弹出的窗口里立刻复制）")
    print()

    api_key = input("粘贴 API Key 后回车：").strip()
    if len(api_key) < 10:
        print("这串太短了，看起来不是 API Key，请重新运行本脚本。")
        return 1

    model_id = input(f"模型 ID（直接回车沿用 {current_model}）：").strip() or current_model

    ENV_PATH.write_text(
        "# 本地配置，请勿提交到 git\n"
        f"ARK_API_KEY={api_key}\n"
        f"ARK_MODEL_ID={model_id}\n",
        encoding="utf-8",
    )
    print()
    print(f"已写入 {ENV_PATH}")
    print("下一步运行连通性自检：")
    print(r"  D:\Trae-CN\tools\python\python.exe D:\Trae-CN\agent-runtime-lab\scripts\smoke_ark.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
