"""Download candles (open time, open, high, low, close, volume) for BTC/ETH/SOL.

Tries several free public sources in order and uses the first that works:
  1. Binance public market data (years of history)
  2. Bybit public market data (years of history)
  3. GeckoTerminal DEX data (only the last 180 days)
No API key or account needed.
"""
import csv
import os
import time
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TF_SECONDS = {"1h": 3600, "4h": 14400}
GECKO_POOLS = {  # deep, long-lived DEX pools
    "BTC": "eth/pools/0x56534741cd8b152df6d48adf7ac51f75169a83b2",   # WBTC/USDT Uniswap v3
    "ETH": "eth/pools/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",   # WETH/USDC Uniswap v3
    "SOL": "solana/pools/Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",  # SOL/USDC
}
_s = requests.Session()
_s.headers["User-Agent"] = "cryptobot-paper/0.2"
_working_source = None


def _get(url, params=None):
    for attempt in range(5):
        r = _s.get(url, params=params, timeout=20)
        if r.status_code != 429:  # 429 = rate limited: wait and retry
            break
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()
    return r.json()


def _binance(sym, tf, start, end):
    out, t = [], start * 1000
    while t < end * 1000:
        rows = _get("https://data-api.binance.vision/api/v3/klines",
                    {"symbol": f"{sym}USDT", "interval": tf, "startTime": t, "limit": 1000})
        if not rows:
            break
        out += [[r[0] // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in rows]
        t = rows[-1][0] + TF_SECONDS[tf] * 1000
        if len(rows) < 1000:
            break
    return out


def _bybit(sym, tf, start, end):
    out, e = [], end * 1000
    while e > start * 1000:
        d = _get("https://api.bybit.com/v5/market/kline",
                 {"category": "linear", "symbol": f"{sym}USDT", "interval": TF_SECONDS[tf] // 60,
                  "end": e, "limit": 1000})
        rows = (d.get("result") or {}).get("list") or []
        if d.get("retCode") not in (0, None) or not rows:
            if not out:
                raise RuntimeError(d.get("retMsg", "bybit error"))
            break
        out += [[int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in rows]
        e = int(rows[-1][0]) - 1
        if len(rows) < 1000:
            break
    return [r for r in out if r[0] >= start]


def _gecko(sym, tf, start, end):
    start = max(start, end - 179 * 86400)  # free API limit: last 180 days
    out, before = [], end
    while before > start:
        d = _get(f"https://api.geckoterminal.com/api/v2/networks/{GECKO_POOLS[sym]}/ohlcv/hour",
                 {"aggregate": TF_SECONDS[tf] // 3600, "limit": 1000, "currency": "usd",
                  "token": "base", "before_timestamp": before})
        rows = d["data"]["attributes"]["ohlcv_list"]
        if not rows:
            break
        out += [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in rows]
        before = int(rows[-1][0])
        if len(rows) < 1000:
            break
        time.sleep(2.5)  # free API: 30 requests/minute
    return [r for r in out if r[0] >= start]


SOURCES = [("Binance", _binance), ("Bybit", _bybit), ("GeckoTerminal", _gecko)]


def fetch(sym, tf, days):
    """Return (source_name, candles sorted oldest->newest, de-duplicated)."""
    global _working_source
    end = int(time.time())
    start = end - days * 86400
    order = sorted(SOURCES, key=lambda s: s[0] != _working_source)
    errors = []
    for name, fn in order:
        try:
            rows = fn(sym, tf, start, end)
            if len(rows) > 50:
                _working_source = name
                rows = sorted({r[0]: r for r in rows}.values())
                return name, rows
            errors.append(f"{name}: no data")
        except Exception as e:
            errors.append(f"{name}: {str(e)[:80]}")
    raise RuntimeError("All data sources failed -> " + " | ".join(errors))


def closed_only(rows, tf):
    """Drop the candle that is still forming."""
    now = time.time()
    return [r for r in rows if r[0] + TF_SECONDS[tf] <= now]


def load_history(sym, tf, days, max_age_hours=12):
    """Download history once and cache it in data/ so backtests are fast."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"candles_{sym}_{tf}.csv")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_hours * 3600:
        with open(path, encoding="utf-8") as f:
            rows = [[int(r[0])] + [float(x) for x in r[1:6]] for r in csv.reader(f)]
        return "cache", rows
    src, rows = fetch(sym, tf, days)
    rows = closed_only(rows, tf)
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    return src, rows
