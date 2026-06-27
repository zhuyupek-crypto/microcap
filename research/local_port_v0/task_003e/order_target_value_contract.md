# order_target_value 行为合同（2026-06-27 冻结）

## 1. 语义

`order_target_value(security, target_value)` 将持仓调整到目标价值，而非目标股数。

## 2. 核心规则

### 2.1 清仓（target_value = 0）

- `order_target_value(security, 0)` 卖出全部持仓
- 允许卖出零股（不足100股的部分）
- 不因整数手规则残留持仓

### 2.2 非清仓（target_value > 0）

- 基于价值差额（delta_value = target_value - current_value）而非目标股数取整
- 不足一手的价值差额不产生交易
- 恰好一手的价值差额产生100股交易
- 负的delta_value使用趋零取整（`-int(abs(raw_lots)) * lot_size`）
- 正的delta_value使用`int(raw_lots) * lot_size`

### 2.3 参考价格

- 优先使用 `position.price`（持仓参考价，与策略内部估值一致）
- 避免 `curr_price` 与 `pos.price` 差异导致的phantom delta

## 3. 边界测试表

### 减仓边界（current_amount=5600, price=10）

| target_value | delta_value | expected_delta |
|---|---|---|
| 55,999 | -1 | 0 |
| 55,001 | -999 | 0 |
| 55,000 | -1,000 | -100 |
| 54,999 | -1,001 | -100 |
| 54,000 | -2,000 | -200 |
| 0 | -56,000 | -5,600 |

### 加仓边界（current_amount=5000, price=10）

| target_value | delta_value | expected_delta |
|---|---|---|
| 50,001 | +1 | 0 |
| 50,999 | +999 | 0 |
| 51,000 | +1,000 | +100 |
| 52,000 | +2,000 | +200 |

## 4. 证据来源

- TASK-003D1 根因分析：300405.XSHE 首分叉案例
- local_quant 单元测试：6个合同测试全部通过
- 35日完整回测：2026-05-14首分叉已消除，14日连续一致

## 5. 实际案例验证

### 案例：300405.XSHE（2026-05-14 本地输入）

| 字段 | 值 |
|---|---|
| current_amount | 5,600 |
| price | 7.23 |
| current_value | 40,488 |
| target_value | 40,210.28 |
| 修复前结果 | 卖出100股（错误） |
| 修复后结果 | 无交易（正确） |

### 案例：300405.XSHE（2026-05-14 JQ推断输入）

| 字段 | 值 |
|---|---|
| current_amount | 5,600 |
| price | 7.24 |
| current_value | 40,544 |
| target_value | ~40,086 |
| 修复前结果 | 卖出100股（推断） |
| 修复后结果 | 无交易（推断） |
