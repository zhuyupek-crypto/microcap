#!/usr/bin/env python3
"""
兼容性清单完整性测试 — 验证 API_COVERAGE.md 的覆盖质量。
"""

import json
import os
import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_COVERAGE = PROJECT_ROOT / "research" / "local_migration" / "API_COVERAGE.md"
COMPAT_SCRIPT = PROJECT_ROOT / "tools" / "check_local_quant_compat.py"
COMPAT_RESULT = PROJECT_ROOT / "research" / "local_migration" / "compatibility_result.json"
MIGRATION_GAPS = PROJECT_ROOT / "research" / "local_migration" / "MIGRATION_GAPS.md"
LQ_PATH = PROJECT_ROOT.parent / "local_quant"

# 已知 API 列表（必须全部覆盖）
REQUIRED_APIS = [
    # 配置与调度
    "set_benchmark", "set_option", "set_slippage", "FixedSlippage",
    "set_order_cost", "OrderCost", "run_daily",
    # 数据接口
    "get_all_securities", "get_extras", "get_price",
    "get_fundamentals", "get_current_data",
    # 交易
    "order_target", "order_target_value",
    # Context
    "context.current_dt", "context.previous_date",
    "context.portfolio.positions", "context.portfolio.total_value",
    # Position
    "position.value",
    # CurrentData
    "current_data.paused", "current_data.is_st",
    "current_data.last_price", "current_data.high_limit",
    "current_data.low_limit",
    # 查询表
    "valuation.code", "valuation.market_cap", "indicator.roe",
    "cash_flow.net_operate_cash_flow",
    "balance.total_liability", "balance.total_assets",
    # 日志
    "log.info", "log.warn",
]

# 必须包含 cash_flow 和 balance 查询字段
REQUIRED_QUERY_FIELDS = [
    "cash_flow.net_operate_cash_flow",
    "balance.total_liability",
    "balance.total_assets",
]


def test_api_coverage_md_exists():
    assert API_COVERAGE.exists(), "API_COVERAGE.md 不存在: %s" % API_COVERAGE


def test_compat_script_exists():
    assert COMPAT_SCRIPT.exists(), "兼容性脚本不存在: %s" % COMPAT_SCRIPT


def test_compat_script_runs():
    """兼容性脚本必须能够运行并生成 JSON 结果。"""
    import subprocess
    if not LQ_PATH.exists():
        pytest.skip("local_quant 路径不存在: %s" % LQ_PATH)

    result = subprocess.run(
        [
            sys.executable, str(COMPAT_SCRIPT),
            "--local-quant-path", str(LQ_PATH),
            "--output", str(COMPAT_RESULT),
        ],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )

    # 退出码为 0 或 2 都是正常的
    assert result.returncode in (0, 2), (
        "脚本异常退出 (code=%d):\nstdout:\n%s\nstderr:\n%s" %
        (result.returncode, result.stdout[:2000], result.stderr[:2000])
    )

    assert COMPAT_RESULT.exists(), "未生成结果文件: %s" % COMPAT_RESULT


def test_compat_result_is_valid_json():
    """JSON 结果格式必须有效。"""
    if not COMPAT_RESULT.exists():
        pytest.skip("结果文件不存在，先运行 test_compat_script_runs")
    with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "coverage" in data, "结果缺少 coverage 字段"
    assert "stats" in data, "结果缺少 stats 字段"
    assert "critical_missing" in data, "结果缺少 critical_missing 字段"
    assert "critical_partial" in data, "结果缺少 critical_partial 字段"
    assert "local_quant_branch" in data, "结果缺少 local_quant_branch 字段"
    assert "local_quant_commit" in data, "结果缺少 local_quant_commit 字段"


def test_coverage_covers_all_required_apis():
    """依赖清单必须覆盖所有已知 API。"""
    if not COMPAT_RESULT.exists():
        pytest.skip("结果文件不存在")
    with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
        data = json.load(f)

    covered = set(data.get("coverage", {}).keys())
    required = set(REQUIRED_APIS)
    missing = required - covered
    assert not missing, "以下 API 未在覆盖清单中: %s" % ", ".join(sorted(missing))


def test_coverage_includes_cash_flow_and_balance():
    """必须包含 cash_flow 和 balance 查询字段。"""
    if not COMPAT_RESULT.exists():
        pytest.skip("结果文件不存在")
    with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
        data = json.load(f)

    covered = set(data.get("coverage", {}).keys())
    for field in REQUIRED_QUERY_FIELDS:
        assert field in covered, "缺少必需查询字段: %s" % field


def test_every_item_has_status():
    """每一项必须有明确状态。"""
    if not COMPAT_RESULT.exists():
        pytest.skip("结果文件不存在")
    with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_statuses = {"PASS", "PARTIAL", "MISSING", "UNKNOWN"}
    for api, info in data.get("coverage", {}).items():
        status = info.get("status", "")
        assert status in valid_statuses, (
            "%s 状态无效: %s (必须是 PASS/PARTIAL/MISSING/UNKNOWN 之一)" % (api, status)
        )


def test_no_blank_status():
    """不允许空白状态。"""
    if not COMPAT_RESULT.exists():
        pytest.skip("结果文件不存在")
    with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
        data = json.load(f)

    for api, info in data.get("coverage", {}).items():
        assert info.get("status", "").strip(), "%s 状态为空" % api


def test_missing_partial_has_impact_statement():
    """MISSING/PARTIAL/UNKNOWN 必须有影响说明。"""
    if not COMPAT_RESULT.exists():
        pytest.skip("结果文件不存在")
    with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
        data = json.load(f)

    non_pass = {k: v for k, v in data.get("coverage", {}).items()
                if v.get("status") in ("MISSING", "PARTIAL", "UNKNOWN")}
    # 影响说明在 API_COVERAGE.md 中长篇描述
    # JSON 结果中的 evidence 字段和 API_COVERAGE.md 文本检查
    # 这里只检查 evidence 字段非空
    for api, info in non_pass.items():
        assert info.get("evidence", "").strip(), (
            "%s 状态为 %s 但 evidence 为空" % (api, info.get("status"))
        )


def test_compat_result_json_stable():
    """JSON 格式必须稳定、可供后续任务消费。"""
    if not COMPAT_RESULT.exists():
        pytest.skip("结果文件不存在")
    with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 检查稳定的顶层结构
    required_keys = [
        "strategy_file", "strategy_sha256",
        "local_quant_path", "local_quant_branch", "local_quant_commit",
        "coverage", "stats", "critical_missing", "critical_partial",
    ]
    for key in required_keys:
        assert key in data, "结果缺少稳定结构字段: %s" % key

    # 每项 coverage 应有统一结构
    for api, info in data.get("coverage", {}).items():
        for field in ["status", "file", "line", "evidence"]:
            assert field in info, "%s 的 coverage 缺少字段 %s" % (api, field)


def test_compat_script_exit_code_for_missing():
    """存在 MISSING 时脚本应返回退出码 2。"""
    import subprocess
    if not LQ_PATH.exists():
        pytest.skip("local_quant 路径不存在")

    result = subprocess.run(
        [sys.executable, str(COMPAT_SCRIPT), "--local-quant-path", str(LQ_PATH)],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    # 如果有 MISSING，退出码应为 2
    if COMPAT_RESULT.exists():
        with open(COMPAT_RESULT, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("stats", {}).get("MISSING", 0) > 0:
            assert result.returncode == 2, (
                "存在 MISSING 时应返回 2，实际返回 %d" % result.returncode
            )
