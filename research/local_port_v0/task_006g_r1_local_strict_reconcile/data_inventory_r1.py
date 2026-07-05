#!/usr/bin/env python3
"""
TASK-006G-R1 Stage 1: Data Inventory
=====================================
Systematically inventory all input files for 2025/2026 strict reconciliation.

For each file, record:
- file_path, exists, data_type, start_date, end_date, row_count
- has_trade_price/qty/fee, has_cash, has_total_asset, has_position_market_value,
  has_position_detail, is_full_period
- usable_for_trade_reconcile, usable_for_equity_reconcile, evidence_level, notes

Output:
- outputs/DATA_INVENTORY_R1.csv
- DATA_INVENTORY_R1.md
"""
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Project root
PROJECT_ROOT = Path(r"D:\Work Space\他山之石\微盘股")
OUTPUT_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_006g_r1_local_strict_reconcile" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_read_csv(path):
    try:
        return pd.read_csv(path)
    except Exception as e:
        return None, str(e)
    return df, None


def _read_csv_safe(path):
    try:
        return pd.read_csv(path), None
    except Exception as e:
        return None, str(e)


def _date_range(df, date_col):
    """Return (min_date, max_date) as strings from a date column."""
    if df is None or df.empty or date_col not in df.columns:
        return ("", "")
    try:
        s = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if s.empty:
            return ("", "")
        return (s.min().strftime("%Y-%m-%d"), s.max().strftime("%Y-%m-%d"))
    except Exception:
        return ("", "")


def _probe_txt_trade_file(path):
    """Probe a JQ trade txt file. Return dict of properties."""
    info = {
        "exists": False, "data_type": "jq_trade_txt", "start_date": "",
        "end_date": "", "row_count": 0, "has_trade_price": False,
        "has_trade_qty": False, "has_trade_fee": False, "has_cash": False,
        "has_total_asset": False, "has_position_market_value": False,
        "has_position_detail": False, "is_full_period": False,
        "notes": "",
    }
    if not path.exists():
        info["notes"] = "FILE_NOT_FOUND"
        return info
    info["exists"] = True
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Count data rows (lines starting with date-like pattern after stripping)
        data_rows = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            # Skip header rows (no leading date)
            if len(s) >= 10 and s[:4].isdigit() and s[4] == "-":
                data_rows.append(s)
        info["row_count"] = len(data_rows)
        if data_rows:
            # Extract first/last date
            dates = []
            for r in data_rows:
                # date is first token before tab
                tok = r.split("\t")[0] if "\t" in r else r.split()[0]
                if len(tok) >= 10 and tok[:4].isdigit():
                    dates.append(tok[:10])
            if dates:
                info["start_date"] = dates[0]
                info["end_date"] = dates[-1]
            # Field probes: scan header text (first ~20 lines)
            header_text = " ".join(lines[:25])
            info["has_trade_price"] = "成交价" in header_text or "price" in header_text.lower()
            info["has_trade_qty"] = "成交数量" in header_text or "数量" in header_text or "quantity" in header_text.lower()
            info["has_trade_fee"] = "手续费" in header_text or "佣金" in header_text or "fee" in header_text.lower()
        info["notes"] = f"txt parsed: {len(data_rows)} date-prefixed rows"
    except Exception as e:
        info["notes"] = f"PARSE_ERROR: {e}"
    return info


def _probe_txt_portfolio_file(path):
    """Probe a JQ portfolio&cash txt file."""
    info = {
        "exists": False, "data_type": "jq_portfolio_txt", "start_date": "",
        "end_date": "", "row_count": 0, "has_trade_price": False,
        "has_trade_qty": False, "has_trade_fee": False, "has_cash": False,
        "has_total_asset": False, "has_position_market_value": False,
        "has_position_detail": False, "is_full_period": False,
        "notes": "",
    }
    if not path.exists():
        info["notes"] = "FILE_NOT_FOUND"
        return info
    info["exists"] = True
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        lines = text.splitlines()
        # Date detection: lines starting with YYYY-MM-DD
        date_lines = [l for l in lines if len(l) >= 10 and l[:4].isdigit() and l[4] == "-"]
        info["row_count"] = len(date_lines)
        if date_lines:
            dates = sorted(set(l[:10] for l in date_lines))
            info["start_date"] = dates[0]
            info["end_date"] = dates[-1]
        info["has_cash"] = "Cash" in text or "现金" in text
        info["has_total_asset"] = "总共" in text or "Total" in text or "总资产" in text
        info["has_position_market_value"] = "市值" in text
        info["has_position_detail"] = "股" in text
        info["notes"] = f"txt parsed: {len(date_lines)} date rows, {len(set(l[:10] for l in date_lines))} unique dates"
    except Exception as e:
        info["notes"] = f"PARSE_ERROR: {e}"
    return info


def _probe_csv(path, data_type, date_col_candidates):
    """Probe a generic CSV file. Return dict of properties."""
    info = {
        "exists": False, "data_type": data_type, "start_date": "",
        "end_date": "", "row_count": 0, "has_trade_price": False,
        "has_trade_qty": False, "has_trade_fee": False, "has_cash": False,
        "has_total_asset": False, "has_position_market_value": False,
        "has_position_detail": False, "is_full_period": False,
        "notes": "",
    }
    if not path.exists():
        info["notes"] = "FILE_NOT_FOUND"
        return info
    info["exists"] = True
    df, err = _read_csv_safe(path)
    if df is None:
        info["notes"] = f"READ_ERROR: {err}"
        return info
    info["row_count"] = len(df)
    # find date column
    date_col = None
    for c in date_col_candidates:
        if c in df.columns:
            date_col = c
            break
    if date_col:
        sd, ed = _date_range(df, date_col)
        info["start_date"] = sd
        info["end_date"] = ed
    cols_lower = set(c.lower() for c in df.columns)
    info["has_trade_price"] = any("price" in c for c in cols_lower)
    info["has_trade_qty"] = any("qty" in c or "amount" in c or "quantity" in c for c in cols_lower)
    info["has_trade_fee"] = any("fee" in c or "commission" in c or "tax" in c for c in cols_lower)
    info["has_cash"] = any("cash" in c for c in cols_lower)
    info["has_total_asset"] = any("total" in c and "asset" in c for c in df.columns.str.lower())
    info["has_total_asset"] = info["has_total_asset"] or any("total_value" in c or "total_asset" in c for c in cols_lower)
    info["has_position_market_value"] = any("position" in c and ("value" in c or "market" in c) for c in df.columns.str.lower())
    info["has_position_detail"] = any("position" in c or "security" in c or "code" in c for c in cols_lower)
    info["notes"] = f"cols={list(df.columns)[:8]}"
    return info


def _classify_usability(info, expected_period_start, expected_period_end, kind):
    """Determine usability flags and evidence level.
    kind: 'trade' or 'equity'
    """
    usable_trade = False
    usable_equity = False
    evidence = "C"

    if not info["exists"] or info["row_count"] == 0:
        return usable_trade, usable_equity, evidence, "file missing or empty"

    if kind == "trade":
        if info["has_trade_price"] and info["has_trade_qty"]:
            usable_trade = True
            # Full-period check
            if info["start_date"] and info["end_date"]:
                if info["start_date"] <= expected_period_start and info["end_date"] >= expected_period_end:
                    evidence = "A"
                    full = True
                else:
                    evidence = "B"
                    full = False
                info["is_full_period"] = full
            else:
                evidence = "B"
        else:
            evidence = "C"
    elif kind == "equity":
        if info["has_total_asset"] and info["has_cash"]:
            usable_equity = True
            if info["start_date"] and info["end_date"]:
                if info["start_date"] <= expected_period_start and info["end_date"] >= expected_period_end:
                    evidence = "A"
                    full = True
                else:
                    evidence = "B"
                    full = False
                info["is_full_period"] = full
            else:
                evidence = "B"
        elif info["has_cash"] or info["has_total_asset"]:
            usable_equity = True
            evidence = "B"
        else:
            evidence = "C"
    return usable_trade, usable_equity, evidence, ""


def main():
    print("=" * 70)
    print("TASK-006G-R1 Stage 1: Data Inventory")
    print("=" * 70)

    rows = []

    # ---- 1. Original JQ txt files (may not exist) ----
    # 2025 trade txt
    p = PROJECT_ROOT / "母版交易记录-20250101-20251231.txt"
    info = _probe_txt_trade_file(p)
    ut, ue, ev, _ = _classify_usability(info, "2025-01-01", "2025-12-31", "trade")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # 2025 portfolio txt (H1 only based on filename)
    p = PROJECT_ROOT / "母版持仓&资金记录-20250101-20250618.txt"
    info = _probe_txt_portfolio_file(p)
    ut, ue, ev, _ = _classify_usability(info, "2025-01-01", "2025-06-18", "equity")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # 2026 trade txt
    p = PROJECT_ROOT / "母版交易记录-20260501-20260623.txt"
    info = _probe_txt_trade_file(p)
    ut, ue, ev, _ = _classify_usability(info, "2026-05-01", "2026-06-23", "trade")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # 2026 portfolio txt
    p = PROJECT_ROOT / "母版持仓&资金记录-20260501-20260623.txt"
    info = _probe_txt_portfolio_file(p)
    ut, ue, ev, _ = _classify_usability(info, "2026-05-01", "2026-06-23", "equity")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # ---- 2. Cleaned JQ CSVs from task_003 / task_004 ----
    base = PROJECT_ROOT / "research" / "local_port_v0"

    # task_004/jq_trades_2025.csv
    p = base / "task_004" / "jq_trades_2025.csv"
    info = _probe_csv(p, "jq_trade_csv_cleaned", ["trade_date", "date"])
    ut, ue, ev, _ = _classify_usability(info, "2025-01-01", "2025-12-31", "trade")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # task_004/local_trades_2025_v2.csv
    p = base / "task_004" / "local_trades_2025_v2.csv"
    info = _probe_csv(p, "local_trade_csv_v2", ["trade_date", "date", "time"])
    ut, ue, ev, _ = _classify_usability(info, "2025-01-01", "2025-12-31", "trade")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # task_003/jq_trades_normalized.csv (2026 fragment)
    p = base / "task_003" / "jq_trades_normalized.csv"
    info = _probe_csv(p, "jq_trade_csv_cleaned_2026", ["trade_date", "date"])
    ut, ue, ev, _ = _classify_usability(info, "2026-05-01", "2026-06-23", "trade")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # task_003/jq_portfolio_normalized.csv (2026 fragment equity)
    p = base / "task_003" / "jq_portfolio_normalized.csv"
    info = _probe_csv(p, "jq_portfolio_csv_cleaned_2026", ["record_date", "date"])
    ut, ue, ev, _ = _classify_usability(info, "2026-05-01", "2026-06-23", "equity")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # task_003/jq_cash_enhanced.csv (2026 fragment cash)
    p = base / "task_003" / "jq_cash_enhanced.csv"
    info = _probe_csv(p, "jq_cash_csv_cleaned_2026", ["date"])
    ut, ue, ev, _ = _classify_usability(info, "2026-05-01", "2026-06-23", "equity")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # task_003/daily_alignment.csv
    p = base / "task_003" / "daily_alignment.csv"
    info = _probe_csv(p, "alignment_daily_2026", ["date"])
    ut, ue, ev, _ = _classify_usability(info, "2026-05-01", "2026-06-23", "equity")
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": ut,
        "usable_for_equity_reconcile": ue,
        "evidence_level": ev,
    })

    # task_003/first_divergence.json
    p = base / "task_003" / "first_divergence.json"
    info = {
        "exists": p.exists(), "data_type": "first_divergence_json",
        "start_date": "", "end_date": "", "row_count": 0,
        "has_trade_price": False, "has_trade_qty": False, "has_trade_fee": False,
        "has_cash": False, "has_total_asset": False, "has_position_market_value": False,
        "has_position_detail": False, "is_full_period": False, "notes": "",
    }
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            info["start_date"] = d.get("first_divergence_date", "")
            info["end_date"] = d.get("first_divergence_date", "")
            info["row_count"] = 1
            info["notes"] = f"first_div_date={d.get('first_divergence_date')}, sec={d.get('security')}"
        except Exception as e:
            info["notes"] = f"PARSE_ERROR: {e}"
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": False,
        "usable_for_equity_reconcile": False,
        "evidence_level": "C",
    })

    # ---- 3. r3_full reference outputs (for context, NOT for direct slice use) ----
    r3_dir = base / "task_005_optimize" / "runs" / "r3_full_2020_202605_research"
    for fname, dtype, date_cols in [
        ("equity.csv", "r3_full_equity_reference", ["date"]),
        ("trades.csv", "r3_full_trades_reference", ["time"]),
        ("closed_trades.csv", "r3_full_closed_trades_reference", ["entry_time", "exit_time", "time"]),
    ]:
        p = r3_dir / fname
        info = _probe_csv(p, dtype, date_cols)
        # r3_full is a 2020-2026 cumulative run; mark NOT usable as standalone local baseline
        rows.append({
            "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
            **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                     "has_trade_price", "has_trade_qty", "has_trade_fee",
                                     "has_cash", "has_total_asset", "has_position_market_value",
                                     "has_position_detail", "is_full_period", "notes")},
            "usable_for_trade_reconcile": False,
            "usable_for_equity_reconcile": False,
            "evidence_level": "C",
        })

    # ---- 4. r2_missing_202606_research (potential 2026 fragment reference, but NOT same-start) ----
    r2_dir = base / "task_005_optimize" / "runs" / "r2_missing_202606_research"
    p = r2_dir / "manifest.json"
    info = {
        "exists": p.exists(), "data_type": "r2_missing_202606_manifest",
        "start_date": "", "end_date": "", "row_count": 0,
        "has_trade_price": False, "has_trade_qty": False, "has_trade_fee": False,
        "has_cash": False, "has_total_asset": False, "has_position_market_value": False,
        "has_position_detail": False, "is_full_period": False, "notes": "",
    }
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            info["start_date"] = d.get("start_date", "")
            info["end_date"] = d.get("end_date", "")
            info["row_count"] = 1
            info["notes"] = f"engine_mode={d.get('engine_mode')}, init_cash={d.get('initial_cash')}"
        except Exception as e:
            info["notes"] = f"PARSE_ERROR: {e}"
    rows.append({
        "file_path": str(p.relative_to(PROJECT_ROOT)) if p.exists() else str(p.name),
        **{k: info[k] for k in ("exists", "data_type", "start_date", "end_date", "row_count",
                                 "has_trade_price", "has_trade_qty", "has_trade_fee",
                                 "has_cash", "has_total_asset", "has_position_market_value",
                                 "has_position_detail", "is_full_period", "notes")},
        "usable_for_trade_reconcile": False,
        "usable_for_equity_reconcile": False,
        "evidence_level": "C",
    })

    # ---- Write CSV ----
    out_csv = OUTPUT_DIR / "DATA_INVENTORY_R1.csv"
    fieldnames = [
        "file_path", "exists", "data_type", "start_date", "end_date", "row_count",
        "has_trade_price", "has_trade_qty", "has_trade_fee", "has_cash",
        "has_total_asset", "has_position_market_value", "has_position_detail",
        "is_full_period", "usable_for_trade_reconcile", "usable_for_equity_reconcile",
        "evidence_level", "notes",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    print(f"\nWrote: {out_csv}  ({len(rows)} rows)")

    # ---- Write MD ----
    out_md = OUTPUT_DIR.parent / "DATA_INVENTORY_R1.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# TASK-006G-R1 Stage 1: Data Inventory\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("## Inventory Summary\n\n")
        f.write("| File | Exists | Type | Start | End | Rows | Trade? | Equity? | Evidence |\n")
        f.write("|------|--------|------|-------|-----|------|--------|---------|----------|\n")
        for r in rows:
            f.write("| {} | {} | {} | {} | {} | {} | {} | {} | {} |\n".format(
                r.get("file_path", ""),
                r.get("exists", ""),
                r.get("data_type", ""),
                r.get("start_date", ""),
                r.get("end_date", ""),
                r.get("row_count", ""),
                r.get("usable_for_trade_reconcile", ""),
                r.get("usable_for_equity_reconcile", ""),
                r.get("evidence_level", ""),
            ))
        f.write("\n## Key Findings\n\n")

        # Key findings
        f.write("### 1. 2025 Trade Records\n\n")
        for r in rows:
            if "2025" in r.get("file_path", "") and "trade" in r.get("data_type", "").lower():
                f.write("- `{}`: exists={}, {} rows, {}~{}\n".format(
                    r["file_path"], r["exists"], r["row_count"], r["start_date"], r["end_date"]))
        f.write("\n### 2. 2025 Equity/Cash Records\n\n")
        for r in rows:
            if "2025" in r.get("file_path", "") and ("portfolio" in r.get("data_type", "").lower() or "equity" in r.get("data_type", "").lower()):
                f.write("- `{}`: exists={}, {} rows, {}~{}\n".format(
                    r["file_path"], r["exists"], r["row_count"], r["start_date"], r["end_date"]))
        f.write("\n### 3. 2026 Fragment Trade Records\n\n")
        for r in rows:
            if "2026" in r.get("file_path", "") and "trade" in r.get("data_type", "").lower():
                f.write("- `{}`: exists={}, {} rows, {}~{}\n".format(
                    r["file_path"], r["exists"], r["row_count"], r["start_date"], r["end_date"]))
        f.write("\n### 4. 2026 Fragment Equity/Cash Records\n\n")
        for r in rows:
            if "2026" in r.get("file_path", "") and ("portfolio" in r.get("data_type", "").lower() or "equity" in r.get("data_type", "").lower() or "cash" in r.get("data_type", "").lower()):
                f.write("- `{}`: exists={}, {} rows, {}~{}\n".format(
                    r["file_path"], r["exists"], r["row_count"], r["start_date"], r["end_date"]))

        f.write("\n### 5. Local Reference Runs (NOT for direct slice use)\n\n")
        for r in rows:
            if "reference" in r.get("data_type", ""):
                f.write("- `{}`: exists={}, {} rows, {}~{}\n".format(
                    r["file_path"], r["exists"], r["row_count"], r["start_date"], r["end_date"]))

        f.write("\n## Implications for Strict Reconciliation\n\n")
        # Determine key implications
        h1_only_2025 = False
        for r in rows:
            if "20250101" in r.get("file_path", "") and "portfolio" in r.get("data_type", "").lower():
                if r["exists"] and r["end_date"] <= "2025-06-30":
                    h1_only_2025 = True
        if h1_only_2025:
            f.write("- **2025 equity records only cover H1**: full-year A-level equity reconciliation NOT possible; "
                    "will downgrade 2025 H1 equity to A/B and full-year equity to C.\n")
        f.write("- **r3_full outputs are reference-only**: cannot be used as same-start baseline; "
                "must rerun local backtest from 2025-01-01 / 2026-05-01 with empty portfolio.\n")
        f.write("- **task_003 normalized CSVs are preferred** for 2026 fragment (already cleaned).\n")
        f.write("- **task_004 jq_trades_2025.csv is preferred** for 2025 trade reconciliation.\n")

    print(f"Wrote: {out_md}")
    print("\n=== Data Inventory Complete ===")


if __name__ == "__main__":
    main()
