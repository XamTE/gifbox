# -*- coding: utf-8 -*-
"""소스 해석 → 파일 수집 → 변환 → 후처리로 이어지는 실행 흐름.

GUI든 CLI든 convert_many() 하나만 호출하면 되고, 진행 상황은 notify 콜백으로
흘러나옵니다. 입력은 파일 경로여도 되고 웹 주소여도 됩니다 — 그 구분은
sources.py 가 흡수합니다.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import actions as actions_mod
from . import sources as sources_mod
from .converters import DEFAULT_EXTS, pick_converter
from .sources import Item


# ---------------------------------------------------------------- 값 객체

@dataclass
class Options:
    # 변환 품질
    fps: float = 15
    width: int = 0
    colors: int = 256
    dither: str = "bayer:bayer_scale=5"
    reencode_gif: bool = False
    # 구간 자르기 ("0:12", "4" 처럼 씁니다. 비면 전체)
    trim_start: str = ""
    trim_duration: str = ""
    # 목표 용량 (MB). 0이면 끔
    target_mb: float = 0
    target_tries: int = 4
    # 출력 위치
    outdir: str = ""
    web_outdir: str = ""
    overwrite: bool = False
    # 웹에서 가져오기
    max_download_mb: int = 200
    download_timeout: int = 20
    # 후처리
    copy_to_clipboard: bool = True
    clipboard_mode: str = "file"
    delete_original: bool = True
    delete_mode: str = "trash"
    open_folder_after: bool = False
    keep_history: bool = True
    preset: str = ""

    @classmethod
    def from_settings(cls, settings):
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in settings.items() if k in known})


@dataclass
class Result:
    src: Path
    dst: Optional[Path] = None
    ok: bool = False
    error: str = ""
    src_size: int = 0
    dst_size: int = 0
    engine: str = ""
    origin: str = ""            # 웹에서 왔다면 원래 주소
    temporary: bool = False     # 원본이 임시 다운로드였는지
    attempts: int = 1           # 용량 맞추려고 다시 변환한 횟수
    target_met: Optional[bool] = None   # 목표 용량을 지켰는지 (None이면 목표 없음)
    final_width: int = 0        # 실제로 나온 가로 크기


# ---------------------------------------------------------------- 헬퍼

def human(n):
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%dB" % int(size) if unit == "B" else "%.1f%s" % (size, unit)
        size /= 1024


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(1, 1000):
        cand = path.with_name("%s (%d)%s" % (path.stem, i, path.suffix))
        if not cand.exists():
            return cand
    raise RuntimeError("빈 이름을 찾지 못함: %s" % path)


def collect(items, recursive=False, exts=None, opts=None):
    """Item 목록을 실제 변환 대상 파일 목록으로 편다.

    폴더를 펼칠 때만 확장자 필터(exts)를 씁니다. 파일을 직접 끌어다 놓거나
    인자로 준 경우에는 '처리할 엔진이 있는가'만 봅니다 — 사용자가 콕 집어
    건넨 파일이 목록에 없다는 이유로 조용히 무시되면 안 되기 때문입니다.
    """
    if exts is None:
        exts = DEFAULT_EXTS
    exts = {e.lower() for e in exts}

    out = []
    seen = set()

    def add(item, explicit):
        try:
            rp = Path(item.path).resolve()
        except OSError:
            return
        if rp in seen:
            return
        if explicit:
            if pick_converter(rp, opts) is None:
                return
        elif rp.suffix.lower() not in exts:
            return
        seen.add(rp)
        out.append(Item(path=rp, temporary=item.temporary, origin=item.origin))

    for item in items:
        p = Path(item.path)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            for f in sorted(it):
                if f.is_file():
                    add(Item(path=f), explicit=False)
        elif p.is_file():
            add(item, explicit=True)
    return out


# ------------------------------------------------- 목표 용량 맞추기

MIN_WIDTH = 120        # 이보다 더 줄이면 알아볼 수 없다
MIN_FPS = 8


def gif_width(path):
    """만들어진 GIF의 가로 크기. 다음 시도에서 얼마나 줄일지 계산하는 근거."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size[0]
    except Exception:
        return 0


def shrink_options(opts: Options, current_width, size, target, attempt):
    """넘친 만큼 설정을 낮춘 새 Options. 더 줄일 게 없으면 None.

    GIF 용량은 대략 (가로² × fps × 프레임수)에 비례하므로 가로를 √비율만큼
    줄이는 것부터 시작하고, 그래도 안 되면 fps → 색상수 순으로 손댑니다.
    화질에 미치는 영향이 작은 것부터 건드리는 순서입니다.
    """
    import math
    from dataclasses import replace

    ratio = max(0.05, min(0.95, target / float(size)))
    width = current_width or opts.width
    if not width:
        return None                       # 크기를 몰라 계산할 수 없다

    new_width = max(MIN_WIDTH, int(width * math.sqrt(ratio) * 0.95) // 2 * 2)
    new_fps = opts.fps or 15
    new_colors = opts.colors

    # 가로만으로 부족한 상황이면 fps·색상수도 함께 낮춘다
    if new_width <= MIN_WIDTH or attempt >= 1:
        new_fps = max(MIN_FPS, round(new_fps * 0.8))
    if attempt >= 2:
        new_colors = min(new_colors, 128)
    if attempt >= 3:
        new_colors = min(new_colors, 64)

    changed = (new_width != width or new_fps != (opts.fps or 15)
               or new_colors != opts.colors)
    if not changed:
        return None

    return replace(opts, width=new_width, fps=new_fps, colors=new_colors,
                   reencode_gif=True)     # 이미 GIF인 입력도 이 단계에선 다시 인코딩


# ---------------------------------------------------------------- 실행

def _output_base(item: Item, opts: Options) -> Path:
    if opts.outdir:
        return Path(opts.outdir)
    if item.temporary:
        # 웹에서 받은 건 '원본 폴더'라는 게 없으므로 지정된 곳(기본 다운로드)으로
        return (Path(opts.web_outdir) if opts.web_outdir
                else sources_mod.default_web_outdir())
    return Path(item.path).parent


def convert_one(item: Item, opts: Options, notify=None) -> Result:
    src = Path(item.path)
    res = Result(src=src, origin=item.origin, temporary=item.temporary)
    try:
        res.src_size = src.stat().st_size
    except OSError:
        pass

    conv = pick_converter(src, opts)
    if conv is None:
        res.error = "%s 형식을 처리할 엔진이 없습니다 (영상은 ffmpeg 필요)" % src.suffix
        return res
    res.engine = conv.label

    base = _output_base(item, opts).resolve()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        res.error = "출력 폴더를 만들지 못했습니다: %s" % e
        return res

    # 이미 GIF인 로컬 파일을 제자리에 '복사'하는 건 의미가 없다
    if conv.is_passthrough and not item.temporary and base == src.parent:
        res.error = "이미 GIF입니다 (크기를 줄이려면 'GIF 다시 인코딩'을 켜세요)"
        return res

    dst = base / (src.stem + ".gif")
    if dst.exists() and not opts.overwrite:
        dst = unique_path(dst)

    target = int(opts.target_mb * 1024 * 1024) if opts.target_mb else 0
    tries = max(1, int(opts.target_tries)) if target else 1

    # 중간에 끊겨도 반쪽짜리 gif가 남지 않도록 임시 이름으로 쓴 뒤 교체
    tmp = dst.with_name(dst.name + ".part")
    try:
        cur = opts
        for attempt in range(tries):
            conv = pick_converter(src, cur)
            if conv is None:
                raise RuntimeError("처리할 엔진이 없습니다")
            res.engine = conv.label
            conv.convert(src, tmp, cur,
                         progress=(lambda m: notify and notify(
                             "progress", file=src, message=m)))
            if not tmp.exists() or tmp.stat().st_size == 0:
                raise RuntimeError("출력 파일이 비어 있습니다")

            size = tmp.stat().st_size
            res.attempts = attempt + 1
            if not target or size <= target:
                break
            if attempt == tries - 1:
                break
            nxt = shrink_options(cur, gif_width(tmp), size, target, attempt)
            if nxt is None:
                break
            if notify:
                notify("shrink", file=src, attempt=attempt + 1,
                       size=size, target=target,
                       width=nxt.width, fps=nxt.fps, colors=nxt.colors)
            cur = nxt

        res.final_width = gif_width(tmp)
        tmp.replace(dst)
        res.dst = dst
        res.dst_size = dst.stat().st_size
        res.ok = True
        if target:
            res.target_met = res.dst_size <= target
    except Exception as e:
        res.error = str(e) or e.__class__.__name__
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return res


def convert_many(inputs, opts: Options, notify=None, recursive=True, exts=None):
    """inputs(파일 경로·폴더·웹 주소가 섞여도 됨)를 전부 변환하고 후처리까지."""

    def emit(kind, **data):
        if notify:
            notify(kind, **data)

    # 1) 들어온 것들을 로컬 파일로 편다 (URL이면 여기서 내려받는다)
    raws = [str(x) for x in inputs]
    items, errors = sources_mod.resolve_all(raws, opts, notify=notify)
    for err in errors:
        emit("source_error", message=err)

    # 2) 폴더를 펼치고 변환 대상만 남긴다
    files = collect(items, recursive=recursive, exts=exts, opts=opts)
    emit("collected", files=files)
    if not files:
        sources_mod.cleanup(items)
        emit("done", results=[],
             message=None if errors else "변환할 파일이 없습니다")
        return []

    results = []
    try:
        for i, item in enumerate(files, 1):
            emit("file_start", file=item.path, index=i, total=len(files))
            res = convert_one(item, opts, notify=notify)
            results.append(res)
            emit("file_done", result=res, index=i, total=len(files))

        # 3) 후처리(클립보드 복사·원본 삭제)는 변환이 검증된 결과에만
        actions_mod.run_actions(results, opts, log=lambda m: emit("action", message=m))
    finally:
        # 웹에서 받은 임시 파일은 성공하든 실패하든 남기지 않는다
        sources_mod.cleanup(files)
        sources_mod.cleanup(items)

    ok = sum(1 for r in results if r.ok)
    emit("done", results=results,
         message="완료: 성공 %d · 실패 %d" % (ok, len(results) - ok))
    return results
