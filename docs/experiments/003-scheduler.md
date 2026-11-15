# 实验 003：调度器（并行 + 失败预算）

## 目标

验证调度器两个能力确实生效：
1. **并行工具调用**：当模型输出 `actions` 数组时，多个独立工具能真正并发执行并合并结果，减少轮次。
2. **失败预算（FailureBudget）**：同签名调用连续失败 ≥ 阈值时，强制提示模型换方法，避免空转浪费步数。

## 实现

- `runtime/scheduler.py`：
  - `execute_parallel(calls, max_workers=4, timeout=30)`：用 `ThreadPoolExecutor` 并发执行工具，单调用超时 30s，异常/超时转为观察文本返回，不中断主循环。
  - `format_observations(calls, observations)`：把并行结果按输入顺序拼成编号列表。
  - `FailureBudget(max_repeat=2)`：以 `工具名+参数签名` 为 key 计数，连续失败达阈值返回提示，成功一次即重置。
- `runtime/agent.py`：解析到 `actions`（数组）时走 `execute_parallel`；单工具失败时调 `failure_budget.check`，返回提示追加到观察文本。

## 复现命令

```
# Mock 回归（零额度，覆盖并行 + 全链路）
python bench.py --mock --reset-memory

# 单任务并行验证
python run_task.py evals/tasks/task_015.json --mock

# 真实模型并行 vs 串行对比（待额度恢复后补跑）
python bench.py --reset-memory --tasks task_007,task_015 --repeat 3
```

## 任务

- `task_007`：并行读取 `inbox/quarter.md` 和 `inbox/tech.md`，取各自第一行标题。
- `task_015`：并行读取 `sales.csv` 和 `data/orders.csv`，求各自列总和后按 `sales,orders` 写入文件。

两个任务的两次读取互相独立，天然适合并行。

## 结果

### Mock 验证（已完成）

用 `MockLLMClient` 预设脚本跑全量 15 任务，四种上下文策略全部通过，**0 tokens 消耗**。

| 策略 | 通过 | 平均步数 | 备注 |
|---|---|---|---|
| full | 15/15 | 2.9 | 基线 |
| window (w=2) | 15/15 | 2.9 | 窗口截断 |
| state_card (w=2) | 15/15 | 2.9 | 状态卡压缩 |
| summary (w=1) | 15/15 | 2.9 | 摘要压缩 |

数据来源：`logs/bench_full_20261115_213739.csv`、`logs/bench_window_20261115_213852.csv`、`logs/bench_state_card_20261115_213851.csv`、`logs/bench_summary_20261115_213844.csv`。

**并行路径证据**（task_015 轨迹 `logs/20261115_213739_task_015_r1.jsonl`）：

```
step 1: tool="read_file,read_file"  parallel=true  call_count=2
        observation: 并行工具调用结果：
          1. read_file({'path': 'sales.csv'}) -> ...
          2. read_file({'path': 'data/orders.csv'}) -> ...
step 2: write_file out/two_sums.txt "1000,60.75"
step 3: finish
```

并行调用在第 1 步一次性拿到两个文件内容，第 2 步直接写结果，3 步完成。

**失败预算单元验证**（无 LLM 直接测）：
- 同签名连续失败 2 次 → `check` 返回"换方法"提示（`max_repeat=2`）。
- 失败 1 次后成功 1 次 → 计数重置，再次失败不触发提示。

### 真实模型对比（待补）

> 火山方舟 `doubao-seed-2-1-lite-260915` 触发 429（安全体验模式用量上限），真实对比数据待配额恢复后补跑。
> 计划：task_007、task_015 各跑 3 次，记录步数；并构造一个必失败的调用观察 FailureBudget 是否减少空转步数。

## 结论

1. **并行执行路径已跑通**：`actions` 数组被正确解析，`execute_parallel` 并发执行并按序合并，模型在下一步即可拿到所有结果，无需串行多轮。
2. **失败预算能拦截重复失败**：同签名连续失败超阈值后强制注入"换方法"提示，成功自动重置，逻辑符合预期。
3. **Mock 让回归零成本**：`MockLLMClient` 用预设脚本替代真实模型，15 任务 × 4 策略全量回归 0 tokens、0.3s，可在每次代码改动后立即跑，不再受额度限制。

## 局限

- 并行度固定 `max_workers=4`，没有按工具类型做资源隔离（如 `run_python` 和 `http_get` 混跑可能互相影响）。
- 失败预算只看调用签名，不看失败原因——同样是读文件失败，"文件不存在"和"权限不足"应区别处理。
- 真实模型是否会主动选择并行（而不是每次只输出一个 `action`），需要真实数据验证；lite 模型可能倾向于保守串行。
- Mock 脚本是写死的正确路径，无法暴露模型在真实场景下的决策错误，仅用于验证运行时链路。
