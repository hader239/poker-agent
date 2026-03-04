"""Configuration model for the poker agent."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POKER_", env_file=".env")

    # API
    anthropic_api_key: SecretStr
    parser_model: str = "claude-sonnet-4-5-20250514"
    decision_model: str = "claude-sonnet-4-5-20250514"

    # Window targeting
    telegram_window_title: str = "Telegram"

    # Timing
    poll_interval_ms: int = 300
    action_delay_ms: int = 500
    turn_timeout_s: int = 30

    # Display
    retina_scale: int = 2

    # Strategy
    strategy_type: Literal["llm", "gto"] = "llm"
    play_style: str = "tight-aggressive"

    # Table
    buy_in_bb: int = 100
    auto_rebuy: bool = True
    auto_rebuy_threshold_bb: int = 30

    # Logging
    log_level: str = "INFO"
    hand_history_dir: Path = Path("./hand_history")
    screenshot_dir: Path = Path("./screenshots")
    save_screenshots: bool = True

    # Safety
    max_hands: Optional[int] = None
    stop_loss_bb: Optional[int] = None
    max_api_cost_usd: Optional[float] = None
