"""汇总 logs/bench_*.csv，输出端到端效果与效率指标（通过率 / 步数 / token / P50·P95 延迟）。

用法：
    python stats.py                # 按策略汇总
    python stats.py --markdown     # 输出 markdown 表格，便于贴到实验记录
    python stats.py --price-in 0.8 --price-out 2.0   # 单价（元/百万 tokens），可选

说明：
- token 与延迟来自真实模型运行的日志；Mock 回归行的 token 为 0，会被单独计入样本但不参与 token 均值。
- 成本 = prompt_tokens × 输入单价 + completion_tokens × 输出单价，单价需自行传入，脚本不内置价格以免过期。
"""

from __future__ import annotations

import argparse
import csv
import glob
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(glob.glob(str(LOGS / "bench_*.csv"))):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["_file"] = Path(path).name
                rows.append(row)
    return rows


def summarize(rows: list[dict], price_in: float, price_out: float) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.get("strategy") or "unknown"].append(row)

    out = []
    for strategy, items in sorted(grouped.items()):
        passed = sum(1 for r in items if r.get("passed") == "True")
        steps = [float(r["steps"]) for r in items if r.get("steps")]
        real = [r for r in items if int(float(r.get("prompt_tokens") or 0)) > 0]
        # 延迟只统计真实模型运行，Mock 回归的 elapsed 接近 0 会污染分位数
        latency = [float(r["elapsed_s"]) for r in real if float(r.get("elapsed_s") or 0) > 0]
        tokens = [
            int(float(r["prompt_tokens"])) + int(float(r["completion_tokens"])) for r in real
        ]
        cost = sum(
            (int(float(r["prompt_tokens"])) * price_in
             + int(float(r["completion_tokens"])) * price_out) / 1_000_000
            for r in real
        )
        out.append(
            {
                "strategy": strategy,
                "runs": len(items),
                "pass_rate": passed / len(items) if items else 0.0,
                "avg_steps": statistics.fmean(steps) if steps else 0.0,
                "real_runs": len(real),
                "avg_tokens": statistics.fmean(tokens) if tokens else 0.0,
                "p50_s": percentile(latency, 0.50) if latency else 0.0,
                "p95_s": percentile(latency, 0.95) if latency else 0.0,
                "cost": cost,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="汇总 bench CSV 的效果与效率指标")
    parser.add_argument("--markdown", action="store_true", help="输出 markdown 表格")
    parser.add_argument("--price-in", type=float, default=0.0, help="输入单价（元/百万 tokens）")
    parser.add_argument("--price-out", type=float, default=0.0, help="输出单价（元/百万 tokens）")
    args = parser.parse_args()

    rows = load_rows()
    if not rows:
        print("没有找到 logs/bench_*.csv，先跑一次 bench.py")
        return

    table = summarize(rows, args.price_in, args.price_out)
    if args.markdown:
        print("| 策略 | 运行数 | 通过率 | 平均步数 | 真实模型样本 | 平均 tokens | P50 延迟(s) | P95 延迟(s) | 估算成本(元) |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in table:
            print(
                f"| {r['strategy']} | {r['runs']} | {r['pass_rate']:.0%} | {r['avg_steps']:.1f} | "
                f"{r['real_runs']} | {r['avg_tokens']:.0f} | {r['p50_s']:.1f} | {r['p95_s']:.1f} | {r['cost']:.4f} |"
            )
    else:
        for r in table:
            print(
                f"[{r['strategy']}] 运行 {r['runs']} 次，通过率 {r['pass_rate']:.0%}，"
                f"平均 {r['avg_steps']:.1f} 步；真实模型 {r['real_runs']} 次，"
                f"平均 {r['avg_tokens']:.0f} tokens，P50 {r['p50_s']:.1f}s / P95 {r['p95_s']:.1f}s"
            )


if __name__ == "__main__":
    main()
