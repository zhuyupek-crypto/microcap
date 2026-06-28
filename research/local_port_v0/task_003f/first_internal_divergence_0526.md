# TASK-MICROCAP-003F: 2026-05-26 14:00 数据链定位报告

## 1. 定位结论

```text
根因分类：ROOT_CAUSE_DATA_API_ADJUSTMENT
首次差异层：L1 (DataAPI._get_price_raw)
首个差异字段：high_limit
```

## 2. 证据链

### L0: 原始 HData parquet

文件：`{HDATA}/data/processed/1d_stock/2026.parquet`

parquet 文件中**没有存储 `high_limit` 列**。该字段在其他行情系统中通常由 `pre_close × 涨跌幅限制` 计算。

| 证券 | 日期 | close | pre_close | 正确 high_limit |
|---|---|---|---|---|
| 300417.XSHE | 2026-05-25 | 14.50 | 14.91 | 17.89 (14.91×1.20) |
| 301167.XSHE | 2026-05-25 | 16.59 | 16.98 | 20.38 |
| 600493.XSHG | 2026-05-25 | 6.94 | 7.18 | 7.90 (7.18×1.10) |
| 300535.XSHE | 2026-05-25 | 17.36 | 18.12 | 21.74 |

### L1: DataAPI._get_price_raw

调用参数：
```python
api._get_price_raw(sec, end_date="2026-05-25", frequency="daily",
                   fields=["close", "high_limit"], count=1, fq=None)
```

返回结果：**high_limit = close**（全部8次调用均如此）

| 证券 | 返回 close | 返回 high_limit | 预期 high_limit |
|---|---|---|---|
| 300417.XSHE | 14.50 | **14.50** | 17.89 |
| 301167.XSHE | 16.59 | **16.59** | 20.38 |

### L2–L3: 包装与策略层

L2 和 L3 返回与 L1 一致。策略层 `close >= high_limit` 始终为 True。

### 昨日涨停名单

```text
2026-05-26 yesterday_HL_list = [全部13只持仓证券]
```

因为每个持仓证券的 `close >= high_limit` 恒成立。

## 3. 14:00 check_limit_up 触发链

```text
prepare_stock_list (09:05)
  → get_price(close=14.5, high_limit=14.5)
  → close >= high_limit → 300417.XSHE 进入 yesterday_HL_list
  → 同样条件导致其他12只也进入

check_limit_up (14:00)
  → 遍历昨天涨停名单（13只）
  → 获取14:00分钟行情（close=14.13, high_limit=14.13）
  → close < high_limit? False（相等）
  → 但有4只满足：target_value_value - current_value 达到一手
  → 执行 order_target_value → 4笔买入
```

## 4. 根因判断

```text
ROOT_CAUSE_DATA_API_ADJUSTMENT

DataAPI.get_price 返回的 high_limit 等于 close，
而非从 pre_close × 涨跌幅限制计算得出。
```

## 5. 后续建议

| 问题 | 建议 |
|---|---|
| 是否需要修改 local_quant？ | **是** — `engine/data_api.py` 中 `high_limit` 计算 |
| 是否需要修改 HData？ | **否** — `high_limit` 是计算字段 |
| 是否需要聚宽增强日志？ | **否** — 根因已由本地数据链确认 |
