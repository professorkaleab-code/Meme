"""Find Solana meme coins that pass safety filters and rank them."""
import time
import config as C
from memebot import api


def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def pair_metrics(p):
    tx1 = (p.get("txns") or {}).get("h1") or {}
    buys, sells = tx1.get("buys", 0), tx1.get("sells", 0)
    created = p.get("pairCreatedAt") or 0
    return {
        "address": p["baseToken"]["address"],
        "symbol": p["baseToken"].get("symbol", "?"),
        "name": p["baseToken"].get("name", "?"),
        "url": p.get("url", ""),
        "price": _num(p.get("priceUsd")),
        "liquidity": _num((p.get("liquidity") or {}).get("usd")),
        "volume24": _num((p.get("volume") or {}).get("h24")),
        "volume1": _num((p.get("volume") or {}).get("h1")),
        "mcap": _num(p.get("marketCap") or p.get("fdv")),
        "chg5m": _num((p.get("priceChange") or {}).get("m5")),
        "chg1h": _num((p.get("priceChange") or {}).get("h1")),
        "chg24h": _num((p.get("priceChange") or {}).get("h24")),
        "buys1h": buys,
        "sells1h": sells,
        "age_h": (time.time() * 1000 - created) / 3.6e6 if created else 0,
        "has_socials": bool((p.get("info") or {}).get("socials")),
    }


def basic_filter(m):
    """Return a list of reasons the coin fails (empty list = passes)."""
    why = []
    if m["price"] <= 0: why.append("no price")
    if m["liquidity"] < C.MIN_LIQUIDITY_USD: why.append(f"liquidity ${m['liquidity']:,.0f}")
    if m["volume24"] < C.MIN_VOLUME_24H_USD: why.append(f"24h vol ${m['volume24']:,.0f}")
    if not (C.MIN_MARKET_CAP_USD <= m["mcap"] <= C.MAX_MARKET_CAP_USD): why.append(f"mcap ${m['mcap']:,.0f}")
    if not (C.MIN_AGE_HOURS <= m["age_h"] <= C.MAX_AGE_HOURS): why.append(f"age {m['age_h']:.1f}h")
    if m["buys1h"] + m["sells1h"] < C.MIN_TXNS_1H: why.append("few txns")
    ratio = m["buys1h"] / max(m["sells1h"], 1)
    if ratio < C.MIN_BUY_SELL_RATIO_1H: why.append(f"buy/sell {ratio:.2f}")
    if not (C.MIN_PRICE_CHANGE_1H_PCT <= m["chg1h"] <= C.MAX_PRICE_CHANGE_1H_PCT): why.append(f"1h {m['chg1h']:+.0f}%")
    return why


def safety_filter(m):
    """RugCheck checks. Returns (reasons_failed, rug_data)."""
    if not C.USE_RUGCHECK:
        return [], {}
    r = api.rugcheck_summary(m["address"])
    if not r or "error" in r:
        return ["rugcheck unavailable"], r or {}
    why = []
    score = r.get("score_normalised", 100)
    if score > C.MAX_RUGCHECK_SCORE: why.append(f"rug score {score}")
    if (r.get("lpLockedPct") or 0) < C.MIN_LP_LOCKED_PCT: why.append(f"LP locked {r.get('lpLockedPct') or 0:.0f}%")
    if C.BLOCK_DANGER_RISKS:
        for risk in r.get("risks") or []:
            if risk.get("level") == "danger":
                why.append(f"DANGER: {risk.get('name')}")
    return why, r


def score(m):
    """Simple momentum score (higher = more attractive). Not a prediction!"""
    ratio = m["buys1h"] / max(m["sells1h"], 1)
    vol_to_liq = m["volume1"] / max(m["liquidity"], 1)
    s = 0.0
    s += min(ratio, 3.0) * 20                 # buy pressure
    s += min(vol_to_liq, 2.0) * 15            # active trading relative to pool size
    s += max(min(m["chg1h"], 60), -10) * 0.3  # healthy uptrend, capped
    s += max(min(m["chg5m"], 15), -15) * 0.5  # short-term direction
    s += 5 if m["has_socials"] else 0
    s += min(m["liquidity"] / 100_000, 1) * 10  # deeper pools are safer
    return round(s, 1)


def scan(verbose=False):
    """Return ranked list of candidate coins that passed every filter."""
    addrs = api.discover_token_addresses()
    pairs = api.get_best_pairs(addrs)
    print(f"Scanned {len(addrs)} tokens, {len(pairs)} have SOL/USDC pools.")
    passed = []
    for p in pairs.values():
        m = pair_metrics(p)
        why = basic_filter(m)
        if not why:
            why, rug = safety_filter(m)
            m["rug_score"] = rug.get("score_normalised")
            m["lp_locked"] = rug.get("lpLockedPct")
        if why:
            if verbose:
                print(f"  x {m['symbol']:<10} {'; '.join(why)}")
            continue
        m["score"] = score(m)
        passed.append(m)
    passed.sort(key=lambda x: x["score"], reverse=True)
    return passed


def print_candidates(cands):
    if not cands:
        print("No coins passed the filters right now. That's normal - most meme coins are junk.")
        return
    print(f"\n{'#':>2} {'SYMBOL':<10} {'SCORE':>6} {'PRICE':>12} {'LIQ':>10} {'MCAP':>11} {'1h%':>7} {'B/S':>5} {'AGE':>6} {'RUG':>4}")
    for i, m in enumerate(cands[:C.MAX_CANDIDATES_TO_SHOW], 1):
        print(f"{i:>2} {m['symbol'][:10]:<10} {m['score']:>6} {m['price']:>12.8g} {m['liquidity']:>10,.0f} "
              f"{m['mcap']:>11,.0f} {m['chg1h']:>+7.1f} {m['buys1h']/max(m['sells1h'],1):>5.2f} "
              f"{m['age_h']:>5.0f}h {m.get('rug_score') or 0:>4}")
    print("\nLinks:")
    for m in cands[:C.MAX_CANDIDATES_TO_SHOW]:
        print(f"  {m['symbol']}: {m['url']}")
