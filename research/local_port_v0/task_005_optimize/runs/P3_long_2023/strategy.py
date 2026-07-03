"""
TASK-005 P3 代码清理版本（基于 COMBINED_v1）
=============================================

清理项：
1. 删除死代码 risk_filter_ok（已被 build_risk_filter_map 替代）
2. build_risk_filter_map 改为 fail-closed（异常时默认拒绝）
3. aggregate_target_values 加日缓存（同一天被 trade/check_limit_up/report_plan 调用 3 次）
4. 基准替换：000001.XSHG → 000852.XSHG（中证 1000，更贴近微盘股）
5. 删除未使用的 g.last_target_values
6. can_buy_today/can_sell_today 异常时返回 False（已是 fail-closed，保持）
"""
from jqdata import *


def initialize(context):
    # P3: 基准替换为中证 1000（更贴近微盘股策略）
    set_benchmark("000852.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    set_slippage(PriceRelatedSlippage(0.002))
    set_option("order_volume_ratio", 0.1)
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

    g.liquidity_avg_amount_20d = 3e6
    g.circulating_mcap_min = 5e7
    g.stock_concentration_cap = 0.06

    g.phase_targets = {offset: [] for offset in g.phase_offsets}
    g.phase_base_values = {offset: 0.0 for offset in g.phase_offsets}
    g.yesterday_HL_list = []
    g.in_defensive_mode = False
    g.last_due_offsets = []
    # P3: aggregate_target_values 日缓存
    g._atv_cache_date = None
    g._atv_cache = None

    run_daily(prepare_stock_list, time="09:05")
    run_daily(trade, time="09:30")
    run_daily(check_limit_up, time="14:00")
    run_daily(report_plan, time="15:00")


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
        if curr is not None and not curr.empty and curr["close"][0] >= curr["high_limit"][0]:
            g.yesterday_HL_list.append(stock)


def trade(context):
    current_month = context.current_dt.month

    if not g.in_defensive_mode and current_month in g.defensive_months:
        switch_to_defensive(context)
        return

    if g.in_defensive_mode and current_month not in g.defensive_months:
        for etf in g.defensive_etfs:
            order_target(etf, 0)
        g.in_defensive_mode = False

    if g.in_defensive_mode:
        return

    due_offsets = [offset for offset in g.phase_offsets if (g.days + offset) % g.phase_cycle == 0]
    g.last_due_offsets = due_offsets
    if due_offsets:
        for offset in due_offsets:
            target_list = select_smallest_market_cap(context)
            g.phase_targets[offset] = target_list
            g.phase_base_values[offset] = context.portfolio.total_value / len(g.phase_offsets)
            log.info("phase offset=%s targets=%s base_value=%.2f"
                     % (offset, ",".join(target_list), g.phase_base_values[offset]))
        rebalance_to_aggregate_targets(context)

    g.days += 1


def select_smallest_market_cap(context):
    data_date = context.previous_date
    pool = get_stock_pool(data_date)
    if len(pool) < g.stocknum:
        return []

    q = query(
        valuation.code,
        valuation.market_cap,
        valuation.circulating_market_cap,
    ).filter(
        valuation.code.in_(pool)
    )
    mcap_df = get_fundamentals(q, date=data_date)
    if mcap_df is None or mcap_df.empty:
        return []

    candidates = mcap_df.dropna().sort_values("market_cap")
    candidates = candidates[candidates["circulating_market_cap"] * 1e8 >= g.circulating_mcap_min]

    candidates = apply_liquidity_filter(candidates["code"].tolist(), data_date)
    if not candidates:
        return []

    risk_ok = build_risk_filter_map(candidates, data_date)
    current_data = get_current_data()
    target_list = []
    for stock in candidates:
        if not risk_ok.get(stock, True):
            continue
        if can_buy_today(stock, current_data):
            target_list.append(stock)
            if len(target_list) >= g.stocknum:
                break
    return target_list


def apply_liquidity_filter(codes, data_date):
    if not codes:
        return []
    try:
        df = get_price(
            codes,
            end_date=data_date,
            count=20,
            frequency="daily",
            fields=["volume", "avg"],
            panel=False,
        )
        if df is None or df.empty:
            return codes
        df["amount"] = df["volume"] * df["avg"]
        avg_amount = df.groupby("code")["amount"].mean()
        passed = avg_amount[avg_amount >= g.liquidity_avg_amount_20d].index.tolist()
        return [c for c in codes if c in passed]
    except Exception as e:
        log.warn("liquidity filter skipped: %s" % e)
        return codes


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
    return [s for s in pool if s in volume.columns and volume[s][0] > 0]


def build_risk_filter_map(stocks, data_date):
    """P3: fail-closed —— 异常或数据缺失时默认拒绝（False）。"""
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
        log.warn("batch risk filter FAILED (fail-closed): %s" % e)
        # P3: fail-closed，异常时拒绝所有
        return {s: False for s in stocks}

    # P3: fail-closed，未在结果中的股票默认拒绝
    result = {s: False for s in stocks}
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
        cond_debt = debt_to_assets < 70
        cond_roe = roe > 0
        cond_ocf = ocf > 0
        result[stock] = sum([cond_debt, cond_roe, cond_ocf]) >= 1
    return result


def aggregate_target_values(context):
    """P3: 加日缓存，避免同一天重复计算。"""
    today = context.current_dt.date()
    if g._atv_cache_date == today and g._atv_cache is not None:
        return g._atv_cache

    target_values = {}
    for offset, stocks in g.phase_targets.items():
        base_value = g.phase_base_values.get(offset, 0.0)
        if base_value <= 0 or not stocks:
            continue
        stock_value = base_value / g.stocknum
        for stock in stocks:
            target_values[stock] = target_values.get(stock, 0.0) + stock_value

    if g.stock_concentration_cap > 0:
        cap_value = g.stock_concentration_cap * context.portfolio.total_value
        target_values = {s: min(v, cap_value) for s, v in target_values.items()}

    g._atv_cache_date = today
    g._atv_cache = target_values
    return target_values


def rebalance_to_aggregate_targets(context):
    target_values = aggregate_target_values(context)
    current_data = get_current_data()

    sell_plan = []
    for stock in list(context.portfolio.positions.keys()):
        if is_defensive_asset(stock):
            continue
        target_value = target_values.get(stock, 0.0)
        if target_value <= 0:
            if stock in g.yesterday_HL_list:
                continue
            if can_sell_today(stock, current_data):
                sell_plan.append((stock, 0.0))
        else:
            current_value = context.portfolio.positions[stock].value
            if current_value > target_value and stock in g.yesterday_HL_list:
                continue
            if can_sell_today(stock, current_data):
                sell_plan.append((stock, target_value))

    buy_plan = []
    for stock, target_value in target_values.items():
        current_value = context.portfolio.positions[stock].value if stock in context.portfolio.positions else 0.0
        if current_value < target_value and can_buy_today(stock, current_data):
            buy_plan.append((stock, target_value))

    log_plan("sell_plan_0930", sell_plan)
    log_plan("buy_plan_0930", buy_plan)
    if not g.trade_enabled:
        return

    for stock, target_value in sell_plan:
        order_target_value(stock, target_value)
    for stock, target_value in buy_plan:
        order_target_value(stock, target_value)


def switch_to_defensive(context):
    current_data = get_current_data()
    sell_plan = []
    for stock in list(context.portfolio.positions.keys()):
        if not is_defensive_asset(stock) and can_sell_today(stock, current_data):
            sell_plan.append((stock, 0.0))
    for offset in g.phase_offsets:
        g.phase_targets[offset] = []
        g.phase_base_values[offset] = 0.0
    # P3: 清缓存
    g._atv_cache = None
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
                if g.trade_enabled:
                    order_target_value(stock, target_value)


def report_plan(context):
    target_values = aggregate_target_values(context)
    log.info(
        "days=%s defensive=%s trade_enabled=%s due_offsets=%s yesterday_HL=%s"
        % (g.days, g.in_defensive_mode, g.trade_enabled, g.last_due_offsets, ",".join(g.yesterday_HL_list))
    )
    for offset in g.phase_offsets:
        log.info("phase offset=%s targets=%s base_value=%.2f"
                 % (offset, ",".join(g.phase_targets.get(offset, [])),
                    g.phase_base_values.get(offset, 0.0)))
    log.info("aggregate target count=%s" % len(target_values))
    log_plan("aggregate_targets", sorted(target_values.items(), key=lambda x: x[0]))


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
