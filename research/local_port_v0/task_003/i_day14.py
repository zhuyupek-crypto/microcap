"""Investigate 2026-05-14 divergence at trade level."""
import pandas as pd, os

odir = r'D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003'

jq = pd.read_csv(os.path.join(odir, 'jq_trades_normalized.csv'))
jq14 = jq[jq['trade_date'] == '2026-05-14'].sort_values('source_sequence')
print('=== JQ TRADES 2026-05-14 ===')
print(jq14[['normalized_security_code','side','quantity','price','commission','gross_amount']].to_string())

local = pd.read_csv(os.path.join(odir, 'local_trades_normalized.csv'))
local14 = local[local['trade_date'] == '2026-05-14'].sort_values('trade_id')
print('\n=== LOCAL TRADES 2026-05-14 ===')
print(local14[['code','side','amount','price','commission']].to_string())

# Compare
print('\n=== PER-TRADE COMPARISON ===')
jq14_map = {}
for _, r in jq14.iterrows():
    jq14_map[r['normalized_security_code']] = r

total_jq = 0
total_local = 0
for _, r in local14.iterrows():
    sec = r['code']
    jqr = jq14_map.get(sec)
    local_gross = abs(r['amount'] * r['price'])
    total_local += local_gross
    if jqr is not None:
        jq_gross = abs(jqr['quantity'] * jqr['price'])
        total_jq += jq_gross
        diff = round(local_gross - jq_gross, 2)
        qty_ok = abs(r['amount']) == abs(jqr['quantity'])
        price_ok = abs(r['price'] - jqr['price']) < 0.01
        flag = ''
        if not qty_ok: flag += ' QTY_DIFF'
        if not price_ok: flag += ' PRICE_DIFF'
        print(f'  {sec}: JQ={int(jqr["quantity"])}@{jqr["price"]} gross={jq_gross:.2f}')
        print(f'         Local={int(abs(r["amount"]))}@{r["price"]} gross={local_gross:.2f} diff={diff}{flag}')
        del jq14_map[sec]
    else:
        print(f'  {sec}: JQ=NO_MATCH Local gross={local_gross:.2f}')

for sec, jqr in sorted(jq14_map.items()):
    jq_gross = abs(jqr['quantity'] * jqr['price'])
    total_jq += jq_gross
    print(f'  {sec}: JQ gross={jq_gross:.2f} qty={int(jqr["quantity"])}@{jqr["price"]} | Local=NO_MATCH')

print(f'\n  TOTAL JQ gross: {total_jq:.2f}')
print(f'  TOTAL Local gross: {total_local:.2f}')
print(f'  Gross diff: {total_local - total_jq:.2f}')

# Commission comparison
print('\n=== COMMISSION ===')
total_jq_comm = jq14['commission'].sum()
total_local_comm = local14['commission'].sum()
print(f'  JQ comm: {total_jq_comm}')
print(f'  Local comm: {total_local_comm}')
print(f'  Comm diff: {total_local_comm - total_jq_comm}')

# Account state before/after 2026-05-14
print('\n=== ACCOUNT STATE ===')
pre_jq = jq[jq['trade_date'] == '2026-05-13']
post_jq = jq14
print(f'  JQ: prev day trades: {len(pre_jq)}, this day trades: {len(post_jq)}')

# Check cash values
jq_port = pd.read_csv(os.path.join(odir, 'jq_portfolio_normalized.csv'))
jq_cash_summary = jq_port[jq_port['snapshot_type'] == 'cash_summary']
print('\n=== JQ CASH SUMMARY ===')
print(jq_cash_summary[jq_cash_summary['record_date'].isin(['2026-05-13','2026-05-14','2026-05-15'])][['record_date','available_cash','total_asset','reported_position_market_value']].to_string())

local_port = pd.read_csv(os.path.join(odir, 'local_portfolio_normalized.csv'))
print('\n=== LOCAL CASH SUMMARY ===')
print(local_port[local_port['date'].isin(['2026-05-13','2026-05-14','2026-05-15'])].to_string())
