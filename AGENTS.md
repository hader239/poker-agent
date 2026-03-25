# AGENTS.md

## Project Structure

For large projects, each major directory should contain its own `AGENTS.md`. These per-section files must capture non-obvious context: architectural constraints, implicit conventions, edge cases, gotchas, and how the section integrates with the rest of the system. Do not restate what the code already says. Focus on what a newcomer would get wrong or waste time on without the file.

The current simulator implementation lives under `backend/` and `frontend/`. The backend owns all poker rules and session state; the frontend is a thin WebSocket client. There is also an older tracked `src/poker_agent/` tree in git history that is currently deleted from the working tree. Treat that historical tree as reference material only unless the user explicitly asks to restore or reuse it directly.

# ExecPlans

When writing complex features or significant refactors, use an ExecPlan (as described in .agent/PLANS.md) from design to implementation.

## Planning and Ambiguity

Before implementing any feature or change, identify every design question that has more than one reasonable answer. These questions **must** be surfaced to the user/parent agent before writing any implementation code. Do not pick a default and proceed silently. Examples: choice of data structure, public API shape, error handling strategy, naming conventions, module boundaries, or trade-offs between simplicity and extensibility. If in doubt whether a decision is ambiguous, ask.

## Maintaining This File

This file is a living document. When you discover a pattern, convention, or gotcha that would save a future agent (or yourself) from repeating a mistake or making a wrong assumption, update the relevant section here — or add a new one. The same applies to per-directory `AGENTS.md` files. Keep edits tight: add what's missing, remove what's stale, never pad.
