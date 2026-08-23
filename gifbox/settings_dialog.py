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
    ("알림", [
        ("show_release_notes", "새 버전으로 처음 실행할 때 바뀐 점 보여주기",
         "'다시 보지 않기' 를 누른 것과 같은 스위치입니다"),
        ("check_updates", "새 버전이 나왔는지 확인",
         "하루 한 번만 확인하고, 실패해도 방해하지 않습니다"),
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
        self.resizable(False, True)
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
        # 항목이 늘면서 창이 화면보다 길어질 수 있어 통째로 스크롤되게 감싼다.
        # 닫기 버튼이 화면 밖으로 밀려나면 창을 닫을 수가 없기 때문이다.
        self.canvas = tk.Canvas(self, bg=c("bg"), highlightthickness=0, bd=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical",
                                    command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        outer = ttk.Frame(self.canvas, padding=14)
        self._outer_id = self.canvas.create_window((0, 0), window=outer,
                                                   anchor="nw")
        outer.bind("<Configure>", self._on_inner_resize)
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._outer_id,
                                                             width=e.width))
        self.bind_all("<MouseWheel>", self._on_wheel)

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

        self._section(outer, "업데이트")
        self._update_row(outer)

        self._section(outer, "즐겨찾기")
        ttk.Label(outer, text="기본 브라우저로 엽니다. 로그인·확장이 그대로 살아 있습니다.",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 4))
        self._bookmark_editor(outer)

        self._section(outer, "웹에서 가져온 결과")
        self._folder_row(outer)
        self._limit_row(outer)

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(18, 0))
        ttk.Button(bar, text="기본값으로", style="Ghost.TButton",
                   command=self.reset).pack(side="left")
        ttk.Button(bar, text="닫기", style="Accent.TButton",
                   command=self.close).pack(side="right")

    def _section(self, parent, title):
        ttk.Label(parent, text=title, style="Head.TLabel").pack(
            anchor="w", pady=(14, 4))
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(0, 6))

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

    # ------------------------------------------------------------ 업데이트

    def _update_row(self, parent):
        from . import __version__

        self.update_state = ttk.Label(
            parent, text="지금 버전 %s" % __version__, style="Muted.TLabel")
        self.update_state.pack(anchor="w")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(6, 0))
        self.update_btn = ttk.Button(row, text="지금 확인", style="Ghost.TButton",
                                     command=self.check_update)
        self.update_btn.pack(side="left")
        ttk.Button(row, text="릴리스 페이지", style="Ghost.TButton",
                   command=self.open_release_page).pack(side="left", padx=6)
        self.download_btn = ttk.Button(row, text="내려받기",
                                       style="Accent.TButton",
                                       command=self.download_update)
        self.latest = None

        found = getattr(self.app, "update_info", None)
        if found:
            self._show_update(found)

    def _show_update(self, info):
        self.latest = info
        if info.get("newer"):
            self.update_state.configure(
                text="새 버전 %s 있음 (%s)" % (info["version"], info["published"]))
            self.download_btn.pack(side="left")
        else:
            self.update_state.configure(text="최신입니다 (%s)" % info["version"])
            self.download_btn.pack_forget()

    def check_update(self):
        import threading

        from . import updater

        self.update_btn.configure(state="disabled")
        self.update_state.configure(text="확인 중…")

        def work():
            info = updater.check()
            self.app.root.after(0, lambda: self._checked(info))

        threading.Thread(target=work, daemon=True).start()

    def _checked(self, info):
        if not self.winfo_exists():
            return
        self.update_btn.configure(state="normal")
        if info is None:
            self.update_state.configure(text="확인하지 못했습니다 (연결 문제)")
            return
        self.app.remember_update(info)
        self._show_update(info)

    def open_release_page(self):
        from . import bookmarks, updater

        info = self.latest or getattr(self.app, "update_info", None)
        bookmarks.open_site((info or {}).get("page") or updater.RELEASES_PAGE)

    def download_update(self):
        import threading

        from . import updater

        info = self.latest
        if not info:
            return
        asset = updater.pick_asset(info["assets"])
        if not asset:
            self.update_state.configure(text="받을 파일이 없습니다")
            return

        self.download_btn.configure(state="disabled")

        def work():
            try:
                sums = updater.fetch_checksums(info["assets"])
                path = updater.download(
                    asset, expected_sha256=sums.get(asset["name"]),
                    progress=lambda got, total: self.app.root.after(
                        0, lambda: self._progress(got, total)))
            except Exception as e:
                self.app.root.after(0, lambda: self._downloaded(None, str(e)))
                return
            self.app.root.after(0, lambda: self._downloaded(path, None))

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, got, total):
        if not self.winfo_exists():
            return
        if total:
            self.update_state.configure(
                text="내려받는 중… %d%%" % int(got * 100 / total))
        else:
            self.update_state.configure(
                text="내려받는 중… %.1fMB" % (got / 1048576))

    def _downloaded(self, path, error):
        if self.winfo_exists():
            self.download_btn.configure(state="normal")
        if error:
            if self.winfo_exists():
                self.update_state.configure(text="실패: %s" % error)
            self.app.log_line("업데이트 내려받기 실패: %s" % error, "err")
            return
        from .winutil import reveal

        if self.winfo_exists():
            self.update_state.configure(text="받았습니다 — 탐색기에서 바꿔주세요")
        self.app.log_line(
            "⬇ %s 내려받음 — 지금 쓰는 exe 를 이 파일로 바꾸면 됩니다" % path.name, "ok")
        reveal(path)

    # ------------------------------------------------------------ 즐겨찾기

    def _bookmark_editor(self, parent):
        from . import bookmarks as bm

        box = ttk.Frame(parent)
        box.pack(fill="x")

        listwrap = ttk.Frame(box)
        listwrap.pack(fill="x")
        self.mark_list = tk.Listbox(listwrap, height=5, width=34, bd=0,
                                    highlightthickness=1, activestyle="none",
                                    bg=c("bg_deep"), fg=c("text"),
                                    highlightbackground=c("border"),
                                    selectbackground=c("accent"),
                                    selectforeground=c("white"),
                                    font=theme.FONT_MD)
        self.mark_list.pack(side="left", fill="x", expand=True)
        bar = ttk.Scrollbar(listwrap, command=self.mark_list.yview)
        bar.pack(side="right", fill="y")
        self.mark_list.configure(yscrollcommand=bar.set)
        self.mark_list.bind("<<ListboxSelect>>", self._mark_selected)

        form = ttk.Frame(box)
        form.pack(fill="x", pady=(6, 0))
        self.var_mark_icon = tk.StringVar()
        self.var_mark_name = tk.StringVar()
        self.var_mark_url = tk.StringVar()
        ttk.Entry(form, textvariable=self.var_mark_icon, width=3).pack(side="left")
        ttk.Entry(form, textvariable=self.var_mark_name, width=10).pack(
            side="left", padx=4)
        ttk.Entry(form, textvariable=self.var_mark_url).pack(
            side="left", fill="x", expand=True)

        btns = ttk.Frame(box)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="추가", style="Ghost.TButton", width=6,
                   command=self._mark_add).pack(side="left")
        ttk.Button(btns, text="수정", style="Ghost.TButton", width=6,
                   command=self._mark_edit).pack(side="left", padx=4)
        ttk.Button(btns, text="삭제", style="Ghost.TButton", width=6,
                   command=self._mark_delete).pack(side="left")
        ttk.Button(btns, text="기본 목록", style="Ghost.TButton",
                   command=lambda: self._mark_save(bm.DEFAULTS)).pack(side="right")
        self.mark_hint = ttk.Label(box, text="아이콘 · 이름 · 주소",
                                   style="Dim.TLabel")
        self.mark_hint.pack(anchor="w", pady=(3, 0))
        self._refresh_marks()

    def _marks(self):
        return list(self.settings.get("bookmarks") or [])

    def _refresh_marks(self):
        from . import bookmarks as bm

        self.mark_list.delete(0, "end")
        for item in self._marks():
            self.mark_list.insert("end", "%-14s %s" % (bm.label(item), item["url"]))

    def _mark_selected(self, event=None):
        sel = self.mark_list.curselection()
        if not sel:
            return
        item = self._marks()[sel[0]]
        self.var_mark_icon.set(item.get("icon", ""))
        self.var_mark_name.set(item.get("name", ""))
        self.var_mark_url.set(item.get("url", ""))

    def _mark_save(self, items):
        from . import bookmarks as bm

        self.settings["bookmarks"] = bm.clean(items)
        self.settings.save()
        self._refresh_marks()
        self.app.refresh_bookmarks()

    def _form_item(self):
        from . import bookmarks as bm

        url = bm.normalize_url(self.var_mark_url.get())
        if not url:
            self.mark_hint.configure(text="주소가 올바르지 않습니다 (http/https)")
            return None
        self.mark_hint.configure(text="아이콘 · 이름 · 주소")
        return {"icon": self.var_mark_icon.get(),
                "name": self.var_mark_name.get(), "url": url}

    def _mark_add(self):
        from . import bookmarks as bm

        item = self._form_item()
        if not item:
            return
        items = self._marks()
        if len(items) >= bm.MAX:
            self.mark_hint.configure(text="최대 %d개까지입니다" % bm.MAX)
            return
        self._mark_save(items + [item])

    def _mark_edit(self):
        sel = self.mark_list.curselection()
        item = self._form_item()
        if not sel or not item:
            return
        items = self._marks()
        items[sel[0]] = item
        self._mark_save(items)

    def _mark_delete(self):
        sel = self.mark_list.curselection()
        if not sel:
            return
        items = self._marks()
        del items[sel[0]]
        self._mark_save(items)

    def _on_inner_resize(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_wheel(self, event):
        if self.winfo_exists():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _place_over_parent(self):
        """화면 안에 들어가도록 크기를 정하고 부모 위에 놓는다."""
        self.update_idletasks()
        need_w = self.canvas.bbox("all")[2] + self.scroll.winfo_reqwidth() + 4
        need_h = self.canvas.bbox("all")[3]

        # 작업 표시줄 등을 감안해 화면 높이의 85% 를 넘지 않게
        max_h = int(self.winfo_screenheight() * 0.85)
        width, height = need_w, min(need_h, max_h)
        self.geometry("%dx%d" % (width, height))
        self.minsize(width, min(360, height))

        root = self.app.root
        x = root.winfo_rootx() + (root.winfo_width() - width) // 2
        y = max(0, root.winfo_rooty() + 40)
        if y + height > self.winfo_screenheight():
            y = max(0, self.winfo_screenheight() - height - 40)
        self.geometry("+%d+%d" % (max(0, x), y))

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
        try:
            self.unbind_all("<MouseWheel>")   # 본 창 휠 동작을 되돌려 준다
        except tk.TclError:
            pass
        self.grab_release()
        self.destroy()
        self.app.settings_window = None
