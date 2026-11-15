# 实验 004：Skill 体系（manifest + 热插拔 + 自进化）

## 目标

验证 Skill 体系三个能力：
1. **Manifest 声明与注入**：把验证过的任务打法（playbook）按关键词匹配注入系统提示，减少 Agent 摸索步数。
2. **热插拔**：运行中新增/删除 skill 文件后，`reload()` 能动态生效，无需重启。
3. **自进化**：Agent 通过 `learn_skill` 工具把成功经验沉淀为新 skill，下次同类任务自动参照。

## 实现

- `runtime/skills.py`：
  - `Skill` 数据类：`name / description / version / triggers / playbook / tools`，`matches(text)` 按触发词（不区分大小写）判断。
  - `SkillRegistry`：扫描 `skills/*/manifest.json` 加载；`match(task)` 过滤已启用 skill；`build_prompt_block(skills)` 拼成注入文本；`enable/disable`；`create_skill(...)` 写 manifest 到磁盘（自进化入口）；`reload()` 热加载。
  - 全局单例 `skill_registry`，供 `tools.py` 调用。
- `runtime/agent.py`：`Agent` 新增 `skill_registry` 参数；`run()` 启动时 `match(task)` 取命中 skill，把 playbook 追加到系统提示；轨迹记录 `matched_skills`。
- `runtime/tools.py`：新增 `learn_skill(name, description, triggers, playbook)` 工具，写 manifest 并注册到内存。
- `skills/` 目录：每个 skill 一个子目录，内含 `manifest.json`。

## 复现命令

```
# 查看已加载 skill
python -c "from runtime.skills import skill_registry; print([s.name for s in skill_registry.all_skills])"

# 全量回归（含 task_016 自进化验证）
python bench.py --mock --reset-memory

# 热插拔：放一个 manifest 后 reload
python -c "from runtime.skills import skill_registry; print(skill_registry.reload())"
```

## 任务

- `task_016`（新增）：让 Agent 调用 `learn_skill` 创建 `json_config_handler` 技能，验证 manifest 落盘且包含指定字段。

## 结果

### Mock 验证（已完成）

| 项目 | 结果 |
|---|---|
| 全量 16 任务 Mock 回归 | 16/16 通过，0 tokens，0.3s |
| skill 匹配注入 | task_001 命中 `csv_sum`，轨迹 `matched_skills: ["csv_sum"]` |
| 自进化落盘 | task_016 调用 `learn_skill`，`skills/json_config_handler/manifest.json` 生成且字段正确 |
| 热插拔 | 手动放 manifest 后 `reload()` 立即可见 |
| 启用/禁用 | `disable(name)` 后匹配结果排除该 skill，`enable(name)` 恢复 |

数据来源：`logs/bench_full_20261115_214634.csv`、`logs/20261115_214422_task_001_r1.jsonl`。

**自进化产物**（`skills/json_config_handler/manifest.json`）：
```json
{
  "name": "json_config_handler",
  "description": "读取 JSON 配置并提取或换算字段",
  "triggers": ["json", "config", "配置"],
  "playbook": "1. 用 read_file 读取 JSON 配置文件\n2. 解析目标字段\n3. 按要求换算或提取后写出结果"
}
```

### 真实模型对比（待补）

> 火山方舟额度受限，真实数据待补。计划：
> - 有 skill vs 无 skill，跑 task_001（csv 求和）各 3 次，对比步数和成功率。
> - 验证 Agent 是否会主动调用 `learn_skill` 沉淀成功经验。

## 结论

1. **Skill 注入链路跑通**：manifest 被正确加载，按触发词匹配后 playbook 追加到系统提示，轨迹可查 `matched_skills`。
2. **自进化闭环验证**：`learn_skill` 工具能把 Agent 产出的打法写成 manifest 落盘，并立即注册到内存供后续任务匹配。
3. **热插拔可用**：`reload()` 重新扫描目录，新增/删除 skill 无需重启进程；`enable/disable` 可运行时切换。
4. **Mock 覆盖全链路**：16 任务（含自进化任务）零额度通过，每次改动后可立即回归。

## 局限

- 触发词匹配是简单的子串包含，没有语义相似度，容易误匹配（如 "md" 可能命中无关任务）。
- playbook 是纯文本提示，没有结构化的「前置条件/步骤/后置验证」，模型遵守率依赖自身能力。
- 没有 skill 执行成功率统计和自动淘汰机制，劣质 skill 会一直留在库里。
- 自进化完全依赖 Agent 主动调用 `learn_skill`，没有「任务成功后自动提炼」的后台机制。
- 真实模型是否会参照 playbook（而不是自己摸索），需要真实数据验证。
