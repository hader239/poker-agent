"""Card helpers, hand evaluation, and simple Monte Carlo equity estimation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from random import Random
from typing import Iterable, Sequence

RANK_CHARS = "23456789TJQKA"
SUITS = "cdhs"


@dataclass(frozen=True, order=True)
class Card:
    rank: int
    suit: str

    def __post_init__(self) -> None:
        if self.rank < 2 or self.rank > 14:
            raise ValueError(f"invalid rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"invalid suit: {self.suit}")

    @classmethod
    def from_code(cls, code: str) -> Card:
        if len(code) != 2:
            raise ValueError(f"invalid card code: {code}")
        return cls(rank=RANK_CHARS.index(code[0].upper()) + 2, suit=code[1].lower())

    @property
    def code(self) -> str:
        return f"{RANK_CHARS[self.rank - 2]}{self.suit}"


def full_deck() -> list[Card]:
    return [Card(rank=rank, suit=suit) for rank in range(2, 15) for suit in SUITS]


def hand_key(card_a: Card, card_b: Card) -> str:
    """Return a canonical 169-hand key such as AKo, QJs, or 77."""

    high, low = sorted((card_a, card_b), reverse=True)
    high_rank = RANK_CHARS[high.rank - 2]
    low_rank = RANK_CHARS[low.rank - 2]
    if high.rank == low.rank:
        return f"{high_rank}{low_rank}"
    suited = "s" if high.suit == low.suit else "o"
    return f"{high_rank}{low_rank}{suited}"


def best_rank(cards: Sequence[Card]) -> tuple[int, ...]:
    """Return a lexicographically comparable rank tuple for 5-7 cards."""

    if len(cards) < 5 or len(cards) > 7:
        raise ValueError("best_rank expects 5 to 7 cards")
    return max(_rank_five(combo) for combo in combinations(cards, 5))


def hand_category_name(rank_tuple: Sequence[int]) -> str:
    category = rank_tuple[0]
    return {
        8: "Straight Flush",
        7: "Four of a Kind",
        6: "Full House",
        5: "Flush",
        4: "Straight",
        3: "Three of a Kind",
        2: "Two Pair",
        1: "One Pair",
        0: "High Card",
    }[category]


def estimate_equity(
    hero_cards: Sequence[Card],
    board_cards: Sequence[Card],
    opponent_count: int,
    *,
    rng: Random,
    samples: int = 180,
) -> float:
    """Estimate showdown equity versus random remaining hands.

    This is intentionally simple: it uses uniformly random unknown hole cards.
    The bot policy layers strategic heuristics on top of this raw estimate.
    """

    if opponent_count <= 0:
        return 1.0

    dead_cards = set(hero_cards) | set(board_cards)
    base_deck = [card for card in full_deck() if card not in dead_cards]

    wins = 0.0
    for _ in range(samples):
        deck = base_deck[:]
        rng.shuffle(deck)

        opponents = []
        offset = 0
        for _opponent in range(opponent_count):
            opponents.append(deck[offset : offset + 2])
            offset += 2

        runout = list(board_cards)
        while len(runout) < 5:
            runout.append(deck[offset])
            offset += 1

        hero_rank = best_rank([*hero_cards, *runout])
        contender_ranks = [best_rank([*opponent_cards, *runout]) for opponent_cards in opponents]
        all_ranks = [hero_rank, *contender_ranks]
        best_hand = max(all_ranks)
        winner_count = sum(1 for rank in all_ranks if rank == best_hand)
        if hero_rank == best_hand:
            wins += 1.0 / winner_count

    return wins / samples


def analyze_draws(hole_cards: Sequence[Card], board_cards: Sequence[Card]) -> dict[str, bool]:
    """Return simple draw flags used by the heuristic bot."""

    cards = [*hole_cards, *board_cards]
    suit_counts: dict[str, int] = {}
    for card in cards:
        suit_counts[card.suit] = suit_counts.get(card.suit, 0) + 1

    flush_draw = any(count == 4 for count in suit_counts.values()) and len(board_cards) < 5

    ranks = {card.rank for card in cards}
    if 14 in ranks:
        ranks.add(1)
    ordered = sorted(ranks)

    open_ended = False
    gutshot = False
    for start in range(1, 11):
        window = set(range(start, start + 5))
        overlap = len(window & set(ordered))
        if overlap >= 4:
            if (start in ranks and start + 4 in ranks) or (
                start + 1 in ranks and start + 3 in ranks
            ):
                open_ended = True
            else:
                gutshot = True

    return {
        "flush_draw": flush_draw,
        "open_ended": open_ended,
        "gutshot": gutshot,
    }


def _rank_five(cards: Sequence[Card]) -> tuple[int, ...]:
    ranks = sorted((card.rank for card in cards), reverse=True)
    counts: dict[int, int] = {}
    for rank in ranks:
        counts[rank] = counts.get(rank, 0) + 1

    ordered_groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    is_flush = len({card.suit for card in cards}) == 1
    straight_high = _straight_high(ranks)

    if is_flush and straight_high is not None:
        return (8, straight_high)

    if ordered_groups[0][1] == 4:
        quad_rank = ordered_groups[0][0]
        kicker = max(rank for rank in ranks if rank != quad_rank)
        return (7, quad_rank, kicker)

    if ordered_groups[0][1] == 3 and ordered_groups[1][1] == 2:
        return (6, ordered_groups[0][0], ordered_groups[1][0])

    if is_flush:
        return (5, *ranks)

    if straight_high is not None:
        return (4, straight_high)

    if ordered_groups[0][1] == 3:
        trip_rank = ordered_groups[0][0]
        kickers = sorted((rank for rank in ranks if rank != trip_rank), reverse=True)
        return (3, trip_rank, *kickers)

    pairs = [rank for rank, count in ordered_groups if count == 2]
    if len(pairs) >= 2:
        high_pair, low_pair = sorted(pairs, reverse=True)[:2]
        kicker = max(rank for rank in ranks if rank not in (high_pair, low_pair))
        return (2, high_pair, low_pair, kicker)

    if len(pairs) == 1:
        pair_rank = pairs[0]
        kickers = sorted((rank for rank in ranks if rank != pair_rank), reverse=True)
        return (1, pair_rank, *kickers)

    return (0, *ranks)


def _straight_high(ranks: Sequence[int]) -> int | None:
    unique_ranks = set(ranks)
    if 14 in unique_ranks:
        unique_ranks.add(1)
    ordered = sorted(unique_ranks)

    run = 1
    best = None
    for index in range(1, len(ordered)):
        if ordered[index] == ordered[index - 1] + 1:
            run += 1
            if run >= 5:
                best = ordered[index]
        else:
            run = 1
    return best
