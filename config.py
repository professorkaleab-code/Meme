"""
Settings for the BTC / ETH / SOL futures bot (paper trading only - no real money).
Edit the numbers here to change how the bot behaves. Money amounts are in US dollars.
"""

# ---------------- Markets ----------------
SYMBOLS = ["BTC", "ETH", "SOL"]
TIMEFRAME = "4h"                 # candle size the strategy uses: "1h" or "4h"
STRATEGY = "donchian"            # "donchian", "ema_trend" or "rsi_dip" - pick using `python main.py backtest`
ALLOW_SHORTS = True              # futures can profit from falling prices too

# ---------------- Paper account & risk ----------------
STARTING_BALANCE_USD = 100.0
RISK_PER_TRADE_PCT = 2.0         # lose at most ~2% of the account if a stop-loss is hit
MAX_LEVERAGE = 3.0               # total position size never exceeds 3x your account
MAX_DAILY_LOSS_PCT = 6.0         # stop opening new trades for the day after losing 6%
ATR_STOP_MULT = 2.5              # stop-loss distance = 2.5 x ATR (average candle range)

# ---------------- Costs (realistic futures costs) ----------------
TAKER_FEE_PCT = 0.055            # exchange fee per side (Binance/Bybit taker ~0.05%)
SLIPPAGE_PCT = 0.02              # majors are very liquid
FUNDING_PCT_PER_8H = 0.01        # typical funding paid by longs every 8 hours (shorts get nothing here, to be safe)

# ---------------- Backtest ----------------
HISTORY_DAYS = 3 * 365           # how much price history to download
OUT_OF_SAMPLE_PCT = 30           # the last 30% of history is kept as an "unseen" test

# ---------------- Paper trading loop ----------------
CHECK_SECONDS = 60               # how often to check prices
