# -*- coding: utf-8 -*-
"""최근 만든 GIF 기록 — 다시 변환하지 않고 클립보드로 바로 꺼내 쓰기 위한 목록.

같은 리액션 GIF를 여러 번 올리게 되는데, 그때마다 탐색기에서 찾는 게 번거로워
최근 결과를 파일 하나에 적어둡니다. (%APPDATA%\\GifBox\\history.json)
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .settings import config_dir

LIMIT = 40


@dataclass
class Entry:
    path: str
    name: str = ""
    size: int = 0
    when: str = ""            # ISO 문자열
    origin: str = ""          # 웹에서 왔다면 원래 주소
    preset: str = ""

    @property
    def icon(self):
        """목록에 붙일 기호 — 어디서 왔는지 한눈에."""
        if not Path(self.path).exists():
            return "⚠"
        return "🌐" if self.origin else "📁"

    @property
    def exists(self):
        return Path(self.path).exists()

    def title(self, human=None):
        size = (" · %s" % human(self.size)) if human and self.size else ""
        return "%s %s%s" % (self.icon, self.name or Path(self.path).name, size)


def history_path() -> Path:
    return config_dir() / "history.json"


def load():
    try:
        with open(history_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for row in raw if isinstance(raw, list) else []:
        if isinstance(row, dict) and row.get("path"):
            out.append(Entry(**{k: v for k, v in row.items()
                                if k in Entry.__dataclass_fields__}))
    return out


def save(entries):
    path = history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in entries[:LIMIT]], f,
                      ensure_ascii=False, indent=2)
        tmp.replace(path)
        return True
    except OSError:
        return False


def add(results, preset=""):
    """변환 결과를 기록 맨 앞에 넣는다. 같은 경로는 위로 끌어올린다."""
    entries = load()
    known = {e.path for e in entries}
    fresh = []
    for r in results:
        if not r.ok or not r.dst:
            continue
        path = str(r.dst)
        if path in known:
            entries = [e for e in entries if e.path != path]
        fresh.append(Entry(path=path, name=r.dst.name, size=r.dst_size,
                           when=datetime.now().isoformat(timespec="seconds"),
                           origin=r.origin, preset=preset))
    if not fresh:
        return entries
    entries = fresh[::-1] + entries
    entries = entries[:LIMIT]
    save(entries)
    return entries


def prune():
    """파일이 사라진 항목을 걷어낸다."""
    entries = [e for e in load() if e.exists]
    save(entries)
    return entries


def clear():
    save([])
    return []
