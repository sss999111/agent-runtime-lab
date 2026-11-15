# 实验 005：进度跟踪、断点续跑、Skill 健康度、向量记忆

## 背景

参考字节跳动 Aime 论文（arxiv 2507.11988）的 Progress Management 思路，以及 LangGraph 的 checkpointing 模式，补充四个工程能力：

1. **进度跟踪（Progress Tracking）**：每步记录「已完成/下一步」，注入系统提示
2. **断点续跑（Checkpoint/Resume）**：任务中断后可从断点继续
3. **Skill 健康度（Skill Health）**：成功率低于阈值的 skill 自动禁用
4. **向量记忆（Vector Memory）**：用字符 n-gram + 余弦相似度检索最相关事实

## 验证方式

全部用 Mock LLM 验证（0 tokens），确保不消耗 API 额度。

## 1. 进度跟踪

**实现**：`runtime/progress.py` 的 `ProgressTracker`，每步工具调用后记录操作和结果摘要，生成文本块注入系统提示。

**验证**：
- 19 个任务全部通过（Mock），进度块不影响执行结果
- 轨迹日志可观察到系统提示中包含「已完成」和「下一步计划」段落

**设计要点**：
- 只保留最近 8 步，避免进度块本身膨胀上下文
- 失败也记录（标注结果），避免重复试错
- 对齐 Aime 论文「全局状态视图」的思路，让 Agent 知道自己做到哪了

## 2. 断点续跑

**实现**：`runtime/checkpoint.py` 的 `CheckpointManager`，每步将 `task/step/turns/tokens` 存为 JSON。

**验证**：
- 第一次用 `--max-steps 1` 跑 task_017 → 失败，留下 checkpoint
- 第二次加 `--resume` → 从第 2 步继续，3 步后完成
- 成功后 checkpoint 自动清除

```
第1次(1步): ok=False steps=1
有 checkpoint: True
[resume] 从第 2 步继续，已有 1 步历史
第2次(resume): ok=True steps=4
checkpoint 已清除: True
```

**设计要点**：
- 失败时不清除 checkpoint（方便续跑），成功时才清除
- 文件名用任务文本的 hash，避免特殊字符
- 恢复时重建进度记录，进度块和首次执行一致

## 3. Skill 健康度

**实现**：`SkillRegistry` 增加 `record_outcome(names, success)`，统计每个 skill 的成功率，`match()` 时过滤掉成功率 < 30% 且样本 ≥ 3 的 skill。

**验证**：
- 手动设置 `markdown_extract` 为 3 次失败 → 成功率 0% → 匹配时被过滤
- 恢复为 3 次成功 → 成功率 100% → 重新匹配

```
markdown_extract 成功率: 0.0
markdown_extract 健康: False
匹配到的 skill: []
恢复后 成功率: 1.0 健康: True
匹配到的 skill: ['markdown_extract']
```

**当前统计**（来自 Mock 全量回归）：
- `csv_sum`: 27/32（84%）
- `config_reader`: 10/10（100%）
- `json_config_handler`: 10/10（100%）

## 4. 向量记忆

**实现**：`memory.py` 增加 `_char_ngrams()` 和 `_cosine_similarity()`，`build_block(task)` 时按事实与任务文本的余弦相似度排序，取 top-k。相似度全为 0 时退回最近 N 条。

**验证**：
- 三条事实：「项目代号是 Phoenix」「用户喜欢 markdown」「数据库超时 30 秒」
- 查询「把项目代号写到文件里」→ 只返回「项目代号是 Phoenix」（相似度 0.289，其余为 0）

```
sim(代号, 项目代号是 Phoenix): 0.289
sim(代号, 数据库超时): 0.0
```

**设计要点**：
- 用 n=2 字符 bigram（中文双字词更合理），不用 n=3
- 纯 Python 实现，不依赖 sentence-transformers 等重库
- 对短查询（如「代号」）也能匹配

## 5. 新增多步骤任务

| 任务 | 要求 | 步骤 |
|---|---|---|
| task_017 | 读两个 CSV 算总额，生成 markdown 表格报告 | 并行读 → run_python 计算写报告 |
| task_018 | 从 4800 字季度报告提取 3 个风险并排序 | 读文件 → 写 risks.md |
| task_019 | 读 config.json + notes.md，生成配置摘要 | 并行读 → 写 summary |

**验证**：3 个任务全部通过 Mock 回归。

## 全量回归

```
策略 full  任务 19 个  重复 1 次  模型 mock-scripted
通过 19/19  平均 2.9 步  平均输入 0 tokens  平均合计 0 tokens  总耗时 0.4s
```

## 待真实模型补充

- 进度跟踪对真实模型的步数影响（理论上减少重复劳动）
- 向量记忆在长期事实增多后的检索准确率
- Skill 健康度在真实失败场景下的过滤效果
