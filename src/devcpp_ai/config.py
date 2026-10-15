"""Default configuration for DevCpp-AI (Bloodshed Dev-C++ 5.11 + AI Chat)."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "DevCpp-AI"
APP_VERSION = "1.0.0"
INSTALL_DIR_NAME = "DevCpp-AI"
MANIFEST_NAME = "install-manifest.json"
MARKER_NAME = ".installed"
PAYLOAD_MARKER = "Dev-Cpp/devcpp.exe"

# Default LLM settings — Dify Cloud (editable via ai_config.json after install)
# Secrets: put real values in secrets.local.json (gitignored) or ai_config.json after install.
# API: https://api.dify.ai/v1
DEFAULT_PROVIDER = "dify"
DEFAULT_API_KEY = ""
DEFAULT_BASE_URL = "https://api.dify.ai/v1"
DEFAULT_MODEL = "dify"
DEFAULT_TIMEOUT_SEC = 120

# Default Personal Hotspot (auto-connect when available)
DEFAULT_HOTSPOT_SSID = "hah"
DEFAULT_HOTSPOT_PASSWORD = ""

# If no hotspot/Wi-Fi: allow Ethernet/LAN for AI chat (classroom PCs often have LAN only)
DEFAULT_ALLOW_LAN_FALLBACK = True


def _load_local_secrets() -> dict:
    """Optional secrets.local.json next to project / beside exe / embedded at build."""
    candidates: list[Path] = []
    try:
        # Frozen: beside exe, and MEIPASS
        import sys

        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "secrets.local.json")
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(Path(meipass) / "secrets.local.json")
        # Dev: project root
        candidates.append(Path(__file__).resolve().parents[2] / "secrets.local.json")
    except Exception:
        pass
    try:
        from . import _embedded_secrets  # type: ignore

        return {
            "api_key": getattr(_embedded_secrets, "API_KEY", "") or "",
            "base_url": getattr(_embedded_secrets, "BASE_URL", "") or DEFAULT_BASE_URL,
            "hotspot_ssid": getattr(_embedded_secrets, "HOTSPOT_SSID", "") or DEFAULT_HOTSPOT_SSID,
            "hotspot_password": getattr(_embedded_secrets, "HOTSPOT_PASSWORD", "") or "",
            "allow_lan_fallback": getattr(
                _embedded_secrets, "ALLOW_LAN_FALLBACK", DEFAULT_ALLOW_LAN_FALLBACK
            ),
        }
    except Exception:
        pass
    for p in candidates:
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return {}


_SECRETS = _load_local_secrets()
if _SECRETS.get("api_key"):
    DEFAULT_API_KEY = str(_SECRETS["api_key"])
if _SECRETS.get("base_url"):
    DEFAULT_BASE_URL = str(_SECRETS["base_url"])
if _SECRETS.get("hotspot_ssid"):
    DEFAULT_HOTSPOT_SSID = str(_SECRETS["hotspot_ssid"])
if "hotspot_password" in _SECRETS and _SECRETS.get("hotspot_password") is not None:
    DEFAULT_HOTSPOT_PASSWORD = str(_SECRETS.get("hotspot_password") or "")
if "allow_lan_fallback" in _SECRETS:
    DEFAULT_ALLOW_LAN_FALLBACK = bool(_SECRETS["allow_lan_fallback"])

# Known Bloodshed install path — never touch during uninstall
PROTECTED_PATHS = [
    r"C:\Program Files (x86)\Dev-Cpp",
    r"C:\Program Files\Dev-Cpp",
    r"C:\Program Files (x86)\Embarcadero\Dev-Cpp",
]


def localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))


def install_root() -> Path:
    return localappdata() / INSTALL_DIR_NAME


def ide_exe() -> Path:
    return install_root() / "Dev-Cpp" / "devcpp.exe"


def manifest_path() -> Path:
    return install_root() / MANIFEST_NAME


def marker_path() -> Path:
    return install_root() / MARKER_NAME


def ai_config_path() -> Path:
    return install_root() / "ai_config.json"


def load_ai_config() -> dict:
    path = ai_config_path()
    defaults = {
        "provider": DEFAULT_PROVIDER,
        "api_key": DEFAULT_API_KEY,
        "base_url": DEFAULT_BASE_URL,
        "model": DEFAULT_MODEL,
        "timeout_sec": DEFAULT_TIMEOUT_SEC,
        "hotspot_ssid": DEFAULT_HOTSPOT_SSID,
        "hotspot_password": DEFAULT_HOTSPOT_PASSWORD,
        "auto_connect_hotspot": True,
        "allow_lan_fallback": DEFAULT_ALLOW_LAN_FALLBACK,
    }
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            defaults.update({k: v for k, v in data.items() if v is not None})
        except (OSError, json.JSONDecodeError):
            pass
    return defaults


def save_ai_config(cfg: dict) -> None:
    install_root().mkdir(parents=True, exist_ok=True)
    ai_config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
