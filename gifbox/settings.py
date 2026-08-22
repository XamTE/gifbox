# -*- coding: utf-8 -*-
"""설정 저장/불러오기.

새 옵션을 추가하려면 DEFAULTS 에 한 줄만 넣으면 됩니다.
(저장·불러오기·기본값 병합이 전부 자동으로 처리됩니다)
"""

import json
import os
from pathlib import Path

from . import APP_NAME

DEFAULTS = {
    # --- 변환 품질 ---
    "fps": 15,                        # 0 또는 None 이면 원본 프레임레이트 유지
    "width": 0,                       # 0 이면 원본 크기 유지
    "colors": 256,                    # 팔레트 색 수 (2~256)
    "dither": "bayer:bayer_scale=5",  # ffmpeg 디더링
    "reencode_gif": False,            # 이미 GIF인 입력도 다시 인코딩할지(용량 줄일 때)

    # --- 구간 자르기 ("0:12", "4" 형식. 비우면 전체) ---
    "trim_start": "",
    "trim_duration": "",

    # --- 목표 용량 ---
    "target_mb": 10,                  # 0이면 제한 없음
    "target_tries": 4,                # 목표에 맞추려 다시 시도할 최대 횟수

    # --- 출력 위치 ---
    "outdir": "",                     # 비우면 원본과 같은 폴더
    "web_outdir": "",                 # 웹에서 받은 것의 결과 위치 (비우면 내려받기\GifBox)
    "overwrite": False,               # 같은 이름이 있으면 덮어쓸지

    # --- 웹에서 가져오기 ---
    "max_download_mb": 200,           # 이보다 큰 파일은 받지 않음
    "download_timeout": 20,           # 초

    # --- 변환 후 동작 (actions.py 의 Action.name 과 이름이 맞물립니다) ---
    "copy_to_clipboard": True,
    "clipboard_mode": "file",         # file | image | both
    "delete_original": True,
    "delete_mode": "trash",           # trash | purge
    "open_folder_after": False,

    # --- 창 상태 ---
    "always_on_top": True,
    "geometry": "",

    # --- 프리셋 / 기록 ---
    "preset": "discord",              # 마지막으로 고른 프리셋
    "keep_history": True,
}

_RANGES = {
    "colors": (2, 256),
    "fps": (0, 120),
    "width": (0, 8192),
    "max_download_mb": (1, 4096),
    "download_timeout": (3, 300),
    "target_tries": (1, 8),
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home()
    return root / APP_NAME


def config_path() -> Path:
    return config_dir() / "settings.json"


class Settings(dict):
    """dict 이면서 s.fps 처럼 속성으로도 읽히는 설정 객체."""

    def __init__(self, data=None):
        super().__init__(DEFAULTS)
        if data:
            # 모르는 키는 버리고, 아는 키만 타입을 맞춰 받는다
            for k, v in data.items():
                if k in DEFAULTS:
                    self[k] = v
        self.normalize()

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value

    def normalize(self):
        for key, (lo, hi) in _RANGES.items():
            try:
                val = int(self.get(key) or 0)
            except (TypeError, ValueError):
                val = DEFAULTS[key]
            self[key] = max(lo, min(hi, val))
        if self.get("clipboard_mode") not in ("file", "image", "both"):
            self["clipboard_mode"] = "file"
        if self.get("delete_mode") not in ("trash", "purge"):
            self["delete_mode"] = "trash"
        for key in ("overwrite", "copy_to_clipboard", "delete_original",
                    "open_folder_after", "always_on_top", "reencode_gif",
                    "keep_history"):
            self[key] = bool(self.get(key))
        for key in ("outdir", "web_outdir", "dither", "geometry",
                    "trim_start", "trim_duration", "preset"):
            self[key] = str(self.get(key) or "")
        try:
            self["target_mb"] = max(0.0, float(self.get("target_mb") or 0))
        except (TypeError, ValueError):
            self["target_mb"] = DEFAULTS["target_mb"]
        return self

    # ------------------------------------------------------------ 입출력

    @classmethod
    def load(cls):
        path = config_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls(json.load(f))
        except (OSError, ValueError):
            return cls()

    def save(self):
        self.normalize()
        path = config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dict(self), f, ensure_ascii=False, indent=2)
            tmp.replace(path)
            return True
        except OSError:
            return False
