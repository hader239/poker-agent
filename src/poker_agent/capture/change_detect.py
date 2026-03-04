"""Perceptual hash change detection to avoid redundant API calls."""

from __future__ import annotations

from typing import Optional

import imagehash
from PIL import Image

import structlog

logger = structlog.get_logger()


class ChangeDetector:
    """Detects whether the screen has changed enough to warrant a new API call."""

    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self._last_hash: Optional[imagehash.ImageHash] = None

    def has_changed(self, screenshot: Image.Image) -> bool:
        """Check if the screenshot differs significantly from the last one.

        Uses perceptual hashing (pHash) to compare images.
        Returns True if changed or if this is the first screenshot.
        """
        current_hash = imagehash.phash(screenshot)

        if self._last_hash is None:
            self._last_hash = current_hash
            return True

        distance = current_hash - self._last_hash
        changed = distance > self.threshold

        if changed:
            logger.debug("screen_changed", hash_distance=distance)
            self._last_hash = current_hash

        return changed

    def force_update(self, screenshot: Image.Image) -> None:
        """Force update the stored hash without checking for changes."""
        self._last_hash = imagehash.phash(screenshot)

    def reset(self) -> None:
        """Reset the stored hash, so the next check will always return True."""
        self._last_hash = None
