# Monthly DCA vs Technical-Timing DCA

Data window: `2021-06-14` to `2026-06-12`.
Price adjustment mode: `auto_adjust`.
Monthly contribution: `$10,000`, contributed on the first trading day of each month.
Costs: `0.10%` commission and `0.05%` slippage on every buy and sell.

Framework A invests every monthly contribution immediately and never sells.
Framework B holds each contribution as cash until the selected technical state is bullish, then buys with all available cash. It never sells existing shares.
Framework C invests 60% of each monthly contribution immediately and keeps 40% as a tactical reserve, deploying reserve cash only on fresh bullish/pullback-recovery entry signals. It never sells existing shares.

## Summary

- Framework B beat plain DCA for 18 of 20 symbols.
- Framework C beat plain DCA for 17 of 20 symbols.
- Framework B best strategy families: {"bollinger_mean_reversion": 10, "donchian_breakout": 2, "macd_momentum": 2, "rsi_pullback": 5, "supertrend": 1}.
- Framework C best strategy families: {"bollinger_mean_reversion": 13, "macd_momentum": 1, "rsi_pullback": 4, "supertrend": 1, "volume_breakout": 1}.
- The most important comparison metrics are final equity, net profit on contributed capital, and money-weighted IRR.

## Best B And C vs Plain DCA

| Symbol | Framework | Best Strategy | Params | Final Equity | Plain DCA | Excess | IRR | Plain IRR | Avg Cash |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AAPL | B_entry_timing_only_no_sell | macd_momentum | `{"fast": 12, "signal": 9, "slow": 21}` | $977,783 | $972,519 | $5,264 | 19.00% | 18.77% | 1.7% |
| AAPL | C_60pct_dca_40pct_tactical_reserve | macd_momentum | `{"fast": 12, "signal": 9, "slow": 21}` | $975,401 | $972,519 | $2,882 | 18.90% | 18.77% | 2.3% |
| AMAT | B_entry_timing_only_no_sell | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 65, "rsi_window": 10}` | $2,431,334 | $2,332,127 | $99,207 | 58.52% | 56.60% | 32.4% |
| AMAT | C_60pct_dca_40pct_tactical_reserve | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 55, "rsi_window": 10}` | $2,361,225 | $2,332,127 | $29,098 | 57.17% | 56.60% | 14.1% |
| AMD | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 30}` | $2,801,827 | $2,632,357 | $169,470 | 65.13% | 62.20% | 34.6% |
| AMD | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 30}` | $2,707,948 | $2,632,357 | $75,590 | 63.53% | 62.20% | 14.4% |
| AMZN | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $938,180 | $924,908 | $13,271 | 17.30% | 16.72% | 15.2% |
| AMZN | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $933,268 | $924,908 | $8,360 | 17.09% | 16.72% | 6.6% |
| ARM | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $1,260,126 | $1,162,846 | $97,280 | 120.76% | 111.51% | 17.1% |
| ARM | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $1,188,176 | $1,162,846 | $25,330 | 113.96% | 111.51% | 8.9% |
| ASML | B_entry_timing_only_no_sell | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 65, "rsi_window": 14}` | $1,648,674 | $1,584,402 | $64,272 | 41.09% | 39.36% | 31.7% |
| ASML | C_60pct_dca_40pct_tactical_reserve | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 55, "rsi_window": 14}` | $1,601,326 | $1,584,402 | $16,924 | 39.82% | 39.36% | 14.4% |
| AVGO | B_entry_timing_only_no_sell | donchian_breakout | `{"entry_window": 10, "exit_window": 20}` | $2,714,728 | $2,719,944 | $-5,217 | 63.64% | 63.73% | 1.6% |
| AVGO | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 1.5, "window": 15}` | $2,712,627 | $2,719,944 | $-7,317 | 63.61% | 63.73% | 2.5% |
| COST | B_entry_timing_only_no_sell | macd_momentum | `{"fast": 12, "signal": 9, "slow": 21}` | $971,250 | $971,486 | $-236 | 18.72% | 18.73% | 1.8% |
| COST | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.0, "window": 15}` | $968,380 | $971,486 | $-3,106 | 18.60% | 18.73% | 3.9% |
| CSCO | B_entry_timing_only_no_sell | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 60, "rsi_window": 10}` | $1,447,700 | $1,434,695 | $13,005 | 35.47% | 35.08% | 33.1% |
| CSCO | C_60pct_dca_40pct_tactical_reserve | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 55, "rsi_window": 10}` | $1,437,549 | $1,434,695 | $2,855 | 35.16% | 35.08% | 13.9% |
| GOOG | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $1,508,321 | $1,490,095 | $18,226 | 37.23% | 36.71% | 16.9% |
| GOOG | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $1,494,883 | $1,490,095 | $4,788 | 36.85% | 36.71% | 7.4% |
| GOOGL | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $1,522,409 | $1,505,969 | $16,440 | 37.63% | 37.16% | 16.8% |
| GOOGL | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $1,509,976 | $1,505,969 | $4,007 | 37.28% | 37.16% | 7.4% |
| INTC | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.0, "window": 30}` | $2,450,625 | $2,332,739 | $117,887 | 58.88% | 56.61% | 6.0% |
| INTC | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.0, "window": 30}` | $2,401,282 | $2,332,739 | $68,543 | 57.94% | 56.61% | 4.3% |
| LRCX | B_entry_timing_only_no_sell | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 65, "rsi_window": 14}` | $3,316,812 | $3,264,405 | $52,407 | 73.19% | 72.42% | 35.0% |
| LRCX | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.0, "window": 15}` | $3,261,943 | $3,264,405 | $-2,462 | 72.38% | 72.42% | 2.8% |
| META | B_entry_timing_only_no_sell | donchian_breakout | `{"entry_window": 55, "exit_window": 20}` | $1,354,399 | $1,113,887 | $240,512 | 32.62% | 24.39% | 32.5% |
| META | C_60pct_dca_40pct_tactical_reserve | volume_breakout | `{"breakout_window": 20, "trend_window": 50, "volume_multiplier": 1.0}` | $1,209,240 | $1,113,887 | $95,352 | 27.82% | 24.39% | 11.0% |
| MSFT | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 30}` | $751,172 | $706,538 | $44,634 | 8.29% | 5.84% | 22.6% |
| MSFT | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 30}` | $726,498 | $706,538 | $19,960 | 6.96% | 5.84% | 10.2% |
| MU | B_entry_timing_only_no_sell | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 60, "rsi_window": 14}` | $7,341,411 | $6,960,320 | $381,091 | 114.35% | 111.41% | 38.1% |
| MU | C_60pct_dca_40pct_tactical_reserve | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 55, "rsi_window": 14}` | $7,083,580 | $6,960,320 | $123,259 | 112.37% | 111.41% | 16.4% |
| NFLX | B_entry_timing_only_no_sell | supertrend | `{"atr_window": 14, "multiplier": 3.5}` | $1,217,919 | $1,004,033 | $213,886 | 28.12% | 20.09% | 22.4% |
| NFLX | C_60pct_dca_40pct_tactical_reserve | supertrend | `{"atr_window": 14, "multiplier": 3.5}` | $1,070,467 | $1,004,033 | $66,434 | 22.73% | 20.09% | 11.3% |
| NVDA | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $3,601,238 | $3,329,452 | $271,787 | 77.20% | 73.37% | 20.2% |
| NVDA | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 20}` | $3,419,608 | $3,329,452 | $90,157 | 74.67% | 73.37% | 9.7% |
| TSLA | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 15}` | $1,039,042 | $963,314 | $75,728 | 21.50% | 18.38% | 24.3% |
| TSLA | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.5, "window": 15}` | $995,105 | $963,314 | $31,792 | 19.72% | 18.38% | 10.4% |
| WMT | B_entry_timing_only_no_sell | bollinger_mean_reversion | `{"std_mult": 2.0, "window": 15}` | $1,252,798 | $1,246,810 | $5,988 | 29.31% | 29.11% | 8.8% |
| WMT | C_60pct_dca_40pct_tactical_reserve | bollinger_mean_reversion | `{"std_mult": 2.0, "window": 15}` | $1,248,738 | $1,246,810 | $1,927 | 29.17% | 29.11% | 3.8% |

## Laggard Investigation

- **AVGO B_entry_timing_only_no_sell**: best `donchian_breakout` ended $5,217 below plain DCA. Timing lagged because continuous monthly exposure captured the trend better than delayed deployment.
- **AVGO C_60pct_dca_40pct_tactical_reserve**: best `bollinger_mean_reversion` ended $7,317 below plain DCA. Timing lagged because continuous monthly exposure captured the trend better than delayed deployment.
- **COST B_entry_timing_only_no_sell**: best `macd_momentum` ended $236 below plain DCA. Timing lagged because continuous monthly exposure captured the trend better than delayed deployment.
- **COST C_60pct_dca_40pct_tactical_reserve**: best `bollinger_mean_reversion` ended $3,106 below plain DCA. Timing lagged because continuous monthly exposure captured the trend better than delayed deployment.
- **LRCX C_60pct_dca_40pct_tactical_reserve**: best `bollinger_mean_reversion` ended $2,462 below plain DCA. Timing lagged because continuous monthly exposure captured the trend better than delayed deployment.

## Research Caveats

- This remains an in-sample comparison because the best technical rule is selected after observing the full period.
- Monthly DCA changes the objective: cash drag and missed rebound days matter more than avoiding every drawdown.
- Framework B and C do not sell existing shares in this version; they only control new cash and reserve deployment.
- Use adjusted data for investment research. Raw mode is available only for TradingView price-level matching.
- The next fairer step is walk-forward selection: choose timing rules using prior data, then test future monthly contributions.
