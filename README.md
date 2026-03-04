# Poker Agent

Autonomous poker-playing agent for a No-Limit Hold'em Telegram mini-app.

## Setup

```bash
# Create virtual environment and install dependencies
uv venv --python 3.13
uv pip install -e ".[dev]"
```

## Configuration

```bash
cp .env.example .env
# Edit .env and set your POKER_ANTHROPIC_API_KEY
```

## Usage

```bash
# Run preflight checks
poker-agent preflight

# Take a test screenshot of the Telegram window
poker-agent screenshot

# Start the agent (dry run — no clicks)
poker-agent start --dry-run

# Start the agent for real
poker-agent start
```

## Architecture

```
capture → parse → decide → act → verify → repeat
```

- **Capture** — screenshots via `mss`
- **Parse** — Claude Vision API extracts game state
- **Decide** — LLM strategy engine (swappable to GTO)
- **Execute** — `pyautogui` mouse/keyboard control
- **Log** — JSONL hand history + session stats
