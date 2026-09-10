import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "approval_engine"))
sys.path.insert(0, str(ROOT / "job_model"))
