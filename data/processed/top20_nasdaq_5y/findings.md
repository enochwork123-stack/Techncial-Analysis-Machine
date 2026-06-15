# Top 20 Nasdaq 5-Year Strategy Optimization

Data window: `2021-06-14` to `2026-06-12`.
Price adjustment: `raw`.
Selection method: first rank default strategy families by total return, then optimize only the winning family using the project parameter grid.

This is an in-sample optimization report. It is useful for pattern discovery, not proof of live-trading edge.

## Universe

| Rank | Symbol | Company | Market Cap |
| ---: | --- | --- | ---: |
| 1 | NVDA | NVIDIA Corporation Common Stock | 4,965,598,000,000 |
| 2 | GOOGL | Alphabet Inc. Class A Common Stock | 4,357,882,880,000 |
| 3 | GOOG | Alphabet Inc. Class C Capital Stock | 4,339,466,560,000 |
| 4 | AAPL | Apple Inc. Common Stock | 4,275,929,952,280 |
| 5 | MSFT | Microsoft Corporation Common Stock | 2,902,586,576,241 |
| 6 | AMZN | Amazon.com, Inc. Common Stock | 2,566,108,455,958 |
| 7 | AVGO | Broadcom Inc. Common Stock | 1,817,728,666,250 |
| 8 | TSLA | Tesla, Inc. Common Stock | 1,526,438,852,891 |
| 9 | META | Meta Platforms, Inc. Class A Common Stock | 1,439,235,244,902 |
| 10 | MU | Micron Technology, Inc. Common Stock | 1,106,995,021,802 |
| 11 | WMT | Walmart Inc. Common Stock | 963,245,900,921 |
| 12 | AMD | Advanced Micro Devices, Inc. Common Stock | 834,166,368,893 |
| 13 | ASML | ASML Holding N.V. New York Registry Shares | 718,245,089,611 |
| 14 | INTC | Intel Corporation Common Stock | 626,088,820,000 |
| 15 | CSCO | Cisco Systems, Inc. Common Stock (DE) | 477,307,737,932 |
| 16 | LRCX | Lam Research Corporation Common Stock | 458,721,948,510 |
| 17 | AMAT | Applied Materials, Inc. Common Stock | 450,373,486,668 |
| 18 | COST | Costco Wholesale Corporation Common Stock | 435,651,403,109 |
| 19 | ARM | Arm Holdings plc American Depositary Shares | 405,202,880,514 |
| 20 | NFLX | Netflix, Inc. Common Stock | 338,295,553,740 |

## Best Strategy Summary

| Symbol | Best Strategy | Params | Return | Buy & Hold | Excess | Max DD | Trades | Sharpe |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MU | ema_cross | `{"fast_window": 20, "slow_window": 60}` | 712.70% | 1119.54% | -406.84% | -55.14% | 10 | 1.21 |
| LRCX | ema_cross | `{"fast_window": 10, "slow_window": 50}` | 457.05% | 464.11% | -7.06% | -38.69% | 10 | 1.15 |
| NVDA | supertrend | `{"atr_window": 10, "multiplier": 3.0}` | 450.01% | 1038.76% | -588.75% | -37.31% | 19 | 1.11 |
| AMD | donchian_breakout | `{"entry_window": 20, "exit_window": 10}` | 439.90% | 527.31% | -87.41% | -37.48% | 17 | 1.08 |
| AVGO | supertrend | `{"atr_window": 10, "multiplier": 3.5}` | 351.29% | 702.95% | -351.67% | -27.64% | 10 | 1.07 |
| ARM | macd_momentum | `{"fast": 8, "signal": 9, "slow": 26}` | 349.35% | 498.85% | -149.51% | -35.99% | 31 | 1.18 |
| TSLA | macd_momentum | `{"fast": 12, "signal": 9, "slow": 21}` | 238.01% | 97.40% | 140.61% | -39.76% | 51 | 0.81 |
| META | volume_breakout | `{"breakout_window": 20, "trend_window": 75, "volume_multiplier": 1.0}` | 216.93% | 68.36% | 148.58% | -22.63% | 8 | 1.02 |
| AMAT | supertrend | `{"atr_window": 7, "multiplier": 3.5}` | 215.47% | 308.01% | -92.54% | -29.17% | 13 | 0.87 |
| INTC | volume_breakout | `{"breakout_window": 40, "trend_window": 100, "volume_multiplier": 1.0}` | 200.27% | 114.07% | 86.19% | -36.14% | 8 | 0.79 |
| NFLX | ema_cross | `{"fast_window": 10, "slow_window": 50}` | 186.07% | 60.72% | 125.36% | -28.97% | 15 | 0.88 |
| ASML | ema_cross | `{"fast_window": 15, "slow_window": 30}` | 160.25% | 162.72% | -2.47% | -39.00% | 14 | 0.80 |
| GOOGL | ema_cross | `{"fast_window": 15, "slow_window": 50}` | 153.72% | 193.75% | -40.02% | -29.42% | 10 | 0.93 |
| GOOG | ema_cross | `{"fast_window": 15, "slow_window": 60}` | 124.69% | 183.46% | -58.78% | -31.72% | 10 | 0.83 |
| AMZN | rsi_pullback | `{"entry_threshold": 45, "exit_threshold": 65, "rsi_window": 21}` | 107.84% | 40.99% | 66.84% | -22.86% | 6 | 0.85 |
| COST | donchian_breakout | `{"entry_window": 10, "exit_window": 20}` | 86.08% | 155.98% | -69.90% | -26.37% | 17 | 0.77 |
| MSFT | bollinger_mean_reversion | `{"std_mult": 1.5, "window": 20}` | 85.18% | 50.35% | 34.83% | -13.75% | 37 | 0.82 |
| CSCO | ema_cross | `{"fast_window": 15, "slow_window": 60}` | 79.19% | 123.56% | -44.37% | -27.90% | 9 | 0.70 |
| AAPL | donchian_breakout | `{"entry_window": 10, "exit_window": 10}` | 77.19% | 123.12% | -45.93% | -23.46% | 25 | 0.74 |
| WMT | macd_momentum | `{"fast": 12, "signal": 9, "slow": 21}` | 66.09% | 158.34% | -92.25% | -14.84% | 48 | 0.73 |

## Pattern Observations

- Winning strategy families: {"bollinger_mean_reversion": 1, "donchian_breakout": 3, "ema_cross": 7, "macd_momentum": 3, "rsi_pullback": 1, "supertrend": 3, "volume_breakout": 2}.
- 6 of 20 optimized strategies beat buy-and-hold in-sample.
- 14 of 20 optimized strategies still lagged buy-and-hold.
- Trend and breakout rules tend to work best where the stock had persistent directional phases with recoverable pullbacks.
- Mean-reversion winners usually indicate repeated panic/rebound behavior rather than smooth compounding trend.
- Underperformance versus buy-and-hold is common in mega-cap momentum names because timing systems sit in cash during part of strong bull legs.
- The biggest underperformers versus buy-and-hold were not necessarily bad absolute strategies; several still made triple-digit returns but failed to keep up with exceptional semiconductor/AI compounding.
- A practical next step is to retest the best candidates with walk-forward validation and a risk-adjusted objective rather than pure total return.

## Underperformer Investigation

- **NVDA**: optimized `supertrend` returned 450.01% versus buy-and-hold 1038.76% (-588.75% excess). The strategy captured large trend legs but sold during high-volatility pauses; buy-and-hold won because the symbol compounded through deep pullbacks.
- **MU**: optimized `ema_cross` returned 712.70% versus buy-and-hold 1119.54% (-406.84% excess). The strategy captured large trend legs but sold during high-volatility pauses; buy-and-hold won because the symbol compounded through deep pullbacks.
- **AVGO**: optimized `supertrend` returned 351.29% versus buy-and-hold 702.95% (-351.67% excess). The strategy captured large trend legs but sold during high-volatility pauses; buy-and-hold won because the symbol compounded through deep pullbacks.
- **ARM**: optimized `macd_momentum` returned 349.35% versus buy-and-hold 498.85% (-149.51% excess). The strategy captured large trend legs but sold during high-volatility pauses; buy-and-hold won because the symbol compounded through deep pullbacks.
- **AMAT**: optimized `supertrend` returned 215.47% versus buy-and-hold 308.01% (-92.54% excess). The strategy captured large trend legs but sold during high-volatility pauses; buy-and-hold won because the symbol compounded through deep pullbacks.
- **WMT**: optimized `macd_momentum` returned 66.09% versus buy-and-hold 158.34% (-92.25% excess). The selected tactical rules traded frequently enough to add costs and cash drag; buy-and-hold benefited more from staying continuously exposed.
- **AMD**: optimized `donchian_breakout` returned 439.90% versus buy-and-hold 527.31% (-87.41% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.
- **COST**: optimized `donchian_breakout` returned 86.08% versus buy-and-hold 155.98% (-69.90% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.
- **GOOG**: optimized `ema_cross` returned 124.69% versus buy-and-hold 183.46% (-58.78% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.
- **AAPL**: optimized `donchian_breakout` returned 77.19% versus buy-and-hold 123.12% (-45.93% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.
- **CSCO**: optimized `ema_cross` returned 79.19% versus buy-and-hold 123.56% (-44.37% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.
- **GOOGL**: optimized `ema_cross` returned 153.72% versus buy-and-hold 193.75% (-40.02% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.
- **LRCX**: optimized `ema_cross` returned 457.05% versus buy-and-hold 464.11% (-7.06% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.
- **ASML**: optimized `ema_cross` returned 160.25% versus buy-and-hold 162.72% (-2.47% excess). Trend timing reduced exposure during selloffs but also missed rebounds; the stock's best days arrived close to volatile regime shifts.

## Research Caveats

- The optimization is in-sample over one 5-year period and can overfit recent market structure.
- The chosen objective is total return; a stricter production workflow should optimize a risk-adjusted objective and validate with walk-forward tests.
- Strategy names are transparent local implementations, not the TradingView MCP black-box definitions.
- Use raw data for TradingView-style price-level matching and adjusted data for long-horizon total-return research.
