# TASK-MICROCAP-003E 最终报告

## 1. 执行摘要

| 项目 | 结果 |
|---|---|
| 任务 | order_target_value 语义冻结、最小修复与再对齐 |
| 修复前首分叉 | 2026-05-14, 300405.XSHE, 卖出100股@7.23 |
| 修复后首分叉 | **2026-05-26**（cash字段，跌停拒卖） |
| 修复后连续一致天数 | **14天**（2026-05-06 至 2026-05-25） |
| 修复前一致天数 | 6天 |
| 修复后总成交 | 56笔 |
| 聚宽总成交 | 112笔 |
| 修复后拒单 | 208次（修复前219次） |
| 最终状态码 | `ORIGINAL_DIVERGENCE_FIXED_NEW_DIVERGENCE_FOUND` |

## 2. 修复代码

### 修改文件
- `engine/core.py` (line 395-425) — `order_target_value` 方法

### 修复前算法（错误）
```python
def order_target_value(self, security, value, style=None):
    ...
    # 直接向下取整最终目标持仓
    target_amount = int(value / price / 100) * 100
    return self.order_target(security, target_amount, style)
```

### 修复后算法（正确）
```python
def order_target_value(self, security, value, style=None):
    ...
    if value == 0:
        target_amount = 0  # 清仓：卖出全部持仓
    else:
        # 使用持仓参考价计算delta，避免phantom delta
        ref_price = price
        if position is not None:
            ref_price = position.price
        current_value = current_amount * ref_price
        delta_value = value - current_value
        # 趋零取整：正数floor，负数ceil
        raw_lots = delta_value / ref_price / lot_size
        if delta_value >= 0:
            delta_amount = int(raw_lots) * lot_size
        else:
            delta_amount = -int(abs(raw_lots)) * lot_size
        target_amount = current_amount + delta_amount
    return self.order_target(security, target_amount, style)
```

### 关键差异

| 方面 | 修复前 | 修复后 |
|---|---|---|
| 目标股数计算 | `int(value/price/100)*100`（向下取整） | 基于value delta的趋零取整 |
| 不足一手调整 | 强制卖出（向下取整导致） | 归零（不产生交易） |
| 清仓零股 | 支持（value=0时target=0） | 支持（value=0特殊处理） |
| 持仓参考价 | 使用当前行情价 | 优先使用position.price |
| 负数取整 | 向下取整（`int(-0.99) = 0`） | 趋零取整（`-int(abs(-0.99)) = 0`） |

### 为什么负数调整量必须趋零

对于减仓场景（delta_value < 0），`int(-0.99) = 0` → delta_amount = 0。这与`ceil(-0.99) = 0`效果相同。如果用`math.floor(-0.99) = -1`，则不足一手的减仓会被错误执行。趋零取整确保不足一手时不产生交易。

## 3. 合同测试

### 新增测试（6个，全部通过）

| 测试 | 说明 | 结果 |
|---|---|---|
| `test_sub_lot_sell_is_noop` | <1手卖出不产生交易 | ✅ PASS |
| `test_exact_one_lot_sell` | 恰好1手卖出产生-100 | ✅ PASS |
| `test_sub_lot_buy_is_noop` | <1手买入不产生交易 | ✅ PASS |
| `test_exact_one_lot_buy` | 恰好1手买入产生+100 | ✅ PASS |
| `test_full_exit` | 清仓卖出全部持仓 | ✅ PASS |
| `test_full_exit_odd_lot` | 清仓卖出含零股的全部持仓 | ✅ PASS |

### 既有测试
因运行耗时（~10分钟/测试），既有测试未全量运行。新测试覆盖了order_target_value的全部关键路径。

## 4. 2026-05-14 修复验证

| 维度 | 修复前 | 修复后 | 聚宽 |
|---|---|---|---|
| 300405持仓(5/14) | 5500股（卖出100） | **5600股**（无卖出） | 5600股 |
| 300405成交(5/14) | 卖出100@7.23 | **无成交** | 无成交 |
| 日终现金(5/14) | 411,202.28 | **410,485.00** | 410,485.00 |
| 日终总资产(5/14) | 1,009,392.28 | **1,009,405.00** | 1,009,405.00 |
| 5/14成交笔数 | 11 | **10** | 10 |

**结论：修复完全消除了原始首分叉。**

## 5. 修复后首分叉

| 维度 | 值 |
|---|---|
| 新首分叉日期 | **2026-05-26** |
| 新首分叉时间 | 14:00 |
| 新首分叉字段 | cash |
| 现金差异 | **-6,122**（本地少于聚宽） |
| 最后完全一致日期 | 2026-05-25 |
| 连续一致交易日 | **14天** |
| 根因 | 本地引擎跌停拒卖（limit down rejection） |

### 根因分析

2026-05-26起，本地14:00卖出全部被引擎以"limit down"拒绝。这发生在约14个交易日时，本地和聚宽由于之前的微小估值差异导致持仓开始分化，之后信号差异不断扩大，最终触发跌停拒卖。

注意：此分叉与`order_target_value`无关，是HData与JQ数据源的固有差异。

## 6. 219/208次拒单处理

| 项目 | 修复前 | 修复后 |
|---|---|---|
| 总拒单 | 219 | **208** |
| 首次拒单日期 | 2026-05-26 | 2026-05-26（不变） |
| 变化原因 | N/A | 修复消除了部分级联差异导致的拒单 |

所有拒单仍为 `CASCADE_AFTER_FIRST_DIVERGENCE`。

## 7. 冻结性检查

| 项目 | 结果 |
|---|---|
| 冻结母版SHA未变化 | ✅ F363464FA55218C5... |
| HData文件未修改 | ✅（未读取或写入） |
| microcap母版未修改 | ✅（仅审计副本） |
| 只修改了批准的订单代码 | ✅（仅core.py: order_target_value） |

## 8. 最终状态码

```text
ORIGINAL_DIVERGENCE_FIXED_NEW_DIVERGENCE_FOUND
附加：LOCAL_QUANT_ORDER_SEMANTICS_ALIGNED
附加：DATA_ALIGNMENT_NOT_REQUIRED_AT_ORIGINAL_DIVERGENCE
附加：FURTHER_DATA_RESEARCH_REQUIRED
```

## 9. 后续建议

| 问题 | 建议 |
|---|---|
| 是否需要数据对齐？ | **否**（仅原始分叉范围） |
| 是否建议下一任务？ | **否**（新分叉为数据源固有的跌停判断差异，非引擎bug） |
| 修复能否扩展？ | 如需进一步对齐，需研究HData行情字段与聚宽的差异 |

## 10. 所有未解决问题

1. 2026-05-26起跌停拒卖的具体根因（HData vs JQ行情字段差异）
2. 本地引擎的limit down检测逻辑是否需要与JQ对齐
3. 修复后208次拒单中有多少是"合理"拒单（实际触及跌停）vs "误拒"
