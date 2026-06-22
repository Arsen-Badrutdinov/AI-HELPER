"""
screen_capture.py — Захват экрана через mss.

Делает скриншот только по триггеру (не постоянно).
Умеет захватывать весь экран или конкретное окно.
"""

import mss
import mss.tools
import ctypes
import ctypes.wintypes
import os
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowInfo:
    """Информация об окне."""
    hwnd: int
    title: str
    rect: dict  # {"left", "top", "width", "height"}


def get_foreground_window() -> Optional[WindowInfo]:
    """Получает информацию об активном окне Windows."""
    user32 = ctypes.windll.user32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    # Заголовок окна
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # Координаты окна
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))

    return WindowInfo(
        hwnd=hwnd,
        title=title,
        rect={
            "left": rect.left,
            "top": rect.top,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        },
    )


def capture_full_screen(monitor_index: int = 1) -> str:
    """
    Захватывает весь экран. Возвращает путь к PNG-файлу.
    monitor_index=1 — основной монитор, 0 = все мониторы.
    """
    output_dir = _get_output_dir()
    filename = os.path.join(output_dir, f"screen_{int(time.time())}.png")

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=filename)

    return filename


def capture_active_window() -> Optional[str]:
    """
    Захватывает только активное окно (редактор кода).
    Возвращает путь к PNG или None если не удалось.
    """
    win = get_foreground_window()
    if not win:
        return None

    output_dir = _get_output_dir()
    filename = os.path.join(output_dir, f"window_{int(time.time())}.png")

    region = {
        "left": max(0, win.rect["left"]),
        "top": max(0, win.rect["top"]),
        "width": max(100, win.rect["width"]),
        "height": max(100, win.rect["height"]),
    }

    with mss.mss() as sct:
        screenshot = sct.grab(region)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=filename)

    return filename


def capture_region(left: int, top: int, width: int, height: int) -> str:
    """Захватывает произвольный регион экрана."""
    output_dir = _get_output_dir()
    filename = os.path.join(output_dir, f"region_{int(time.time())}.png")

    region = {"left": left, "top": top, "width": width, "height": height}

    with mss.mss() as sct:
        screenshot = sct.grab(region)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=filename)

    return filename


def get_screenshot_bytes(filepath: str) -> bytes:
    """Читает скриншот как байты для отправки на API."""
    with open(filepath, "rb") as f:
        return f.read()


def cleanup_old_screenshots(max_age_seconds: int = 300):
    """Удаляет скриншоты старше N секунд (по умолчанию 5 мин)."""
    output_dir = _get_output_dir()
    if not os.path.isdir(output_dir):
        return

    now = time.time()
    for f in os.listdir(output_dir):
        path = os.path.join(output_dir, f)
        if os.path.isfile(path) and f.endswith(".png"):
            if now - os.path.getmtime(path) > max_age_seconds:
                try:
                    os.remove(path)
                except OSError:
                    pass


def _get_output_dir() -> str:
    """Директория для временных скриншотов."""
    d = os.path.join(os.path.dirname(__file__), ".screenshots")
    os.makedirs(d, exist_ok=True)
    return d


# ─── Тест ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    win = get_foreground_window()
    if win:
        print(f"Активное окно: {win.title}")
        print(f"Координаты: {win.rect}")

    path = capture_full_screen()
    print(f"Скриншот сохранён: {path}")
