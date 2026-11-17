"""Replay a strategy over historical candles with fees, slippage, funding and stop-losses."""
import config as C
from cryptobot import data
from cryptobot.strategies import STRATEGIES, WARMUP, atr

COST = (C.TAKER_FEE_PCT + C.SLIPPAGE_PCT) / 100  # per side, fraction of notional


def size_position(equity, price, stop_dist):
    """Risk RISK_PER_TRADE_PCT of equity if the stop is hit, capped by MAX_LEVERAGE."""
    qty = equity * C.RISK_PER_TRADE_PCT / 100 / stop_dist
    return min(qty, equity * C.MAX_LEVERAGE / price)


def run(rows, strategy, tf):
    want = STRATEGIES[strategy](rows)
    atrs = atr(rows)
    bar_h = data.TF_SECONDS[tf] / 3600
    equity = peak = C.STARTING_BALANCE_USD
    max_dd = 0.0
    pos = None          # dict(dir, entry, qty, stop)
    blocked = 0         # after a stop-out, don't re-enter that side until the signal resets
    trades = []

    def close(price, i, why):
        nonlocal equity, pos
        pnl = pos["dir"] * pos["qty"] * (price - pos["entry"]) - pos["qty"] * price * COST
        equity += pnl
        trades.append({"net": pnl - pos["fee"], "why": why, "bars": i - pos["i"]})
        pos = None

    for i in range(WARMUP, len(rows) - 1):
        t, o, h, l, c, _ = rows[i]
        if pos:
            # 1) stop-loss hit during this candle? (gap through the stop fills at the open)
            d = pos["dir"]
            if (d == 1 and l <= pos["stop"]) or (d == -1 and h >= pos["stop"]):
                fill = min(o, pos["stop"]) if d == 1 else max(o, pos["stop"])
                close(fill, i, "STOP")
                blocked = d
            else:
                if d == 1:  # 2) funding cost for longs
                    equity -= pos["qty"] * c * C.FUNDING_PCT_PER_8H / 100 * bar_h / 8
                # 3) trail the stop in the profitable direction only
                new = c - d * C.ATR_STOP_MULT * atrs[i]
                pos["stop"] = max(pos["stop"], new) if d == 1 else min(pos["stop"], new)
        if want[i] != blocked:
            blocked = 0
        nxt_open = rows[i + 1][1]
        target = want[i] if (want[i] != -1 or C.ALLOW_SHORTS) else 0
        if pos and target != pos["dir"]:
            close(nxt_open, i, "SIGNAL")
        if not pos and target != 0 and target != blocked and equity > 0:
            stop_dist = C.ATR_STOP_MULT * atrs[i]
            qty = size_position(equity, nxt_open, stop_dist)
            fee = qty * nxt_open * COST
            equity -= fee
            pos = {"dir": target, "entry": nxt_open, "qty": qty, "i": i, "fee": fee,
                   "stop": nxt_open - target * stop_dist}
        mark = equity + (pos["dir"] * pos["qty"] * (c - pos["entry"]) if pos else 0)
        peak = max(peak, mark)
        max_dd = max(max_dd, (peak - mark) / peak * 100)
    if pos:
        close(rows[-1][4], len(rows) - 1, "END")

    wins = [x["net"] for x in trades if x["net"] > 0]
    losses = [x["net"] for x in trades if x["net"] <= 0]
    start_px, end_px = rows[WARMUP][4], rows[-1][4]
    return {
        "return_pct": (equity / C.STARTING_BALANCE_USD - 1) * 100,
        "buy_hold_pct": (end_px / start_px - 1) * 100,
        "max_dd_pct": max_dd,
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses and sum(losses) else float("inf") if wins else 0,
        "days": (rows[-1][0] - rows[WARMUP][0]) / 86400,
    }


def fmt(r):
    pf = "inf" if r["profit_factor"] == float("inf") else f"{r['profit_factor']:.2f}"
    return (f"{r['return_pct']:>+8.1f}% {r['buy_hold_pct']:>+8.1f}% {r['max_dd_pct']:>6.1f}% "
            f"{r['trades']:>6} {r['win_rate']:>5.0f}% {pf:>6}")


def main(strategies=None, symbols=None, tf=None):
    tf = tf or C.TIMEFRAME
    strategies = strategies or list(STRATEGIES)
    symbols = symbols or C.SYMBOLS
    print(f"Backtest on {tf} candles. Costs: fee {C.TAKER_FEE_PCT}% + slippage {C.SLIPPAGE_PCT}% per side, "
          f"funding {C.FUNDING_PCT_PER_8H}%/8h on longs.")
    print(f"Risk {C.RISK_PER_TRADE_PCT}% per trade, max leverage {C.MAX_LEVERAGE}x, stop {C.ATR_STOP_MULT}x ATR.\n")
    hist = {}
    for sym in symbols:
        src, rows = data.load_history(sym, tf, C.HISTORY_DAYS)
        hist[sym] = rows
        print(f"  {sym}: {len(rows)} candles ({len(rows) * data.TF_SECONDS[tf] / 86400:.0f} days) from {src}")
    head = f"{'STRATEGY':<10} {'COIN':<4} {'PERIOD':<9} {'RETURN':>9} {'BUY&HOLD':>9} {'MAX DD':>7} {'TRADES':>6} {'WIN%':>6} {'PF':>6}"
    print("\n" + head + "\n" + "-" * len(head))
    summary = {}
    for st in strategies:
        for sym in symbols:
            rows = hist[sym]
            split = int(len(rows) * (1 - C.OUT_OF_SAMPLE_PCT / 100))
            parts = [("ALL", rows), ("first70%", rows[:split]), ("last30%", rows[max(split - WARMUP, 0):])]
            for name, part in parts:
                if len(part) < WARMUP + 50:
                    continue
                r = run(part, st, tf)
                print(f"{st:<10} {sym:<4} {name:<9} {fmt(r)}")
                if name == "last30%":
                    summary.setdefault(st, []).append(r["return_pct"])
        print()
    print("Unseen-data (last 30%) average return per strategy:")
    for st, v in sorted(summary.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {st:<10} {sum(v) / len(v):+.1f}%  {'<- current STRATEGY in config.py' if st == C.STRATEGY else ''}")
    print("\nRETURN = account growth. MAX DD = worst drop from a peak. PF = profit factor (>1.3 is decent).")
    print("Trust a strategy only if it is profitable in BOTH periods and on most coins.")
