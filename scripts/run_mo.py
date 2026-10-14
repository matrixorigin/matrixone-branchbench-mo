#!/usr/bin/env python3
"""Forward to the pinned MatrixOne 4.2.5 driver; preparation is explicit."""

import os
import subprocess
import sys

if __package__:
    from .release_package import prepared_runtime
else:
    from release_package import prepared_runtime


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    reserved = ("--backend", "--repo", "--configs", "--expected-version")
    if any(arg.startswith("--") and any(option.startswith(arg.split("=", 1)[0])
                                        for option in reserved) for arg in argv):
        print("FAIL: backend, runner and configs are pinned; use the canonical package for custom runs",
              file=sys.stderr)
        return 1
    try:
        benchmarks, runner, python = prepared_runtime()
        command = [str(python), str(benchmarks / "run_branchbench.py"),
                   "--backend", "MATRIXONE", "--repo", str(runner), *argv]
        os.execv(str(python), command)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
