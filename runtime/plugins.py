"""工具插件注册表：往 plugins/<name>/ 放一个目录，就能给 Agent 增加新工具。

插件目录结构：
    plugins/<name>/plugin.json   {"name": ..., "description": ..., "args_hint": ...}
    plugins/<name>/plugin.py     def run(**args) -> str

设计取舍：
- 插件在本进程内运行，属于「本地可信代码」，不追求沙箱隔离（与 MCP 的进程隔离是不同层次）。
- 加载失败只跳过该插件并记录原因，不影响主循环启动。
- 与 Skill 的区别：Skill 是「怎么用工具」的打法（提示词），插件是「新增一个工具」（能力）。
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins"


@dataclass
class Plugin:
    name: str
    description: str
    args_hint: str
    run: callable
    source: Path


class PluginRegistry:
    def __init__(self, directory: Path = PLUGIN_DIR) -> None:
        self.directory = directory
        self.plugins: dict[str, Plugin] = {}
        self.errors: list[str] = []

    def load(self) -> dict[str, Plugin]:
        """扫描插件目录，覆盖式重建注册表。"""
        self.plugins = {}
        self.errors = []
        if not self.directory.exists():
            return self.plugins
        for manifest_path in sorted(self.directory.glob("*/plugin.json")):
            try:
                self._load_one(manifest_path)
            except Exception as exc:  # 单个插件坏掉不影响其它插件
                self.errors.append(f"{manifest_path.parent.name}: {type(exc).__name__}: {exc}")
        return self.plugins

    def _load_one(self, manifest_path: Path) -> None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        name = str(manifest["name"]).strip()
        if not name.isidentifier():
            raise ValueError("插件名必须是合法标识符（字母/数字/下划线）")
        entry = manifest_path.parent / "plugin.py"
        if not entry.exists():
            raise FileNotFoundError("缺少 plugin.py")
        spec = importlib.util.spec_from_file_location(f"agent_plugin_{name}", entry)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        run = getattr(module, "run", None)
        if not callable(run):
            raise AttributeError("plugin.py 必须定义 run(**args)")
        self.plugins[name] = Plugin(
            name=name,
            description=str(manifest.get("description", "")),
            args_hint=str(manifest.get("args_hint", "{}")),
            run=run,
            source=entry,
        )

    def register_into(self, specs: dict, hints: dict, tools: dict) -> None:
        """把插件并入主循环的工具表（跳过与内置工具重名的插件）。"""
        for name, plugin in self.plugins.items():
            if name in tools:
                self.errors.append(f"{name}: 与内置工具重名，已跳过")
                continue
            specs[name] = plugin.description
            hints[name] = plugin.args_hint
            tools[name] = plugin.run

    def reload(self) -> dict[str, Plugin]:
        return self.load()

    def summary(self) -> str:
        if not self.plugins:
            return "（没有加载到插件）"
        return "、".join(f"{p.name}" for p in self.plugins.values())


plugin_registry = PluginRegistry()
plugin_registry.load()
