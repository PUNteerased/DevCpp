import sys
from pathlib import Path

# Dev mode: allow `python src/run_devcpp_ai.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from devcpp_ai.app import main

if __name__ == "__main__":
    raise SystemExit(main())
