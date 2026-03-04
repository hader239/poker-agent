"""Coordinate translation between image space and screen space."""

from __future__ import annotations

from poker_agent.capture.window import WindowInfo


class CoordinateTranslator:
    """Translates coordinates between image pixel space and pyautogui screen space.

    mss captures at native Retina resolution (2x on macOS), so image coordinates
    are at 2x scale. pyautogui operates in logical (1x) coordinates.
    Window position is already in logical coordinates.
    """

    def __init__(self, retina_scale: int = 2):
        self.retina_scale = retina_scale

    def image_to_screen(
        self, img_x: int, img_y: int, window: WindowInfo
    ) -> tuple[int, int]:
        """Convert image pixel coordinates to pyautogui screen coordinates.

        Args:
            img_x: X coordinate in the captured image (Retina pixels).
            img_y: Y coordinate in the captured image (Retina pixels).
            window: The window info with position in logical coordinates.

        Returns:
            (screen_x, screen_y) in logical coordinates for pyautogui.
        """
        logical_x = img_x / self.retina_scale
        logical_y = img_y / self.retina_scale

        screen_x = window.left + logical_x
        screen_y = window.top + logical_y

        return int(screen_x), int(screen_y)

    def screen_to_image(
        self, screen_x: int, screen_y: int, window: WindowInfo
    ) -> tuple[int, int]:
        """Convert screen coordinates to image pixel coordinates.

        Args:
            screen_x: X coordinate in logical screen space.
            screen_y: Y coordinate in logical screen space.
            window: The window info with position in logical coordinates.

        Returns:
            (img_x, img_y) in Retina pixel coordinates.
        """
        local_x = screen_x - window.left
        local_y = screen_y - window.top

        img_x = local_x * self.retina_scale
        img_y = local_y * self.retina_scale

        return int(img_x), int(img_y)
