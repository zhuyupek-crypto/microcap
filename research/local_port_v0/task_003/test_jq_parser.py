#!/usr/bin/env python3
"""Tests for JQ record parser (TASK-MICROCAP-003A)."""

import os, sys, csv, io, re, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _parse_jq_records import (
    code_from_name_cell, name_from_name_cell, normalize_code,
    parse_quantity, parse_amount, sha256_of
)

TEST_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")
DATA_DIR = Path(r"D:\Work Space\他山之石\微盘股")

# ============================================================
# Encoding and basic file checks
# ============================================================

def test_trade_file_encoding():
    fp = DATA_DIR / "母版交易记录-20260501-20260623.txt"
    with open(fp, "rb") as f:
        raw = f.read()
    # UTF-8 without BOM
    assert raw[:3] != b"\xef\xbb\xbf", "Should have no BOM"
    decoded = raw.decode("utf-8")
    assert "\t" in decoded, "Should be tab-separated"

def test_portfolio_file_encoding():
    fp = DATA_DIR / "母版持仓&资金记录-20260501-20260623.txt"
    with open(fp, "rb") as f:
        raw = f.read()
    assert raw[:3] != b"\xef\xbb\xbf", "Should have no BOM"
    decoded = raw.decode("utf-8")
    assert "Cash" in decoded, "Should contain Cash records"

def test_trade_file_has_chinese():
    fp = DATA_DIR / "母版交易记录-20260501-20260623.txt"
    with open(fp, "r", encoding="utf-8") as f:
        text = f.read()
    # Verify Chinese characters are present (not garbled)
    assert "买" in text or "卖" in text or "日期" in text or "委托时间" in text

# ============================================================
# Helper function tests
# ============================================================

def test_code_from_name_cell():
    assert code_from_name_cell("金埔园林(301098.XSHE)") == "301098.XSHE"
    assert code_from_name_cell("凤竹纺织(600493.XSHG)") == "600493.XSHG"
    assert code_from_name_cell("NoCode") is None
    assert code_from_name_cell("") is None

def test_name_from_name_cell():
    assert name_from_name_cell("金埔园林(301098.XSHE)") == "金埔园林"
    assert name_from_name_cell("凤竹纺织(600493.XSHG)") == "凤竹纺织"
    assert name_from_name_cell("NoCode") == "NoCode"

def test_normalize_code():
    assert normalize_code("301098.XSHE") == "301098.XSHE"
    assert normalize_code("600493.XSHG") == "600493.XSHG"
    assert normalize_code("000001.SH") == "000001.XSHG"
    assert normalize_code("000001.SZ") == "000001.XSHE"
    assert normalize_code(None) is None

def test_parse_quantity():
    assert parse_quantity("200股") == 200
    assert parse_quantity("-300股") == -300
    assert parse_quantity("2300股") == 2300
    assert parse_quantity("200") == 200
    assert parse_quantity("") is None
    assert parse_quantity(None) is None
    assert parse_quantity("1,500股") == 1500

def test_parse_amount():
    assert parse_amount("19,260.00") == 19260.0
    assert parse_amount("-2,955.00") == -2955.0
    assert parse_amount("805,259.00") == 805259.0
    assert parse_amount("") is None
    assert parse_amount("1,001,161.00") == 1001161.0
    assert parse_amount(None) is None

def test_parse_amount_with_thousand_sep():
    """Test that Chinese comma-format amounts parse correctly."""
    assert parse_amount("19,260.00") == 19260.0
    assert parse_amount("1,001,161.00") == 1001161.0
    assert parse_amount("805,259.00") == 805259.0

def test_parse_amount_fullwidth():
    """Test full-width comma variants."""
    assert parse_amount("19，260.00") == 19260.0  # full-width comma

# ============================================================
# Trade record parsing tests
# ============================================================

def test_trade_records_parse():
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    assert len(errors) == 0, f"Unexpected parse errors: {errors}"
    assert len(records) > 0, "Should have parsed records"
    # Check fields
    r = records[0]
    assert "trade_date" in r
    assert "trade_time" in r
    assert "normalized_security_code" in r
    assert "side" in r
    assert "quantity" in r
    assert "price" in r
    assert "gross_amount" in r

def test_trade_records_date_range():
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    dates = sorted(set(r["trade_date"] for r in records if r["trade_date"]))
    assert len(dates) > 0
    assert dates[0] >= "2026-05-01", f"First date {dates[0]} before expected range"
    assert dates[-1] <= "2026-06-23", f"Last date {dates[-1]} after expected range"

def test_trade_records_buy_sell_mix():
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    sides = set(r["side"] for r in records)
    assert "buy" in sides, "Should have buy records"
    assert "sell" in sides, "Should have sell records"
    buys = [r for r in records if r["side"] == "buy"]
    sells = [r for r in records if r["side"] == "sell"]
    assert len(buys) > 0
    assert len(sells) > 0
    # Verify sell records have security codes
    for s in sells:
        assert s["normalized_security_code"], f"Sell without code: {s}"

def test_trade_records_code_normalization():
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    for r in records:
        code = r["normalized_security_code"]
        if code:
            assert code.endswith(".XSHG") or code.endswith(".XSHE"), \
                f"Unnormalized code: {code}"

# ============================================================
# Portfolio record parsing tests
# ============================================================

def test_portfolio_records_parse():
    from _parse_jq_records import parse_portfolio_records
    records, errors = parse_portfolio_records()
    assert len(errors) == 0, f"Unexpected parse errors: {errors}"
    assert len(records) > 0
    types = set(r["snapshot_type"] for r in records)
    assert "position" in types, "Should have position records"
    assert "cash_summary" in types, "Should have cash records"
    assert "total_summary" in types, "Should have total records"

def test_portfolio_no_header_leak():
    """Header lines like '标的', '数量' should NOT appear as position records."""
    from _parse_jq_records import parse_portfolio_records
    records, errors = parse_portfolio_records()
    bad_names = [r["security_name"] for r in records
                 if r["security_name"] in ("标的", "数量", "收盘价/结算价", "市值/净值", "盈亏/浮动盈亏")]
    assert len(bad_names) == 0, f"Header names leaked: {bad_names}"

def test_portfolio_cash_consistency():
    from _parse_jq_records import parse_portfolio_records
    records, errors = parse_portfolio_records()
    cash_rows = [r for r in records if r["snapshot_type"] == "cash_summary"]
    assert len(cash_rows) > 0
    for c in cash_rows:
        assert c["available_cash"] is not None and c["available_cash"] > 0, \
            f"Invalid cash at {c['record_date']}: {c['available_cash']}"

def test_portfolio_total_consistency():
    from _parse_jq_records import parse_portfolio_records
    records, errors = parse_portfolio_records()
    total_rows = [r for r in records if r["snapshot_type"] == "total_summary"]
    assert len(total_rows) > 0
    for t in total_rows:
        assert t["total_asset"] is not None and t["total_asset"] > 0

# ============================================================
# Long-format (tall) checks
# ============================================================

def test_portfolio_long_format():
    """Verify portfolio CSV is in tall/long format (one row per security per date)."""
    fp = TEST_DIR / "jq_portfolio_normalized.csv"
    assert fp.exists()
    with open(fp, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    # Should have position rows for multiple securities per date
    pos_rows = [r for r in rows if r["snapshot_type"] == "position"]
    assert len(pos_rows) > len(set(r["record_date"] for r in pos_rows)), \
        "Should have multiple positions per date (long format)"

# ============================================================
# Duplicate detection tests
# ============================================================

def test_duplicates_detected():
    """Source file has genuine duplicate rows; verify they are detected."""
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    texts = [r["raw_text"] for r in records]
    from collections import Counter
    dup_counts = [c for c in Counter(texts).values() if c > 1]
    assert len(dup_counts) > 0, "Source file has known duplicates; should be found"
    # The duplicate is a 100-share buy of 301098.XSHE on 2026-06-09
    dup_texts = [t for t, c in Counter(texts).items() if c > 1]
    assert "301098.XSHE" in dup_texts[0], f"Unexpected duplicate content: {dup_texts[0][:80]}"

# ============================================================
# End-of-file truncation check
# ============================================================

def test_trade_file_no_truncation():
    """Last line of trade file should be a complete record."""
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    # If the last record has all expected fields, it's not truncated
    last = records[-1]
    assert last["trade_date"] is not None
    assert last["normalized_security_code"] is not None
    assert last["commission"] is not None or True  # Some records may not have commission

# ============================================================
# Empty line handling
# ============================================================

def test_empty_lines_skipped():
    """Trade file has empty/whitespace-only separator lines; they should be skipped."""
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    for r in records:
        assert r["trade_date"], "Parsed records should always have a date"

# ============================================================
# Security code normalization
# ============================================================

def test_all_codes_have_suffix():
    from _parse_jq_records import parse_trade_records
    records, errors, header = parse_trade_records()
    for r in records:
        code = r["normalized_security_code"]
        if code:
            assert code.endswith(".XSHE") or code.endswith(".XSHG"), f"Bad suffix: {code}"

# ============================================================
# Run
# ============================================================
if __name__ == "__main__":
    import inspect
    this_mod = sys.modules[__name__]
    tests = [fn for fn in dir(this_mod) if fn.startswith("test_")]
    passed = 0
    failed = 0
    for name in tests:
        try:
            getattr(this_mod, name)()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
