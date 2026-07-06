"""Simplify order.py intraday branch: use minute close only, remove offset/HLOC comments."""
import os

path = r'D:\Work Space\local_quant\engine\order.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''    else:
        # Intraday minute data: match JQ's behavior of using the minute close
        # at the simulation time (JQ run_daily at "14:00" executes at the end
        # of the 14:00 minute bar, so close is causal and not a lookahead).
        # Note: _get_price_raw applies an internal -1 minute offset for 1m
        # queries in single-field mode, but the multi-field path (>=5 fields)
        # does NOT apply this offset. To get the current minute's bar
        # consistently, we pass current_dt directly with the 8-field query.
        df = data_api._get_price_raw(
            security, end_date=current_dt, count=1,
            fields=["open", "close", "high", "low", "high_limit", "low_limit", "paused", "volume"],
            frequency="1m", fq=None
        )
        field = "close"
        if df.empty:
            if is_research and norm_time < "15:00":
                # Research mode intraday: minute data missing -> MUST NOT
                # fall back to the daily close (would be a lookahead on the
                # full-day bar). Return zero price/volume; the caller will
                # reject the order. jq_parity preserves the original fallback.
                return 0, 999999, 0, False, 0
            df = data_api._get_price_raw(
                security, end_date=current_dt.replace(hour=15, minute=0), count=1,
                fields=["close", "high_limit", "low_limit", "paused", "volume"],
                frequency="daily", fq=None
            )
            field = "close"
            used_daily = True'''

new = '''    else:
        # Intraday: use the minute bar close at current_dt (matches JQ).
        df = data_api._get_price_raw(
            security, end_date=current_dt, count=1,
            fields=["close", "high_limit", "low_limit", "paused", "volume"],
            frequency="1m", fq=None
        )
        field = "close"
        if df.empty:
            if is_research and norm_time < "15:00":
                # No minute bar before 15:00 -> reject (daily close is lookahead).
                return 0, 999999, 0, False, 0
            df = data_api._get_price_raw(
                security, end_date=current_dt.replace(hour=15, minute=0), count=1,
                fields=["close", "high_limit", "low_limit", "paused", "volume"],
                frequency="daily", fq=None
            )
            field = "close"
            used_daily = True'''

if old not in content:
    print('OLD block not found - already simplified or different')
else:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Simplified order.py intraday branch')
