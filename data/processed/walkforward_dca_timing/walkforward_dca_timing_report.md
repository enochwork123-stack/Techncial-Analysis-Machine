# Walk-Forward Monthly DCA Timing Validation

Out-of-sample period: `2023-01-01` to `2026-06-12`.
Training windows use only data before each test year. Selected rules are then applied to the following unseen year.
Execution uses same-day close after signal/contribution; this is optimistic versus next-day execution but does not use future bars.

## Direct Answers

1. Entry-timing-only DCA beat plain DCA for 4 of 80 symbol/objective combinations.
2. Core+tactical DCA beat plain DCA for 2 of 80 symbol/objective combinations.
3. Objective win counts are shown below; judge by out-of-sample excess, not training fit.
4. Strategy family counts are in the workbook. They show which rules survived train-only selection.
5. Bollinger dominance is weakened if other families appear frequently after walk-forward selection.
6. Biggest beneficiaries are the top rows by excess final equity in the summary CSV.
7. Most harmed names are the bottom rows by excess final equity.
8. Cash drag is measured by average cash ratio and held-cash months.
9. Compare the walk-forward win counts below with the earlier in-sample 18/20 and 17/20 result; any reduction is overfit evidence.
10. A practical rule should favor the simplest objective/framework that wins broadly with modest cash drag.

## Objective Win Counts

| framework | objective | beat_plain_dca |
| --- | --- | --- |
| B_entry_timing_only_no_sell | final_equity | 1 |
| B_entry_timing_only_no_sell | irr | 1 |
| B_entry_timing_only_no_sell | plateau | 2 |
| B_entry_timing_only_no_sell | risk_adjusted | 0 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | 0 |
| C_60pct_dca_40pct_tactical_reserve | irr | 0 |
| C_60pct_dca_40pct_tactical_reserve | plateau | 1 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | 1 |

## Selected Family Counts

| framework | objective | strategy_family | count |
| --- | --- | --- | --- |
| B_entry_timing_only_no_sell | final_equity | bollinger_mean_reversion | 34 |
| B_entry_timing_only_no_sell | final_equity | donchian_breakout | 2 |
| B_entry_timing_only_no_sell | final_equity | macd_momentum | 5 |
| B_entry_timing_only_no_sell | final_equity | qqq_200d_market_filter | 3 |
| B_entry_timing_only_no_sell | final_equity | rsi_pullback | 10 |
| B_entry_timing_only_no_sell | final_equity | simple_200d_trend | 2 |
| B_entry_timing_only_no_sell | final_equity | simple_pullback | 14 |
| B_entry_timing_only_no_sell | final_equity | volume_breakout | 9 |
| B_entry_timing_only_no_sell | irr | bollinger_mean_reversion | 34 |
| B_entry_timing_only_no_sell | irr | donchian_breakout | 2 |
| B_entry_timing_only_no_sell | irr | macd_momentum | 5 |
| B_entry_timing_only_no_sell | irr | qqq_200d_market_filter | 3 |
| B_entry_timing_only_no_sell | irr | rsi_pullback | 10 |
| B_entry_timing_only_no_sell | irr | simple_200d_trend | 2 |
| B_entry_timing_only_no_sell | irr | simple_pullback | 14 |
| B_entry_timing_only_no_sell | irr | volume_breakout | 9 |
| B_entry_timing_only_no_sell | plateau | bollinger_mean_reversion | 26 |
| B_entry_timing_only_no_sell | plateau | donchian_breakout | 3 |
| B_entry_timing_only_no_sell | plateau | macd_momentum | 8 |
| B_entry_timing_only_no_sell | plateau | qqq_200d_market_filter | 5 |
| B_entry_timing_only_no_sell | plateau | rsi_pullback | 9 |
| B_entry_timing_only_no_sell | plateau | simple_200d_trend | 3 |
| B_entry_timing_only_no_sell | plateau | simple_pullback | 23 |
| B_entry_timing_only_no_sell | plateau | volume_breakout | 2 |
| B_entry_timing_only_no_sell | risk_adjusted | bollinger_mean_reversion | 23 |
| B_entry_timing_only_no_sell | risk_adjusted | donchian_breakout | 7 |
| B_entry_timing_only_no_sell | risk_adjusted | macd_momentum | 5 |
| B_entry_timing_only_no_sell | risk_adjusted | rsi_pullback | 19 |
| B_entry_timing_only_no_sell | risk_adjusted | simple_pullback | 10 |
| B_entry_timing_only_no_sell | risk_adjusted | supertrend | 2 |
| B_entry_timing_only_no_sell | risk_adjusted | volume_breakout | 13 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | bollinger_mean_reversion | 37 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | donchian_breakout | 3 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | macd_momentum | 3 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | qqq_200d_market_filter | 1 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | rsi_pullback | 13 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | simple_pullback | 9 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | supertrend | 4 |
| C_60pct_dca_40pct_tactical_reserve | final_equity | volume_breakout | 9 |
| C_60pct_dca_40pct_tactical_reserve | irr | bollinger_mean_reversion | 37 |
| C_60pct_dca_40pct_tactical_reserve | irr | donchian_breakout | 3 |
| C_60pct_dca_40pct_tactical_reserve | irr | macd_momentum | 3 |
| C_60pct_dca_40pct_tactical_reserve | irr | qqq_200d_market_filter | 1 |
| C_60pct_dca_40pct_tactical_reserve | irr | rsi_pullback | 13 |
| C_60pct_dca_40pct_tactical_reserve | irr | simple_pullback | 9 |
| C_60pct_dca_40pct_tactical_reserve | irr | supertrend | 4 |
| C_60pct_dca_40pct_tactical_reserve | irr | volume_breakout | 9 |
| C_60pct_dca_40pct_tactical_reserve | plateau | bollinger_mean_reversion | 29 |
| C_60pct_dca_40pct_tactical_reserve | plateau | donchian_breakout | 3 |
| C_60pct_dca_40pct_tactical_reserve | plateau | macd_momentum | 7 |
| C_60pct_dca_40pct_tactical_reserve | plateau | qqq_200d_market_filter | 1 |
| C_60pct_dca_40pct_tactical_reserve | plateau | rsi_pullback | 15 |
| C_60pct_dca_40pct_tactical_reserve | plateau | simple_pullback | 18 |
| C_60pct_dca_40pct_tactical_reserve | plateau | supertrend | 4 |
| C_60pct_dca_40pct_tactical_reserve | plateau | volume_breakout | 2 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | bollinger_mean_reversion | 20 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | donchian_breakout | 6 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | macd_momentum | 7 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | qqq_200d_market_filter | 3 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | rsi_pullback | 13 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | simple_pullback | 17 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | supertrend | 4 |
| C_60pct_dca_40pct_tactical_reserve | risk_adjusted | volume_breakout | 9 |

## Top Entry-Timing OOS Results

| symbol | objective | final_equity | excess_final_equity_vs_plain_dca | money_weighted_irr_pct | average_cash_pct |
| --- | --- | --- | --- | --- | --- |
| MSFT | plateau | 435224.30 | 2230.65 | 2.06 | 24.76 |
| NFLX | plateau | 551044.80 | 2079.85 | 16.17 | 13.44 |
| NFLX | irr | 551044.80 | 2079.85 | 16.17 | 13.44 |
| NFLX | final_equity | 551044.80 | 2079.85 | 16.17 | 13.44 |
| MSFT | final_equity | 418782.99 | -14210.65 | -0.17 | 32.87 |
| MSFT | irr | 418782.99 | -14210.65 | -0.17 | 32.87 |
| NFLX | risk_adjusted | 533661.33 | -15303.62 | 14.20 | 11.54 |
| CSCO | risk_adjusted | 909914.17 | -16355.53 | 49.07 | 9.04 |
| WMT | irr | 708965.52 | -16791.06 | 32.17 | 11.49 |
| WMT | final_equity | 708965.52 | -16791.06 | 32.17 | 11.49 |

## Top Core+Tactical OOS Results

| symbol | objective | final_equity | excess_final_equity_vs_plain_dca | money_weighted_irr_pct | average_cash_pct |
| --- | --- | --- | --- | --- | --- |
| MSFT | plateau | 433885.91 | 892.26 | 1.88 | 9.32 |
| ASML | risk_adjusted | 991341.73 | 608.32 | 55.14 | 4.68 |
| MSFT | risk_adjusted | 427309.38 | -5684.26 | 1.00 | 12.26 |
| MSFT | irr | 427309.38 | -5684.26 | 1.00 | 12.26 |
| MSFT | final_equity | 427309.38 | -5684.26 | 1.00 | 12.26 |
| WMT | final_equity | 719214.28 | -6542.30 | 33.11 | 4.39 |
| WMT | irr | 719214.28 | -6542.30 | 33.11 | 4.39 |
| WMT | risk_adjusted | 718538.44 | -7218.14 | 33.05 | 4.41 |
| AAPL | risk_adjusted | 595328.23 | -7514.60 | 20.97 | 4.26 |
| WMT | plateau | 718095.55 | -7661.03 | 33.01 | 4.31 |

## Conclusion Categories

- Robust: None
- Mixed: MSFT, NFLX
- Not worth it: AAPL, AMAT, AMD, AMZN, ARM, ASML, AVGO, COST, CSCO, GOOG, GOOGL, INTC, LRCX, META, MU, NVDA, TSLA, WMT

## Caveats

- This validates rule selection by year, but it still uses the current candidate library chosen by the researcher.
- Same-day close execution can be generous. A next-day execution rerun would be stricter.
- QQQ 200D and stock 200D rules are automatically cash-heavy in early windows if insufficient moving-average history exists.
