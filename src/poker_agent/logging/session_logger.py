"""Session-level statistics and logging."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class SessionStats:
    """Accumulated statistics for a poker session."""

    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    hands_played: int = 0
    hands_won: int = 0
    hands_lost: int = 0

    total_net_result: float = 0.0
    biggest_win: float = 0.0
    biggest_loss: float = 0.0

    total_api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    errors_count: int = 0
    parse_failures: int = 0
    action_failures: int = 0

    @property
    def win_rate(self) -> float:
        if self.hands_played == 0:
            return 0.0
        return self.hands_won / self.hands_played

    @property
    def bb_per_hand(self) -> Optional[float]:
        if self.hands_played == 0:
            return None
        return self.total_net_result / self.hands_played

    @property
    def duration_minutes(self) -> float:
        end = self.end_time or time.time()
        return (end - self.start_time) / 60


class SessionLogger:
    """Tracks and logs session-level statistics."""

    def __init__(self, hand_history_dir: Path):
        self.stats = SessionStats()
        self._log_dir = hand_history_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def record_hand_result(self, net_result: float, won: Optional[bool]) -> None:
        """Record the result of a completed hand."""
        self.stats.hands_played += 1
        self.stats.total_net_result += net_result

        if won is True:
            self.stats.hands_won += 1
        elif won is False:
            self.stats.hands_lost += 1

        if net_result > self.stats.biggest_win:
            self.stats.biggest_win = net_result
        if net_result < self.stats.biggest_loss:
            self.stats.biggest_loss = net_result

    def record_api_usage(
        self, calls: int, input_tokens: int, output_tokens: int
    ) -> None:
        """Record API usage from parser or strategy engine."""
        self.stats.total_api_calls += calls
        self.stats.total_input_tokens += input_tokens
        self.stats.total_output_tokens += output_tokens

        # Rough cost estimate (Sonnet pricing)
        input_cost = input_tokens * 3.0 / 1_000_000
        output_cost = output_tokens * 15.0 / 1_000_000
        self.stats.estimated_cost_usd += input_cost + output_cost

    def record_error(self, error_type: str) -> None:
        """Record an error occurrence."""
        self.stats.errors_count += 1
        if error_type == "parse":
            self.stats.parse_failures += 1
        elif error_type == "action":
            self.stats.action_failures += 1

    def log_summary(self) -> dict:
        """Log and return a summary of the session."""
        self.stats.end_time = time.time()
        summary = {
            "duration_minutes": round(self.stats.duration_minutes, 1),
            "hands_played": self.stats.hands_played,
            "hands_won": self.stats.hands_won,
            "win_rate": f"{self.stats.win_rate:.1%}",
            "total_net_result": round(self.stats.total_net_result, 2),
            "bb_per_hand": (
                round(self.stats.bb_per_hand, 2)
                if self.stats.bb_per_hand is not None
                else None
            ),
            "biggest_win": round(self.stats.biggest_win, 2),
            "biggest_loss": round(self.stats.biggest_loss, 2),
            "api_calls": self.stats.total_api_calls,
            "estimated_cost_usd": round(self.stats.estimated_cost_usd, 4),
            "errors": self.stats.errors_count,
        }

        logger.info("session_summary", **summary)

        # Save to file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        summary_path = self._log_dir / f"session_{timestamp}.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        return summary

    def check_stop_conditions(
        self,
        max_hands: Optional[int],
        stop_loss_bb: Optional[int],
        max_cost_usd: Optional[float],
    ) -> Optional[str]:
        """Check if any stop condition has been met.

        Returns the reason string if a stop condition is met, None otherwise.
        """
        if max_hands and self.stats.hands_played >= max_hands:
            return f"Max hands reached ({max_hands})"

        if stop_loss_bb and self.stats.total_net_result <= -stop_loss_bb:
            return f"Stop loss reached ({stop_loss_bb} BB)"

        if max_cost_usd and self.stats.estimated_cost_usd >= max_cost_usd:
            return f"Max API cost reached (${max_cost_usd})"

        return None
