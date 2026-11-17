"""Trading strategies. Each returns, for every candle, the position it wants
AFTER that candle closes: +1 long, -1 short, 0 flat. Only closed candles are used."""


def ema(values, n):
    out, k, e = [], 2 / (n + 1), None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def atr(rows, n=14):
    out, a, prev = [], None, None
    for _, o, h, l, c, _v in rows:
        tr = h - l if prev is None else max(h - l, abs(h - prev), abs(l - prev))
        a = tr if a is None else (a * (n - 1) + tr) / n
        out.append(a)
        prev = c
    return out


def rsi(closes, n=14):
    out, g, l = [50.0], 0.0, 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
        out.append(100.0 if l == 0 else 100 - 100 / (1 + g / l))
    return out


def donchian(rows, entry_n=20, exit_n=10, trend_n=200):
    """Breakout: buy a new 20-candle high, sell short a new 20-candle low.
    Exit when price makes a 10-candle extreme the other way. Trend filter: 200 EMA."""
    closes = [r[4] for r in rows]
    trend = ema(closes, trend_n)
    pos, out = 0, []
    for i, (_, o, h, l, c, _v) in enumerate(rows):
        if i < entry_n:
            out.append(0)
            continue
        hi_e = max(r[2] for r in rows[i - entry_n:i])
        lo_e = min(r[3] for r in rows[i - entry_n:i])
        hi_x = max(r[2] for r in rows[i - exit_n:i])
        lo_x = min(r[3] for r in rows[i - exit_n:i])
        if pos == 1 and c < lo_x: pos = 0
        if pos == -1 and c > hi_x: pos = 0
        if pos == 0:
            if c > hi_e and c > trend[i]: pos = 1
            elif c < lo_e and c < trend[i]: pos = -1
        out.append(pos)
    return out


def ema_trend(rows, fast=20, slow=50, trend_n=200):
    """Follow the trend: long when fast EMA > slow EMA and price above the 200 EMA; short the opposite."""
    closes = [r[4] for r in rows]
    f, s, t = ema(closes, fast), ema(closes, slow), ema(closes, trend_n)
    out = []
    for i, c in enumerate(closes):
        if f[i] > s[i] and c > t[i]: out.append(1)
        elif f[i] < s[i] and c < t[i]: out.append(-1)
        else: out.append(0)
    return out


def rsi_dip(rows, trend_n=200, buy_below=30, sell_above=70, exit_at=55):
    """Buy oversold dips in an uptrend (short overbought rallies in a downtrend)."""
    closes = [r[4] for r in rows]
    r, t = rsi(closes), ema(closes, trend_n)
    pos, out = 0, []
    for i, c in enumerate(closes):
        if pos == 1 and r[i] > exit_at: pos = 0
        if pos == -1 and r[i] < 100 - exit_at: pos = 0
        if pos == 0:
            if r[i] < buy_below and c > t[i]: pos = 1
            elif r[i] > sell_above and c < t[i]: pos = -1
        out.append(pos)
    return out


STRATEGIES = {"donchian": donchian, "ema_trend": ema_trend, "rsi_dip": rsi_dip}
WARMUP = 200  # candles needed before signals are meaningful
