# -*- coding: utf-8 -*-
"""새 버전이 나왔는지 GitHub 릴리스를 확인하고, 받아오기까지.

**받은 파일로 자기 자신을 덮어쓰지는 않습니다.** 실행 중인 exe 는 윈도우가
잠가두기 때문에 도우미 프로세스로 교체해야 하는데, 중간에 실패하면 설치가
깨지고 서명 없는 exe 의 자기 교체는 백신이 정확히 잡는 패턴이기도 합니다.
그래서 여기서는 **내려받아 탐색기로 열어주는 데까지만** 하고, 파일을 바꾸는
마지막 한 걸음은 사람이 합니다.

받은 파일은 릴리스에 함께 올라온 SHA256SUMS.txt 로 검증합니다.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from . import APP_NAME, __version__

REPO = "XamTE/gifbox"
API = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASES_PAGE = "https://github.com/%s/releases/latest" % REPO
CHECKSUM_ASSET = "SHA256SUMS.txt"

CHECK_INTERVAL = 24 * 60 * 60          # 하루 한 번이면 충분하다
TIMEOUT = 10
MAX_ASSET_MB = 400

_NUM = re.compile(r"\d+")


def parse_version(text):
    """'v1.2.0' -> (1, 2, 0). 못 읽으면 (0,)."""
    nums = _NUM.findall(str(text or ""))
    return tuple(int(n) for n in nums) or (0,)


def is_newer(remote, local=None):
    return parse_version(remote) > parse_version(local or __version__)


def _get(url, timeout=TIMEOUT, accept="application/vnd.github+json"):
    req = Request(url, headers={
        "User-Agent": "%s/%s" % (APP_NAME, __version__),
        "Accept": accept,
    })
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def should_check(settings):
    """하루가 지났는지. 설정에서 껐으면 아예 안 본다."""
    if not settings.get("check_updates", True):
        return False
    try:
        last = float(settings.get("last_update_check") or 0)
    except (TypeError, ValueError):
        last = 0
    return (time.time() - last) >= CHECK_INTERVAL


def check(timeout=TIMEOUT):
    """최신 릴리스 정보. 실패하면 None (조용히 넘어가라는 뜻)."""
    try:
        data = json.loads(_get(API, timeout).decode("utf-8"))
    except Exception:
        return None

    tag = data.get("tag_name") or ""
    if not tag:
        return None
    assets = [{"name": a.get("name", ""),
               "url": a.get("browser_download_url", ""),
               "size": int(a.get("size") or 0)}
              for a in data.get("assets", []) if a.get("browser_download_url")]

    published = data.get("published_at") or ""
    try:
        when = datetime.fromisoformat(published.replace("Z", "+00:00"))
        when = when.astimezone().strftime("%Y-%m-%d")
    except ValueError:
        when = published[:10]

    return {
        "tag": tag,
        "version": tag.lstrip("v"),
        "newer": is_newer(tag),
        "published": when,
        "page": data.get("html_url") or RELEASES_PAGE,
        "notes": data.get("body") or "",
        "assets": assets,
    }


def running_flavor():
    """지금 돌고 있는 게 ffmpeg 를 품은 빌드인지.

    번들 안(_MEI…)의 ffmpeg 를 쓰고 있으면 full 빌드다. 같은 종류를 받도록
    기본값을 맞춰주기 위한 판단이다.
    """
    from .converters import find_ffmpeg

    found = find_ffmpeg() or ""
    return "full" if "_MEI" in found else "slim"


def pick_asset(assets, flavor=None):
    """내려받을 자산 하나 고르기. 지금 쓰는 것과 같은 종류를 우선."""
    exes = [a for a in assets if a["name"].lower().endswith(".exe")]
    if not exes:
        return None
    want_full = (flavor or running_flavor()) == "full"
    for asset in exes:
        if ("full" in asset["name"].lower()) == want_full:
            return asset
    return exes[0]


def fetch_checksums(assets):
    """릴리스에 함께 올라온 SHA256SUMS.txt 를 {파일이름: 해시} 로."""
    for asset in assets:
        if asset["name"] == CHECKSUM_ASSET:
            try:
                text = _get(asset["url"], accept="*/*").decode("utf-8")
            except Exception:
                return {}
            out = {}
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 2 and len(parts[0]) == 64:
                    out[parts[-1].lstrip("*")] = parts[0].lower()
            return out
    return {}


def default_download_dir() -> Path:
    home = Path.home()
    downloads = home / "Downloads"
    return downloads if downloads.is_dir() else home


def download(asset, dest_dir=None, expected_sha256=None, progress=None,
             timeout=60):
    """자산을 내려받아 경로를 돌려준다. 해시가 어긋나면 지우고 예외."""
    import hashlib

    dest_dir = Path(dest_dir) if dest_dir else default_download_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / asset["name"]
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        for i in range(1, 100):
            cand = dest_dir / ("%s (%d)%s" % (stem, i, suffix))
            if not cand.exists():
                dest = cand
                break

    total = asset.get("size") or 0
    if total > MAX_ASSET_MB * 1024 * 1024:
        raise RuntimeError("파일이 너무 큽니다 (%dMB 제한)" % MAX_ASSET_MB)

    digest = hashlib.sha256()
    got = 0
    req = Request(asset["url"], headers={
        "User-Agent": "%s/%s" % (APP_NAME, __version__), "Accept": "*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                got += len(chunk)
                digest.update(chunk)
                f.write(chunk)
                if progress:
                    progress(got, total)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
        dest.unlink(missing_ok=True)
        raise RuntimeError("받은 파일이 온전하지 않습니다 (체크섬 불일치)")
    return dest
