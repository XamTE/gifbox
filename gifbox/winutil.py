# -*- coding: utf-8 -*-
"""Windows 전용 잡일 — 휴지통, 탐색기 열기. (다른 OS에서는 안전하게 대체 동작)"""

import subprocess
import sys
from pathlib import Path


def use_utf8_console():
    """콘솔 출력에 한글을 써도 죽지 않게 한다.

    파이프로 넘기거나 CI처럼 코드페이지가 cp1252 인 곳에서는 print 가
    UnicodeEncodeError 로 터집니다. 못 그리는 글자는 대체 문자로 넘깁니다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def app_dir() -> Path:
    """프로그램이 놓인 폴더.

    exe로 묶였을 때(sys.frozen)는 exe 옆, 스크립트로 돌 때는 프로젝트 루트.
    ffmpeg.exe 를 옆에 두는 배포 방식을 지원하기 위해 필요합니다.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative) -> Path:
    """번들에 같이 넣은 파일(아이콘 등)의 실제 경로.

    PyInstaller onefile 은 실행할 때 임시 폴더에 풀고 sys._MEIPASS 로 알려줍니다.
    """
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root / relative


def send_to_trash(path):
    """휴지통으로 보냄. Windows가 아니면 그냥 삭제."""
    path = Path(path)
    if sys.platform != "win32":
        path.unlink()
        return

    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = str(path.resolve()) + "\0\0"   # 이중 널 종료 필요
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI

    res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if res != 0:
        raise OSError("휴지통 이동 실패 (코드 %s): %s" % (res, path))


def reveal(path):
    """탐색기에서 해당 파일을 선택된 상태로 연다."""
    path = Path(path)
    if sys.platform != "win32":
        return False
    try:
        subprocess.Popen(["explorer", "/select,", str(path.resolve())])
        return True
    except OSError:
        return False


def no_window_kwargs():
    """subprocess 호출 시 콘솔 창이 깜빡이지 않게 하는 인자."""
    if sys.platform != "win32":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": si, "creationflags": 0x08000000}  # CREATE_NO_WINDOW
