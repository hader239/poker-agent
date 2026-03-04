"""Window manager for finding and focusing the Telegram desktop app."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class WindowInfo:
    """Information about a window's position and size in logical (non-Retina) coordinates."""

    left: int
    top: int
    width: int
    height: int
    title: str

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def region(self) -> tuple[int, int, int, int]:
        """Return (left, top, width, height) for mss capture.

        Note: mss on macOS uses logical coordinates (same as window position),
        but captures at native Retina resolution.
        """
        return (self.left, self.top, self.width, self.height)


class WindowManager:
    """Finds and manages the Telegram desktop app window on macOS."""

    def __init__(self, window_title: str = "Telegram"):
        self.window_title = window_title

    def find_window(self) -> Optional[WindowInfo]:
        """Find the Telegram window using AppleScript.

        Returns WindowInfo with logical (non-Retina) coordinates, or None if not found.
        """
        script = f"""
        tell application "System Events"
            set targetProcess to first process whose name contains "{self.window_title}"
            tell targetProcess
                set frontWindow to first window
                set windowPos to position of frontWindow
                set windowSize to size of frontWindow
                set windowTitle to name of frontWindow
                return (item 1 of windowPos as text) & "," & \\
                       (item 2 of windowPos as text) & "," & \\
                       (item 1 of windowSize as text) & "," & \\
                       (item 2 of windowSize as text) & "," & \\
                       windowTitle
            end tell
        end tell
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.warning("applescript_failed", stderr=result.stderr.strip())
                return None

            parts = result.stdout.strip().split(",", 4)
            if len(parts) < 4:
                logger.warning("unexpected_applescript_output", output=result.stdout.strip())
                return None

            return WindowInfo(
                left=int(parts[0]),
                top=int(parts[1]),
                width=int(parts[2]),
                height=int(parts[3]),
                title=parts[4] if len(parts) > 4 else self.window_title,
            )
        except subprocess.TimeoutExpired:
            logger.warning("applescript_timeout")
            return None
        except (ValueError, IndexError) as e:
            logger.warning("window_parse_error", error=str(e))
            return None

    def focus_window(self) -> bool:
        """Bring the Telegram window to the foreground."""
        script = f"""
        tell application "{self.window_title}"
            activate
        end tell
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("focus_timeout")
            return False
