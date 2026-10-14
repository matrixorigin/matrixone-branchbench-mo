#!/usr/bin/env python3
"""Prepare and verify the canonical Git4Data benchmark package."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
# PR #1 is not merged yet; pin its published source rather than a moving branch.
PACKAGE_URL = "https://github.com/VioletQwQ-0/git4data-tutorial.git"
PACKAGE_COMMIT = "b0d6832ad1c39c06fef6ebdf5c62f173495273a1"
PACKAGE = ROOT / ".runtime" / "git4data-tutorial"


def verify_package(package=PACKAGE):
    head = subprocess.check_output(
        ["git", "-C", str(package), "rev-parse", "HEAD"], text=True).strip()
    changes = subprocess.check_output(
        ["git", "-C", str(package), "status", "--porcelain", "--", "benchmarks"],
        text=True)
    if head != PACKAGE_COMMIT or changes:
        raise RuntimeError("canonical package differs from the pinned commit")
    return package / "benchmarks"


def prepared_runtime(package=PACKAGE):
    if not package.exists():
        raise RuntimeError("run python3 scripts/release_package.py --prepare first")
    benchmarks = verify_package(package)
    runner = benchmarks / ".runtime" / "branchbench"
    python = runner / ".venv" / "bin" / "python"
    if not python.is_file():
        raise RuntimeError("runner preparation incomplete; inspect the preparation log")
    return benchmarks, runner, python


def prepare(package=PACKAGE):
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11+ required")
    if package.exists():
        raise RuntimeError("destination exists; reuse a prepared package or inspect it first")
    package.parent.mkdir(parents=True, exist_ok=True)
    log_path = package.parent / "release-package.prepare.log"
    with log_path.open("w") as log:
        subprocess.run(["git", "clone", "--quiet", PACKAGE_URL, str(package)],
                       stdout=log, stderr=log, check=True)
        subprocess.run(["git", "-C", str(package), "checkout", "--quiet",
                        "--detach", PACKAGE_COMMIT], stdout=log, stderr=log, check=True)
        benchmarks = verify_package(package)
        subprocess.run(["bash", str(benchmarks / "prepare_branchbench.sh")],
                       env={**os.environ, "PYTHON": sys.executable},
                       stdout=log, stderr=log, check=True)
    prepared_runtime(package)
    print("PASS: canonical release package and runner prepared")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        prepare()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}; see .runtime/release-package.prepare.log", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
