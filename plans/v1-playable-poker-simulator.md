# Build a local 6-max NLHE simulator with strong heuristic bots

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

`PLANS.md` exists at the repository root and this document must be maintained in accordance with `/PLANS.md`.

## Purpose / Big Picture

After this change, a user can start a local poker session, sit in one fixed seat at a 6-max no-limit hold'em cash table, and play repeated hands against five bots in a browser. The backend owns all poker rules, side pots, rake, and bot decisions. The frontend remains thin: it renders the current table state, sends human actions, and optionally reveals all hole cards after a hand ends when the session toggle is enabled.

The observable outcome is a local app with a FastAPI backend and a React + Vite frontend. Starting a session shows stacks, blinds, the current board, the hero's cards, legal actions, and bot actions arriving over a WebSocket connection. The game continues hand after hand with dealer rotation and between-hand top-ups.

## Progress

- [x] (2026-03-25 14:45Z) Confirmed the product direction with the user: v1 is a play-only simulator with strong heuristic bots, a minimal web UI, and no learning or coaching.
- [x] (2026-03-25 15:05Z) Chose the implementation stack: Python + FastAPI backend, React + Vite frontend, and WebSockets for live table state delivery.
- [x] (2026-03-25 15:24Z) Created the repository skeleton for `backend/`, `frontend/`, and `plans/`.
- [x] (2026-03-25 15:41Z) Implemented the pure Python poker engine, hand evaluator, session controller, and heuristic bot policies.
- [x] (2026-03-25 15:48Z) Added the FastAPI app, session creation endpoint, health endpoint, and WebSocket action/state loop.
- [x] (2026-03-25 15:56Z) Added the React + Vite frontend for setup, table play, human actions, and reveal-after-hand flow.
- [x] (2026-03-25 16:02Z) Added engine and session tests and a simple benchmark helper for strong bots versus weak baselines.
- [x] (2026-03-25 16:16Z) Installed runtime dependencies, ran tests, built the frontend, started the FastAPI server, and created a real session through the API.
- [x] (2026-03-25 16:55Z) Completed a stabilization/debug pass: fixed backend packaging metadata, fixed missing WebSocket runtime support, added an extra engine regression test, and reran backend, packaging, server, proxy, and live WebSocket smoke checks.

## Surprises & Discoveries

- Observation: The current git worktree is not actually empty. The only tracked commit contains an older autonomous poker-agent codebase, but the whole working tree for that code is currently deleted.
  Evidence: `git status --short` showed deleted tracked files such as `src/poker_agent/agent.py`, `pyproject.toml`, and `README.md`.

- Observation: `fastapi`, `uvicorn`, and `pytest` are not installed in the current Python environment.
  Evidence: `python3 -c "import fastapi, uvicorn"` and `python3 -c "import pytest"` both failed with `ModuleNotFoundError`.

- Observation: `compileall` initially failed even though the code parsed correctly, because the sandboxed Python process tried to write bytecode caches into a protected macOS cache directory.
  Evidence: `python3 -m compileall backend/src/poker_sim` failed with `PermissionError` until `PYTHONPYCACHEPREFIX=/tmp/pycache` was used.

- Observation: Binding `uvicorn` to `127.0.0.1:8000` required elevated execution in this environment, and the non-elevated shell could not curl the elevated localhost process.
  Evidence: the first server start failed with `operation not permitted`; the later elevated start succeeded and `curl -s http://127.0.0.1:8000/api/health` returned `{"status":"ok"}` only when the curl ran with the same permission level.

- Observation: Installing the backend initially produced an `UNKNOWN-0.0.0` distribution with no importable `poker_sim` package.
  Evidence: `pip show UNKNOWN` reported the installed package metadata, and `python -c "import poker_sim"` failed until a `setup.py` was added and the package was reinstalled.

- Observation: The original runtime dependency set was enough for HTTP but not enough for WebSockets.
  Evidence: `uvicorn` logged `No supported WebSocket library detected` during the first live WebSocket smoke test until `uvicorn[standard]` and its websocket stack were installed.

## Decision Log

- Decision: Treat the deleted historical code as reference material only and implement the simulator additively in new `backend/` and `frontend/` directories instead of restoring the old application tree.
  Rationale: The worktree is dirty and the deleted files may reflect intentional user changes. Building additively avoids reverting or silently reviving code the user removed.
  Date/Author: 2026-03-25 / Codex

- Decision: Use WebSockets between the browser and FastAPI for table state updates and human actions.
  Rationale: Poker state evolves as a stream of events. The same stream-oriented boundary can later accept adapters that capture state from real apps.
  Date/Author: 2026-03-25 / Codex

- Decision: Keep the poker engine dependency-light and separate from FastAPI-specific concerns.
  Rationale: The core simulator must be testable with the Python standard library, independent of whether web dependencies are installed locally.
  Date/Author: 2026-03-25 / Codex

- Decision: Run the backend from `PYTHONPATH=backend/src` instead of requiring a full package install as part of initial validation.
  Rationale: This avoids blocking runtime verification on packaging quirks and keeps the focus on the simulator behavior itself.
  Date/Author: 2026-03-25 / Codex

- Decision: Add a compatibility `setup.py` and keep `uvicorn[standard]` in the backend dependency set.
  Rationale: The local toolchain did not package the project correctly from PEP 621 metadata alone, and the frontend requires actual WebSocket support rather than plain HTTP-only `uvicorn`.
  Date/Author: 2026-03-25 / Codex

## Outcomes & Retrospective

The feature is now implemented as a playable foundation: a pure Python hold'em engine, a FastAPI/WebSocket API, and a React + Vite client. The backend rules are testable without FastAPI, the frontend builds successfully, a fresh backend install works in a clean virtualenv, and the dev-server proxy path can create a session and play a hand over WebSockets. The remaining gap is still visual/manual browser QA, not core correctness or runtime wiring.

## Context and Orientation

The repository root currently contains `AGENTS.md` and `PLANS.md`, plus a historical tracked project whose files are deleted from the working tree. The new simulator will live under `backend/` and `frontend/`.

`backend/` will contain a Python package that owns the poker rules. The package will store chip values as integer hundredths of a big blind so the engine can represent `0.5bb` blinds and arbitrary no-limit bet sizes without floating-point drift. The engine will not depend on FastAPI. FastAPI will only appear at the API edge in `backend/src/poker_sim/app.py`.

`frontend/` will contain a minimal React + Vite app. The frontend must never compute legal actions or apply poker rules on its own. It only renders server snapshots and sends user intent back over the WebSocket.

The older `src/poker_agent/` tree from git history may still contain useful card-modeling ideas, but it must not be restored accidentally. Any reused logic should be copied intentionally into the new structure.

## Plan of Work

Start by creating backend models for cards, seats, game streets, actions, and hand results. Add a pure-Python hand evaluator that ranks seven-card holdings by checking all five-card combinations. Build the hand engine on top of those models, with explicit responsibilities for dealing, posting blinds, rotating action, validating legal moves, resolving betting rounds, and distributing side pots with rake.

Once the engine can run a complete hand locally, add the session controller that manages the fixed hero seat, bot seat initialization, between-hand top-ups, and next-hand rotation. Add two bot policies: a strong heuristic policy for production play and a weak baseline policy for benchmarks. The strong policy should combine seeded preflop ranges with postflop heuristics based on made hand strength, draw strength, pot odds, stack-to-pot ratio, and board texture.

After the engine works, wrap it in a FastAPI app with a session creation endpoint, a session state endpoint, and a WebSocket endpoint for live updates and human actions. The WebSocket should always send full table snapshots that are already sanitized for the hero's point of view.

Finally, build a small React interface that starts a session, connects to the WebSocket, renders the table state, shows legal action controls, and optionally reveals all cards after the hand. Validate the engine with `unittest`-based tests before attempting to install or run FastAPI and frontend dependencies.

## Concrete Steps

From `/Users/zero_skill/coding/poker-agent`:

1. Create the new directory layout and living documentation.
2. Implement the backend engine and run:

       python3 -m unittest discover -s backend/tests

   Observed result:

       ........
       ----------------------------------------------------------------------
       Ran 8 tests in 0.002s
       OK

3. Install backend dependencies and run the backend server:

       cd backend
       python3 -m venv .venv
       .venv/bin/pip install ./backend
       cd ..
       backend/.venv/bin/uvicorn poker_sim.app:app --host 127.0.0.1 --port 8000

   Observed result:

       INFO:     Uvicorn running on http://127.0.0.1:8000

4. Check the backend:

       curl -s http://127.0.0.1:8000/api/health
       curl -s -X POST -H 'Content-Type: application/json' \
         -d '{"hero_buyin_bb":50,"reveal_all_cards_after_hand":true}' \
         http://127.0.0.1:8000/api/session

   Observed result:

       {"status":"ok"}

       {"session_id":"...","snapshot":{"street":"preflop","actor_index":0,...}}

5. Install frontend dependencies and run the frontend:

       cd frontend
       npm install
       npm run dev

   Production build check:

       npm run build

   Observed result:

       vite v7.3.1 building client environment for production...
       ✓ built in 455ms

6. Open the local frontend URL printed by Vite, create a session, and play a hand against the bots.

   Proxy smoke check:

       curl -s http://127.0.0.1:5173/api/health
       # and a websocket session through ws://127.0.0.1:5173/ws/session/<id>

   Observed result:

       {"status":"ok"}

       final-smoke-ok

This section must be updated with real outputs once validation is complete.

## Validation and Acceptance

Acceptance is behavioral:

- Starting a session shows six occupied seats, the hero's cards, blinds posted, and a valid first actor.
- Human actions that violate min-raise or stack constraints are rejected by the backend.
- A forced all-in and multi-way showdown produces correct main-pot and side-pot distributions.
- A preflop fold-to-raise hand collects no rake; a flop-seen hand applies 5% rake capped at 8bb.
- After a hand ends, the dealer button advances one seat and stacks are topped up to the configured target before the next hand starts.
- The frontend never receives live hidden opponent cards during a hand.
- When reveal-all is enabled, the frontend receives all hole cards after the hand is complete.
- The strong bots beat a weak baseline over a benchmark sample measured in positive bb/100.

## Idempotence and Recovery

The new simulator lives in new directories and does not require restoring the deleted historical files. Re-running test commands is safe. If dependency installation fails because the environment lacks network access, continue validating the pure-Python engine locally and record the gap here instead of editing around the missing packages.

## Artifacts and Notes

Relevant verification snippets:

    backend benchmark over 30 hands against weak baseline:

        {'hands': 30.0, 'strong_pair_profit_bb': 167.07, 'bb_per_100': 556.9}

    random hero-action stress run over 60 hands:

        random-session-ok

    sample session snapshot after API creation:

        {
          "street": "preflop",
          "button_index": 0,
          "actor_index": 0,
          "legal_actions": {
            "can_fold": true,
            "can_check": false,
            "call_amount_bb": 2.35,
            "min_raise_to_bb": 3.7,
            "max_raise_to_bb": 50.0
          }
        }

    live websocket smoke checks:

        ws-flow-ok
        vite-ws-proxy-ok
        final-smoke-ok

## Interfaces and Dependencies

In `backend/src/poker_sim/engine.py`, define a `GameEngine` class with methods that cover session setup, hand start, legal-action lookup, action application, and hand resolution. The engine should operate on pure Python dataclasses and integers measured in hundredths of a big blind.

In `backend/src/poker_sim/bots.py`, define a `BotPolicy` protocol or base class plus `StrongHeuristicBot` and `RandomBot` implementations. The strong bot must return a validated `PlayerAction` using only the visible table state available to that seat.

In `backend/src/poker_sim/session.py`, define a `SessionController` that owns one `GameEngine`, one fixed hero seat, session config, reveal settings, and async hooks for broadcasting sanitized snapshots.

In `backend/src/poker_sim/app.py`, define the FastAPI app and WebSocket handlers that expose session creation and action submission.

In `frontend/src/App.jsx`, keep the page as a thin session shell that renders server-provided snapshots, forms for setup, action controls, and end-of-hand reveal data.

Revision note: created the initial implementation plan after confirming stack, transport, and simulator scope with the user. The plan intentionally avoids restoring the deleted historical tree and instead builds the simulator in new directories.
