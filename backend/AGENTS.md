# Backend AGENTS

## Architecture

The backend owns every poker rule. The React app must never compute legal actions, betting-round transitions, side pots, or rake locally. If a UI feature seems to need derived poker state, add that derivation to the backend snapshot instead of duplicating logic in the browser.

## Numeric Model

Store chip amounts as integer hundredths of a big blind. This avoids float drift while still allowing the fixed `0.5bb` small blind and arbitrary no-limit bet sizes from the human player.

## Dependency Boundary

Keep the engine and bot logic free of FastAPI-specific code. The pure simulator should remain runnable and testable with the Python standard library even if the local environment has not installed web dependencies yet.

When validating the live API, install `uvicorn[standard]` rather than bare `uvicorn`. The simulator relies on WebSockets, and a plain `uvicorn` install can start the HTTP server while still failing all WebSocket upgrades.

The backend keeps both `pyproject.toml` and a small `setup.py`. That is intentional: the local environment uses an older pip/setuptools path where relying on PEP 621 metadata alone produced an `UNKNOWN-0.0.0` install with no importable package.

## Bot Policy

The strong bot is allowed to be heuristic, but it should still be disciplined. Avoid hidden special cases in the frontend or API layer. If a behavior change affects bot style, make it explicit in the policy inputs or configuration rather than burying it in engine control flow.
