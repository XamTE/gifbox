# -*- coding: utf-8 -*-
"""변환이 끝난 뒤 실행되는 동작들 (후처리 훅).

새 동작을 추가하려면 Action 을 상속하고 @register_action 을 붙입니다.
켜고 끄는 스위치는 settings.DEFAULTS 에 키를 하나 넣고 enabled()에서 읽으면 됩니다.

    @register_action
    class UploadAction(Action):
        name = "upload"
        label = "서버에 업로드"
        order = 40
        def enabled(self, opts): return opts.upload
        def run(self, results, opts): ...; return "3개 업로드 완료"

run()에는 '성공한 결과 전체'가 한 번에 들어옵니다. 여러 파일을 한 번에
클립보드에 올리는 것 같은 일괄 처리를 그대로 쓸 수 있게 하기 위함입니다.
"""

_ACTIONS = []


class Action:
    name = "base"
    label = ""
    order = 50          # 작을수록 먼저 실행

    def enabled(self, opts):
        return False

    def run(self, results, opts):
        """성공한 Result 목록을 받아 처리하고, 사용자에게 보여줄 한 줄을 반환."""
        raise NotImplementedError


def register_action(cls):
    _ACTIONS.append(cls)
    _ACTIONS.sort(key=lambda c: c.order)
    return cls


def all_actions():
    return list(_ACTIONS)


def run_actions(results, opts, log=None):
    """성공 결과에 대해 켜져 있는 액션을 순서대로 실행."""
    results = [r for r in results if r.ok]
    if not results:
        return
    for cls in _ACTIONS:
        action = cls()
        try:
            if not action.enabled(opts):
                continue
            msg = action.run(results, opts)
        except Exception as e:
            msg = "%s 실패: %s" % (action.label or action.name, e)
        if msg and log:
            log(msg)


# ---------------------------------------------------------------- 기본 액션

@register_action
class HistoryAction(Action):
    """만든 GIF를 최근 목록에 적어둔다 (창의 '최근' 탭에서 바로 다시 복사)."""

    name = "history"
    label = "기록"
    order = 5

    def enabled(self, opts):
        return bool(getattr(opts, "keep_history", True))

    def run(self, results, opts):
        from . import history

        history.add(results, preset=getattr(opts, "preset", ""))
        return None


@register_action
class ClipboardAction(Action):
    name = "clipboard"
    label = "클립보드 복사"
    order = 10

    def enabled(self, opts):
        return bool(opts.copy_to_clipboard)

    def run(self, results, opts):
        from .clipboard import copy_files

        paths = [r.dst for r in results]
        formats = copy_files(paths, opts.clipboard_mode)
        what = "GIF %d개" % len(paths) if len(paths) > 1 else results[-1].dst.name
        return "📋 %s 복사됨 (%s) — 바로 Ctrl+V" % (what, "/".join(formats))


@register_action
class DeleteOriginalAction(Action):
    name = "delete_original"
    label = "원본 정리"
    order = 20

    def enabled(self, opts):
        return bool(opts.delete_original)

    def run(self, results, opts):
        from .winutil import send_to_trash

        purge = opts.delete_mode == "purge"
        done = 0
        errors = []
        # 웹에서 받은 임시 파일은 파이프라인이 따로 지운다 (휴지통에 넣을 이유가 없음)
        for r in [x for x in results if not x.temporary]:
            try:
                if purge:
                    r.src.unlink()
                else:
                    send_to_trash(r.src)
                done += 1
            except Exception as e:
                errors.append("%s (%s)" % (r.src.name, e))

        if not done and not errors:
            return None
        where = "영구 삭제" if purge else "휴지통으로"
        msg = "🗑 원본 %d개 %s" % (done, where)
        if errors:
            msg += " · 실패 %d개: %s" % (len(errors), ", ".join(errors[:2]))
        return msg


@register_action
class RevealAction(Action):
    name = "open_folder"
    label = "결과 폴더 열기"
    order = 30

    def enabled(self, opts):
        return bool(opts.open_folder_after)

    def run(self, results, opts):
        from .winutil import reveal

        reveal(results[-1].dst)
        return None
