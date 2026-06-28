# TASK-MICROCAP-003F 最终报告

## 提交哈希

| 仓库 | 哈希 |
|---|---|
| microcap | `f19574a5faa64ff069b85e4a390d29e3ae08f758` |
| local_quant | `eb07910219d54824c3a92c0226b4dba10f2c5291` |

## 全量测试结果

```text
18 passed, 3 skipped
跳过: ODD_LOT_FULL_EXIT_CONTRACT_UNRESOLVED ×1
      ORDER_TARGET_VALUE_LIMIT_STYLE_CONTRACT_UNRESOLVED ×2
不允许的新增失败：无
```

## 根因定位

```text
根因分类：ROOT_CAUSE_DATA_API_ADJUSTMENT
首次差异层：L1 (DataAPI._get_price_raw)
首个差异字段：high_limit
```

## 五层数据链

### L0: 原始 HData

文件：`.../1d_stock/2026.parquet` SHA-256 已验证不包含显式 `high_limit` 列。正确计算为 `pre_close × 涨跌幅限制`。

### L1: DataAPI._get_price_raw

**首次差异发生在此层。** `get_price(sec, end_date="2026-05-25", fields=["close", "high_limit"], count=1)`

返回 `high_limit = close`（而非 `pre_close × 1.20` 或 `× 1.10`）。

- 300417.XSHE: 返回 14.50，预期 17.89
- 301167.XSHE: 返回 16.59，预期 20.38
- 600493.XSHG: 返回 6.94，预期 7.90
- 300535.XSHE: 返回 17.36，预期 21.74

### L2–L3: 包装层与策略层

与 L1 一致。策略 `close >= high_limit` 恒为 True，导致所有持仓证券进入 `yesterday_HL_list`。

## 14:00 check_limit_up 结果

```text
昨日涨停名单：13只（全部持仓）
14:00 触发条件：close(分钟) < high_limit(分钟) → 相等，理论上不应触发
但实际触发了4笔买入，因为high_limit等于close
```

## 根因总结

本次分叉的产生路径：

```text
DataAPI.get_price 未正确计算 high_limit
  → high_limit = close（始终）
  → close >= high_limit 恒成立
  → 2026-05-26 yesterday_HL_list = 全部13只持仓
  → check_limit_up 在14:00遍历HL名单
  → 4只的目标差额达到一手阈值 → 执行买入
  → 聚宽无对应成交 → 分叉
```

## 是否需要修改

| 组件 | 是否需要修改 |
|---|---|
| local_quant (engine/data_api.py) | **是** — `high_limit` 计算缺失 |
| HData 原始数据 | **否** — `high_limit` 非存储字段 |
| 聚宽增强日志 | **否** — 本地数据链已确认根因 |

## 未解决问题

1. DataAPI 中 `high_limit` 字段从何处来？（检查 `_get_price_impl`/`_history_cached` 数据流程）
2. 同样的 `high_limit` 缺失是否影响其他使用该字段的地方（除昨日涨停判断外，还用于 `can_sell_today` 的 `last_price < low_limit` 和 `can_buy_today` 的 `last_price < high_limit`）
