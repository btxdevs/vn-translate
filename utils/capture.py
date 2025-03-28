# --- START OF FILE utils/capture.py ---

import win32gui
import win32ui
import win32con
import mss
import numpy as np
import cv2
from ctypes import windll, byref, wintypes
import time # For performance timing
import win32process # For getting process ID and executable path
import win32api # For opening process
import os # For getting file size

# Flag to reduce repetitive logging
LOG_CAPTURE_DETAILS = False # Set to True for debugging capture methods/rects

def enum_window_callback(hwnd, windows):
    """Callback for win32gui.EnumWindows adds visible, non-minimized windows with titles."""
    try:
        if not win32gui.IsWindowVisible(hwnd): return True
        if not win32gui.GetWindowText(hwnd): return True
        if win32gui.IsIconic(hwnd): return True # Exclude minimized

        windows.append(hwnd)
    except Exception as e:
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
        return title
    except Exception as e:
        return ""

def get_executable_details(hwnd):
    """
    Gets the full path and size of the executable associated with the window handle.

    Args:
        hwnd: The window handle.

    Returns:
        A tuple (executable_path, file_size) or (None, None) if failed.
    """
    try:
        if not hwnd or not win32gui.IsWindow(hwnd):
            return None, None

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            print(f"Could not get PID for HWND {hwnd}")
            return None, None

        process_handle = None
        try:
            process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        except Exception as open_err:
            try:
                process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
            except Exception as open_err_fallback:
                print(f"Could not open process PID {pid} for HWND {hwnd}: {open_err_fallback}")
                return None, None

        if not process_handle:
            print(f"Failed to get handle for process PID {pid}")
            return None, None

        try:
            exe_path = win32process.GetModuleFileNameEx(process_handle, 0)
            if not exe_path or not os.path.exists(exe_path):
                print(f"Could not get valid executable path for PID {pid}")
                return None, None

            file_size = os.path.getsize(exe_path)
            return exe_path, file_size

        except Exception as e:
            print(f"Error getting module filename or size for PID {pid}: {e}")
            return None, None
        finally:
            if process_handle:
                win32api.CloseHandle(process_handle)

    except Exception as e:
        print(f"General error getting executable details for HWND {hwnd}: {e}")
        return None, None


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

        client_rect_rel = win32gui.GetClientRect(hwnd)
        pt_tl = wintypes.POINT(client_rect_rel[0], client_rect_rel[1])
        pt_br = wintypes.POINT(client_rect_rel[2], client_rect_rel[3])

        if not windll.user32.ClientToScreen(hwnd, byref(pt_tl)):
            print(f"ClientToScreen failed for top-left point, HWND {hwnd}")
            return None
        if not windll.user32.ClientToScreen(hwnd, byref(pt_br)):
            print(f"ClientToScreen failed for bottom-right point, HWND {hwnd}")
            return None

        rect_screen = (pt_tl.x, pt_tl.y, pt_br.x, pt_br.y)
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
    save_bitmap = None
    save_dc = None
    mfc_dc = None
    hwnd_dc = None
    try:
        target_rect = get_client_rect(hwnd)
        rect_type = "Client"
        if target_rect is None:
            target_rect = get_window_rect(hwnd)
            rect_type = "Window"
            if target_rect is None:
                print(f"Failed to get any rect for HWND {hwnd}. Cannot capture.")
                return None

        left, top, right, bottom = target_rect
        width = right - left
        height = bottom - top

        if LOG_CAPTURE_DETAILS: print(f"Direct Capture using {rect_type} Rect: ({left},{top}) {width}x{height}")

        if width <= 0 or height <= 0:
            if rect_type == "Window" and win32gui.IsIconic(hwnd): print("Window is minimized.")
            return None

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc: print(f"Failed to get Window DC for HWND {hwnd}"); return None
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        # PW_RENDERFULLCONTENT needed for some modern apps
        print_window_flag = 0x1 | 0x2 if rect_type == "Client" else 0x2 # Try client + full render or just full render

        result = 0
        try:
            # PrintWindow is generally preferred for modern apps
            result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), print_window_flag)
        except Exception as pw_error:
            print(f"PrintWindow call failed: {pw_error}")
            result = 0

        if not result:
            if LOG_CAPTURE_DETAILS: print("PrintWindow failed or skipped, falling back to BitBlt")
            try:
                src_x = 0
                src_y = 0
                if rect_type == "Client":
                    # For client rect, need offset from window origin for BitBlt source
                    window_rect = win32gui.GetWindowRect(hwnd)
                    src_x = left - window_rect[0]
                    src_y = top - window_rect[1]
                    if LOG_CAPTURE_DETAILS: print(f"BitBlt source offset: ({src_x}, {src_y})")
                # For window rect, BitBlt source is (0,0) relative to the WindowDC
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (src_x, src_y), win32con.SRCCOPY)
            except Exception as blt_error:
                print(f"BitBlt failed: {blt_error}")
                # Don't return yet, allow fallback to MSS if direct method fails completely
                # Cleanup happens in finally block
                # We return None only if BOTH direct methods fail
                return None # Explicitly return None if BitBlt fails after PrintWindow attempt

        # --- Conversion to numpy array (common to both PrintWindow and BitBlt success) ---
        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        if not bmp_str or len(bmp_str) != bmp_info['bmWidthBytes'] * bmp_info['bmHeight']:
            print("Error: Invalid bitmap data received.")
            return None

        img = np.frombuffer(bmp_str, dtype='uint8')
        img.shape = (bmp_info['bmHeight'], bmp_info['bmWidth'], 4) # BGRA
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        if LOG_CAPTURE_DETAILS: print(f"Direct capture success ({rect_type}). Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")
        return img_bgr

    except Exception as e:
        print(f"!!! Direct capture error for HWND {hwnd}: {e}")
        import traceback; traceback.print_exc()
        return None # Return None on general exceptions in direct method
    finally:
        # Ensure cleanup happens regardless of success/failure within the try block
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
            # Use None check as hwnd_dc might not be assigned if GetWindowDC fails early
            if hwnd_dc and hwnd: win32gui.ReleaseDC(hwnd, hwnd_dc)
        except: pass


def capture_window_mss(hwnd):
    """
    Capture window using MSS (fallback, uses screen coordinates).
    Returns numpy array (BGR) or None.
    """
    start_time = time.perf_counter()
    try:
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

        if width <= 0 or height <= 0: return None

        monitor = {"left": left, "top": top, "width": width, "height": height}
        with mss.mss() as sct:
            img_mss = sct.grab(monitor)

        img_bgra = np.array(img_mss, dtype=np.uint8)
        img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        # if LOG_CAPTURE_DETAILS: print(f"MSS capture success ({rect_type})... Time: {end_time - start_time:.4f}s")
        return img_bgr

    except Exception as e:
        print(f"!!! MSS capture error for HWND {hwnd}: {e}")
        return None

def capture_screen_region_direct(region):
    """
    Attempt to capture screen region using Windows GDI (BitBlt from Desktop DC).
    Returns numpy array (BGR) or None if failed.
    """
    start_time = time.perf_counter()
    desktop_dc = None
    mem_dc = None
    bitmap = None
    try:
        left, top = region["left"], region["top"]
        width, height = region["width"], region["height"]

        if width <= 0 or height <= 0: return None

        # Get DC for the entire screen (desktop)
        desktop_dc = win32gui.GetDC(0) # 0 or None should work for primary screen
        if not desktop_dc:
            print("[Capture Direct Region] Failed to get Desktop DC.")
            return None

        desktop_mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = desktop_mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(desktop_mfc_dc, width, height)
        mem_dc.SelectObject(bitmap)

        # Perform BitBlt from desktop DC to memory DC
        mem_dc.BitBlt((0, 0), (width, height), desktop_mfc_dc, (left, top), win32con.SRCCOPY)

        # Convert bitmap to numpy array
        bmp_info = bitmap.GetInfo()
        bmp_str = bitmap.GetBitmapBits(True)
        if not bmp_str or len(bmp_str) != bmp_info['bmWidthBytes'] * bmp_info['bmHeight']:
            print("[Capture Direct Region] Error: Invalid bitmap data.")
            return None

        img = np.frombuffer(bmp_str, dtype='uint8')
        img.shape = (height, width, 4) # BGRA
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        if LOG_CAPTURE_DETAILS: print(f"[Capture Direct Region] Success. Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")
        return img_bgr

    except Exception as e:
        print(f"!!! Direct screen region capture error: {e}")
        # import traceback; traceback.print_exc() # Optional for deep debug
        return None # Return None on failure
    finally:
        # Ensure cleanup
        try:
            if bitmap: win32gui.DeleteObject(bitmap.GetHandle())
        except: pass
        try:
            if mem_dc: mem_dc.DeleteDC()
        except: pass
        try:
            # desktop_mfc_dc created from desktop_dc, should be cleaned up by releasing desktop_dc
            pass
        except: pass
        try:
            if desktop_dc: win32gui.ReleaseDC(0, desktop_dc)
        except: pass


def capture_screen_region_mss(region):
    """
    Capture screen region using MSS.
    Returns numpy array (BGR) or None.
    """
    start_time = time.perf_counter()
    try:
        if region["width"] <= 0 or region["height"] <= 0: return None

        with mss.mss() as sct:
            img_mss = sct.grab(region)

        img_bgra = np.array(img_mss, dtype=np.uint8)
        img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        # if LOG_CAPTURE_DETAILS: print(f"[Capture MSS Region] Success. Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")
        return img_bgr
    except Exception as e:
        print(f"!!! MSS screen region capture error: {e}")
        return None


def capture_screen_region(region):
    """
    Capture an arbitrary screen region, trying direct GDI first, then MSS.

    Args:
        region (dict): A dictionary with {"left": x, "top": y, "width": w, "height": h}
                       in screen coordinates.

    Returns:
        numpy array (BGR) of the captured frame or None if failed
    """
    # Validate region format once
    if not all(k in region for k in ("left", "top", "width", "height")):
        print("[Capture Region] Error: Invalid region format.")
        return None
    if region["width"] <= 0 or region["height"] <= 0:
        print("[Capture Region] Error: Invalid region dimensions.")
        return None

    # Try direct method first
    frame = capture_screen_region_direct(region)

    # Fallback to MSS if direct method failed
    if frame is None:
        if LOG_CAPTURE_DETAILS: print("[Capture Region] Direct capture failed, trying MSS fallback...")
        frame = capture_screen_region_mss(region)
        if frame is None and LOG_CAPTURE_DETAILS:
            print("[Capture Region] MSS capture also failed.")

    # Optional: Basic validation of the final frame
    if frame is not None and (frame.shape[0] < 1 or frame.shape[1] < 1):
        print(f"[Capture Region] Warning: Captured frame seems invalid ({frame.shape}).")
        return None

    return frame


def capture_window(hwnd):
    """
    Capture a window using the best available method.
    Tries direct capture (PrintWindow/BitBlt) first, then falls back to MSS.

    Args:
        hwnd: Window handle

    Returns:
        numpy array (BGR) of the captured frame or None if failed
    """
    if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
        return None

    frame = capture_window_direct(hwnd)
    if frame is None:
        if LOG_CAPTURE_DETAILS: print("Direct window capture failed, trying MSS fallback...")
        frame = capture_window_mss(hwnd)
        if frame is None and LOG_CAPTURE_DETAILS:
            print("MSS window capture also failed.")

    if frame is not None and (frame.shape[0] < 10 or frame.shape[1] < 10):
        return None

    return frame

# --- END OF FILE utils/capture.py ---