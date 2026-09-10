"""Re-exports from core-v2-prototypes/job_model/jobs.py -- reused
directly, not duplicated, per explicit instruction to align the Worker
Runtime's job lifecycle with the existing Core v2 job model rather than
create a competing one. See _prototype_paths.py."""

import _prototype_paths  # noqa: F401
from jobs import (  # noqa: F401
    Job,
    JobState,
    JobStateError,
    JobStore,
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    deterministic_job_id,
)
