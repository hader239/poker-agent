"""Hand history logger — writes per-hand records as JSON Lines."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

import structlog

from poker_agent.models.actions import Action
from poker_agent.models.game_state import GameState
from poker_agent.models.hand_record import ActionRecord, HandRecord

logger = structlog.get_logger()


class HandLogger:
    """Logs individual poker hands to a JSONL file."""

    def __init__(self, hand_history_dir: Path):
        self.hand_history_dir = hand_history_dir
        self.hand_history_dir.mkdir(parents=True, exist_ok=True)
        self._current_hand: Optional[HandRecord] = None
        self._last_phase: Optional[str] = None

        # Create a session-specific log file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._log_path = self.hand_history_dir / f"hands_{timestamp}.jsonl"

    def start_hand(self, game_state: GameState) -> None:
        """Start recording a new hand."""
        me = game_state.me

        self._current_hand = HandRecord(
            hand_id=str(uuid.uuid4())[:8],
            hand_number=game_state.hand_number,
            small_blind=game_state.small_blind or 0,
            big_blind=game_state.big_blind or 0,
            num_players=game_state.num_players_in_hand,
            my_hole_cards=(
                [str(c) for c in game_state.my_hole_cards]
                if game_state.my_hole_cards
                else None
            ),
            my_position=(
                game_state.my_position.value if game_state.my_position else None
            ),
            my_starting_stack=me.stack if me else None,
        )
        self._last_phase = game_state.phase.value

        logger.info(
            "hand_started",
            hand_id=self._current_hand.hand_id,
            hand_number=game_state.hand_number,
        )

    def log_action(
        self, game_state: GameState, action: Action, is_agent: bool = True
    ) -> None:
        """Log an action taken during the current hand."""
        if self._current_hand is None:
            return

        me = game_state.me
        record = ActionRecord(
            timestamp=time.time(),
            phase=game_state.phase.value,
            player_name=me.name if me and is_agent else None,
            player_seat=me.seat_number if me else -1,
            action=action.action_type.value,
            amount=action.amount,
            is_agent=is_agent,
            reasoning=action.reasoning,
        )
        self._current_hand.actions.append(record)

    def update_state(self, game_state: GameState) -> None:
        """Update the hand record with new state info (e.g., new board cards)."""
        if self._current_hand is None:
            return

        # Update board cards
        if game_state.board_cards:
            self._current_hand.board = [str(c) for c in game_state.board_cards]

        # Track phase changes
        current_phase = game_state.phase.value
        if current_phase != self._last_phase:
            self._last_phase = current_phase

    def add_screenshot(self, path: str) -> None:
        """Add a screenshot path to the current hand record."""
        if self._current_hand is not None:
            self._current_hand.screenshots.append(path)

    def complete_hand(
        self,
        final_state: GameState,
        won: Optional[bool] = None,
    ) -> Optional[HandRecord]:
        """Complete the current hand and write it to the log file."""
        if self._current_hand is None:
            return None

        hand = self._current_hand
        hand.end_time = time.time()

        me = final_state.me
        if me:
            hand.my_ending_stack = me.stack
            if hand.my_starting_stack is not None and me.stack is not None:
                hand.net_result = me.stack - hand.my_starting_stack

        hand.won_hand = won
        hand.went_to_showdown = final_state.phase.value == "showdown"

        # Update final board state
        if final_state.board_cards:
            hand.board = [str(c) for c in final_state.board_cards]

        # Write to file
        self._write_record(hand)

        logger.info(
            "hand_completed",
            hand_id=hand.hand_id,
            net_result=hand.net_result,
            actions=len(hand.actions),
        )

        self._current_hand = None
        self._last_phase = None
        return hand

    def _write_record(self, hand: HandRecord) -> None:
        """Append a hand record to the JSONL file."""
        with open(self._log_path, "a") as f:
            f.write(hand.model_dump_json() + "\n")

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def current_hand(self) -> Optional[HandRecord]:
        return self._current_hand
