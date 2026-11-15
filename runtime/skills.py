"""Skill 体系：可复用的打法手册，支持热插拔与自进化。

一个 Skill 就是一个目录，里面必须有 manifest.json：
    skills/<name>/manifest.json

manifest 字段：
    name:         技能名（唯一）
    description:  一句话说明能做什么
    version:      版本号
    triggers:     触发关键词列表，任务文本命中任一关键词即匹配
    playbook:     打法步骤，会注入到系统提示供 Agent 参照
    tools:        （可选）该技能依赖的工具名列表

用法：
    registry = SkillRegistry(skills_dir)
    registry.reload()                      # 热加载：重新扫描目录
    skills = registry.match(task_prompt)   # 按触发词匹配
    block = registry.build_prompt_block(skills)  # 生成注入文本
    registry.create_skill(name, desc, triggers, playbook)  # 自进化：写新 skill
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS_DIR = ROOT / "skills"
STATS_PATH = ROOT / "workspace" / ".memory" / "skill_stats.json"


@dataclass
class Skill:
    name: str
    description: str
    version: str = "1.0"
    triggers: list[str] = field(default_factory=list)
    playbook: str = ""
    tools: list[str] = field(default_factory=list)
    path: Path | None = None

    def matches(self, text: str) -> bool:
        """任务文本命中任一触发关键词即匹配（不区分大小写）。"""
        lowered = text.lower()
        return any(trigger.lower() in lowered for trigger in self.triggers)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "triggers": self.triggers,
            "playbook": self.playbook,
            "tools": self.tools,
        }


class SkillRegistry:
    """管理所有 Skill 的加载、匹配、启用与创建。"""

    def __init__(self, skills_dir: Path | str | None = None, min_success_rate: float = 0.3, min_samples: int = 3) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, Skill] = {}
        self._enabled: set[str] = set()
        # 成功率统计：{name: {"success": int, "total": int}}
        self._stats: dict[str, dict[str, int]] = self._load_stats()
        self.min_success_rate = min_success_rate
        self.min_samples = min_samples
        self.reload()

    def _load_stats(self) -> dict[str, dict[str, int]]:
        if not STATS_PATH.exists():
            return {}
        try:
            return json.loads(STATS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_stats(self) -> None:
        STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATS_PATH.write_text(json.dumps(self._stats, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_outcome(self, skill_names: list[str], success: bool) -> None:
        """记录匹配到的 skill 在本次任务中的成功/失败。"""
        for name in skill_names:
            if name not in self._stats:
                self._stats[name] = {"success": 0, "total": 0}
            self._stats[name]["total"] += 1
            if success:
                self._stats[name]["success"] += 1
        self._save_stats()

    def success_rate(self, name: str) -> float | None:
        """返回某个 skill 的成功率，样本不足返回 None。"""
        stat = self._stats.get(name)
        if not stat or stat["total"] < self.min_samples:
            return None
        return stat["success"] / stat["total"]

    def is_healthy(self, name: str) -> bool:
        """skill 是否健康（样本不足视为健康，只有足够样本且成功率低于阈值才不健康）。"""
        rate = self.success_rate(name)
        if rate is None:
            return True
        return rate >= self.min_success_rate

    @property
    def stats(self) -> dict[str, dict[str, int]]:
        return dict(self._stats)

    def reload(self) -> int:
        """重新扫描 skills 目录，返回加载到的 skill 数量。已存在的 skill 状态保留。"""
        if not self.skills_dir.exists():
            return 0
        loaded: dict[str, Skill] = {}
        for manifest_path in sorted(self.skills_dir.glob("*/manifest.json")):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                skill = Skill(
                    name=str(data["name"]).strip(),
                    description=str(data.get("description", "")).strip(),
                    version=str(data.get("version", "1.0")),
                    triggers=list(data.get("triggers", []) or []),
                    playbook=str(data.get("playbook", "")).strip(),
                    tools=list(data.get("tools", []) or []),
                    path=manifest_path.parent,
                )
                loaded[skill.name] = skill
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                # 单个 skill 损坏不影响其他
                print(f"[skill] 加载失败 {manifest_path}: {exc}")
        self._skills = loaded
        # 保留之前已启用的状态，新 skill 默认启用
        self._enabled = {name for name in self._enabled if name in loaded} | set(loaded.keys())
        return len(loaded)

    @property
    def all_skills(self) -> list[Skill]:
        return list(self._skills.values())

    @property
    def enabled_skills(self) -> list[Skill]:
        return [s for s in self._skills.values() if s.name in self._enabled]

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def enable(self, name: str) -> bool:
        if name in self._skills:
            self._enabled.add(name)
            return True
        return False

    def disable(self, name: str) -> bool:
        self._enabled.discard(name)
        return name not in self._enabled

    def match(self, text: str) -> list[Skill]:
        """按触发词从已启用且健康的 skill 中匹配，返回命中的列表。"""
        return [
            s for s in self.enabled_skills
            if s.matches(text) and self.is_healthy(s.name)
        ]

    def build_prompt_block(self, skills: list[Skill]) -> str:
        """把匹配到的 skill 拼成系统提示里的注入文本。"""
        if not skills:
            return ""
        lines = ["## 可用技能（已匹配当前任务）"]
        lines.append("以下是经过验证的任务打法，匹配时请参照执行：")
        for skill in skills:
            lines.append("")
            lines.append(f"### {skill.name}：{skill.description}")
            if skill.playbook:
                lines.append(skill.playbook)
        lines.append("")
        lines.append("如果任务与某个技能匹配，优先按该技能的步骤执行。")
        return "\n".join(lines)

    def create_skill(
        self,
        name: str,
        description: str,
        triggers: list[str],
        playbook: str,
        version: str = "1.0",
        tools: list[str] | None = None,
    ) -> Skill:
        """把一个新 skill 写入磁盘并加载（自进化入口）。"""
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
        if not safe_name:
            raise ValueError("skill 名称不能为空")
        skill_dir = self.skills_dir / safe_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": safe_name,
            "description": description.strip(),
            "version": version,
            "triggers": [str(t).strip() for t in triggers if str(t).strip()],
            "playbook": playbook.strip(),
            "tools": tools or [],
        }
        (skill_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        skill = Skill(
            name=safe_name,
            description=description.strip(),
            version=version,
            triggers=manifest["triggers"],
            playbook=playbook.strip(),
            tools=tools or [],
            path=skill_dir,
        )
        self._skills[safe_name] = skill
        self._enabled.add(safe_name)
        return skill


# 全局单例，供 tools.py 的 learn_skill 使用
skill_registry = SkillRegistry()
