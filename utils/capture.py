import win32gui
import win32ui
import win32con
import mss
import numpy as np
import cv2
from ctypes import windll, byref, wintypes
import time
import win32process
import win32api
import os

LOG_CAPTURE_DETAILS = False

def enum_window_callback(hwnd, windows):
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if not win32gui.GetWindowText(hwnd):
            return True
        if win32gui.IsIconic(hwnd):
            return True
        windows.append(hwnd)
    except Exception:
        pass
    return True

def get_windows():
    windows = []
    try:
        win32gui.EnumWindows(enum_window_callback, windows)
    except Exception as e:
        print(f"Error during EnumWindows: {e}")
    return windows

def get_window_title(hwnd):
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return ""

def get_executable_details(hwnd):
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
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception as e:
        print(f"Error getting window rect for HWND {hwnd}: {e}")
        return None

def get_client_rect(hwnd):
    try:
        if not win32gui.IsWindow(hwnd):
            return None
        client_rect_rel = win32gui.GetClientRect(hwnd)
        pt_tl = wintypes.POINT(client_rect_rel[0], client_rect_rel[1])
        pt_br = wintypes.POINT(client_rect_rel[2], client_rect_rel[3])
        if not windll.user32.ClientToScreen(hwnd, byref(pt_tl)):
            print(f"ClientToScreen failed for top-left, HWND {hwnd}")
            return None
        if not windll.user32.ClientToScreen(hwnd, byref(pt_br)):
            print(f"ClientToScreen failed for bottom-right, HWND {hwnd}")
            return None
        return (pt_tl.x, pt_tl.y, pt_br.x, pt_br.y)
    except Exception as e:
        print(f"Error getting client rect for HWND {hwnd}: {e}")
        return None

def capture_window_direct(hwnd):
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
                print(f"Failed to get any rect for HWND {hwnd}.")
                return None
        left, top, right, bottom = target_rect
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            if rect_type == "Window" and win32gui.IsIconic(hwnd):
                print("Window is minimized.")
            return None
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc:
            print(f"Failed to get Window DC for HWND {hwnd}")
            return None
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)
        print_window_flag = 0x1 | 0x2 if rect_type == "Client" else 0x2
        result = 0
        try:
            result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), print_window_flag)
        except Exception as pw_error:
            print(f"PrintWindow call failed: {pw_error}")
            result = 0
        if not result:
            try:
                src_x = 0
                src_y = 0
                if rect_type == "Client":
                    window_rect = win32gui.GetWindowRect(hwnd)
                    src_x = left - window_rect[0]
                    src_y = top - window_rect[1]
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (src_x, src_y), win32con.SRCCOPY)
            except Exception as blt_error:
                print(f"BitBlt failed: {blt_error}")
                return None
        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        if not bmp_str or len(bmp_str) != bmp_info['bmWidthBytes'] * bmp_info['bmHeight']:
            print("Error: Invalid bitmap data received.")
            return None
        img = np.frombuffer(bmp_str, dtype='uint8')
        img.shape = (bmp_info['bmHeight'], bmp_info['bmWidth'], 4)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        end_time = time.perf_counter()
        if LOG_CAPTURE_DETAILS:
            print(f"Direct capture success ({rect_type}). Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")
        return img_bgr
    except Exception as e:
        print(f"Direct capture error for HWND {hwnd}: {e}")
        return None
    finally:
        try:
            if save_bitmap:
                win32gui.DeleteObject(save_bitmap.GetHandle())
        except:
            pass
        try:
            if save_dc:
                save_dc.DeleteDC()
        except:
            pass
        try:
            if mfc_dc:
                mfc_dc.DeleteDC()
        except:
            pass
        try:
            if hwnd_dc and hwnd:
                win32gui.ReleaseDC(hwnd, hwnd_dc)
        except:
            pass

def capture_window_mss(hwnd):
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
        if width <= 0 or height <= 0:
            return None
        monitor = {"left": left, "top": top, "width": width, "height": height}
        with mss.mss() as sct:
            img_mss = sct.grab(monitor)
        img_bgra = np.array(img_mss, dtype=np.uint8)
        img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
        end_time = time.perf_counter()
        return img_bgr
    except Exception as e:
        print(f"MSS capture error for HWND {hwnd}: {e}")
        return None

def capture_screen_region_direct(region):
    start_time = time.perf_counter()
    desktop_dc = None
    mem_dc = None
    bitmap = None
    try:
        left, top, width, height = region["left"], region["top"], region["width"], region["height"]
        if width <= 0 or height <= 0:
            return None
        desktop_dc = win32gui.GetDC(0)
        if not desktop_dc:
            print("[Capture Direct Region] Failed to get Desktop DC.")
            return None
        desktop_mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = desktop_mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(desktop_mfc_dc, width, height)
        mem_dc.SelectObject(bitmap)
        mem_dc.BitBlt((0, 0), (width, height), desktop_mfc_dc, (left, top), win32con.SRCCOPY)
        bmp_info = bitmap.GetInfo()
        bmp_str = bitmap.GetBitmapBits(True)
        if not bmp_str or len(bmp_str) != bmp_info['bmWidthBytes'] * bmp_info['bmHeight']:
            print("[Capture Direct Region] Error: Invalid bitmap data.")
            return None
        img = np.frombuffer(bmp_str, dtype='uint8')
        img.shape = (height, width, 4)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        end_time = time.perf_counter()
        if LOG_CAPTURE_DETAILS:
            print(f"[Capture Direct Region] Success. Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")
        return img_bgr
    except Exception as e:
        print(f"Direct screen region capture error: {e}")
        return None
    finally:
        try:
            if bitmap:
                win32gui.DeleteObject(bitmap.GetHandle())
        except:
            pass
        try:
            if mem_dc:
                mem_dc.DeleteDC()
        except:
            pass
        try:
            if desktop_dc:
                win32gui.ReleaseDC(0, desktop_dc)
        except:
            pass

def capture_screen_region_mss(region):
    start_time = time.perf_counter()
    try:
        if region["width"] <= 0 or region["height"] <= 0:
            return None
        with mss.mss() as sct:
            img_mss = sct.grab(region)
        img_bgra = np.array(img_mss, dtype=np.uint8)
        img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
        end_time = time.perf_counter()
        return img_bgr
    except Exception as e:
        print(f"MSS screen region capture error: {e}")
        return None

def capture_screen_region(region):
    if not all(k in region for k in ("left", "top", "width", "height")):
        print("[Capture Region] Error: Invalid region format.")
        return None
    if region["width"] <= 0 or region["height"] <= 0:
        print("[Capture Region] Error: Invalid region dimensions.")
        return None
    frame = capture_screen_region_direct(region)
    if frame is None:
        if LOG_CAPTURE_DETAILS:
            print("[Capture Region] Direct capture failed, trying MSS fallback...")
        frame = capture_screen_region_mss(region)
        if frame is None and LOG_CAPTURE_DETAILS:
            print("[Capture Region] MSS capture also failed.")
    if frame is not None and (frame.shape[0] < 1 or frame.shape[1] < 1):
        print(f"[Capture Region] Warning: Captured frame seems invalid ({frame.shape}).")
        return None
    return frame

def capture_window(hwnd):
    if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
        return None
    frame = capture_window_direct(hwnd)
    if frame is None:
        if LOG_CAPTURE_DETAILS:
            print("Direct window capture failed, trying MSS fallback...")
        frame = capture_window_mss(hwnd)
        if frame is None and LOG_CAPTURE_DETAILS:
            print("MSS window capture also failed.")
    if frame is not None and (frame.shape[0] < 10 or frame.shape[1] < 10):
        return None
    return frame
