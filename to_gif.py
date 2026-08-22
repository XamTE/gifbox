#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webp / mp4 -> gif 변환 (명령줄 버전).

창 버전은 GifBox.pyw 를 실행하세요. 둘 다 gifbox/ 패키지를 그대로 씁니다.

사용 예:
    python to_gif.py a.webp b.mp4          # 변환 후 원본을 휴지통으로
    python to_gif.py ./videos -r           # 폴더 안(하위 포함) 전부
    python to_gif.py a.mp4 --fps 15 --width 480
    python to_gif.py a.mp4 --keep --copy   # 원본 유지 + 클립보드 복사
    python to_gif.py https://example.com/a.webp   # 웹에서 바로 가져오기
    python to_gif.py a.mp4 --preset discord --trim 0:12-0:16
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gifbox.converters import (DEFAULT_EXTS, IMAGE_EXTS, VIDEO_EXTS,  # noqa: E402
                               find_ffmpeg)
from gifbox.pipeline import Options, convert_many, human  # noqa: E402
from gifbox.settings import Settings  # noqa: E402


def build_parser():
    ap = argparse.ArgumentParser(
        description="webp / mp4 파일을 gif로 변환하고 원본을 정리합니다.")
    ap.add_argument("inputs", nargs="+",
                    help="파일 · 폴더 · 웹 주소(http/https) (여러 개 가능)")
    ap.add_argument("-r", "--recursive", action="store_true", help="폴더 하위까지 탐색")
    ap.add_argument("-o", "--outdir", help="결과 저장 폴더 (기본: 원본과 같은 위치)")
    ap.add_argument("--fps", type=float, help="출력 프레임레이트 (0이면 원본 유지)")
    ap.add_argument("--width", type=int, help="가로 픽셀로 축소 (0이면 원본 크기)")
    ap.add_argument("--colors", type=int, help="팔레트 색 수 (2~256)")
    ap.add_argument("--dither", help="ffmpeg 디더링 방식 (none 가능)")
    ap.add_argument("--keep", action="store_true", help="원본을 삭제하지 않음")
    ap.add_argument("--purge", action="store_true", help="휴지통이 아니라 영구 삭제")
    ap.add_argument("--copy", dest="copy", action="store_true",
                    help="변환한 GIF를 클립보드에 복사")
    ap.add_argument("--no-copy", dest="copy", action="store_false",
                    help="클립보드 복사 안 함")
    ap.set_defaults(copy=None)
    ap.add_argument("--overwrite", action="store_true",
                    help="같은 이름 gif가 있으면 덮어쓰기 (기본은 이름 뒤에 번호)")
    ap.add_argument("--all-types", action="store_true",
                    help="폴더를 훑을 때 mov·mkv·webm·avi·apng 등도 포함")
    ap.add_argument("--reencode-gif", action="store_true",
                    help="이미 GIF인 입력도 다시 인코딩 (기본은 그대로 저장)")
    ap.add_argument("--web-outdir",
                    help=r"웹에서 받은 것의 결과 위치 (기본: 내려받기\GifBox)")
    ap.add_argument("--preset", help="프리셋 이름 (discord, discord_emoji, light, high)")
    ap.add_argument("--start", help="자르기 시작 지점 (0:12 · 12 · 1:02.5)")
    ap.add_argument("--duration", help="자를 길이 (초 또는 0:04)")
    ap.add_argument("--trim", metavar="시작-끝",
                    help="구간을 한 번에 (예: 0:12-0:16). --start/--duration 대신 사용")
    ap.add_argument("--target-mb", type=float,
                    help="목표 용량(MB). 넘으면 자동으로 낮춰 다시 변환. 0이면 제한 없음")
    ap.add_argument("--presets", action="store_true", help="프리셋 목록 출력 후 종료")
    ap.add_argument("--dry-run", action="store_true", help="무엇을 할지 출력만 하고 종료")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.presets:
        from gifbox.presets import all_presets
        for p in all_presets():
            print("  %-16s %s — %s" % (p.name, p.title, p.description))
        return 0

    # 저장된 설정을 바탕으로, 명령줄에서 준 값만 덮어쓴다
    settings = Settings.load()

    # 프리셋을 먼저 얹고, 그 위에 개별 옵션을 덮어쓴다
    if args.preset:
        from gifbox.presets import apply_preset
        if not apply_preset(settings, args.preset):
            print("그런 프리셋이 없습니다: %s  (--presets 로 목록 확인)" % args.preset)
            return 1
        settings["preset"] = args.preset

    if args.trim:
        parts = args.trim.replace("~", "-").split("-", 1)
        if len(parts) == 2:
            from gifbox.converters import format_time, parse_time
            begin, end = parse_time(parts[0]), parse_time(parts[1])
            if end <= begin:
                print("--trim 의 끝이 시작보다 뒤여야 합니다: %s" % args.trim)
                return 1
            settings["trim_start"] = parts[0].strip()
            settings["trim_duration"] = format_time(end - begin)
        else:
            settings["trim_start"] = args.trim.strip()
    if args.start is not None:
        settings["trim_start"] = args.start
    if args.duration is not None:
        settings["trim_duration"] = args.duration
    if args.target_mb is not None:
        settings["target_mb"] = args.target_mb
    for key in ("fps", "width", "colors", "dither", "outdir", "overwrite",
                "web_outdir", "reencode_gif"):
        val = getattr(args, key, None)
        if val is not None and val is not False:
            settings[key] = val
    if args.keep:
        settings["delete_original"] = False
    if args.purge:
        settings["delete_original"] = True
        settings["delete_mode"] = "purge"
    if args.copy is not None:
        settings["copy_to_clipboard"] = args.copy
    settings["open_folder_after"] = False
    settings.normalize()

    if not (2 <= settings.colors <= 256):
        print("--colors 는 2~256 사이여야 합니다")
        return 1

    opts = Options.from_settings(settings)
    exts = (VIDEO_EXTS | IMAGE_EXTS) if args.all_types else DEFAULT_EXTS

    if args.dry_run:
        from gifbox.pipeline import collect
        from gifbox.sources import Item, is_url
        raws = [r for r in args.inputs if not is_url(r)]
        for url in [r for r in args.inputs if is_url(r)]:
            print("  ~ %s (실행하면 내려받습니다)" % url)
        files = collect([Item(path=Path(r)) for r in raws],
                        recursive=args.recursive, exts=exts, opts=opts)
        print("대상 %d개 · 엔진: %s"
              % (len(files), "ffmpeg" if find_ffmpeg() else "Pillow (webp 전용)"))
        for f in files:
            print("  - %s" % f.path)
        print("(--dry-run 이므로 아무것도 바꾸지 않았습니다)")
        return 0

    state = {"failed": 0, "ok": 0}

    def notify(kind, **data):
        if kind == "collected":
            print("대상 %d개 · 엔진: %s"
                  % (len(data["files"]),
                     "ffmpeg" if find_ffmpeg() else "Pillow (webp 전용)"), flush=True)
        elif kind == "file_done":
            r = data["result"]
            head = "[%d/%d]" % (data["index"], data["total"])
            if r.ok:
                state["ok"] += 1
                extra = " · %d번 시도" % r.attempts if r.attempts > 1 else ""
                if r.target_met is False:
                    extra += " · 목표 미달"
                print("%s %s -> %s  (%s → %s%s)"
                      % (head, r.src.name, r.dst.name,
                         human(r.src_size), human(r.dst_size), extra), flush=True)
            else:
                state["failed"] += 1
                print("%s %s !! 실패: %s" % (head, r.src.name, r.error), flush=True)
        elif kind == "shrink":
            print("   %s 초과(%s) — 가로 %d · %gfps · %d색으로 재시도"
                  % (human(data["target"]), human(data["size"]),
                     data["width"], data["fps"], data["colors"]), flush=True)
        elif kind == "source_error":
            state["failed"] += 1
            print("!! %s" % data["message"], flush=True)
        elif kind in ("action", "done"):
            msg = data.get("message")
            if msg:
                print(msg, flush=True)

    results = convert_many(args.inputs, opts, notify=notify,
                           recursive=args.recursive, exts=exts)
    if not results:
        return 1
    return 0 if state["failed"] == 0 else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(130)
