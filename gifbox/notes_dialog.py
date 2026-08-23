# -*- coding: utf-8 -*-
"""패치노트 창 — 새 버전으로 처음 실행할 때 한 번만 뜬다.

내용은 exe 에 동봉한 CHANGELOG.md 에서 읽습니다(changelog.py 참고).
'다시 보지 않기' 를 켜면 앞으로 어떤 버전에서도 뜨지 않습니다. 끄지 않아도
같은 버전에서 두 번 뜨지는 않습니다 — 본 버전을 설정에 적어두기 때문입니다.
"""

import tkinter as tk
from tkinter import ttk

from . import __version__, changelog, theme
from .theme import c


def should_show(settings):
    """이 버전의 패치노트를 아직 안 봤고, 보여주기가 켜져 있는가."""
    if not settings.get("show_release_notes", True):
        return False
    if str(settings.get("last_seen_version") or "") == __version__:
        return False
    return bool(changelog.for_version())


class NotesDialog(tk.Toplevel):
    def __init__(self, app, version=None):
        super().__init__(app.root)
        self.app = app
        self.settings = app.settings
        self.version = version or __version__

        self.title("GifBox %s" % self.version)
        self.configure(bg=c("bg"))
        self.transient(app.root)
        try:
            self.iconbitmap(str(app.icon_path))
        except tk.TclError:
            pass

        self._build()
        self._place_over_parent()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        self.grab_set()

    def _build(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="%s 에서 바뀐 것" % self.version,
                  style="Head.TLabel").pack(anchor="w")
        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(6, 8))

        wrap = ttk.Frame(outer)
        wrap.pack(fill="both", expand=True)
        text = tk.Text(wrap, width=46, height=14, wrap="word", bd=0,
                       highlightthickness=0, padx=10, pady=8,
                       bg=c("bg_deep"), fg=c("text"), font=theme.FONT_MD,
                       spacing1=2, spacing3=4,
                       selectbackground=c("accent"))
        text.pack(side="left", fill="both", expand=True)
        bar = ttk.Scrollbar(wrap, command=text.yview)
        bar.pack(side="right", fill="y")
        text.configure(yscrollcommand=bar.set)

        text.tag_configure("bullet", lmargin1=8, lmargin2=22)
        text.tag_configure("strong", foreground=c("accent"), font=theme.FONT_BOLD)
        self._render(text, changelog.for_version(self.version))
        text.configure(state="disabled")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(10, 0))
        self.var_never = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, text="다시 보지 않기",
                        variable=self.var_never).pack(side="left")
        ttk.Button(bottom, text="닫기", style="Accent.TButton",
                   command=self.close).pack(side="right")

    def _render(self, widget, body):
        """마크다운을 완전히 파싱하진 않고, 읽기 좋게만 다듬는다.

        원문은 한 항목이 여러 줄에 걸쳐 적혀 있는데, 그 줄바꿈을 그대로 두면
        이어지는 줄이 딴 문단처럼 보입니다. 한 항목을 한 문단으로 합쳐서
        위젯이 알아서 접게 두고, 접힌 줄은 lmargin2 로 글머리 아래 들여씁니다.
        """
        para = []

        def flush():
            if para:
                self._insert_marked(widget, " ".join(para) + "\n")
                para.clear()

        for raw in (body or "").splitlines():
            stripped = raw.strip()
            if not stripped:
                flush()
                widget.insert("end", "\n")
            elif stripped.startswith("- "):
                flush()
                para.append("• " + stripped[2:])
            else:
                para.append(stripped)          # 앞 항목에서 이어지는 줄
        flush()

    def _insert_marked(self, widget, line):
        """**강조** 부분만 색을 넣어 삽입."""
        rest = line
        while "**" in rest:
            before, _, after = rest.partition("**")
            widget.insert("end", before, "bullet")
            strong, _, rest = after.partition("**")
            widget.insert("end", strong, ("bullet", "strong"))
        widget.insert("end", rest, "bullet")

    def _place_over_parent(self):
        self.update_idletasks()
        root = self.app.root
        x = root.winfo_rootx() + (root.winfo_width() - self.winfo_width()) // 2
        y = root.winfo_rooty() + 60
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def close(self):
        # 같은 버전에서 또 뜨지 않도록 본 버전을 적어둔다
        self.settings["last_seen_version"] = self.version
        if self.var_never.get():
            self.settings["show_release_notes"] = False
        self.settings.save()
        self.grab_release()
        self.destroy()
        self.app.notes_window = None
