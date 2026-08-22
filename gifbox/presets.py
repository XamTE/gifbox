# -*- coding: utf-8 -*-
"""프리셋 레지스트리 — 자주 쓰는 설정 묶음.

새 프리셋은 Preset 하나 만들어 register_preset 에 넘기면 GUI 목록과 CLI
--preset 에 자동으로 나타납니다. values 에는 settings.DEFAULTS 의 키만 넣습니다.

    register_preset(Preset(
        name="twitter", label="트위터용", icon="🐦",
        description="15MB 이하 · 가로 640",
        values={"target_mb": 15, "width": 640, "fps": 15},
    ))
"""

from dataclasses import dataclass, field

_PRESETS = []


@dataclass
class Preset:
    name: str
    label: str
    icon: str = "●"                       # 목록에 함께 보여줄 기호
    description: str = ""
    values: dict = field(default_factory=dict)

    @property
    def title(self):
        return "%s %s" % (self.icon, self.label)


def register_preset(preset):
    _PRESETS.append(preset)
    return preset


def all_presets():
    return list(_PRESETS)


def get_preset(name):
    name = (name or "").strip().lower()
    for p in _PRESETS:
        if name in (p.name, p.label.lower(), p.title.lower()):
            return p
    return None


def apply_preset(settings, name):
    """설정에 프리셋 값을 덮어쓴다. 없는 이름이면 False."""
    preset = get_preset(name)
    if preset is None:
        return False
    settings.update(preset.values)
    settings.normalize()
    return True


# ---------------------------------------------------------------- 기본 프리셋

register_preset(Preset(
    name="discord", label="디스코드용", icon="🎮",
    description="10MB 이하 · 가로 480 · 15fps",
    values={"target_mb": 10, "width": 480, "fps": 15, "colors": 256,
            "reencode_gif": False},
))

register_preset(Preset(
    name="discord_emoji", label="디스코드 이모지", icon="😀",
    description="256KB 이하 · 128×128",
    values={"target_mb": 0.25, "width": 128, "fps": 15, "colors": 128,
            "reencode_gif": True},
))

register_preset(Preset(
    name="light", label="초경량", icon="⚡",
    description="2MB 이하 · 가로 320 · 10fps",
    values={"target_mb": 2, "width": 320, "fps": 10, "colors": 64,
            "reencode_gif": False},
))

register_preset(Preset(
    name="high", label="고화질", icon="💎",
    description="용량 제한 없음 · 원본 크기 · 24fps",
    values={"target_mb": 0, "width": 0, "fps": 24, "colors": 256,
            "reencode_gif": False},
))
