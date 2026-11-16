"""
Solana meme coin scanner + paper trader.  NO REAL MONEY IS USED.

Usage:
    python main.py scan            # show coins that pass the filters right now
    python main.py scan -v         # also show why each coin was rejected
    python main.py paper           # run the paper trader (Ctrl+C to stop)
    python main.py paper --once    # run one cycle and exit
    python main.py report          # show paper trading results
    python main.py reset           # wipe paper account and start over
"""
import argparse
import os
import sys

from memebot import paper, scanner


def main():
    ap = argparse.ArgumentParser(description="Solana meme coin scanner + paper trader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("-v", "--verbose", action="store_true")
    p = sub.add_parser("paper"); p.add_argument("--once", action="store_true")
    sub.add_parser("report")
    sub.add_parser("reset")
    a = ap.parse_args()

    if a.cmd == "scan":
        scanner.print_candidates(scanner.scan(verbose=a.verbose))
    elif a.cmd == "paper":
        paper.run(once=a.once)
    elif a.cmd == "report":
        paper.report()
    elif a.cmd == "reset":
        if input("Delete paper account and trade history? (yes/no): ").strip().lower() == "yes":
            for f in (paper.STATE_FILE, paper.TRADES_FILE):
                if os.path.exists(f):
                    os.remove(f)
            print("Reset done.")


if __name__ == "__main__":
    sys.exit(main())
