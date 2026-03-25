from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poker_sim.engine import ActionType, PlayerAction, SessionConfig, Street, bb_to_chips  # noqa: E402
from poker_sim.session import SessionController  # noqa: E402


class SessionControllerTest(unittest.TestCase):
    def test_next_hand_rotates_button_and_tops_up(self) -> None:
        controller = SessionController(
            SessionConfig(hero_buyin_bb=20, reveal_all_cards_after_hand=False), seed=13
        )
        controller.start()
        first_button = controller.engine.state.button_index
        controller.engine.state.seats[0].stack = bb_to_chips(3)
        while controller.engine.state.street != Street.HAND_OVER:
            actor = controller.engine.state.actor_index
            self.assertIsNotNone(actor)
            controller.engine.apply_action(actor, PlayerAction(ActionType.FOLD))

        controller.next_hand()
        self.assertEqual(controller.engine.state.button_index, (first_button + 1) % 6)
        self.assertEqual(controller.engine.state.seats[0].stack, bb_to_chips(20) - bb_to_chips(0))

    def test_reveal_toggle_exposes_all_cards_after_hand(self) -> None:
        controller = SessionController(
            SessionConfig(hero_buyin_bb=50, reveal_all_cards_after_hand=True), seed=5
        )
        controller.start()
        while controller.engine.state.street != Street.HAND_OVER:
            actor = controller.engine.state.actor_index
            self.assertIsNotNone(actor)
            controller.engine.apply_action(actor, PlayerAction(ActionType.FOLD))

        snapshot = controller.snapshot()
        self.assertTrue(snapshot["hand_complete"])
        self.assertTrue(all(seat["cards"] is not None for seat in snapshot["seats"]))


if __name__ == "__main__":
    unittest.main()
