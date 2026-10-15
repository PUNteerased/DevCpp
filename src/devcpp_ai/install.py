"""Extract DevCpp-AI payload into %LOCALAPPDATA%\\DevCpp-AI and write scoped manifest."""

from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from . import config


def _resource_base() -> Path:
    """PyInstaller extracts datas to sys._MEIPASS; dev mode uses project root."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # src/devcpp_ai/install.py -> project root
    return Path(__file__).resolve().parents[2]


def payload_zip_path() -> Path:
    return _resource_base() / "payload" / "Dev-Cpp-payload.zip"


def payload_dir_path() -> Path:
    return _resource_base() / "payload" / "Dev-Cpp"


def is_installed() -> bool:
    return config.ide_exe().is_file() and config.marker_path().is_file()


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def _write_manifest(files: list[str], shortcuts: list[str]) -> None:
    data = {
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "install_root": str(config.install_root()),
        "files": files,
        "shortcuts": shortcuts,
        "protected_never_delete": config.PROTECTED_PATHS,
    }
    config.manifest_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _ensure_ai_config() -> None:
    if not config.ai_config_path().is_file():
        config.save_ai_config(
            {
                "provider": config.DEFAULT_PROVIDER,
                "api_key": config.DEFAULT_API_KEY,
                "base_url": config.DEFAULT_BASE_URL,
                "model": config.DEFAULT_MODEL,
                "timeout_sec": config.DEFAULT_TIMEOUT_SEC,
                "hotspot_ssid": config.DEFAULT_HOTSPOT_SSID,
                "hotspot_password": config.DEFAULT_HOTSPOT_PASSWORD,
                "auto_connect_hotspot": True,
                "allow_lan_fallback": config.DEFAULT_ALLOW_LAN_FALLBACK,
            }
        )


def _create_start_menu_shortcut(target: Path) -> Optional[str]:
    """Create a Start Menu shortcut pointing at DevCpp-AI launcher if available."""
    try:
        programs = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "DevCpp-AI"
        programs.mkdir(parents=True, exist_ok=True)
        shortcut = programs / "DevCpp-AI.lnk"
        # Prefer launching the frozen exe if we are frozen
        if getattr(sys, "frozen", False):
            launch_target = sys.executable
        else:
            launch_target = str(target)

        ps = f"""
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut('{shortcut}')
$sc.TargetPath = '{launch_target}'
$sc.WorkingDirectory = '{Path(launch_target).parent}'
$sc.Description = 'Bloodshed Dev-C++ 5.11 with AI Chat'
$sc.Save()
"""
        import subprocess

        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if shortcut.is_file():
            return str(shortcut)
    except OSError:
        return None
    return None


def install_or_repair(progress_cb=None) -> Path:
    """
    Install Bloodshed Dev-C++ payload into LOCALAPPDATA\\DevCpp-AI.
    Returns path to devcpp.exe.
    """
    root = config.install_root()
    root.mkdir(parents=True, exist_ok=True)
    dest = root / "Dev-Cpp"

    zip_path = payload_zip_path()
    dir_path = payload_dir_path()

    if progress_cb:
        progress_cb("กำลังติดตั้ง Bloodshed Dev-C++ 5.11 ...")

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)

    if zip_path.is_file():
        if progress_cb:
            progress_cb("กำลังแตกไฟล์จาก DevCpp-AI.exe ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
    elif dir_path.is_dir():
        if progress_cb:
            progress_cb("กำลังคัดลอกไฟล์ Dev-C++ ...")
        shutil.copytree(dir_path, dest, dirs_exist_ok=True)
    else:
        raise FileNotFoundError(
            "ไม่พบ payload ของ Dev-C++ ในแพ็กเกจ (Dev-Cpp-payload.zip หรือ payload/Dev-Cpp)"
        )

    ide = dest / "devcpp.exe"
    if not ide.is_file():
        raise FileNotFoundError(f"ติดตั้งไม่สมบูรณ์: ไม่พบ {ide}")

    files = [str(p.relative_to(root)).replace("\\", "/") for p in _iter_files(root) if p.name != config.MANIFEST_NAME]
    shortcuts: list[str] = []
    sc = _create_start_menu_shortcut(ide)
    if sc:
        shortcuts.append(sc)

    _write_manifest(files, shortcuts)
    config.marker_path().write_text(config.APP_VERSION, encoding="utf-8")
    _ensure_ai_config()

    # Refresh file list after config + marker
    files = [str(p.relative_to(root)).replace("\\", "/") for p in _iter_files(root) if p.name != config.MANIFEST_NAME]
    _write_manifest(files, shortcuts)

    if progress_cb:
        progress_cb("ติดตั้งเสร็จแล้ว")
    return ide
