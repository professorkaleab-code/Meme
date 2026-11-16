"""Thin wrappers around free public APIs (no API key needed)."""
import time
import requests

DEX = "https://api.dexscreener.com"
RUGCHECK = "https://api.rugcheck.xyz/v1"
SOL_QUOTES = {
    "So11111111111111111111111111111111111111112",   # wrapped SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wNGEDNtTfY4bA",  # USDC
}

_session = requests.Session()
_session.headers["User-Agent"] = "memebot-paper/0.1"


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            r = _session.get(url, timeout=20)
            if r.status_code == 429:  # rate limited
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def discover_token_addresses():
    """Solana token addresses from DexScreener's latest profiles + boosted lists."""
    addrs = []
    for path in ("/token-profiles/latest/v1", "/token-boosts/latest/v1", "/token-boosts/top/v1"):
        try:
            for item in _get(DEX + path) or []:
                if item.get("chainId") == "solana" and item.get("tokenAddress"):
                    addrs.append(item["tokenAddress"])
        except Exception as e:
            print(f"  [warn] {path}: {e}")
    return list(dict.fromkeys(addrs))  # de-duplicate, keep order


def get_best_pairs(addresses):
    """Return {token_address: most-liquid SOL/USDC pair} for up to N tokens."""
    best = {}
    for i in range(0, len(addresses), 30):  # API accepts max 30 per call
        chunk = addresses[i:i + 30]
        try:
            pairs = _get(f"{DEX}/tokens/v1/solana/{','.join(chunk)}") or []
        except Exception as e:
            print(f"  [warn] price lookup failed: {e}")
            continue
        for p in pairs:
            base = p.get("baseToken", {}).get("address")
            if base not in chunk or p.get("quoteToken", {}).get("address") not in SOL_QUOTES:
                continue
            liq = (p.get("liquidity") or {}).get("usd") or 0
            if base not in best or liq > ((best[base].get("liquidity") or {}).get("usd") or 0):
                best[base] = p
    return best


_rug_cache = {}


def rugcheck_summary(mint):
    """RugCheck safety summary (cached for the session)."""
    if mint in _rug_cache:
        return _rug_cache[mint]
    try:
        data = _get(f"{RUGCHECK}/tokens/{mint}/report/summary")
    except Exception as e:
        data = {"error": str(e)}
    _rug_cache[mint] = data
    time.sleep(0.5)  # be polite
    return data
