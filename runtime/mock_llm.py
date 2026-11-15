"""Mock LLM 客户端：用预设脚本替代真实模型，零额度消耗地跑通全链路。

用法：
    client = MockLLMClient()
    agent = Agent(client, tracer, ...)
    agent.run(task_prompt)
"""

from __future__ import annotations

import json
import time


# 每个任务的脚本：按顺序返回的模型回复（JSON 字符串）。
# 脚本会真正调用工具，覆盖 read/write/list/run_python/remember/并行 等路径。
SCRIPTS: dict[str, list[str]] = {
    "task_001": [
        json.dumps({"thought": "读取 sales.csv 查看 total 列", "action": {"tool": "read_file", "args": {"path": "sales.csv"}}}),
        json.dumps({"thought": "total 列总和是 1000，写入 out/total.txt", "action": {"tool": "write_file", "args": {"path": "out/total.txt", "content": "1000"}}}),
        json.dumps({"thought": "已写入 1000", "finish": {"answer": "1000"}}),
    ],
    "task_002": [
        json.dumps({"thought": "读取 notes.md 统计列表项", "action": {"tool": "read_file", "args": {"path": "notes.md"}}}),
        json.dumps({"thought": "有 6 行以 - 开头，写入 out/line_count.txt", "action": {"tool": "write_file", "args": {"path": "out/line_count.txt", "content": "6"}}}),
        json.dumps({"thought": "已写入 6", "finish": {"answer": "6"}}),
    ],
    "task_003": [
        json.dumps({"thought": "读取 data/orders.csv 求 amount 总和", "action": {"tool": "read_file", "args": {"path": "data/orders.csv"}}}),
        json.dumps({"thought": "amount 总和是 60.75，写入 out/orders_total.txt", "action": {"tool": "write_file", "args": {"path": "out/orders_total.txt", "content": "60.75"}}}),
        json.dumps({"thought": "已写入 60.75", "finish": {"answer": "60.75"}}),
    ],
    "task_004": [
        json.dumps({"thought": "列出所有 csv 文件", "action": {"tool": "list_files", "args": {"pattern": "**/*.csv"}}}),
        json.dumps({"thought": "把 csv 文件名写到 out/csv_files.txt", "action": {"tool": "write_file", "args": {"path": "out/csv_files.txt", "content": "sales.csv\norders.csv\nraw.csv"}}}),
        json.dumps({"thought": "已写入所有 csv 文件名", "finish": {"answer": "sales.csv, orders.csv, raw.csv"}}),
    ],
    "task_005": [
        json.dumps({"thought": "读取 config.json 取 retries", "action": {"tool": "read_file", "args": {"path": "config.json"}}}),
        json.dumps({"thought": "retries=3，乘以 2 得 6，写入 out/retries.txt", "action": {"tool": "write_file", "args": {"path": "out/retries.txt", "content": "6"}}}),
        json.dumps({"thought": "已写入 6", "finish": {"answer": "6"}}),
    ],
    "task_006": [
        json.dumps({"thought": "用 run_python 计算 1 到 100 的和", "action": {"tool": "run_python", "args": {"code": "print(sum(range(1, 101)))"}}}),
        json.dumps({"thought": "结果是 5050，写入 out/sum100.txt", "action": {"tool": "write_file", "args": {"path": "out/sum100.txt", "content": "5050"}}}),
        json.dumps({"thought": "已写入 5050", "finish": {"answer": "5050"}}),
    ],
    "task_007": [
        json.dumps({"thought": "两个文件互相独立，并行读取", "actions": [{"tool": "read_file", "args": {"path": "inbox/quarter.md"}}, {"tool": "read_file", "args": {"path": "inbox/tech.md"}}]}),
        json.dumps({"thought": "两个标题分别是季度复盘和技术方案，写入 out/titles.txt", "action": {"tool": "write_file", "args": {"path": "out/titles.txt", "content": "季度复盘\n技术方案"}}}),
        json.dumps({"thought": "已写入两个标题", "finish": {"answer": "季度复盘, 技术方案"}}),
    ],
    "task_008": [
        json.dumps({"thought": "读取 data/raw.csv 去重统计行数", "action": {"tool": "read_file", "args": {"path": "data/raw.csv"}}}),
        json.dumps({"thought": "去重空行后剩 3 行，写入 out/dedup_count.txt", "action": {"tool": "write_file", "args": {"path": "out/dedup_count.txt", "content": "3"}}}),
        json.dumps({"thought": "已写入 3", "finish": {"answer": "3"}}),
    ],
    "task_009": [
        json.dumps({"thought": "读取 config.json 取 timeout", "action": {"tool": "read_file", "args": {"path": "config.json"}}}),
        json.dumps({"thought": "timeout=30 分钟，乘以 60 得 1800 秒，写入 out/timeout_seconds.txt", "action": {"tool": "write_file", "args": {"path": "out/timeout_seconds.txt", "content": "1800"}}}),
        json.dumps({"thought": "已写入 1800", "finish": {"answer": "1800"}}),
    ],
    "task_010": [
        json.dumps({"thought": "列出 data 目录下的 csv 文件", "action": {"tool": "list_files", "args": {"pattern": "data/*.csv"}}}),
        json.dumps({"thought": "把文件名写到 out/data_csv.txt", "action": {"tool": "write_file", "args": {"path": "out/data_csv.txt", "content": "orders.csv\nraw.csv"}}}),
        json.dumps({"thought": "已写入 data 目录下的 csv 文件名", "finish": {"answer": "orders.csv, raw.csv"}}),
    ],
    "task_011": [
        json.dumps({"thought": "读取 reports/quarterly.md 找风险点", "action": {"tool": "read_file", "args": {"path": "reports/quarterly.md"}}}),
        json.dumps({"thought": "三个风险是数据合规、模型幻觉、成本失控，写入 out/risks.txt", "action": {"tool": "write_file", "args": {"path": "out/risks.txt", "content": "数据合规\n模型幻觉\n成本失控"}}}),
        json.dumps({"thought": "已写入三个风险点", "finish": {"answer": "数据合规, 模型幻觉, 成本失控"}}),
    ],
    "task_012": [
        json.dumps({"thought": "读取 reports/quarterly.md 找优先风险", "action": {"tool": "read_file", "args": {"path": "reports/quarterly.md"}}}),
        json.dumps({"thought": "建议优先处理数据合规，写入 out/priority.txt", "action": {"tool": "write_file", "args": {"path": "out/priority.txt", "content": "数据合规"}}}),
        json.dumps({"thought": "已写入数据合规", "finish": {"answer": "数据合规"}}),
    ],
    "task_013": [
        json.dumps({"thought": "把项目代号 Phoenix 写入长期记忆", "action": {"tool": "remember", "args": {"content": "项目代号是 Phoenix"}}}),
        json.dumps({"thought": "已写入记忆", "finish": {"answer": "已记住项目代号是 Phoenix"}}),
    ],
    "task_014": [
        json.dumps({"thought": "从长期记忆知道代号是 Phoenix，写入 out/codename.txt", "action": {"tool": "write_file", "args": {"path": "out/codename.txt", "content": "Phoenix"}}}),
        json.dumps({"thought": "读回确认", "action": {"tool": "read_file", "args": {"path": "out/codename.txt"}}}),
        json.dumps({"thought": "确认是 Phoenix", "finish": {"answer": "Phoenix"}}),
    ],
    "task_015": [
        json.dumps({"thought": "两个文件读取互相独立，并行执行", "actions": [{"tool": "read_file", "args": {"path": "sales.csv"}}, {"tool": "read_file", "args": {"path": "data/orders.csv"}}]}),
        json.dumps({"thought": "sales 总和 1000，orders 总和 60.75，写入 out/two_sums.txt", "action": {"tool": "write_file", "args": {"path": "out/two_sums.txt", "content": "1000,60.75"}}}),
        json.dumps({"thought": "已写入两个和", "finish": {"answer": "1000,60.75"}}),
    ],
    "task_016": [
        json.dumps({"thought": "用 learn_skill 把 JSON 配置处理打法沉淀为技能", "action": {"tool": "learn_skill", "args": {"name": "json_config_handler", "description": "读取 JSON 配置并提取或换算字段", "triggers": "json,config,配置", "playbook": "1. 用 read_file 读取 JSON 配置文件\n2. 解析目标字段\n3. 按要求换算或提取后写出结果"}}}),
        json.dumps({"thought": "技能已创建", "finish": {"answer": "已创建 json_config_handler 技能"}}),
    ],
    "task_017": [
        json.dumps({"thought": "并行读取两个 CSV 文件", "actions": [
            {"tool": "read_file", "args": {"path": "sales.csv"}},
            {"tool": "read_file", "args": {"path": "data/orders.csv"}},
        ]}),
        json.dumps({"thought": "计算两个文件的总额并生成 markdown 报告", "action": {"tool": "run_python", "args": {"code": "sales=1000.0\norders=60.75\nmd='''# 销售报告\\n\\n| 数据源 | 总额 |\\n|---|---|\\n| sales | 1000.0 |\\n| orders | 60.75 |\\n| 合计 | 1060.75 |\\n'''\nopen('out/sales_report.md','w',encoding='utf-8').write(md)\nprint('done')"}}}),
        json.dumps({"thought": "报告已生成", "finish": {"answer": "已生成 sales_report.md"}}),
    ],
    "task_018": [
        json.dumps({"thought": "读取季度报告提取风险", "action": {"tool": "read_file", "args": {"path": "reports/quarterly.md"}}}),
        json.dumps({"thought": "按严重程度排序并写入 risks.md", "action": {"tool": "write_file", "args": {"path": "out/risks.md", "content": "1. 数据合规\\n2. 模型幻觉\\n3. 成本失控\\n"}}}),
        json.dumps({"thought": "风险清单已生成", "finish": {"answer": "已生成 risks.md"}}),
    ],
    "task_019": [
        json.dumps({"thought": "读取 config.json 和 notes.md", "actions": [
            {"tool": "read_file", "args": {"path": "config.json"}},
            {"tool": "read_file", "args": {"path": "notes.md"}},
        ]}),
        json.dumps({"thought": "生成配置摘要", "action": {"tool": "write_file", "args": {"path": "out/config_summary.md", "content": "# 配置摘要\\n\\n- retries: 3\\n- timeout: 30\\n- notes 条目数量: 6\\n"}}}),
        json.dumps({"thought": "摘要已生成", "finish": {"answer": "已生成 config_summary.md"}}),
    ],
}


# 任务匹配关键词（出现在用户消息里即可）
_TASK_KEYWORDS: dict[str, str] = {
    "task_001": "out/total.txt",
    "task_002": "out/line_count.txt",
    "task_003": "out/orders_total.txt",
    "task_004": "out/csv_files.txt",
    "task_005": "out/retries.txt",
    "task_006": "out/sum100.txt",
    "task_007": "out/titles.txt",
    "task_008": "out/dedup_count.txt",
    "task_009": "out/timeout_seconds.txt",
    "task_010": "out/data_csv.txt",
    "task_011": "out/risks.txt",
    "task_012": "out/priority.txt",
    "task_013": "写入长期记忆",
    "task_014": "out/codename.txt",
    "task_015": "out/two_sums.txt",
    "task_016": "json_config_handler",
    "task_017": "sales_report.md",
    "task_018": "risks.md",
    "task_019": "config_summary.md",
}


def _is_summary_call(messages: list[dict]) -> bool:
    """判断这次调用是不是上下文压缩摘要请求。"""
    for message in messages:
        if message.get("role") == "system" and "压缩成不超过 200 字" in message.get("content", ""):
            return True
    return False


def _match_task(messages: list[dict]) -> str:
    """从消息里的用户文本匹配任务 id。"""
    for message in messages:
        if message.get("role") != "user":
            continue
        text = message.get("content", "")
        for task_id, keyword in _TASK_KEYWORDS.items():
            if keyword in text:
                return task_id
    return "unknown"


class MockLLMClient:
    """预设脚本的假模型，不消耗任何 API 额度。"""

    model_id = "mock-scripted"

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def chat(self, messages: list[dict]) -> dict:
        started = time.perf_counter()

        # 摘要压缩调用：返回一个固定的简短摘要，不走任务脚本
        if _is_summary_call(messages):
            return {
                "content": "已完成若干步骤的工具调用并获得观察结果，正在继续推进任务。",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                "latency_ms": (time.perf_counter() - started) * 1000,
            }

        task_id = _match_task(messages)
        script = SCRIPTS.get(task_id)
        assistant_count = sum(1 for m in messages if m.get("role") == "assistant")

        # 第一轮（还没有 assistant 回复）重置该任务的步骤计数器
        if assistant_count == 0:
            self._counters[task_id] = 0

        idx = self._counters.get(task_id, 0)

        if not script or idx >= len(script):
            content = json.dumps({"thought": "脚本结束", "finish": {"answer": "(mock 脚本越界)"}})
        else:
            content = script[idx]

        self._counters[task_id] = idx + 1
        return {
            "content": content,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "latency_ms": (time.perf_counter() - started) * 1000,
        }
