import win32gui
import win32ui
import win32con
import mss
import numpy as np
import cv2
from ctypes import windll

def enum_window_callback(hwnd, windows):
    """Callback for win32gui.EnumWindows; adds visible windows with titles."""
    if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
        windows.append(hwnd)

def get_windows():
    """Return a list of handles for visible windows."""
    windows = []
    win32gui.EnumWindows(enum_window_callback, windows)
    return windows

def get_window_title(hwnd):
    """Return the title of a window given its handle."""
    return win32gui.GetWindowText(hwnd)

def get_window_rect(hwnd):
    """Return (left, top, right, bottom) of the window."""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        return rect
    except Exception as e:
        print(f"Error getting window rect: {e}")
        return None

def capture_window_direct(hwnd):
    """
    Capture a window directly using Windows API (more reliable for games).

    Args:
        hwnd: Window handle

    Returns:
        numpy array of the captured frame or None if failed
    """
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        if width == 0 or height == 0:
            return None
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)
        result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        if not result:
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (height, width, 4)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        # Clean up resources
        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        return img
    except Exception as e:
        print(f"Direct capture error: {e}")
        return None

def capture_window_fallback(hwnd):
    """
    Capture a window using mss (fallback method).

    Args:
        hwnd: Window handle

    Returns:
        numpy array of the captured frame or None if failed
    """
    try:
        rect = get_window_rect(hwnd)
        if rect is None:
            return None
        left, top, right, bottom = rect
        width, height = right - left, bottom - top
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            img = sct.grab(monitor)
            frame = np.array(img)[:, :, :3]
            return frame
    except Exception as e:
        print(f"Fallback capture error: {e}")
        return None

def capture_window(hwnd):
    """
    Capture a window using the best available method.
    Tries direct capture first, then falls back to mss if that fails.

    Args:
        hwnd: Window handle

    Returns:
        numpy array of the captured frame or None if failed
    """
    frame = capture_window_direct(hwnd)
    if frame is None:
        print("Direct capture failed, trying fallback method...")
        frame = capture_window_fallback(hwnd)
    return frame