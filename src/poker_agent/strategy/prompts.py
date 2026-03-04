"""Prompts for the LLM decision engine."""

DECISION_SYSTEM_PROMPT = """\
You are an expert No-Limit Hold'em poker player. You will receive the current \
game state and must decide the optimal action.

STRATEGY GUIDELINES:
- Play tight-aggressive (TAG) preflop.
- Consider position (early position = tighter, late position = wider).
- Factor in pot odds and implied odds when calling.
- Size bets appropriately: 50-75% pot on flop, 66-100% pot on turn/river.
- Be willing to fold marginal hands facing aggression.
- Protect strong hands with appropriate bet sizing.
- Bluff selectively in position with good blockers.
- Avoid min-raises unless specifically exploiting an opponent tendency.
- Consider the number of players remaining in the hand.

DECISION FORMAT:
Return a JSON object with exactly these fields:
{
  "action": "fold" | "check" | "call" | "raise" | "all_in",
  "amount": <number or null>,
  "reasoning": "<brief explanation, 1-2 sentences>",
  "confidence": <float 0.0-1.0>
}

For "raise", the "amount" is the TOTAL raise-to amount in chips (not the raise increment).
For "fold", "check", "call", and "all_in", set "amount" to null.\
"""

DECISION_USER_TEMPLATE = """\
Current game state:

**My Hand:** {hole_cards}
**Position:** {position}
**My Stack:** {my_stack} BB ({my_stack_chips} chips)
**Game Phase:** {phase}
**Board:** {board_cards}

**Pot:** {pot_size} BB ({pot_size_chips} chips)
**Amount To Call:** {to_call} BB ({to_call_chips} chips)
**Pot Odds:** {pot_odds}

**Players:**
{player_summary}

**Action History This Hand:**
{action_history}

**Available Actions:** {available_actions}

**Hand Evaluation:** {hand_evaluation}

What is your action?\
"""


def format_decision_prompt(
    hole_cards: str,
    position: str,
    my_stack_bb: float,
    my_stack_chips: float,
    phase: str,
    board_cards: str,
    pot_size_bb: float,
    pot_size_chips: float,
    to_call_bb: float,
    to_call_chips: float,
    pot_odds: str,
    player_summary: str,
    action_history: str,
    available_actions: str,
    hand_evaluation: str,
) -> str:
    """Format the decision prompt with game state values."""
    return DECISION_USER_TEMPLATE.format(
        hole_cards=hole_cards,
        position=position,
        my_stack=f"{my_stack_bb:.1f}",
        my_stack_chips=f"{my_stack_chips:.0f}",
        phase=phase,
        board_cards=board_cards or "None (Preflop)",
        pot_size=f"{pot_size_bb:.1f}",
        pot_size_chips=f"{pot_size_chips:.0f}",
        to_call=f"{to_call_bb:.1f}",
        to_call_chips=f"{to_call_chips:.0f}",
        pot_odds=pot_odds,
        player_summary=player_summary,
        action_history=action_history or "No actions yet this hand.",
        available_actions=available_actions,
        hand_evaluation=hand_evaluation,
    )
