import win32gui
import win32ui
import win32con
import mss
import numpy as np
import cv2
from ctypes import windll, byref, wintypes
import time # For performance timing

# Flag to reduce repetitive logging
LOG_CAPTURE_DETAILS = False # Set to True for debugging capture methods/rects

def enum_window_callback(hwnd, windows):
    """Callback for win32gui.EnumWindows; adds visible, non-minimized windows with titles."""
    try:
        # Filter more aggressively: check style, title, visibility, parent, not minimized
        if not win32gui.IsWindowVisible(hwnd): return True
        if not win32gui.GetWindowText(hwnd): return True
        # if win32gui.GetParent(hwnd) != 0: return True # Exclude child windows? Might exclude some games.
        if win32gui.IsIconic(hwnd): return True # Exclude minimized

        # Optional: Filter based on class name? (e.g., exclude Taskbar, specific tool windows)
        # class_name = win32gui.GetClassName(hwnd)
        # if class_name in ["Shell_TrayWnd", "Progman", "ApplicationFrameWindow"]: return True # AppFrame for UWP borders

        windows.append(hwnd)
    except Exception as e:
        # Ignore errors for windows we can't access
        # print(f"Enum callback error for HWND {hwnd}: {e}")
        pass
    return True

def get_windows():
    """Return a list of handles for potentially relevant windows."""
    if LOG_CAPTURE_DETAILS: print("Getting list of windows...")
    windows = []
    try:
        win32gui.EnumWindows(enum_window_callback, windows)
    except Exception as e:
        print(f"Error during EnumWindows: {e}")
    if LOG_CAPTURE_DETAILS: print(f"Found {len(windows)} candidate windows")
    return windows

def get_window_title(hwnd):
    """Return the title of a window given its handle."""
    try:
        title = win32gui.GetWindowText(hwnd)
        # if LOG_CAPTURE_DETAILS: print(f"Window title for HWND {hwnd}: {title}")
        return title
    except Exception as e:
        # print(f"Error getting title for HWND {hwnd}: {e}") # Can be noisy
        return ""


def get_window_rect(hwnd):
    """Return (left, top, right, bottom) of the window including borders."""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        if LOG_CAPTURE_DETAILS: print(f"Window rect for HWND {hwnd}: {rect}")
        return rect
    except Exception as e:
        print(f"Error getting window rect for HWND {hwnd}: {e}")
        return None

def get_client_rect(hwnd):
    """Get the client area rectangle relative to the screen."""
    try:
        if not win32gui.IsWindow(hwnd): return None

        # Get client rectangle relative to window's top-left
        client_rect_rel = win32gui.GetClientRect(hwnd)
        # if LOG_CAPTURE_DETAILS: print(f"Relative client rect for HWND {hwnd}: {client_rect_rel}")

        # Convert client rect's top-left (0,0) and bottom-right points to screen coordinates
        pt_tl = wintypes.POINT(client_rect_rel[0], client_rect_rel[1])
        pt_br = wintypes.POINT(client_rect_rel[2], client_rect_rel[3])

        # Check if ClientToScreen succeeds
        if not windll.user32.ClientToScreen(hwnd, byref(pt_tl)):
            print(f"ClientToScreen failed for top-left point, HWND {hwnd}")
            return None
        if not windll.user32.ClientToScreen(hwnd, byref(pt_br)):
            print(f"ClientToScreen failed for bottom-right point, HWND {hwnd}")
            return None

        # Screen coordinates rectangle
        rect_screen = (pt_tl.x, pt_tl.y, pt_br.x, pt_br.y)
        # if LOG_CAPTURE_DETAILS: print(f"Screen client rect for HWND {hwnd}: {rect_screen}")
        return rect_screen
    except Exception as e:
        print(f"Error getting client rect for HWND {hwnd}: {e}")
        return None

def capture_window_direct(hwnd):
    """
    Capture window's client area using Windows API (PrintWindow/BitBlt).
    Returns numpy array (BGR) or None.
    """
    start_time = time.perf_counter()
    save_bitmap = None # Define outside try for cleanup
    save_dc = None
    mfc_dc = None
    hwnd_dc = None
    try:
        # --- Get Target Area ---
        # Prioritize client rect
        target_rect = get_client_rect(hwnd)
        rect_type = "Client"
        if target_rect is None:
            # Fallback to full window rect if client rect fails
            target_rect = get_window_rect(hwnd)
            rect_type = "Window"
            if target_rect is None:
                print(f"Failed to get any rect for HWND {hwnd}. Cannot capture.")
                return None

        left, top, right, bottom = target_rect
        width = right - left
        height = bottom - top

        if LOG_CAPTURE_DETAILS:
            print(f"Direct Capture using {rect_type} Rect: ({left},{top}) {width}x{height}")

        if width <= 0 or height <= 0:
            # print(f"Invalid dimensions for HWND {hwnd}: {width}x{height}")
            # If it's the window rect, maybe the window is minimized?
            if rect_type == "Window" and win32gui.IsIconic(hwnd):
                print("Window is minimized.")
            return None

        # --- Prepare Device Contexts ---
        # Get DC for the entire window (needed for PrintWindow and BitBlt source)
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc:
            print(f"Failed to get Window DC for HWND {hwnd}")
            return None
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        # Create compatible DC for destination bitmap
        save_dc = mfc_dc.CreateCompatibleDC()

        # --- Create Bitmap ---
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        # Select bitmap into destination DC
        save_dc.SelectObject(save_bitmap)

        # --- Perform Capture ---
        # Try PrintWindow first (better for layered windows, DWM)
        # Flags: 0 = Full window, 1 = Client area only (use if rect_type == "Client"),
        # 2 (PW_RENDERFULLCONTENT) or 3? Docs vary. Let's stick to 0 or 1.
        print_window_flag = 1 if rect_type == "Client" else 0

        result = 0
        try:
            # Important: For PrintWindow, the target DC (save_dc) gets the content.
            # The source is the window itself (hwnd).
            result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), print_window_flag)
            # if LOG_CAPTURE_DETAILS: print(f"PrintWindow result: {result} (Flag: {print_window_flag})")
        except Exception as pw_error:
            print(f"PrintWindow call failed: {pw_error}")
            result = 0

        # Fallback to BitBlt if PrintWindow failed (result is 0)
        if not result:
            if LOG_CAPTURE_DETAILS: print("PrintWindow failed or skipped, falling back to BitBlt")
            try:
                # For BitBlt: Copy from source DC (mfc_dc) to destination DC (save_dc)
                # Source origin depends on the DC obtained by GetWindowDC.
                # For client rect, we want to copy from the client origin within that DC.
                # For window rect, we copy from (0,0).
                src_x = 0
                src_y = 0
                if rect_type == "Client":
                    # Client rect was screen coords, need coords relative to window origin
                    window_rect = win32gui.GetWindowRect(hwnd)
                    src_x = left - window_rect[0] # client left screen - window left screen
                    src_y = top - window_rect[1]  # client top screen - window top screen
                    if LOG_CAPTURE_DETAILS: print(f"BitBlt source offset: ({src_x}, {src_y})")


                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (src_x, src_y), win32con.SRCCOPY)
                # if LOG_CAPTURE_DETAILS: print("BitBlt executed.")
            except Exception as blt_error:
                print(f"BitBlt failed: {blt_error}")
                # Clean up handled in finally block
                return None


        # --- Convert Bitmap to Numpy Array ---
        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        # Check if bitmap data is valid
        if not bmp_str or len(bmp_str) != bmp_info['bmWidthBytes'] * bmp_info['bmHeight']:
            print("Error: Invalid bitmap data received.")
            return None

        img = np.frombuffer(bmp_str, dtype='uint8')
        img.shape = (bmp_info['bmHeight'], bmp_info['bmWidth'], 4) # BGRA format

        # Remove alpha channel, convert to BGR
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        if LOG_CAPTURE_DETAILS:
            print(f"Direct capture success ({rect_type}). Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")

        return img_bgr

    except Exception as e:
        print(f"!!! Direct capture error for HWND {hwnd}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # --- Ensure Cleanup ---
        try:
            if save_bitmap: win32gui.DeleteObject(save_bitmap.GetHandle())
        except: pass
        try:
            if save_dc: save_dc.DeleteDC()
        except: pass
        try:
            if mfc_dc: mfc_dc.DeleteDC()
        except: pass
        try:
            if hwnd_dc: win32gui.ReleaseDC(hwnd, hwnd_dc)
        except: pass


def capture_window_mss(hwnd):
    """
    Capture window using MSS (fallback, uses screen coordinates).
    Returns numpy array (BGR) or None.
    """
    start_time = time.perf_counter()
    try:
        # --- Get Target Area (Screen Coordinates) ---
        # Must use screen coordinates for MSS
        target_rect = get_client_rect(hwnd)
        rect_type = "Client"
        if target_rect is None:
            target_rect = get_window_rect(hwnd)
            rect_type = "Window"
            if target_rect is None:
                print(f"MSS: Failed to get any rect for HWND {hwnd}.")
                return None

        left, top, right, bottom = target_rect
        width = right - left
        height = bottom - top

        # if LOG_CAPTURE_DETAILS:
        #      print(f"MSS Capture using Screen {rect_type} Rect: ({left},{top}) {width}x{height}")

        if width <= 0 or height <= 0:
            # print(f"MSS: Invalid dimensions for HWND {hwnd}: {width}x{height}")
            return None

        # --- Capture using MSS ---
        monitor = {"left": left, "top": top, "width": width, "height": height}
        with mss.mss() as sct:
            img_mss = sct.grab(monitor)

        # Convert to numpy array (BGRA) -> (BGR)
        img_bgra = np.array(img_mss, dtype=np.uint8)
        img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        # if LOG_CAPTURE_DETAILS:
        #      print(f"MSS capture success ({rect_type}). Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")

        return img_bgr

    except Exception as e:
        print(f"!!! MSS capture error for HWND {hwnd}: {e}")
        return None


def capture_window(hwnd):
    """
    Capture a window using the best available method.
    Tries direct capture first, then falls back to MSS.

    Args:
        hwnd: Window handle

    Returns:
        numpy array (BGR) of the captured frame or None if failed
    """
    # Check if window handle is valid and window is visible/not minimized
    if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
        # print(f"Capture attempt skipped: Invalid/hidden/minimized HWND {hwnd}") # Can be noisy
        return None

    # Try direct method
    frame = capture_window_direct(hwnd)

    # If direct failed, try MSS
    if frame is None:
        if LOG_CAPTURE_DETAILS: print("Direct capture failed, trying MSS fallback...")
        frame = capture_window_mss(hwnd)
        if frame is None and LOG_CAPTURE_DETAILS:
            print("MSS capture also failed.")

    # Optional: Check frame dimensions/content?
    if frame is not None and (frame.shape[0] < 10 or frame.shape[1] < 10):
        # print(f"Warning: Captured frame seems too small ({frame.shape}).")
        return None # Reject tiny frames?

    return frame