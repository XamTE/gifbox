# -*- coding: utf-8 -*-
"""항상 띄워두고 쓰는 작은 변환 창.

- 파일/폴더를 창에 끌어다 놓으면 즉시 GIF로 변환
- Ctrl+V 로 탐색기에서 복사한 파일을 받아서 변환
- 변환된 GIF는 곧바로 클립보드에 올라가므로 Ctrl+V 로 어디든 붙여넣기
"""

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import history as history_mod
from .converters import (DEFAULT_EXTS, find_ffmpeg, format_time, parse_time,
                         supported_extensions)
from .presets import all_presets, get_preset
from .pipeline import Options, convert_many, human
from .settings import Settings
from .sources import is_url
from .winutil import resource_path

try:
    from tkinterdnd2 import DND_FILES, DND_TEXT, TkinterDnD
    HAS_DND = True
except Exception:                                    # 패키지가 없어도 동작하게
    DND_FILES = DND_TEXT = None
    TkinterDnD = None
    HAS_DND = False

PAD = 8
THUMB = 96               # 최근 탭 썸네일 한 변 (기본 창 폭에서 3열)
CELL_BG = "#ffffff"
SELECT_BG = "#5865f2"
SELECT_SOFT = "#eef1ff"
FPS_CHOICES = ["원본", "10", "12", "15", "20", "24", "30"]
WIDTH_CHOICES = ["원본", "240", "320", "480", "640", "800", "1080", "1280"]


def _to_num(text, default=0):
    text = str(text).strip()
    if not text or text == "원본":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return default


def _to_choice(value):
    return "원본" if not value else str(int(value))


def _mb_text(value):
    """10.0 -> "10", 0.25 -> "0.25" 처럼 군더더기 없이."""
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return "0"
    return ("%g" % value)


def _to_float(text, default=0.0):
    try:
        return max(0.0, float(str(text).strip() or 0))
    except ValueError:
        return default


def split_drop_list(data):
    """tkdnd가 준 파일 목록 문자열을 경로들로 가른다.

    tk.splitlist() 를 쓰면 안 됩니다. Tcl이 백슬래시 이스케이프를 해석해버려서
    C:\\new\\a.mp4 의 \\n 이 줄바꿈으로, \\b 가 백스페이스로 바뀝니다.
    여기서는 중괄호만 보고 직접 자릅니다 (공백 있는 경로는 {…} 로 묶여 옵니다).
    """
    out = []
    buf = ""
    i, n = 0, len(data)
    while i < n:
        ch = data[i]
        if ch == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if data[j] == "{":
                    depth += 1
                elif data[j] == "}":
                    depth -= 1
                j += 1
            out.append(data[i + 1:j - 1])
            i = j
        elif ch.isspace():
            if buf:
                out.append(buf)
                buf = ""
            i += 1
        else:
            buf += ch
            i += 1
    if buf:
        out.append(buf)
    return [p for p in out if p]


class App:
    def __init__(self):
        self.settings = Settings.load()
        self.queue = queue.Queue()
        self.busy = False
        self._had_source_error = False

        self.root = (TkinterDnD.Tk() if HAS_DND else tk.Tk())
        self.root.title("GifBox")
        self.root.minsize(380, 460)
        try:
            self.root.iconbitmap(str(resource_path("assets/GifBox.ico")))
        except tk.TclError:
            pass
        if self.settings.geometry:
            try:
                self.root.geometry(self.settings.geometry)
            except tk.TclError:
                pass

        self._build()
        self._fit_window()
        self._bind()
        self._pump()

    def _fit_window(self):
        """위젯이 요구하는 크기보다 창이 작으면 넓혀준다.

        글꼴·DPI 배율에 따라 필요한 크기가 달라지므로 숫자를 박아두지 않고
        그때그때 재서 맞춥니다. (기능을 더 붙여도 저절로 따라옵니다)
        """
        self.root.update_idletasks()
        need_w = self.root.winfo_reqwidth()
        need_h = self.root.winfo_reqheight()
        self.root.minsize(need_w, need_h)

        cur_w = self.root.winfo_width()
        cur_h = self.root.winfo_height()
        if cur_w <= 1 or cur_h <= 1:          # 아직 배치 전이면 요구 크기로
            cur_w, cur_h = need_w, need_h
        want_w, want_h = max(cur_w, need_w), max(cur_h, need_h)
        if (want_w, want_h) != (cur_w, cur_h) or not self.settings.geometry:
            self.root.geometry("%dx%d" % (want_w, want_h))

    # ------------------------------------------------------------ 화면 구성

    def _build(self):
        root = self.root
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        outer = ttk.Frame(root, padding=PAD)
        outer.pack(fill="both", expand=True)

        # --- 프리셋 ----------------------------------------------------
        prow = ttk.Frame(outer)
        prow.pack(fill="x", pady=(0, 6))
        ttk.Label(prow, text="프리셋").pack(side="left")
        self.var_preset = tk.StringVar()
        self.preset_box = ttk.Combobox(
            prow, textvariable=self.var_preset, state="readonly",
            values=[p.title for p in all_presets()])
        self.preset_box.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.preset_box.bind("<<ComboboxSelected>>", self.on_preset_change)
        self.preset_hint = ttk.Label(outer, text="", foreground="#7a8699")
        self.preset_hint.pack(fill="x", pady=(0, 4))

        # --- 드롭 영역 -------------------------------------------------
        self.drop = tk.Label(
            outer,
            text=("여기에 끌어다 놓으세요\n\n"
                  "내 파일 (webp · mp4 · mov · webm …)\n"
                  "또는 브라우저에서 이미지를 그대로 드래그"),
            justify="center", relief="ridge", bd=2, padx=10, pady=20,
            bg="#f4f6f8", fg="#44506a",
        )
        # expand 하지 않는다 — 남는 세로 공간은 '최근' 격자가 써야 유용하다
        self.drop.pack(fill="x")
        self._drop_idle_bg = "#f4f6f8"

        # --- 주소로 가져오기 -------------------------------------------
        urlrow = ttk.Frame(outer)
        urlrow.pack(fill="x", pady=(6, 0))
        ttk.Label(urlrow, text="주소").pack(side="left")
        self.var_url = tk.StringVar()
        entry = ttk.Entry(urlrow, textvariable=self.var_url)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
        entry.bind("<Return>", lambda e: self.fetch_url())
        ttk.Button(urlrow, text="가져오기", width=9,
                   command=self.fetch_url).pack(side="left")

        # --- 옵션 ------------------------------------------------------
        opts = ttk.LabelFrame(outer, text="옵션", padding=PAD)
        opts.pack(fill="x", pady=(PAD, 0))

        row = ttk.Frame(opts)
        row.pack(fill="x")

        self.var_fps = tk.StringVar(value=_to_choice(self.settings.fps))
        self.var_width = tk.StringVar(value=_to_choice(self.settings.width))
        self.var_colors = tk.StringVar(value=str(self.settings.colors))

        ttk.Label(row, text="FPS").pack(side="left")
        ttk.Combobox(row, textvariable=self.var_fps, values=FPS_CHOICES,
                     width=6).pack(side="left", padx=(4, 12))
        ttk.Label(row, text="가로").pack(side="left")
        ttk.Combobox(row, textvariable=self.var_width, values=WIDTH_CHOICES,
                     width=7).pack(side="left", padx=(4, 2))
        ttk.Label(row, text="px").pack(side="left", padx=(0, 12))
        ttk.Label(row, text="색상").pack(side="left")
        ttk.Spinbox(row, textvariable=self.var_colors, from_=2, to=256,
                    width=5).pack(side="left", padx=(4, 0))

        # 자르기 · 목표 용량
        row_trim = ttk.Frame(opts)
        row_trim.pack(fill="x", pady=(6, 0))
        self.var_start = tk.StringVar(value=self.settings.trim_start)
        self.var_dur = tk.StringVar(value=self.settings.trim_duration)
        self.var_target = tk.StringVar(value=_mb_text(self.settings.target_mb))

        ttk.Label(row_trim, text="자르기 시작").pack(side="left")
        e1 = ttk.Entry(row_trim, textvariable=self.var_start, width=7)
        e1.pack(side="left", padx=(4, 6))
        ttk.Label(row_trim, text="길이").pack(side="left")
        e2 = ttk.Entry(row_trim, textvariable=self.var_dur, width=6)
        e2.pack(side="left", padx=(4, 10))
        ttk.Label(row_trim, text="목표").pack(side="left")
        ttk.Entry(row_trim, textvariable=self.var_target, width=5).pack(side="left",
                                                                       padx=(4, 2))
        ttk.Label(row_trim, text="MB").pack(side="left")
        for widget in (e1, e2):
            widget.bind("<FocusOut>", self._normalize_trim)

        ttk.Label(opts, text="0:12 / 4 처럼 · 비우면 전체 · 목표 0이면 제한 없음",
                  foreground="#7a8699").pack(anchor="w", pady=(2, 0))

        self.var_clip = tk.BooleanVar(value=self.settings.copy_to_clipboard)
        self.var_del = tk.BooleanVar(value=self.settings.delete_original)
        self.var_top = tk.BooleanVar(value=self.settings.always_on_top)
        self.var_open = tk.BooleanVar(value=self.settings.open_folder_after)
        self.var_reenc = tk.BooleanVar(value=self.settings.reencode_gif)

        ttk.Checkbutton(opts, text="변환 후 클립보드에 복사 (바로 Ctrl+V)",
                        variable=self.var_clip).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(opts, text="원본을 휴지통으로 보내기",
                        variable=self.var_del).pack(anchor="w")

        row2 = ttk.Frame(opts)
        row2.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(row2, text="항상 위", variable=self.var_top,
                        command=self._apply_topmost).pack(side="left")
        ttk.Checkbutton(row2, text="끝나면 폴더 열기",
                        variable=self.var_open).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(row2, text="GIF 다시 인코딩",
                        variable=self.var_reenc).pack(side="left", padx=(12, 0))

        # --- 로그 / 최근 ------------------------------------------------
        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True, pady=(PAD, 0))
        self.tabs = tabs

        logwrap = ttk.Frame(tabs, padding=2)
        tabs.add(logwrap, text="로그")
        # width 를 지정하지 않으면 Text 가 기본 80자를 요구해 창이 쓸데없이 넓어진다
        self.log = tk.Text(logwrap, height=7, width=30, wrap="word",
                           state="disabled", bd=1, relief="solid", padx=6, pady=4,
                           font=("Malgun Gothic", 9))
        self.log.pack(side="left", fill="both", expand=True)
        bar = ttk.Scrollbar(logwrap, command=self.log.yview)
        bar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=bar.set)
        self.log.tag_configure("ok", foreground="#1a7f37")
        self.log.tag_configure("err", foreground="#c0392b")
        self.log.tag_configure("dim", foreground="#7a8699")

        recent = ttk.Frame(tabs, padding=2)
        tabs.add(recent, text="최근")
        self._build_recent(recent)

        # --- 버튼 ------------------------------------------------------
        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(PAD, 0))
        ttk.Button(btns, text="파일 선택…", command=self.choose_files).pack(side="left")
        ttk.Button(btns, text="붙여넣기 (Ctrl+V)",
                   command=self.paste_and_convert).pack(side="left", padx=6)
        self.status = ttk.Label(btns, text="", foreground="#7a8699")
        self.status.pack(side="right")

        self._apply_topmost()
        self._show_preset(self.settings.preset)
        self._greet()

    # ------------------------------------------------------------ 프리셋

    def _sync_widgets(self):
        """self.settings 값을 화면 위젯으로 밀어넣는다 (프리셋 적용 후 등)."""
        s = self.settings
        self.var_fps.set(_to_choice(s.fps))
        self.var_width.set(_to_choice(s.width))
        self.var_colors.set(str(s.colors))
        self.var_target.set(_mb_text(s.target_mb))
        self.var_start.set(s.trim_start)
        self.var_dur.set(s.trim_duration)
        self.var_reenc.set(s.reencode_gif)

    def _show_preset(self, name):
        preset = get_preset(name)
        if preset:
            self.var_preset.set(preset.title)
            self.preset_hint.configure(text=preset.description)
        else:
            self.var_preset.set("")
            self.preset_hint.configure(text="직접 설정")

    def on_preset_change(self, event=None):
        preset = get_preset(self.var_preset.get())
        if not preset:
            return
        self.settings.update(preset.values)
        self.settings["preset"] = preset.name
        self.settings.normalize()
        self._sync_widgets()
        self.preset_hint.configure(text=preset.description)
        self._write("%s 적용 — %s" % (preset.title, preset.description), "dim")

    def _normalize_trim(self, event=None):
        """0:12 / 4 / 1:02.5 를 받아 보기 좋게 되돌려 준다."""
        for var in (self.var_start, self.var_dur):
            text = var.get().strip()
            if text:
                var.set(format_time(parse_time(text)) or "")

    # ------------------------------------------------------------ 최근 기록

    def _build_recent(self, parent):
        """썸네일 격자. 이름만 봐서는 어떤 GIF인지 모르니 그림으로 고르게 한다."""
        wrap = ttk.Frame(parent)
        wrap.pack(fill="both", expand=True)

        self.hist_canvas = tk.Canvas(wrap, bd=1, relief="solid",
                                     highlightthickness=0, bg=CELL_BG,
                                     width=THUMB * 3, height=THUMB * 2 + 40)
        self.hist_canvas.pack(side="left", fill="both", expand=True)
        hbar = ttk.Scrollbar(wrap, command=self.hist_canvas.yview)
        hbar.pack(side="right", fill="y")
        self.hist_canvas.configure(yscrollcommand=hbar.set)

        self.hist_inner = tk.Frame(self.hist_canvas, bg=CELL_BG)
        self._inner_id = self.hist_canvas.create_window(
            (0, 0), window=self.hist_inner, anchor="nw")
        self.hist_inner.bind(
            "<Configure>",
            lambda e: self.hist_canvas.configure(
                scrollregion=self.hist_canvas.bbox("all")))
        self.hist_canvas.bind("<Configure>", self._on_recent_resize)
        self._bind_wheel(self.hist_canvas)

        self.hist_empty = tk.Label(self.hist_inner, bg=CELL_BG, fg="#7a8699",
                                   text="아직 만든 GIF가 없습니다")

        btn = ttk.Frame(parent)
        btn.pack(fill="x", pady=(4, 0))
        ttk.Button(btn, text="📋 복사", width=9,
                   command=self.history_copy).pack(side="left")
        ttk.Button(btn, text="📂 폴더", width=9,
                   command=self.history_reveal).pack(side="left", padx=4)
        self.hist_count = ttk.Label(btn, text="", foreground="#7a8699")
        self.hist_count.pack(side="left", padx=(6, 0))
        ttk.Button(btn, text="🧹 비우기", width=10,
                   command=self.history_clear).pack(side="right")

        self.history = []
        self.cells = []
        self.selected = -1
        self._thumb_token = 0
        self._hover = None
        self._hover_job = None
        self._hover_frames = []
        self._placeholder = None
        self._columns = 0
        self.refresh_history()

    def _bind_wheel(self, widget):
        widget.bind("<MouseWheel>",
                    lambda e: self.hist_canvas.yview_scroll(
                        -1 if e.delta > 0 else 1, "units"))

    def _make_placeholder(self):
        if self._placeholder is None:
            from PIL import Image, ImageTk
            self._placeholder = ImageTk.PhotoImage(
                Image.new("RGB", (THUMB, THUMB), (232, 236, 241)))
        return self._placeholder

    def refresh_history(self):
        self.history = history_mod.load()
        for cell in self.cells:
            cell["frame"].destroy()
        self.cells = []
        self.selected = -1
        self._stop_hover()

        self.hist_count.configure(text=("%d개" % len(self.history))
                                  if self.history else "")
        if not self.history:
            self.hist_empty.pack(padx=12, pady=12)
            return
        self.hist_empty.pack_forget()

        for idx, entry in enumerate(self.history):
            self.cells.append(self._make_cell(idx, entry))
        self._columns = 0
        self._reflow()
        self._request_thumbs()

    def _make_cell(self, idx, entry):
        frame = tk.Frame(self.hist_inner, bg=CELL_BG, bd=2, relief="flat",
                         highlightthickness=1, highlightbackground=CELL_BG)
        image = tk.Label(frame, image=self._make_placeholder(), bd=0,
                         bg="#e8ecf1", cursor="hand2")
        image.pack()
        name = entry.name or Path(entry.path).name
        if len(name) > 16:
            name = name[:14] + "…"
        caption = tk.Label(frame, text=name, bg=CELL_BG, fg="#44506a",
                           font=("Malgun Gothic", 8), width=14)
        caption.pack(pady=(2, 0))
        size = tk.Label(frame, bg=CELL_BG, fg="#8a93a6",
                        font=("Malgun Gothic", 8),
                        text=("%s %s" % (entry.icon, human(entry.size))
                              if entry.size else entry.icon))
        size.pack()

        cell = {"frame": frame, "image": image, "entry": entry, "photo": None}
        for widget in (frame, image, caption, size):
            widget.bind("<Button-1>", lambda e, i=idx: self._select_cell(i))
            widget.bind("<Double-Button-1>", lambda e, i=idx: self._open_cell(i))
            widget.bind("<Enter>", lambda e, i=idx: self._start_hover(i))
            widget.bind("<Leave>", lambda e, i=idx: self._maybe_stop_hover(i))
            self._bind_wheel(widget)
        return cell

    def _on_recent_resize(self, event):
        self.hist_canvas.itemconfigure(self._inner_id, width=event.width)
        self._reflow(event.width)

    def _reflow(self, width=None):
        if not self.cells:
            return
        if width is None:
            width = self.hist_canvas.winfo_width()
        cols = max(1, int(width) // (THUMB + 18))
        if cols == self._columns:
            return
        self._columns = cols
        for i, cell in enumerate(self.cells):
            cell["frame"].grid(row=i // cols, column=i % cols, padx=3, pady=3)

    # -- 썸네일 굽기 (창이 멈추지 않게 별도 스레드) ----------------------

    def _request_thumbs(self):
        self._thumb_token += 1
        token = self._thumb_token
        entries = list(self.history)

        def work():
            from . import thumbs as thumbs_mod
            for idx, entry in enumerate(entries):
                path = thumbs_mod.get_thumb(entry.path) if entry.exists else None
                self.queue.put(("thumb", {"token": token, "index": idx,
                                          "path": path}))

        threading.Thread(target=work, daemon=True).start()

    def _apply_thumb(self, data):
        if data["token"] != self._thumb_token:
            return                      # 그 사이에 목록이 바뀌었다
        idx, path = data["index"], data["path"]
        if idx >= len(self.cells) or not path:
            return
        try:
            from PIL import Image, ImageTk
            with Image.open(path) as im:
                photo = ImageTk.PhotoImage(im.copy())
        except Exception:
            return
        cell = self.cells[idx]
        cell["photo"] = photo           # 참조를 붙들고 있어야 안 지워진다
        cell["image"].configure(image=photo)

    # -- 마우스를 올리면 움직이는 미리보기 -------------------------------

    def _start_hover(self, idx):
        if idx == self._hover or idx >= len(self.cells):
            return
        self._stop_hover()
        entry = self.cells[idx]["entry"]
        if not entry.exists:
            return
        self._hover = idx
        # 프레임 읽기는 무거우니 백그라운드에서
        token = self._thumb_token

        def work():
            from . import thumbs as thumbs_mod
            frames = thumbs_mod.load_frames(entry.path)
            self.queue.put(("hover", {"token": token, "index": idx,
                                      "frames": frames}))

        threading.Thread(target=work, daemon=True).start()

    def _begin_animation(self, data):
        if (data["token"] != self._thumb_token or data["index"] != self._hover
                or not data["frames"]):
            return
        try:
            from PIL import ImageTk
            self._hover_frames = [(ImageTk.PhotoImage(img), delay)
                                  for img, delay in data["frames"]]
        except Exception:
            self._hover_frames = []
            return
        self._animate(0)

    def _animate(self, step):
        if self._hover is None or not self._hover_frames:
            return
        if self._hover >= len(self.cells):
            return
        photo, delay = self._hover_frames[step % len(self._hover_frames)]
        self.cells[self._hover]["image"].configure(image=photo)
        self._hover_job = self.root.after(
            int(delay), lambda: self._animate(step + 1))

    def _maybe_stop_hover(self, idx):
        if idx == self._hover:
            self._stop_hover()

    def _stop_hover(self):
        if self._hover_job is not None:
            try:
                self.root.after_cancel(self._hover_job)
            except Exception:
                pass
            self._hover_job = None
        if self._hover is not None and self._hover < len(self.cells):
            cell = self.cells[self._hover]
            cell["image"].configure(image=cell["photo"] or self._make_placeholder())
        self._hover = None
        self._hover_frames = []          # 메모리 붙들고 있지 않게 놓아준다

    # -- 선택 / 동작 -----------------------------------------------------

    def _select_cell(self, idx):
        for i, cell in enumerate(self.cells):
            on = (i == idx)
            cell["frame"].configure(highlightbackground=SELECT_BG if on else CELL_BG,
                                    bg=SELECT_SOFT if on else CELL_BG)
            for child in cell["frame"].winfo_children():
                if child is not cell["image"]:
                    child.configure(bg=SELECT_SOFT if on else CELL_BG)
        self.selected = idx

    def _open_cell(self, idx):
        self._select_cell(idx)
        self.history_copy()

    def _selected_entry(self):
        if 0 <= self.selected < len(self.history):
            return self.history[self.selected]
        return None

    def history_copy(self):
        entry = self._selected_entry()
        if entry is None:
            self._write("최근 탭에서 썸네일을 하나 고르세요 (더블클릭하면 바로 복사)", "dim")
            return
        if not entry.exists:
            self._write("파일이 없습니다 (옮겼거나 지운 듯): %s" % entry.name, "err")
            self.history = history_mod.prune()
            self.refresh_history()
            return
        from .clipboard import copy_files
        try:
            copy_files([Path(entry.path)], self.settings.clipboard_mode)
            self._write("📋 %s 복사됨 — 바로 Ctrl+V" % entry.name, "ok")
        except Exception as e:
            self._write("복사 실패: %s" % e, "err")

    def history_reveal(self):
        entry = self._selected_entry()
        if entry is None or not entry.exists:
            self._write("최근 탭에서 살아있는 항목을 고르세요", "dim")
            return
        from .winutil import reveal
        reveal(Path(entry.path))

    def history_clear(self):
        from . import thumbs as thumbs_mod

        history_mod.clear()
        thumbs_mod.clear_cache()
        self.refresh_history()
        self._write("최근 목록을 비웠습니다 (파일은 그대로)", "dim")

    def _greet(self):
        if find_ffmpeg():
            self._write("엔진: ffmpeg · 영상과 webp 모두 변환합니다", "dim")
        else:
            self._write("엔진: Pillow · webp만 변환됩니다 "
                        "(mp4를 쓰려면 ffmpeg 설치)", "err")
        if not HAS_DND:
            self._write("드래그앤드롭 비활성 (pip install tkinterdnd2) "
                        "— '파일 선택'이나 Ctrl+V를 쓰세요", "err")

    def _bind(self):
        if HAS_DND:
            # 파일뿐 아니라 텍스트도 받는다 — 브라우저에서 이미지를 끌면
            # 파일이 아니라 이미지 '주소'가 텍스트로 떨어지기 때문
            for w in (self.drop, self.root):
                w.drop_target_register(DND_FILES, DND_TEXT)
                w.dnd_bind("<<Drop>>", self.on_drop)
            self.drop.dnd_bind("<<DropEnter>>", self.on_drag_enter)
            self.drop.dnd_bind("<<DropLeave>>", self.on_drag_leave)
        self.root.bind("<Control-v>", lambda e: self.paste_and_convert())
        self.root.bind("<Control-V>", lambda e: self.paste_and_convert())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------ 이벤트

    def on_drag_enter(self, event):
        self.drop.configure(bg="#e3f0ff", fg="#0b5cad")
        return event.action

    def on_drag_leave(self, event):
        self.drop.configure(bg=self._drop_idle_bg, fg="#44506a")
        return event.action

    def on_drop(self, event):
        self.on_drag_leave(event)
        self.start(self._parse_drop(event))
        return event.action

    def _parse_drop(self, event):
        """떨어진 게 파일 목록인지 주소 텍스트인지 가른다."""
        data = event.data or ""
        dnd_type = str(getattr(event, "type", "") or "")

        if dnd_type.lower().endswith("text") or is_url(data.strip()):
            # uri-list 는 줄 단위. 주석(#)과 빈 줄은 버린다
            return [line.strip() for line in data.splitlines()
                    if line.strip() and not line.startswith("#")]

        items = split_drop_list(data)
        # 파일 이름에 } 가 들어 있으면 목록 구분이 모호해진다(프로토콜 한계).
        # 쪼갠 조각이 하나도 실재하지 않으면 통째로 한 경로였다고 보고 되돌린다.
        if items and not any(Path(p).exists() for p in items):
            whole = data.strip()
            if whole.startswith("{") and whole.endswith("}"):
                whole = whole[1:-1]
            if whole and Path(whole).exists():
                return [whole]
        return items

    def choose_files(self):
        exts = sorted(supported_extensions() | DEFAULT_EXTS)
        pattern = " ".join("*" + e for e in exts)
        paths = filedialog.askopenfilenames(
            title="변환할 파일 선택",
            filetypes=[("변환 가능한 파일", pattern), ("모든 파일", "*.*")])
        if paths:
            self.start([Path(p) for p in paths])

    def fetch_url(self):
        url = self.var_url.get().strip()
        if not url:
            return
        if not is_url(url):
            self._write("http:// 또는 https:// 로 시작하는 주소만 됩니다", "err")
            return
        self.var_url.set("")
        self.start([url])

    def paste_and_convert(self):
        """클립보드에 파일이 있으면 그걸, 없으면 텍스트를 주소로 본다."""
        from .clipboard import paste_files

        try:
            paths = paste_files()
        except Exception as e:
            paths = []
            self._write("클립보드를 읽지 못했습니다: %s" % e, "err")
        if paths:
            self.start(paths)
            return

        text = ""
        try:
            text = (self.root.clipboard_get() or "").strip()
        except tk.TclError:
            pass
        urls = [line.strip() for line in text.splitlines() if is_url(line.strip())]
        if urls:
            self.start(urls)
            return

        self._write("클립보드에 파일도 이미지 주소도 없습니다 "
                    "(이미지에서 우클릭 → '이미지 주소 복사')", "dim")

    def on_close(self):
        self._stop_hover()
        self._collect_settings()
        self.settings.geometry = self.root.winfo_geometry()
        self.settings.save()
        self.root.destroy()

    def _apply_topmost(self):
        self.root.attributes("-topmost", bool(self.var_top.get()))

    # ------------------------------------------------------------ 변환 실행

    def _collect_settings(self):
        s = self.settings
        s.fps = _to_num(self.var_fps.get(), 15)
        s.width = _to_num(self.var_width.get(), 0)
        s.colors = _to_num(self.var_colors.get(), 256)
        s.copy_to_clipboard = self.var_clip.get()
        s.delete_original = self.var_del.get()
        s.open_folder_after = self.var_open.get()
        s.always_on_top = self.var_top.get()
        s.reencode_gif = self.var_reenc.get()
        s.trim_start = self.var_start.get().strip()
        s.trim_duration = self.var_dur.get().strip()
        s.target_mb = _to_float(self.var_target.get(), 0.0)
        preset = get_preset(self.var_preset.get())
        s.preset = preset.name if preset else ""
        s.normalize()
        # 정규화된 값을 화면에도 되돌려 준다
        self.var_fps.set(_to_choice(s.fps))
        self.var_width.set(_to_choice(s.width))
        self.var_colors.set(str(s.colors))
        self.var_target.set(_mb_text(s.target_mb))
        return s

    def start(self, paths):
        if self.busy:
            self._write("변환이 끝난 뒤에 다시 시도하세요", "dim")
            return
        settings = self._collect_settings()
        settings.save()
        opts = Options.from_settings(settings)

        self.busy = True
        self._had_source_error = False
        self.status.configure(text="처리 중…")
        self._write("─" * 28, "dim")

        def notify(kind, **data):
            self.queue.put((kind, data))

        def work():
            try:
                convert_many(paths, opts, notify=notify)
            except Exception as e:
                notify("fatal", message=str(e))
            finally:
                notify("finished")

        threading.Thread(target=work, daemon=True).start()

    def _pump(self):
        try:
            while True:
                kind, data = self.queue.get_nowait()
                self._handle(kind, data)
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _handle(self, kind, data):
        if kind == "source_error":
            self._had_source_error = True
            self._write("✘ %s" % data["message"], "err")

        elif kind == "collected":
            n = len(data["files"])
            if n == 0:
                if not self._had_source_error:
                    self._write("변환할 파일이 없습니다 (지원 형식이 아님)", "err")
            else:
                self._write("%d개 변환 시작" % n, "dim")

        elif kind == "file_start":
            self.status.configure(text="변환 중… %d/%d" % (data["index"], data["total"]))

        elif kind == "thumb":
            self._apply_thumb(data)

        elif kind == "hover":
            self._begin_animation(data)

        elif kind == "shrink":
            self._write("   %s 초과 (%s) — 가로 %d · %gfps · %d색으로 다시 시도"
                        % (human(data["target"]), human(data["size"]),
                           data["width"], data["fps"], data["colors"]), "dim")
            self.status.configure(text="용량 맞추는 중… %d차" % (data["attempt"] + 1))

        elif kind == "progress":
            self.status.configure(text=data.get("message", ""))

        elif kind == "file_done":
            r = data["result"]
            mark = "🌐 " if r.temporary else ""
            if r.ok:
                extra = ""
                if r.final_width:
                    extra = " · 가로 %d" % r.final_width
                if r.attempts > 1:
                    extra += " · %d번 시도" % r.attempts
                self._write("✔ %s%s → %s  (%s → %s%s)"
                            % (mark, r.src.name, r.dst.name,
                               human(r.src_size), human(r.dst_size), extra), "ok")
                if r.target_met is False:
                    self._write("   ⚠ 목표 용량까지는 못 줄였습니다 "
                                "(더 줄이려면 자르기나 목표값을 조정하세요)", "err")
                if r.temporary:
                    self._write("   저장 위치: %s" % r.dst.parent, "dim")
            else:
                self._write("✘ %s%s — %s" % (mark, r.src.name, r.error), "err")

        elif kind == "action":
            self._write(data["message"])

        elif kind in ("done", "fatal"):
            msg = data.get("message")
            if msg:
                self._write(msg, "err" if kind == "fatal" else "dim")

        elif kind == "finished":
            self.busy = False
            self.status.configure(text="")
            self.refresh_history()

    def _write(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------ 진입점

    def run(self):
        self.root.mainloop()


def selftest():
    """묶어놓은 exe 안에서 부품들이 제대로 살아있는지 점검한다.

    창 없이 돌고 결과를 dict 로 돌려줍니다. exe 로 만든 뒤 드래그앤드롭이나
    ffmpeg가 안 먹을 때 원인을 바로 짚기 위한 진단입니다.
    """
    import tempfile

    from .converters import all_converters, find_ffmpeg
    from .settings import config_path

    report = {
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "설정파일": str(config_path()),
    }

    try:
        from PIL import Image
        report["Pillow"] = Image.__version__
    except Exception as e:
        report["Pillow"] = "실패: %s" % e

    report["ffmpeg"] = find_ffmpeg() or "없음"
    report["엔진"] = [c.name for c in all_converters() if c.available()]

    # 드래그앤드롭: 모듈만 있는 게 아니라 tkdnd 바이너리까지 살아있는지 본다
    try:
        root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        root.withdraw()
        if HAS_DND:
            probe = tk.Label(root)
            probe.drop_target_register(DND_FILES, DND_TEXT)
            report["드래그앤드롭"] = "정상 (tkdnd %s)" % root.tk.call("package", "versions", "tkdnd")
        else:
            report["드래그앤드롭"] = "비활성 (tkinterdnd2 없음)"
        report["아이콘"] = ("있음" if resource_path("assets/GifBox.ico").exists()
                         else "없음")
        # 최근 탭 썸네일은 ImageTk(_imagingtk)에 달렸다 — 번들에서 빠지기 쉬운 부분
        try:
            from PIL import Image, ImageTk
            ImageTk.PhotoImage(Image.new("RGB", (4, 4)))
            report["썸네일"] = "정상"
        except Exception as e:
            report["썸네일"] = "실패: %s" % e
        root.destroy()
    except Exception as e:
        report["드래그앤드롭"] = "실패: %s" % e

    # 클립보드 왕복
    try:
        from .clipboard import copy_files, paste_files
        probe = Path(tempfile.gettempdir()) / "gifbox_selftest.gif"
        probe.write_bytes(b"GIF89a")
        copy_files([probe], "file")
        got = [p.name for p in paste_files()]
        report["클립보드"] = "정상" if probe.name in got else "이상: %s" % got
        probe.unlink(missing_ok=True)
    except Exception as e:
        report["클립보드"] = "실패: %s" % e

    return report


def main(argv=None):
    argv_probe = list(argv if argv is not None else sys.argv[1:])
    if argv_probe and argv_probe[0] == "--selftest":
        import json
        report = selftest()
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if len(argv_probe) > 1:                 # 창 모드는 stdout이 없으므로 파일로
            Path(argv_probe[1]).write_text(text, encoding="utf-8")
        else:
            print(text)
        # 빌드 자동화에서 쓸 수 있게, 깨진 항목이 있으면 종료코드로 알린다
        broken = [k for k, v in report.items()
                  if isinstance(v, str) and v.startswith("실패")]
        return 1 if broken else 0

    if sys.platform == "win32":
        try:                              # 고해상도에서 글씨가 뭉개지지 않게
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = App()
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv:                              # 파일을 인자로 받으면 바로 변환
        app.root.after(300, lambda: app.start([Path(p) for p in argv]))
    app.run()
    return 0
