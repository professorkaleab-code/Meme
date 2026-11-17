# BTC / ETH / SOL futures bot — backtest + paper trading

> **Paper trading only. No exchange account, no API keys, no real money.**
> Most people who trade futures lose money. Leverage makes losses bigger. Nothing here is financial advice.

## What it does
1. **Backtest:** downloads ~3 years of 4-hour price candles for BTC, ETH and SOL (free public data:
   Binance → Bybit → GeckoTerminal as backups) and replays 3 strategies with realistic costs:
   exchange fee 0.055% + slippage 0.02% per side, funding 0.01% per 8h on longs, stop-losses (including price gaps).
   History is split: first 70% vs. the last 30% ("unseen") to catch strategies that only worked by luck.
2. **Paper trade:** runs the chosen strategy on live prices with a fake $100 account. It can go **LONG** (profit when
   price rises) or **SHORT** (profit when price falls).

## Strategies
| Name | Idea |
|---|---|
| `donchian` | Breakout: go long on a new 20-candle high, short on a new 20-candle low (with 200-EMA trend filter) |
| `ema_trend` | Trend following: long when the 20 EMA > 50 EMA and price above the 200 EMA; short the opposite |
| `rsi_dip` | Buy oversold dips in an uptrend / short overbought rallies in a downtrend |

## Risk rules (all in `config.py`)
- Each trade risks **2% of the account** if its stop-loss is hit (~$2 on $100)
- Stop-loss = 2.5 × ATR (average candle size), trailing as price moves your way
- Max **3x** leverage, max 6% loss per day, one position per coin

## Setup on Windows
```bat
cd Meme
git pull
venv\Scripts\activate
pip install -r requirements.txt
```

## Usage
| Command | What it does |
|---|---|
| `python main.py backtest` | Test all strategies on ~3 years of history (first run downloads data, ~1 min) |
| `python main.py backtest --tf 1h` | Same on 1-hour candles |
| `python main.py paper` | Paper trade live (Ctrl+C to stop, progress saved) |
| `python main.py report` | Show paper results |
| `python main.py reset` | Wipe the paper account |

To change the strategy, open `config.py` in Notepad and edit `STRATEGY = "..."`.

## History
- v1–v2: Solana meme coin bot. Paper result: −52% in the first day. Retired (code is in git history).
- v3: this futures bot.
