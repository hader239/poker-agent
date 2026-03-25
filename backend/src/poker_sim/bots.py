"""Bot policies for the local poker simulator."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from poker_sim.cards import Card, analyze_draws, best_rank, estimate_equity, hand_key
from poker_sim.engine import ActionType, PlayerAction, Street, bb_to_chips


def _combo_set(items: str) -> set[str]:
    return set(items.split())


OPEN_RANGES_DEEP = {
    "UTG": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s "
        "KQs KJs KTs QJs QTs JTs T9s 98s 87s "
        "AKo AQo AJo KQo"
    ),
    "HJ": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s "
        "KQs KJs KTs K9s QJs QTs Q9s JTs J9s T9s T8s 98s 97s 87s 76s "
        "AKo AQo AJo ATo KQo KJo QJo"
    ),
    "CO": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s "
        "KQs KJs KTs K9s K8s K7s K6s K5s "
        "QJs QTs Q9s Q8s JTs J9s J8s T9s T8s 98s 97s 96s 87s 86s 76s 75s 65s 54s "
        "AKo AQo AJo ATo A9o KQo KJo KTo QJo QTo JTo"
    ),
    "BTN": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s "
        "KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s "
        "QJs QTs Q9s Q8s Q7s Q6s Q5s JTs J9s J8s J7s J6s "
        "T9s T8s T7s T6s 98s 97s 96s 95s 87s 86s 85s 76s 75s 74s 65s 64s 54s 53s "
        "AKo AQo AJo ATo A9o A8o A7o A6o A5o A4o A3o A2o "
        "KQo KJo KTo K9o K8o QJo QTo Q9o JTo J9o T9o 98o"
    ),
    "SB": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s "
        "KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s "
        "QJs QTs Q9s Q8s Q7s Q6s Q5s JTs J9s J8s J7s J6s "
        "T9s T8s T7s T6s 98s 97s 96s 87s 86s 76s 75s 65s 64s 54s "
        "AKo AQo AJo ATo A9o A8o A7o A6o A5o A4o A3o A2o "
        "KQo KJo KTo K9o K8o QJo QTo Q9o JTo J9o T9o"
    ),
}

OPEN_RANGES_SHORT = {
    "UTG": _combo_set("AA KK QQ JJ TT 99 88 77 66 55 AKo AKs AQs AQo AJs KQs"),
    "HJ": _combo_set("AA KK QQ JJ TT 99 88 77 66 55 44 AKo AKs AQs AQo AJs ATs KQs KJs"),
    "CO": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKo AKs AQo AQs AJo AJs ATo ATs A9s KQo KQs KJs QJs JTs"
    ),
    "BTN": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKo AKs AQo AQs AJo AJs ATo ATs A9o A9s A8s A7s "
        "KQo KQs KJo KJs KTs QJo QJs QTs JTs T9s 98s"
    ),
    "SB": _combo_set(
        "AA KK QQ JJ TT 99 88 77 66 55 44 33 22 "
        "AKo AKs AQo AQs AJo AJs ATo ATs A9o A9s A8o A8s A7s "
        "KQo KQs KJo KJs KTs QJo QJs QTs JTs T9s 98s"
    ),
}

THREE_BET_VALUE = _combo_set("AA KK QQ JJ TT AKs AKo AQs AQo")
THREE_BET_LINEAR = _combo_set("99 88 AJs ATs KQs KJs QJs JTs AJo KQo")
CALL_IP = _combo_set(
    "99 88 77 66 55 44 33 22 "
    "AQs AJs ATs A9s A8s A7s A6s A5s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s "
    "AQo AJo KQo"
)
CALL_OOP = _combo_set("QQ JJ TT 99 88 77 AQs AJs ATs KQs KJs QJs JTs AQo")
FOUR_BET_VALUE = _combo_set("AA KK QQ AKs AKo")
JAM_SHORT = _combo_set(
    "AA KK QQ JJ TT 99 88 77 66 "
    "AKs AQs AJs AKo AQo AJo KQs"
)


@dataclass(frozen=True)
class BotStyle:
    name: str
    looseness: float
    aggression: float
    bluffiness: float
    thin_value: float
    sizing_bias: float


DEFAULT_STYLES = [
    BotStyle("solid", looseness=0.00, aggression=0.05, bluffiness=0.04, thin_value=0.08, sizing_bias=0.00),
    BotStyle("pressing", looseness=0.03, aggression=0.12, bluffiness=0.10, thin_value=0.10, sizing_bias=0.08),
    BotStyle("sticky", looseness=0.05, aggression=-0.02, bluffiness=0.03, thin_value=0.04, sizing_bias=-0.05),
    BotStyle("sharp", looseness=-0.02, aggression=0.10, bluffiness=0.07, thin_value=0.08, sizing_bias=0.03),
    BotStyle("active", looseness=0.04, aggression=0.08, bluffiness=0.08, thin_value=0.06, sizing_bias=0.04),
]


class StrongHeuristicBot:
    """A strong baseline bot built from seeded ranges and board heuristics."""

    def __init__(self, style: BotStyle) -> None:
        self.style = style

    def choose_action(self, snapshot: dict[str, object], *, rng: Random) -> PlayerAction:
        street = snapshot["street"]
        if street == Street.PREFLOP.value:
            return self._choose_preflop(snapshot, rng=rng)
        return self._choose_postflop(snapshot, rng=rng)

    def _choose_preflop(self, snapshot: dict[str, object], *, rng: Random) -> PlayerAction:
        legal = snapshot["legal_actions"] or {}
        hero_seat = snapshot["viewer_seat_index"]
        seat_info = next(item for item in snapshot["seats"] if item["seat_index"] == hero_seat)
        hole_cards = [Card.from_code(code) for code in seat_info["cards"]]
        position = seat_info["position"]
        hand = hand_key(*hole_cards)
        call_amount = legal.get("call_amount_bb", 0.0) or 0.0
        min_raise = legal.get("min_raise_to_bb")
        max_raise = legal.get("max_raise_to_bb")
        effective_stack = min(
            seat_info["stack_bb"] + seat_info["committed_bb"],
            max(
                other["stack_bb"] + other["committed_bb"]
                for other in snapshot["seats"]
                if not other["folded"] and other["seat_index"] != hero_seat
            ),
        )

        preflop_actions = [item for item in snapshot["action_history"] if item["street"] == Street.PREFLOP.value]
        raises = [item for item in preflop_actions if item["action_type"] in {ActionType.RAISE_TO.value, ActionType.ALL_IN.value}]
        limpers = [
            item
            for item in preflop_actions
            if item["action_type"] == ActionType.CALL.value and item["amount_bb"] is None
        ]

        open_range = self._open_range(position, effective_stack)
        range_roll = rng.random()
        if hand not in open_range and range_roll < self.style.looseness:
            open_range = open_range | self._borderline_open_range(position)

        if not raises and not limpers:
            if position == "BB" and call_amount == 0:
                return PlayerAction(ActionType.CHECK)
            if hand in open_range and min_raise is not None and max_raise is not None:
                open_size = self._open_size(position)
                return PlayerAction(ActionType.RAISE_TO, amount=_clamp_raise(open_size, min_raise, max_raise))
            return _passive_action(legal)

        if not raises and limpers:
            if hand in open_range and min_raise is not None and max_raise is not None:
                iso_size = 3.5 + len(limpers) * 1.0 + self.style.sizing_bias
                return PlayerAction(ActionType.RAISE_TO, amount=_clamp_raise(iso_size, min_raise, max_raise))
            if call_amount == 0 and legal.get("can_check"):
                return PlayerAction(ActionType.CHECK)
            if hand in CALL_IP or hand in CALL_OOP:
                return PlayerAction(ActionType.CALL)
            return PlayerAction(ActionType.FOLD)

        if raises:
            opener_position = self._seat_position(snapshot, raises[0]["seat_index"])
            in_position = _is_in_position(position, opener_position)
            if effective_stack <= 18 and hand in JAM_SHORT:
                return PlayerAction(ActionType.ALL_IN)

            if hand in FOUR_BET_VALUE and len(raises) >= 2:
                if min_raise is None or max_raise is None:
                    return PlayerAction(ActionType.ALL_IN)
                target = max(min_raise, (raises[-1]["amount_bb"] or 0) * 2.2)
                return PlayerAction(ActionType.RAISE_TO, amount=_clamp_raise(target, min_raise, max_raise))

            if hand in THREE_BET_VALUE or (hand in THREE_BET_LINEAR and (in_position or self.style.aggression > 0)):
                if min_raise is not None and max_raise is not None:
                    target = self._three_bet_size(raises[0]["amount_bb"] or 2.5, in_position=in_position)
                    return PlayerAction(ActionType.RAISE_TO, amount=_clamp_raise(target, min_raise, max_raise))

            call_range = CALL_IP if in_position else CALL_OOP
            if hand in call_range and call_amount <= max(5.5, effective_stack * 0.18):
                return PlayerAction(ActionType.CALL)

        if legal.get("can_check"):
            return PlayerAction(ActionType.CHECK)
        return PlayerAction(ActionType.FOLD)

    def _choose_postflop(self, snapshot: dict[str, object], *, rng: Random) -> PlayerAction:
        legal = snapshot["legal_actions"] or {}
        viewer_seat = snapshot["viewer_seat_index"]
        seat_info = next(item for item in snapshot["seats"] if item["seat_index"] == viewer_seat)
        hole_cards = [Card.from_code(code) for code in seat_info["cards"]]
        board_cards = [Card.from_code(code) for code in snapshot["board"]]
        live_opponents = [seat for seat in snapshot["seats"] if seat["seat_index"] != viewer_seat and not seat["folded"]]
        opponent_count = len(live_opponents)

        made_rank = best_rank([*hole_cards, *board_cards])
        category = made_rank[0]
        draws = analyze_draws(hole_cards, board_cards)
        equity = estimate_equity(hole_cards, board_cards, opponent_count=max(1, opponent_count), rng=rng, samples=120)
        pot = snapshot["pot_bb"]
        call_amount = legal.get("call_amount_bb", 0.0) or 0.0
        pot_odds = (call_amount / (pot + call_amount)) if call_amount > 0 else 0.0
        position = seat_info["position"]
        initiative = snapshot.get("initiative_seat") == viewer_seat
        made_tier = _made_hand_tier(hole_cards, board_cards, made_rank)
        board_texture = _board_texture(board_cards)

        if call_amount == 0:
            if legal.get("can_check") and not legal.get("min_raise_to_bb"):
                return PlayerAction(ActionType.CHECK)
            if made_tier in {"monster", "strong"}:
                return _bet_action(legal, _choose_bet_size_bb(pot, board_texture, self.style, value_heavy=True))
            if made_tier == "medium" and (initiative or position in {"BTN", "CO"}):
                if rng.random() < 0.65 + self.style.thin_value:
                    return _bet_action(legal, _choose_bet_size_bb(pot, board_texture, self.style, value_heavy=False))
            if draws["flush_draw"] or draws["open_ended"]:
                if rng.random() < 0.50 + self.style.bluffiness:
                    return _bet_action(legal, _choose_bet_size_bb(pot, board_texture, self.style, value_heavy=False))
            return PlayerAction(ActionType.CHECK)

        if made_tier == "monster":
            if legal.get("min_raise_to_bb") is not None and rng.random() < 0.55 + self.style.aggression:
                return _raise_action(
                    legal,
                    _choose_raise_to_bb(
                        current_bet=snapshot["current_bet_bb"],
                        pot=pot,
                        style=self.style,
                        pressure=True,
                    ),
                )
            return PlayerAction(ActionType.CALL)

        if made_tier == "strong":
            if legal.get("min_raise_to_bb") is not None and opponent_count <= 2 and rng.random() < 0.25 + self.style.aggression:
                return _raise_action(
                    legal,
                    _choose_raise_to_bb(
                        current_bet=snapshot["current_bet_bb"],
                        pot=pot,
                        style=self.style,
                        pressure=False,
                    ),
                )
            if equity >= pot_odds + 0.06:
                return PlayerAction(ActionType.CALL)
            return PlayerAction(ActionType.FOLD)

        if draws["flush_draw"] or draws["open_ended"]:
            if legal.get("min_raise_to_bb") is not None and rng.random() < 0.18 + self.style.bluffiness:
                return _raise_action(
                    legal,
                    _choose_raise_to_bb(
                        current_bet=snapshot["current_bet_bb"],
                        pot=pot,
                        style=self.style,
                        pressure=False,
                    ),
                )
            if equity >= pot_odds - 0.02:
                return PlayerAction(ActionType.CALL)
            return PlayerAction(ActionType.FOLD)

        if made_tier == "medium" and equity >= pot_odds + 0.02:
            return PlayerAction(ActionType.CALL)

        if legal.get("can_check"):
            return PlayerAction(ActionType.CHECK)
        return PlayerAction(ActionType.FOLD)

    def _open_range(self, position: str, effective_stack: float) -> set[str]:
        if effective_stack <= 20:
            return OPEN_RANGES_SHORT.get(position, set())
        return OPEN_RANGES_DEEP.get(position, set())

    def _borderline_open_range(self, position: str) -> set[str]:
        return {
            "UTG": _combo_set("KJo QJo"),
            "HJ": _combo_set("KTo QTo JTo 65s"),
            "CO": _combo_set("A8o K9o Q9o J9o"),
            "BTN": _combo_set("K7o Q8o J8o 87o"),
            "SB": _combo_set("K7o Q8o J8o T8o"),
        }.get(position, set())

    def _open_size(self, position: str) -> float:
        baseline = {"UTG": 2.4, "HJ": 2.4, "CO": 2.3, "BTN": 2.25, "SB": 3.0}.get(position, 2.4)
        return baseline + self.style.sizing_bias

    def _three_bet_size(self, open_size: float, *, in_position: bool) -> float:
        factor = 3.0 if in_position else 4.0
        return max(open_size * factor, open_size + 3.0 + self.style.sizing_bias)

    def _seat_position(self, snapshot: dict[str, object], seat_index: int) -> str:
        for seat in snapshot["seats"]:
            if seat["seat_index"] == seat_index:
                return seat["position"]
        return "Unknown"


class RandomBot:
    """Weak baseline bot for validation."""

    def choose_action(self, snapshot: dict[str, object], *, rng: Random) -> PlayerAction:
        legal = snapshot["legal_actions"] or {}
        options = []
        if legal.get("can_fold"):
            options.append(PlayerAction(ActionType.FOLD))
        if legal.get("can_check"):
            options.append(PlayerAction(ActionType.CHECK))
        if (legal.get("call_amount_bb", 0.0) or 0.0) > 0:
            options.append(PlayerAction(ActionType.CALL))
        if legal.get("min_raise_to_bb") is not None and legal.get("max_raise_to_bb") is not None:
            lower = legal["min_raise_to_bb"]
            upper = legal["max_raise_to_bb"]
            mid = (lower + upper) / 2
            options.append(PlayerAction(ActionType.RAISE_TO, bb_to_chips(mid)))
        if not options:
            return PlayerAction(ActionType.CHECK)
        return rng.choice(options)


def default_bot_style_for_seat(seat_index: int) -> BotStyle:
    return DEFAULT_STYLES[(seat_index - 1) % len(DEFAULT_STYLES)]


def _passive_action(legal: dict[str, object]) -> PlayerAction:
    if legal.get("can_check"):
        return PlayerAction(ActionType.CHECK)
    if (legal.get("call_amount_bb", 0.0) or 0.0) > 0:
        return PlayerAction(ActionType.FOLD)
    return PlayerAction(ActionType.CHECK)


def _clamp_raise(target_bb: float, min_raise_to_bb: float | None, max_raise_to_bb: float | None) -> int:
    if min_raise_to_bb is None or max_raise_to_bb is None:
        return bb_to_chips(target_bb)
    target = max(min_raise_to_bb, min(max_raise_to_bb, target_bb))
    return bb_to_chips(target)


def _bet_action(legal: dict[str, object], target_bb: float) -> PlayerAction:
    min_raise = legal.get("min_raise_to_bb")
    max_raise = legal.get("max_raise_to_bb")
    if min_raise is None or max_raise is None:
        return PlayerAction(ActionType.CHECK)
    return PlayerAction(ActionType.BET, amount=_clamp_raise(target_bb, min_raise, max_raise))


def _raise_action(legal: dict[str, object], target_bb: float) -> PlayerAction:
    min_raise = legal.get("min_raise_to_bb")
    max_raise = legal.get("max_raise_to_bb")
    if min_raise is None or max_raise is None:
        return PlayerAction(ActionType.CALL)
    return PlayerAction(ActionType.RAISE_TO, amount=_clamp_raise(target_bb, min_raise, max_raise))


def _choose_bet_size_bb(pot: float, board_texture: str, style: BotStyle, *, value_heavy: bool) -> float:
    if value_heavy:
        base = 0.70 if board_texture == "wet" else 0.55
    else:
        base = 0.55 if board_texture == "wet" else 0.40
    return max(1.0, pot * (base + style.sizing_bias))


def _choose_raise_to_bb(current_bet: float, pot: float, style: BotStyle, *, pressure: bool) -> float:
    factor = 3.2 if pressure else 2.6
    size = max(current_bet * factor, current_bet + pot * (0.65 + style.sizing_bias))
    return size


def _made_hand_tier(hole_cards: list[Card], board_cards: list[Card], rank_tuple: tuple[int, ...]) -> str:
    category = rank_tuple[0]
    if category >= 4:
        return "monster"
    if category in {2, 3}:
        return "strong"
    if category == 1:
        board_high = max(card.rank for card in board_cards)
        hole_ranks = sorted((card.rank for card in hole_cards), reverse=True)
        pair_rank = rank_tuple[1]
        if hole_ranks[0] == hole_ranks[1] and hole_ranks[0] > board_high:
            return "strong"
        if pair_rank == board_high and board_high in hole_ranks:
            return "medium" if hole_ranks[0] >= 11 or hole_ranks[1] >= 11 else "marginal"
        return "marginal"
    return "air"


def _board_texture(board_cards: list[Card]) -> str:
    if len(board_cards) < 3:
        return "dry"
    suits = {}
    for card in board_cards:
        suits[card.suit] = suits.get(card.suit, 0) + 1
    suited = max(suits.values())
    ranks = sorted(card.rank for card in board_cards)
    connected = sum(1 for first, second in zip(ranks, ranks[1:]) if second - first <= 2)
    if suited >= 2 and connected >= 2:
        return "wet"
    return "dry"


def _is_in_position(hero_position: str, opener_position: str) -> bool:
    order = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
    try:
        return order.index(hero_position) > order.index(opener_position)
    except ValueError:
        return False
