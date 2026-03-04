"""Poker math utilities using the treys library."""

from __future__ import annotations

from typing import Optional

from treys import Card as TreysCard
from treys import Evaluator

from poker_agent.models.game_state import Card, GamePhase, GameState, Position

import structlog

logger = structlog.get_logger()

_evaluator = Evaluator()

# Maps number of active players + seat offset from dealer to Position
_POSITION_MAP_6MAX = {
    0: Position.BUTTON,
    1: Position.SMALL_BLIND,
    2: Position.BIG_BLIND,
    3: Position.UNDER_THE_GUN,
    4: Position.MIDDLE,
    5: Position.CUTOFF,
}

_POSITION_MAP_9MAX = {
    0: Position.BUTTON,
    1: Position.SMALL_BLIND,
    2: Position.BIG_BLIND,
    3: Position.UNDER_THE_GUN,
    4: Position.UTG_PLUS_1,
    5: Position.MIDDLE,
    6: Position.MIDDLE,
    7: Position.CUTOFF,
    8: Position.CUTOFF,
}


def card_to_treys(card: Card) -> int:
    """Convert our Card model to a treys integer representation."""
    return TreysCard.new(card.to_treys())


def evaluate_hand(hole_cards: list[Card], board_cards: list[Card]) -> tuple[int, str]:
    """Evaluate hand strength.

    Args:
        hole_cards: The player's 2 hole cards.
        board_cards: The community cards (3, 4, or 5).

    Returns:
        Tuple of (rank, class_string) where rank is 1 (best) to 7462 (worst),
        and class_string is e.g. "Two Pair", "Flush", etc.
    """
    treys_hand = [card_to_treys(c) for c in hole_cards]
    treys_board = [card_to_treys(c) for c in board_cards]

    rank = _evaluator.evaluate(treys_board, treys_hand)
    rank_class = _evaluator.get_rank_class(rank)
    class_string = _evaluator.class_to_string(rank_class)

    return rank, class_string


def calculate_pot_odds(amount_to_call: float, pot_size: float) -> Optional[float]:
    """Calculate pot odds as a ratio.

    Returns the fraction of the new pot you need to win to break even.
    E.g., calling 50 into a 200 pot = 50/250 = 0.20 (20%).
    """
    if amount_to_call <= 0 or pot_size <= 0:
        return None
    total = pot_size + amount_to_call
    return amount_to_call / total


def determine_position(
    game_state: GameState,
) -> Optional[Position]:
    """Determine the agent's position at the table based on dealer button location."""
    me = game_state.me
    if me is None or game_state.dealer_seat is None:
        return None

    # Get active player seats in order
    active_seats = sorted(
        [
            p.seat_number
            for p in game_state.players
            if p.status not in ("empty", "sitting_out")
        ]
    )

    if not active_seats:
        return None

    num_players = len(active_seats)

    # Find dealer index
    try:
        dealer_idx = active_seats.index(game_state.dealer_seat)
    except ValueError:
        # Dealer seat not in active players; find closest
        return Position.UNKNOWN

    # Find my index relative to dealer
    try:
        my_idx = active_seats.index(me.seat_number)
    except ValueError:
        return Position.UNKNOWN

    offset = (my_idx - dealer_idx) % num_players

    position_map = _POSITION_MAP_6MAX if num_players <= 6 else _POSITION_MAP_9MAX

    return position_map.get(offset, Position.UNKNOWN)


def enrich_game_state(game_state: GameState) -> GameState:
    """Add computed fields to a GameState (hand strength, pot odds, position).

    Modifies the game_state in place and returns it.
    """
    # Position
    game_state.my_position = determine_position(game_state)

    # Hand strength (only if we have hole cards and board cards)
    if (
        game_state.my_hole_cards
        and len(game_state.my_hole_cards) == 2
        and len(game_state.board_cards) >= 3
    ):
        try:
            rank, class_str = evaluate_hand(
                game_state.my_hole_cards, game_state.board_cards
            )
            game_state.hand_strength_rank = rank
            game_state.hand_strength_class = class_str
        except Exception as e:
            logger.warning("hand_evaluation_failed", error=str(e))

    # Pot odds
    if game_state.amount_to_call and game_state.total_pot:
        game_state.pot_odds = calculate_pot_odds(
            game_state.amount_to_call, game_state.total_pot
        )

    return game_state
