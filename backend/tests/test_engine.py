from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poker_sim.cards import Card
from poker_sim.engine import (  # noqa: E402
    ActionType,
    GameEngine,
    PlayerAction,
    SessionConfig,
    Street,
    bb_to_chips,
)


class EngineRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GameEngine(
            SessionConfig(hero_buyin_bb=50, reveal_all_cards_after_hand=False), seed=17
        )
        self.engine.start_next_hand()

    def test_opening_state_posts_blinds_and_sets_actor(self) -> None:
        self.assertEqual(self.engine.state.street, Street.PREFLOP)
        self.assertEqual(self.engine.state.button_index, 0)
        self.assertEqual(self.engine.state.seats[1].committed, bb_to_chips(0.5))
        self.assertEqual(self.engine.state.seats[2].committed, bb_to_chips(1))
        self.assertEqual(self.engine.state.actor_index, 3)

    def test_preflop_foldout_takes_no_rake(self) -> None:
        for seat_index in [3, 4, 5, 0, 1]:
            self.engine.apply_action(seat_index, PlayerAction(ActionType.FOLD))

        result = self.engine.state.hand_result
        self.assertIsNotNone(result)
        self.assertEqual(result.rake_taken, 0)
        self.assertEqual(result.winners, [2])
        self.assertEqual(result.pot_distribution[2], bb_to_chips(1.5))

    def test_side_pot_resolution_splits_main_and_side(self) -> None:
        engine = GameEngine(
            SessionConfig(hero_buyin_bb=100, reveal_all_cards_after_hand=False), seed=2
        )
        engine.start_next_hand()
        engine._rake_amount = lambda: 0  # type: ignore[method-assign]
        engine.state.street = Street.RIVER
        engine.state.board = [
            Card.from_code("2c"),
            Card.from_code("7d"),
            Card.from_code("9h"),
            Card.from_code("Ts"),
            Card.from_code("Jc"),
        ]
        for seat in engine.state.seats:
            seat.folded = True
            seat.all_in = True
            seat.contributed = 0

        seat0 = engine.state.seats[0]
        seat1 = engine.state.seats[1]
        seat2 = engine.state.seats[2]
        seat0.folded = False
        seat1.folded = False
        seat2.folded = False
        seat0.hole_cards = [Card.from_code("Ah"), Card.from_code("Ad")]
        seat1.hole_cards = [Card.from_code("Kh"), Card.from_code("Kd")]
        seat2.hole_cards = [Card.from_code("Qh"), Card.from_code("Qd")]
        seat0.contributed = bb_to_chips(5)
        seat1.contributed = bb_to_chips(10)
        seat2.contributed = bb_to_chips(10)
        seat0.stack = 0
        seat1.stack = 0
        seat2.stack = 0
        seat0.all_in = True
        seat1.all_in = True
        seat2.all_in = True

        engine._resolve_showdown()

        result = engine.state.hand_result
        self.assertIsNotNone(result)
        self.assertEqual(result.pot_distribution[0], bb_to_chips(15))
        self.assertEqual(result.pot_distribution[1], bb_to_chips(10))
        self.assertEqual(result.winning_hand_names, {0: "One Pair", 1: "One Pair"})

    def test_raise_below_minimum_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.apply_action(
                3,
                PlayerAction(ActionType.RAISE_TO, amount=bb_to_chips(1.5)),
            )


if __name__ == "__main__":
    unittest.main()
