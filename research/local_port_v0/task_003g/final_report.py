"""Final report for TASK-003G."""
import json
from pathlib import Path
OUT = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003g")

report = {
    "hdata_hash": "N/A (not a git repo, use SHA of individual files)",
    "microcap_commit": "56cc088749b3cac34e01e483936f6c6482b98a88",
    "local_quant_commit": "eb07910219d54824c3a92c0226b4dba10f2c5291",
    
    "l0_1d_stock": {
        "300417.SZ_20260525": {"close": 14.5, "pre_close": 14.91, "vol": 14267604.0, "status": "RAW_1D_BAR_VALID"},
        "301167.SZ_20260525": {"close": 16.59, "pre_close": 16.98, "vol": 3221763.0, "status": "RAW_1D_BAR_VALID"},
        "600493.SH_20260525": {"close": 6.94, "pre_close": 7.18, "vol": 8270996.0, "status": "RAW_1D_BAR_VALID"},
        "300535.SZ_20260525": {"close": 17.36, "pre_close": 18.12, "vol": 1431905.0, "status": "RAW_1D_BAR_VALID"},
        "300665.SZ_20260518": {"close": 9.9, "pre_close": 10.05, "vol": 8223501.0, "status": "RAW_1D_BAR_VALID"},
    },
    
    "l1_trading_status": {
        "300417.SZ_20260525": {"status": 0, "expected": 0, "correct": True},
        "301167.SZ_20260525": {"status": 0, "expected": 0, "correct": True},
        "600493.SH_20260525": {"status": 0, "expected": 0, "correct": True},
        "300535.SZ_20260525": {"status": 0, "expected": 0, "correct": True},
        "300665.SZ_20260518": {"status": 0, "expected": 0, "correct": True},
    },
    
    "l2_limit_status": {
        "300417.SZ_20260525": {"limit_up_price": 17.89, "limit_down_price": 11.93, "correct": True},
        "301167.SZ_20260525": {"limit_up_price": 20.38, "limit_down_price": 13.58, "correct": True},
        "600493.SH_20260525": {"limit_up_price": 7.90, "limit_down_price": 6.46, "correct": True},
        "300535.SZ_20260525": {"limit_up_price": 21.74, "limit_down_price": 14.50, "correct": True},
        "300665.SZ_20260518": {"limit_up_price": 12.06, "limit_down_price": 8.04, "correct": True},
    },
    
    "l3_pivot_cache": {
        "300417.SZ_20260525": {"high_limit": 14.5, "low_limit": 14.5, "close": 14.5, "high_limit_correct": False},
        "301167.SZ_20260525": {"high_limit": 16.59, "low_limit": 16.59, "close": 16.59, "high_limit_correct": False},
        "600493.SH_20260525": {"high_limit": 6.94, "low_limit": 6.94, "close": 6.94, "high_limit_correct": False},
        "300535.SZ_20260525": {"high_limit": 17.36, "low_limit": 17.36, "close": 17.36, "high_limit_correct": False},
        "300665.SZ_20260518": {"high_limit": 12.06, "low_limit": 8.04, "close": 9.9, "high_limit_correct": True},
    },
    
    "build_order": {
        "pivot_cache": "2026-05-30 15:59",
        "limit_status": "2026-06-14 06:37",
        "trading_status": "2026-06-14 06:38",
        "1d_stock": "2026-06-25 04:53",
        "order": "pivot_cache is STALE (oldest); feature data rebuilt later",
        "pivot_stale": True,
    },
    
    "build_pivot_cache_logic": {
        "file": "scripts/maintenance/build_pivot_cache.py",
        "relevant_lines": "L81-85",
        "code": """
paused_mask = (merged['paused'] == 1) & valid_mask
if 'close' in merged.columns:
    for c in ['open', 'high', 'low', 'vwap', 'pre_close', 'limit_up_price', 'limit_down_price']:
        if c in merged.columns:
            merged.loc[paused_mask, c] = merged.loc[paused_mask, 'close']
""",
        "trigger": "paused_mask applies when paused==1, setting limit_up_price = close",
        "current_trading_status": "paused=0 for all 5 stocks (correct)",
        "inference": "At build time (May 30), trading_status likely had paused=1 for these 4 stocks, or pivot used different source data",
    },
    
    "root_cause": "ROOT_CAUSE_STALE_PIVOT_CACHE",
    "root_cause_secondary": "ROOT_CAUSE_FALSE_SUSPENSION_PLUS_PIVOT_OVERRIDE",
    "root_cause_detail": (
        "The pivot_cache (built 2026-05-30) is stale. It predates the current "
        "trading_status (2026-06-14) and limit_status (2026-06-14) updates. "
        "At build time, the pivot_cache incorrectly set high_limit = close "
        "for 300417.SZ, 301167.SZ, 600493.SH, 300535.SZ on 2026-05-25. "
        "The current trading_status correctly shows paused=0 for all 5 stocks, "
        "but the pivot was never rebuilt. "
        "The hdata_reader reads high_limit from pivot_cache, returning close "
        "instead of the correct limit price. This cascades into incorrect "
        "yesterday_HL_list entries, triggering false check_limit_up trades."
    ),
    
    "fix_suggestion": {
        "file": "scripts/maintenance/build_pivot_cache.py",
        "lines": "81-85",
        "action": "Rebuild pivot_cache after trading_status and limit_status updates",
        "note": "The logic at L81-85 is correct for genuinely paused stocks; "
                "the issue is that the cache is stale. Re-running build_pivot_cache "
                "with current data would produce correct high_limit values."
    },
    
    "needs_pivot_rebuild": True,
    "needs_hdata_fix": False,
    "needs_local_quant_fix": False,
}

with open(OUT / "pipeline_root_cause.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"Report generated: {report['root_cause']}")
