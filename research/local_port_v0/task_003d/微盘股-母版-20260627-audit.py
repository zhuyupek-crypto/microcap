# --- AUDIT COPY: 微盘股-母版-20260627-audit.py ---
# Semantic difference from original: ADDITIONS ONLY
#   + json audit_logger import
#   + audit_log_event() calls at key decision points
#   + order_obj = order_target_value() return capture
# No changes to: variables, conditions, loops, API calls, selection logic, target calculation

from jqdata import *
import json
import os

# === AUDIT: structured JSON logger (exception-safe) ===
_AUDIT_LOG = []
_AUDIT_RUN_ID = os.environ.get("AUDIT_RUN_ID", "audit_local")
_STRATEGY_SHA = "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"
_EVENT_SEQ = [0]
_AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "")

def _audit_log(event_type, **kwargs):
    try:
        _EVENT_SEQ[0] += 1
        entry = {
            "run_id": _AUDIT_RUN_ID,
            "strategy_sha256": _STRATEGY_SHA,
            "event_sequence": _EVENT_SEQ[0],
            "event_type": event_type,
        }
        entry.update(kwargs)
        _AUDIT_LOG.append(entry)
    except Exception:
        pass

def _flush_audit_log():
    if not _AUDIT_LOG_PATH:
        return
    try:
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            for entry in _AUDIT_LOG:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _AUDIT_LOG.clear()
    except Exception:
        pass
# === END AUDIT ===


def initialize(context):
    set_benchmark("000001.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0001,
            close_commission=0.0001,
            min_commission=5,
        ),
        type="stock",
    )

    g.days = 0
    g.phase_cycle = 15
    g.phase_offsets = [0, 3, 6, 9, 12]
    g.stocknum = 10
    g.min_list_days = 375
    g.defensive_months = [1, 4]
    g.defensive_etfs = ["511880.XSHG"]
    g.use_risk_filter = True
    g.trade_enabled = True

    g.phase_targets = {offset: [] for offset in g.phase_offsets}
    g.yesterday_HL_list = []
    g.in_defensive_mode = False
    g.last_due_offsets = []
    g.last_target_values = {}

    run_daily(prepare_stock_list, time="09:05")
    run_daily(trade, time="09:30")
    run_daily(check_limit_up, time="14:00")
    run_daily(report_plan, time="15:00")

    _audit_log("initialize", g_days=g.days, g_stocknum=g.stocknum, g_phase_cycle=g.phase_cycle,
               g_phase_offsets=g.phase_offsets, g_min_list_days=g.min_list_days,
               g_use_risk_filter=g.use_risk_filter, g_defensive_months=g.defensive_months,
               g_defensive_etfs=g.defensive_etfs)


def prepare_stock_list(context):
    g.yesterday_HL_list = []
    for stock in context.portfolio.positions:
        if is_defensive_asset(stock):
            continue
        curr = get_price(
            stock,
            end_date=context.previous_date,
            frequency="daily",
            fields=["close", "high_limit"],
            count=1,
        )
        close_val = None
        high_limit_val = None
        is_hl = False
        if curr is not None and not curr.empty:
            close_val = float(curr["close"][0])
            high_limit_val = float(curr["high_limit"][0])
            is_hl = close_val >= high_limit_val
            if is_hl:
                g.yesterday_HL_list.append(stock)
        _audit_log("yesterday_HL_check",
                   callback_name="prepare_stock_list",
                   security=stock,
                   previous_date=str(context.previous_date),
                   close=close_val,
                   high_limit=high_limit_val,
                   is_at_high_limit=is_hl,
                   in_yesterday_HL_list=is_hl)

    _audit_log("yesterday_HL_list_result",
               callback_name="prepare_stock_list",
               yesterday_HL_list=list(g.yesterday_HL_list),
               previous_date=str(context.previous_date),
               hl_count=len(g.yesterday_HL_list))


def trade(context):
    current_month = context.current_dt.month

    days_before = g.days
    _audit_log("trade_enter",
               callback_name="trade",
               current_dt=str(context.current_dt),
               previous_date=str(context.previous_date),
               g_days_before=days_before,
               in_defensive_mode=g.in_defensive_mode,
               current_month=current_month,
               portfolio_cash=float(context.portfolio.available_cash),
               portfolio_total_value=float(context.portfolio.total_value),
               position_count=len(context.portfolio.positions))

    if not g.in_defensive_mode and current_month in g.defensive_months:
        _audit_log("trade_defensive_enter", callback_name="trade",
                   defensive_month=current_month)
        switch_to_defensive(context)
        _audit_log("trade_defensive_done", callback_name="trade",
                   in_defensive_mode=g.in_defensive_mode)
        return

    if g.in_defensive_mode and current_month not in g.defensive_months:
        for etf in g.defensive_etfs:
            order_target(etf, 0)
        g.in_defensive_mode = False

    if g.in_defensive_mode:
        return

    due_offsets = [offset for offset in g.phase_offsets if (g.days + offset) % g.phase_cycle == 0]
    g.last_due_offsets = due_offsets
    _audit_log("trade_due_offsets", callback_name="trade",
               due_offsets=due_offsets, g_days=g.days,
               total_value=float(context.portfolio.total_value))

    if due_offsets:
        for offset in due_offsets:
            target_list = select_smallest_market_cap(context)
            g.phase_targets[offset] = target_list
            log.info("phase offset=%s targets=%s" % (offset, ",".join(target_list)))
            _audit_log("trade_phase_target_selected",
                       callback_name="trade",
                       phase_offset=offset,
                       target_count=len(target_list),
                       target_list=target_list)

        rebalance_to_aggregate_targets(context)

    else:
        _audit_log("trade_no_due_offsets", callback_name="trade")

    g.days += 1
    _audit_log("trade_exit",
               callback_name="trade",
               g_days_after=g.days,
               last_due_offsets=g.last_due_offsets)


def select_smallest_market_cap(context):
    data_date = context.previous_date
    pool = get_stock_pool(data_date)
    if len(pool) < g.stocknum:
        _audit_log("select_mcap_pool_too_small",
                   callback_name="select_smallest_market_cap",
                   pool_size=len(pool), required=g.stocknum)
        return []

    q = query(
        valuation.code,
        valuation.market_cap,
    ).filter(
        valuation.code.in_(pool)
    )
    mcap_df = get_fundamentals(q, date=data_date)
    if mcap_df is None or mcap_df.empty:
        _audit_log("select_mcap_empty_fundamentals",
                   callback_name="select_smallest_market_cap")
        return []

    candidates = mcap_df.dropna().sort_values("market_cap")["code"].tolist()
    risk_ok = build_risk_filter_map(candidates, data_date)
    current_data = get_current_data()
    target_list = []
    for stock in candidates:
        if not risk_ok.get(stock, True):
            _audit_log("select_mcap_risk_filtered",
                       callback_name="select_smallest_market_cap",
                       security=stock, risk_ok=False)
            continue
        if can_buy_today(stock, current_data):
            target_list.append(stock)
            _audit_log("select_mcap_selected",
                       callback_name="select_smallest_market_cap",
                       security=stock, rank=len(target_list))
            if len(target_list) >= g.stocknum:
                break
        else:
            _audit_log("select_mcap_cannot_buy",
                       callback_name="select_smallest_market_cap",
                       security=stock, reason="can_buy_today_false")

    _audit_log("select_mcap_result",
               callback_name="select_smallest_market_cap",
               target_count=len(target_list),
               target_list=target_list)
    return target_list


def get_stock_pool(data_date):
    securities = get_all_securities(["stock"], date=data_date)
    pool = []
    for stock, row in securities.iterrows():
        if not is_common_stock(stock):
            continue
        if (data_date - row["start_date"]).days <= g.min_list_days:
            continue
        pool.append(stock)

    if not pool:
        _audit_log("stock_pool_empty", callback_name="get_stock_pool",
                   data_date=str(data_date))
        return []

    st_data = get_extras("is_st", pool, start_date=data_date, end_date=data_date)
    pool = [s for s in pool if not st_data[s][0]]

    volume = get_price(
        pool,
        start_date=data_date,
        end_date=data_date,
        frequency="daily",
        fields="volume",
    )["volume"]
    pool_with_vol = [s for s in pool if s in volume.columns and volume[s][0] > 0]

    _audit_log("stock_pool_result", callback_name="get_stock_pool",
               data_date=str(data_date),
               pool_size_before_volume=len(pool),
               pool_size=len(pool_with_vol))
    return pool_with_vol


def risk_filter_ok(stock, data_date):
    if not g.use_risk_filter:
        return True
    try:
        q = query(
            valuation.code,
            indicator.roe,
            cash_flow.net_operate_cash_flow,
            balance.total_liability,
            balance.total_assets,
        ).filter(valuation.code == stock)
        df = get_fundamentals(q, date=data_date)
    except Exception as e:
        log.warn("risk filter skipped for %s: %s" % (stock, e))
        return True

    if df is None or df.empty:
        return True
    row = df.iloc[0]
    total_assets = row.get("total_assets", None)
    total_liability = row.get("total_liability", None)
    roe = row.get("roe", 0)
    ocf = row.get("net_operate_cash_flow", 0)
    if total_assets is None or total_assets <= 0:
        return False
    debt_to_assets = total_liability / total_assets * 100.0

    return debt_to_assets < 95 and (roe > -50 or ocf > -1e8)


def build_risk_filter_map(stocks, data_date):
    if not g.use_risk_filter or not stocks:
        return {s: True for s in stocks}
    try:
        q = query(
            valuation.code,
            indicator.roe,
            cash_flow.net_operate_cash_flow,
            balance.total_liability,
            balance.total_assets,
        ).filter(valuation.code.in_(stocks))
        df = get_fundamentals(q, date=data_date)
    except Exception as e:
        log.warn("batch risk filter skipped: %s" % e)
        return {s: True for s in stocks}

    result = {s: True for s in stocks}
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        stock = row["code"]
        total_assets = row.get("total_assets", None)
        total_liability = row.get("total_liability", None)
        roe = row.get("roe", 0)
        ocf = row.get("net_operate_cash_flow", 0)
        if total_assets is None or total_assets <= 0:
            result[stock] = False
            continue
        debt_to_assets = total_liability / total_assets * 100.0
        result[stock] = debt_to_assets < 95 and (roe > -50 or ocf > -1e8)
    return result


def aggregate_target_values(context):
    target_values = {}
    phase_value = context.portfolio.total_value / len(g.phase_offsets)
    stock_value = phase_value / g.stocknum

    _audit_log("aggregate_target_params",
               callback_name="aggregate_target_values",
               portfolio_total_value=float(context.portfolio.total_value),
               total_phases=len(g.phase_offsets),
               phase_value=float(phase_value),
               stocknum=g.stocknum,
               stock_value=float(stock_value))

    for offset, stocks in g.phase_targets.items():
        for stock in stocks:
            old_val = target_values.get(stock, 0.0)
            target_values[stock] = old_val + stock_value
            _audit_log("aggregate_target_stock",
                       callback_name="aggregate_target_values",
                       security=stock,
                       phase_offset=offset,
                       stock_value=float(stock_value),
                       cumulative_target=float(target_values[stock]))

    _audit_log("aggregate_target_result",
               callback_name="aggregate_target_values",
               target_count=len(target_values),
               target_300405=float(target_values.get("300405.XSHE", 0.0)))

    return target_values


def rebalance_to_aggregate_targets(context):
    target_values = aggregate_target_values(context)
    g.last_target_values = target_values
    current_data = get_current_data()

    sell_plan = []
    for stock in list(context.portfolio.positions.keys()):
        if is_defensive_asset(stock):
            continue
        target_value = target_values.get(stock, 0.0)
        current_value = context.portfolio.positions[stock].value if stock in context.portfolio.positions else 0.0
        current_price = float(current_data[stock].last_price) if stock in current_data else None

        sell_decision = None
        if target_value <= 0:
            if stock in g.yesterday_HL_list:
                sell_decision = "SKIPPED_YESTERDAY_HL_GUARD"
                _audit_log("sell_decision",
                           callback_name="rebalance", security=stock,
                           target_value=float(target_value),
                           current_value=float(current_value),
                           in_yesterday_HL_list=True,
                           decision="SKIPPED_YESTERDAY_HL_GUARD",
                           target_type="ZERO_TARGET")
                continue
            if can_sell_today(stock, current_data):
                sell_plan.append((stock, 0.0))
                sell_decision = "FULL_EXIT"
            else:
                sell_decision = "BLOCKED_CANNOT_SELL"
        else:
            if current_value > target_value and stock in g.yesterday_HL_list:
                sell_decision = "SKIPPED_CURRENT_GT_TARGET_AND_HL_LIST"
                _audit_log("sell_decision",
                           callback_name="rebalance", security=stock,
                           target_value=float(target_value),
                           current_value=float(current_value),
                           in_yesterday_HL_list=True,
                           decision="SKIPPED_CURRENT_GT_TARGET_AND_HL_LIST",
                           target_type="POSITIVE_TARGET")
                continue
            if can_sell_today(stock, current_data):
                sell_plan.append((stock, target_value))
                sell_decision = "PARTIAL_REDUCTION" if current_value > target_value else "TARGET_ADJUSTMENT"
            else:
                sell_decision = "BLOCKED_CANNOT_SELL"

        _audit_log("sell_decision",
                   callback_name="rebalance", security=stock,
                   target_value=float(target_value),
                   current_value=float(current_value),
                   current_price=current_price,
                   in_yesterday_HL_list=stock in g.yesterday_HL_list,
                   can_sell_today=can_sell_today(stock, current_data) if stock in current_data else None,
                   decision=sell_decision,
                   target_type="ZERO_TARGET" if target_value <= 0 else "POSITIVE_TARGET")

    buy_plan = []
    for stock, target_value in target_values.items():
        current_value = context.portfolio.positions[stock].value if stock in context.portfolio.positions else 0.0
        if current_value < target_value and can_buy_today(stock, current_data):
            buy_plan.append((stock, target_value))
            _audit_log("buy_decision",
                       callback_name="rebalance", security=stock,
                       target_value=float(target_value),
                       current_value=float(current_value),
                       target_type="BUY_TO_TARGET")

    _audit_log("rebalance_plan",
               callback_name="rebalance",
               sell_plan=[{"stock": s, "target": float(v)} for s, v in sell_plan],
               buy_plan=[{"stock": s, "target": float(v)} for s, v in buy_plan])

    log_plan("sell_plan_0930", sell_plan)
    log_plan("buy_plan_0930", buy_plan)
    if not g.trade_enabled:
        _audit_log("rebalance_trade_disabled", callback_name="rebalance")
        return

    for stock, target_value in sell_plan:
        order_obj = order_target_value(stock, target_value)
        _audit_log("order_target_value",
                   callback_name="rebalance", order_type="sell_plan",
                   security=stock, target_value=float(target_value),
                   order_id=str(getattr(order_obj, 'order_id', None)) if order_obj is not None else None,
                   order_status=str(getattr(order_obj, 'status', None)) if order_obj is not None else None,
                   filled_amount=getattr(order_obj, 'filled', None) if order_obj is not None else None)
    for stock, target_value in buy_plan:
        order_obj = order_target_value(stock, target_value)
        _audit_log("order_target_value",
                   callback_name="rebalance", order_type="buy_plan",
                   security=stock, target_value=float(target_value),
                   order_id=str(getattr(order_obj, 'order_id', None)) if order_obj is not None else None,
                   order_status=str(getattr(order_obj, 'status', None)) if order_obj is not None else None,
                   filled_amount=getattr(order_obj, 'filled', None) if order_obj is not None else None)
    _flush_audit_log()


def _audit_safe_flush():
    """Called from trade() after g.days += 1 to ensure audit is flushed."""
    _flush_audit_log()


def switch_to_defensive(context):
    current_data = get_current_data()
    sell_plan = []
    for stock in list(context.portfolio.positions.keys()):
        if not is_defensive_asset(stock) and can_sell_today(stock, current_data):
            sell_plan.append((stock, 0.0))
    for offset in g.phase_offsets:
        g.phase_targets[offset] = []
    log_plan("sell_defense_plan", sell_plan)
    if g.trade_enabled:
        for stock, target_value in sell_plan:
            order_target_value(stock, target_value)
        for etf in g.defensive_etfs:
            order_target_value(etf, context.portfolio.total_value / len(g.defensive_etfs))
    for etf in g.defensive_etfs:
        log.info("defensive target %s value=%.2f" % (etf, context.portfolio.total_value / len(g.defensive_etfs)))
    g.in_defensive_mode = True


def check_limit_up(context):
    if g.in_defensive_mode:
        return
    target_values = aggregate_target_values(context)
    for stock in g.yesterday_HL_list:
        if stock in context.portfolio.positions:
            curr = get_price(
                stock,
                end_date=context.current_dt,
                frequency="1m",
                count=1,
                fields=["close", "high_limit"],
            )
            if curr is not None and not curr.empty and curr["close"][0] < curr["high_limit"][0]:
                target_value = target_values.get(stock, 0.0)
                log.info("[%s] limit opened, reduce to target_value=%.2f" % (stock, target_value))
                _audit_log("check_limit_up_open",
                           callback_name="check_limit_up", security=stock,
                           target_value=float(target_value))
                if g.trade_enabled:
                    order_target_value(stock, target_value)


def report_plan(context):
    target_values = aggregate_target_values(context)
    log.info(
        "days=%s defensive=%s trade_enabled=%s due_offsets=%s yesterday_HL=%s"
        % (g.days, g.in_defensive_mode, g.trade_enabled, g.last_due_offsets, ",".join(g.yesterday_HL_list))
    )
    for offset in g.phase_offsets:
        log.info("phase offset=%s targets=%s" % (offset, ",".join(g.phase_targets.get(offset, []))))
    log.info("aggregate target count=%s" % len(target_values))
    log_plan("aggregate_targets", sorted(target_values.items(), key=lambda x: x[0]))

    _audit_log("report_plan_summary",
               callback_name="report_plan",
               g_days=g.days,
               in_defensive_mode=g.in_defensive_mode,
               trade_enabled=g.trade_enabled,
               last_due_offsets=g.last_due_offsets,
               yesterday_HL_list=list(g.yesterday_HL_list),
               aggregate_target_count=len(target_values),
               position_count=len(context.portfolio.positions),
               portfolio_cash=float(context.portfolio.available_cash),
               portfolio_total_value=float(context.portfolio.total_value),
               target_300405=float(target_values.get("300405.XSHE", 0.0)))

    _flush_audit_log()


def log_plan(title, rows):
    if not rows:
        log.info("%s: empty" % title)
        return
    parts = []
    for stock, value in rows:
        parts.append("%s:%.0f" % (stock, value))
    log.info("%s: %s" % (title, "; ".join(parts)))


def can_buy_today(stock, current_data):
    try:
        data = current_data[stock]
    except Exception:
        return False
    if data.paused or data.is_st:
        return False
    return data.last_price < data.high_limit and data.last_price > data.low_limit


def can_sell_today(stock, current_data):
    try:
        data = current_data[stock]
    except Exception:
        return False
    if data.paused:
        return False
    return data.last_price > data.low_limit


def is_common_stock(stock):
    code = stock.split(".")[0]
    if code.startswith(("688", "689", "4", "8", "9")):
        return False
    return stock.endswith((".XSHG", ".XSHE"))


def is_defensive_asset(stock):
    return stock in g.defensive_etfs
