"""GTO solver-based strategy engine (stub for future implementation)."""

from __future__ import annotations

from poker_agent.models.actions import Action, ActionType
from poker_agent.models.game_state import GameState
from poker_agent.strategy.base import Strategy


class GTOStrategy(Strategy):
    """GTO solver-based decision engine.

    This is a stub — to be implemented with a GTO solver integration.
    For now it raises NotImplementedError.
    """

    async def decide(self, game_state: GameState) -> Action:
        raise NotImplementedError(
            "GTO strategy is not yet implemented. Use 'llm' strategy_type instead."
        )
