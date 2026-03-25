"""Pure Python no-limit hold'em engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from random import Random
from typing import Iterable

from poker_sim.cards import Card, best_rank, full_deck, hand_category_name

CHIP_SCALE = 100
SMALL_BLIND = 50
BIG_BLIND = 100
RAKE_CAP = 800
SEAT_COUNT = 6


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    HAND_OVER = "hand_over"


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE_TO = "raise_to"
    ALL_IN = "all_in"


@dataclass
class SessionConfig:
    hero_buyin_bb: int
    reveal_all_cards_after_hand: bool
    hero_seat_index: int = 0


@dataclass
class PlayerAction:
    action_type: ActionType
    amount: int | None = None


@dataclass
class LegalActionSet:
    can_fold: bool
    can_check: bool
    call_amount: int
    min_raise_to: int | None
    max_raise_to: int | None


@dataclass
class ActionRecord:
    seat_index: int
    player_name: str
    street: Street
    action_type: ActionType
    amount: int | None
    contribution: int


@dataclass
class HandResult:
    winners: list[int]
    pot_distribution: dict[int, int]
    rake_taken: int
    showdown_cards_revealed: dict[int, list[Card]]
    winning_hand_names: dict[int, str]
    summary: str


@dataclass
class SeatState:
    seat_index: int
    name: str
    is_human: bool
    target_stack: int
    stack: int
    hole_cards: list[Card] = field(default_factory=list)
    committed: int = 0
    contributed: int = 0
    folded: bool = False
    all_in: bool = False
    acted_this_round: bool = False
    last_acted_token: int = -1

    @property
    def active_for_pot(self) -> bool:
        return not self.folded

    @property
    def can_act(self) -> bool:
        return not self.folded and not self.all_in


@dataclass
class TableState:
    seats: list[SeatState]
    button_index: int
    street: Street = Street.HAND_OVER
    board: list[Card] = field(default_factory=list)
    deck: list[Card] = field(default_factory=list)
    actor_index: int | None = None
    current_bet: int = 0
    last_full_raise_size: int = BIG_BLIND
    action_history: list[ActionRecord] = field(default_factory=list)
    hand_number: int = 0
    hand_result: HandResult | None = None
    full_raise_token: int = 0
    initiative_seat: int | None = None
    preflop_last_raise_size: int = BIG_BLIND


class GameEngine:
    """Owns the full table rules and current table state."""

    def __init__(self, config: SessionConfig, *, seed: int | None = None) -> None:
        self.config = config
        self.random = Random(seed)
        self._action_queue: list[int] = []
        self._revealed_showdown_seats: set[int] = set()

        hero_stack = bb_to_chips(max(10, min(100, config.hero_buyin_bb)))
        seats: list[SeatState] = []
        for seat_index in range(SEAT_COUNT):
            is_human = seat_index == config.hero_seat_index
            target_stack = hero_stack if is_human else bb_to_chips(100)
            name = "Hero" if is_human else f"Bot {seat_index}"
            seats.append(
                SeatState(
                    seat_index=seat_index,
                    name=name,
                    is_human=is_human,
                    target_stack=target_stack,
                    stack=target_stack,
                )
            )

        self.state = TableState(seats=seats, button_index=SEAT_COUNT - 1)

    @property
    def hero_seat_index(self) -> int:
        return self.config.hero_seat_index

    @property
    def hero_to_act(self) -> bool:
        return self.state.actor_index == self.hero_seat_index and self.state.street != Street.HAND_OVER

    def top_up_between_hands(self) -> None:
        for seat in self.state.seats:
            if seat.stack < seat.target_stack:
                seat.stack = seat.target_stack

    def start_next_hand(self) -> None:
        self.top_up_between_hands()
        self.state.hand_number += 1
        self.state.button_index = self._next_occupied_seat(self.state.button_index)
        self.state.street = Street.PREFLOP
        self.state.board = []
        self.state.deck = full_deck()
        self.random.shuffle(self.state.deck)
        self.state.current_bet = BIG_BLIND
        self.state.last_full_raise_size = BIG_BLIND
        self.state.preflop_last_raise_size = BIG_BLIND
        self.state.action_history = []
        self.state.hand_result = None
        self.state.full_raise_token = 0
        self.state.initiative_seat = self._big_blind_index()
        self._revealed_showdown_seats.clear()

        for seat in self.state.seats:
            seat.hole_cards = []
            seat.committed = 0
            seat.contributed = 0
            seat.folded = False
            seat.all_in = False
            seat.acted_this_round = False
            seat.last_acted_token = -1

        for _round in range(2):
            for seat in self.state.seats:
                seat.hole_cards.append(self.state.deck.pop())

        self._post_blind(self._small_blind_index(), SMALL_BLIND)
        self._post_blind(self._big_blind_index(), BIG_BLIND)
        self._action_queue = self._round_order(start_index=self._next_occupied_seat(self._big_blind_index()))
        self.state.actor_index = self._action_queue[0]

    def seat_position(self, seat_index: int) -> str:
        button = self.state.button_index
        labels = ["BTN", "SB", "BB", "UTG", "HJ", "CO"]
        mapping: dict[int, str] = {}
        current = button
        for label in labels:
            mapping[current] = label
            current = self._next_occupied_seat(current)
        return mapping.get(seat_index, f"Seat {seat_index + 1}")

    def pot_size(self) -> int:
        return sum(seat.contributed for seat in self.state.seats)

    def live_seat_indices(self) -> list[int]:
        return [seat.seat_index for seat in self.state.seats if not seat.folded]

    def actionable_seat_indices(self) -> list[int]:
        return [seat.seat_index for seat in self.state.seats if seat.can_act]

    def legal_actions_for(self, seat_index: int) -> LegalActionSet:
        seat = self.state.seats[seat_index]
        if self.state.actor_index != seat_index or self.state.street == Street.HAND_OVER:
            return LegalActionSet(False, False, 0, None, None)

        to_call = max(0, self.state.current_bet - seat.committed)
        can_check = to_call == 0
        can_fold = to_call > 0
        call_amount = min(to_call, seat.stack)

        min_raise_to: int | None = None
        max_raise_to: int | None = None
        can_raise = False
        if seat.stack > to_call:
            can_raise = (not seat.acted_this_round) or (
                seat.last_acted_token < self.state.full_raise_token
            )

        if can_raise:
            if self.state.current_bet == 0:
                min_raise_to = BIG_BLIND
            else:
                min_raise_to = self.state.current_bet + self.state.last_full_raise_size
            max_raise_to = seat.committed + seat.stack
            if max_raise_to < min_raise_to:
                min_raise_to = None
                max_raise_to = None

        return LegalActionSet(
            can_fold=can_fold,
            can_check=can_check,
            call_amount=call_amount,
            min_raise_to=min_raise_to,
            max_raise_to=max_raise_to,
        )

    def apply_action(self, seat_index: int, action: PlayerAction) -> None:
        if seat_index != self.state.actor_index:
            raise ValueError("action submitted for non-acting seat")

        seat = self.state.seats[seat_index]
        legal = self.legal_actions_for(seat_index)
        contribution = 0
        target_total: int | None = None
        increased_bet = False

        if action.action_type == ActionType.FOLD:
            if not legal.can_fold:
                raise ValueError("cannot fold here")
            seat.folded = True
        elif action.action_type == ActionType.CHECK:
            if not legal.can_check:
                raise ValueError("cannot check here")
        elif action.action_type == ActionType.CALL:
            if legal.call_amount <= 0:
                raise ValueError("nothing to call")
            contribution = self._commit(seat, seat.committed + legal.call_amount)
        elif action.action_type == ActionType.BET:
            if legal.min_raise_to is None or action.amount is None:
                raise ValueError("bet not available")
            target_total = action.amount
        elif action.action_type == ActionType.RAISE_TO:
            if legal.min_raise_to is None or action.amount is None:
                raise ValueError("raise not available")
            target_total = action.amount
        elif action.action_type == ActionType.ALL_IN:
            if seat.stack <= 0:
                raise ValueError("seat has no chips left")
            target_total = seat.committed + seat.stack
        else:
            raise ValueError(f"unsupported action: {action.action_type}")

        current_bet_before = self.state.current_bet
        if target_total is not None:
            max_total = seat.committed + seat.stack
            if target_total > max_total:
                raise ValueError("bet exceeds stack")

            if action.action_type in (ActionType.BET, ActionType.RAISE_TO):
                if legal.min_raise_to is None or legal.max_raise_to is None:
                    raise ValueError("raise not available")
                if target_total < legal.min_raise_to or target_total > legal.max_raise_to:
                    raise ValueError("raise target outside legal bounds")

            contribution = self._commit(seat, target_total)
            increased_bet = target_total > current_bet_before
            if increased_bet:
                raise_size = target_total if current_bet_before == 0 else target_total - current_bet_before
                full_raise = raise_size >= self.state.last_full_raise_size
                self.state.current_bet = target_total
                self.state.initiative_seat = seat_index
                if full_raise:
                    self.state.last_full_raise_size = raise_size
                    self.state.preflop_last_raise_size = raise_size
                    self.state.full_raise_token += 1

        if action.action_type == ActionType.CALL and seat.stack == 0:
            seat.all_in = True

        if target_total is not None and seat.stack == 0:
            seat.all_in = True

        seat.acted_this_round = True
        seat.last_acted_token = self.state.full_raise_token

        self.state.action_history.append(
            ActionRecord(
                seat_index=seat_index,
                player_name=seat.name,
                street=self.state.street,
                action_type=action.action_type,
                amount=target_total,
                contribution=contribution,
            )
        )

        if increased_bet:
            self._action_queue = self._round_order(start_index=seat_index, exclude_start=True)
        else:
            self._action_queue.pop(0)

        if len(self.live_seat_indices()) == 1:
            self._award_uncontested(self.live_seat_indices()[0])
            return

        if not self._action_queue:
            self._end_betting_round()
            return

        self.state.actor_index = self._action_queue[0]

    def visible_state_for(self, viewer_seat_index: int, *, reveal_all_after_hand: bool = False) -> dict[str, object]:
        legal = self.legal_actions_for(viewer_seat_index)
        showdown_revealed = reveal_all_after_hand and self.state.street == Street.HAND_OVER

        seats_payload = []
        for other in self.state.seats:
            cards = None
            if other.seat_index == viewer_seat_index:
                cards = [card.code for card in other.hole_cards]
            elif showdown_revealed:
                cards = [card.code for card in other.hole_cards]
            elif self.state.street == Street.HAND_OVER and other.seat_index in self._revealed_showdown_seats:
                cards = [card.code for card in other.hole_cards]

            seats_payload.append(
                {
                    "seat_index": other.seat_index,
                    "name": other.name,
                    "is_human": other.is_human,
                    "position": self.seat_position(other.seat_index),
                    "stack_bb": chips_to_bb(other.stack),
                    "committed_bb": chips_to_bb(other.committed),
                    "contributed_bb": chips_to_bb(other.contributed),
                    "cards": cards,
                    "folded": other.folded,
                    "all_in": other.all_in,
                    "acting": other.seat_index == self.state.actor_index,
                }
            )

        hand_result = None
        if self.state.hand_result is not None:
            hand_result = {
                "winners": self.state.hand_result.winners,
                "pot_distribution_bb": {
                    str(seat_index): chips_to_bb(amount)
                    for seat_index, amount in self.state.hand_result.pot_distribution.items()
                },
                "rake_bb": chips_to_bb(self.state.hand_result.rake_taken),
                "winning_hand_names": self.state.hand_result.winning_hand_names,
                "summary": self.state.hand_result.summary,
            }

        return {
            "viewer_seat_index": viewer_seat_index,
            "hero_seat_index": self.hero_seat_index,
            "hand_number": self.state.hand_number,
            "street": self.state.street.value,
            "board": [card.code for card in self.state.board],
            "button_index": self.state.button_index,
            "initiative_seat": self.state.initiative_seat,
            "pot_bb": chips_to_bb(self.pot_size()),
            "current_bet_bb": chips_to_bb(self.state.current_bet),
            "actor_index": self.state.actor_index,
            "seats": seats_payload,
            "legal_actions": {
                "can_fold": legal.can_fold,
                "can_check": legal.can_check,
                "call_amount_bb": chips_to_bb(legal.call_amount),
                "min_raise_to_bb": chips_to_bb(legal.min_raise_to) if legal.min_raise_to else None,
                "max_raise_to_bb": chips_to_bb(legal.max_raise_to) if legal.max_raise_to else None,
            }
            if viewer_seat_index == self.state.actor_index
            else None,
            "action_history": [
                {
                    "seat_index": item.seat_index,
                    "player_name": item.player_name,
                    "street": item.street.value,
                    "action_type": item.action_type.value,
                    "amount_bb": chips_to_bb(item.amount) if item.amount is not None else None,
                    "contribution_bb": chips_to_bb(item.contribution),
                }
                for item in self.state.action_history[-12:]
            ],
            "hand_complete": self.state.street == Street.HAND_OVER,
            "hand_result": hand_result,
            "reveal_all_cards_after_hand": reveal_all_after_hand,
        }

    def _post_blind(self, seat_index: int, blind_amount: int) -> None:
        seat = self.state.seats[seat_index]
        self._commit(seat, min(blind_amount, seat.stack))
        if seat.stack == 0:
            seat.all_in = True

    def _commit(self, seat: SeatState, target_total: int) -> int:
        if target_total < seat.committed:
            raise ValueError("cannot reduce committed amount")
        contribution = target_total - seat.committed
        if contribution > seat.stack:
            raise ValueError("insufficient stack")
        seat.stack -= contribution
        seat.committed = target_total
        seat.contributed += contribution
        return contribution

    def _end_betting_round(self) -> None:
        if self.state.street == Street.RIVER:
            self._resolve_showdown()
            return

        for seat in self.state.seats:
            seat.committed = 0
            seat.acted_this_round = False
            seat.last_acted_token = -1

        self.state.current_bet = 0
        self.state.last_full_raise_size = BIG_BLIND
        self.state.full_raise_token = 0

        if self.state.street == Street.PREFLOP:
            self.state.board.extend([self.state.deck.pop(), self.state.deck.pop(), self.state.deck.pop()])
            self.state.street = Street.FLOP
        elif self.state.street == Street.FLOP:
            self.state.board.append(self.state.deck.pop())
            self.state.street = Street.TURN
        elif self.state.street == Street.TURN:
            self.state.board.append(self.state.deck.pop())
            self.state.street = Street.RIVER

        if len(self.actionable_seat_indices()) <= 1 and len(self.live_seat_indices()) > 1:
            while len(self.state.board) < 5:
                self.state.board.append(self.state.deck.pop())
            self._resolve_showdown()
            return

        self._action_queue = self._round_order(start_index=self._next_occupied_seat(self.state.button_index))
        self.state.actor_index = self._action_queue[0]

    def _award_uncontested(self, winner_index: int) -> None:
        rake_taken = self._rake_amount()
        payout = self.pot_size() - rake_taken
        self.state.seats[winner_index].stack += payout
        winner_name = self.state.seats[winner_index].name
        self.state.hand_result = HandResult(
            winners=[winner_index],
            pot_distribution={winner_index: payout},
            rake_taken=rake_taken,
            showdown_cards_revealed={},
            winning_hand_names={winner_index: "Uncontested"},
            summary=f"{winner_name} wins {format_bb(payout)} uncontested.",
        )
        self.state.street = Street.HAND_OVER
        self.state.actor_index = None
        self._action_queue = []

    def _resolve_showdown(self) -> None:
        live_players = [self.state.seats[index] for index in self.live_seat_indices()]
        hand_ranks = {
            seat.seat_index: best_rank([*seat.hole_cards, *self.state.board]) for seat in live_players
        }
        winning_names = {
            seat_index: hand_category_name(rank_tuple) for seat_index, rank_tuple in hand_ranks.items()
        }
        self._revealed_showdown_seats = {seat.seat_index for seat in live_players}

        payouts = {seat.seat_index: 0 for seat in live_players}
        rake_remaining = self._rake_amount()
        previous_level = 0

        levels = sorted({seat.contributed for seat in self.state.seats if seat.contributed > 0})
        for level in levels:
            contributors = [seat for seat in self.state.seats if seat.contributed >= level]
            if not contributors:
                continue
            eligible = [seat for seat in contributors if not seat.folded]
            if not eligible:
                previous_level = level
                continue

            pot_amount = (level - previous_level) * len(contributors)
            pot_rake = min(rake_remaining, pot_amount)
            pot_amount -= pot_rake
            rake_remaining -= pot_rake
            previous_level = level
            if pot_amount <= 0:
                continue

            best_hand = max(hand_ranks[seat.seat_index] for seat in eligible)
            winners = [seat.seat_index for seat in eligible if hand_ranks[seat.seat_index] == best_hand]
            share = pot_amount // len(winners)
            remainder = pot_amount % len(winners)
            for winner in winners:
                payouts[winner] = payouts.get(winner, 0) + share
            for winner in self._odd_chip_order(winners)[:remainder]:
                payouts[winner] = payouts.get(winner, 0) + 1

        for seat_index, amount in payouts.items():
            self.state.seats[seat_index].stack += amount

        actual_winners = [seat_index for seat_index, amount in payouts.items() if amount > 0]
        winner_names = ", ".join(self.state.seats[seat_index].name for seat_index in actual_winners)
        winner_hand_names = {
            seat_index: hand_category_name(hand_ranks[seat_index]) for seat_index in actual_winners
        }
        summary_verb = "wins" if len(actual_winners) == 1 else "win"
        self.state.hand_result = HandResult(
            winners=actual_winners,
            pot_distribution={seat: amount for seat, amount in payouts.items() if amount > 0},
            rake_taken=self._rake_amount(),
            showdown_cards_revealed={seat.seat_index: seat.hole_cards for seat in live_players},
            winning_hand_names=winner_hand_names,
            summary=f"{winner_names} {summary_verb} the pot.",
        )
        self.state.street = Street.HAND_OVER
        self.state.actor_index = None
        self._action_queue = []

    def _rake_amount(self) -> int:
        if len(self.state.board) < 3:
            return 0
        return min(self.pot_size() * 5 // 100, RAKE_CAP)

    def _big_blind_index(self) -> int:
        return self._next_occupied_seat(self._small_blind_index())

    def _small_blind_index(self) -> int:
        return self._next_occupied_seat(self.state.button_index)

    def _next_occupied_seat(self, seat_index: int) -> int:
        candidate = seat_index
        while True:
            candidate = (candidate + 1) % len(self.state.seats)
            if self.state.seats[candidate].stack >= 0:
                return candidate

    def _round_order(self, *, start_index: int, exclude_start: bool = False) -> list[int]:
        order = []
        candidate = start_index
        first_loop = True
        while first_loop or candidate != start_index:
            first_loop = False
            if not (exclude_start and candidate == start_index):
                seat = self.state.seats[candidate]
                if seat.can_act:
                    order.append(candidate)
            candidate = self._next_occupied_seat(candidate)
        return order

    def _odd_chip_order(self, winners: Iterable[int]) -> list[int]:
        winner_set = set(winners)
        order = []
        seat = self._next_occupied_seat(self.state.button_index)
        for _ in range(SEAT_COUNT):
            if seat in winner_set:
                order.append(seat)
            seat = self._next_occupied_seat(seat)
        return order


def bb_to_chips(big_blinds: float) -> int:
    return int(round(big_blinds * CHIP_SCALE))


def chips_to_bb(chips: int | None) -> float:
    if chips is None:
        return 0.0
    return round(chips / CHIP_SCALE, 2)


def format_bb(chips: int) -> str:
    value = chips_to_bb(chips)
    if value.is_integer():
        return f"{int(value)}bb"
    return f"{value:.2f}bb"
