"""KARMO's code sandbox on Worker02 (item 5 of the five Kamara approved in
writing, 2026-10-03): run a short Python program KARMO wrote, with no
network and no access to anything but the files sent with the job.

Two halves, joined by a spool directory (SPOOL_ROOT):

- submit_and_wait() runs inside the worker's code_run capability, as the
  hardened karmo-worker02 service (NoNewPrivileges, no Docker access). It
  writes one job folder -- main.py plus any input files -- marks it ready,
  and waits for result.json.
- serve() is the separate karmo-sandbox-runner service (root, because it
  drives Docker). It takes each ready job and runs it once in a throwaway
  container: --network none, read-only root, 512 MB memory, 1 CPU, 64
  processes, all capabilities dropped, user nobody, the job's input
  mounted read-only. It writes result.json and removes the container.

The worker never gets Docker, and the runner never runs anything but
`python /work/main.py` in that fixed container shape.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

SPOOL_ROOT = Path(os.environ.get("KARMO_SANDBOX_SPOOL", "/var/lib/karmo/sandbox"))
SANDBOX_IMAGE = "docker.io/library/python:3.12-slim"
MAX_CODE_CHARS = 20_000
MAX_INPUT_FILES = 5
MAX_INPUT_BYTES = 1_000_000
MAX_OUTPUT_CHARS = 8_000
RUN_SECONDS = 60
_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_JOB_ID = re.compile(r"^[0-9a-f]{32}$")


class CodeSandboxError(RuntimeError):
    pass


def _validate(code, files):
    if not isinstance(code, str) or not code.strip():
        raise CodeSandboxError("code must be non-empty text")
    if len(code) > MAX_CODE_CHARS:
        raise CodeSandboxError(f"code exceeds {MAX_CODE_CHARS} characters")
    files = files or {}
    if not isinstance(files, dict) or len(files) > MAX_INPUT_FILES:
        raise CodeSandboxError(f"files must be a map of at most {MAX_INPUT_FILES} name -> text")
    total = 0
    for name, text in files.items():
        if not isinstance(name, str) or not _FILE_NAME.match(name) or name == "main.py":
            raise CodeSandboxError(f"bad input file name: {name!r}")
        if not isinstance(text, str):
            raise CodeSandboxError(f"input file {name} must be text")
        total += len(text.encode("utf-8"))
    if total > MAX_INPUT_BYTES:
        raise CodeSandboxError(f"input files exceed {MAX_INPUT_BYTES} bytes")
    return files


def submit_and_wait(code, files=None, *, spool_root=None, wait_seconds=RUN_SECONDS + 30, poll_seconds=0.5):
    """Worker side. Returns the runner's result dict:
    {exit_code, stdout, stderr, timed_out, seconds}."""
    files = _validate(code, files)
    spool = Path(spool_root or SPOOL_ROOT)
    jobs = spool / "jobs"
    if not jobs.is_dir():
        raise CodeSandboxError("sandbox spool is missing -- karmo-sandbox-runner is not set up on this worker")
    job_id = uuid.uuid4().hex
    staging = jobs / f".{job_id}"
    (staging / "in").mkdir(parents=True)
    (staging / "in" / "main.py").write_text(code, encoding="utf-8")
    for name, text in files.items():
        (staging / "in" / name).write_text(text, encoding="utf-8")
    # The worker service runs with UMask=0077, but the container runs as
    # nobody and must read these (seen live 2026-10-06: every run failed).
    (staging / "in").chmod(0o755)
    for path in (staging / "in").iterdir():
        path.chmod(0o644)
    final = jobs / job_id
    staging.rename(final)
    (final / "ready").write_text("", encoding="utf-8")

    deadline = time.monotonic() + wait_seconds
    result_file = final / "result.json"
    try:
        while time.monotonic() < deadline:
            if result_file.exists():
                try:
                    return json.loads(result_file.read_text(encoding="utf-8"))
                except ValueError:
                    pass  # runner still writing; try again next poll
            time.sleep(poll_seconds)
        raise CodeSandboxError("the sandbox runner did not answer in time")
    finally:
        (final / "done").write_text("", encoding="utf-8")


def _cap(text):
    text = text or ""
    return text if len(text) <= MAX_OUTPUT_CHARS else text[:MAX_OUTPUT_CHARS] + "\n...[output cut]"


def docker_command(job_in: Path, name: str, docker="docker"):
    return [
        docker, "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=64m",
        "--memory", "512m", "--memory-swap", "512m", "--cpus", "1", "--pids-limit", "64",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534",
        "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", f"{job_in}:/work:ro", "-w", "/work",
        SANDBOX_IMAGE, "python", "-I", "/work/main.py",
    ]


def run_job(job_dir: Path, *, docker="docker", run_seconds=RUN_SECONDS):
    """Runner side: runs one ready job and writes result.json."""
    name = f"karmo-sbx-{job_dir.name}"
    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(docker_command(job_dir / "in", name, docker), capture_output=True, text=True,
                              timeout=run_seconds, stdin=subprocess.DEVNULL)
        exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=30)
        timed_out = True
        exit_code, stdout = None, exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = f"stopped after {run_seconds} seconds"
    result = {"exit_code": exit_code, "stdout": _cap(stdout), "stderr": _cap(stderr),
              "timed_out": timed_out, "seconds": round(time.monotonic() - start, 2)}
    # The runner is root and the job folder belongs to the worker user, so
    # never follow a link the worker may have planted. The spool's setgid
    # bit gives this file the karmo group, so 0640 lets the worker read it.
    tmp = job_dir / "result.json.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(result))
    os.replace(tmp, job_dir / "result.json")
    return result


def serve_once(spool_root=None, *, docker="docker", run_seconds=RUN_SECONDS, stale_seconds=600):
    """One pass: run every ready job once, delete finished or stale ones."""
    jobs = Path(spool_root or SPOOL_ROOT) / "jobs"
    now = time.time()
    for job_dir in sorted(jobs.iterdir()):
        if not _JOB_ID.match(job_dir.name) or job_dir.is_symlink() or not job_dir.is_dir():
            if job_dir.name.startswith(".") and now - job_dir.stat().st_mtime > stale_seconds:
                shutil.rmtree(job_dir, ignore_errors=True)
            continue
        if (job_dir / "done").exists() or now - job_dir.stat().st_mtime > stale_seconds:
            shutil.rmtree(job_dir, ignore_errors=True)
        elif (job_dir / "ready").exists() and not (job_dir / "result.json").exists():
            job_in = job_dir / "in"
            main = job_in / "main.py"
            if not job_in.is_symlink() and job_in.is_dir() and main.is_file() and not main.is_symlink():
                run_job(job_dir, docker=docker, run_seconds=run_seconds)


def serve(spool_root=None, *, poll_seconds=1.0):
    while True:
        try:
            serve_once(spool_root)
        except Exception as exc:  # noqa: BLE001 -- keep serving; report and carry on
            print(f"karmo-sandbox-runner: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    if sys.argv[1:] != ["--serve"]:
        sys.exit("usage: code_sandbox.py --serve")
    serve()
