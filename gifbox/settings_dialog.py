# -*- coding: utf-8 -*-
"""설정 창 — 켜고 끄는 것들을 한곳에 모아둔다.

본 창은 '무엇을 어떻게 변환할지'(프리셋·크기·자르기)만 남기고,
한 번 정해두면 잘 안 바꾸는 것들은 전부 여기로 옮겼습니다.

항목을 늘리려면 SECTIONS 에 한 줄 추가하면 됩니다. 키는 settings.DEFAULTS
의 이름과 같아야 하고, 바꾸는 즉시 저장됩니다.
"""

import tkinter as tk
from tkinter import filedialog, ttk

from . import theme
from .theme import c

#: (제목, [(설정키, 라벨, 설명), …])
SECTIONS = [
    ("변환이 끝나면", [
        ("copy_to_clipboard", "클립보드에 복사",
         "바로 Ctrl+V 로 디스코드에 붙여넣을 수 있습니다"),
        ("delete_original", "원본을 휴지통으로 보내기",
         "변환에 성공한 파일만. 실패하면 원본은 그대로 둡니다"),
        ("open_folder_after", "결과 폴더 열기", ""),
        ("keep_history", "최근 목록에 남기기",
         "'최근' 탭에서 다시 꺼내 쓸 수 있습니다"),
    ]),
    ("변환 방식", [
        ("reencode_gif", "이미 GIF인 파일도 다시 인코딩",
         "끄면 웹에서 받은 GIF를 건드리지 않고 그대로 저장합니다"),
        ("overwrite", "같은 이름이 있으면 덮어쓰기",
         "끄면 이름 뒤에 번호를 붙입니다"),
    ]),
    ("창", [
        ("always_on_top", "항상 위에 두기", ""),
    ]),
]

CLIPBOARD_MODES = [("file", "파일로 (애니메이션 유지 · 권장)"),
                   ("image", "이미지로 (첫 프레임만)"),
                   ("both", "둘 다")]

DELETE_MODES = [("trash", "휴지통으로 (되돌릴 수 있음 · 권장)"),
                ("purge", "영구 삭제")]


class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.settings = app.settings
        self.vars = {}

        self.title("GifBox 설정")
        self.configure(bg=c("bg"))
        self.transient(app.root)
        self.resizable(False, False)
        try:
            self.iconbitmap(str(app.icon_path))
        except tk.TclError:
            pass

        self._build()
        self._place_over_parent()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        self.grab_set()

    # ------------------------------------------------------------ 화면

    def _build(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        for title, rows in SECTIONS:
            ttk.Label(outer, text=title, style="Head.TLabel").pack(
                anchor="w", pady=(10, 4))
            ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 6))
            for key, label, hint in rows:
                self._checkbox(outer, key, label, hint)
                if key == "copy_to_clipboard":
                    self._choice(outer, "clipboard_mode", CLIPBOARD_MODES)
                elif key == "delete_original":
                    self._choice(outer, "delete_mode", DELETE_MODES)

        ttk.Label(outer, text="웹에서 가져온 결과", style="Head.TLabel").pack(
            anchor="w", pady=(14, 4))
        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 6))
        self._folder_row(outer)
        self._limit_row(outer)

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(18, 0))
        ttk.Button(bar, text="기본값으로", style="Ghost.TButton",
                   command=self.reset).pack(side="left")
        ttk.Button(bar, text="닫기", style="Accent.TButton",
                   command=self.close).pack(side="right")

    def _checkbox(self, parent, key, label, hint):
        var = tk.BooleanVar(value=bool(self.settings.get(key)))
        var.trace_add("write", lambda *_, k=key, v=var: self._set(k, v.get()))
        self.vars[key] = var
        ttk.Checkbutton(parent, text=label, variable=var).pack(anchor="w")
        if hint:
            ttk.Label(parent, text="      " + hint, style="Dim.TLabel").pack(
                anchor="w", pady=(0, 2))

    def _choice(self, parent, key, options):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=(22, 0), pady=(2, 6))
        labels = [text for _, text in options]
        current = dict(options).get(self.settings.get(key), labels[0])
        var = tk.StringVar(value=current)
        self.vars[key] = var

        def changed(*_):
            for value, text in options:
                if text == var.get():
                    self._set(key, value)
                    break

        var.trace_add("write", changed)
        ttk.Combobox(row, textvariable=var, values=labels, state="readonly",
                     width=30).pack(side="left", fill="x", expand=True)

    def _folder_row(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(2, 0))
        var = tk.StringVar(value=self.settings.get("web_outdir") or "")
        var.trace_add("write", lambda *_: self._set("web_outdir", var.get()))
        self.vars["web_outdir"] = var
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾기", style="Ghost.TButton", width=6,
                   command=lambda: self._pick_folder(var)).pack(side="left", padx=(6, 0))
        ttk.Label(parent, text="      비워두면 내려받기\\GifBox 에 저장합니다",
                  style="Dim.TLabel").pack(anchor="w", pady=(2, 0))

    def _limit_row(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text="최대 다운로드 크기", style="Muted.TLabel").pack(side="left")
        var = tk.StringVar(value=str(self.settings.get("max_download_mb")))
        self.vars["max_download_mb"] = var

        def changed(*_):
            try:
                self._set("max_download_mb", int(float(var.get() or 0)))
            except ValueError:
                pass

        var.trace_add("write", changed)
        ttk.Spinbox(row, textvariable=var, from_=1, to=4096, width=7).pack(
            side="left", padx=(8, 4))
        ttk.Label(row, text="MB", style="Muted.TLabel").pack(side="left")

    def _pick_folder(self, var):
        chosen = filedialog.askdirectory(parent=self, title="결과를 저장할 폴더")
        if chosen:
            var.set(chosen)

    def _place_over_parent(self):
        self.update_idletasks()
        root = self.app.root
        x = root.winfo_rootx() + (root.winfo_width() - self.winfo_width()) // 2
        y = root.winfo_rooty() + 40
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    # ------------------------------------------------------------ 동작

    def _set(self, key, value):
        self.settings[key] = value
        self.settings.normalize()
        self.settings.save()
        self.app.on_settings_changed(key)

    def reset(self):
        from .settings import DEFAULTS

        for key in self.vars:
            if key in DEFAULTS:
                self.settings[key] = DEFAULTS[key]
        self.settings.normalize()
        self.settings.save()
        for key, var in self.vars.items():
            value = self.settings.get(key)
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            elif key == "clipboard_mode":
                var.set(dict(CLIPBOARD_MODES).get(value, CLIPBOARD_MODES[0][1]))
            elif key == "delete_mode":
                var.set(dict(DELETE_MODES).get(value, DELETE_MODES[0][1]))
            else:
                var.set(str(value))
        self.app.on_settings_changed(None)

    def close(self):
        self.settings.save()
        self.grab_release()
        self.destroy()
        self.app.settings_window = None
