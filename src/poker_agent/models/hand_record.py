"""Hand history record models for logging."""

from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel, Field


class ActionRecord(BaseModel):
    """Record of a single action taken during a hand."""

    timestamp: float
    phase: str
    player_name: Optional[str]
    player_seat: int
    action: str
    amount: Optional[float] = None
    is_agent: bool = False
    reasoning: Optional[str] = None


class HandRecord(BaseModel):
    """Complete record of a played hand for logging and analysis."""

    hand_id: str
    hand_number: Optional[int] = None
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None

    # Structure
    small_blind: float
    big_blind: float
    num_players: int

    # Cards
    my_hole_cards: Optional[list[str]] = None  # ["Ah", "Ks"]
    board: list[str] = Field(default_factory=list)

    # My info
    my_position: Optional[str] = None
    my_starting_stack: Optional[float] = None
    my_ending_stack: Optional[float] = None
    net_result: Optional[float] = None

    # Actions
    actions: list[ActionRecord] = Field(default_factory=list)

    # Analysis
    went_to_showdown: bool = False
    won_hand: Optional[bool] = None
    screenshots: list[str] = Field(default_factory=list)
