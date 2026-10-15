"""Local download page for DevCpp-AI.exe (Personal Hotspot / LAN host)."""

from __future__ import annotations

import argparse
import http.server
import socket
import socketserver
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DIST = ROOT / "dist"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def local_ips() -> list[str]:
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    # Also try UDP trick for primary outbound IP (may be LAN — still useful to show)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.insert(0, ip)
    except OSError:
        pass
    return ips or ["127.0.0.1"]


def prepare_web_root() -> Path:
    """Serve web/ plus a copy/link of DevCpp-AI.exe."""
    stage = ROOT / "build" / "web_share"
    stage.mkdir(parents=True, exist_ok=True)
    # copy index
    (stage / "index.html").write_bytes((WEB / "index.html").read_bytes())
    exe_src = DIST / "DevCpp-AI.exe"
    exe_dst = stage / "DevCpp-AI.exe"
    if exe_src.is_file():
        exe_dst.write_bytes(exe_src.read_bytes())
    elif not exe_dst.is_file():
        print("WARNING: dist/DevCpp-AI.exe not found yet — build it first.", file=sys.stderr)
    return stage


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve DevCpp-AI download page on local network")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    directory = prepare_web_root()
    handler = partial(Handler, directory=str(directory))
    with socketserver.ThreadingTCPServer(("0.0.0.0", args.port), handler) as httpd:
        httpd.allow_reuse_address = True
        print("DevCpp-AI local download server")
        print(f"Serving: {directory}")
        for ip in local_ips():
            print(f"  http://{ip}:{args.port}/")
        print("เปิดฮอตสปอต / ต่อ Wi-Fi เดียวกัน แล้วเปิด URL ด้านบนบนเครื่องอื่น")
        print("Ctrl+C เพื่อหยุด")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
