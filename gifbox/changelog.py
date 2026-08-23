# -*- coding: utf-8 -*-
"""CHANGELOG.md 에서 특정 버전의 항목만 뽑아온다.

패치노트를 GitHub 에서 받아오지 않고 exe 에 동봉한 파일에서 읽습니다.
네트워크가 없어도 보이고, 무엇보다 **지금 실행 중인 빌드의 내용**과 항상
일치하기 때문입니다(받아오면 이미 새 버전이 나와 있을 때 엉뚱한 걸 보여줌).
"""

import re

from . import __version__
from .winutil import resource_path

HEADING = re.compile(r"^##\s+v?(\S+)\s*$")


def changelog_path():
    return resource_path("CHANGELOG.md")


def load_text():
    try:
        return changelog_path().read_text(encoding="utf-8")
    except OSError:
        return ""


def sections(text=None):
    """[(버전, 본문), …] 을 파일에 적힌 순서대로."""
    text = load_text() if text is None else text
    out = []
    version = None
    body = []
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            if version is not None:
                out.append((version, "\n".join(body).strip()))
            version = m.group(1)
            body = []
        elif version is not None:
            body.append(line)
    if version is not None:
        out.append((version, "\n".join(body).strip()))
    return out


def for_version(version=None):
    """해당 버전의 본문. 없으면 빈 문자열."""
    want = (version or __version__).lstrip("v")
    for found, body in sections():
        if found.lstrip("v") == want:
            return body
    return ""


def latest():
    """파일 맨 위 항목 (버전, 본문)."""
    found = sections()
    return found[0] if found else ("", "")
