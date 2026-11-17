"""
Version 2 settings (v1 lost 52% in its first day of paper trading).
All bot settings live here. Edit these numbers to change how the bot behaves.
Money amounts are in US dollars.
"""

# ---------------- Paper trading account ----------------
STARTING_BALANCE_USD = 100.0     # fake money the paper account starts with
TRADE_SIZE_USD = 20.0            # how much to "spend" on each buy
MAX_OPEN_POSITIONS = 3           # never hold more than this many coins at once
MAX_DAILY_LOSS_USD = 40.0        # stop opening new trades for the day after losing this much
REBUY_COOLDOWN_HOURS = 24        # don't buy the same coin again within this many hours

# ---------------- Exit rules ----------------
TAKE_PROFIT_PCT = 40.0           # sell when up +40%
STOP_LOSS_PCT = 20.0             # sell when down -20%
TRAILING_START_PCT = 25.0        # once up +25%, start a trailing stop...
TRAILING_STOP_PCT = 12.0         # ...and sell if price falls 12% from its highest point (locks in ~+10%)
MAX_HOLD_HOURS = 6.0             # sell anyway after this long

# ---------------- Realistic cost simulation ----------------
SLIPPAGE_PCT = 1.5               # price moves against you when you buy/sell
SWAP_FEE_PCT = 0.5               # DEX / aggregator fee per swap
NETWORK_FEE_USD = 0.02           # Solana tx + priority fee per swap

# ---------------- Coin filters (scanner) ----------------
MIN_LIQUIDITY_USD = 30_000       # pools thinner than this are easy to manipulate
MIN_VOLUME_24H_USD = 100_000
MIN_MARKET_CAP_USD = 100_000
MAX_MARKET_CAP_USD = 20_000_000
MIN_AGE_HOURS = 3.0              # skip brand-new launches (most rugs happen here)
MAX_AGE_HOURS = 24 * 14          # focus on coins less than 2 weeks old
MAX_PRICE_CHANGE_1H_PCT = 40.0   # don't chase coins that already pumped too hard
MIN_PRICE_CHANGE_1H_PCT = -5.0   # don't buy a coin that is crashing
MIN_PRICE_CHANGE_5M_PCT = -3.0   # don't buy while it is dropping right now
MIN_BUY_SELL_RATIO_1H = 1.2  # need clearly more buyers than sellers
MIN_TXNS_1H = 100                # needs real activity

# ---------------- RugCheck safety ----------------
USE_RUGCHECK = True
MAX_RUGCHECK_SCORE = 30          # score_normalised 0-100, lower is safer
MIN_LP_LOCKED_PCT = 80.0         # % of liquidity that is locked/burned
BLOCK_DANGER_RISKS = True        # reject any token with a "danger" level risk

# ---------------- Loop ----------------
POLL_SECONDS = 60                # how often to scan for NEW coins to buy
EXIT_CHECK_SECONDS = 15          # how often to check prices of coins you hold (faster = smaller stop-loss gaps)
MAX_CANDIDATES_TO_SHOW = 10
