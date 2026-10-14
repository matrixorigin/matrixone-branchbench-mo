#!/usr/bin/env python3
"""Legacy CLI adapter to the canonical MatrixOne 4.2.5 driver, not a 4.2.4 runner."""

import argparse
import os
from pathlib import Path
import sys

if __package__:
    from . import run_mo
else:
    import run_mo


WORKFLOWS = ("software_dev", "failure_repro", "data_cleaning", "mcts", "simulation")
SCALES = {"smoke": "smoke", "sf100": "100", "sf1000": "1000"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", choices=SCALES, required=True)
    parser.add_argument("--seed-db", required=True)
    parser.add_argument("--workflows", nargs="+", choices=WORKFLOWS, default=WORKFLOWS)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=7200, help="Legacy worker-only cap")
    parser.add_argument("--hard-timeout", type=int, help="Complete runner cap; default worker cap + 1800s")
    parser.add_argument("--container", help="Required dedicated container for actual runs")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--user")
    parser.add_argument("--password", help="Prefer MO_PASSWORD to avoid shell history")
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    if min(args.reps, args.timeout, args.hard_timeout if args.hard_timeout is not None else args.timeout) < 1:
        parser.error("reps and timeouts must be positive")
    if not args.plan and not args.container:
        parser.error("--container is now required; cold reps restart only this dedicated instance")
    return args


def translate(args):
    command = ["--scale", SCALES[args.scale], "--seed-db", args.seed_db,
               "--reps", str(args.reps), "--max-runtime-sec", str(args.timeout),
               "--timeout", str(args.hard_timeout if args.hard_timeout is not None else args.timeout + 1800),
               "--workflows", *args.workflows]
    if args.container:
        command += ["--container", args.container]
    if args.output:
        command += ["--output", str(args.output)]
    if args.plan:
        command += ["--check"]
    return command


def main(argv=None):
    args = parse_args(argv)
    for key in ("host", "port", "user", "password"):
        value = getattr(args, key)
        if value is not None:
            os.environ["MO_" + key.upper()] = str(value)
    print("NOTICE: legacy filename now forwards to MO 4.2.5; use scripts/run_mo.py for new runs",
          file=sys.stderr)
    return run_mo.main(translate(args))


if __name__ == "__main__":
    raise SystemExit(main())
