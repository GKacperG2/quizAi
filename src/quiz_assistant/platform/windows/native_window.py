from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def apply_nonactivating_clickthrough(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    get_style = user32.GetWindowLongPtrW
    set_style = user32.SetWindowLongPtrW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = ctypes.c_ssize_t
    set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    set_style.restype = ctypes.c_ssize_t
    style = get_style(hwnd, GWL_EXSTYLE)
    style |= WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
    set_style(hwnd, GWL_EXSTYLE, style)


def show_without_activation(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    set_window_pos = ctypes.windll.user32.SetWindowPos
    set_window_pos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    set_window_pos.restype = wintypes.BOOL
    set_window_pos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )


def flush_compositor() -> bool:
    if sys.platform != "win32":
        return False
    try:
        dwm_flush = ctypes.windll.dwmapi.DwmFlush
        dwm_flush.argtypes = []
        dwm_flush.restype = ctypes.c_long
        return int(dwm_flush()) == 0
    except (AttributeError, OSError):
        return False
