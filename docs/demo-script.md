# 录屏演示脚本（30 秒）

## 准备

1. 打开一个终端窗口（在 `D:\Trae-CN\agent-runtime-lab` 地址栏输入 `cmd` 回车）
2. 打开文件资源管理器，导航到 `D:\Trae-CN\agent-runtime-lab`
3. 打开屏幕录制工具（Windows 自带：Win + G，或 OBS）

## 录制内容（按顺序操作）

### 第 1 段：展示项目结构（5 秒）

在文件资源管理器里展开 `runtime/` 目录，让观众看到：
- `agent.py`（主循环）
- `context.py` / `memory.py` / `scheduler.py` / `skills.py`（四大模块）
- `tools.py`（7 个工具）

同时可以快速展开 `skills/` 目录，展示 4 个 skill 子目录。

### 第 2 段：跑一个任务（10 秒）

在终端输入（用 Mock 模式，保证秒出结果不卡）：

```
D:\Trae-CN\tools\python\python.exe run_task.py evals\tasks\task_015.json --mock
```

等输出出现：
```
任务：task_015
结果：通过（包含全部 2 项）
步数：3  耗时：0.0s  tokens：0 + 0
```

**旁白要点**：这个任务要求并行读取两个 CSV 求和，3 步完成，0 tokens（Mock 模式）。

### 第 3 段：展示轨迹日志（10 秒）

在文件资源管理器里打开最新的 `logs/*task_015*.jsonl`（用记事本或 VS Code），展示：

```json
{"event": "start", "matched_skills": ["csv_sum"], ...}
{"event": "step", "step": 1, "tool": "read_file,read_file", "parallel": true, "call_count": 2, ...}
{"event": "step", "step": 2, "tool": "write_file", ...}
{"event": "finish", "step": 3, "ok": true, ...}
```

**旁白要点**：
- 第 1 步 `parallel: true, call_count: 2` — 两个文件并行读取
- `matched_skills: ["csv_sum"]` — Skill 自动匹配并注入
- 每一步的 thought / tool / args / observation 都有记录

### 第 4 段：展示实验结果（5 秒）

打开 `docs/experiments/` 目录，快速滚动展示 4 个实验记录文件。或者打开 `README.md` 展示核心结果表格。

**旁白要点**：每个模块都有对照实验，数字全部来自 `logs/` 里的真实运行记录。

## 录制建议

- 用 Mock 模式跑，保证流畅不卡（真实 API 可能 429）
- 终端字体调大一点（方便看清）
- 全程控制在 30-45 秒，面试官没耐心看长视频
- 录完后可以用剪映/CapCut 加个标题和简单转场

## 如果想录真实 API 版本

等额度恢复后，去掉 `--mock` 参数跑 `task_001`，能看到真实的 token 消耗和模型回复。但有 429 风险，建议 Mock 版为主、真实版为辅。
