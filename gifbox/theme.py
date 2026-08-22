# -*- coding: utf-8 -*-
"""디스코드를 모티브로 한 어두운 팔레트와 ttk 스타일.

색을 여기 한 곳에 모아둡니다. 다른 색으로 바꾸고 싶으면 PALETTE 만 고치면
창 전체가 따라옵니다. ttk 기본 테마(vista)는 배경색을 거의 못 바꾸므로
clam 위에 얹습니다.
"""

import tkinter as tk
from tkinter import ttk

FONT = "Malgun Gothic"          # 한글이 깨지지 않는 기본 글꼴
FONT_SM = (FONT, 8)
FONT_MD = (FONT, 9)
FONT_BOLD = (FONT, 9, "bold")

PALETTE = {
    "bg": "#313338",            # 본문 배경
    "bg_alt": "#2B2D31",        # 한 단계 어두운 면 (카드·목록)
    "bg_deep": "#1E1F22",       # 가장 어두운 면 (드롭존·로그)
    "surface": "#383A40",       # 입력 칸
    "surface_hi": "#404249",    # 입력 칸 위에 마우스
    "border": "#3F4147",
    "text": "#F2F3F5",
    "muted": "#B5BAC1",
    "dim": "#80848E",
    "accent": "#5865F2",        # 블러플 — 디스코드의 그 색
    "accent_hi": "#4752C4",
    "accent_lo": "#3C45A5",
    "accent_soft": "#3A3F63",   # 선택된 칸 배경
    "green": "#3BA55D",
    "red": "#ED4245",
    "yellow": "#F0B232",
    "white": "#FFFFFF",
}


def c(name):
    return PALETTE[name]


def apply(root):
    """창 전체에 테마를 입힌다. ttk.Style 을 돌려준다."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")     # 색을 마음대로 바꿀 수 있는 유일한 기본 테마
    except tk.TclError:
        pass

    bg, bg_alt, bg_deep = c("bg"), c("bg_alt"), c("bg_deep")
    surface, surface_hi = c("surface"), c("surface_hi")
    text, muted, dim = c("text"), c("muted"), c("dim")
    accent, accent_hi, accent_lo = c("accent"), c("accent_hi"), c("accent_lo")
    border, white = c("border"), c("white")

    root.configure(bg=bg)

    # --- 기본 ----------------------------------------------------------
    # clam 은 위젯 테두리를 lightcolor/darkcolor/bordercolor 로 그린다. 이 셋이
    # 기본 밝은 회색으로 남아 있으면 배경만 어둡게 해도 흰 테두리가 남는다.
    style.configure(".", background=bg, foreground=text, font=FONT_MD,
                    borderwidth=0, focuscolor=bg,
                    bordercolor=border, lightcolor=bg, darkcolor=bg,
                    troughcolor=bg_deep)
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=text, font=FONT_MD)
    style.configure("Muted.TLabel", background=bg, foreground=muted)
    style.configure("Dim.TLabel", background=bg, foreground=dim, font=FONT_SM)
    style.configure("Head.TLabel", background=bg, foreground=text, font=FONT_BOLD)

    # --- 버튼 ----------------------------------------------------------
    style.configure("TButton", background=surface, foreground=text,
                    bordercolor=surface, lightcolor=surface, darkcolor=surface,
                    borderwidth=0, relief="flat", padding=(12, 7), font=FONT_MD)
    style.map("TButton",
              background=[("pressed", accent_lo), ("active", surface_hi)],
              foreground=[("disabled", dim)])

    style.configure("Accent.TButton", background=accent, foreground=white,
                    bordercolor=accent, lightcolor=accent, darkcolor=accent,
                    font=FONT_BOLD)
    style.map("Accent.TButton",
              background=[("pressed", accent_lo), ("active", accent_hi)],
              lightcolor=[("pressed", accent_lo), ("active", accent_hi)],
              darkcolor=[("pressed", accent_lo), ("active", accent_hi)])

    style.configure("Ghost.TButton", background=bg_alt, foreground=muted,
                    bordercolor=border, lightcolor=bg_alt, darkcolor=bg_alt,
                    padding=(10, 6))
    ghost_states = [("pressed", surface), ("active", surface_hi)]
    style.map("Ghost.TButton",
              background=ghost_states, lightcolor=ghost_states,
              darkcolor=ghost_states, foreground=[("active", text)])

    # --- 입력 ----------------------------------------------------------
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground=surface, background=surface,
                        foreground=text, bordercolor=border,
                        lightcolor=surface, darkcolor=surface,
                        insertcolor=text, arrowcolor=muted,
                        selectbackground=accent, selectforeground=white,
                        padding=(6, 4))
        style.map(name,
                  fieldbackground=[("readonly", surface), ("focus", surface_hi)],
                  bordercolor=[("focus", accent)],
                  lightcolor=[("focus", accent)],
                  darkcolor=[("focus", accent)],
                  arrowcolor=[("active", text)],
                  foreground=[("readonly", text)])

    # 콤보박스가 펼치는 목록은 ttk 가 아니라 tk 리스트박스라 따로 지정해야 한다
    root.option_add("*TCombobox*Listbox.background", bg_deep)
    root.option_add("*TCombobox*Listbox.foreground", text)
    root.option_add("*TCombobox*Listbox.selectBackground", accent)
    root.option_add("*TCombobox*Listbox.selectForeground", white)
    root.option_add("*TCombobox*Listbox.font", FONT_MD)

    # --- 체크박스 -------------------------------------------------------
    style.configure("TCheckbutton", background=bg, foreground=text,
                    font=FONT_MD, padding=(2, 5), focuscolor=bg,
                    indicatorbackground=surface, indicatorforeground=white,
                    indicatormargin=(0, 0, 8, 0), indicatorrelief="flat",
                    upperbordercolor=border, lowerbordercolor=border)
    style.map("TCheckbutton",
              background=[("active", bg)],
              foreground=[("disabled", dim)],
              indicatorbackground=[("selected", accent),
                                   ("active", surface_hi)],
              upperbordercolor=[("selected", accent)],
              lowerbordercolor=[("selected", accent)])

    # --- 탭 (선택된 탭이 확 보이도록 블러플) ------------------------------
    style.configure("TNotebook", background=bg, borderwidth=0,
                    bordercolor=bg, lightcolor=bg, darkcolor=bg,
                    tabmargins=(0, 2, 0, 0))
    style.configure("TNotebook.Tab", background=bg_alt, foreground=dim,
                    bordercolor=bg_alt, lightcolor=bg_alt, darkcolor=bg_alt,
                    padding=(18, 8), borderwidth=0, font=FONT_BOLD)
    # 선택된 탭은 블러플로 확 다르게 — 어느 탭인지 한눈에 보이도록
    tab_states = [("selected", accent), ("active", surface_hi)]
    style.map("TNotebook.Tab",
              background=tab_states,
              lightcolor=tab_states,
              darkcolor=tab_states,
              bordercolor=tab_states,
              foreground=[("selected", white), ("active", text)],
              expand=[("selected", (0, 0, 0, 0))])

    # --- 묶음 상자 ------------------------------------------------------
    style.configure("TLabelframe", background=bg, bordercolor=border,
                    lightcolor=border, darkcolor=border,
                    borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", background=bg, foreground=muted,
                    font=FONT_BOLD)

    # --- 스크롤바 -------------------------------------------------------
    style.configure("Vertical.TScrollbar", background=surface,
                    troughcolor=bg_alt, bordercolor=bg_alt, arrowcolor=muted,
                    lightcolor=surface, darkcolor=surface, borderwidth=0,
                    gripcount=0, arrowsize=12)
    style.map("Vertical.TScrollbar",
              background=[("pressed", accent), ("active", surface_hi)])

    style.configure("TSeparator", background=border)
    return style
