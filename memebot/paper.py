"""Paper trading: simulated buys/sells with fake money, using real live prices."""
import csv
import json
import os
import time
from datetime import datetime, timezone

import config as C
from memebot import api, scanner

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE = os.path.join(DATA_DIR, "paper_state.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.csv")
TRADE_FIELDS = ["closed_at", "symbol", "address", "entry_price", "exit_price", "cost_usd",
                "proceeds_usd", "pnl_usd", "pnl_pct", "hold_hours", "reason", "entry_score",
                "max_gain_pct", "entry_liq", "entry_mcap", "entry_age_h", "entry_chg5m", "entry_chg1h",
                "entry_buy_sell", "entry_rug", "url"]
ENTRY_KEYS = {"entry_liq": "liquidity", "entry_mcap": "mcap", "entry_age_h": "age_h", "entry_chg5m": "chg5m",
              "entry_chg1h": "chg1h", "entry_rug": "rug_score"}


def now():
    return time.time()


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"cash": C.STARTING_BALANCE_USD, "positions": {}, "last_bought": {},
            "daily_pnl": {}, "started": now()}


def save_state(s):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, STATE_FILE)


def log_trade(row):
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        if header != TRADE_FIELDS:  # old v1 file: keep it, start a new one
            old = os.path.join(DATA_DIR, "trades_v1.csv")
            os.replace(TRADES_FILE, old if not os.path.exists(old) else TRADES_FILE + f".{int(now())}.old")
    new = not os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def buy(s, m):
    cost = C.TRADE_SIZE_USD
    fill = m["price"] * (1 + C.SLIPPAGE_PCT / 100)
    spend = cost * (1 - C.SWAP_FEE_PCT / 100) - C.NETWORK_FEE_USD
    qty = spend / fill
    s["cash"] -= cost
    s["positions"][m["address"]] = {
        "symbol": m["symbol"], "qty": qty, "entry_price": fill, "cost": cost,
        "peak_price": fill, "opened": now(), "score": m["score"], "url": m["url"],
        "entry": {k: m.get(v) for k, v in ENTRY_KEYS.items()},
    }
    s["positions"][m["address"]]["entry"]["entry_buy_sell"] = round(m.get("buys1h", 0) / max(m.get("sells1h", 0), 1), 2)
    s["last_bought"][m["address"]] = now()
    print(f"  BUY  {m['symbol']:<10} ${cost:.2f} @ {fill:.8g}  (score {m['score']})")


def sell(s, addr, price, reason):
    p = s["positions"].pop(addr)
    fill = price * (1 - C.SLIPPAGE_PCT / 100)
    proceeds = p["qty"] * fill * (1 - C.SWAP_FEE_PCT / 100) - C.NETWORK_FEE_USD
    proceeds = max(proceeds, 0.0)
    pnl = proceeds - p["cost"]
    s["cash"] += proceeds
    s["daily_pnl"][today()] = s["daily_pnl"].get(today(), 0.0) + pnl
    hold = (now() - p["opened"]) / 3600
    log_trade({
        "closed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbol": p["symbol"], "address": addr, "entry_price": f"{p['entry_price']:.10g}",
        "exit_price": f"{fill:.10g}", "cost_usd": f"{p['cost']:.2f}", "proceeds_usd": f"{proceeds:.2f}",
        "pnl_usd": f"{pnl:.2f}", "pnl_pct": f"{pnl / p['cost'] * 100:.1f}", "hold_hours": f"{hold:.2f}",
        "reason": reason, "entry_score": p["score"], "url": p["url"],
        "max_gain_pct": f"{(p['peak_price'] / p['entry_price'] - 1) * 100:.1f}",
        **{k: (f"{v:.2f}" if isinstance(v, float) else v) for k, v in (p.get("entry") or {}).items()},
    })
    print(f"  SELL {p['symbol']:<10} {reason:<14} P&L ${pnl:+.2f} ({pnl / p['cost'] * 100:+.1f}%)")


def check_exits(s):
    if not s["positions"]:
        return
    pairs = api.get_best_pairs(list(s["positions"].keys()))
    for addr, p in list(s["positions"].items()):
        pair = pairs.get(addr)
        if not pair:
            # Pool vanished = likely rug. Count it as a total loss after 10 min of no data.
            p.setdefault("missing_since", now())
            if now() - p["missing_since"] > 600:
                sell(s, addr, 0.0, "NO_PRICE/RUG")
            continue
        p.pop("missing_since", None)
        price = float(pair.get("priceUsd") or 0)
        p["peak_price"] = max(p["peak_price"], price)
        p["last_price"] = price
        change = (price / p["entry_price"] - 1) * 100
        from_peak = (price / p["peak_price"] - 1) * 100
        peak_gain = (p["peak_price"] / p["entry_price"] - 1) * 100
        hours = (now() - p["opened"]) / 3600
        if change >= C.TAKE_PROFIT_PCT:
            sell(s, addr, price, "TAKE_PROFIT")
        elif change <= -C.STOP_LOSS_PCT:
            sell(s, addr, price, "STOP_LOSS")
        elif peak_gain >= C.TRAILING_START_PCT and from_peak <= -C.TRAILING_STOP_PCT:
            sell(s, addr, price, "TRAILING_STOP")
        elif hours >= C.MAX_HOLD_HOURS:
            sell(s, addr, price, "TIME_LIMIT")


def can_open(s):
    if len(s["positions"]) >= C.MAX_OPEN_POSITIONS:
        return False, "max positions"
    if s["cash"] < C.TRADE_SIZE_USD:
        return False, "not enough cash"
    if s["daily_pnl"].get(today(), 0.0) <= -C.MAX_DAILY_LOSS_USD:
        return False, "daily loss limit hit"
    return True, ""


def check_entries(s):
    ok, why = can_open(s)
    if not ok:
        print(f"  (no new buys: {why})")
        return
    for m in scanner.scan():
        ok, _ = can_open(s)
        if not ok:
            break
        if m["address"] in s["positions"]:
            continue
        if now() - s["last_bought"].get(m["address"], 0) < C.REBUY_COOLDOWN_HOURS * 3600:
            continue
        buy(s, m)


def portfolio_value(s):
    """Estimated value if everything were sold now (includes selling costs)."""
    k = (1 - C.SLIPPAGE_PCT / 100) * (1 - C.SWAP_FEE_PCT / 100)
    return s["cash"] + sum(p["qty"] * p.get("last_price", p["entry_price"]) * k - C.NETWORK_FEE_USD
                           for p in s["positions"].values())


def run(once=False):
    s = load_state()
    print(f"Paper trading started. Cash ${s['cash']:.2f}, {len(s['positions'])} open positions.")
    print("Press Ctrl+C to stop (state is saved).\n")
    last_scan = 0.0
    try:
        while True:
            scan_now = once or now() - last_scan >= C.POLL_SECONDS
            try:
                check_exits(s)  # fast: only prices of coins we hold
                if scan_now:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] checking market...")
                    check_entries(s)
                    last_scan = now()
            except Exception as e:
                print(f"  [error] {e} - will retry next cycle")
            save_state(s)
            if scan_now:
                print(f"  Portfolio ~${portfolio_value(s):.2f} (cash ${s['cash']:.2f}, "
                      f"{len(s['positions'])} open, today P&L ${s['daily_pnl'].get(today(), 0):+.2f})")
            if once:
                break
            time.sleep(C.EXIT_CHECK_SECONDS)
    except KeyboardInterrupt:
        save_state(s)
        print("\nStopped. State saved.")


def report():
    s = load_state()
    print(f"Cash: ${s['cash']:.2f}   Est. portfolio: ${portfolio_value(s):.2f}   "
          f"(started with ${C.STARTING_BALANCE_USD:.2f})")
    if s["positions"]:
        print("\nOpen positions:")
        for p in s["positions"].values():
            last = p.get("last_price", p["entry_price"])
            print(f"  {p['symbol']:<10} entry {p['entry_price']:.8g}  last {last:.8g}  "
                  f"{(last / p['entry_price'] - 1) * 100:+.1f}%")
    if not os.path.exists(TRADES_FILE):
        print("\nNo closed trades yet.")
        return
    with open(TRADES_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("\nNo closed trades yet.")
        return
    pnls = [float(r["pnl_usd"]) for r in rows]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]
    print(f"\nClosed trades: {len(rows)}   Win rate: {len(wins) / len(rows) * 100:.0f}%")
    print(f"Total P&L: ${sum(pnls):+.2f}   Avg win: ${sum(wins) / max(len(wins), 1):+.2f}   "
          f"Avg loss: ${sum(losses) / max(len(losses), 1):+.2f}")
    print(f"Best: ${max(pnls):+.2f}   Worst: ${min(pnls):+.2f}")
    reasons = {}
    for r in rows:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    print("Exit reasons: " + ", ".join(f"{k} {v}" for k, v in reasons.items()))
    print("\nLast 10 trades:")
    for r in rows[-10:]:
        print(f"  {r['closed_at'][:16]} {r['symbol']:<10} {r['reason']:<14} ${float(r['pnl_usd']):+.2f} ({r['pnl_pct']}%)")
