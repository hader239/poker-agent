"""Action models for agent decisions."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"
    # Lifecycle actions
    SIT_IN = "sit_in"
    SIT_OUT = "sit_out"
    BUY_IN = "buy_in"
    LEAVE_TABLE = "leave_table"


class Action(BaseModel):
    """An action the agent has decided to take."""

    action_type: ActionType
    amount: Optional[float] = None  # in chips, for raise/buy-in
    amount_bb: Optional[float] = None  # normalized to BB
    reasoning: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
