from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def enable_per_monitor_v2_awareness() -> bool:
    if sys.platform != "win32":
        return False

    user32 = ctypes.windll.user32
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        return bool(user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
    except (AttributeError, OSError):
        try:
            # PROCESS_PER_MONITOR_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
            ctypes.windll.shcore.SetProcessDpiAwareness.restype = ctypes.c_long
            return int(ctypes.windll.shcore.SetProcessDpiAwareness(2)) == 0
        except (AttributeError, OSError):
            return False
