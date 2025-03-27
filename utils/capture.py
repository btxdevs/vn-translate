import win32gui
import win32ui
import win32con
import mss
import numpy as np
import cv2
from ctypes import windll, byref, wintypes

def enum_window_callback(hwnd, windows):
    """Callback for win32gui.EnumWindows; adds visible, non-minimized windows with titles."""
    if (win32gui.IsWindowVisible(hwnd) and
            win32gui.GetWindowText(hwnd) and
            not win32gui.IsIconic(hwnd)):  # Checks if window is not minimized
        windows.append(hwnd)
    return True

def get_windows():
    """Return a list of handles for visible windows."""
    print("Getting list of visible windows")
    windows = []
    win32gui.EnumWindows(enum_window_callback, windows)
    print(f"Found {len(windows)} visible windows")
    return windows

def get_window_title(hwnd):
    """Return the title of a window given its handle."""
    title = win32gui.GetWindowText(hwnd)
    print(f"Window title for handle {hwnd}: {title}")
    return title

def get_window_rect(hwnd):
    """Return (left, top, right, bottom) of the window."""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        print(f"Window rect for handle {hwnd}: {rect}")
        return rect
    except Exception as e:
        print(f"Error getting window rect: {e}")
        return None

def get_client_rect(hwnd):
    """Get the client area rectangle of a window."""
    try:
        # Get client rectangle in window's coordinates
        client_rect = win32gui.GetClientRect(hwnd)
        # Convert to screen coordinates
        pt1 = wintypes.POINT(client_rect[0], client_rect[1])
        pt2 = wintypes.POINT(client_rect[2], client_rect[3])
        windll.user32.ClientToScreen(hwnd, byref(pt1))
        windll.user32.ClientToScreen(hwnd, byref(pt2))

        rect = (pt1.x, pt1.y, pt2.x, pt2.y)
      #  print(f"Client rect for handle {hwnd}: {rect}")
        return rect
    except Exception as e:
        print(f"Error getting client rect: {e}")
        return None

def capture_window_direct(hwnd):
    """
    Capture a window's client area directly using Windows API (more reliable for games).

    Args:
        hwnd: Window handle

    Returns:
        numpy array of the captured frame or None if failed
    """
    try:
        #  print(f"Starting direct capture for window handle {hwnd}")

        # Get client rectangle
        client_rect = get_client_rect(hwnd)
        if client_rect is None:
            print("Failed to get client rectangle, falling back to window rectangle")
            client_rect = get_window_rect(hwnd)

        left, top, right, bottom = client_rect
        width = right - left - 4  # Subtract 4 from width
        height = bottom - top - 4  # Subtract 4 from height

        #print(f"Client area dimensions: {width}x{height}, at position ({left}, {top})")

        if width <= 0 or height <= 0:
            print("Invalid window dimensions")
            return None

        # Get device contexts
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        # Create bitmap
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        # Attempt PrintWindow first (better for modern apps)
        # print("Attempting PrintWindow capture method")
        result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)  # PW_RENDERFULLCONTENT = 3

        # If PrintWindow failed, fall back to BitBlt
        if not result:
            print("PrintWindow failed, falling back to BitBlt")
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (left - left, top - top), win32con.SRCCOPY)

        # Convert bitmap to numpy array
        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (height, width, 4)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # print(f"Direct capture succeeded. Image shape: {img.shape}")

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
    Capture a window's client area using mss (fallback method).

    Args:
        hwnd: Window handle

    Returns:
        numpy array of the captured frame or None if failed
    """
    try:
        print(f"Starting fallback capture for window handle {hwnd}")

        # Get client rectangle
        client_rect = get_client_rect(hwnd)
        if client_rect is None:
            print("Failed to get client rectangle, falling back to window rectangle")
            client_rect = get_window_rect(hwnd)

        if client_rect is None:
            print("Failed to get any window rectangle")
            return None

        left, top, right, bottom = client_rect
        width = right - left - 4  # Subtract 4 from width
        height = bottom - top - 4  # Subtract 4 from height

        print(f"Fallback capture area: ({left}, {top}) with dimensions {width}x{height}")

        if width <= 0 or height <= 0:
            print("Invalid window dimensions for fallback capture")
            return None

        # Capture using mss
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            img = sct.grab(monitor)
            frame = np.array(img)[:, :, :3]

            print(f"Fallback capture succeeded. Image shape: {frame.shape}")
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
  #  print(f"Capturing window with handle {hwnd}")

    frame = capture_window_direct(hwnd)
    if frame is None:
        print("Direct capture failed, trying fallback method...")
        frame = capture_window_fallback(hwnd)
    return frame