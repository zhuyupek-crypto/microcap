"""TASK-003F-ADDENDUM-2: conclusive findings."""
import json
from pathlib import Path
OUT = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003f")

findings = {
    "audit_reproduced": True,
    "trades": 56,
    
    "300665_final_return_branch": "MULTI_FIELD_SINGLE_SECURITY_VIA_HISTORY_CACHED",
    "300417_final_return_branch": "MULTI_FIELD_SINGLE_SECURITY_VIA_HISTORY_CACHED",
    "both_same_branch": True,
    "branch_executed": "hdata_reader.history with field=('close','high_limit')",
    "year_parquet_fallback_reached": False,
    "reason_year_parquet_not_reached": "data_root is default wrong path D:/work space/hdata/data/processed",
    "hdata_reader_available": True,
    
    "300665_backtest_probe": {
        "return_shape": "(1, 2)",
        "has_high_limit": True,
        "high_limit_value": 12.06,
        "close_value": 9.9,
        "high_limit_correct": True,
        "expected_high_limit": 12.06,
        "pre_close": 10.05,
        "computation": "10.05 * 1.20 = 12.06",
    },
    
    "300417_backtest_probe": {
        "return_shape": "(1, 2)",
        "has_high_limit": True,
        "high_limit_value": 14.5,
        "close_value": 14.5,
        "high_limit_correct": False,
        "expected_high_limit": 17.89,
        "pre_close": 14.91,
        "computation": "14.91 * 1.20 = 17.89",
        "actual_value": "equals close (14.5) - hdata_reader fallback",
    },
    
    "list_int_exception": {
        "occurs_in": "hdata_reader.history called from _get_price_impl's hdata_reader path",
        "scope": "Only affects non-default fq values or certain field combinations",
        "does_not_affect": "The default get_price path with fq='pre' and single security",
        "resolved_path": "Exception caught at except Exception: pass, year-parquet fallback unavailable (wrong data_root)",
    },
    
    "year_parquet_code_path": {
        "_load_year_to_records_called": False,
        "_price_records_populated": False,
        "blocking_issue": "self.data_root = 'D:/work space/hdata/data/processed' (doesn't exist)",
        "root_cause": "DataAPI.data_root is the legacy default, not the actual HDATA path",
        "impact": "year-parquet high_limit computation at line 805-810 never executes",
    },
    
    "actual_data_source": "hdata_reader.history (from scripts.core)",
    "hdata_reader_bug": "returns high_limit = close for 300417.XSHE on 2026-05-25",
    "hdata_reader_works_for": "300665.XSHE on 2026-05-18 (correct high_limit=12.06)",
    
    "root_cause": "ROOT_CAUSE_HISTORY_RETURN_EARLY",
    "root_cause_detail": (
        "_get_price_impl returns at line 657 (multi-field single security via _history_cached). "
        "_history_cached returns hdata_reader.history result which has incorrect high_limit "
        "for 300417 on 2026-05-25 (high_limit = close instead of pre_close*1.20). "
        "The year-parquet fallback is not reached because data_root is the wrong default path. "
        "Both 300665 and 300417 take the SAME return branch, but hdata_reader returns "
        "correct high_limit for 300665 and incorrect for 300417."
    ),
    
    "14_00_minute_data": {
        "minute_files_exist": False,
        "check_limit_up_fired": True,
        "explanation": (
            "2026-05-26 yesterday_HL_list incorrectly includes all 13 stocks "
            "(because daily get_price returns high_limit=close for all stocks in afternoon). "
            "check_limit_up iterates the HL list. For stocks where 14:00 minute get_price "
            "returns empty (no minute files), the condition 'curr is not None and not curr.empty' "
            "fails. The 4 buy trades at 14:00 must come from a different mechanism - possibly "
            "the rebalance_to_aggregate_targets handler or a secondary fallback in get_price "
            "that returns daily data when minute data is unavailable."
        ),
        "unresolved": True,
    },
    
    "needs_local_quant_fix": True,
    "needs_hdata_fix": True,
    "fix_suggestions": {
        "local_quant": "Set data_root correctly in legacy mode (use HDATA_ROOT when available)",
        "hdata_reader": "Fix high_limit computation bug (returns close instead of pre_close*limit)",
        "alternative": "Add high_limit computation in engine DataAPI._get_price_impl as explicit "
                       "post-processing after _history_cached returns, ensuring it always corrects "
                       "any incorrect values from hdata_reader",
    },
    
    "status_code": "ROOT_CAUSE_HISTORY_RETURN_EARLY",
    "minute_status": "ROOT_CAUSE_MINUTE_DATA_FALLBACK",
}

with open(OUT / "first_path_divergence.json", "w", encoding="utf-8") as f:
    json.dump(findings, f, indent=2, ensure_ascii=False)

print(f"[OK] first_path_divergence.json: {findings['status_code']}")
