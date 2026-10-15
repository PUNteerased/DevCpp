"""Lightweight markdown rendering for Tk Text (bold / italic / inline code)."""

from __future__ import annotations

import re
import tkinter as tk

# **bold** or __bold__, *italic* or _italic_, `code`
_TOKEN = re.compile(
    r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`)",
)


def configure_tags(widget: tk.Text, *, base_font, bold_font, italic_font, code_font) -> None:
    widget.tag_configure("md_bold", font=bold_font)
    widget.tag_configure("md_italic", font=italic_font)
    widget.tag_configure("md_code", font=code_font, background="#F5F5F5")
    widget.tag_configure("md_normal", font=base_font)


def insert_markdown(widget: tk.Text, text: str, *, index=tk.END) -> None:
    """Insert text with simple markdown emphasis; markers themselves are not shown."""
    pos = 0
    for m in _TOKEN.finditer(text):
        if m.start() > pos:
            widget.insert(index, text[pos : m.start()], ("md_normal",))
        token = m.group(0)
        if token.startswith("**") and token.endswith("**"):
            widget.insert(index, token[2:-2], ("md_bold",))
        elif token.startswith("__") and token.endswith("__"):
            widget.insert(index, token[2:-2], ("md_bold",))
        elif token.startswith("`") and token.endswith("`"):
            widget.insert(index, token[1:-1], ("md_code",))
        elif token.startswith("*") and token.endswith("*"):
            widget.insert(index, token[1:-1], ("md_italic",))
        elif token.startswith("_") and token.endswith("_"):
            widget.insert(index, token[1:-1], ("md_italic",))
        else:
            widget.insert(index, token, ("md_normal",))
        pos = m.end()
    if pos < len(text):
        widget.insert(index, text[pos:], ("md_normal",))
