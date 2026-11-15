# agent-runtime-lab

一个自带评测与消融实验的通用任务型 Agent 运行时：可插拔 Skill、三层记忆、上下文预算压缩、可解释的调度与失败归因。

[English README](README.md)

## 目标

用可复现的实验数字回答三个问题：

1. 上下文压缩到什么程度会开始丢关键约束？
2. 三层记忆在什么任务上真正带来收益，什么任务上纯属负担？
3. Skill 规模扩大后，按需加载与自进化各贡献多少？

所有结论只来自 `logs/` 里的真实运行记录。

## 核心结果

| 模块 | 结论 | 证据 |
|---|---|---|
| **上下文压缩** | `state_card` 输入 token 降 **34%**，成功率不变，耗时仅 +18% | `docs/experiments/001-context-compression.md` |
| **三层记忆** | 有记忆 4/4 通过（2.5 步），无记忆 0/2 跑满 8 步 | `docs/experiments/002-memory.md` |
| **调度器** | 并行调用通路验证；失败预算连续 2 次失败后强制换方法 | `docs/experiments/003-scheduler.md` |
| **Skill** | manifest 按触发词注入；`learn_skill` 自进化写盘 | `docs/experiments/004-skills.md` |

## 快速开始

```powershell
# 1. 按提示粘贴 API Key 与模型 ID（自动写入 .env）
D:\Trae-CN\tools\python\python.exe scripts\set_key.py

# 2. 连通性自检
D:\Trae-CN\tools\python\python.exe scripts\smoke_ark.py

# 3. 跑单个任务
D:\Trae-CN\tools\python\python.exe run_task.py evals\tasks\task_001.json

# 4. 跑全量基准（16 个任务）
D:\Trae-CN\tools\python\python.exe bench.py --reset-memory
```

Python 使用便携版，路径为 `D:\Trae-CN\tools\python\python.exe`，不依赖系统 PATH。

## 零额度回归

所有任务支持 `--mock` 模式，用预设脚本替代真实模型，跑通全链路不消耗 API 额度：

```powershell
D:\Trae-CN\tools\python\python.exe bench.py --mock --reset-memory
# → 16/16 通过，0 tokens，0.3s
```

每次代码改动后先跑 Mock 回归，只有做效果实验时才调真实 API。

## 状态

- [x] P0：主循环 + 7 个工具 + 轨迹日志 + 16 个任务 + 基准表
- [x] P1：上下文压缩（full/window/state_card/summary）、三层记忆、调度器（并行 + 失败预算）
- [x] P2：Skill 体系（manifest + 热插拔 + 自进化 learn_skill）
- [x] P3a：英文 README、博客、简历要点、录屏脚本
- [ ] P3b：Web 控制台
