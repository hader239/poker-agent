# Poker Simulator

Local 6-max no-limit hold'em simulator with a Python/FastAPI backend and a React/Vite frontend.

The current project goal is simple: let you sit in one seat and play repeated cash-game hands against five bots that are reasonably strong and strategically coherent. The code is also structured so this simulator can later evolve into a decision engine fed by captured game state from real poker apps.

## What Works Today

- 6-max no-limit hold'em cash only.
- One human player in a fixed seat.
- Five heuristic bots with small style differences built on the same core policy.
- Full hand flow: blinds, dealing, preflop, flop, turn, river, showdown.
- All-in handling, side pots, split pots, and rake.
- Cash-game top-ups between hands.
- Minimal local web UI for playing hands.
- WebSocket session updates from backend to frontend.
- Optional reveal-all-cards view after each hand for debugging.

## Current Rules and Defaults

- Game type: 6-max no-limit hold'em cash.
- Hero buy-in: 10bb to 100bb.
- Bot buy-in: always 100bb.
- Small blind: `0.5bb`.
- Big blind: `1bb`.
- Rake: `5%`, capped at `8bb`.
- Rake policy: no flop, no drop.
- Sessions are in memory only.
- No persistence, accounts, match history database, or external table capture yet.

## What This Is Not Yet

- Not a solver or GTO engine.
- Not a coaching tool.
- Not connected to real poker clients.
- Not a mobile app.
- Not a tournament engine.
- Not a multi-table system.

## Architecture

The active implementation lives in `backend/` and `frontend/`.

- `backend/` contains the pure poker engine, bot policies, session controller, and FastAPI app.
- `frontend/` contains the React + Vite browser client.
- `plans/` contains the living ExecPlan for this feature.

The backend owns all poker rules. The frontend is intentionally thin: it renders snapshots, sends actions, and does not compute legal poker behavior on its own.

Internally, the engine stores chips as integer hundredths of a big blind. That keeps calculations stable while still supporting the fixed `0.5bb` small blind and arbitrary no-limit bet sizes. The UI and API expose amounts in `bb`.

This split is intentional for the future pivot: today the frontend consumes simulator state over WebSockets, but later a capture layer could feed the same backend/session boundary from a real poker app.

## Repository Layout

- `backend/src/poker_sim/cards.py`: card model, hand ranking, simple equity helpers.
- `backend/src/poker_sim/engine.py`: the core game engine and state transitions.
- `backend/src/poker_sim/bots.py`: strong heuristic bot policy and weak baseline bot.
- `backend/src/poker_sim/session.py`: session orchestration and bot-driving loop.
- `backend/src/poker_sim/app.py`: FastAPI HTTP + WebSocket API.
- `backend/tests/`: engine, session, and bot regression tests.
- `frontend/src/App.jsx`: main playable UI shell.
- `frontend/src/styles.css`: table layout and styling.

If your git status still shows an older deleted `src/poker_agent/` tree, treat that as historical residue. The active app is the `backend/` + `frontend/` split above.

## Prerequisites

- Python `3.9+`
- Node.js and npm

The project has been verified with Python `3.9.6`, Node `v24.10.0`, and npm `11.6.0`.

## Quick Start

From the repository root:

### 1. Install backend dependencies

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install ./backend
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Run the backend

```bash
backend/.venv/bin/uvicorn poker_sim.app:app --host 127.0.0.1 --port 8000
```

### 4. Run the frontend

In a second terminal:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### 5. Open the app

Open `http://127.0.0.1:5173` in your browser.

## How To Use It

1. Choose your starting stack between `10bb` and `100bb`.
2. Optionally enable reveal-all-cards after each hand.
3. Click `Create Table`.
4. Play the current hand using the action panel on the right.
5. When a hand ends, review the summary and click `Next Hand`.

During a hand:

- You only see your own hole cards and public board cards.
- Opponent hole cards stay hidden.
- The backend sends live state changes over WebSockets as bots act.

After a hand:

- The result summary is shown.
- Rake is shown.
- If reveal mode was enabled, all hole cards are displayed.

## Development Commands

### Backend tests

```bash
python3 -m unittest discover -s backend/tests
```

### Frontend production build

```bash
cd frontend
npm run build
```

### Backend health check

```bash
curl -s http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

## API Overview

### `GET /api/health`

Returns a simple health response.

### `POST /api/session`

Creates a new in-memory session.

Request body:

```json
{
  "hero_buyin_bb": 50,
  "reveal_all_cards_after_hand": true
}
```

Response:

- `session_id`
- initial hero-facing snapshot

### `GET /api/session/{session_id}`

Returns the current hero-facing snapshot for an existing session.

### `WS /ws/session/{session_id}`

WebSocket stream for live state updates and user actions.

Client messages:

```json
{"type":"action","action":"fold"}
```

```json
{"type":"action","action":"call"}
```

```json
{"type":"action","action":"bet","amount_bb":4.5}
```

```json
{"type":"action","action":"raise_to","amount_bb":12}
```

```json
{"type":"action","action":"all_in"}
```

```json
{"type":"next_hand"}
```

Server messages:

```json
{"type":"state","payload":{...}}
```

```json
{"type":"error","message":"..."}
```

## Bot Model

The bots are intentionally heuristic rather than solver-driven.

Preflop:

- seeded opening and response ranges by position,
- stack-aware adjustments,
- sensible open, 3-bet, and jam behavior.

Postflop:

- simple equity estimation,
- made-hand and draw evaluation,
- board texture heuristics,
- pot-odds and pressure logic,
- formula-driven sizing rather than fixed buckets.

The bots are meant to be disciplined and playable, not theoretically perfect.

## Notes For Future Work

The most important design choice to preserve is the clean boundary between:

- state generation,
- decision logic,
- transport,
- and UI.

If you later build a capture system for real poker apps, it should feed structured table state into the same backend/session layer instead of bypassing the engine directly.

## Troubleshooting

If the backend starts but WebSocket sessions fail, reinstall the backend dependencies with:

```bash
backend/.venv/bin/pip install --force-reinstall ./backend
```

The backend depends on `uvicorn[standard]`, not bare `uvicorn`, because the simulator needs actual WebSocket support.

If you want a fresh packaging check, this should work:

```bash
python3 -m venv /tmp/poker-sim-check-venv
/tmp/poker-sim-check-venv/bin/pip install ./backend
/tmp/poker-sim-check-venv/bin/python -c "import poker_sim; print(poker_sim.__file__)"
```
