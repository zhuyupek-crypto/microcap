#!/usr/bin/env python3
"""TASK-MICROCAP-003A-ADDENDUM: Supplementary audit."""
import os, sys, re, json, csv
from collections import defaultdict
from pathlib import Path
from datetime import datetime

sys.path.insert(0, r"D:\Work Space\HData\scripts\core")
sys.path.insert(0, r"D:\Work Space\local_quant")

OUTPUT_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")
DATA_DIR = Path(r"D:\Work Space\他山之石\微盘股")
HDATA_DIR = Path(r"D:\Work Space\HData")
LQ_DIR = Path(r"D:\Work Space\local_quant")

# ============================================================
# 1. Trading calendar
# ============================================================
def get_trade_calendar():
    """Get A-share trading calendar from HData."""
    try:
        import pandas as pd
        cal = pd.read_parquet(HDATA_DIR / "data" / "processed" / "metadata" / "calendar.parquet")
        print(f"Calendar loaded: {cal.shape}")
        print(f"Columns: {list(cal.columns)}")
        cal2026 = cal[(cal["date"] >= "2026-05-01") & (cal["date"] <= "2026-06-30")]
        # Check column name for trading day flag
        trade_col = None
        for c in ["is_trading_day", "is_open", "trade_date", "trading_day"]:
            if c in cal.columns:
                trade_col = c
                break
        if trade_col:
            trade_days = sorted(cal2026[cal2026[trade_col] == True]["date"].tolist())
            all_dates = sorted(cal2026["date"].tolist())
        else:
            # If no explicit flag, assume all dates are trading days
            trade_days = sorted(cal2026["date"].tolist())
            all_dates = trade_days
        print(f"Trade days 2026-05 to 06-30: {len(trade_days)}")
        return trade_days, all_dates
    except Exception as e:
        print(f"Calendar error: {e}")
        return None, None

# ============================================================
# 2. Defensive ETFs from frozen strategy
# ============================================================
def extract_defensive_etfs():
    """Extract defensive ETF codes from frozen strategy (read-only)."""
    fp = DATA_DIR / "微盘股-母版-20260627.py"
    with open(fp, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Look for defensive ETF definitions
    etfs = []
    # Pattern 1: g.defensive_etfs = [...]
    m = re.search(r'g\.defensive_etfs\s*=\s*\[([^\]]*)\]', text)
    if m:
        content = m.group(1)
        codes = re.findall(r"'([^']+)'|\"([^\"]+)\"", content)
        for c in codes:
            etfs.append(c[0] or c[1])
    
    # Pattern 2: hardcoded list
    m2 = re.search(r'defensive_etf\w*\s*=\s*\[([^\]]*)\]', text, re.IGNORECASE)
    if m2 and not etfs:
        content = m2.group(1)
        codes = re.findall(r"'([^']+)'|\"([^\"]+)\"", content)
        for c in codes:
            etfs.append(c[0] or c[1])
    
    return etfs

# ============================================================
# 3. Initial cash search
# ============================================================
def search_initial_cash():
    """Search for initial cash evidence in the project."""
    results = []
    
    # Check task reports
    report_dir = DATA_DIR / "research" / "local_migration" / "reports"
    if report_dir.exists():
        for fp in report_dir.glob("*.md"):
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read()
            m = re.search(r'initial_cash|初始资金|起始资金|start_cash|100万|1,000,000', text)
            if m:
                results.append({"source": str(fp), "context": text[max(0, m.start()-50):m.end()+50]})
    
    # Check main task report
    report_fp = LQ_DIR / "reports" / "microcap" / "task002c" / "TASK-MICROCAP-002_REPORT.md"
    if report_fp.exists():
        with open(report_fp, "r", encoding="utf-8") as f:
            text = f.read()
        # Look for asset values on first day
        m = re.search(r'\d{4}-\d{2}-\d{2}.*?1[,.]?\d{3}', text)
        if m:
            results.append({"source": str(report_fp), "context": text[max(0, m.start()-50):m.end()+50]})
    
    return results

# ============================================================
# 4. Enhanced cash diagnostics
# ============================================================
def cash_diagnostics(trade_records, port_records):
    """Detailed cash residual analysis per date."""
    # Load parsed data
    from _parse_jq_records import (
        reconcile_cash, reconcile_positions
    )
    
    cash_recon = reconcile_cash(trade_records, port_records)
    
    stats = {
        "comparable_dates": len(cash_recon),
        "zero_diff_dates": sum(1 for r in cash_recon if r["cash_difference"] == 0),
        "non_zero_diff_dates": sum(1 for r in cash_recon if abs(r["cash_difference"] or 0) > 0),
        "abs_diffs": [abs(r["cash_difference"]) for r in cash_recon if r["cash_difference"] is not None],
        "dates_with_trades": [],
        "dates_without_trades": [],
    }
    
    if stats["abs_diffs"]:
        stats["min_abs_diff"] = min(stats["abs_diffs"])
        stats["max_abs_diff"] = max(stats["abs_diffs"])
        stats["median_abs_diff"] = sorted(stats["abs_diffs"])[len(stats["abs_diffs"])//2]
        stats["mean_abs_diff"] = sum(stats["abs_diffs"]) / len(stats["abs_diffs"])
    
    for r in cash_recon:
        r["has_trade"] = (r["buy_amount"] or 0) > 0 or (r["sell_amount"] or 0) > 0
        if r["has_trade"]:
            stats["dates_with_trades"].append(r)
        else:
            stats["dates_without_trades"].append(r)
    
    return cash_recon, stats

# ============================================================
# 5. 301098 duplicate analysis
# ============================================================
def analyze_301098_duplicate(trade_records, port_records):
    """Analyze the 301098.XSHE 2026-06-09 duplicate trade."""
    results = {}
    
    # Find the duplicate trades
    dup_trades = [r for r in trade_records 
                  if r["normalized_security_code"] == "301098.XSHE" 
                  and r["trade_date"] == "2026-06-09"
                  and r["quantity"] == 100 and r["price"] == 8.26]
    
    results["trades_found"] = len(dup_trades)
    results["trades"] = dup_trades
    
    # Get positions before (06-08), during (06-09), and after (06-10)
    pos_by_date = defaultdict(lambda: defaultdict(int))
    for p in port_records:
        if p["snapshot_type"] == "position" and p["normalized_security_code"]:
            pos_by_date[p["record_date"]][p["normalized_security_code"]] = p["position_quantity"] or 0
    
    before_date = "2026-06-08"
    on_date = "2026-06-09"
    after_date = "2026-06-10"
    
    for d in [before_date, on_date, after_date]:
        qty = pos_by_date.get(d, {}).get("301098.XSHE", "NO_SNAPSHOT")
        results[f"position_{d}"] = qty
    
    # Check other positions in same period
    # ... 
    
    return results

# ============================================================
# 6. First and last portfolio snapshot
# ============================================================
def full_snapshot(port_records, date):
    """Get complete portfolio state for a given date."""
    cash = None
    total = None
    positions = []
    
    for p in port_records:
        if p["record_date"] != date:
            continue
        if p["snapshot_type"] == "cash_summary":
            cash = p["available_cash"]
        elif p["snapshot_type"] == "total_summary":
            total = p["total_asset"]
        elif p["snapshot_type"] == "position" and p["normalized_security_code"]:
            positions.append({
                "code": p["normalized_security_code"],
                "name": p["security_name"],
                "quantity": p["position_quantity"],
                "price": p["market_price"],
                "market_value": p["market_value"],
                "pnl": p["pnl"],
            })
    
    total_mv = sum(p["market_value"] or 0 for p in positions)
    return {
        "date": date,
        "cash": cash,
        "total_asset": total,
        "position_market_value": total_mv,
        "num_positions": len(positions),
        "positions": positions,
        "snapshot_time_known": False,
        "snapshot_type": "SNAPSHOT_TIME_UNKNOWN",
    }

# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("TASK-MICROCAP-003A-ADDENDUM")
    print("=" * 60)
    
    # 1. Trading calendar
    print("\n[1] Trading calendar...")
    trade_days, all_dates = get_trade_calendar()
    if trade_days:
        print(f"  Trade days 2026-05-01~06-24: {len(trade_days)}")
        print(f"  First: {trade_days[0]}, Last: {trade_days[-1]}")
    else:
        print("  WARNING: Could not load trading calendar from HData")
    
    # 2. Defensive ETFs from frozen strategy
    print("\n[2] Defensive ETFs from frozen strategy...")
    etfs = extract_defensive_etfs()
    print(f"  Found: {etfs}")
    
    # 3. Initial cash search
    print("\n[3] Initial cash search...")
    cash_evidence = search_initial_cash()
    if cash_evidence:
        for e in cash_evidence:
            print(f"  Found in {e['source']}: {e['context'][:100]}")
    else:
        print("  No initial cash evidence found")
    
    # Load parsed data
    from _parse_jq_records import parse_trade_records, parse_portfolio_records
    trade_records, trade_errors, _ = parse_trade_records()
    port_records, port_errors = parse_portfolio_records()
    
    # 4. Cash diagnostics
    print("\n[4] Cash residual diagnostics...")
    cash_recon, cash_stats = cash_diagnostics(trade_records, port_records)
    print(f"  Comparable dates: {cash_stats['comparable_dates']}")
    print(f"  Zero diff: {cash_stats['zero_diff_dates']}")
    print(f"  Non-zero diff: {cash_stats['non_zero_diff_dates']}")
    if "abs_diffs" in cash_stats and cash_stats["abs_diffs"]:
        print(f"  Min abs diff: {cash_stats['min_abs_diff']}")
        print(f"  Median abs diff: {cash_stats['median_abs_diff']}")
        print(f"  Max abs diff: {cash_stats['max_abs_diff']}")
        print(f"  Mean abs diff: {cash_stats['mean_abs_diff']:.2f}")
    
    # Export enhanced cash reconciliation
    enhanced_fields = [
        "date", "opening_cash", "buy_amount", "sell_amount",
        "reported_fees", "reported_other_fees", "expected_closing_cash",
        "observed_closing_cash", "cash_difference",
        "has_buy", "has_sell", "has_trade"
    ]
    with open(OUTPUT_DIR / "jq_cash_enhanced.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=enhanced_fields, extrasaction="ignore")
        writer.writeheader()
        for r in cash_recon:
            r["has_buy"] = (r["buy_amount"] or 0) > 0
            r["has_sell"] = (r["sell_amount"] or 0) > 0
            r["reported_other_fees"] = None
            r["cash_difference"] = r.get("cash_difference")
            writer.writerow(r)
    
    # 5. 301098 duplicate
    print("\n[5] 301098 duplicate analysis...")
    dup_results = analyze_301098_duplicate(trade_records, port_records)
    print(f"  Trades found: {dup_results['trades_found']}")
    for k, v in dup_results.items():
        if k.startswith("position_"):
            print(f"  {k}: {v}")
    
    # Determine which口径 works
    if dup_results["trades_found"] >= 2:
        # Check if both trades are needed for position reconciliation
        before_qty = dup_results.get("position_2026-06-08")
        on_qty = dup_results.get("position_2026-06-09")
        after_qty = dup_results.get("position_2026-06-10")
        
        if before_qty is not None and on_qty is not None and after_qty is not None:
            if isinstance(before_qty, int) and isinstance(on_qty, int):
                # One trade: before + 100 = ?
                # Two trades: before + 200 = ?
                # Check which matches
                one_trade_expected = before_qty + 100
                two_trade_expected = before_qty + 200
                print(f"  One trade expected: {one_trade_expected}, On date: {on_qty}, Two trade expected: {two_trade_expected}")
    
    # 6. First and last snapshots
    print("\n[6] First and last portfolio snapshots...")
    port_dates = sorted(set(p["record_date"] for p in port_records if p["record_date"]))
    first_date = port_dates[0]
    last_date = port_dates[-1]
    
    first_state = full_snapshot(port_records, first_date)
    last_state = full_snapshot(port_records, last_date)
    
    print(f"  First date: {first_state['date']}")
    print(f"    Cash: {first_state['cash']}")
    print(f"    Total asset: {first_state['total_asset']}")
    print(f"    Position MV: {first_state['position_market_value']}")
    print(f"    Positions ({first_state['num_positions']}):")
    for p in first_state['positions']:
        print(f"      {p['code']} {p['name']} qty={p['quantity']} mv={p['market_value']}")
    
    print(f"  Last date: {last_state['date']}")
    print(f"    Cash: {last_state['cash']}")
    print(f"    Total asset: {last_state['total_asset']}")
    print(f"    Position MV: {last_state['position_market_value']}")
    print(f"    Positions ({last_state['num_positions']}):")
    for p in last_state['positions']:
        print(f"      {p['code']} {p['name']} qty={p['quantity']} mv={p['market_value']}")
    
    # Save full state
    with open(OUTPUT_DIR / "jq_first_last_state.json", "w", encoding="utf-8") as f:
        json.dump({"first": first_state, "last": last_state}, f, ensure_ascii=False, indent=2, default=str)
    
    # 7. 2026-06-24 check
    print("\n[7] 2026-06-24 check...")
    if "2026-06-24" in port_dates:
        jun24 = full_snapshot(port_records, "2026-06-24")
        print(f"  2026-06-24 exists: YES")
        print(f"    Cash: {jun24['cash']}")
        print(f"    Total asset: {jun24['total_asset']}")
        
        # Check trades on 06-23 and positions on 06-24 for reconciliation
        jun23_trades = [t for t in trade_records if t["trade_date"] == "2026-06-23"]
        print(f"    Trades on 06-23: {len(jun23_trades)}")
        
        # Compare positions 06-23 vs 06-24
        jun23_state = full_snapshot(port_records, "2026-06-23") if "2026-06-23" in port_dates else None
        if jun23_state:
            print(f"    06-23 positions: {[p['code'] for p in jun23_state['positions']]}")
        print(f"    06-24 positions: {[p['code'] for p in jun24['positions']]}")
    else:
        print("  2026-06-24 does not exist in portfolio records")
    
    # 8. Summary for report
    print("\n[8] Summary...")
    print(f"  Trade calendar: {'AVAILABLE' if trade_days else 'UNAVAILABLE'}")
    print(f"  Defensive ETFs: {etfs}")
    print(f"  Initial cash evidence: {'FOUND' if cash_evidence else 'NOT FOUND'}")
    print(f"  Cash recon status: {'ZERO_DIFF' if cash_stats['zero_diff_dates'] == cash_stats['comparable_dates'] else 'HAS_DIFF'}")
    
    with open(OUTPUT_DIR / "addendum_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "trade_days_count": len(trade_days) if trade_days else 0,
            "first_trade_day": str(trade_days[0]) if trade_days else None,
            "last_trade_day": str(trade_days[-1]) if trade_days else None,
            "defensive_etfs": etfs,
            "initial_cash_evidence": [{"source": e["source"], "context": e["context"]} for e in cash_evidence] if cash_evidence else [],
            "initial_cash_status": "UNKNOWN" if not cash_evidence else "CANDIDATE",
            "cash_recon": {
                "comparable": cash_stats["comparable_dates"],
                "zero_diff": cash_stats["zero_diff_dates"],
                "min_abs_diff": cash_stats.get("min_abs_diff"),
                "median_abs_diff": cash_stats.get("median_abs_diff"),
                "max_abs_diff": cash_stats.get("max_abs_diff"),
                "mean_abs_diff": round(cash_stats.get("mean_abs_diff", 0), 2),
            },
            "first_snapshot": first_state,
            "last_snapshot": last_state,
            "jun24_exists": "2026-06-24" in port_dates,
            "dup_301098": dup_results,
        }, f, ensure_ascii=False, indent=2, default=str)
    
    print("\nDone. Results saved to jq_cash_enhanced.csv, jq_first_last_state.json, addendum_results.json")

if __name__ == "__main__":
    main()
