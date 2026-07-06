"""Analyze 2020 recon: separate 2020 in-scope vs 2021 out-of-scope."""
import pandas as pd

df = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_006g_r1_local_strict_reconcile\outputs\TRADE_RECON_2020.csv')
df['date'] = pd.to_datetime(df['date'])

# 只看 2020 年内（本地回测区间）
df2020 = df[df['date'].dt.year == 2020].copy()
print('=== 2020 年内对账（本地回测区间）===')
print(df2020['match_status'].value_counts())
em = (df2020['match_status'] == 'exact_match').sum()
total = len(df2020)
print(f'精确匹配率: {em}/{total} = {em/total*100:.1f}%')
print()

# 2021 年的（本地没跑）
df2021 = df[df['date'].dt.year == 2021].copy()
print('=== 2021 年（本地未回测，应排除）===')
print(df2021['match_status'].value_counts())
print()

# 2020 年 missing_in_local 详情
mil = df2020[df2020['match_status'] == 'missing_in_local']
print('=== 2020 年 missing_in_local 详情 ===')
print(mil[['date', 'code', 'side', 'jq_quantity', 'jq_price', 'jq_gross_amount']].to_string())
print()

# 2020 年 missing_in_jq 详情
mij = df2020[df2020['match_status'] == 'missing_in_jq']
print('=== 2020 年 missing_in_jq 详情 ===')
print(mij[['date', 'code', 'side', 'local_quantity', 'local_price', 'local_gross_amount']].to_string())
print()

# 2020 年 quantity_diff 详情
qd = df2020[df2020['match_status'] == 'quantity_diff']
print(f'=== 2020 年 quantity_diff: {len(qd)} 笔 ===')
print(qd[['date', 'code', 'side', 'jq_quantity', 'local_quantity', 'quantity_diff', 'jq_price', 'local_price']].head(20).to_string())
print()

# 2020 年 price_diff 详情
pd_df = df2020[df2020['match_status'] == 'price_diff']
print(f'=== 2020 年 price_diff: {len(pd_df)} 笔 ===')
print(pd_df[['date', 'code', 'side', 'jq_quantity', 'local_quantity', 'jq_price', 'local_price', 'price_diff']].to_string())
