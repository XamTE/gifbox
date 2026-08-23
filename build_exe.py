# -*- coding: utf-8 -*-
r"""GifBox 를 exe 로 묶는다.

    python build_exe.py                  # dist\GifBox.exe 한 개 (권장)
    python build_exe.py --with-ffmpeg    # ffmpeg 까지 넣어 어디서든 동작
    python build_exe.py --onedir         # 폴더 형태 (실행이 더 빠름)
    python build_exe.py --cli            # 콘솔용 to_gif.exe 도 함께

ffmpeg 를 넣지 않아도, exe 는 실행할 때 아래 순서로 알아서 찾습니다.
    PATH → exe 옆의 ffmpeg.exe → winget 설치 경로 → imageio-ffmpeg
따라서 내 PC에서 쓸 거면 굳이 넣을 필요가 없고(용량 절약),
ffmpeg 없는 PC에 건네줄 거면 --with-ffmpeg 로 묶으면 됩니다.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    # CI 콘솔(cp1252)에서 한글 print 가 터지지 않게
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON = ROOT / "assets" / "GifBox.ico"

# 안 쓰는데 딸려 들어와 용량만 키우는 것들
EXCLUDES = ["numpy", "scipy", "matplotlib", "pandas", "PyQt5", "PyQt6",
            "PySide2", "PySide6", "pytest", "setuptools", "pip",
            "IPython", "notebook", "sqlite3", "unittest", "pydoc"]


def ensure_icon():
    if ICON.exists():
        return True
    print("아이콘이 없어 새로 만듭니다…")
    r = subprocess.run([sys.executable, str(ROOT / "make_icon.py")])
    return r.returncode == 0 and ICON.exists()


def find_ffmpeg_exe():
    sys.path.insert(0, str(ROOT))
    from gifbox.converters import find_ffmpeg
    return find_ffmpeg()


def run_pyinstaller(entry, name, windowed, args):
    cmd = [sys.executable, "-m", "PyInstaller",
           "--noconfirm", "--clean",
           "--name", name,
           "--distpath", str(DIST),
           "--workpath", str(BUILD),
           "--specpath", str(BUILD),
           "--collect-all", "tkinterdnd2",       # tkdnd 바이너리가 같이 가야 함
           ]
    cmd += ["--onedir"] if args.onedir else ["--onefile"]
    cmd += ["--windowed"] if windowed else ["--console"]

    if ICON.exists():
        cmd += ["--icon", str(ICON), "--add-data", "%s;assets" % ICON]

    # 패치노트는 exe 에 넣는다 — 네트워크 없이도, 지금 이 빌드의 내용으로 보이게
    changelog = ROOT / "CHANGELOG.md"
    if changelog.exists():
        cmd += ["--add-data", "%s;." % changelog]

    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]

    if args.with_ffmpeg:
        exe = find_ffmpeg_exe()
        if not exe:
            print("!! ffmpeg 를 찾지 못해 넣지 못했습니다. 설치 후 다시 시도하세요.")
            return None
        # exe 와 같은 위치에 풀리도록 넣는다 (converters.find_ffmpeg 가 여기를 봄)
        cmd += ["--add-binary", "%s;." % exe]
        print("ffmpeg 포함:", exe)

    cmd += [str(entry)]
    print("\n$ " + " ".join(cmd) + "\n")
    if subprocess.run(cmd).returncode != 0:
        return None
    return DIST / (name if args.onedir else name + ".exe")


def human(n):
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f%s" % (size, unit)
        size /= 1024


def main():
    ap = argparse.ArgumentParser(description="GifBox 를 exe 로 빌드합니다.")
    ap.add_argument("--with-ffmpeg", action="store_true",
                    help="ffmpeg 를 함께 넣어 ffmpeg 없는 PC에서도 동작하게 (용량 증가)")
    ap.add_argument("--onedir", action="store_true",
                    help="한 파일 대신 폴더로 (실행 시작이 빠름)")
    ap.add_argument("--cli", action="store_true",
                    help="콘솔용 to_gif.exe 도 함께 빌드")
    args = ap.parse_args()

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller 가 없습니다:  pip install pyinstaller")
        return 1

    ensure_icon()

    made = []
    out = run_pyinstaller(ROOT / "GifBox.pyw", "GifBox", True, args)
    if out is None:
        return 1
    made.append(out)

    if args.cli:
        out = run_pyinstaller(ROOT / "to_gif.py", "to_gif", False, args)
        if out is None:
            return 1
        made.append(out)

    print("\n" + "=" * 50)
    for path in made:
        if path.is_dir():
            total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            print("  %s\\  (%s)" % (path, human(total)))
        else:
            print("  %s  (%s)" % (path, human(path.stat().st_size)))
    print("=" * 50)
    if not args.with_ffmpeg:
        print("ffmpeg 는 넣지 않았습니다. 다른 PC에 줄 거라면 --with-ffmpeg 를 쓰거나,")
        print("ffmpeg.exe 를 GifBox.exe 옆에 그냥 복사해두어도 됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
