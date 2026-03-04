"""Main agent orchestrator — the game loop and state machine."""

from __future__ import annotations

import asyncio
import signal
import time
from enum import Enum
from typing import Optional

import structlog

from poker_agent.capture import ChangeDetector, ScreenCapture, WindowManager
from poker_agent.config import AgentConfig
from poker_agent.executor import ActionExecutor
from poker_agent.logging import HandLogger, SessionLogger
from poker_agent.models.actions import ActionType
from poker_agent.models.game_state import GamePhase, GameState
from poker_agent.parser import ParseError, ScreenParser
from poker_agent.preflight import PreflightChecker
from poker_agent.strategy import create_strategy
from poker_agent.strategy.poker_math import enrich_game_state

logger = structlog.get_logger()


class AgentState(str, Enum):
    INITIALIZING = "initializing"
    FINDING_TABLE = "finding_table"
    WAITING_FOR_HAND = "waiting_for_hand"
    WAITING_FOR_TURN = "waiting_for_turn"
    ACTING = "acting"
    VERIFYING_ACTION = "verifying_action"
    ERROR_RECOVERY = "error_recovery"
    STOPPED = "stopped"


class PokerAgent:
    """The main poker agent that orchestrates the capture-parse-decide-act loop."""

    def __init__(self, config: AgentConfig, dry_run: bool = False):
        self.config = config
        self.state = AgentState.INITIALIZING
        self._running = False
        self._dry_run = dry_run

        # Components
        self.window_manager = WindowManager(config.telegram_window_title)
        self.capture = ScreenCapture(
            retina_scale=config.retina_scale,
            screenshot_dir=config.screenshot_dir if config.save_screenshots else None,
        )
        self.change_detector = ChangeDetector()
        self.parser = ScreenParser(config)
        self.strategy = create_strategy(config)
        self.executor = ActionExecutor(
            self.window_manager,
            retina_scale=config.retina_scale,
            action_delay_ms=config.action_delay_ms,
        )
        self.executor.dry_run = dry_run
        self.hand_logger = HandLogger(config.hand_history_dir)
        self.session_logger = SessionLogger(config.hand_history_dir)

        # State tracking
        self._current_hand_number: Optional[int] = None
        self._current_phase: Optional[str] = None
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5

    async def run(self) -> None:
        """Run the agent main loop."""
        logger.info("agent_starting", dry_run=self._dry_run)

        # Run preflight checks
        if not self._preflight():
            return

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

        self._running = True
        self.state = AgentState.FINDING_TABLE

        # Find the Telegram window
        window = self.window_manager.find_window()
        if window is None:
            logger.error("telegram_window_not_found")
            return

        logger.info(
            "window_found",
            title=window.title,
            position=(window.left, window.top),
            size=(window.width, window.height),
        )

        self.state = AgentState.WAITING_FOR_HAND
        poll_interval = self.config.poll_interval_ms / 1000

        while self._running:
            try:
                # Check stop conditions
                stop_reason = self.session_logger.check_stop_conditions(
                    max_hands=self.config.max_hands,
                    stop_loss_bb=self.config.stop_loss_bb,
                    max_cost_usd=self.config.max_api_cost_usd,
                )
                if stop_reason:
                    logger.info("stop_condition_met", reason=stop_reason)
                    break

                # Re-find window in case it moved
                window = self.window_manager.find_window()
                if window is None:
                    logger.warning("window_lost")
                    await asyncio.sleep(2.0)
                    continue

                # 1. CAPTURE
                screenshot = self.capture.take_screenshot(window)

                # 2. CHANGE DETECT
                if not self.change_detector.has_changed(screenshot):
                    await asyncio.sleep(poll_interval)
                    continue

                # 3. PARSE
                try:
                    api_screenshot = self.capture.resize_for_api(screenshot)
                    game_state = await self.parser.parse(api_screenshot)
                except ParseError as e:
                    logger.warning("parse_error", error=str(e))
                    self.session_logger.record_error("parse")
                    self._consecutive_errors += 1
                    if self._consecutive_errors >= self._max_consecutive_errors:
                        logger.error("too_many_consecutive_errors")
                        break
                    await asyncio.sleep(poll_interval)
                    continue

                # Reset error counter on successful parse
                self._consecutive_errors = 0

                # Low confidence — skip
                if game_state.parse_confidence < 0.6:
                    logger.warning(
                        "low_parse_confidence",
                        confidence=game_state.parse_confidence,
                    )
                    await asyncio.sleep(poll_interval)
                    continue

                # Enrich with computed fields
                game_state = enrich_game_state(game_state)

                # Track hand transitions
                self._handle_hand_transition(game_state)

                # Save screenshot if configured
                if self.config.save_screenshots:
                    ts = time.strftime("%H%M%S")
                    path = self.capture.save_screenshot(
                        screenshot, f"frame_{ts}.png"
                    )
                    if path:
                        self.hand_logger.add_screenshot(str(path))

                # Update hand logger with current state
                self.hand_logger.update_state(game_state)

                # 4. CHECK IF OUR TURN
                if not game_state.is_my_turn:
                    self.state = AgentState.WAITING_FOR_TURN
                    await asyncio.sleep(poll_interval)
                    continue

                # 5. DECIDE
                self.state = AgentState.ACTING
                action = await self.strategy.decide(game_state)
                self.hand_logger.log_action(game_state, action)

                logger.info(
                    "executing_action",
                    action=action.action_type.value,
                    amount=action.amount,
                    confidence=action.confidence,
                )

                # 6. EXECUTE
                success = await self.executor.execute(action, game_state, window)

                # 7. VERIFY
                self.state = AgentState.VERIFYING_ACTION
                if not success:
                    logger.warning("action_failed", action=action.action_type.value)
                    self.session_logger.record_error("action")

                    # Try fallback: check or fold
                    if action.action_type not in (ActionType.FOLD, ActionType.CHECK):
                        fallback = ActionType.CHECK
                        if (
                            game_state.available_actions
                            and game_state.available_actions.check is None
                        ):
                            fallback = ActionType.FOLD
                        logger.info("trying_fallback", fallback=fallback.value)

                # Wait for UI to update
                await asyncio.sleep(self.config.action_delay_ms / 1000)
                self.state = AgentState.WAITING_FOR_TURN

                # Force change detector to re-evaluate
                self.change_detector.reset()

            except Exception as e:
                logger.error("unexpected_error", error=str(e), exc_info=True)
                self.session_logger.record_error("unexpected")
                self._consecutive_errors += 1
                if self._consecutive_errors >= self._max_consecutive_errors:
                    logger.error("too_many_errors_stopping")
                    break
                await asyncio.sleep(1.0)

        # Shutdown
        self._shutdown()

    def _preflight(self) -> bool:
        """Run preflight checks. Returns True if all critical checks pass."""
        checker = PreflightChecker(self.config)
        results = checker.run_all_checks()

        all_passed = True
        for result in results:
            level = "info" if result.passed else "error"
            getattr(logger, level)(
                "preflight_check",
                name=result.name,
                passed=result.passed,
                message=result.message,
            )
            if not result.passed:
                all_passed = False

        return all_passed

    def _handle_hand_transition(self, game_state: GameState) -> None:
        """Detect when a new hand starts or the phase changes."""
        # New hand detection
        if (
            game_state.hand_number is not None
            and game_state.hand_number != self._current_hand_number
        ):
            # Complete previous hand if exists
            if self._current_hand_number is not None:
                hand = self.hand_logger.complete_hand(game_state)
                if hand and hand.net_result is not None:
                    self.session_logger.record_hand_result(
                        hand.net_result, hand.won_hand
                    )

            # Start new hand
            self._current_hand_number = game_state.hand_number
            self._current_phase = game_state.phase.value
            self.hand_logger.start_hand(game_state)
            asyncio.ensure_future(self.strategy.on_hand_start(game_state))

        # Phase change detection (within the same hand)
        elif (
            game_state.phase.value != self._current_phase
            and game_state.phase != GamePhase.UNKNOWN
        ):
            self._current_phase = game_state.phase.value
            asyncio.ensure_future(self.strategy.on_street_change(game_state))

    def _handle_shutdown(self) -> None:
        """Handle graceful shutdown signal."""
        logger.info("shutdown_signal_received")
        self._running = False

    def _shutdown(self) -> None:
        """Clean up resources and log session summary."""
        self.state = AgentState.STOPPED
        self.capture.close()

        # Record API usage from parser and strategy
        parser_stats = self.parser.stats
        self.session_logger.record_api_usage(
            parser_stats["api_calls"],
            parser_stats["total_input_tokens"],
            parser_stats["total_output_tokens"],
        )

        if hasattr(self.strategy, "stats"):
            strategy_stats = self.strategy.stats
            self.session_logger.record_api_usage(
                strategy_stats["api_calls"],
                strategy_stats["total_input_tokens"],
                strategy_stats["total_output_tokens"],
            )

        summary = self.session_logger.log_summary()
        logger.info("agent_stopped", **summary)
