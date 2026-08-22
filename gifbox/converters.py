# -*- coding: utf-8 -*-
"""변환 엔진 레지스트리.

새 입력 포맷을 지원하려면 이 파일(또는 아무 모듈)에서 Converter 를 상속하고
@register_converter 를 붙이기만 하면 됩니다. 나머지(선택·폴백·GUI 표시)는
자동으로 따라옵니다.

    @register_converter
    class MyConverter(Converter):
        name = "my"
        extensions = frozenset({".foo"})
        priority = 50
        @classmethod
        def available(cls): return True
        def convert(self, src, dst, opts, progress=None): ...
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .winutil import app_dir, no_window_kwargs, resource_path

VIDEO_EXTS = frozenset({".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".flv", ".wmv"})
IMAGE_EXTS = frozenset({".webp", ".apng", ".png", ".jpg", ".jpeg", ".bmp"})
GIF_EXTS = frozenset({".gif"})

#: 폴더를 훑을 때 자동으로 주워담는 확장자
#: (파일을 직접 끌어다 놓거나 인자로 주면 이 목록과 무관하게 처리합니다)
DEFAULT_EXTS = frozenset({".webp", ".mp4"})

_REGISTRY = []


def parse_time(text):
    """"12", "0:12", "1:02.5" 를 초(float)로. 비었거나 못 읽으면 0."""
    text = str(text or "").strip().replace(",", ".")
    if not text:
        return 0.0
    total = 0.0
    try:
        for part in text.split(":"):
            total = total * 60 + float(part or 0)
    except ValueError:
        return 0.0
    return max(0.0, total)


def format_time(seconds):
    """초를 0:04.5 꼴로. 0이면 빈 문자열."""
    seconds = float(seconds or 0)
    if seconds <= 0:
        return ""
    m, s = divmod(seconds, 60)
    text = "%d:%04.1f" % (m, s) if m else "%g" % round(s, 2)
    return text.rstrip("0").rstrip(".") if "." in text and not m else text


class Converter:
    """변환 엔진 인터페이스."""

    name = "base"
    label = "변환기"
    extensions = frozenset()
    priority = 0                 # 클수록 먼저 선택됨
    is_passthrough = False       # True면 변환이 아니라 그대로 복사한다는 뜻

    @classmethod
    def available(cls):
        """이 엔진을 지금 쓸 수 있는지."""
        return False

    @classmethod
    def handles(cls, path, opts=None):
        return Path(path).suffix.lower() in cls.extensions

    def convert(self, src, dst, opts, progress=None):
        """src -> dst(GIF). 실패하면 예외를 던진다."""
        raise NotImplementedError


def register_converter(cls):
    _REGISTRY.append(cls)
    _REGISTRY.sort(key=lambda c: -c.priority)
    return cls


def all_converters():
    return list(_REGISTRY)


def supported_extensions(only_available=True):
    exts = set()
    for cls in _REGISTRY:
        if not only_available or cls.available():
            exts |= set(cls.extensions)
    return exts


def pick_converter(path, opts=None):
    """해당 파일을 처리할 수 있는 엔진 중 우선순위가 가장 높은 것."""
    for cls in _REGISTRY:
        if cls.handles(path, opts) and cls.available():
            return cls()
    return None


# ---------------------------------------------------------------- 그대로 통과

@register_converter
class PassthroughConverter(Converter):
    """이미 GIF인 입력. 웹에서 끌어온 GIF를 다시 인코딩해 망치지 않도록 그냥 복사한다.

    설정에서 reencode_gif 를 켜면 이 엔진이 빠지고 ffmpeg가 맡아
    fps·가로크기·색상수를 실제로 적용합니다(용량 줄일 때 유용).
    """

    name = "passthrough"
    label = "그대로 저장"
    extensions = GIF_EXTS
    priority = 200
    is_passthrough = True

    @classmethod
    def available(cls):
        return True

    @classmethod
    def handles(cls, path, opts=None):
        if Path(path).suffix.lower() not in cls.extensions:
            return False
        return not getattr(opts, "reencode_gif", False)

    def convert(self, src, dst, opts, progress=None):
        shutil.copyfile(str(src), str(dst))


# ---------------------------------------------------------------- ffmpeg

_ffmpeg_cache = []


def find_ffmpeg():
    """PATH -> exe 옆/번들 안 -> winget 설치 경로 -> imageio-ffmpeg 순으로 탐색."""
    if _ffmpeg_cache:
        return _ffmpeg_cache[0]

    found = shutil.which("ffmpeg")

    if not found:
        # exe 옆에 둔 것과, exe 안에 묶여 임시로 풀린 것(onefile) 둘 다 본다
        roots = [app_dir(), resource_path("")]
        cands = []
        for here in roots:
            cands += [here / "ffmpeg.exe",
                      here / "ffmpeg" / "ffmpeg.exe",
                      here / "ffmpeg" / "bin" / "ffmpeg.exe"]
        for cand in cands:
            if cand.is_file():
                found = str(cand)
                break

    if not found and sys.platform == "win32":
        # winget(Gyan.FFmpeg)은 PATH 갱신 전이면 안 잡히므로 설치 위치를 직접 본다
        local = os.environ.get("LOCALAPPDATA")
        if local:
            base = Path(local) / "Microsoft" / "WinGet" / "Packages"
            for cand in sorted(base.glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe")):
                found = str(cand)
                break

    if not found:
        try:
            import imageio_ffmpeg
            found = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            found = None

    # 반드시 절대 경로로 돌려준다. Windows 의 which 는 현재 폴더에 있으면
    # ".\ffmpeg.EXE" 같은 상대 경로를 주는데, 작업 폴더가 다른 곳에서 쓰이면
    # (빌드 도구, 다른 폴더의 파일 변환) 그대로 깨진다.
    if found:
        try:
            found = str(Path(found).resolve())
        except OSError:
            pass
    _ffmpeg_cache.append(found)
    return found


@register_converter
class FfmpegConverter(Converter):
    """palettegen/paletteuse 2패스. 영상·애니메이션 전부 처리, 색 품질이 좋음."""

    name = "ffmpeg"
    label = "ffmpeg"
    extensions = VIDEO_EXTS | IMAGE_EXTS | GIF_EXTS
    priority = 100

    @classmethod
    def available(cls):
        return find_ffmpeg() is not None

    def build_filter(self, opts):
        parts = []
        if opts.fps:
            parts.append("fps=%s" % opts.fps)
        if opts.width:
            parts.append("scale=%d:-2:flags=lanczos" % opts.width)
        chain = ",".join(parts)
        if chain:
            chain += ","
        return ("%ssplit[a][b];"
                "[a]palettegen=max_colors=%d:stats_mode=diff[p];"
                "[b][p]paletteuse=dither=%s:diff_mode=rectangle"
                % (chain, opts.colors, opts.dither or "none"))

    def convert(self, src, dst, opts, progress=None):
        exe = find_ffmpeg()
        start = parse_time(getattr(opts, "trim_start", ""))
        length = parse_time(getattr(opts, "trim_duration", ""))

        cmd = [exe, "-hide_banner", "-loglevel", "error", "-y"]
        if start:
            # -i 앞의 -ss 는 빠른 탐색. 요즘 ffmpeg는 이 위치에서도 정확하다
            cmd += ["-ss", "%.3f" % start]
        cmd += ["-i", str(src)]
        if length:
            cmd += ["-t", "%.3f" % length]
        cmd += ["-vf", self.build_filter(opts), "-loop", "0", "-f", "gif", str(dst)]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              **no_window_kwargs())
        if proc.returncode != 0:
            msg = (proc.stderr or "").strip().splitlines()
            raise RuntimeError(msg[-1] if msg else "ffmpeg 종료코드 %d" % proc.returncode)


# ---------------------------------------------------------------- Pillow

@register_converter
class PillowConverter(Converter):
    """ffmpeg 없이 애니메이션 webp/png -> gif. 영상은 처리 못함."""

    name = "pillow"
    label = "Pillow"
    extensions = IMAGE_EXTS | GIF_EXTS
    priority = 10

    @classmethod
    def available(cls):
        try:
            import PIL  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, src, dst, opts, progress=None):
        from PIL import Image, ImageSequence

        colors = opts.colors
        with Image.open(src) as im:
            # 구간 자르기 — 프레임 시간을 누적해가며 범위 밖은 건너뛴다
            start_ms = parse_time(getattr(opts, "trim_start", "")) * 1000
            len_ms = parse_time(getattr(opts, "trim_duration", "")) * 1000
            if getattr(im, "n_frames", 1) <= 1:
                start_ms = len_ms = 0        # 정지 이미지에는 적용하지 않는다
            clock = 0.0

            frames = []
            durations = []
            for frame in ImageSequence.Iterator(im):
                step = frame.info.get("duration", 0) or 100
                at, clock = clock, clock + step
                if start_ms and at + step <= start_ms:
                    continue
                if len_ms and at >= start_ms + len_ms:
                    break

                rgba = frame.convert("RGBA")
                if opts.width and rgba.width != opts.width:
                    h = max(1, round(rgba.height * opts.width / rgba.width))
                    rgba = rgba.resize((opts.width, h), Image.LANCZOS)

                alpha = rgba.getchannel("A")
                if alpha.getextrema()[0] < 250:
                    # 마지막 팔레트 인덱스를 투명색으로 예약
                    p = rgba.convert("RGB").quantize(
                        colors=max(2, colors - 1), method=Image.Quantize.MEDIANCUT)
                    mask = alpha.point(lambda a: 255 if a < 128 else 0).convert("1")
                    p.paste(colors - 1, mask)
                    p.info["transparency"] = colors - 1
                else:
                    p = rgba.convert("RGB").quantize(
                        colors=colors, method=Image.Quantize.MEDIANCUT)

                frames.append(p)
                durations.append(frame.info.get("duration", 0) or 0)
                if progress and len(frames) % 20 == 0:
                    progress("%d프레임…" % len(frames))

            if not frames:
                raise RuntimeError("프레임을 읽지 못했습니다")

            if opts.fps:
                durations = [max(20, round(1000 / opts.fps))] * len(frames)
            else:
                durations = [d if d >= 10 else 100 for d in durations]

            kw = dict(save_all=True, append_images=frames[1:], loop=0,
                      duration=durations, disposal=2, optimize=False)
            if "transparency" in frames[0].info:
                kw["transparency"] = frames[0].info["transparency"]
            frames[0].save(dst, format="GIF", **kw)
