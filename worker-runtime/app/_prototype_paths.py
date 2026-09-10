"""Adds the sibling core-v2-prototypes component directories to sys.path
so worker-runtime can import their modules directly rather than
duplicating them, per explicit instruction not to create competing
abstractions. Imported for its side effect by every reuse shim in this
package."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_PROTOTYPES = _ROOT / "core-v2-prototypes"

for _sub in ("tool_registry", "approval_engine", "job_model"):
    _path = str(_PROTOTYPES / _sub)
    if _path not in sys.path:
        sys.path.insert(0, _path)
