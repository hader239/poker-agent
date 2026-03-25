from __future__ import annotations

import sys
from pathlib import Path
from random import Random
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poker_sim.bots import StrongHeuristicBot, default_bot_style_for_seat  # noqa: E402
from poker_sim.cards import Card  # noqa: E402
from poker_sim.engine import ActionType, GameEngine, SessionConfig, Street  # noqa: E402


class BotPolicyTest(unittest.TestCase):
    def test_bot_open_raises_premium_hand_in_unopened_pot(self) -> None:
        engine = GameEngine(
            SessionConfig(hero_buyin_bb=50, reveal_all_cards_after_hand=False), seed=11
        )
        engine.start_next_hand()
        engine.state.actor_index = 3
        engine._action_queue = [3, 4, 5, 0, 1, 2]  # keep unopened state deterministic
        engine.state.seats[3].hole_cards = [Card.from_code("As"), Card.from_code("Ah")]
        bot = StrongHeuristicBot(default_bot_style_for_seat(3))
        snapshot = engine.visible_state_for(3, reveal_all_after_hand=False)
        action = bot.choose_action(snapshot, rng=Random(1))
        self.assertIn(action.action_type, {ActionType.RAISE_TO, ActionType.ALL_IN})

    def test_bot_does_not_open_limp_from_utg(self) -> None:
        engine = GameEngine(
            SessionConfig(hero_buyin_bb=50, reveal_all_cards_after_hand=False), seed=11
        )
        engine.start_next_hand()
        engine.state.actor_index = 3
        engine._action_queue = [3, 4, 5, 0, 1, 2]
        engine.state.seats[3].hole_cards = [Card.from_code("7d"), Card.from_code("2c")]
        bot = StrongHeuristicBot(default_bot_style_for_seat(3))
        snapshot = engine.visible_state_for(3, reveal_all_after_hand=False)
        action = bot.choose_action(snapshot, rng=Random(2))
        self.assertNotEqual(action.action_type, ActionType.CALL)


if __name__ == "__main__":
    unittest.main()
