# -*- coding: utf-8 -*-
"""즐겨찾기 — 자주 가는 사이트를 기본 브라우저로 연다.

창 안에 웹뷰를 심지 않고 기본 브라우저를 부릅니다. 로그인 세션과 확장
프로그램이 그대로 살아 있고, exe 가 커지지도 않기 때문입니다.
GifBox 를 '항상 위'로 띄워두면 브라우저에서 이미지를 끌어다 바로 떨어뜨릴 수
있어서, 결국 이쪽이 하려던 일에 더 잘 맞습니다.

목록은 설정(JSON)에 그대로 저장됩니다. 항목 하나는 {"name", "url", "icon"}.
"""

import re
import webbrowser
from urllib.parse import urlparse

#: 처음 실행할 때 들어가 있는 목록 (디스코드에 GIF 올리는 흐름 기준)
DEFAULTS = [
    {"name": "디스코드", "url": "https://discord.com/app", "icon": "🎮"},
    {"name": "텐서", "url": "https://tenor.com", "icon": "🔍"},
    {"name": "기피", "url": "https://giphy.com", "icon": "✨"},
    {"name": "유튜브", "url": "https://www.youtube.com", "icon": "▶"},
]

MAX = 12

#: 앞에 붙은 스킴을 가려내기 위한 것 (RFC 3986 형태)
SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")


def normalize_url(url):
    """사용자가 'tenor.com' 처럼 적어도 열리도록 스킴을 붙여준다.

    스킴이 이미 있는데 http/https 가 아니면(javascript:, file: 등) 그냥 버립니다.
    '://' 만 보고 판단하면 javascript:alert(1) 이 https://javascript:alert(1) 로
    둔갑해 저장되므로, 스킴 자체를 정규식으로 가려냅니다.
    """
    url = (url or "").strip()
    if not url:
        return ""

    found = SCHEME.match(url)
    if found and found.group(1).lower() not in ("http", "https"):
        # 'localhost:8080' 처럼 뒤가 포트 숫자면 스킴이 아니라 host:port 다
        rest = url[found.end():]
        if rest[:1].isdigit():
            found = None
        else:
            return ""
    if not found:
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    try:
        host = parsed.hostname
        parsed.port                     # 포트가 숫자가 아니면 여기서 ValueError
    except ValueError:
        return ""
    if not host:
        return ""
    return url


def clean(items):
    """저장된 목록을 믿을 수 있는 형태로 다듬는다."""
    out = []
    for row in items or []:
        if not isinstance(row, dict):
            continue
        url = normalize_url(row.get("url"))
        if not url:
            continue
        name = str(row.get("name") or "").strip() or urlparse(url).netloc
        icon = str(row.get("icon") or "").strip()[:2]
        out.append({"name": name[:20], "url": url, "icon": icon})
        if len(out) >= MAX:
            break
    return out


def label(item):
    icon = item.get("icon") or ""
    return ("%s %s" % (icon, item["name"])).strip()


def open_site(item_or_url):
    """기본 브라우저로 연다. 열지 못하면 False."""
    url = item_or_url if isinstance(item_or_url, str) else item_or_url.get("url")
    url = normalize_url(url)
    if not url:
        return False
    try:
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False
