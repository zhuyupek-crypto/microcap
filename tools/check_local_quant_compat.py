#!/usr/bin/env python3
"""
微盘股策略 → local_quant 兼容性预检脚本。

使用 AST 分析策略源码提取依赖，并与 local_quant 框架的实际暴露 API 对比。
输出控制台表格和可选 JSON 结果文件。

退出码：
  0 — 全部关键依赖满足（无 MISSING 或关键 PARTIAL）
  2 — 存在 MISSING 或关键 PARTIAL
  1 — 脚本自身错误
"""

import argparse
import ast
import json
import os
import sys
import hashlib
from pathlib import Path


# ─── 已知的聚宽 API / 字段 / 查询表 ──────────────────────────────────────

KNOWN_JQ_CONFIG_API = [
    "set_benchmark",
    "set_option",
    "set_slippage",
    "FixedSlippage",
    "set_order_cost",
    "OrderCost",
    "run_daily",
]

KNOWN_JQ_DATA_API = [
    "get_all_securities",
    "get_extras",
    "get_price",
    "get_fundamentals",
    "get_current_data",
]

KNOWN_JQ_TRADE_API = [
    "order_target",
    "order_target_value",
]

KNOWN_JQ_CONTEXT_ATTRS = [
    "context.current_dt",
    "context.previous_date",
    "context.portfolio.positions",
    "context.portfolio.total_value",
    "context.portfolio.available_cash",
]

KNOWN_JQ_POSITION_ATTRS = [
    "position.value",
    "position.total_amount",
    "position.closeable_amount",
    "position.price",
    "position.avg_cost",
]

KNOWN_JQ_CURRENT_DATA_FIELDS = [
    "current_data.paused",
    "current_data.is_st",
    "current_data.last_price",
    "current_data.high_limit",
    "current_data.low_limit",
]

KNOWN_JQ_QUERY_TABLES = [
    "valuation.code",
    "valuation.market_cap",
    "indicator.roe",
    "cash_flow.net_operate_cash_flow",
    "balance.total_liability",
    "balance.total_assets",
]

KNOWN_JQ_OTHERS = [
    "log.info",
    "log.warn",
    "log.warning",
]

KNOWN_JQ_ALL = set(
    KNOWN_JQ_CONFIG_API
    + KNOWN_JQ_DATA_API
    + KNOWN_JQ_TRADE_API
    + KNOWN_JQ_CONTEXT_ATTRS
    + KNOWN_JQ_POSITION_ATTRS
    + KNOWN_JQ_CURRENT_DATA_FIELDS
    + KNOWN_JQ_QUERY_TABLES
    + KNOWN_JQ_OTHERS
)

# ─── 依赖严重等级 ──────────────────────────────────────────────────────

CRITICAL_APIS = {
    "get_all_securities",
    "get_extras",
    "get_price",
    "get_fundamentals",
    "get_current_data",
    "order_target_value",
    "order_target",
    "run_daily",
    "context.current_dt",
    "context.previous_date",
    "context.portfolio.positions",
    "context.portfolio.total_value",
    "position.value",
    "current_data.last_price",
    "current_data.high_limit",
    "current_data.low_limit",
    "current_data.paused",
    "current_data.is_st",
    "valuation.code",
    "valuation.market_cap",
    "indicator.roe",
    "cash_flow.net_operate_cash_flow",
    "balance.total_liability",
    "balance.total_assets",
    "log.info",
    "log.warn",
    "set_order_cost",
    "OrderCost",
    "set_slippage",
    "FixedSlippage",
    "set_benchmark",
    "set_option",
}

# ─── AST 提取策略依赖 ─────────────────────────────────────────────────


def extract_dependencies_from_source(source_path):
    """使用 AST 分析策略源码，提取使用的 API、属性等。"""
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    deps = set()

    for node in ast.walk(tree):
        # 函数调用: func(...)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                deps.add(func.id)
            elif isinstance(func, ast.Attribute):
                parts = []
                curr = func
                while isinstance(curr, ast.Attribute):
                    parts.append(curr.attr)
                    curr = curr.value
                if isinstance(curr, ast.Name):
                    parts.append(curr.id)
                else:
                    parts.append("<expr>")
                deps.add(".".join(reversed(parts)))

        # 属性访问: a.b.c
        if isinstance(node, ast.Attribute):
            parts = []
            curr = node
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
                deps.add(".".join(reversed(parts)))

        # 名称 (变量/函数引用)
        if isinstance(node, ast.Name):
            # 只记录顶级名称，避免过多噪声
            if isinstance(node.ctx, (ast.Load, ast.Store)):
                pass  # 所有名称都会在 Call/Attribute 中被捕获

    return deps


def match_deps_to_known(deps_set):
    """将提取的依赖匹配到已知 API 列表。"""
    matched = set()
    for dep in deps_set:
        # 精确匹配
        if dep in KNOWN_JQ_ALL:
            matched.add(dep)
        else:
            # 部分匹配：如 "valuation" 匹配 "valuation.code"
            for known in KNOWN_JQ_ALL:
                if dep == known or known.startswith(dep + ".") or dep.startswith(known):
                    matched.add(known)
    return matched


# ─── local_quant 覆盖检查 ─────────────────────────────────────────────


def check_local_quant_coverage(local_quant_path):
    """
    检查 local_quant 中每个已知 API 的覆盖情况。
    返回 {api_name: {"status": str, "file": str, "line": int, "evidence": str}}
    """
    cov = {}
    lq = Path(local_quant_path)
    engine_dir = lq / "engine"

    # 构建文件名 → 全文 映射
    file_texts = {}
    for py_file in engine_dir.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                file_texts[py_file.relative_to(lq)] = f.read()
        except Exception:
            pass

    core_text = file_texts.get(Path("engine/core.py"), "")
    data_api_text = file_texts.get(Path("engine/data_api.py"), "")
    context_text = file_texts.get(Path("engine/context.py"), "")
    order_text = file_texts.get(Path("engine/order.py"), "")

    def _find_in_text(text, keyword):
        """查找 keyword 在 text 中的位置，返回 (行号, 上下文行)。"""
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if keyword in line:
                return i + 1, line.strip()
        return None, None

    # ── 配置/调度 ──
    for api in KNOWN_JQ_CONFIG_API:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}

        if api == "FixedSlippage":
            line, ctx = _find_in_text(order_text, "class FixedSlippage")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/order.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "OrderCost":
            line, ctx = _find_in_text(order_text, "class OrderCost")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/order.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "set_slippage":
            line, ctx = _find_in_text(core_text, "def set_slippage")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "set_order_cost":
            line, ctx = _find_in_text(core_text, "def set_order_cost")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "set_benchmark":
            line, ctx = _find_in_text(core_text, "set_benchmark")
            if line:
                info["status"] = "PARTIAL"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = "lambda x: None (no-op)"

        elif api == "set_option":
            line, ctx = _find_in_text(core_text, "def set_option")
            if line:
                # 检查是否只处理 order_volume_ratio
                if "order_volume_ratio" in (ctx or ""):
                    info["status"] = "PARTIAL"
                    info["evidence"] = "only processes order_volume_ratio key"
                else:
                    line2, ctx2 = _find_in_text(core_text, "order_volume_ratio")
                    if line2:
                        info["status"] = "PARTIAL"
                        info["evidence"] = "only processes order_volume_ratio key (line %d)" % line2
                    else:
                        info["status"] = "PARTIAL"
                info["file"] = "engine/core.py"
                info["line"] = line

        elif api == "run_daily":
            line, ctx = _find_in_text(core_text, "def run_daily")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        cov[api] = info

    # ── 数据接口 ──
    for api in KNOWN_JQ_DATA_API:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}

        if api == "get_all_securities":
            line, ctx = _find_in_text(data_api_text, "def get_all_securities")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/data_api.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "get_extras":
            line, ctx = _find_in_text(data_api_text, "def get_extras")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/data_api.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "get_price":
            line, ctx = _find_in_text(data_api_text, "def get_price")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/data_api.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "get_fundamentals":
            line, ctx = _find_in_text(data_api_text, "def get_fundamentals")
            if line:
                info["status"] = "PARTIAL"
                info["file"] = "engine/data_api.py"
                info["line"] = line
                info["evidence"] = "PARTIAL: missing cash_flow and balance tables"

        elif api == "get_current_data":
            line, ctx = _find_in_text(core_text, "def get_current_data")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        cov[api] = info

    # ── 交易接口 ──
    for api in KNOWN_JQ_TRADE_API:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}

        if api == "order_target":
            line, ctx = _find_in_text(core_text, "def order_target")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        elif api == "order_target_value":
            line, ctx = _find_in_text(core_text, "def order_target_value")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        cov[api] = info

    # ── Context 属性 ──
    for api in KNOWN_JQ_CONTEXT_ATTRS:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}

        attr_name = api.split(".")[-1]
        context_name = api.split(".")[1] if len(api.split(".")) > 2 else api.split(".")[0]

        if "current_dt" in api:
            line, ctx = _find_in_text(context_text, "current_dt")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/context.py"
                info["line"] = line
                info["evidence"] = ctx

        elif "previous_date" in api:
            line, ctx = _find_in_text(context_text, "previous_date")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/context.py"
                info["line"] = line
                info["evidence"] = ctx

        elif "positions" in api:
            line, ctx = _find_in_text(context_text, "positions")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/context.py"
                info["line"] = line
                info["evidence"] = ctx

        elif "total_value" in api:
            line, ctx = _find_in_text(context_text, "total_value")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/context.py"
                info["line"] = line
                info["evidence"] = ctx

        elif "available_cash" in api:
            line, ctx = _find_in_text(context_text, "available_cash")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/context.py"
                info["line"] = line
                info["evidence"] = ctx

        cov[api] = info

    # ── Position 属性 ──
    for api in KNOWN_JQ_POSITION_ATTRS:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}
        attr_name = api.split(".")[-1]

        if attr_name == "value":
            # 检查是否有 @property def value
            line, ctx = _find_in_text(context_text, "def value")
            found = False
            if line:
                # 检查前面的行是否有 @property
                lines = context_text.split("\n")
                if line >= 2 and "@property" in lines[line - 2]:
                    info["status"] = "PASS"
                    info["evidence"] = ctx
                    info["line"] = line
                    found = True
            if not found:
                info["status"] = "MISSING"
                info["evidence"] = "position.value not implemented as property"
        else:
            line, ctx = _find_in_text(context_text, attr_name)
            if line:
                info["status"] = "PASS"
                info["line"] = line
                info["evidence"] = ctx

        info["file"] = "engine/context.py"
        cov[api] = info

    # ── CurrentData 字段 ──
    for api in KNOWN_JQ_CURRENT_DATA_FIELDS:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}
        field = api.split(".")[-1]

        line, ctx = _find_in_text(core_text, '"' + field + '"')
        if line is None:
            line, ctx = _find_in_text(core_text, "'" + field + "'")
        if line:
            info["status"] = "PASS"
            info["file"] = "engine/core.py"
            info["line"] = line
            info["evidence"] = ctx
        else:
            info["status"] = "MISSING"

        cov[api] = info

    # ── 查询表 ──
    for api in KNOWN_JQ_QUERY_TABLES:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}
        parts = api.split(".")
        table = parts[0]
        field = parts[1]

        if table in ("valuation", "indicator"):
            # core.py 中创建 JQField
            line, ctx = _find_in_text(core_text, "'" + field + "'")
            if line is None:
                line, ctx = _find_in_text(core_text, '"' + field + '"')
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx
            else:
                info["status"] = "MISSING"

        elif table in ("cash_flow", "balance"):
            # 检查是否有对应的 JQTable / JQField 创建
            line, _ = _find_in_text(core_text, table)
            if line:
                info["status"] = "PARTIAL"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = "table referenced but fields may not be fully implemented"
            else:
                info["status"] = "MISSING"
                info["evidence"] = "table '%s' not created in core.py JQField definitions" % table

        elif table == "income":
            line, ctx = _find_in_text(core_text, "'" + field + "'")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        cov[api] = info

    # ── 日志 ──
    for api in KNOWN_JQ_OTHERS:
        info = {"status": "MISSING", "file": "", "line": 0, "evidence": ""}

        if "log.info" in api or "log.warn" in api:
            line, ctx = _find_in_text(core_text, "def info")
            if line:
                info["status"] = "PASS"
                info["file"] = "engine/core.py"
                info["line"] = line
                info["evidence"] = ctx

        cov[api] = info

    return cov


# ─── 输出 ──────────────────────────────────────────────────────────────


def print_table(coverage):
    """打印控制台表格。"""
    headers = ["API", "Status", "File", "Line", "Evidence"]
    col_widths = [30, 10, 30, 6, 60]

    def fmt_row(cols):
        return " | ".join(c.ljust(w) for c, w in zip(cols, col_widths))

    sep = "-+-".join("-" * w for w in col_widths)
    print(fmt_row(headers))
    print(sep)
    for api, info in sorted(coverage.items()):
        status = info["status"]
        f = info["file"][:28] if info["file"] else ""
        ln = str(info["line"]) if info["line"] else ""
        ev = info.get("evidence", "")[:58]
        print(fmt_row([api[:28], status, f, ln, ev]))


# ─── 主逻辑 ────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="检查微盘股策略与 local_quant 框架的兼容性"
    )
    parser.add_argument(
        "--strategy-path",
        default=None,
        help="策略文件路径（默认自动查找当前目录下的 微盘股-母版-*.py）",
    )
    parser.add_argument(
        "--local-quant-path",
        default=None,
        help="local_quant 框架路径（默认 ../local_quant）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出 JSON 结果文件路径",
    )
    args = parser.parse_args()

    # 定位策略文件
    if args.strategy_path:
        strategy_path = Path(args.strategy_path)
    else:
        cwd = Path.cwd()
        matches = list(cwd.glob("微盘股-母版-*.py"))
        if not matches:
            print("ERROR: 找不到策略文件", file=sys.stderr)
            sys.exit(1)
        strategy_path = matches[0]

    if not strategy_path.exists():
        print("ERROR: 策略文件不存在: %s" % strategy_path, file=sys.stderr)
        sys.exit(1)

    # 计算 SHA-256
    sha256 = hashlib.sha256()
    with open(strategy_path, "rb") as f:
        sha256.update(f.read())
    strategy_sha256 = sha256.hexdigest()

    # 定位 local_quant
    if args.local_quant_path:
        lq_path = Path(args.local_quant_path)
    else:
        lq_path = Path.cwd().parent / "local_quant"

    if not lq_path.exists():
        print("ERROR: local_quant 不存在: %s" % lq_path, file=sys.stderr)
        sys.exit(1)

    engine_init = lq_path / "engine" / "__init__.py"
    if not engine_init.exists():
        print("ERROR: local_quant engine 不存在: %s" % engine_init, file=sys.stderr)
        sys.exit(1)

    # 检查 local_quant git 状态
    import subprocess

    def git_cmd(*args):
        try:
            return subprocess.check_output(
                ["git"] + list(args), cwd=str(lq_path), stderr=subprocess.STDOUT
            ).decode().strip()
        except Exception:
            return "(unknown)"

    lq_branch = git_cmd("rev-parse", "--abbrev-ref", "HEAD")
    lq_commit = git_cmd("rev-parse", "HEAD")
    lq_remote = git_cmd("remote", "get-url", "origin")

    # 提取策略依赖
    deps = extract_dependencies_from_source(str(strategy_path))
    known_matched = match_deps_to_known(deps)
    unmatched = deps - KNOWN_JQ_ALL

    # 检查 local_quant 覆盖
    coverage = check_local_quant_coverage(str(lq_path))

    # 统计
    pass_count = sum(1 for v in coverage.values() if v["status"] == "PASS")
    partial_count = sum(1 for v in coverage.values() if v["status"] == "PARTIAL")
    missing_count = sum(1 for v in coverage.values() if v["status"] == "MISSING")
    unknown_count = sum(1 for v in coverage.values() if v["status"] == "UNKNOWN")

    # 检查关键缺失
    critical_missing = [
        api for api, info in coverage.items()
        if info["status"] in ("MISSING",) and api in CRITICAL_APIS
    ]
    critical_partial = [
        api for api, info in coverage.items()
        if info["status"] == "PARTIAL" and api in CRITICAL_APIS
    ]

    print("=" * 80)
    print("微盘股策略 → local_quant 兼容性预检报告")
    print("=" * 80)
    print()
    print("策略文件: %s" % strategy_path)
    print("  SHA-256: %s" % strategy_sha256)
    print()
    print("local_quant: %s" % lq_path)
    print("  分支: %s" % lq_branch)
    print("  HEAD: %s" % lq_commit)
    print("  远端: %s" % lq_remote)
    print()

    print("─" * 80)
    print("依赖提取（从策略 AST）")
    print("─" * 80)
    print("匹配到已知 API: %d" % len(known_matched))
    if unmatched:
        print("未匹配项: %s" % ", ".join(sorted(unmatched)[:20]))
    print()

    print("─" * 80)
    print("API 覆盖")
    print("─" * 80)
    print_table(coverage)
    print()

    print("─" * 80)
    print("统计")
    print("─" * 80)
    print("  PASS:    %d" % pass_count)
    print("  PARTIAL: %d" % partial_count)
    print("  MISSING: %d" % missing_count)
    print("  UNKNOWN: %d" % unknown_count)
    print("  合计:    %d" % len(coverage))
    print()
    print("关键缺失 (MISSING): %s" % ", ".join(critical_missing) if critical_missing else "无")
    print("关键 PARTIAL: %s" % ", ".join(critical_partial) if critical_partial else "无")
    print()

    # 构建结果
    result = {
        "strategy_file": str(strategy_path),
        "strategy_sha256": strategy_sha256,
        "local_quant_path": str(lq_path),
        "local_quant_branch": lq_branch,
        "local_quant_commit": lq_commit,
        "local_quant_remote": lq_remote,
        "coverage": coverage,
        "stats": {
            "PASS": pass_count,
            "PARTIAL": partial_count,
            "MISSING": missing_count,
            "UNKNOWN": unknown_count,
            "total": len(coverage),
        },
        "critical_missing": critical_missing,
        "critical_partial": critical_partial,
    }

    # 输出 JSON
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("结果已写入: %s" % out_path)

    # 退出码
    if missing_count > 0:
        sys.exit(2)
    if critical_partial:
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
