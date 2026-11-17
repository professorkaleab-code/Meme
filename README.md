# Meme — Solana meme coin scanner + paper trader

> **Paper trading only. No wallet, no private key, no real money.**
> Run this for at least 1–2 weeks. Only consider live trading if results are clearly positive.
> Most meme coins go to zero. Nothing here is financial advice.

## What it does
1. **Scan** – pulls new / trending Solana tokens from DexScreener (free, no API key).
2. **Filter** – rejects coins with thin liquidity, low volume, tiny or huge market cap, brand-new launches,
   more sellers than buyers, coins already pumped too hard or crashing.
3. **Safety check** – RugCheck: rejects high risk scores, unlocked liquidity, and any "danger" flags
   (mint authority, freeze authority, etc.).
4. **Rank** – a simple momentum score (buy pressure, volume vs. liquidity, trend).
5. **Paper trade** – "buys" **$20** of the top coins with fake money using real live prices,
   including slippage + fees, then sells on take-profit / stop-loss / trailing stop / time limit.
6. **Report** – win rate, total P&L, exit reasons.

## Setup on Windows 10
1. Install **Python 3.10+** from <https://www.python.org/downloads/> — tick **"Add Python to PATH"** during install.
2. Install **Git** from <https://git-scm.com/download/win>.
3. Open **Command Prompt** (Win key → type `cmd`) and run:
   ```bat
   git clone https://github.com/professorkaleab-code/Meme.git
   cd Meme
   git checkout claude/focused-cray-ighkt9
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Usage
Each time you open a new Command Prompt: `cd Meme` then `venv\Scripts\activate`.

| Command | What it does |
|---|---|
| `python main.py scan` | Show coins passing all filters right now |
| `python main.py scan -v` | Also show why every other coin was rejected |
| `python main.py paper` | Run the paper trader (checks every 60s). **Ctrl+C** to stop — progress is saved |
| `python main.py report` | Show results |
| `python main.py reset` | Wipe paper account and start over |

Leave `python main.py paper` running (keep the window open, stop your PC from sleeping) for days to collect results.
Trades are saved in `data\trades.csv` — open it in Excel, or share it with Claude to analyze and tune the strategy.

## Settings
Everything is in **`config.py`**: trade size ($20), starting balance ($100), max 3 open positions,
$40 daily loss limit, +50% take profit, −25% stop loss, trailing stop, 6h max hold, and all filter thresholds.

## Results log
- **v1 (first day):** 30 trades, 37% win rate, **−$51.88 (−52%)**. Losses were bigger than wins, stop-losses
  filled at −27% to −35% (and one −97%) because prices were only checked every 60s, and many buys chased coins that had already pumped.
- **v2:** checks held coins every 15s, stricter entry filters (no chasing pumps, more liquidity, older coins,
  stronger buy pressure), tighter stop-loss / take-profit, and logs entry details per trade for analysis.

## Roadmap
- [x] Stage A – scanner + safety checks
- [x] Stage B – paper trading + reports
- [ ] Stage C – live trading via Jupiter (only after paper results are positive; separate wallet, small funds, hard limits)
