"""DevCpp-AI entry: install payload, launch Bloodshed Dev-C++ 5.11, open AI Chat."""

from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from . import config
from .chat_ui import AIChatWindow
from .install import install_or_repair, is_installed
from .network import ensure_default_hotspot


def _show_progress_and_install() -> Path:
    root = tk.Tk()
    root.title("DevCpp-AI Setup")
    root.geometry("420x120")
    root.resizable(False, False)
    root.configure(bg="#d4d0c8")

    label = tk.Label(root, text="กำลังเตรียม Bloodshed Dev-C++ 5.11 ...", bg="#d4d0c8", font=("Tahoma", 9))
    label.pack(pady=16, padx=12)

    err: list[BaseException] = []
    result: list[Path] = []

    def work() -> None:
        try:
            ide = install_or_repair(progress_cb=lambda s: root.after(0, lambda: label.config(text=s)))
            result.append(ide)
        except BaseException as e:  # noqa: BLE001
            err.append(e)
        finally:
            root.after(0, root.destroy)

    threading.Thread(target=work, daemon=True).start()
    root.mainloop()

    if err:
        raise err[0]
    if not result:
        raise RuntimeError("ติดตั้งไม่สำเร็จ")
    return result[0]


def launch_ide(ide: Path) -> subprocess.Popen:
    # Portable-friendly: run with working directory = IDE folder
    return subprocess.Popen(
        [str(ide)],
        cwd=str(ide.parent),
        close_fds=True,
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--uninstall" in argv:
        from .uninstall import uninstall_devcpp_ai

        ok, msg = uninstall_devcpp_ai()
        print(msg)
        return 0 if ok else 1

    if "--chat-only" in argv:
        AIChatWindow().run()
        return 0

    try:
        if not is_installed():
            ide = _show_progress_and_install()
        else:
            ide = config.ide_exe()
            if not ide.is_file():
                ide = _show_progress_and_install()
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("DevCpp-AI", f"ติดตั้งไม่สำเร็จ:\n{e}")
        return 1

    # Auto-connect default Personal Hotspot (SSID/password in ai_config)
    try:
        ensure_default_hotspot()
    except Exception:
        pass

    try:
        proc = launch_ide(ide)
    except OSError as e:
        messagebox.showerror("DevCpp-AI", f"เปิด Dev-C++ ไม่ได้:\n{e}")
        return 1

    # AI Chat panel — stays open alongside the IDE
    def on_chat_close() -> None:
        # Do not kill IDE on chat close; user may keep coding
        pass

    chat = AIChatWindow(on_close=on_chat_close)
    chat.run()

    # When chat closes, leave IDE running (Bloodshed independent)
    _ = proc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
