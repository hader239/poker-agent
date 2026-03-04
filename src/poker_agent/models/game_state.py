"""Core data models for representing the poker game state."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Suit(str, Enum):
    HEARTS = "h"
    DIAMONDS = "d"
    CLUBS = "c"
    SPADES = "s"


class Rank(str, Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class Card(BaseModel):
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"

    def to_treys(self) -> str:
        """Convert to treys library format (e.g., 'Ah', 'Td')."""
        return f"{self.rank.value}{self.suit.value}"


class GamePhase(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    BETWEEN_HANDS = "between_hands"
    UNKNOWN = "unknown"


class PlayerStatus(str, Enum):
    ACTIVE = "active"
    FOLDED = "folded"
    ALL_IN = "all_in"
    SITTING_OUT = "sitting_out"
    EMPTY_SEAT = "empty"


class Position(str, Enum):
    SMALL_BLIND = "SB"
    BIG_BLIND = "BB"
    UNDER_THE_GUN = "UTG"
    UTG_PLUS_1 = "UTG+1"
    MIDDLE = "MP"
    CUTOFF = "CO"
    BUTTON = "BTN"
    UNKNOWN = "unknown"


class ButtonInfo(BaseModel):
    """A clickable UI button detected in the screenshot."""

    label: str
    center_x: int  # x coordinate in image space (Retina pixels)
    center_y: int  # y coordinate in image space (Retina pixels)
    width: Optional[int] = None
    height: Optional[int] = None
    is_visible: bool = True
    is_enabled: bool = True


class AvailableActions(BaseModel):
    """All action buttons currently visible on the UI."""

    fold: Optional[ButtonInfo] = None
    check: Optional[ButtonInfo] = None
    call: Optional[ButtonInfo] = None
    raise_btn: Optional[ButtonInfo] = None
    all_in: Optional[ButtonInfo] = None
    raise_input: Optional[ButtonInfo] = None  # text field for bet amount
    raise_confirm: Optional[ButtonInfo] = None  # confirm raise button
    bet_slider: Optional[ButtonInfo] = None
    preset_buttons: list[ButtonInfo] = Field(default_factory=list)


class Player(BaseModel):
    """A player at the table."""

    seat_number: int
    name: Optional[str] = None
    stack: Optional[float] = None  # in chips
    current_bet: float = 0.0  # amount bet this street
    status: PlayerStatus = PlayerStatus.ACTIVE
    is_dealer: bool = False
    is_me: bool = False
    position: Optional[Position] = None
    hole_cards: Optional[list[Card]] = None  # visible at showdown


class GameState(BaseModel):
    """Complete snapshot of the poker table state at a point in time."""

    # Meta
    timestamp: float
    hand_number: Optional[int] = None
    parse_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Game structure
    phase: GamePhase
    small_blind: Optional[float] = None
    big_blind: Optional[float] = None

    # Cards
    board_cards: list[Card] = Field(default_factory=list)
    my_hole_cards: Optional[list[Card]] = None

    # Players
    players: list[Player] = Field(default_factory=list)
    dealer_seat: Optional[int] = None

    # Pot
    main_pot: Optional[float] = None
    side_pots: list[float] = Field(default_factory=list)
    total_pot: Optional[float] = None

    # Actions
    is_my_turn: bool = False
    available_actions: Optional[AvailableActions] = None
    amount_to_call: Optional[float] = None
    min_raise: Optional[float] = None
    max_raise: Optional[float] = None

    # Computed (filled in by poker_math after parsing)
    my_position: Optional[Position] = None
    hand_strength_rank: Optional[int] = None  # 1 (royal flush) to 7462
    hand_strength_class: Optional[str] = None  # e.g., "Two Pair", "Flush"
    pot_odds: Optional[float] = None

    @property
    def me(self) -> Optional[Player]:
        return next((p for p in self.players if p.is_me), None)

    @property
    def active_opponents(self) -> list[Player]:
        return [
            p
            for p in self.players
            if not p.is_me and p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
        ]

    @property
    def num_players_in_hand(self) -> int:
        return len(
            [p for p in self.players if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)]
        )
