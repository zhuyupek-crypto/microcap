#!/usr/bin/env python3
"""
兼容性清单完整性测试 — 验证 API_COVERAGE.md 的覆盖质量。
"""

import json
import os
import sys
import subprocess
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_COVERAGE = PROJECT_ROOT / "research" / "local_migration" / "API_COVERAGE.md"
COMPAT_SCRIPT = PROJECT_ROOT / "tools" / "check_local_quant_compat.py"
COMPAT_RESULT = PROJECT_ROOT / "research" / "local_migration" / "compatibility_result.json"
MIGRATION_GAPS = PROJECT_ROOT / "research" / "local_migration" / "MIGRATION_GAPS.md"
REPORT_FILE = PROJECT_ROOT / "research" / "local_migration" / "reports" / "TASK-MICROCAP-001_REPORT.md"
STRATEGY_FILE = PROJECT_ROOT / "微盘股-母版-20260627.py"

HDATA_ROOT = os.environ.get("HDATA_ROOT", r"D:\Work Space\HData")


def resolve_local_quant_path():
    path_from_env = os.environ.get("LOCAL_QUANT_PATH")
    if path_from_env:
        p = Path(path_from_env)
        if p.exists():
            return p
        raise FileNotFoundError("LOCAL_QUANT_PATH=%s 不存在" % path_from_env)
    candidates = [PROJECT_ROOT.parent / "local_quant"]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "local_quant 路径不存在。请设置环境变量 LOCAL_QUANT_PATH 或确认 ../local_quant 存在"
    )


LQ_PATH = resolve_local_quant_path()
sys.path.insert(0, str(LQ_PATH))
os.environ.setdefault("HDATA_ROOT", HDATA_ROOT)
os.environ.setdefault("LOCAL_QUANT_HDATA_SOURCE", "legacy")

REQUIRED_APIS = [
    "set_benchmark", "set_option", "set_slippage", "FixedSlippage",
    "set_order_cost", "OrderCost", "run_daily",
    "get_all_securities", "get_extras", "get_price",
    "get_fundamentals", "get_current_data",
    "order_target", "order_target_value",
    "context.current_dt", "context.previous_date",
    "context.portfolio.positions", "context.portfolio.total_value",
    "position.value",
    "current_data.paused", "current_data.is_st",
    "current_data.last_price", "current_data.high_limit",
    "current_data.low_limit",
    "valuation.code", "valuation.market_cap", "indicator.roe",
    "cash_flow.net_operate_cash_flow",
    "balance.total_liability", "balance.total_assets",
    "log.info", "log.warn",
]

REQUIRED_QUERY_FIELDS = [
    "cash_flow.net_operate_cash_flow",
    "balance.total_liability",
    "balance.total_assets",
]


# ─── 路径与环境 ───────────────────────────────────────────────────────

def test_local_quant_path_must_resolve():
    assert LQ_PATH.exists(), "local_quant 路径不存在: %s" % LQ_PATH


def test_strategy_file_exists():
    assert STRATEGY_FILE.exists(), "策略文件不存在: %s" % STRATEGY_FILE


def test_api_coverage_md_exists():
    assert API_COVERAGE.exists(), "API_COVERAGE.md 不存在: %s" % API_COVERAGE


def test_compat_script_exists():
    assert COMPAT_SCRIPT.exists(), "兼容性脚本不存在: %s" % COMPAT_SCRIPT


# ─── 兼容性脚本运行 ───────────────────────────────────────────────────

def test_compat_script_runs():
    result = subprocess.run(
        [sys.executable, str(COMPAT_SCRIPT),
         "--local-quant-path", str(LQ_PATH),
         "--output", str(COMPAT_RESULT)],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120,
    )
    assert result.returncode in (0, 2), (
        "脚本异常退出 (code=%d):\nstdout:%s\nstderr:%s" %
        (result.returncode, result.stdout[:2000], result.stderr[:2000])
    )
    assert COMPAT_RESULT.exists(), "未生成结果文件: %s" % COMPAT_RESULT


def test_compat_script_exit_code_for_missing():
    result = subprocess.run(
        [sys.executable, str(COMPAT_SCRIPT), "--local-quant-path", str(LQ_PATH)],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120,
    )
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    if data.get("stats", {}).get("MISSING", 0) > 0:
        assert result.returncode == 2, (
            "存在 MISSING 时应返回 2，实际返回 %d" % result.returncode
        )


# ─── JSON 结果验证 ────────────────────────────────────────────────────

def test_compat_result_is_valid_json():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    for key in ["coverage", "stats", "critical_missing", "critical_partial",
                "local_quant_branch", "local_quant_commit",
                "extracted_dependencies", "matched_dependencies",
                "unmatched_dependencies", "semantic_checks"]:
        assert key in data, "结果缺少 %s 字段" % key


def test_coverage_covers_all_required_apis():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    covered = set(data.get("coverage", {}).keys())
    missing = set(REQUIRED_APIS) - covered
    assert not missing, "以下 API 未在覆盖清单中: %s" % ", ".join(sorted(missing))


def test_coverage_includes_cash_flow_and_balance():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    covered = set(data.get("coverage", {}).keys())
    for field in REQUIRED_QUERY_FIELDS:
        assert field in covered, "缺少必需查询字段: %s" % field


def test_every_item_has_status():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    valid = {"PASS", "PARTIAL", "MISSING", "UNKNOWN"}
    for api, info in data.get("coverage", {}).items():
        assert info.get("status", "") in valid, "%s 状态无效: %s" % (api, info.get("status"))


def test_no_blank_status():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    for api, info in data.get("coverage", {}).items():
        assert info.get("status", "").strip(), "%s 状态为空" % api


def test_missing_partial_has_evidence():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    for api, info in data.get("coverage", {}).items():
        if info.get("status") in ("MISSING", "PARTIAL", "UNKNOWN"):
            assert info.get("evidence", "").strip(), "%s 状态为 %s 但 evidence 为空" % (
                api, info.get("status"))


def test_compat_result_json_stable():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    for key in ["strategy_file", "strategy_sha256",
                "local_quant_path", "local_quant_branch", "local_quant_commit",
                "coverage", "stats", "critical_missing", "critical_partial"]:
        assert key in data, "结果缺少稳定结构字段: %s" % key
    for api, info in data.get("coverage", {}).items():
        for field in ["status", "file", "line", "evidence"]:
            assert field in info, "%s 的 coverage 缺少字段 %s" % (api, field)


# ─── 统计一致性验证（唯一数据源） ────────────────────────────────────

def test_coverage_stats_consistent():
    """JSON、API_COVERAGE.md、报告三份文档的四个状态数字完全一致。"""
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    s = data["stats"]
    computed_total = s["PASS"] + s["PARTIAL"] + s["MISSING"] + s["UNKNOWN"]
    assert computed_total == s["total"], "状态数量之和 (%d) != total (%d)" % (computed_total, s["total"])
    assert s["total"] == len(data["coverage"]), "stats.total (%d) != coverage 项数 (%d)" % (
        s["total"], len(data["coverage"]))

    # 从 API_COVERAGE.md 解析统计
    md_text = API_COVERAGE.read_text(encoding="utf-8")
    md_stats = {}
    for line in md_text.split("\n"):
        if not line.startswith("| **"):
            continue
        cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in ("PASS", "PARTIAL", "MISSING", "UNKNOWN"):
            try:
                md_stats[cells[0]] = int(cells[1])
            except ValueError:
                pass
    md_total = sum(md_stats.values())
    assert md_total > 0, "无法从 API_COVERAGE.md 解析统计数字"
    assert md_stats.get("PASS") == s["PASS"], "API_COVERAGE PASS (%d) != JSON (%d)" % (
        md_stats.get("PASS"), s["PASS"])
    assert md_stats.get("PARTIAL") == s["PARTIAL"], "API_COVERAGE PARTIAL (%d) != JSON (%d)" % (
        md_stats.get("PARTIAL"), s["PARTIAL"])
    assert md_stats.get("MISSING") == s["MISSING"], "API_COVERAGE MISSING (%d) != JSON (%d)" % (
        md_stats.get("MISSING"), s["MISSING"])
    assert md_stats.get("UNKNOWN") == s["UNKNOWN"], "API_COVERAGE UNKNOWN (%d) != JSON (%d)" % (
        md_stats.get("UNKNOWN"), s["UNKNOWN"])

    # 从报告文件解析统计
    report_text = REPORT_FILE.read_text(encoding="utf-8")
    report_stats = {"PASS": None, "PARTIAL": None, "MISSING": None, "UNKNOWN": None}
    for line in report_text.split("\n"):
        if not line.startswith("| **"):
            continue
        cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in ("PASS", "PARTIAL", "MISSING", "UNKNOWN"):
            try:
                report_stats[cells[0]] = int(cells[1])
            except ValueError:
                pass
    if all(v is not None for v in report_stats.values()):
        assert report_stats["PASS"] == s["PASS"]
        assert report_stats["PARTIAL"] == s["PARTIAL"]
        assert report_stats["MISSING"] == s["MISSING"]
        assert report_stats["UNKNOWN"] == s["UNKNOWN"]


def test_unknown_count_zero():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    assert data["stats"]["UNKNOWN"] == 0, "UNKNOWN 不为 0: %d" % data["stats"]["UNKNOWN"]


# ─── blocking 级别验证 ─────────────────────────────────────────────

def test_set_benchmark_not_critical():
    """set_benchmark 不应进入 critical_partial，它不影响策略信号。"""
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    cp = data.get("critical_partial", [])
    assert "set_benchmark" not in cp, "set_benchmark 不应在 critical_partial 中"


# ─── log 方法专项检查 ────────────────────────────────────────────────

def test_log_warn_detected_as_missing():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    status = data["coverage"].get("log.warn", {}).get("status", "")
    assert status == "MISSING", "log.warn 应为 MISSING，实际为 %s" % status


def test_log_warning_detected_as_present():
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    status = data["coverage"].get("log.warning", {}).get("status", "")
    assert status == "PASS", "log.warning 应为 PASS，实际为 %s" % status


# ─── 09:30 价格语义实证 ─────────────────────────────────────────────

def test_current_data_0930_last_price_uses_open():
    """
    使用真实 Engine 实例测试 09:30 时 get_current_data().last_price。
    验证：last_price == 当日开盘价，且开盘价 != 前收盘。
    """
    from engine.core import Engine
    from engine.order import OrderCost

    test_date = "2024-01-03"
    engine = Engine("probe_0930", test_date, test_date, initial_cash=1000000, frequency="daily")
    engine.context._current_dt = pd.Timestamp("%s 09:30:00" % test_date)
    engine.current_time = "09:30"
    engine.context.__setattr__("previous_date", pd.Timestamp("2024-01-02"))

    code = "000001.XSHE"
    cd = engine.get_current_data()
    last_price = cd[code].last_price

    # 从日线数据获取验证基准
    df = pd.read_parquet(os.path.join(HDATA_ROOT, "data", "processed", "1d_stock", "2024.parquet"))
    row = df[(df["code"] == "000001.SZ") & (df["date"].astype(str) == "20240103")]
    assert not row.empty, "缺少 2024-01-03 日线数据"
    r = row.iloc[0]
    actual_open = float(r["open"])
    actual_pre_close = float(r["pre_close"])

    assert abs(actual_open - actual_pre_close) > 0.01, (
        "测试前提不成立: 2024-01-03 开盘价(%s)应不同于前收盘(%s)" % (actual_open, actual_pre_close))
    assert abs(last_price - actual_open) < 0.01, (
        "09:30 last_price(%s) 应等于当日开盘价(%s)" % (last_price, actual_open))

    # GAP-005 已关闭: local_quant 在 09:30 正确返回开盘价
    print("\n09:30 价格语义验证通过: last_price=%.2f == open=%.2f != pre_close=%.2f" % (
        last_price, actual_open, actual_pre_close))


# ─── ETF 费用路由实证 ─────────────────────────────────────────────

def test_511880_uses_etf_cost_model():
    """
    使用真实 Engine 验证 511880.XSHG 使用独立的 ETF 费用模型。
    set_order_cost(type='stock') 不覆盖 ETF 费用。
    ETF 费用: close_tax=0, 免印花税。
    """
    from engine.core import Engine
    from engine.order import OrderCost

    engine = Engine("probe_etf", "2024-01-03", "2024-01-03", initial_cash=1000000)

    etf_code = "511880.XSHG"
    stock_code = "000001.XSHE"

    # 验证类型识别
    assert engine._get_instrument_type(etf_code) == "etf", "511880 应识别为 etf"
    assert engine._get_instrument_type(stock_code) == "stock", "000001.XSHE 应识别为 stock"

    # 模拟策略的 set_order_cost 调用
    strategy_cost = OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0001, close_commission=0.0001,
        min_commission=5,
    )
    engine.set_order_cost(strategy_cost, type="stock")

    # 获取 ETF 的费用模型（按 _execute_trade 中的路由）
    etf_cost = engine._order_costs.get(
        f"ref:{etf_code}",
        engine._order_costs.get("etf", engine.order_cost))

    # 获取股票的费用模型
    stock_cost = engine._order_costs.get(
        f"ref:{stock_code}",
        engine._order_costs.get("stock", engine.order_cost))

    print("\nETF 费用验证:")
    print("  ETF close_tax=%s (应=0)" % etf_cost.close_tax)
    print("  股票 close_tax=%s (应=0.001)" % stock_cost.close_tax)

    # ETF 关账印花税为 0
    assert etf_cost.close_tax == 0, "ETF 印花税应为 0，实际 %s" % etf_cost.close_tax
    # ETF 佣金费率
    assert etf_cost.open_commission == 0.0001, "ETF open_commission 应为 0.0001，实际 %s" % etf_cost.open_commission
    assert etf_cost.close_commission == 0.0001, "ETF close_commission 应为 0.0001，实际 %s" % etf_cost.close_commission
    # ETF 最低佣金为 0
    assert etf_cost.min_commission == 0, "ETF min_commission 应为 0，实际 %s" % etf_cost.min_commission
    # 股票印花税为 0.001（策略设置）
    assert stock_cost.close_tax == 0.001, "股票 close_tax 应为 0.001（策略设置）"
    # ETF 费用 != 股票费用
    assert etf_cost.close_tax != stock_cost.close_tax, "ETF 与股票费用应不同"

    print("  GAP-008 关闭: ETF 使用独立费用模型，免印花税。")


# ─── 分钟数据 high_limit 验证 ─────────────────────────────────────────

def test_minute_data_has_high_limit_for_check_limit_up():
    """
    使用真实 DataAPI 验证 14:00 get_price(frequency='1m', fields=['close','high_limit'])
    能返回 high_limit 字段。
    至少检查 2023/2024/2025 各一个样本。
    """
    from engine.data_api import DataAPI

    api = DataAPI()
    code = "000001.SZ"
    test_cases = [
        ("2023", "2023-01-04"),
        ("2024", "2024-01-03"),
        ("2025", "2025-01-06"),
    ]

    checked = 0
    for year_label, date_str in test_cases:
        end_dt = pd.Timestamp("%s 14:00:00" % date_str)
        result = api.get_price(
            security=code,
            end_date=end_dt,
            frequency="1m",
            count=1,
            fields=["close", "high_limit"],
        )
        assert result is not None and not result.empty, (
            "分钟数据为空: %s %s" % (code, date_str))
        assert "close" in result.columns, (
            "%s: 结果缺少 close 列" % date_str)
        assert "high_limit" in result.columns, (
            "%s: 结果缺少 high_limit 列" % date_str)
        assert result["high_limit"].notna().all(), (
            "%s: high_limit 存在空值" % date_str)
        assert result.index.max() <= end_dt, (
            "%s: 索引最大时间 %s 超过查询时间 %s" % (
                date_str, result.index.max(), end_dt))
        checked += 1

    assert checked == 3, "只检查了 %d/3 个样本" % checked
    print("\n分钟数据 high_limit 验证通过: 3/3 样本均包含 high_limit 字段")


# ─── 缺口清单一致性验证 ──────────────────────────────────────────────

def _parse_gap_table(md_path):
    """从 MIGRATION_GAPS.md 解析 P0/P1/P2 缺口数量和编号列表。"""
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    gaps = {"P0": [], "P1": [], "P2": []}
    for line in lines:
        if not line.startswith("| **P"):
            continue
        cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in ("P0", "P1", "P2"):
            gap_ids = [g.strip() for g in cells[2].split(",") if g.strip().startswith("GAP-")]
            gaps[cells[0]] = gap_ids
    return gaps


def test_gap_list_consistent_with_json():
    """验证 MIGRATION_GAPS.md 与报告的 P0/P1/P2 编号和数量一致。"""
    data = json.loads(COMPAT_RESULT.read_text(encoding="utf-8"))
    missing_count = data["stats"]["MISSING"]

    gaps = _parse_gap_table(MIGRATION_GAPS)
    all_ids = gaps["P0"] + gaps["P1"] + gaps["P2"]

    # 每个编号不得重复
    assert len(all_ids) == len(set(all_ids)), "GAP 编号存在重复"

    # 验证 GAP-012 存在于 P0
    assert "GAP-012" in gaps["P0"] or "GAP-012" in [g.strip() for g in gaps["P0"]], (
        "GAP-012 未在 MIGRATION_GAPS.md 的 P0 中")

    # 验证统计表的总数
    for line in MIGRATION_GAPS.read_text(encoding="utf-8").split("\n"):
        if "**合计**" in line or "**\u5408\u8ba1**" in line:
            cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
            total_ids = len(all_ids)
            if len(cells) >= 2:
                reported_total = cells[1].strip("*").strip()
                if reported_total.isdigit():
                    assert int(reported_total) == total_ids, (
                        "MIGRATION_GAPS 合计(%s) != 实际GAP数(%d)" % (reported_total, total_ids))

    # 验证报告与 MIGRATION_GAPS 一致
    report_gaps = _parse_gap_table(REPORT_FILE)
    if report_gaps["P0"] or report_gaps["P1"] or report_gaps["P2"]:
        assert report_gaps == gaps, (
            "报告缺口列表与 MIGRATION_GAPS 不一致:\n  报告: %s\n  MIGRATION_GAPS: %s" % (
                report_gaps, gaps))


def test_gap_005_closed():
    """确认 GAP-005 已关闭：09:30 返回开盘价已验证通过。"""
    from engine.core import Engine
    engine = Engine("probe", "2024-01-03", "2024-01-03", frequency="daily")
    engine.context._current_dt = pd.Timestamp("2024-01-03 09:30:00")
    engine.current_time = "09:30"
    engine.context.__setattr__("previous_date", pd.Timestamp("2024-01-02"))
    cd = engine.get_current_data()
    last_price = cd["000001.XSHE"].last_price
    df = pd.read_parquet(os.path.join(HDATA_ROOT, "data", "processed", "1d_stock", "2024.parquet"))
    row = df[(df["code"] == "000001.SZ") & (df["date"].astype(str) == "20240103")]
    actual_open = float(row.iloc[0]["open"])
    assert abs(last_price - actual_open) < 0.01


def test_gap_008_closed():
    """确认 GAP-008 已关闭：ETF 使用独立费用模型，免印花税。"""
    from engine.core import Engine
    from engine.order import OrderCost
    engine = Engine("probe", "2024-01-03", "2024-01-03")
    engine.set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0001,
                                     close_commission=0.0001, min_commission=5), type="stock")
    etf_cost = engine._order_costs.get("etf", engine.order_cost)
    assert etf_cost.close_tax == 0, "ETF close_tax 应为 0"
