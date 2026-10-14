# Hyperliquid Copy Trading

A real-time copy trading system for [Hyperliquid](https://hyperliquid.xyz/) that mirrors the trades of target wallets and logs every executed trade to Notion. Pairs of wallets (for example a "long" pair and a "short" pair) are watched continuously, and when a target wallet trades, the same market order is placed from your own wallet. A Telegram bot lets you monitor balances and positions and switch copying on or off without touching the server.

Built with the Hyperliquid Python SDK and `websockets` for real-time updates.

## How it works

- **Wallet watching** — `wallet.py` wraps the Hyperliquid API: it reads a target wallet's positions, filled history, and historical orders, and places market orders (with configurable leverage and trade mode) from your wallet.
- **Copy engine** — `copyTrade.py` runs a `CopyTradingPair` for each configured pair (your wallet + a target wallet). Each pair runs its own async worker that detects changes in the target's positions and mirrors them.
- **Telegram control** — `bot.py` runs a Telegram bot (via `python-telegram-bot`) in a separate thread. Commands let you check your balance and positions, view the target's positions, change the target address, set the trade mode, and switch copying on or off per pair.
- **Trade logging** — `notion.py` logs each executed trade to a Notion database: coin, position direction, price, size, PnL, percentage PnL, fee, and timestamp.

## Project structure

| File | Purpose |
| --- | --- |
| `copyTrade.py` | Copy-trading engine: `CopyTradingPair` workers that mirror target wallets |
| `wallet.py` | `Wallet` / `My_Wallet` classes over the Hyperliquid API (positions, history, market orders, leverage) |
| `bot.py` | Telegram bot for monitoring and controlling the pairs |
| `notion.py` | Logs executed trades to Notion databases |
| `utils.py` | Loads `config.yaml` |
| `healthcheck.py` | Container health check |
| `config.yaml` | Pair configuration: your wallet and target wallet per pair, Notion database IDs |
| `Dockerfile`, `compose.yaml` | Container build and deployment (Python 3.11) |

## Setup

1. Clone the repository and install dependencies:

   ```bash
   git clone https://github.com/ivjiyeon/HyperliquidCopyTrading.git
   cd HyperliquidCopyTrading
   pip install -r requirements.txt
   ```

2. Configure your pairs in `config.yaml` — for each pair, set your wallet address and the target wallet address to mirror, plus the Notion database ID used for trade logs. Provide your Telegram bot token and other secrets through a `.env` file (see `compose.yaml`).

   > **Never commit real private keys.** The `private` field in `config.yaml` and your `.env` file must stay out of version control — use placeholder values in anything you push publicly, and rotate any key that has ever been committed.

3. Run it:

   ```bash
   python copyTrade.py
   ```

   Or with Docker:

   ```bash
   docker compose up --build
   ```

## Notes

- Copying a trader's positions carries the same risks as the original trades, plus execution lag. Start with small sizes and a trade mode you understand before letting it run unattended.
- This project is for personal/educational use and is not financial advice.
