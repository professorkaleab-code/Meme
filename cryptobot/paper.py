"""Paper futures trading on live prices. Same rules as the backtest. NO REAL MONEY."""
import csv
import json
import os
import time
from datetime import datetime, timezone

import config as C
from cryptobot import data
from cryptobot.backtest import COST, size_position
from cryptobot.strategies import STRATEGIES, WARMUP, atr

STATE_FILE = os.path.join(data.DATA_DIR, "futures_state.json")
TRADES_FILE = os.path.join(data.DATA_DIR, "futures_trades.csv")
FIELDS = ["closed_at", "symbol", "side", "entry_price", "exit_price", "qty", "notional_usd",
          "pnl_usd", "pnl_pct_of_account", "hold_hours", "reason", "strategy"]
NAME = {1: "LONG", -1: "SHORT"}


def now():
    return time.time()


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"balance": C.STARTING_BALANCE_USD, "positions": {}, "blocked": {}, "last_bar": {},
            "day_start_equity": {}, "funding_paid": 0.0, "started": now()}


def save_state(s):
    os.makedirs(data.DATA_DIR, exist_ok=True)
    with open(STATE_FILE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(STATE_FILE + ".tmp", STATE_FILE)


def equity(s, prices):
    return s["balance"] + sum(p["dir"] * p["qty"] * (prices.get(sym, p["entry"]) - p["entry"])
                              for sym, p in s["positions"].items())


def open_pos(s, sym, d, price, stop_dist, eq):
    qty = size_position(eq, price, stop_dist)
    fee = qty * price * COST
    s["balance"] -= fee
    s["positions"][sym] = {"dir": d, "entry": price, "qty": qty, "stop": price - d * stop_dist,
                           "opened": now(), "fee": fee, "last_funding": now()}
    print(f"  OPEN  {NAME[d]:<5} {sym} {qty:.6g} @ {price:,.2f}  (${qty * price:,.2f} position, "
          f"stop {price - d * stop_dist:,.2f})")


def close_pos(s, sym, price, reason):
    p = s["positions"].pop(sym)
    pnl = p["dir"] * p["qty"] * (price - p["entry"]) - p["qty"] * price * COST
    s["balance"] += pnl
    net = pnl - p["fee"]
    start_eq = s["day_start_equity"].get(today(), C.STARTING_BALANCE_USD)
    os.makedirs(data.DATA_DIR, exist_ok=True)
    new = not os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"closed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "symbol": sym,
                    "side": NAME[p["dir"]], "entry_price": f"{p['entry']:.4f}", "exit_price": f"{price:.4f}",
                    "qty": f"{p['qty']:.6g}", "notional_usd": f"{p['qty'] * p['entry']:.2f}",
                    "pnl_usd": f"{net:.2f}", "pnl_pct_of_account": f"{net / start_eq * 100:.2f}",
                    "hold_hours": f"{(now() - p['opened']) / 3600:.1f}", "reason": reason,
                    "strategy": C.STRATEGY})
    print(f"  CLOSE {NAME[p['dir']]:<5} {sym} @ {price:,.2f}  {reason:<7} P&L ${net:+.2f}")
    return p["dir"]


def step(s):
    tf = C.TIMEFRAME
    prices, rows_by = {}, {}
    for sym in C.SYMBOLS:
        try:
            _, rows = data.fetch(sym, tf, days=max(60, WARMUP * data.TF_SECONDS[tf] // 86400 + 15))
        except Exception as e:
            print(f"  [warn] {sym}: {e}")
            continue
        prices[sym] = rows[-1][4]          # live price = close of the candle still forming
        rows_by[sym] = data.closed_only(rows, tf)
    eq = equity(s, prices)
    s["day_start_equity"].setdefault(today(), eq)
    day_loss_pct = (s["day_start_equity"][today()] - eq) / s["day_start_equity"][today()] * 100

    for sym, rows in rows_by.items():
        price = prices[sym]
        p = s["positions"].get(sym)
        # 1) stop-loss check on live price
        if p and ((p["dir"] == 1 and price <= p["stop"]) or (p["dir"] == -1 and price >= p["stop"])):
            s["blocked"][sym] = close_pos(s, sym, price, "STOP")
            p = None
        # 2) funding for longs
        if p and p["dir"] == 1:
            hrs = (now() - p["last_funding"]) / 3600
            cost = p["qty"] * price * C.FUNDING_PCT_PER_8H / 100 * hrs / 8
            s["balance"] -= cost
            s["funding_paid"] += cost
            p["last_funding"] = now()
        # 3) act only when a new candle has closed (same as the backtest)
        if len(rows) < WARMUP or rows[-1][0] == s["last_bar"].get(sym):
            continue
        s["last_bar"][sym] = rows[-1][0]
        want = STRATEGIES[C.STRATEGY](rows)[-1]
        a = atr(rows)[-1]
        if want == -1 and not C.ALLOW_SHORTS:
            want = 0
        if p:  # trail stop
            new = rows[-1][4] - p["dir"] * C.ATR_STOP_MULT * a
            p["stop"] = max(p["stop"], new) if p["dir"] == 1 else min(p["stop"], new)
        if want != s["blocked"].get(sym, 0):
            s["blocked"][sym] = 0
        print(f"  {sym}: new {tf} candle closed @ {rows[-1][4]:,.2f} -> strategy wants "
              f"{NAME.get(want, 'FLAT')}")
        if p and want != p["dir"]:
            close_pos(s, sym, price, "SIGNAL")
            p = None
        if not p and want != 0 and want != s["blocked"].get(sym, 0):
            if day_loss_pct >= C.MAX_DAILY_LOSS_PCT:
                print(f"  (skip {sym}: daily loss limit {C.MAX_DAILY_LOSS_PCT}% reached)")
            else:
                open_pos(s, sym, want, price, C.ATR_STOP_MULT * a, equity(s, prices))
    return prices


def status_line(s, prices):
    parts = []
    for sym, p in s["positions"].items():
        pr = prices.get(sym, p["entry"])
        parts.append(f"{NAME[p['dir']]} {sym} {p['dir'] * (pr / p['entry'] - 1) * 100:+.2f}%")
    return (f"  Equity ${equity(s, prices):.2f} (balance ${s['balance']:.2f}) | "
            + (", ".join(parts) if parts else "no open positions"))


def run(once=False):
    s = load_state()
    print(f"Paper FUTURES trading: {', '.join(C.SYMBOLS)} | strategy '{C.STRATEGY}' on {C.TIMEFRAME} candles | "
          f"risk {C.RISK_PER_TRADE_PCT}%/trade, max {C.MAX_LEVERAGE}x")
    print("Trades happen only when a candle closes (every 4h for '4h'), so it can be quiet for hours.")
    print("Press Ctrl+C to stop (state is saved).\n")
    last_print = 0
    try:
        while True:
            try:
                prices = step(s)
                save_state(s)
                if once or now() - last_print > 900:  # status every 15 min
                    print(f"[{datetime.now().strftime('%H:%M')}]" + status_line(s, prices))
                    last_print = now()
            except Exception as e:
                print(f"  [error] {e} - retrying next cycle")
            if once:
                break
            time.sleep(C.CHECK_SECONDS)
    except KeyboardInterrupt:
        save_state(s)
        print("\nStopped. State saved.")


def report():
    s = load_state()
    print(f"Balance: ${s['balance']:.2f} (started ${C.STARTING_BALANCE_USD:.2f}), funding paid ${s['funding_paid']:.2f}")
    for sym, p in s["positions"].items():
        print(f"  open: {NAME[p['dir']]} {sym} {p['qty']:.6g} @ {p['entry']:,.2f}, stop {p['stop']:,.2f}")
    if not os.path.exists(TRADES_FILE):
        print("No closed trades yet.")
        return
    with open(TRADES_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pnls = [float(r["pnl_usd"]) for r in rows]
    wins, losses = [x for x in pnls if x > 0], [x for x in pnls if x <= 0]
    print(f"\nClosed trades: {len(rows)}  Win rate: {len(wins) / len(rows) * 100:.0f}%  Total P&L: ${sum(pnls):+.2f}")
    print(f"Avg win ${sum(wins) / max(len(wins), 1):+.2f}  Avg loss ${sum(losses) / max(len(losses), 1):+.2f}  "
          f"Profit factor {sum(wins) / abs(sum(losses)) if sum(losses) else float('inf'):.2f}")
    print("\nLast 10 trades:")
    for r in rows[-10:]:
        print(f"  {r['closed_at'][:16]} {r['side']:<5} {r['symbol']:<4} {r['reason']:<7} ${float(r['pnl_usd']):+.2f}")
