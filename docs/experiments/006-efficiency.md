# 006 · 端到端效率度量（token 成本 / P50·P95 延迟）

## 目的

前面几篇实验只回答了「效果」（通过率、步数），没有回答「效率」：同样通过一个任务，不同上下文策略要花多少 token、多长时间。这篇把效率指标固定下来，避免只用单一指标下结论。

## 方法

`stats.py` 汇总 `logs/bench_*.csv`（每次 bench 一行），按策略分组统计：

- 通过率、平均步数：全部运行
- 平均 tokens、P50 / P95 延迟：只统计真实模型运行（`prompt_tokens > 0`），Mock 回归的 elapsed≈0 会污染分位数，已排除
- 成本：需传入单价（`--price-in/--price-out`，元/百万 tokens），脚本不内置价格

```powershell
D:\Trae-CN\tools\python\python.exe stats.py --markdown
```

## 结果（截至 2026-11-16，logs/ 全量）

| 策略 | 运行数 | 通过率 | 平均步数 | 真实模型样本 | 平均 tokens | P50 延迟(s) | P95 延迟(s) |
|---|---|---|---|---|---|---|---|
| full | 164 | 91% | 3.0 | 29 | 5510 | 10.0 | 19.0 |
| state_card | 23 | 100% | 3.9 | 8 | 11547 | 11.9 | 18.5 |
| summary | 4 | 100% | 4.8 | 2 | 13958 | 167.1 | 192.6 |
| window | 17 | 100% | 3.4 | 2 | 12753 | 14.9 | 18.0 |
| unknown（早期无 strategy 列） | 30 | 93% | 4.3 | 30 | 3505 | 7.7 | 13.5 |

## 结论

1. **P95 比 P50 更能反映体验**：`full` 的 P50 是 10.0 s，但 P95 到 19.0 s，说明少数长任务（多步 + 大输入）才是延迟主要来源。
2. **summary 的代价在延迟不在 token**：它的平均 tokens 与 state_card 同量级（13958 vs 11547），但 P50 延迟 167 s，是 full 的 16 倍，与 001 中「摘要策略耗时涨 14 倍」的结论一致。
3. **token 与延迟不是同向指标**：state_card 省 token（相对同长度对话），但因为多一步压缩计算，延迟略高于 full，做取舍时要明确优化目标。

## 局限

- `summary` / `window` 的真实模型样本各只有 2 个，P50 噪声大，只能说明方向
- 延迟含公网调用抖动，同一策略跨时段会有波动；跨策略比较应尽量在同一时段跑
- 成本字段默认 0，需要按当期官网价格传入单价才是有效数字

## 复现

```powershell
D:\Trae-CN\tools\python\python.exe stats.py --markdown
D:\Trae-CN\tools\python\python.exe stats.py --markdown --price-in <输入单价> --price-out <输出单价>
```
