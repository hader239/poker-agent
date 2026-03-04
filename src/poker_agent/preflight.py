"""Preflight checks to verify the system is ready to run."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

from poker_agent.config import AgentConfig

logger = structlog.get_logger()


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str


class PreflightChecker:
    """Runs startup checks to verify the system is properly configured."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def run_all_checks(self) -> list[CheckResult]:
        """Run all preflight checks and return results."""
        checks = [
            self._check_api_key(),
            self._check_telegram_running(),
            self._check_directories(),
            self._check_screen_recording_hint(),
        ]
        return checks

    def _check_api_key(self) -> CheckResult:
        """Check that the Anthropic API key is set."""
        key = self.config.anthropic_api_key.get_secret_value()
        if not key or key == "sk-ant-...":
            return CheckResult(
                name="API Key",
                passed=False,
                message="POKER_ANTHROPIC_API_KEY is not set or is the placeholder value.",
            )
        return CheckResult(
            name="API Key", passed=True, message="API key is configured."
        )

    def _check_telegram_running(self) -> CheckResult:
        """Check if Telegram desktop app is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-x", "Telegram"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return CheckResult(
                    name="Telegram", passed=True, message="Telegram is running."
                )
            return CheckResult(
                name="Telegram",
                passed=False,
                message="Telegram desktop app is not running. Please start it.",
            )
        except Exception as e:
            return CheckResult(
                name="Telegram",
                passed=False,
                message=f"Could not check Telegram status: {e}",
            )

    def _check_directories(self) -> CheckResult:
        """Check that output directories can be created."""
        try:
            self.config.hand_history_dir.mkdir(parents=True, exist_ok=True)
            if self.config.save_screenshots:
                self.config.screenshot_dir.mkdir(parents=True, exist_ok=True)
            return CheckResult(
                name="Directories",
                passed=True,
                message="Output directories are ready.",
            )
        except OSError as e:
            return CheckResult(
                name="Directories",
                passed=False,
                message=f"Cannot create output directories: {e}",
            )

    def _check_screen_recording_hint(self) -> CheckResult:
        """Remind about screen recording permission (can't programmatically check)."""
        return CheckResult(
            name="Screen Recording",
            passed=True,
            message=(
                "Ensure Screen Recording permission is granted to your terminal "
                "in System Preferences > Privacy & Security > Screen Recording. "
                "Also grant Accessibility permission for keyboard/mouse control."
            ),
        )
