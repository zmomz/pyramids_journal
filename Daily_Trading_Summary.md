📊 Daily Trading Summary

📅 Date: {{DATE}}
⏰ Session: {{TIME_RANGE}}

Execution Summary
• Total Trades (Positions): {{TOTAL_TRADES}}

• Total Pyramids Executed: {{TOTAL_PYRAMIDS}}

• Total Capital Executed: {{TOTAL_EXECUTED_CAPITAL}} USDT


PnL Breakdown (Overall)
• Gross Profit: {{GROSS_PROFIT}} USDT
• Gross Loss: {{GROSS_LOSS}} USDT
• Net Profit: {{NET_PROFIT}} USDT
• Net Profit Percentage: {{NET_PROFIT_PERCENT}} %

PnL by Pair
• {{PAIR_1}}
Capital Executed: {{PAIR_1_CAPITAL}} USDT
Net Profit: {{PAIR_1_NET_PROFIT}} USDT ({{PAIR_1_NET_PERCENT}} %)

• {{PAIR_2}}
Capital Executed: {{PAIR_2_CAPITAL}} USDT
Net Profit: {{PAIR_2_NET_PROFIT}} USDT ({{PAIR_2_NET_PERCENT}} %)

• {{PAIR_3}}
Capital Executed: {{PAIR_3_CAPITAL}} USDT
Net Profit: {{PAIR_3_NET_PROFIT}} USDT ({{PAIR_3_NET_PERCENT}} %)

Performance Metrics:
• Win Rate: {{WIN_RATE}} %
• Profit Factor: {{PROFIT_FACTOR}}
• Capital ROI: {{CAPITAL_ROI}} %
• Avg Trade Return: {{AVG_PROFIT_PERCENT}} %




---

Notes for development:
• Total capital executed is the sum of all executed pyramids
• Net profit per pair includes all pyramids executed on that pair
• Percentages are calculated based on executed capital
• Fees are included in all calculations
• One exit closes all active pyramids per position