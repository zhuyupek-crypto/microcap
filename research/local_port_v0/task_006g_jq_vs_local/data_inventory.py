#!/usr/bin/env python3
"""TASK-006G Stage 0: Data inventory for JQ vs local attribution.

Scans all relevant data files and produces DATA_INVENTORY.md/csv with:
- filename, path, data_type, start_date, end_date, rows, fields
- whether file contains price/volume/fee/cash/asset/positions
- evidence level A/B/C
- whether file can be used for trade-level attribution
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # microcap root
OUTPUT_DIR = Path(__file__).resolve().parent

# Files to inventory: (relative_path, description, data_type)
TARGETS = [
    # JQ mother log files
    ("母版交易记录-20250101-20251231.txt", "JQ trades 2025 full year", "jq_trades"),
    ("母版持仓&资金记录-20250101-20250618.txt", "JQ positions 2025 H1", "jq_positions"),
    ("母版交易记录-20260501-20260623.txt", "JQ trades 2026 May-Jun", "jq_trades"),
    ("母版持仓&资金记录-20260501-20260623.txt", "JQ positions 2026 May-Jun", "jq_positions"),
    # Task-003 alignment products
    ("research/local_port_v0/task_003/jq_trades_normalized.csv", "JQ trades normalized (003)", "jq_trades_normalized"),
    ("research/local_port_v0/task_003/jq_portfolio_normalized.csv", "JQ portfolio normalized (003)", "jq_portfolio"),
    ("research/local_port_v0/task_003/local_trades_normalized.csv", "local trades normalized (003)", "local_trades"),
    ("research/local_port_v0/task_003/local_portfolio_normalized.csv", "local portfolio normalized (003)", "local_portfolio"),
    ("research/local_port_v0/task_003/daily_alignment.csv", "daily alignment 003", "daily_alignment"),
    ("research/local_port_v0/task_003/trade_alignment.csv", "trade alignment 003", "trade_alignment"),
    ("research/local_port_v0/task_003/first_divergence.json", "first divergence 003", "first_divergence"),
    # Task-004 alignment products
    ("research/local_port_v0/task_004/jq_trades_2025.csv", "JQ trades 2025 (004)", "jq_trades_004"),
    ("research/local_port_v0/task_004/local_trades_2025.csv", "local trades 2025 (004)", "local_trades_004"),
    ("research/local_port_v0/task_004/local_trades_2025_v2.csv", "local trades 2025 v2 (004)", "local_trades_004_v2"),
    ("research/local_port_v0/task_004/TASK_004_REPORT.md", "004 report", "report"),
    # Task-003d
    ("research/local_port_v0/task_003d/task_003d1_report.md", "003d1 report", "report"),
    ("research/local_port_v0/task_003d/order_result_comparison.csv", "order result comparison 003d", "order_comparison"),
    # Task-003e
    ("research/local_port_v0/task_003e/task_003e_report.md", "003e report", "report"),
    ("research/local_port_v0/task_003e/trade_alignment_after_fix.csv", "trade alignment after fix 003e", "trade_alignment"),
    # Task-003f
    ("research/local_port_v0/task_003f/task_003f_report.md", "003f report", "report"),
    # r3 full Research run
    ("research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/equity.csv", "r3 full equity", "local_equity"),
    ("research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/trades.csv", "r3 full trades", "local_trades"),
    ("research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/manifest.json", "r3 full manifest", "manifest"),
    ("research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/performance_report.json", "r3 full perf report", "perf_report"),
    ("research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/closed_trades.csv", "r3 full closed trades", "closed_trades"),
    ("research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/yearly_summary.csv", "r3 full yearly", "yearly"),
    # r4 full jq_parity run
    ("research/local_port_v0/task_005_optimize/runs/r4_full_2020_202605_jq_parity/performance_report.json", "r4 full perf report", "perf_report"),
    # Strategy source
    ("微盘股-母版-20260627.py", "mother strategy source", "strategy"),
    # baseline manifest
    ("research/local_migration/BASELINE_MANIFEST.json", "baseline manifest", "manifest"),
]


def _read_text_lines(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def _count_csv_rows(path: Path) -> int:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f) - 1  # exclude header


def _extract_dates_from_text(lines: list[str]) -> tuple[str, str]:
    """Extract first and last date-like strings from text lines."""
    dates = []
    date_re = re.compile(r"(\d{4}-\d{2}-\d{2})")
    for line in lines[:200]:  # scan first 200 lines
        m = date_re.search(line)
        if m:
            dates.append(m.group(1))
    # Also scan last 50 lines
    for line in lines[-50:]:
        m = date_re.search(line)
        if m:
            dates.append(m.group(1))
    if dates:
        return min(dates), max(dates)
    return "", ""


def _extract_dates_from_csv(path: Path, date_col_hint: str = "date") -> tuple[str, str]:
    """Extract date range from CSV."""
    dates = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k in [date_col_hint, "trade_date", "datetime", "date"]:
                if k in row and row[k]:
                    dates.append(row[k][:10])
                    break
    if dates:
        return min(dates), max(dates)
    return "", ""


def _infer_evidence_level(data_type: str, has_price: bool, has_qty: bool, has_date: bool, has_code: bool) -> str:
    """A=strict trade-level, B=partial, C=macro only."""
    if data_type in ("jq_trades", "jq_trades_normalized", "local_trades", "local_trades_normalized",
                      "trade_alignment", "order_comparison"):
        if has_price and has_qty and has_date and has_code:
            return "A"
    if data_type in ("jq_positions", "jq_portfolio", "local_portfolio", "daily_alignment"):
        return "A" if has_date else "B"
    if data_type in ("local_equity", "closed_trades", "yearly"):
        return "A"
    if data_type in ("perf_report", "manifest"):
        return "B"
    if data_type in ("report", "strategy"):
        return "C"
    return "B"


def inventory_file(rel_path: str, description: str, data_type: str) -> dict[str, Any]:
    full_path = PROJECT_ROOT / rel_path
    info: dict[str, Any] = {
        "filename": Path(rel_path).name,
        "path": rel_path,
        "description": description,
        "data_type": data_type,
        "exists": full_path.exists(),
        "start_date": "",
        "end_date": "",
        "rows": 0,
        "fields": "",
        "has_price": False,
        "has_volume": False,
        "has_fee": False,
        "has_cash": False,
        "has_asset": False,
        "has_positions": False,
        "trade_level_attribution": False,
        "evidence_level": "C",
        "notes": "",
    }
    if not full_path.exists():
        info["notes"] = "FILE NOT FOUND"
        return info

    ext = full_path.suffix.lower()
    if ext == ".csv":
        info["rows"] = _count_csv_rows(full_path)
        # Read header
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            info["fields"] = ",".join(header[:15])
        # Check fields
        h_lower = " ".join(header).lower()
        info["has_price"] = any("price" in h_lower for x in ["price", "成交价"])
        info["has_volume"] = any(x in h_lower for x in ["amount", "quantity", "volume", "数量", "成交数量"])
        info["has_fee"] = any(x in h_lower for x in ["fee", "commission", "手续费", "cost"])
        info["has_cash"] = any(x in h_lower for x in ["cash", "现金"])
        info["has_asset"] = any(x in h_lower for x in ["asset", "total", "总资产", "value"])
        info["has_positions"] = any(x in h_lower for x in ["position", "持仓", "portfolio"])
        # Date range
        sd, ed = _extract_dates_from_csv(full_path)
        info["start_date"] = sd
        info["end_date"] = ed
    elif ext == ".txt":
        lines = _read_text_lines(full_path)
        info["rows"] = len(lines)
        content = "".join(lines[:50])
        info["fields"] = "see description (txt format)"
        info["has_price"] = any(x in content for x in ["成交价", "price"])
        info["has_volume"] = any(x in content for x in ["成交数量", "数量", "股"])
        info["has_fee"] = any(x in content for x in ["手续费", "fee"])
        info["has_cash"] = "Cash" in content or "现金" in content
        info["has_asset"] = "总共" in content or "总资产" in content
        info["has_positions"] = any(x in content for x in ["股", "持仓"])
        sd, ed = _extract_dates_from_text(lines)
        info["start_date"] = sd
        info["end_date"] = ed
    elif ext == ".json":
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        info["rows"] = 1 if isinstance(data, dict) else len(data)
        if isinstance(data, dict):
            info["fields"] = ",".join(list(data.keys())[:10])
        else:
            info["fields"] = "json array"
        sd, ed = _extract_dates_from_text([json.dumps(data)])
        info["start_date"] = sd
        info["end_date"] = ed
    elif ext == ".md":
        lines = _read_text_lines(full_path)
        info["rows"] = len(lines)
        info["fields"] = "markdown report"
        sd, ed = _extract_dates_from_text(lines)
        info["start_date"] = sd
        info["end_date"] = ed
    elif ext == ".py":
        lines = _read_text_lines(full_path)
        info["rows"] = len(lines)
        info["fields"] = "python source"
        info["start_date"] = "n/a"
        info["end_date"] = "n/a"

    # Evidence level
    has_code = info["has_volume"] and "code" in info["fields"].lower() or "标的" in info["fields"]
    info["evidence_level"] = _infer_evidence_level(
        data_type, info["has_price"], info["has_volume"],
        bool(info["start_date"]), has_code)
    info["trade_level_attribution"] = (
        info["evidence_level"] == "A"
        and info["has_price"]
        and info["has_volume"]
        and info["start_date"] != ""
    )

    return info


def main():
    print("=" * 70)
    print("TASK-006G Stage 0: Data Inventory")
    print("=" * 70)

    results = []
    for rel_path, desc, dtype in TARGETS:
        print(f"  scanning: {rel_path}")
        info = inventory_file(rel_path, desc, dtype)
        results.append(info)
        status = "OK" if info["exists"] else "MISSING"
        print(f"    -> {status}, rows={info['rows']}, dates={info['start_date']}~{info['end_date']}, level={info['evidence_level']}")

    # Write CSV
    csv_path = OUTPUT_DIR / "DATA_INVENTORY.csv"
    fieldnames = list(results[0].keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print(f"\nCSV: {csv_path}")

    # Write MD
    md_path = OUTPUT_DIR / "DATA_INVENTORY.md"
    lines = [
        "# TASK-006G Data Inventory",
        "",
        f"Total files scanned: {len(results)}",
        f"Files found: {sum(1 for r in results if r['exists'])}",
        f"Files missing: {sum(1 for r in results if not r['exists'])}",
        "",
        "## Evidence Level Summary",
        "",
        f"- A (strict trade-level): {sum(1 for r in results if r['evidence_level']=='A')}",
        f"- B (partial): {sum(1 for r in results if r['evidence_level']=='B')}",
        f"- C (macro only): {sum(1 for r in results if r['evidence_level']=='C')}",
        "",
        "## File Details",
        "",
        "| filename | data_type | start_date | end_date | rows | evidence | trade_level | notes |",
        "|----------|-----------|------------|----------|------|----------|-------------|-------|",
    ]
    for r in results:
        lines.append(f"| {r['filename']} | {r['data_type']} | {r['start_date']} | {r['end_date']} | {r['rows']} | {r['evidence_level']} | {'Y' if r['trade_level_attribution'] else 'N'} | {r['notes']} |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD: {md_path}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    a_files = [r for r in results if r["evidence_level"] == "A" and r["exists"]]
    print(f"A-level files (strict attribution possible): {len(a_files)}")
    for r in a_files:
        print(f"  - {r['filename']}: {r['start_date']}~{r['end_date']}, {r['rows']} rows")
    jq_a = [r for r in a_files if "jq" in r["data_type"]]
    print(f"\nJQ A-level files: {len(jq_a)}")
    print(f"  -> Strict JQ vs local trade-level attribution possible for:")
    for r in jq_a:
        print(f"     {r['filename']} ({r['start_date']}~{r['end_date']})")


if __name__ == "__main__":
    main()
