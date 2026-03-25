"""Session orchestration for the local poker simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from uuid import uuid4

from poker_sim.bots import RandomBot, StrongHeuristicBot, default_bot_style_for_seat
from poker_sim.engine import GameEngine, PlayerAction, SessionConfig, Street, bb_to_chips


@dataclass
class SessionController:
    """Own one game engine and drive bots until the hero acts."""

    config: SessionConfig
    seed: int | None = None
    engine: GameEngine = field(init=False)
    session_id: str = field(default_factory=lambda: uuid4().hex)
    _rng: Random = field(init=False)
    _bots: dict[int, StrongHeuristicBot] = field(init=False)

    def __post_init__(self) -> None:
        self._rng = Random(self.seed)
        self.engine = GameEngine(self.config, seed=self.seed)
        self._bots = {
            seat_index: StrongHeuristicBot(default_bot_style_for_seat(seat_index))
            for seat_index in range(len(self.engine.state.seats))
            if seat_index != self.engine.hero_seat_index
        }

    def start(self) -> list[dict[str, object]]:
        self.engine.start_next_hand()
        snapshots = [self.snapshot()]
        snapshots.extend(self._play_bots_until_hero())
        return snapshots

    def snapshot(self) -> dict[str, object]:
        return self.engine.visible_state_for(
            self.engine.hero_seat_index,
            reveal_all_after_hand=self.config.reveal_all_cards_after_hand,
        )

    def next_hand(self) -> list[dict[str, object]]:
        self.engine.start_next_hand()
        snapshots = [self.snapshot()]
        snapshots.extend(self._play_bots_until_hero())
        return snapshots

    def apply_human_action(self, action: PlayerAction) -> list[dict[str, object]]:
        self.engine.apply_action(self.engine.hero_seat_index, action)
        snapshots = [self.snapshot()]
        snapshots.extend(self._play_bots_until_hero())
        return snapshots

    def benchmark_against_random(self, hands: int, *, seed: int = 7) -> dict[str, float]:
        """Simple benchmark helper for acceptance checks."""
        strong_profit = 0
        bot_rnd = Random(seed)
        for _ in range(hands):
            config = SessionConfig(hero_buyin_bb=100, reveal_all_cards_after_hand=False)
            engine = GameEngine(config, seed=bot_rnd.randint(1, 10_000_000))
            strong_bot = self._bots[1]
            weak_bots = {seat: RandomBot() for seat in range(2, 6)}
            engine.start_next_hand()

            while engine.state.street != Street.HAND_OVER:
                actor = engine.state.actor_index
                assert actor is not None
                snapshot = engine.visible_state_for(actor, reveal_all_after_hand=False)
                if actor == engine.hero_seat_index:
                    action = strong_bot.choose_action(snapshot, rng=bot_rnd)
                elif actor == 1:
                    action = strong_bot.choose_action(snapshot, rng=bot_rnd)
                else:
                    action = weak_bots[actor].choose_action(snapshot, rng=bot_rnd)
                engine.apply_action(actor, action)

            strong_stack = engine.state.seats[0].stack + engine.state.seats[1].stack
            strong_profit += strong_stack - 2 * bb_to_chips(100)

        return {
            "hands": float(hands),
            "strong_pair_profit_bb": strong_profit / 100.0,
            "bb_per_100": (strong_profit / 100.0) / hands * 100.0,
        }

    def _play_bots_until_hero(self) -> list[dict[str, object]]:
        snapshots = []
        while (
            self.engine.state.street != Street.HAND_OVER
            and self.engine.state.actor_index is not None
            and self.engine.state.actor_index != self.engine.hero_seat_index
        ):
            actor = self.engine.state.actor_index
            bot = self._bots[actor]
            bot_snapshot = self.engine.visible_state_for(actor, reveal_all_after_hand=False)
            action = bot.choose_action(bot_snapshot, rng=self._rng)
            self.engine.apply_action(actor, action)
            snapshots.append(self.snapshot())
        return snapshots
