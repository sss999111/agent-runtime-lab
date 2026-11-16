"""示例插件：统计文本文件的行数 / 词数 / 字符数。

插件约定：暴露 run(**args) -> str，返回值会作为工具观察结果回给模型。
文件读取复用主程序的安全路径校验，插件不能越出 workspace。
"""

from __future__ import annotations


def run(path: str) -> str:
    from runtime.tools import _safe_path

    text = _safe_path(path).read_text(encoding="utf-8")
    lines = len(text.splitlines())
    words = len(text.split())
    return f"行数 {lines}，词数 {words}，字符数 {len(text)}"
