# -*- coding: utf-8 -*-
"""Windows 클립보드 — 파일 복사(CF_HDROP) / 이미지 복사(CF_DIB) / 붙여넣기.

GIF는 '파일'로 복사하는 게 기본입니다. 이미지(CF_DIB)로 넣으면 받는 쪽이
첫 프레임짜리 정지 이미지로 붙여넣어 애니메이션이 죽기 때문입니다.
카카오톡·디스코드·슬랙·탐색기·워드 모두 파일 붙여넣기를 지원합니다.
"""

import ctypes
import io
import sys
from ctypes import wintypes
from pathlib import Path

CF_DIB = 8
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT,
                                       wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT

    class DROPFILES(ctypes.Structure):
        _fields_ = [
            ("pFiles", wintypes.DWORD),
            ("pt", wintypes.POINT),
            ("fNC", wintypes.BOOL),
            ("fWide", wintypes.BOOL),
        ]


class ClipboardError(RuntimeError):
    pass


class _Clipboard:
    """with 문으로 열고 닫는 클립보드. 다른 앱이 잡고 있으면 잠깐 재시도."""

    def __init__(self, tries=10, delay=0.05):
        self.tries = tries
        self.delay = delay

    def __enter__(self):
        import time
        for _ in range(self.tries):
            if user32.OpenClipboard(None):
                return self
            time.sleep(self.delay)
        raise ClipboardError("클립보드를 다른 프로그램이 사용 중입니다")

    def __exit__(self, *exc):
        user32.CloseClipboard()
        return False


def _global_from_bytes(payload: bytes):
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        raise ClipboardError("메모리 할당 실패")
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        kernel32.GlobalFree(handle)
        raise ClipboardError("메모리 잠금 실패")
    try:
        ctypes.memmove(ptr, payload, len(payload))
    finally:
        kernel32.GlobalUnlock(handle)
    return handle


def _hdrop_bytes(paths):
    names = "\0".join(str(Path(p).resolve()) for p in paths) + "\0\0"
    tail = names.encode("utf-16-le")
    head = DROPFILES()
    head.pFiles = ctypes.sizeof(DROPFILES)
    head.fWide = True
    return ctypes.string_at(ctypes.byref(head), ctypes.sizeof(head)) + tail


def _dib_bytes(path):
    """첫 프레임을 CF_DIB로. BMP 저장 후 14바이트 파일 헤더를 떼면 DIB."""
    from PIL import Image

    with Image.open(path) as im:
        im.seek(0)
        rgb = im.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, "BMP")
    return buf.getvalue()[14:]


def copy_files(paths, mode="file"):
    """paths 를 클립보드에 올린다.

    mode: file(권장) | image(첫 프레임 정지 이미지) | both
    반환: 실제로 올린 포맷 이름 리스트
    """
    if not _IS_WIN:
        raise ClipboardError("Windows에서만 지원합니다")
    paths = [Path(p) for p in paths]
    if not paths:
        return []

    formats = []
    with _Clipboard():
        user32.EmptyClipboard()

        if mode in ("file", "both"):
            handle = _global_from_bytes(_hdrop_bytes(paths))
            if user32.SetClipboardData(CF_HDROP, handle):
                formats.append("파일")
            else:
                kernel32.GlobalFree(handle)

        if mode in ("image", "both"):
            try:
                handle = _global_from_bytes(_dib_bytes(paths[-1]))
            except Exception:
                handle = None
            if handle:
                if user32.SetClipboardData(CF_DIB, handle):
                    formats.append("이미지")
                else:
                    kernel32.GlobalFree(handle)

    if not formats:
        raise ClipboardError("클립보드에 넣지 못했습니다")
    return formats


def paste_files():
    """클립보드에 복사된 파일 목록을 읽어온다 (탐색기에서 Ctrl+C 한 것 등)."""
    if not _IS_WIN:
        return []
    if not user32.IsClipboardFormatAvailable(CF_HDROP):
        return []

    out = []
    with _Clipboard():
        handle = user32.GetClipboardData(CF_HDROP)
        if not handle:
            return []
        count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
        for i in range(count):
            length = shell32.DragQueryFileW(handle, i, None, 0)
            buf = ctypes.create_unicode_buffer(length + 1)
            shell32.DragQueryFileW(handle, i, buf, length + 1)
            if buf.value:
                out.append(Path(buf.value))
    return out
