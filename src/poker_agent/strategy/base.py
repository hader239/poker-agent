"""Abstract base class for poker strategy engines."""

from __future__ import annotations

from abc import ABC, abstractmethod

from poker_agent.models.actions import Action
from poker_agent.models.game_state import GameState
from poker_agent.models.hand_record import HandRecord


class Strategy(ABC):
    """Abstract base class for poker strategy engines.

    All strategy implementations must conform to this interface,
    enabling the strategy engine to be swapped (e.g., LLM -> GTO).
    """

    @abstractmethod
    async def decide(self, game_state: GameState) -> Action:
        """Given the current game state, return the action to take.

        The game state will have computed fields populated
        (hand_strength_rank, pot_odds, position, etc.)
        """
        ...

    async def on_hand_start(self, game_state: GameState) -> None:
        """Called when a new hand begins. Override for setup/context reset."""
        pass

    async def on_hand_end(self, hand_record: HandRecord) -> None:
        """Called when a hand ends. Override for learning/tracking."""
        pass

    async def on_street_change(self, game_state: GameState) -> None:
        """Called when the game phase changes (flop dealt, turn, river)."""
        pass
