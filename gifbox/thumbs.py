# -*- coding: utf-8 -*-
"""'최근' 탭에 보여줄 썸네일 만들기 · 캐시.

목록에서 파일 이름만 보고 어떤 GIF인지 떠올리기는 어렵습니다. 첫 프레임을
작게 구워 캐시해두고(%APPDATA%\\GifBox\\thumbs), 마우스를 올리면 원본에서
프레임을 읽어 움직이게 합니다.

캐시 키에 파일의 수정시각·크기를 넣으므로, 같은 이름으로 내용이 바뀌면
자동으로 다시 굽습니다.
"""

import hashlib
from pathlib import Path

from .settings import config_dir

SIZE = 96                  # 썸네일 한 변 (정사각형 칸에 letterbox)
BG = (43, 45, 49)          # 남는 여백 색 — 창 테마(bg_alt)와 맞춘다
HOVER_MAX_FRAMES = 48      # 마우스 올렸을 때 재생할 최대 프레임
HOVER_MIN_DELAY = 40       # ms


def thumb_dir() -> Path:
    d = config_dir() / "thumbs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(path: Path, size, bg):
    try:
        stat = path.stat()
        stamp = "%d-%d" % (stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = "none"
    # 여백 색도 키에 넣는다 — 테마가 바뀌면 예전 썸네일을 그대로 쓰면 안 된다
    raw = "%s|%s|%d|%s" % (path.resolve(), stamp, size, bg)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _fit(img, size, bg=BG):
    """비율 유지하며 정사각형 칸 가운데에 놓는다."""
    from PIL import Image

    img = img.convert("RGBA")
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), bg + (255,))
    canvas.alpha_composite(img, ((size - img.width) // 2,
                                 (size - img.height) // 2))
    return canvas.convert("RGB")


def get_thumb(path, size=SIZE, bg=BG):
    """첫 프레임 썸네일 파일 경로. 만들 수 없으면 None."""
    from PIL import Image

    path = Path(path)
    if not path.is_file():
        return None

    out = thumb_dir() / (cache_key(path, size, bg) + ".png")
    if out.is_file():
        return out
    try:
        with Image.open(path) as im:
            im.seek(0)
            thumb = _fit(im, size, bg)
        tmp = out.with_suffix(".png.tmp")
        thumb.save(tmp, "PNG")
        tmp.replace(out)
        return out
    except Exception:
        return None


def load_frames(path, size=SIZE, max_frames=HOVER_MAX_FRAMES, bg=BG):
    """마우스 올렸을 때 재생할 프레임들. [(PIL.Image, 지연ms), …]"""
    from PIL import Image, ImageSequence

    path = Path(path)
    if not path.is_file():
        return []
    try:
        out = []
        with Image.open(path) as im:
            total = getattr(im, "n_frames", 1)
            if total <= 1:
                return []
            # 프레임이 아주 많으면 건너뛰며 읽어 부담을 줄인다
            step = max(1, total // max_frames + (1 if total % max_frames else 0))
            for i, frame in enumerate(ImageSequence.Iterator(im)):
                if i % step:
                    continue
                delay = max(HOVER_MIN_DELAY,
                            (frame.info.get("duration", 0) or 100) * step)
                out.append((_fit(frame, size, bg), delay))
                if len(out) >= max_frames:
                    break
        return out
    except Exception:
        return []


def clear_cache():
    removed = 0
    try:
        for f in thumb_dir().glob("*.png"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
    except OSError:
        pass
    return removed
