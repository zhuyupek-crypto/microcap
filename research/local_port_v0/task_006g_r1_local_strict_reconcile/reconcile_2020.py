#!/usr/bin/env python3
"""
TASK-006G-R1 extension: 2020 strict reconciliation
===================================================
Parse newly provided 2020 JQ logs and reconcile with local r3_full backtest.

Inputs:
- 母版交易记录-20200101-20210319.txt   (trades 2020-01-02 ~ 2021-03-19)
- 母版持仓&资金记录-20200101-20200611.txt (portfolio 2020-01-02 ~ 2020-06-01)
- r3_full_2020_202605_research/equity.csv  (local backtest)
- r3_full_2020_202605_research/trades.csv  (local trades)

Outputs (under outputs/):
- JQ_2020_TRADES_NORMALIZED.csv
- JQ_2020_EQUITY_NORMALIZED.csv
- LOCAL_2020_TRADES.csv
- LOCAL_2020_EQUITY.csv
- TRADE_RECON_2020.csv
- EQUITY_RECON_2020.csv
- DIFF_ATTRIBUTION_2020.csv

Note: r3_full is a cumulative backtest from 2020-01-02, so the 2020 slice IS
a same-start-point independent backtest (no prior accumulation). This is A-level.
"""
import csv
import re
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(r"D:\Work Space\他山之石\微盘股")
TASK_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_006g_r1_local_strict_reconcile"
OUTPUT_DIR = TASK_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JQ_TRADES_TXT = PROJECT_ROOT / "母版交易记录-20200101-20210319.txt"
JQ_PORTFOLIO_TXT = PROJECT_ROOT / "母版持仓&资金记录-20200101-20200611.txt"
LOCAL_EQUITY = PROJECT_ROOT / "research" / "local_port_v0" / "task_005_optimize" / "runs" / "r3_2020_minute_close" / "equity.csv"
LOCAL_TRADES = PROJECT_ROOT / "research" / "local_port_v0" / "task_005_optimize" / "runs" / "r3_2020_minute_close" / "trades.csv"

# Period definitions
TRADE_PERIOD_START = "2020-01-02"
TRADE_PERIOD_END = "2021-03-19"
EQUITY_PERIOD_START = "2020-01-02"
EQUITY_PERIOD_END = "2020-06-01"


# ---------------------------------------------------------------------------
# Trade log parser (reused from parse_jq_logs_r1.py logic)
# ---------------------------------------------------------------------------
def _parse_number(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s or s == "-":
        return None
    s = re.sub(r"[,\s股元]", "", s)
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def _extract_code(name_field):
    m = re.search(r"\(([^)]+)\)", name_field)
    if m:
        code = m.group(1)
        name = name_field[:m.start()].strip()
        return name, code
    return name_field.strip(), ""


def parse_trade_txt(txt_path):
    rows = []
    if not txt_path.exists():
        print(f"WARNING: {txt_path} not found")
        return rows
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    src_name = txt_path.name
    for i, line in enumerate(lines, 1):
        s = line.rstrip("\n").rstrip("\r")
        if not s.strip():
            continue
        if not re.match(r"^\d{4}-\d{2}-\d{2}\t", s):
            continue
        parts = s.split("\t")
        if len(parts) < 10:
            continue
        try:
            date = parts[0].strip()
            time = parts[1].strip()
            name_field = parts[2].strip()
            side_zh = parts[3].strip()
            order_type = parts[4].strip() if len(parts) > 4 else ""
            qty_str = parts[5].strip() if len(parts) > 5 else ""
            price_str = parts[6].strip() if len(parts) > 6 else ""
            gross_str = parts[7].strip() if len(parts) > 7 else ""
            pnl_str = parts[8].strip() if len(parts) > 8 else ""
            fee_str = parts[9].strip() if len(parts) > 9 else ""

            name, code = _extract_code(name_field)
            side = "buy" if side_zh == "买" else ("sell" if side_zh == "卖" else "unknown")
            quantity = _parse_number(qty_str)
            price = _parse_number(price_str)
            gross_amount = _parse_number(gross_str)
            commission = _parse_number(fee_str)

            parse_status = "parsed"
            if quantity is None:
                parse_status = "missing_quantity"
                quantity = 0
            if price is None:
                parse_status = "missing_price"
            if quantity == 0 and gross_amount not in (None, 0):
                parse_status = "jq_qty_zero_export_defect"

            net_amount = None
            if gross_amount is not None:
                fee = commission if commission is not None else 0
                if side == "buy":
                    net_amount = gross_amount + fee
                else:
                    net_amount = gross_amount - fee

            rows.append({
                "date": date,
                "time": time,
                "code": code,
                "name": name,
                "side": side,
                "quantity": quantity,
                "price": price,
                "gross_amount": gross_amount,
                "commission": commission if commission is not None else 0,
                "stamp_tax": 0,
                "transfer_fee": 0,
                "net_amount": net_amount,
                "source_file": src_name,
                "source_line_no": i,
                "raw_text": s[:200],
                "parse_status": parse_status,
            })
        except Exception as e:
            rows.append({
                "date": parts[0].strip() if parts else "",
                "time": "",
                "code": "",
                "name": "",
                "side": "unknown",
                "quantity": None,
                "price": None,
                "gross_amount": None,
                "commission": 0,
                "stamp_tax": 0,
                "transfer_fee": 0,
                "net_amount": None,
                "source_file": src_name,
                "source_line_no": i,
                "raw_text": s[:200],
                "parse_status": f"parse_error: {e}",
            })
    return rows


# ---------------------------------------------------------------------------
# Portfolio parser
# ---------------------------------------------------------------------------
def parse_portfolio_txt(txt_path):
    """Parse JQ portfolio txt. Returns (account_rows, position_rows)."""
    account_rows = []
    position_rows = []
    if not txt_path.exists():
        print(f"WARNING: {txt_path} not found")
        return account_rows, position_rows
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    src_name = txt_path.name
    current_date = None
    current_positions = []
    for i, line in enumerate(lines, 1):
        s = line.rstrip("\n").rstrip("\r")
        if not s.strip():
            continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2})$", s.strip())
        if m:
            if current_date and current_positions:
                _flush_day(account_rows, position_rows, current_date, current_positions, src_name)
            current_date = m.group(1)
            current_positions = []
            continue
        if current_date is None:
            continue
        parts = s.split("\t")
        if len(parts) < 4:
            continue
        name_field = parts[0].strip()
        qty_str = parts[1].strip() if len(parts) > 1 else ""
        price_str = parts[2].strip() if len(parts) > 2 else ""
        value_str = parts[3].strip() if len(parts) > 3 else ""
        pnl_str = parts[4].strip() if len(parts) > 4 else ""

        if name_field.startswith("Cash"):
            cash = _parse_number(value_str)
            current_positions.append({
                "type": "cash",
                "name": "Cash",
                "code": "CASH",
                "qty": None,
                "price": None,
                "value": cash,
                "pnl": _parse_number(pnl_str),
            })
        elif "总共" in name_field or "总共" in value_str or "总共" in qty_str or "总共" in price_str:
            # Total row format: " \t \t \t总共:1,000,069.30\t69.30"
            # The "总共:XXX" may appear in value_str or other fields
            total_str = value_str
            if "总共" not in total_str:
                # Search all fields for 总共
                for p in parts:
                    if "总共" in p:
                        total_str = p.strip()
                        break
            # Extract number after "总共:"
            m_total = re.search(r"总共[:：]?\s*([\d,\.]+)", total_str)
            total = _parse_number(m_total.group(1)) if m_total else _parse_number(total_str.replace("总共", "").replace(":", "").replace("：", ""))
            current_positions.append({
                "type": "total",
                "name": "Total",
                "code": "TOTAL",
                "qty": None,
                "price": None,
                "value": total,
                "pnl": _parse_number(pnl_str),
            })
        else:
            name, code = _extract_code(name_field)
            current_positions.append({
                "type": "position",
                "name": name,
                "code": code,
                "qty": _parse_number(qty_str),
                "price": _parse_number(price_str),
                "value": _parse_number(value_str),
                "pnl": _parse_number(pnl_str),
            })
    if current_date and current_positions:
        _flush_day(account_rows, position_rows, current_date, current_positions, src_name)
    return account_rows, position_rows


def _flush_day(account_rows, position_rows, date, positions, src_name):
    # First pass: extract day-level aggregates
    total_asset = None
    cash = None
    pos_count = 0
    pos_market_value = 0
    position_list = []
    for p in positions:
        if p["type"] == "total":
            total_asset = p["value"]
        elif p["type"] == "cash":
            cash = p["value"]
        elif p["type"] == "position":
            pos_count += 1
            if p["value"]:
                pos_market_value += p["value"]
            position_list.append(p)
    # Second pass: write position rows with full day-level aggregates
    for p in position_list:
        position_rows.append({
            "date": date,
            "time": "",
            "snapshot_type": "position",
            "total_asset": total_asset,
            "cash": cash,
            "available_cash": cash,
            "position_market_value_reported": pos_market_value,
            "position_market_value_calculated": pos_market_value,
            "position_count": pos_count,
            "code": p["code"],
            "position_qty": p["qty"],
            "available_qty": p["qty"],
            "market_price": p["price"],
            "market_value": p["value"],
            "source_file": src_name,
            "source_line_no": 0,
            "parse_status": "parsed",
        })
    account_rows.append({
        "date": date,
        "time": "",
        "snapshot_type": "account",
        "total_asset": total_asset,
        "cash": cash,
        "available_cash": cash,
        "position_market_value_reported": pos_market_value,
        "position_market_value_calculated": pos_market_value,
        "position_count": pos_count,
        "code": "",
        "position_qty": None,
        "available_qty": None,
        "market_price": None,
        "market_value": None,
        "source_file": src_name,
        "source_line_no": 0,
        "parse_status": "parsed",
    })


# ---------------------------------------------------------------------------
# Reconcile trades
# ---------------------------------------------------------------------------
def load_local_trades():
    df = pd.read_csv(LOCAL_TRADES)
    df['time'] = pd.to_datetime(df['time'])
    df['date'] = df['time'].dt.strftime('%Y-%m-%d')
    df['time_str'] = df['time'].dt.strftime('%H:%M')
    # Filter to trade period
    df = df[(df['date'] >= TRADE_PERIOD_START) & (df['date'] <= TRADE_PERIOD_END)].copy()
    # Normalize: amount > 0 = buy, amount < 0 = sell
    df['side'] = df['amount'].apply(lambda x: 'buy' if x > 0 else 'sell')
    df['quantity'] = df['amount'].abs()
    df['gross_amount'] = df['quantity'] * df['price']
    return df[['date', 'time_str', 'code', 'side', 'quantity', 'price', 'gross_amount', 'commission', 'tax']].copy()


def reconcile_trades(jq_trades_df, local_trades_df):
    """Three-level matching."""
    results = []
    # Group by date+code+side
    jq_grouped = {}
    for _, row in jq_trades_df.iterrows():
        key = (row['date'], row['code'], row['side'])
        jq_grouped.setdefault(key, []).append(row)
    local_grouped = {}
    for _, row in local_trades_df.iterrows():
        key = (row['date'], row['code'], row['side'])
        local_grouped.setdefault(key, []).append(row)

    all_keys = set(jq_grouped.keys()) | set(local_grouped.keys())
    for key in sorted(all_keys):
        date, code, side = key
        jq_rows = jq_grouped.get(key, [])
        local_rows = local_grouped.get(key, [])
        # Use absolute values for quantity comparison (JQ sell qty is negative, local is positive)
        jq_total_qty = sum(abs(r['quantity']) for r in jq_rows) if jq_rows else 0
        local_total_qty = sum(abs(r['quantity']) for r in local_rows) if local_rows else 0
        jq_qty_signed = sum(r['quantity'] for r in jq_rows) if jq_rows else 0
        local_qty_signed = sum(r['quantity'] for r in local_rows) if local_rows else 0
        # Weighted avg price using absolute quantities
        jq_avg_price = (sum(abs(r['quantity']) * r['price'] for r in jq_rows) / jq_total_qty) if jq_total_qty > 0 else None
        local_avg_price = (sum(abs(r['quantity']) * r['price'] for r in local_rows) / local_total_qty) if local_total_qty > 0 else None
        # Gross amount: take absolute for comparison
        jq_gross = sum(abs(r['gross_amount']) for r in jq_rows) if jq_rows else 0
        local_gross = sum(abs(r['gross_amount']) for r in local_rows) if local_rows else 0

        if not jq_rows:
            match_status = "missing_in_jq"
        elif not local_rows:
            match_status = "missing_in_local"
        elif jq_total_qty == local_total_qty and jq_avg_price and local_avg_price and abs(jq_avg_price - local_avg_price) < 0.001:
            match_status = "exact_match"
        elif jq_total_qty == local_total_qty:
            match_status = "price_diff"
        elif jq_avg_price and local_avg_price and abs(jq_avg_price - local_avg_price) < 0.001:
            match_status = "quantity_diff"
        else:
            match_status = "price_and_quantity_diff"

        results.append({
            'date': date,
            'code': code,
            'side': side,
            'jq_quantity': jq_total_qty,
            'local_quantity': local_total_qty,
            'quantity_diff': local_total_qty - jq_total_qty,
            'jq_price': jq_avg_price,
            'local_price': local_avg_price,
            'price_diff': (local_avg_price - jq_avg_price) if (jq_avg_price and local_avg_price) else None,
            'jq_gross_amount': jq_gross,
            'local_gross_amount': local_gross,
            'gross_amount_diff': local_gross - jq_gross,
            'jq_commission': sum(r['commission'] for r in jq_rows) if jq_rows else 0,
            'local_commission': sum(r['commission'] for r in local_rows) if local_rows else 0,
            'jq_tax': sum(r.get('stamp_tax', 0) for r in jq_rows) if jq_rows else 0,
            'local_tax': sum(r['tax'] for r in local_rows) if local_rows else 0,
            'match_status': match_status,
            'diff_reason': 'unknown',
        })
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Reconcile equity
# ---------------------------------------------------------------------------
def load_local_equity():
    df = pd.read_csv(LOCAL_EQUITY)
    df['date'] = df['date'].astype(str)
    df = df[(df['date'] >= EQUITY_PERIOD_START) & (df['date'] <= EQUITY_PERIOD_END)].copy()
    return df


def reconcile_equity(jq_equity_df, local_equity_df):
    jq = jq_equity_df[['date', 'total_asset', 'cash', 'position_market_value_calculated', 'position_count']].copy()
    jq.columns = ['date', 'jq_total_asset', 'jq_cash', 'jq_position_value', 'jq_position_count']
    # Detect truncated JQ days: position_count drops >50% from prior day AND cash is NaN
    jq['is_truncated'] = False
    for i in range(1, len(jq)):
        prev_count = jq.loc[i-1, 'jq_position_count']
        cur_count = jq.loc[i, 'jq_position_count']
        cur_cash_nan = pd.isna(jq.loc[i, 'jq_cash'])
        if prev_count > 0 and cur_count < prev_count * 0.5 and cur_cash_nan:
            jq.loc[i, 'is_truncated'] = True
    truncated_dates = jq[jq['is_truncated']]['date'].tolist()
    if truncated_dates:
        print(f"  WARNING: Detected {len(truncated_dates)} truncated JQ equity day(s): {truncated_dates}")
        print(f"  These will be excluded from reconciliation stats.")
        jq = jq[~jq['is_truncated']].copy()
    local = local_equity_df.copy()
    local.columns = ['date', 'local_total_asset']
    merged = pd.merge(jq, local, on='date', how='outer')
    merged['asset_diff'] = merged['local_total_asset'] - merged['jq_total_asset']
    merged['asset_diff_pct'] = (merged['asset_diff'] / merged['jq_total_asset'] * 100).round(4)
    merged['cash_diff'] = None  # local doesn't have cash separately in equity.csv
    merged['position_value_diff'] = None
    merged['position_count_diff'] = None
    # Daily returns (NaN-safe)
    merged['jq_daily_return'] = merged['jq_total_asset'].pct_change()
    merged['local_daily_return'] = merged['local_total_asset'].pct_change()
    merged['daily_return_diff'] = merged['local_daily_return'] - merged['jq_daily_return']
    # Cum returns (NaN-safe: forward fill start)
    jq_start = merged['jq_total_asset'].iloc[0]
    local_start = merged['local_total_asset'].iloc[0]
    if pd.isna(jq_start) or pd.isna(local_start):
        # Find first valid
        first_valid = merged.dropna(subset=['jq_total_asset', 'local_total_asset'])
        if len(first_valid) > 0:
            jq_start = first_valid['jq_total_asset'].iloc[0]
            local_start = first_valid['local_total_asset'].iloc[0]
            print(f"  WARNING: first row had NaN, using start jq={jq_start}, local={local_start}")
        else:
            jq_start = 1
            local_start = 1
    merged['jq_cum_return'] = (merged['jq_total_asset'] / jq_start - 1) * 100
    merged['local_cum_return'] = (merged['local_total_asset'] / local_start - 1) * 100
    merged['cum_return_diff'] = merged['local_cum_return'] - merged['jq_cum_return']
    merged['match_status'] = merged['asset_diff'].abs().apply(
        lambda x: 'exact_match' if (pd.notna(x) and abs(x) < 1) else ('small_diff' if (pd.notna(x) and abs(x) < 1000) else 'large_diff')
    )
    return merged


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("TASK-006G-R1 2020 Strict Reconciliation")
    print("=" * 70)

    # 1. Parse JQ trades
    print("\n[1] Parsing JQ trades...")
    jq_trades = parse_trade_txt(JQ_TRADES_TXT)
    jq_trades_df = pd.DataFrame(jq_trades)
    print(f"  Parsed {len(jq_trades_df)} JQ trades")
    print(f"  Date range: {jq_trades_df['date'].min()} ~ {jq_trades_df['date'].max()}")
    jq_trades_df.to_csv(OUTPUT_DIR / "JQ_2020_TRADES_NORMALIZED.csv", index=False)
    print(f"  Saved: JQ_2020_TRADES_NORMALIZED.csv")

    # 2. Parse JQ portfolio
    print("\n[2] Parsing JQ portfolio...")
    jq_account, jq_positions = parse_portfolio_txt(JQ_PORTFOLIO_TXT)
    jq_equity_df = pd.DataFrame(jq_account)
    print(f"  Parsed {len(jq_equity_df)} account days, {len(jq_positions)} position rows")
    print(f"  Date range: {jq_equity_df['date'].min()} ~ {jq_equity_df['date'].max()}")
    jq_equity_all = pd.concat([jq_equity_df, pd.DataFrame(jq_positions)], ignore_index=True)
    jq_equity_all.to_csv(OUTPUT_DIR / "JQ_2020_EQUITY_NORMALIZED.csv", index=False)
    print(f"  Saved: JQ_2020_EQUITY_NORMALIZED.csv")

    # 3. Load local trades
    print("\n[3] Loading local trades...")
    local_trades_df = load_local_trades()
    print(f"  Loaded {len(local_trades_df)} local trades")
    print(f"  Date range: {local_trades_df['date'].min()} ~ {local_trades_df['date'].max()}")
    local_trades_df.to_csv(OUTPUT_DIR / "LOCAL_2020_TRADES.csv", index=False)
    print(f"  Saved: LOCAL_2020_TRADES.csv")

    # 4. Load local equity
    print("\n[4] Loading local equity...")
    local_equity_df = load_local_equity()
    print(f"  Loaded {len(local_equity_df)} local equity days")
    local_equity_df.to_csv(OUTPUT_DIR / "LOCAL_2020_EQUITY.csv", index=False)
    print(f"  Saved: LOCAL_2020_EQUITY.csv")

    # 5. Reconcile trades
    print("\n[5] Reconciling trades...")
    trade_recon = reconcile_trades(jq_trades_df, local_trades_df)
    trade_recon.to_csv(OUTPUT_DIR / "TRADE_RECON_2020.csv", index=False)
    print(f"  Saved: TRADE_RECON_2020.csv ({len(trade_recon)} rows)")
    # Stats
    total_jq = len(jq_trades_df)
    total_local = len(local_trades_df)
    exact = len(trade_recon[trade_recon['match_status'] == 'exact_match'])
    missing_local = len(trade_recon[trade_recon['match_status'] == 'missing_in_local'])
    missing_jq = len(trade_recon[trade_recon['match_status'] == 'missing_in_jq'])
    price_diff = len(trade_recon[trade_recon['match_status'] == 'price_diff'])
    qty_diff = len(trade_recon[trade_recon['match_status'] == 'quantity_diff'])
    both_diff = len(trade_recon[trade_recon['match_status'] == 'price_and_quantity_diff'])
    print(f"  Total JQ trades: {total_jq}")
    print(f"  Total local trades: {total_local}")
    print(f"  Exact match: {exact} ({exact/len(trade_recon)*100:.1f}%)")
    print(f"  Missing in local: {missing_local}")
    print(f"  Missing in JQ: {missing_jq}")
    print(f"  Price diff: {price_diff}")
    print(f"  Quantity diff: {qty_diff}")
    print(f"  Price+Qty diff: {both_diff}")
    # First divergence
    non_match = trade_recon[trade_recon['match_status'] != 'exact_match']
    if len(non_match) > 0:
        first_div = non_match.iloc[0]
        print(f"  First divergence: {first_div['date']} {first_div['code']} {first_div['side']} ({first_div['match_status']})")

    # 6. Reconcile equity
    print("\n[6] Reconciling equity...")
    equity_recon = reconcile_equity(jq_equity_df, local_equity_df)
    equity_recon.to_csv(OUTPUT_DIR / "EQUITY_RECON_2020.csv", index=False)
    print(f"  Saved: EQUITY_RECON_2020.csv ({len(equity_recon)} rows)")
    # Stats (NaN-safe: drop rows where either is NaN)
    valid = equity_recon.dropna(subset=['jq_total_asset', 'local_total_asset']).copy()
    if len(valid) == 0:
        print("  ERROR: no valid equity rows for stats")
    else:
        jq_start = valid['jq_total_asset'].iloc[0]
        jq_end = valid['jq_total_asset'].iloc[-1]
        local_start = valid['local_total_asset'].iloc[0]
        local_end = valid['local_total_asset'].iloc[-1]
        jq_return = (jq_end / jq_start - 1) * 100
        local_return = (local_end / local_start - 1) * 100
        corr_pairs = valid.dropna(subset=['jq_daily_return', 'local_daily_return'])
        corr = corr_pairs[['jq_daily_return', 'local_daily_return']].corr().iloc[0, 1] if len(corr_pairs) > 1 else float('nan')
        mean_diff = valid['asset_diff'].abs().mean()
        max_diff = valid['asset_diff'].abs().max()
        # Max drawdown
        jq_nav = valid['jq_total_asset'] / jq_start
        local_nav = valid['local_total_asset'] / local_start
        jq_dd = ((jq_nav - jq_nav.cummax()) / jq_nav.cummax()).min() * 100
        local_dd = ((local_nav - local_nav.cummax()) / local_nav.cummax()).min() * 100
        print(f"  Period: {valid['date'].iloc[0]} ~ {valid['date'].iloc[-1]} ({len(valid)} valid days)")
        print(f"  JQ start={jq_start:,.2f}, end={jq_end:,.2f}, return={jq_return:.4f}%")
        print(f"  Local start={local_start:,.2f}, end={local_end:,.2f}, return={local_return:.4f}%")
        print(f"  Return diff: {local_return - jq_return:.4f}%")
        print(f"  Daily return corr: {corr:.6f}")
        print(f"  Mean abs asset diff: {mean_diff:,.2f}")
        print(f"  Max abs asset diff: {max_diff:,.2f}")
        print(f"  JQ max_dd: {jq_dd:.4f}%")
        print(f"  Local max_dd: {local_dd:.4f}%")
    # First equity divergence
    large_diff = equity_recon[equity_recon['asset_diff'].abs() > 1]
    if len(large_diff) > 0:
        first_ediv = large_diff.iloc[0]
        print(f"  First equity divergence: {first_ediv['date']} diff={first_ediv['asset_diff']:,.2f}")

    # 7. Diff attribution
    print("\n[7] Diff attribution...")
    attributions = []
    # Categorize trade diffs
    for _, row in trade_recon.iterrows():
        if row['match_status'] == 'exact_match':
            continue
        reason = 'unknown'
        if row['match_status'] == 'missing_in_local':
            reason = 'missing_in_local'
        elif row['match_status'] == 'missing_in_jq':
            reason = 'missing_in_jq'
        elif row['match_status'] == 'price_diff':
            reason = 'trade_price_diff'
        elif row['match_status'] == 'quantity_diff':
            reason = 'trade_quantity_diff'
        elif row['match_status'] == 'price_and_quantity_diff':
            reason = 'trade_price_and_quantity_diff'
        attributions.append({
            'category': reason,
            'date': row['date'],
            'code': row['code'],
            'side': row['side'],
            'impact': row['gross_amount_diff'] if row['gross_amount_diff'] else 0,
        })
    attr_df = pd.DataFrame(attributions)
    if len(attr_df) > 0:
        attr_summary = attr_df.groupby('category').agg(
            count=('date', 'count'),
            first_date=('date', 'min'),
            last_date=('date', 'max'),
            sum_impact=('impact', 'sum'),
            max_impact=('impact', 'max'),
        ).reset_index()
    else:
        attr_summary = pd.DataFrame(columns=['category', 'count', 'first_date', 'last_date', 'sum_impact', 'max_impact'])
    attr_summary.to_csv(OUTPUT_DIR / "DIFF_ATTRIBUTION_2020.csv", index=False)
    print(f"  Saved: DIFF_ATTRIBUTION_2020.csv")
    print(attr_summary.to_string(index=False))

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
