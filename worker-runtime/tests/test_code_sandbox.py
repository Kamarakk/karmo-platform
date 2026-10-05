"""Tests for the code sandbox spool: the worker half (submit_and_wait) and
the runner half (serve_once), with a fake `docker` that runs main.py
locally so no container engine is needed."""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
import time

import pytest

import code_sandbox
from code_sandbox import CodeSandboxError, docker_command, serve_once, submit_and_wait

FAKE_DOCKER = """#!{python}
import os, sys
args = sys.argv[1:]
if args[:1] == ["rm"]:
    sys.exit(0)
src = next(a.split(":")[0] for i, a in enumerate(args) if args[i - 1] == "-v")
os.chdir(src)
os.execv(sys.executable, [sys.executable, "main.py"])
"""


@pytest.fixture
def spool(tmp_path):
    (tmp_path / "jobs").mkdir()
    return tmp_path


@pytest.fixture
def fake_docker(tmp_path):
    path = tmp_path / "docker"
    path.write_text(FAKE_DOCKER.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def _runner(spool, docker, stop, run_seconds=20):
    while not stop.is_set():
        serve_once(spool, docker=docker, run_seconds=run_seconds)
        time.sleep(0.05)


def _run(spool, docker, code, files=None, run_seconds=20):
    stop = threading.Event()
    thread = threading.Thread(target=_runner, args=(spool, docker, stop, run_seconds), daemon=True)
    thread.start()
    try:
        return submit_and_wait(code, files, spool_root=spool, wait_seconds=30, poll_seconds=0.05)
    finally:
        stop.set()
        thread.join()


def test_a_program_runs_with_its_input_files_and_the_job_is_cleaned_up(spool, fake_docker):
    code = "import csv\nrows = list(csv.reader(open('sales.csv')))\nprint(sum(int(r[1]) for r in rows[1:]))\n"
    result = _run(spool, fake_docker, code, {"sales.csv": "plant,qty\nalbo,3\nbegonia,4\n"})
    assert result["exit_code"] == 0 and result["stdout"].strip() == "7" and result["timed_out"] is False
    serve_once(spool, docker=fake_docker)
    assert list((spool / "jobs").iterdir()) == []


def test_errors_and_long_output_come_back_capped(spool, fake_docker):
    result = _run(spool, fake_docker, "print('x' * 20000)\nraise SystemExit('boom')")
    assert result["exit_code"] == 1 and "boom" in result["stderr"]
    assert result["stdout"].endswith("...[output cut]") and len(result["stdout"]) < 8100


def test_a_runaway_program_is_stopped(spool, fake_docker):
    result = _run(spool, fake_docker, "while True: pass", run_seconds=1)
    assert result["timed_out"] is True and result["exit_code"] is None


@pytest.mark.parametrize("code, files, message", [
    ("", None, "non-empty"),
    ("x" * 20001, None, "exceeds"),
    ("print(1)", {"../etc": "x"}, "bad input file name"),
    ("print(1)", {"main.py": "x"}, "bad input file name"),
    ("print(1)", {f"f{i}": "x" for i in range(6)}, "at most 5"),
    ("print(1)", {"big.csv": "x" * 1_000_001}, "exceed"),
])
def test_bad_jobs_are_refused_before_anything_is_written(spool, code, files, message):
    with pytest.raises(CodeSandboxError, match=message):
        submit_and_wait(code, files, spool_root=spool, wait_seconds=1)
    assert list((spool / "jobs").iterdir()) == []


def test_missing_spool_is_reported(tmp_path):
    with pytest.raises(CodeSandboxError, match="not set up"):
        submit_and_wait("print(1)", spool_root=tmp_path / "nope", wait_seconds=1)


def test_runner_never_follows_a_planted_result_link(spool, fake_docker, tmp_path):
    target = tmp_path / "victim.txt"
    target.write_text("keep me")
    job = spool / "jobs" / ("a" * 32)
    (job / "in").mkdir(parents=True)
    (job / "in" / "main.py").write_text("print('hi')")
    (job / "result.json.tmp").symlink_to(target)
    (job / "ready").write_text("")
    serve_once(spool, docker=fake_docker)
    assert target.read_text() == "keep me"
    assert json.loads((job / "result.json").read_text())["stdout"].strip() == "hi"


def test_runner_skips_a_job_whose_input_is_a_link(spool, fake_docker, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "main.py").write_text("print('no')")
    job = spool / "jobs" / ("b" * 32)
    job.mkdir()
    os.symlink(elsewhere, job / "in")
    (job / "ready").write_text("")
    serve_once(spool, docker=fake_docker)
    assert not (job / "result.json").exists()


def test_the_container_is_locked_down():
    command = " ".join(docker_command(code_sandbox.Path("/var/lib/karmo/sandbox/jobs/x/in"), "karmo-sbx-x"))
    for flag in ("--network none", "--read-only", "--cap-drop ALL", "--user 65534:65534", "--pids-limit 64",
                 "--memory 512m", "no-new-privileges", "/var/lib/karmo/sandbox/jobs/x/in:/work:ro"):
        assert flag in command
