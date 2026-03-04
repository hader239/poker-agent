"""Vision API screen parser — converts screenshots to GameState."""

from __future__ import annotations

import base64
import io
import json
import time
from typing import Optional

import anthropic
from PIL import Image

import structlog

from poker_agent.config import AgentConfig
from poker_agent.models.game_state import (
    AvailableActions,
    ButtonInfo,
    Card,
    GamePhase,
    GameState,
    Player,
    PlayerStatus,
    Rank,
    Suit,
)
from poker_agent.parser.prompts import PARSER_SYSTEM_PROMPT, PARSER_USER_PROMPT

logger = structlog.get_logger()


class ParseError(Exception):
    """Raised when screen parsing fails."""


class ScreenParser:
    """Parses poker table screenshots into structured GameState using Claude Vision."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = anthropic.Anthropic(
            api_key=config.anthropic_api_key.get_secret_value()
        )
        self.model = config.parser_model
        self._api_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    async def parse(self, screenshot: Image.Image) -> GameState:
        """Parse a screenshot into a GameState.

        Args:
            screenshot: PIL Image of the poker table (at native resolution).

        Returns:
            Parsed GameState with all visible information extracted.

        Raises:
            ParseError: If parsing fails or the response is invalid.
        """
        b64_image = self._encode_image(screenshot)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=PARSER_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64_image,
                                },
                            },
                            {"type": "text", "text": PARSER_USER_PROMPT},
                        ],
                    }
                ],
            )
        except anthropic.APIError as e:
            raise ParseError(f"API call failed: {e}") from e

        self._api_calls += 1
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens

        raw_text = response.content[0].text
        return self._parse_response(raw_text)

    def _encode_image(self, img: Image.Image) -> str:
        """Encode a PIL Image to base64 PNG string."""
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")

    def _parse_response(self, raw_text: str) -> GameState:
        """Parse the raw JSON response into a GameState model."""
        # Strip markdown code fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON from parser: {e}\nRaw: {raw_text[:500]}") from e

        try:
            return self._build_game_state(data)
        except (KeyError, ValueError, TypeError) as e:
            raise ParseError(f"Failed to build GameState: {e}") from e

    def _build_game_state(self, data: dict) -> GameState:
        """Build a GameState from parsed JSON data."""
        # Parse board cards
        board_cards = []
        for card_data in data.get("board_cards") or []:
            board_cards.append(self._parse_card(card_data))

        # Parse hole cards
        my_hole_cards = None
        if data.get("my_hole_cards"):
            my_hole_cards = [self._parse_card(c) for c in data["my_hole_cards"]]

        # Parse players
        players = []
        for p_data in data.get("players") or []:
            hole_cards = None
            if p_data.get("hole_cards"):
                hole_cards = [self._parse_card(c) for c in p_data["hole_cards"]]

            players.append(
                Player(
                    seat_number=p_data["seat_number"],
                    name=p_data.get("name"),
                    stack=p_data.get("stack"),
                    current_bet=p_data.get("current_bet", 0.0),
                    status=PlayerStatus(p_data.get("status", "active")),
                    is_dealer=p_data.get("is_dealer", False),
                    is_me=p_data.get("is_me", False),
                    hole_cards=hole_cards,
                )
            )

        # Parse available actions
        available_actions = None
        if data.get("available_actions"):
            available_actions = self._parse_actions(data["available_actions"])

        return GameState(
            timestamp=time.time(),
            hand_number=data.get("hand_number"),
            parse_confidence=data.get("parse_confidence", 1.0),
            phase=GamePhase(data.get("phase", "unknown")),
            small_blind=data.get("small_blind"),
            big_blind=data.get("big_blind"),
            board_cards=board_cards,
            my_hole_cards=my_hole_cards,
            players=players,
            dealer_seat=data.get("dealer_seat"),
            main_pot=data.get("main_pot"),
            side_pots=data.get("side_pots") or [],
            total_pot=data.get("total_pot"),
            is_my_turn=data.get("is_my_turn", False),
            available_actions=available_actions,
            amount_to_call=data.get("amount_to_call"),
            min_raise=data.get("min_raise"),
            max_raise=data.get("max_raise"),
        )

    def _parse_card(self, card_data: dict) -> Card:
        """Parse a card from JSON data."""
        return Card(
            rank=Rank(card_data["rank"]),
            suit=Suit(card_data["suit"]),
        )

    def _parse_actions(self, actions_data: dict) -> AvailableActions:
        """Parse available actions from JSON data."""

        def parse_button(btn_data: Optional[dict]) -> Optional[ButtonInfo]:
            if btn_data is None:
                return None
            return ButtonInfo(
                label=btn_data.get("label", ""),
                center_x=btn_data["center_x"],
                center_y=btn_data["center_y"],
            )

        preset_buttons = []
        for btn_data in actions_data.get("preset_buttons") or []:
            btn = parse_button(btn_data)
            if btn:
                preset_buttons.append(btn)

        return AvailableActions(
            fold=parse_button(actions_data.get("fold")),
            check=parse_button(actions_data.get("check")),
            call=parse_button(actions_data.get("call")),
            raise_btn=parse_button(actions_data.get("raise_btn")),
            all_in=parse_button(actions_data.get("all_in")),
            raise_input=parse_button(actions_data.get("raise_input")),
            raise_confirm=parse_button(actions_data.get("raise_confirm")),
            bet_slider=parse_button(actions_data.get("bet_slider")),
            preset_buttons=preset_buttons,
        )

    @property
    def stats(self) -> dict:
        """Return API usage statistics."""
        return {
            "api_calls": self._api_calls,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
        }
