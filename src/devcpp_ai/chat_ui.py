"""AI helper UI — Dev-C++ theme, Thai-friendly fonts, markdown display."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from typing import Callable, Optional

from . import config
from .llm import CHATBOT_PROMPT, LLMError, chat_completion, extract_code_blocks
from .markdown_view import configure_tags, insert_markdown
from .network import ensure_default_hotspot, find_hotspot_bind_address, has_ethernet_up
from .uninstall import uninstall_devcpp_ai

BG = "#F0F0F0"
BG_WHITE = "#FFFFFF"
FG = "#000000"
FG_MUTED = "#555555"
BTN = "#E1E1E1"

# Tahoma / Leelawadee UI อ่านไทยดี; Consolas ใช้เฉพาะช่องโค้ด
FONT_UI = ("Leelawadee UI", 10)
FONT_UI_BOLD = ("Leelawadee UI", 10, "bold")
FONT_UI_ITALIC = ("Leelawadee UI", 10, "italic")
FONT_CODE = ("Consolas", 10)
FONT_CODE_TH = ("Leelawadee UI", 10)  # ข้อความ AI ที่มีไทยปนโค้ดสั้นๆ
FONT_SMALL = ("Leelawadee UI", 9)


class AIChatWindow:
    def __init__(self, on_close: Optional[Callable[[], None]] = None):
        self.on_close = on_close
        self.cfg = config.load_ai_config()
        self.history: list[dict] = [{"role": "system", "content": CHATBOT_PROMPT}]
        self.conversation_id = ""
        self._busy = False
        self._last_code = ""
        self._pending_code: Optional[str] = None

        self.root = tk.Tk()
        self.root.title("DevCpp-AI")
        self.root.geometry("720x480")
        self.root.minsize(320, 240)
        self.root.configure(bg=BG)
        try:
            self.root.option_add("*Font", FONT_UI)
        except tk.TclError:
            pass

        INPUT_BAR_H = 40
        bottom = tk.Frame(self.root, bg=BG, height=INPUT_BAR_H)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=6)
        bottom.pack_propagate(False)

        self.entry = tk.Entry(bottom, font=FONT_UI, relief=tk.SUNKEN, bg=BG_WHITE)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4), pady=4)
        self.entry.bind("<Return>", lambda e: self._on_send())

        tk.Button(
            bottom,
            text="วางโค้ด",
            font=FONT_SMALL,
            bg=BTN,
            command=self._attach_clipboard,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=2, pady=4)

        self.btn_send = tk.Button(
            bottom,
            text="ส่ง",
            font=FONT_UI_BOLD,
            bg=BTN,
            command=self._on_send,
            padx=10,
            pady=2,
        )
        self.btn_send.pack(side=tk.LEFT, pady=4)

        top = tk.Frame(self.root, bg=BG)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        self.status = tk.Label(top, text="", bg=BG, fg=FG_MUTED, font=FONT_SMALL, anchor="w")
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            top,
            text="Uninstall",
            font=FONT_SMALL,
            bg=BTN,
            relief=tk.RAISED,
            command=self._on_uninstall,
            padx=6,
            pady=1,
        ).pack(side=tk.RIGHT)

        self.paned = tk.PanedWindow(
            self.root, orient=tk.VERTICAL, bg=BG, sashwidth=4, sashrelief=tk.RAISED
        )
        self.paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        chat_frame = tk.Frame(self.paned, bg=BG)
        code_frame = tk.Frame(self.paned, bg=BG)
        self.paned.add(chat_frame, minsize=40)
        self.paned.add(code_frame, minsize=40)

        self.log = scrolledtext.ScrolledText(
            chat_frame,
            height=8,
            font=FONT_CODE_TH,
            bg=BG_WHITE,
            fg=FG,
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.SUNKEN,
            borderwidth=1,
            highlightthickness=0,
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        configure_tags(
            self.log,
            base_font=FONT_CODE_TH,
            bold_font=FONT_UI_BOLD,
            italic_font=FONT_UI_ITALIC,
            code_font=FONT_CODE,
        )
        self.log.tag_configure("who", font=FONT_UI_BOLD, foreground="#0000AA")

        code_head = tk.Frame(code_frame, bg=BG)
        code_head.pack(fill=tk.X)
        tk.Button(
            code_head,
            text="Copy โค้ด",
            font=FONT_SMALL,
            bg=BTN,
            relief=tk.RAISED,
            command=self._copy_code,
            padx=8,
            pady=1,
        ).pack(side=tk.RIGHT)

        self.code_box = scrolledtext.ScrolledText(
            code_frame,
            height=6,
            font=FONT_CODE,
            bg=BG_WHITE,
            fg=FG,
            wrap=tk.NONE,
            relief=tk.SUNKEN,
            borderwidth=1,
            highlightthickness=0,
        )
        self.code_box.pack(fill=tk.BOTH, expand=True)
        self.code_box.bind("<Control-a>", self._select_all_code)
        self.code_box.bind("<Control-A>", self._select_all_code)

        self.entry.focus_set()

        def _connect() -> None:
            ok, msg = ensure_default_hotspot(self.cfg)
            self.root.after(0, lambda: self.status.config(text=(msg if ok else msg)[:70]))
            self.root.after(0, self._refresh_net_status)

        threading.Thread(target=_connect, daemon=True).start()
        self._refresh_net_status()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _refresh_net_status(self) -> None:
        bind = find_hotspot_bind_address()
        eth = has_ethernet_up()
        if bind:
            if bind.reason == "lan_fallback":
                self.status.config(text=f"เน็ต: LAN {bind.ip}")
            else:
                extra = " | มีสาย LAN" if eth else ""
                self.status.config(text=f"เน็ต: {bind.ip}{extra}")
        else:
            self.status.config(text="")

    def _append(self, who: str, text: str, *, as_markdown: bool = False) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"[{who}] ", ("who",))
        if as_markdown:
            insert_markdown(self.log, text)
            self.log.insert(tk.END, "\n\n")
        else:
            self.log.insert(tk.END, f"{text}\n\n", ("md_normal",))
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _set_code_box(self, code: str) -> None:
        self._last_code = code or ""
        self.code_box.delete("1.0", tk.END)
        if self._last_code:
            self.code_box.insert("1.0", self._last_code)

    def _update_code_from_reply(self, reply: str) -> None:
        blocks = extract_code_blocks(reply)
        if blocks:
            self._set_code_box("\n\n".join(blocks))

    def _copy_code(self) -> None:
        code = self.code_box.get("1.0", tk.END).rstrip("\n")
        if not code.strip():
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.root.update()

    def _select_all_code(self, event=None):
        self.code_box.tag_add(tk.SEL, "1.0", tk.END)
        self.code_box.mark_set(tk.INSERT, "1.0")
        self.code_box.see(tk.INSERT)
        return "break"

    def _clipboard_code(self) -> Optional[str]:
        try:
            data = self.root.clipboard_get()
        except tk.TclError:
            return None
        data = (data or "").strip()
        return data or None

    def _attach_clipboard(self) -> None:
        data = self._clipboard_code()
        if not data:
            return
        self._pending_code = data
        self._append("คุณ", "(วางโค้ด)")
        self.entry.focus_set()

    def _build_outgoing(self, text: str) -> tuple[str, str]:
        pending = self._pending_code
        self._pending_code = None

        if pending and text:
            display = f"(วางโค้ด)\n{text}"
            payload = f"{text}\n\nนี่คือโค้ดจาก Dev-C++:\n```cpp\n{pending}\n```"
        elif pending:
            display = "(วางโค้ด)"
            payload = f"นี่คือโค้ดจาก Dev-C++:\n```cpp\n{pending}\n```"
        else:
            display = text
            payload = text
        return display, payload

    def _on_send(self) -> None:
        if self._busy:
            return
        text = self.entry.get().strip()
        if not text and not self._pending_code:
            return
        self.entry.delete(0, tk.END)

        _display, payload = self._build_outgoing(text)
        self.history.append({"role": "user", "content": payload})
        if text:
            self._append("คุณ", text)

        self._busy = True
        self.btn_send.config(state=tk.DISABLED)

        def worker() -> None:
            try:
                reply, cid = chat_completion(
                    self.history,
                    api_key=str(self.cfg.get("api_key") or config.DEFAULT_API_KEY),
                    base_url=str(self.cfg.get("base_url") or config.DEFAULT_BASE_URL),
                    model=str(self.cfg.get("model") or config.DEFAULT_MODEL),
                    timeout=float(self.cfg.get("timeout_sec") or config.DEFAULT_TIMEOUT_SEC),
                    provider=str(self.cfg.get("provider") or config.DEFAULT_PROVIDER),
                    conversation_id=self.conversation_id,
                    on_status=lambda s: self.root.after(0, lambda: self.status.config(text=s[:60])),
                )

                def done() -> None:
                    if cid:
                        self.conversation_id = cid
                    self.history.append({"role": "assistant", "content": reply})
                    self._append("AI", reply, as_markdown=True)
                    self._update_code_from_reply(reply)

                self.root.after(0, done)
            except LLMError as e:
                self.root.after(0, lambda: self._append("ระบบ", str(e)))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: self._append("ระบบ", f"ผิดพลาด: {e}"))
            finally:
                self.root.after(0, self._finish_send)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_send(self) -> None:
        self._busy = False
        self.btn_send.config(state=tk.NORMAL)
        self._refresh_net_status()
        self.entry.focus_set()

    def _on_uninstall(self) -> None:
        ok = messagebox.askyesno(
            "Uninstall",
            "ลบเฉพาะไฟล์ DevCpp-AI\nไม่แตะ Bloodshed เดิม / โปรแกรมอื่น\n\nดำเนินการ?",
        )
        if not ok:
            return
        success, msg = uninstall_devcpp_ai()
        messagebox.showinfo("Uninstall", msg)
        if success:
            self._close()

    def _close(self) -> None:
        if self.on_close:
            self.on_close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_chat() -> None:
    AIChatWindow().run()
