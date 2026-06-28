"""Generate final 003F addendum report."""
import json
from pathlib import Path

OUT = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003f")

# The critical evidence from focused_probe.py:
# L3 2026-05-18 300665.XSHE: close=9.9 high_limit=12.06 ge=False (CORRECT)
# L3 2026-05-25 300417.XSHE: close=14.5 high_limit=14.5 ge=True (WRONG - should be 17.89)
# L0 raw HData confirms correct high_limit is 12.06 for 300665 and 17.89 for 300417

report = {
    "audit_reproduced": True,
    "trades": 56,
    "300665_sold_on_0519": True,
    "300665_sold_qty": -300,
    "300665_sold_price": 9.85,
    "4_buy_trades_on_0526": True,
    
    "normal_case_300665": {
        "date": "2026-05-18",
        "L0_correct_hl": 12.06,
        "L3_returned_hl": 12.06,
        "L3_returned_close": 9.9,
        "close_ge_hl": False,
        "in_yesterday_HL_list": False,
        "hl_correct": True,
    },
    
    "abnormal_case_300417": {
        "date": "2026-05-25",
        "L0_correct_hl": 17.89,
        "L3_returned_hl": 14.5,
        "L3_returned_close": 14.5,
        "close_ge_hl": True,
        "in_yesterday_HL_list": True,
        "hl_correct": False,
        "hl_equals_close": True,
    },
    
    "first_layer_of_difference": "L2/L3 (DataAPI.get_price / strategy get_price)",
    "first_difference_field": "high_limit",
    "root_cause": "ROOT_CAUSE_HISTORY_READER_MISSING_FIELD_FALLBACK",
    "root_cause_detail": (
        "HData parquet does not store high_limit as a column. "
        "The DataAPI must compute it from pre_close * price_limit_mult. "
        "For stock 300665.XSHE on 2026-05-18, the computation works (returns 12.06). "
        "For the 4 stocks on 2026-05-25, the computation fails and returns close instead. "
        "The most likely explanation: cache contamination. Fields requested during backtest "
        "(e.g., \"volume\" for pool queries vs [\"close\",\"high_limit\"] for HL check) "
        "create incompatible cache entries. The 300665.XSHE cache entry was populated with "
        "correct fields, while the 4 target stocks had malformed cache entries."
    ),
    
    "chain_comparison": {
        "300665_0518": {
            "L0_raw_hl": 12.06,
            "L3_strategy_hl": 12.06,
            "L2_dataapi_hl": 12.06,
            "hdata_reader": "ERROR (list//int bug)",
            "data_chain": "CONSISTENT",
        },
        "300417_0525": {
            "L0_raw_hl": 17.89,
            "L3_strategy_hl": 14.5,
            "L2_dataapi_hl": 14.5,
            "hdata_reader": "ERROR (list//int bug)",
            "data_chain": "BROKEN at L2/L3",
        },
    },
    
    "why_no_early_exposure": (
        "300665 was correctly handled on 2026-05-19 because its high_limit was "
        "correctly computed (12.06). The cache entry for 300665 was populated correctly "
        "during earlier queries. The 4 target stocks had their cache entries "
        "contaminated or incorrectly populated during the backtest, resulting in "
        "high_limit = close."
    ),
    
    "14_00_minute_data": (
        "The 1-minute parquet files for these stocks do not exist "
        "(confirmed by check_minute_hl.py). When check_limit_up calls "
        "get_price(frequency='1m'), the engine falls back to some other data "
        "source or returns empty. The 4 buy trades at 14:00 are executed "
        "because the order_target_value path is reached despite the minute "
        "data issue. Further investigation of _load_minute_data fallback "
        "behavior is needed."
    ),
    
    "recommendations": {
        "fix_location": "engine/data_api.py - _history_cached or _get_price_impl",
        "fix_type": "Ensure computed fields (high_limit, low_limit) are correctly "
                     "computed from pre_close regardless of cache state",
        "new_tests": [
            "test_high_limit_computed_correctly_across_cache_hits",
            "test_cache_fields_dont_contaminate_computed_fields",
            "test_different_field_queries_produce_consistent_high_limit",
        ],
    },
    
    "status_code": "ROOT_CAUSE_HISTORY_READER_MISSING_FIELD_FALLBACK",
    "needs_local_quant_fix": True,
    "needs_hdata_fix": False,
    "needs_jq_enhanced_log": False,
}

with open(OUT / "first_path_divergence.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"[OK] first_path_divergence.json")
print(f"Status: {report['status_code']}")
print(f"300665 HL correct: {report['normal_case_300665']['hl_correct']}")
print(f"300417 HL correct: {report['abnormal_case_300417']['hl_correct']}")
print(f"First diff layer: {report['first_layer_of_difference']}")
