"""Portable host-truth tests for KARMO Worker Runtime resource discovery.

These assertions deliberately validate the machine that is actually running the
suite. They complement, rather than replace, the historical KARMO-DEV01-specific
Darwin/arm64 regression test.
"""

import platform

import resource_discovery


def test_resource_discovery_reports_actual_host_architecture():
    report = resource_discovery.full_report()

    assert report["cpu"]["status"] == "VERIFIED"
    assert report["cpu"]["machine"] == platform.machine()


def test_apple_silicon_flag_matches_actual_host():
    report = resource_discovery.full_report()
    expected = platform.system() == "Darwin" and platform.machine() == "arm64"

    assert report["acceleration"]["apple_silicon_status"] == "VERIFIED"
    assert report["acceleration"]["apple_silicon"] is expected
