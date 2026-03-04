"""Screenshot capture using mss."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import mss
import mss.tools
from PIL import Image

import structlog

from poker_agent.capture.window import WindowInfo

logger = structlog.get_logger()


class ScreenCapture:
    """Captures screenshots of the poker table region."""

    def __init__(self, retina_scale: int = 2, screenshot_dir: Optional[Path] = None):
        self.retina_scale = retina_scale
        self.screenshot_dir = screenshot_dir
        self._sct = mss.mss()

    def take_screenshot(self, window: WindowInfo) -> Image.Image:
        """Capture a screenshot of the specified window region.

        Returns a PIL Image at native Retina resolution (2x logical).
        """
        monitor = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }
        raw = self._sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img

    def take_full_screenshot(self) -> Image.Image:
        """Capture the full primary monitor."""
        monitor = self._sct.monitors[1]  # primary monitor
        raw = self._sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img

    def save_screenshot(self, img: Image.Image, filename: str) -> Optional[Path]:
        """Save a screenshot to the screenshot directory."""
        if self.screenshot_dir is None:
            return None
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshot_dir / filename
        img.save(str(path), "PNG")
        logger.debug("screenshot_saved", path=str(path))
        return path

    def resize_for_api(self, img: Image.Image, max_edge: int = 1568) -> Image.Image:
        """Resize an image so the longest edge is at most max_edge pixels.

        This reduces token usage when sending to the Vision API.
        """
        w, h = img.size
        if max(w, h) <= max_edge:
            return img
        scale = max_edge / max(w, h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    def close(self) -> None:
        """Clean up mss resources."""
        self._sct.close()
