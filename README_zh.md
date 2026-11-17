# agent-runtime-lab

一个自带评测与消融实验的通用任务型 Agent 运行时：可插拔 Skill、三层记忆、上下文预算压缩、可解释的调度与失败归因。

[English README](README.md)

## 目标

用可复现的实验数字回答三个问题：

1. 上下文压缩到什么程度会开始丢关键约束？
2. 三层记忆在什么任务上真正带来收益，什么任务上纯属负担？
3. Skill 规模扩大后，按需加载与自进化各贡献多少？

**所有结论都附带可复现的实验数据。** 真实模型跑批的 CSV 汇总在 [`docs/efficiency-data/`](docs/efficiency-data/)；每次运行自动重建的 mock 回归轨迹在 `logs/`（gitignore）。不拍脑袋。

## 核心结果

| 模块 | 结论 | 证据 |
|---|---|---|
| **上下文压缩** | `state_card` 输入 token 降 **34%**，自身 8 任务集成功率不掉，耗时仅 +18% | `docs/experiments/001-context-compression.md` |
| **三层记忆** | 有记忆 4/4 通过（2.5 步），无记忆 0/2 跑满 8 步 | `docs/experiments/002-memory.md` |
| **调度器** | 并行调用通路验证；失败预算连续 2 次失败后强制换方法 | `docs/experiments/003-scheduler.md` |
| **Skill** | manifest 按触发词注入；`learn_skill` 自进化写盘 | `docs/experiments/004-skills.md` |
| **进度跟踪** | 每步记录「已完成/下一步」注入系统提示（参考字节 Aime 论文） | `docs/experiments/005-advanced.md` |
| **断点续跑** | 任务中断后用 `--resume` 从断点继续 | `docs/experiments/005-advanced.md` |
| **Skill 健康度** | 成功率 < 30% 且样本 >= 3 的 skill 自动禁用 | `docs/experiments/005-advanced.md` |
| **向量记忆** | 字符 n-gram + 余弦相似度检索最相关事实 | `docs/experiments/005-advanced.md` |
| **插件注册表** | 在 `plugins/` 下放一个文件夹即可作为新工具被主循环调用 | `runtime/plugins.py`, `plugins/word_count/` |
| **效率指标** | 29 次真实模型跑批：平均 5510 tokens/任务，P50 10.0s，P95 19.0s；`summary` 策略 P50 达 167s | `docs/efficiency-data/`, `stats.py`, `docs/experiments/006-efficiency.md` |

## 架构

```
run_task.py / bench.py
        |
        v
   Agent (ReAct loop)
        |
        +-- ContextManager   -> full / window / state_card / summary
        +-- MemoryStore      -> 短期工作记忆 / 情景记忆 / 长期事实（向量检索）
        +-- ProgressTracker  -> 每步进度状态（Aime 风格）
        +-- CheckpointManager-> 保存 / 恢复任务状态
        +-- SkillRegistry    -> 按触发词匹配，注入 playbook，健康度过滤，自进化
        +-- Scheduler        -> 并行执行 + 失败预算
        +-- PluginRegistry   -> 往 plugins/ 丢一个文件夹就能加工具
        +-- Tools            -> read_file / write_file / list_files / run_python / http_get / remember / learn_skill
```

## 效率指标

**数据来源严格区分：**

| 类型 | 位置 | 用途 |
|---|---|---|
| **真实模型证据** | [`docs/efficiency-data/`](docs/efficiency-data/) — 20 个 bench CSV + 汇总 | 测量 token/延迟、P50/P95，用于 README 里的数字 |
| **Mock 回归** | `logs/`（gitignore，每次运行重建） | 零额度冒烟测试 + CI 门禁 — 证明链路通，不代表模型效果 |

`stats.py` 聚合 `logs/bench_*.csv` 的数据。Mock 行（`prompt_tokens = 0`）不计入 token/延迟百分位，真实数据不被污染。

| 策略 | 运行次数 | 通过 | 真实样本 | 平均 token | P50 (s) | P95 (s) |
|---|---|---|---|---|---|---|
| full | 29 | **16/29 (55%)** | 29 | 5510 | 10.0 | 19.0 |
| state_card | 8 | 8/8 | 8 | 11547 | 11.9 | 18.5 |
| summary | 2 | 2/2 | 2 | 13958 | 167.1 | 192.6 |
| window | 2 | 2/2 | 2 | 12753 | 14.9 | 18.0 |

**坦诚说明：**
- 各策略在不同时间、不同任务子集上运行，通过率不能直接横比。
- `docs/experiments/001-context-compression.md` 中的消融实验让 `full` vs `state_card` 在**同一批 12 个任务**上对比 —— 那里才是「成功率不掉、token -34%」的来源，不是上表。
- 基线 `full` 通过率 16/29 (55%)；13 次失败集中在开放式写作任务（task_014）— 每任务分析见 `docs/experiments/005-advanced.md`。
- 真实验证跑了 29 次 full 策略样本后触发 `SetLimitExceeded`，`state_card` / `window` / `summary` 样本少 —— 已知缺口。

## 快速开始

任意 Python 3.10+ 均可。开发时用了便携版 Python（无系统 PATH 依赖），把下面的 python 替换成你的路径即可。

```powershell
# 1. 按提示粘贴 API Key 与模型 ID（自动写入 .env）
python scripts/set_key.py

# 2. 连通性自检
python scripts/smoke_ark.py

# 3. 跑单个任务
python run_task.py evals/tasks/task_001.json

# 4. 跑完整 19 任务评测
python bench.py --reset-memory
```

## 零额度回归

全部 19 个任务都支持 `--mock` 模式，用脚本化响应代替真实 LLM 调用 —— 全链路覆盖，**0 API token**：

```powershell
python bench.py --mock --reset-memory
# -> 19/19 通过，0 tokens，0.4s
```

每次改代码都先跑这个；真实 API 调用留给效果对比实验。

## 项目结构

```
runtime/
  agent.py        ReAct 主循环
  context.py      4 种上下文组装策略
  memory.py       三层记忆 + 向量检索
  progress.py     每步进度状态（Aime 风格）
  checkpoint.py   任务状态保存 / 恢复
  scheduler.py    并行执行 + FailureBudget
  skills.py       Skill 匹配、健康度、自进化
  plugins.py      插件注册表
  tools.py        7 个内置工具 + 插件
  llm.py          火山方舟（豆包）OpenAI 兼容客户端
  mock_llm.py     脚本化 mock LLM
  trace.py        每步 JSONL 轨迹日志
evals/tasks/      19 个自动判分任务
skills/           skill manifests
plugins/          工具插件
docs/efficiency-data/ 真实模型 bench CSV（20 个文件，71 行）
docs/experiments/ 实验记录与原始数字
docs/tech-survey.md  框架选型对比与自研决策
stats.py          从 bench CSV 算通过率 / 步数 / tokens / P50-P95
.github/workflows/mock-bench.yml   CI：每次 push 跑 mock 回归
```

## 状态

- [x] P0: ReAct 主循环 + 7 工具 + 轨迹日志 + 16 任务 + 基线
- [x] P1: 上下文压缩（4 策略）、三层记忆、调度器（并行 + 失败预算）
- [x] P2: Skill 体系（manifest + 热插拔 + `learn_skill` 自进化）
- [x] P3a: 英文 / 中文 README、博客、简历 bullet、演示脚本
- [ ] P3b: Web 控制台
