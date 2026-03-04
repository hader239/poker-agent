"""Claude-based LLM decision engine."""

from __future__ import annotations

import json
from typing import Optional

import anthropic

import structlog

from poker_agent.config import AgentConfig
from poker_agent.models.actions import Action, ActionType
from poker_agent.models.game_state import GameState, PlayerStatus
from poker_agent.models.hand_record import HandRecord
from poker_agent.strategy.base import Strategy
from poker_agent.strategy.prompts import DECISION_SYSTEM_PROMPT, format_decision_prompt

logger = structlog.get_logger()


class LLMStrategy(Strategy):
    """Claude API-based decision engine for poker play."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = anthropic.Anthropic(
            api_key=config.anthropic_api_key.get_secret_value()
        )
        self.model = config.decision_model
        self._hand_context: list[dict] = []
        self._api_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    async def decide(self, game_state: GameState) -> Action:
        """Decide the best action given the current game state."""
        prompt = self._build_prompt(game_state)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=DECISION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            logger.error("llm_decision_failed", error=str(e))
            return self._fallback_action(game_state)

        self._api_calls += 1
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens

        raw_text = response.content[0].text
        action = self._parse_decision(raw_text, game_state)

        self._hand_context.append(
            {
                "phase": game_state.phase.value,
                "action": action.action_type.value,
                "amount": action.amount,
                "reasoning": action.reasoning,
            }
        )

        logger.info(
            "decision_made",
            action=action.action_type.value,
            amount=action.amount,
            reasoning=action.reasoning,
            confidence=action.confidence,
        )
        return action

    async def on_hand_start(self, game_state: GameState) -> None:
        """Reset hand context for a new hand."""
        self._hand_context = []

    async def on_hand_end(self, hand_record: HandRecord) -> None:
        """Log hand result."""
        self._hand_context = []

    def _build_prompt(self, state: GameState) -> str:
        """Build the decision prompt from game state."""
        bb = state.big_blind or 1.0
        me = state.me

        # Hole cards
        hole_cards = "Unknown"
        if state.my_hole_cards:
            hole_cards = " ".join(str(c) for c in state.my_hole_cards)

        # Board cards
        board_cards = " ".join(str(c) for c in state.board_cards) if state.board_cards else ""

        # Position
        position = state.my_position.value if state.my_position else "Unknown"

        # My stack
        my_stack_chips = me.stack if me and me.stack else 0.0
        my_stack_bb = my_stack_chips / bb

        # Pot
        pot_chips = state.total_pot or state.main_pot or 0.0
        pot_bb = pot_chips / bb

        # To call
        to_call_chips = state.amount_to_call or 0.0
        to_call_bb = to_call_chips / bb

        # Pot odds
        pot_odds = "N/A"
        if state.pot_odds is not None:
            pot_odds = f"{state.pot_odds:.1%}"

        # Player summary
        player_lines = []
        for p in state.players:
            if p.status == PlayerStatus.EMPTY_SEAT:
                continue
            stack_str = f"{p.stack:.0f}" if p.stack is not None else "?"
            pos_str = f" ({p.position.value})" if p.position else ""
            status_str = f" [{p.status.value}]" if p.status != PlayerStatus.ACTIVE else ""
            bet_str = f" bet:{p.current_bet:.0f}" if p.current_bet > 0 else ""
            me_str = " (ME)" if p.is_me else ""
            dealer_str = " [D]" if p.is_dealer else ""
            player_lines.append(
                f"  Seat {p.seat_number}{pos_str}: {p.name or '?'} "
                f"- Stack: {stack_str}{bet_str}{status_str}{dealer_str}{me_str}"
            )
        player_summary = "\n".join(player_lines)

        # Action history from hand context
        action_history = ""
        if self._hand_context:
            history_lines = []
            for ctx in self._hand_context:
                amt = f" {ctx['amount']:.0f}" if ctx.get("amount") else ""
                history_lines.append(f"  [{ctx['phase']}] Agent: {ctx['action']}{amt}")
            action_history = "\n".join(history_lines)

        # Available actions
        action_list = []
        if state.available_actions:
            aa = state.available_actions
            if aa.fold:
                action_list.append("Fold")
            if aa.check:
                action_list.append("Check")
            if aa.call:
                action_list.append(f"Call ({aa.call.label})")
            if aa.raise_btn:
                min_r = f", min: {state.min_raise:.0f}" if state.min_raise else ""
                max_r = f", max: {state.max_raise:.0f}" if state.max_raise else ""
                action_list.append(f"Raise{min_r}{max_r}")
            if aa.all_in:
                action_list.append("All-In")
        available_actions_str = ", ".join(action_list) if action_list else "Unknown"

        # Hand evaluation
        hand_eval = "N/A (preflop)" if not state.board_cards else "Unknown"
        if state.hand_strength_class and state.hand_strength_rank:
            hand_eval = f"{state.hand_strength_class} (rank {state.hand_strength_rank}/7462)"

        return format_decision_prompt(
            hole_cards=hole_cards,
            position=position,
            my_stack_bb=my_stack_bb,
            my_stack_chips=my_stack_chips,
            phase=state.phase.value,
            board_cards=board_cards,
            pot_size_bb=pot_bb,
            pot_size_chips=pot_chips,
            to_call_bb=to_call_bb,
            to_call_chips=to_call_chips,
            pot_odds=pot_odds,
            player_summary=player_summary,
            action_history=action_history,
            available_actions=available_actions_str,
            hand_evaluation=hand_eval,
        )

    def _parse_decision(self, raw_text: str, game_state: GameState) -> Action:
        """Parse the LLM response into an Action."""
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("decision_parse_failed", raw=raw_text[:300])
            return self._fallback_action(game_state)

        action_str = data.get("action", "fold").lower()
        amount = data.get("amount")
        reasoning = data.get("reasoning", "")
        confidence = data.get("confidence", 0.5)

        # Map action string to ActionType
        action_map = {
            "fold": ActionType.FOLD,
            "check": ActionType.CHECK,
            "call": ActionType.CALL,
            "raise": ActionType.RAISE,
            "all_in": ActionType.ALL_IN,
        }

        action_type = action_map.get(action_str, ActionType.FOLD)

        # Normalize raise amount to BB
        bb = game_state.big_blind or 1.0
        amount_bb = amount / bb if amount else None

        return Action(
            action_type=action_type,
            amount=amount,
            amount_bb=amount_bb,
            reasoning=reasoning,
            confidence=confidence,
        )

    def _fallback_action(self, game_state: GameState) -> Action:
        """Return a safe fallback action when the LLM fails."""
        # Prefer check over fold if available
        if game_state.available_actions and game_state.available_actions.check:
            return Action(
                action_type=ActionType.CHECK,
                reasoning="Fallback: LLM decision failed, checking.",
                confidence=0.0,
            )
        return Action(
            action_type=ActionType.FOLD,
            reasoning="Fallback: LLM decision failed, folding.",
            confidence=0.0,
        )

    @property
    def stats(self) -> dict:
        """Return API usage statistics."""
        return {
            "api_calls": self._api_calls,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
        }
