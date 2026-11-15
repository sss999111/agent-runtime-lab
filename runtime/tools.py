"""Agent 可调用的工具集合。所有文件路径都限制在 workspace 目录内。"""

from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "workspace"


def _safe_path(relative: str) -> Path:
    target = (WORKSPACE / relative).resolve()
    if not str(target).startswith(str(WORKSPACE.resolve())):
        raise ValueError("路径必须位于 workspace 内")
    return target


def read_file(path: str) -> str:
    """读取工作区内的文本文件。"""
    content = _safe_path(path).read_text(encoding="utf-8")
    return content[:20000]


def write_file(path: str, content: str) -> str:
    """写入文件，自动创建父目录。"""
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {path}（{len(content)} 个字符）"


def list_files(pattern: str = "**/*") -> str:
    """按通配符列出工作区内的文件。"""
    files = sorted(str(p.relative_to(WORKSPACE)) for p in WORKSPACE.glob(pattern) if p.is_file())
    return "\n".join(files) if files else "（没有匹配的文件）"


def run_python(code: str) -> str:
    """在工作区内执行一段 Python 代码并返回输出。"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    output = (result.stdout + result.stderr).strip()
    return output[:4000] if output else "（没有输出）"


def http_get(url: str) -> str:
    """抓取网页前 3000 个字符。"""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")[:3000]


def remember(content: str) -> str:
    """把一条长期事实写入记忆库，供后续任务参考。"""
    from runtime.memory import memory_store

    memory_store.add_fact(content, source="agent")
    return f"已写入长期记忆：{content[:100]}"


def learn_skill(name: str, description: str, triggers: str, playbook: str) -> str:
    """把成功的任务打法沉淀为一个新 Skill，后续同类任务可参照。

    参数：
        name:        技能名（英文/数字/下划线）
        description: 一句话说明能做什么
        triggers:    触发关键词，逗号分隔
        playbook:    打法步骤（多行文本）
    """
    from runtime.skills import skill_registry

    trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]
    try:
        skill = skill_registry.create_skill(name, description, trigger_list, playbook)
    except ValueError as exc:
        return f"创建 skill 失败：{exc}"
    return f"已创建技能 {skill.name}（触发词：{', '.join(skill.triggers)}），后续同类任务会自动参照。"


TOOL_SPECS: dict[str, str] = {
    "read_file": "读取工作区内的文本文件。参数：path",
    "write_file": "写入文件并自动建目录。参数：path, content",
    "list_files": "按通配符列出工作区内文件。参数：pattern，例如 **/*.csv",
    "run_python": "在工作区内执行 Python 代码并返回输出，适合计算和数据处理。参数：code",
    "http_get": "抓取网页文本，返回前 3000 字符。参数：url",
    "remember": "把一条长期事实写入记忆库，后续任务会看到。参数：content",
    "learn_skill": "把成功的任务打法沉淀为新 Skill，后续同类任务自动参照。参数：name, description, triggers(逗号分隔), playbook",
}

ARG_HINTS: dict[str, str] = {
    "read_file": '{"path": "文件名"}',
    "write_file": '{"path": "文件名", "content": "要写入的内容"}',
    "list_files": '{"pattern": "**/*.csv"}',
    "run_python": '{"code": "要执行的 Python 代码"}',
    "http_get": '{"url": "https://..."}',
    "remember": '{"content": "要记住的事情"}',
    "learn_skill": '{"name": "技能名", "description": "一句话说明", "triggers": "关键词1,关键词2", "playbook": "步骤1\\n步骤2"}',
}

_TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files,
    "run_python": run_python,
    "http_get": http_get,
    "remember": remember,
    "learn_skill": learn_skill,
}


def run_tool(name: str, args: dict) -> str:
    """执行工具调用，失败时把错误作为观察结果返回给模型。"""
    if name not in _TOOLS:
        return f"未知工具：{name}。可用工具：{', '.join(sorted(_TOOLS))}"
    try:
        return str(_TOOLS[name](**args))
    except TypeError as exc:
        return f"参数不正确：{exc}。正确写法：{name} {ARG_HINTS.get(name, '')}"
    except Exception as exc:
        return f"工具执行失败：{type(exc).__name__}: {exc}"
