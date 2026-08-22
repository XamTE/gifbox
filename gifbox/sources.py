# -*- coding: utf-8 -*-
"""입력 소스 레지스트리 — '끌어다 놓은 것'을 로컬 파일로 바꿔주는 계층.

창에 떨어지는 게 항상 파일 경로인 건 아닙니다. 브라우저에서 이미지를 끌면
URL 문자열이 들어옵니다. 그 차이를 여기서 흡수해서, 파이프라인 뒤쪽은
언제나 '로컬 파일'만 상대하면 되게 합니다.

새 소스를 추가하려면 Source 를 상속하고 @register_source 를 붙입니다.

    @register_source
    class YoutubeSource(Source):
        name = "youtube"
        order = 40                       # 작을수록 먼저 검사
        def matches(self, raw): return "youtube.com/watch" in raw
        def resolve(self, raw, opts, notify=None):
            return [Item(path=download_via_ytdlp(raw), temporary=True, origin=raw)]
"""

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from . import APP_NAME, __version__

_SOURCES = []

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "%s/%s" % (APP_NAME, __version__))

#: Content-Type -> 확장자. 새 포맷을 받으려면 여기에 한 줄 추가.
CONTENT_TYPES = {
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/png": ".png",
    "image/apng": ".apng",
    "image/jpeg": ".jpg",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
    "application/octet-stream": "",      # URL 쪽 확장자를 믿는다
}

_BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class Item:
    """변환 대상 하나. temporary면 처리 후 자동으로 지웁니다."""
    path: Path
    temporary: bool = False
    origin: str = ""          # 원래 URL 등, 로그에 보여줄 출처


class SourceError(RuntimeError):
    pass


class Source:
    name = "base"
    label = ""
    order = 100               # 작을수록 먼저 검사

    def matches(self, raw) -> bool:
        return False

    def resolve(self, raw, opts=None, notify=None):
        """raw 하나를 Item 목록으로. 실패하면 SourceError."""
        raise NotImplementedError


def register_source(cls):
    _SOURCES.append(cls)
    _SOURCES.sort(key=lambda c: c.order)
    return cls


def all_sources():
    return list(_SOURCES)


def pick_source(raw):
    for cls in _SOURCES:
        src = cls()
        if src.matches(raw):
            return src
    return None


def resolve_all(raws, opts=None, notify=None):
    """드롭/인자로 들어온 것들을 전부 로컬 Item 으로 편다.

    반환: (items, errors) — errors 는 사람이 읽을 오류 문자열 목록
    """
    items = []
    errors = []
    for raw in raws:
        raw = raw.strip() if isinstance(raw, str) else raw
        if not raw:
            continue
        src = pick_source(str(raw))
        if src is None:
            errors.append("무엇인지 모르겠습니다: %s" % raw)
            continue
        try:
            items.extend(src.resolve(str(raw), opts, notify))
        except Exception as e:
            errors.append("%s — %s" % (_shorten(str(raw)), e))
    return items, errors


def _shorten(text, limit=60):
    return text if len(text) <= limit else text[:limit - 1] + "…"


# ---------------------------------------------------------------- 로컬 파일

@register_source
class LocalSource(Source):
    name = "local"
    label = "로컬 파일"
    order = 100

    def matches(self, raw):
        if is_url(raw):
            return False
        try:
            return Path(raw).exists()
        except OSError:
            return False

    def resolve(self, raw, opts=None, notify=None):
        return [Item(path=Path(raw))]


# ---------------------------------------------------------------- 웹 URL

def is_url(raw):
    return str(raw).lower().startswith(("http://", "https://"))


def temp_dir() -> Path:
    d = Path(tempfile.gettempdir()) / (APP_NAME.lower() + "-download")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ext_from_url(url):
    name = unquote(urlparse(url).path).rsplit("/", 1)[-1]
    ext = Path(name).suffix.lower()
    return ext if 1 < len(ext) <= 6 else ""


def _name_from_url(url, ext):
    stem = unquote(urlparse(url).path).rsplit("/", 1)[-1]
    stem = _BAD_NAME.sub("_", Path(stem).stem).strip(" .")
    if not stem:
        stem = "download"
    return stem[:60] + ext


@register_source
class UrlSource(Source):
    """브라우저에서 끌어온 이미지/영상 주소를 내려받는다."""

    name = "url"
    label = "웹 주소"
    order = 50

    def matches(self, raw):
        return is_url(raw)

    def resolve(self, raw, opts=None, notify=None):
        limit_mb = getattr(opts, "max_download_mb", 200) or 200
        timeout = getattr(opts, "download_timeout", 20) or 20
        path = self.download(raw, temp_dir(), limit_mb * 1024 * 1024,
                             timeout=timeout, notify=notify)
        return [Item(path=path, temporary=True, origin=raw)]

    # -- 실제 다운로드 --------------------------------------------------

    def download(self, url, dest_dir, max_bytes, timeout=20, notify=None):
        if not is_url(url):
            raise SourceError("http/https 주소만 받습니다")

        req = Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/*,video/*,*/*;q=0.8",
        })

        if notify:
            notify("progress", message="내려받는 중…")

        with urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get_content_type() or "").lower()
            if ctype.startswith("text/") or ctype == "application/xhtml+xml":
                raise SourceError(
                    "이미지가 아니라 웹페이지 주소입니다 "
                    "(이미지에서 우클릭 → '이미지 주소 복사'를 쓰세요)")

            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise SourceError("파일이 너무 큽니다 (%.0fMB 제한)"
                                  % (max_bytes / 1024 / 1024))

            ext = CONTENT_TYPES.get(ctype) or _ext_from_url(url)
            if not ext:
                raise SourceError("형식을 알 수 없습니다 (Content-Type: %s)"
                                  % (ctype or "없음"))

            final_url = resp.geturl()
            dest = _unique(dest_dir / _name_from_url(final_url, ext))
            total = 0
            try:
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise SourceError("파일이 너무 큽니다 (%.0fMB 제한)"
                                              % (max_bytes / 1024 / 1024))
                        f.write(chunk)
                        if notify:
                            notify("progress",
                                   message="내려받는 중… %.1fMB" % (total / 1024 / 1024))
            except Exception:
                dest.unlink(missing_ok=True)
                raise

        if total == 0:
            dest.unlink(missing_ok=True)
            raise SourceError("빈 파일을 받았습니다")
        return dest


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(1, 1000):
        cand = path.with_name("%s_%d%s" % (path.stem, i, path.suffix))
        if not cand.exists():
            return cand
    raise SourceError("임시 파일 이름을 만들지 못했습니다")


def cleanup(items):
    """temporary 로 표시된 임시 파일을 지운다."""
    for it in items:
        if not it.temporary:
            continue
        try:
            Path(it.path).unlink(missing_ok=True)
        except OSError:
            pass


def default_web_outdir() -> Path:
    """웹에서 받은 파일의 GIF 결과를 둘 곳 (원본 폴더라는 게 없으므로)."""
    home = Path(os.path.expanduser("~"))
    downloads = home / "Downloads"
    base = downloads if downloads.is_dir() else home
    out = base / APP_NAME
    return out
