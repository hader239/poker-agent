# Frontend AGENTS

## Role

The frontend is a thin player surface over the backend simulator. It renders snapshots from the server, sends human actions, and displays hand results. It must not derive legal poker behavior independently.

## Source of Truth

The WebSocket session stream is the source of truth for live table state. Do not cache or mutate poker state optimistically in ways that can diverge from the backend.

## Visibility Rules

Opponent hole cards are hidden during a hand. If reveal-all is enabled, only render those cards after the backend marks the hand complete. Do not infer or preview private information client-side.
