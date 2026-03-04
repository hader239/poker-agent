"""Screen capture and window management."""

from poker_agent.capture.capture import ScreenCapture
from poker_agent.capture.change_detect import ChangeDetector
from poker_agent.capture.window import WindowInfo, WindowManager

__all__ = ["ChangeDetector", "ScreenCapture", "WindowInfo", "WindowManager"]
