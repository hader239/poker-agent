"""Action executor — translates abstract Actions into physical UI interactions."""

from __future__ import annotations

import asyncio
import random
from typing import Optional

import pyautogui

import structlog

from poker_agent.capture.window import WindowInfo, WindowManager
from poker_agent.executor.coordinates import CoordinateTranslator
from poker_agent.models.actions import Action, ActionType
from poker_agent.models.game_state import ButtonInfo, GameState

logger = structlog.get_logger()

# Disable pyautogui fail-safe (moving mouse to corner) during automated play.
# We handle our own safety via stop conditions.
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05  # Small pause between pyautogui actions


class ExecutionError(Exception):
    """Raised when action execution fails."""


class ActionExecutor:
    """Executes poker actions by controlling the mouse and keyboard."""

    def __init__(
        self,
        window_manager: WindowManager,
        retina_scale: int = 2,
        action_delay_ms: int = 500,
    ):
        self.window_manager = window_manager
        self.coords = CoordinateTranslator(retina_scale)
        self.action_delay_ms = action_delay_ms
        self._dry_run = False

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    @dry_run.setter
    def dry_run(self, value: bool) -> None:
        self._dry_run = value

    async def execute(
        self, action: Action, state: GameState, window: WindowInfo
    ) -> bool:
        """Execute an action on the poker UI.

        Args:
            action: The action to execute.
            state: Current game state (contains button positions).
            window: Window position info.

        Returns:
            True if the action was executed successfully.
        """
        if state.available_actions is None:
            logger.warning("no_available_actions")
            return False

        # Focus the Telegram window first
        self.window_manager.focus_window()
        await asyncio.sleep(0.15)

        aa = state.available_actions

        try:
            match action.action_type:
                case ActionType.FOLD:
                    return await self._click_button(aa.fold, window, "fold")
                case ActionType.CHECK:
                    return await self._click_button(aa.check, window, "check")
                case ActionType.CALL:
                    return await self._click_button(aa.call, window, "call")
                case ActionType.RAISE:
                    return await self._execute_raise(action.amount, state, window)
                case ActionType.ALL_IN:
                    return await self._click_button(aa.all_in, window, "all_in")
                case _:
                    logger.warning("unsupported_action", action=action.action_type.value)
                    return False
        except Exception as e:
            logger.error("execution_error", action=action.action_type.value, error=str(e))
            return False

    async def _click_button(
        self, button: Optional[ButtonInfo], window: WindowInfo, name: str
    ) -> bool:
        """Click a button on the UI."""
        if button is None or not button.is_visible:
            logger.warning("button_not_available", button=name)
            return False

        screen_x, screen_y = self.coords.image_to_screen(
            button.center_x, button.center_y, window
        )

        logger.info(
            "clicking_button",
            button=name,
            label=button.label,
            screen_x=screen_x,
            screen_y=screen_y,
        )

        if self._dry_run:
            logger.info("dry_run_click", x=screen_x, y=screen_y, button=name)
            return True

        pyautogui.click(screen_x, screen_y)
        await asyncio.sleep(self.action_delay_ms / 1000)
        return True

    async def _execute_raise(
        self, amount: Optional[float], state: GameState, window: WindowInfo
    ) -> bool:
        """Execute a raise action: click raise, type amount, confirm."""
        aa = state.available_actions
        if aa is None:
            return False

        # Step 1: Click the raise button to open the raise input
        if aa.raise_btn is None:
            logger.warning("raise_button_not_found")
            return False

        clicked = await self._click_button(aa.raise_btn, window, "raise")
        if not clicked:
            return False

        await asyncio.sleep(0.2)

        # Step 2: If we have a specific amount and an input field, type it
        if amount is not None and aa.raise_input is not None:
            screen_x, screen_y = self.coords.image_to_screen(
                aa.raise_input.center_x, aa.raise_input.center_y, window
            )

            logger.info("typing_raise_amount", amount=amount, x=screen_x, y=screen_y)

            if not self._dry_run:
                # Triple-click to select all existing text
                pyautogui.tripleClick(screen_x, screen_y)
                await asyncio.sleep(0.05)

                # Type the amount
                amount_str = str(int(amount))
                pyautogui.typewrite(amount_str, interval=0.02)
                await asyncio.sleep(0.1)

        # Step 3: Click the confirm button
        if aa.raise_confirm is not None:
            return await self._click_button(aa.raise_confirm, window, "raise_confirm")

        # If no confirm button, the raise button itself might have submitted
        return True

    async def click_with_retry(
        self,
        button: ButtonInfo,
        window: WindowInfo,
        name: str,
        max_retries: int = 2,
        jitter_px: int = 5,
    ) -> bool:
        """Click a button with retries and coordinate jitter."""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                # Add random jitter to coordinates
                jittered = ButtonInfo(
                    label=button.label,
                    center_x=button.center_x + random.randint(-jitter_px, jitter_px),
                    center_y=button.center_y + random.randint(-jitter_px, jitter_px),
                    is_visible=button.is_visible,
                    is_enabled=button.is_enabled,
                )
                logger.info("retrying_click", attempt=attempt, button=name)
                success = await self._click_button(jittered, window, name)
            else:
                success = await self._click_button(button, window, name)

            if success:
                return True
            await asyncio.sleep(0.3)

        return False
