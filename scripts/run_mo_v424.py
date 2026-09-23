#!/usr/bin/env python3
"""Run the five MatrixOne BranchBench workflows against a seeded MO 4.2.4."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = Path(__file__).resolve().parent / "mo_v424_configs"
WORKFLOWS = ("software_dev", "failure_repro", "data_cleaning", "mcts", "simulation")
EXPECTED_ROWS = {
    "smoke": (10, 10),
    "sf100": (100, 30_000_000),
    "sf1000": (1000, 300_000_000),
}


def identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe database identifier: {value!r}")
    return value


def render_config(workflow, run_id, database, scale, smoke=False):
    template = (CONFIGS / f"{workflow}_noclone.textproto").read_text()
    template = re.sub(r'(?m)^run_id: .*$', f'run_id: "{run_id}"', template)
    template = re.sub(r'(?m)^    db_name: .*$', f'    db_name: "{database}"', template)
    template = re.sub(r'(?m)^    db_scale: \d+', f'    db_scale: {scale}', template)
    template = re.sub(r'(?m)^(    cleanup: true)$', r'\1\n    existing_db { branch_id: "main" }', template)
    if smoke:
        workers = 2 if workflow in ("data_cleaning", "simulation") else 1
        template = re.sub(r'(?m)^    workers: \d+', f'    workers: {workers}', template)
        template = re.sub(r'(?m)^    total_steps: \d+', '    total_steps: 1', template)
        template = re.sub(r'(?m)^    root_fanout: \d+', f'    root_fanout: {workers}', template)
    return template


def connect(args):
    import pymysql

    return pymysql.connect(
        host=args.host, port=args.port, user=args.user, password=args.password,
        autocommit=True, connect_timeout=10, read_timeout=1800,
    )


def preflight(conn, seed_db, scale):
    with conn.cursor() as cur:
        cur.execute("SELECT VERSION()")
        version = str(cur.fetchone()[0])
        if "4.2.4" not in version:
            raise RuntimeError(f"Expected MO 4.2.4, got {version!r}")
        counts = []
        for table in ("warehouse", "order_line"):
            cur.execute(f"SELECT COUNT(*) FROM `{seed_db}`.`{table}`")
            counts.append(int(cur.fetchone()[0]))
    if tuple(counts) != EXPECTED_ROWS[scale]:
        raise RuntimeError(f"Seed row counts {tuple(counts)} != {EXPECTED_ROWS[scale]}")
    return version


def run_one(args, conn, workflow, rep, batch, output_dir, version):
    run_id = f"mo424_{args.scale}_{workflow}_{batch}_r{rep}"
    database = identifier(run_id)
    run_dir = output_dir / run_id
    run_dir.mkdir()
    config_path = run_dir / "config.textproto"
    config_path.write_text(render_config(
        workflow, run_id, database, 0 if args.scale == "smoke" else EXPECTED_ROWS[args.scale][0],
        smoke=args.scale == "smoke",
    ))

    with conn.cursor() as cur:
        cur.execute("SHOW DATABASES LIKE %s", (database,))
        if cur.fetchone():
            raise RuntimeError(f"Refusing to overwrite existing database: {database}")
        cur.execute(f"CREATE DATABASE `{database}` CLONE `{args.seed_db}`")

    command = [sys.executable, "-m", "macrobench.runner", "--config", str(config_path),
               "--outdir", str(run_dir), "--no-progress", "--strict-operations",
               "--max-runtime-sec", str(args.timeout)]
    env = os.environ.copy()
    env.update(MO_HOST=args.host, MO_PORT=str(args.port), MO_USER=args.user,
               MO_PASSWORD=args.password)
    with (run_dir / "run.log").open("w") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                stderr=subprocess.STDOUT, check=False)
    stats_path = run_dir / f"{run_id}_e2e_stats.json"
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else {}
    valid = result.returncode == 0 and stats.get("run_valid") is True
    record = {"run_id": run_id, "workflow": workflow, "rep": rep,
              "scale": args.scale, "mo_version": version,
              "exit_code": result.returncode, "valid": valid,
              "invalid_reasons": stats.get("invalid_reasons", ["missing_stats"]),
              "total_operation_errors": stats.get("total_operation_errors"),
              "elapsed_s": stats.get("elapsed_sec"), "run_dir": str(run_dir)}
    (run_dir / "driver_result.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", choices=EXPECTED_ROWS, required=True)
    parser.add_argument("--seed-db", required=True, type=identifier)
    parser.add_argument("--workflows", nargs="+", choices=WORKFLOWS, default=WORKFLOWS)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "mo_v424")
    parser.add_argument("--host", default=os.environ.get("MO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MO_PORT", "6001")))
    parser.add_argument("--user", default=os.environ.get("MO_USER", "root"))
    parser.add_argument("--password", default=os.environ.get("MO_PASSWORD", "111"))
    parser.add_argument("--plan", action="store_true", help="Print configs without connecting to MO")
    args = parser.parse_args()
    if args.reps < 1 or args.timeout < 1:
        parser.error("--reps and --timeout must be positive")

    batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.plan:
        for workflow in args.workflows:
            db_scale = 0 if args.scale == "smoke" else EXPECTED_ROWS[args.scale][0]
            print(render_config(workflow, f"mo424_{args.scale}_{workflow}_{batch}_r1",
                                f"mo424_{args.scale}_{workflow}_{batch}_r1",
                                db_scale, smoke=args.scale == "smoke"))
        return

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(args)
    try:
        version = preflight(conn, args.seed_db, args.scale)
        failed = False
        for workflow in args.workflows:
            for rep in range(1, args.reps + 1):
                record = run_one(args, conn, workflow, rep, batch, output_dir, version)
                with (output_dir / "runs.jsonl").open("a") as out:
                    out.write(json.dumps(record) + "\n")
                print(json.dumps(record), flush=True)
                failed |= not record["valid"]
        if failed:
            raise SystemExit(2)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
