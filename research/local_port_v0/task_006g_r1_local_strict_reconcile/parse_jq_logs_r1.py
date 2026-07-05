#!/usr/bin/env python3
"""
TASK-006G-R1 Stage 2: JQ Log Normalization
============================================
Parse raw JQ txt logs into standardized CSVs.

Inputs:
- 母版交易记录-20250101-20251231.txt  (2025 full-year trades)
- 母版持仓&资金记录-20250101-20250618.txt (2025 H1 portfolio)
- 母版交易记录-20260501-20260623.txt  (2026 fragment trades)
- 母版持仓&资金记录-20260501-20260623.txt (2026 fragment portfolio)

Outputs (under outputs/):
- JQ_2025_TRADES_NORMALIZED.csv
- JQ_2025_EQUITY_NORMALIZED.csv        (daily account-level + position detail)
- JQ_2026_FRAGMENT_TRADES_NORMALIZED.csv
- JQ_2026_FRAGMENT_EQUITY_NORMALIZED.csv

Trade standard fields:
  date, time, code, name, side, quantity, price, gross_amount, commission,
  stamp_tax, transfer_fee, net_amount, source_file, source_line_no,
  raw_text, parse_status

side unified: buy / sell / unknown

Special handling:
- JQ qty=0 export defect (mark but keep original)
- ETF 511880.XSHG special price precision
- Chinese stock names
- Missing timestamp
- Missing fee fields

Equity standard fields (position detail rows):
  date, time, total_asset, cash, available_cash, position_market_value_reported,
  position_market_value_calculated, position_count, code, position_qty,
  available_qty, market_price, market_value, source_file, source_line_no,
  parse_status

Plus a daily account-level equity table is embedded (snapshot_type=account).
"""
import csv
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"D:\Work Space\他山之石\微盘股")
OUTPUT_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_006g_r1_local_strict_reconcile" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Trade log parser
# ---------------------------------------------------------------------------
TRADE_FIELDS = [
    "date", "time", "code", "name", "side", "quantity", "price", "gross_amount",
    "commission", "stamp_tax", "transfer_fee", "net_amount",
    "source_file", "source_line_no", "raw_text", "parse_status",
]


def _parse_number(s):
    """Parse a number string that may contain commas and Chinese chars."""
    if s is None:
        return None
    s = str(s).strip()
    if not s or s == "-":
        return None
    # Remove commas, spaces, 股, 元
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
    """Extract code from '银华日利(511880.XSHG)' -> ('银华日利', '511880.XSHG')"""
    m = re.search(r"\(([^)]+)\)", name_field)
    if m:
        code = m.group(1)
        name = name_field[:m.start()].strip()
        return name, code
    return name_field.strip(), ""


def parse_trade_txt(txt_path):
    """Parse a JQ trade txt file. Return list of dicts."""
    rows = []
    if not txt_path.exists():
        return rows
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    src_name = txt_path.name
    for i, line in enumerate(lines, 1):
        s = line.rstrip("\n").rstrip("\r")
        if not s.strip():
            continue
        # Skip header lines (before first data row)
        # Data rows start with a date YYYY-MM-DD followed by tab
        if not re.match(r"^\d{4}-\d{2}-\d{2}\t", s):
            continue
        parts = s.split("\t")
        if len(parts) < 10:
            # Some rows may have separator-only content; skip
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

            # Determine parse_status
            parse_status = "parsed"
            if quantity is None:
                parse_status = "missing_quantity"
                quantity = 0
            if price is None:
                parse_status = "missing_price"
            # JQ qty=0 export defect: quantity is 0 but gross_amount is non-zero
            if quantity == 0 and gross_amount not in (None, 0):
                parse_status = "jq_qty_zero_export_defect"

            # Compute net_amount (gross + fees; sell gross is negative)
            net_amount = None
            if gross_amount is not None:
                fee = commission if commission is not None else 0
                # Buy: net = gross + fee; Sell: net = gross - fee (gross already negative)
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
                "stamp_tax": 0,  # not separately in txt
                "transfer_fee": 0,
                "net_amount": net_amount,
                "source_file": src_name,
                "source_line_no": i,
                "raw_text": s,
                "parse_status": parse_status,
            })
        except Exception as e:
            rows.append({
                "date": "", "time": "", "code": "", "name": "", "side": "unknown",
                "quantity": None, "price": None, "gross_amount": None,
                "commission": None, "stamp_tax": None, "transfer_fee": None,
                "net_amount": None, "source_file": src_name,
                "source_line_no": i, "raw_text": s,
                "parse_status": f"parse_error: {e}",
            })
    return rows


def write_trades_csv(rows, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in TRADE_FIELDS})
    print(f"Wrote: {out_path}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Portfolio / equity parser
# ---------------------------------------------------------------------------
EQUITY_FIELDS = [
    "date", "time", "snapshot_type", "total_asset", "cash", "available_cash",
    "position_market_value_reported", "position_market_value_calculated",
    "position_count", "code", "position_qty", "available_qty",
    "market_price", "market_value", "source_file", "source_line_no",
    "parse_status",
]


def _parse_total_asset(s):
    """Parse '总共:1,001,161.00' -> 1001161.00"""
    s = s.replace("总共:", "").replace(":", "").strip()
    return _parse_number(s)


def parse_portfolio_txt(txt_path):
    """Parse a JQ portfolio&cash txt file.
    Returns (account_rows, position_rows) where account_rows are daily
    account-level snapshots and position_rows are per-position detail.
    Both share the same schema for unified output.
    """
    account_rows = []
    position_rows = []
    if not txt_path.exists():
        return account_rows, position_rows
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    src_name = txt_path.name

    current_date = None
    current_positions = []
    current_cash = None
    current_total = None
    current_pnl = None
    block_start_line = None

    def _flush_block():
        nonlocal current_date, current_positions, current_cash, current_total, current_pnl, block_start_line
        if current_date is None:
            return
        # Calculate position market value
        pos_mv = sum(p["market_value"] for p in current_positions if p["market_value"] is not None)
        # Account-level row
        account_rows.append({
            "date": current_date,
            "time": "",
            "snapshot_type": "account",
            "total_asset": current_total,
            "cash": current_cash,
            "available_cash": current_cash,
            "position_market_value_reported": pos_mv if current_positions else 0,
            "position_market_value_calculated": pos_mv if current_positions else 0,
            "position_count": len(current_positions),
            "code": "",
            "position_qty": "",
            "available_qty": "",
            "market_price": "",
            "market_value": "",
            "source_file": src_name,
            "source_line_no": block_start_line,
            "parse_status": "parsed",
        })
        # Per-position rows
        for p in current_positions:
            position_rows.append({
                "date": current_date,
                "time": "",
                "snapshot_type": "position",
                "total_asset": current_total,
                "cash": current_cash,
                "available_cash": current_cash,
                "position_market_value_reported": pos_mv,
                "position_market_value_calculated": pos_mv,
                "position_count": len(current_positions),
                "code": p["code"],
                "position_qty": p["qty"],
                "available_qty": p["qty"],
                "market_price": p["price"],
                "market_value": p["market_value"],
                "source_file": src_name,
                "source_line_no": p["line_no"],
                "parse_status": "parsed",
            })
        current_date = None
        current_positions = []
        current_cash = None
        current_total = None
        current_pnl = None
        block_start_line = None

    for i, line in enumerate(lines, 1):
        s = line.rstrip("\n").rstrip("\r")
        if not s.strip():
            continue
        # Date line
        m = re.match(r"^(\d{4}-\d{2}-\d{2})$", s.strip())
        if m:
            # Flush previous block
            _flush_block()
            current_date = m.group(1)
            block_start_line = i
            continue
        # Skip header lines (标的/数量/收盘价/市值/盈亏)
        if s.strip() in ("标的", "数量", "收盘价/结算价", "市值/价值", "盈亏/逐笔浮盈"):
            continue
        # Parse position/cash/total line
        parts = s.split("\t")
        if len(parts) < 4:
            continue
        first = parts[0].strip()
        # Cash line: "Cash\t\t\t9,198.10\t0.00"
        if first.lower().startswith("cash"):
            cash_str = parts[3] if len(parts) > 3 else parts[2]
            current_cash = _parse_number(cash_str)
            continue
        # Total line: " \t\t\t总共:999,901.00\t-99.00"
        if "总共" in s or (parts[0].strip() == "" and any("总共" in p for p in parts)):
            for p in parts:
                if "总共" in p:
                    current_total = _parse_total_asset(p)
                    break
            continue
        # Position line: "银华日利(511880.XSHG)\t9900股\t100.071\t990,702.90\t-99.00"
        if first and first != "Cash":
            name, code = _extract_code(first)
            qty = _parse_number(parts[1]) if len(parts) > 1 else None
            price = _parse_number(parts[2]) if len(parts) > 2 else None
            mv = _parse_number(parts[3]) if len(parts) > 3 else None
            pnl = _parse_number(parts[4]) if len(parts) > 4 else None
            if code and qty is not None:
                current_positions.append({
                    "code": code, "name": name, "qty": qty,
                    "price": price, "market_value": mv, "pnl": pnl,
                    "line_no": i,
                })
    # Flush last block
    _flush_block()
    return account_rows, position_rows


def write_equity_csv(account_rows, position_rows, out_path):
    """Write combined equity CSV: account rows first (one per day), then position rows.
    The snapshot_type field distinguishes them.
    """
    all_rows = account_rows + position_rows
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EQUITY_FIELDS)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k, "") for k in EQUITY_FIELDS})
    print(f"Wrote: {out_path}  ({len(all_rows)} rows: {len(account_rows)} account + {len(position_rows)} position)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("TASK-006G-R1 Stage 2: JQ Log Normalization")
    print("=" * 70)

    # ---- 2025 trades ----
    print("\n[1/4] Parsing 2025 trade txt...")
    p = PROJECT_ROOT / "母版交易记录-20250101-20251231.txt"
    rows = parse_trade_txt(p)
    out = OUTPUT_DIR / "JQ_2025_TRADES_NORMALIZED.csv"
    write_trades_csv(rows, out)
    # Stats
    qty_zero = sum(1 for r in rows if r["parse_status"] == "jq_qty_zero_export_defect")
    print(f"  Total: {len(rows)}, jq_qty_zero_export_defect: {qty_zero}")
    if rows:
        print(f"  Date range: {rows[0]['date']} ~ {rows[-1]['date']}")

    # ---- 2025 portfolio (H1 only) ----
    print("\n[2/4] Parsing 2025 portfolio txt (H1)...")
    p = PROJECT_ROOT / "母版持仓&资金记录-20250101-20250618.txt"
    acct, pos = parse_portfolio_txt(p)
    out = OUTPUT_DIR / "JQ_2025_EQUITY_NORMALIZED.csv"
    write_equity_csv(acct, pos, out)
    if acct:
        print(f"  Account rows date range: {acct[0]['date']} ~ {acct[-1]['date']}")
        print(f"  First day total_asset: {acct[0]['total_asset']}, cash: {acct[0]['cash']}, positions: {acct[0]['position_count']}")
        print(f"  Last day total_asset: {acct[-1]['total_asset']}")

    # ---- 2026 fragment trades ----
    print("\n[3/4] Parsing 2026 fragment trade txt...")
    p = PROJECT_ROOT / "母版交易记录-20260501-20260623.txt"
    rows = parse_trade_txt(p)
    out = OUTPUT_DIR / "JQ_2026_FRAGMENT_TRADES_NORMALIZED.csv"
    write_trades_csv(rows, out)
    qty_zero = sum(1 for r in rows if r["parse_status"] == "jq_qty_zero_export_defect")
    print(f"  Total: {len(rows)}, jq_qty_zero_export_defect: {qty_zero}")
    if rows:
        print(f"  Date range: {rows[0]['date']} ~ {rows[-1]['date']}")

    # ---- 2026 fragment portfolio ----
    print("\n[4/4] Parsing 2026 fragment portfolio txt...")
    p = PROJECT_ROOT / "母版持仓&资金记录-20260501-20260623.txt"
    acct, pos = parse_portfolio_txt(p)
    out = OUTPUT_DIR / "JQ_2026_FRAGMENT_EQUITY_NORMALIZED.csv"
    write_equity_csv(acct, pos, out)
    if acct:
        print(f"  Account rows date range: {acct[0]['date']} ~ {acct[-1]['date']}")
        print(f"  First day total_asset: {acct[0]['total_asset']}, cash: {acct[0]['cash']}, positions: {acct[0]['position_count']}")
        print(f"  Last day total_asset: {acct[-1]['total_asset']}")

    print("\n=== JQ Log Normalization Complete ===")


if __name__ == "__main__":
    main()
