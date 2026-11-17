"""
BTC / ETH / SOL futures bot - backtest + paper trading. NO REAL MONEY IS USED.

Usage:
    python main.py backtest        # test all strategies on ~3 years of history
    python main.py paper           # paper trade live with the STRATEGY in config.py (Ctrl+C to stop)
    python main.py paper --once    # run one check and exit
    python main.py report          # show paper trading results
    python main.py reset           # wipe the paper account
"""
import argparse
import os

from cryptobot import backtest, paper


def main():
    ap = argparse.ArgumentParser(description="BTC/ETH/SOL futures backtest + paper trader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backtest")
    b.add_argument("--tf", choices=["1h", "4h"], help="candle size (default from config.py)")
    p = sub.add_parser("paper"); p.add_argument("--once", action="store_true")
    sub.add_parser("report"); sub.add_parser("reset")
    a = ap.parse_args()
    if a.cmd == "backtest":
        backtest.main(tf=a.tf)
    elif a.cmd == "paper":
        paper.run(once=a.once)
    elif a.cmd == "report":
        paper.report()
    elif a.cmd == "reset":
        if input("Delete the paper futures account and trade history? (yes/no): ").strip().lower() == "yes":
            for f in (paper.STATE_FILE, paper.TRADES_FILE):
                if os.path.exists(f):
                    os.remove(f)
            print("Reset done.")


if __name__ == "__main__":
    main()
