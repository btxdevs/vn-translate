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
        if not (win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) and not win32gui.IsIconic(hwnd)):
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
            return None, None
        process_handle = None
        try:
            process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        except Exception:
            try:
                process_handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid
                )
            except Exception:
                return None, None
        if not process_handle:
            return None, None
        try:
            exe_path = win32process.GetModuleFileNameEx(process_handle, 0)
            if not exe_path or not os.path.exists(exe_path):
                return None, None
            file_size = os.path.getsize(exe_path)
            return exe_path, file_size
        except Exception:
            return None, None
        finally:
            if process_handle:
                win32api.CloseHandle(process_handle)
    except Exception:
        return None, None


def get_window_rect(hwnd):
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception:
        return None


def get_client_rect(hwnd):
    try:
        if not win32gui.IsWindow(hwnd):
            return None
        client_rect_rel = win32gui.GetClientRect(hwnd)
        pt_tl = wintypes.POINT(client_rect_rel[0], client_rect_rel[1])
        pt_br = wintypes.POINT(client_rect_rel[2], client_rect_rel[3])
        if not windll.user32.ClientToScreen(hwnd, byref(pt_tl)):
            return None
        if not windll.user32.ClientToScreen(hwnd, byref(pt_br)):
            return None
        return (pt_tl.x, pt_tl.y, pt_br.x, pt_br.y)
    except Exception:
        return None


def capture_window_direct(hwnd):
    save_bitmap = save_dc = mfc_dc = hwnd_dc = None
    try:
        target_rect = get_client_rect(hwnd)
        rect_type = "Client"
        if target_rect is None:
            target_rect = get_window_rect(hwnd)
            rect_type = "Window"
            if target_rect is None:
                return None
        left, top, right, bottom = target_rect
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc:
            return None
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)
        print_window_flag = 0x1 | 0x2 if rect_type == "Client" else 0x2
        result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), print_window_flag)
        if not result:
            src_x = src_y = 0
            if rect_type == "Client":
                window_rect = win32gui.GetWindowRect(hwnd)
                src_x = left - window_rect[0]
                src_y = top - window_rect[1]
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (src_x, src_y), win32con.SRCCOPY)
        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        if not bmp_str or len(bmp_str) != bmp_info["bmWidthBytes"] * bmp_info["bmHeight"]:
            return None
        img = np.frombuffer(bmp_str, dtype="uint8")
        img.shape = (bmp_info["bmHeight"], bmp_info["bmWidth"], 4)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img_bgr
    except Exception:
        return None
    finally:
        try:
            if save_bitmap:
                win32gui.DeleteObject(save_bitmap.GetHandle())
        except Exception:
            pass
        try:
            if save_dc:
                save_dc.DeleteDC()
        except Exception:
            pass
        try:
            if mfc_dc:
                mfc_dc.DeleteDC()
        except Exception:
            pass
        try:
            if hwnd_dc and hwnd:
                win32gui.ReleaseDC(hwnd, hwnd_dc)
        except Exception:
            pass


def capture_window_mss(hwnd):
    try:
        target_rect = get_client_rect(hwnd)
        rect_type = "Client"
        if target_rect is None:
            target_rect = get_window_rect(hwnd)
            rect_type = "Window"
            if target_rect is None:
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
        return img_bgr
    except Exception:
        return None


def capture_screen_region_direct(region):
    desktop_dc = mem_dc = bitmap = None
    try:
        left, top, width, height = region["left"], region["top"], region["width"], region["height"]
        if width <= 0 or height <= 0:
            return None
        desktop_dc = win32gui.GetDC(0)
        if not desktop_dc:
            return None
        desktop_mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = desktop_mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(desktop_mfc_dc, width, height)
        mem_dc.SelectObject(bitmap)
        mem_dc.BitBlt((0, 0), (width, height), desktop_mfc_dc, (left, top), win32con.SRCCOPY)
        bmp_info = bitmap.GetInfo()
        bmp_str = bitmap.GetBitmapBits(True)
        if not bmp_str or len(bmp_str) != bmp_info["bmWidthBytes"] * bmp_info["bmHeight"]:
            return None
        img = np.frombuffer(bmp_str, dtype="uint8")
        img.shape = (height, width, 4)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img_bgr
    except Exception:
        return None
    finally:
        try:
            if bitmap:
                win32gui.DeleteObject(bitmap.GetHandle())
        except Exception:
            pass
        try:
            if mem_dc:
                mem_dc.DeleteDC()
        except Exception:
            pass
        try:
            if desktop_dc:
                win32gui.ReleaseDC(0, desktop_dc)
        except Exception:
            pass


def capture_screen_region_mss(region):
    try:
        if region["width"] <= 0 or region["height"] <= 0:
            return None
        with mss.mss() as sct:
            img_mss = sct.grab(region)
        img_bgra = np.array(img_mss, dtype=np.uint8)
        img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
        return img_bgr
    except Exception:
        return None


def capture_screen_region(region):
    if not all(k in region for k in ("left", "top", "width", "height")):
        return None
    if region["width"] <= 0 or region["height"] <= 0:
        return None
    frame = capture_screen_region_direct(region)
    if frame is None:
        frame = capture_screen_region_mss(region)
    if frame is not None and (frame.shape[0] < 1 or frame.shape[1] < 1):
        return None
    return frame


def capture_window(hwnd):
    if (
            not hwnd
            or not win32gui.IsWindow(hwnd)
            or not win32gui.IsWindowVisible(hwnd)
            or win32gui.IsIconic(hwnd)
    ):
        return None
    frame = capture_window_direct(hwnd)
    if frame is None:
        frame = capture_window_mss(hwnd)
    if frame is not None and (frame.shape[0] < 10 or frame.shape[1] < 10):
        return None
    return frame