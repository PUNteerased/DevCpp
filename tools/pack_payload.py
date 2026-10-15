"""Zip payload/Dev-Cpp into build/Dev-Cpp-payload.zip for embedding in DevCpp-AI.exe."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "payload" / "Dev-Cpp"
OUT_DIR = ROOT / "build"
OUT = OUT_DIR / "Dev-Cpp-payload.zip"


def main() -> None:
    if not (SRC / "devcpp.exe").is_file():
        raise SystemExit(f"Missing Bloodshed payload at {SRC}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    count = 0
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in SRC.rglob("*"):
            if path.is_file():
                arc = path.relative_to(SRC).as_posix()
                zf.write(path, arcname=arc)
                count += 1
                if count % 500 == 0:
                    print(f"  packed {count} files...")

    mb = OUT.stat().st_size / (1024 * 1024)
    print(f"Wrote {OUT} ({mb:.1f} MB, {count} files)")


if __name__ == "__main__":
    main()
