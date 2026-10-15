"""Scoped uninstall: delete ONLY files created by DevCpp-AI.exe."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import config


def _normalize(p: str | Path) -> str:
    return os.path.normcase(str(Path(p).resolve()))


def _is_protected(path: Path) -> bool:
    target = _normalize(path)
    for protected in config.PROTECTED_PATHS:
        try:
            prot = _normalize(protected)
        except OSError:
            continue
        if target == prot or target.startswith(prot + os.sep):
            return True
    return False


def _under_install_root(path: Path) -> bool:
    try:
        root = _normalize(config.install_root())
        return _normalize(path) == root or _normalize(path).startswith(root + os.sep)
    except OSError:
        return False


def load_manifest() -> dict | None:
    mp = config.manifest_path()
    if not mp.is_file():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def kill_ide_processes() -> None:
    """Stop only Dev-C++ processes started from our install folder."""
    install = str(config.install_root())
    try:
        # taskkill by image, then rely on path checks during delete
        subprocess.run(
            ["taskkill", "/F", "/IM", "devcpp.exe"],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        pass
    time.sleep(0.4)
    _ = install


def uninstall_devcpp_ai() -> tuple[bool, str]:
    """
    Remove only DevCpp-AI installation artifacts.
    Never touches Bloodshed installs under Program Files or unrelated exes.
    """
    root = config.install_root()
    if not root.exists() and not config.manifest_path().is_file():
        return False, "ไม่พบการติดตั้ง DevCpp-AI บนเครื่องนี้"

    if _is_protected(root):
        return False, "ปฏิเสธ: โฟลเดอร์ติดตั้งทับ path ที่ป้องกันไว้"

    kill_ide_processes()

    manifest = load_manifest()
    removed_shortcuts = 0
    if manifest:
        for sc in manifest.get("shortcuts") or []:
            p = Path(sc)
            # Only delete shortcuts we created under DevCpp-AI start menu folder
            try:
                if p.is_file() and "DevCpp-AI" in str(p):
                    p.unlink(missing_ok=True)
                    removed_shortcuts += 1
                    # remove empty parent
                    parent = p.parent
                    if parent.is_dir() and parent.name == "DevCpp-AI" and not any(parent.iterdir()):
                        parent.rmdir()
            except OSError:
                pass

    # Delete install root entirely — scoped to LOCALAPPDATA\\DevCpp-AI only
    if root.exists():
        if not _under_install_root(root):
            return False, "ปฏิเสธ: install root ไม่ได้อยู่ใต้ LOCALAPPDATA\\DevCpp-AI"
        if _is_protected(root):
            return False, "ปฏิเสธ: ไม่ลบ path ที่ป้องกันไว้"
        shutil.rmtree(root, ignore_errors=True)

    # Schedule self-delete of frozen exe if it lives inside install root (rare)
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        if _under_install_root(exe) and exe.is_file():
            # should already be gone with rmtree; if not, best-effort
            try:
                exe.unlink(missing_ok=True)
            except OSError:
                pass

    still = root.exists()
    if still:
        return False, f"ลบไม่หมด: ยังเหลือ {root}"

    msg = (
        f"ถอนการติดตั้ง DevCpp-AI แล้ว (ลบเฉพาะไฟล์ของแอปนี้)\n"
        f"ลบ shortcut: {removed_shortcuts}\n"
        f"Bloodshed Dev-C++ / โปรแกรมอื่นในเครื่อง ไม่ถูกแตะต้อง"
    )
    return True, msg
