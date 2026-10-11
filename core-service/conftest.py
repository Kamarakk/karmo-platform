"""Lets `python3 -m pytest core-service/tests` run from the repo root (the
deploy script's test gate) as well as from inside core-service/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
