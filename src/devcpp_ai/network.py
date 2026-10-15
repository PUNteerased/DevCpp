"""Force LLM traffic through Personal Hotspot Wi-Fi; never use Ethernet/LAN."""

from __future__ import annotations

import socket
import subprocess
import tempfile
import time
import xml.sax.saxutils
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config


HOTSPOT_GATEWAY_PREFIXES = (
    "192.168.43.",   # Android hotspot common
    "192.168.137.",  # Windows mobile hotspot / ICS
    "172.20.10.",    # iPhone hotspot common
)

ETHERNET_IFACE_HINTS = (
    "ethernet",
    "local area connection",
    "lan",
    "realtek pcie",
    "intel(r) ethernet",
    "killer ethernet",
)


@dataclass
class BindAddress:
    ip: str
    iface_name: str
    reason: str


def _run_ipconfig() -> str:
    try:
        out = subprocess.check_output(
            ["ipconfig", "/all"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return out
    except (OSError, subprocess.CalledProcessError):
        return ""


def _parse_adapters(ipconfig_text: str) -> list[dict]:
    adapters: list[dict] = []
    current: Optional[dict] = None
    for raw in ipconfig_text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if current is None:
                continue
            lower = line.lower()
            if "ipv4 address" in lower or "ip address" in lower:
                # e.g. IPv4 Address. . . . . . . . . . . : 192.168.43.12(Preferred)
                if ":" in line:
                    val = line.split(":", 1)[1].strip()
                    val = val.split("(")[0].strip()
                    if val and val[0].isdigit():
                        current.setdefault("ipv4", []).append(val)
            if "default gateway" in lower and ":" in line:
                val = line.split(":", 1)[1].strip()
                if val and val[0].isdigit():
                    current["gateway"] = val
            if "description" in lower and ":" in line:
                current["description"] = line.split(":", 1)[1].strip()
            if "media state" in lower and "disconnected" in lower:
                current["disconnected"] = True
        else:
            # Adapter header: "Wireless LAN adapter ...:" or "Ethernet adapter ..."
            if "adapter" in line.lower() and line.strip().endswith(":"):
                name = line.strip().rstrip(":").strip()
                current = {"name": name, "ipv4": [], "gateway": "", "disconnected": False, "description": ""}
                adapters.append(current)
    return adapters


def _is_ethernet(adapter: dict) -> bool:
    blob = f"{adapter.get('name', '')} {adapter.get('description', '')}".lower()
    if "wireless" in blob or "wi-fi" in blob or "wifi" in blob:
        return False
    if "ethernet" in blob:
        return True
    return any(h in blob for h in ETHERNET_IFACE_HINTS)


def _is_wifi(adapter: dict) -> bool:
    blob = f"{adapter.get('name', '')} {adapter.get('description', '')}".lower()
    return any(x in blob for x in ("wireless", "wi-fi", "wifi", "wlan"))


def _looks_like_hotspot(adapter: dict) -> bool:
    gw = adapter.get("gateway") or ""
    if any(gw.startswith(p) for p in HOTSPOT_GATEWAY_PREFIXES):
        return True
    for ip in adapter.get("ipv4") or []:
        if any(ip.startswith(p) for p in HOTSPOT_GATEWAY_PREFIXES):
            return True
    return False


def find_hotspot_bind_address(allow_lan_fallback: bool | None = None) -> Optional[BindAddress]:
    """
    Prefer Personal Hotspot / Wi-Fi. Optionally fall back to Ethernet/LAN
    when classroom PCs have cable only and hotspot is off.
    """
    if allow_lan_fallback is None:
        try:
            allow_lan_fallback = bool(config.load_ai_config().get("allow_lan_fallback", True))
        except Exception:
            allow_lan_fallback = True

    adapters = _parse_adapters(_run_ipconfig())
    wifi_candidates: list[dict] = []
    lan_candidates: list[dict] = []
    for a in adapters:
        if a.get("disconnected"):
            continue
        if not a.get("ipv4"):
            continue
        if _is_ethernet(a):
            lan_candidates.append(a)
            continue
        if _is_wifi(a) or _looks_like_hotspot(a):
            wifi_candidates.append(a)

    hotspot = [a for a in wifi_candidates if _looks_like_hotspot(a)]
    pool = hotspot or wifi_candidates
    if pool:
        chosen = pool[0]
        ip = chosen["ipv4"][0]
        reason = "personal_hotspot" if _looks_like_hotspot(chosen) else "wifi"
        return BindAddress(ip=ip, iface_name=chosen.get("name", "Wi-Fi"), reason=reason)

    if allow_lan_fallback and lan_candidates:
        chosen = lan_candidates[0]
        return BindAddress(
            ip=chosen["ipv4"][0],
            iface_name=chosen.get("name", "Ethernet"),
            reason="lan_fallback",
        )
    return None


def has_ethernet_up() -> bool:
    for a in _parse_adapters(_run_ipconfig()):
        if a.get("disconnected"):
            continue
        if _is_ethernet(a) and a.get("ipv4"):
            return True
    return False


def _run_netsh(args: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["netsh", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out
    except OSError as e:
        return 1, str(e)


def current_wifi_ssid() -> Optional[str]:
    code, out = _run_netsh(["wlan", "show", "interfaces"])
    if code != 0:
        return None
    for line in out.splitlines():
        if "ssid" in line.lower() and "bssid" not in line.lower() and ":" in line:
            val = line.split(":", 1)[1].strip()
            if val:
                return val
    return None


def _wifi_profile_xml(ssid: str, password: str) -> str:
    esc_ssid = xml.sax.saxutils.escape(ssid)
    esc_pass = xml.sax.saxutils.escape(password)
    # hex SSID for profile name safety
    ssid_hex = ssid.encode("utf-8").hex()
    return f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{esc_ssid}</name>
  <SSIDConfig>
    <SSID>
      <hex>{ssid_hex}</hex>
      <name>{esc_ssid}</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{esc_pass}</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>
"""


def connect_hotspot(ssid: str, password: str, wait_sec: float = 12.0) -> tuple[bool, str]:
    """Add/update WLAN profile and connect to Personal Hotspot SSID."""
    ssid = (ssid or "").strip()
    password = password or ""
    if not ssid:
        return False, "ไม่ได้ตั้ง SSID ของฮอตสปอต"

    cur = current_wifi_ssid()
    if cur and cur.lower() == ssid.lower() and find_hotspot_bind_address():
        return True, f"เชื่อมต่อ {ssid} อยู่แล้ว"

    profile = _wifi_profile_xml(ssid, password)
    tmp = Path(tempfile.gettempdir()) / f"devcpp-ai-{ssid}.xml"
    try:
        tmp.write_text(profile, encoding="utf-8")
    except OSError as e:
        return False, f"เขียน Wi-Fi profile ไม่ได้: {e}"

    code, out = _run_netsh(["wlan", "add", "profile", f"filename={tmp}", "user=current"])
    # ignore "already exists" style failures; still try connect
    code2, out2 = _run_netsh(["wlan", "connect", f"name={ssid}", f"ssid={ssid}"])
    if code2 != 0:
        # retry connect by profile name only
        code2, out2 = _run_netsh(["wlan", "connect", f"name={ssid}"])

    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if current_wifi_ssid() and current_wifi_ssid().lower() == ssid.lower():
            if find_hotspot_bind_address():
                return True, f"เชื่อมต่อ Personal Hotspot '{ssid}' สำเร็จ"
        time.sleep(0.7)

    detail = (out2 or out or "").strip()
    return False, f"เชื่อมต่อ '{ssid}' ไม่สำเร็จ (เปิดฮอตสปอตมือถือก่อน)\n{detail[:300]}"


def ensure_default_hotspot(cfg: Optional[dict] = None) -> tuple[bool, str]:
    """Connect using defaults / ai_config hotspot settings."""
    cfg = cfg or config.load_ai_config()
    if cfg.get("auto_connect_hotspot") is False:
        bind = find_hotspot_bind_address()
        if bind:
            return True, f"ใช้ Wi-Fi ปัจจุบัน ({bind.ip})"
        return False, "auto_connect_hotspot ปิดอยู่ และยังไม่พบ Hotspot"

    ssid = str(cfg.get("hotspot_ssid") or config.DEFAULT_HOTSPOT_SSID)
    password = str(cfg.get("hotspot_password") or config.DEFAULT_HOTSPOT_PASSWORD)
    return connect_hotspot(ssid, password)


class BoundHTTPConnection:
    """
    Helper: create a TCP connection bound to a specific local IP
    so traffic exits via Personal Hotspot, not Ethernet.
    """

    def __init__(self, local_ip: str):
        self.local_ip = local_ip

    def connect(self, host: str, port: int, timeout: float = 30.0) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.bind((self.local_ip, 0))
        sock.connect((host, port))
        return sock
