# MatrixOne BranchBench 4.2.4

The smoke seed is shared via a relative symlink to `../common/seed/smoke.sql`.
Keep `common/` alongside this version directory.

Run five BranchBench macrobenchmark workflows against **MatrixOne 4.2.4**:
`software_dev`, `failure_repro`, `data_cleaning`, `mcts`, and `simulation`.
This MatrixOne-only adaptation is based on
[dengn/matrixone-branchbench](https://github.com/dengn/matrixone-branchbench)
commit `95c18b7bf7a51029e3344a65e807df07aa28a2ea`.

The `microbench/` directory is an internal dependency of the macrobenchmark
runner. Generated protobuf modules are included; no compilation is needed.

Commands below run from the repository root. The driver, `configs/`, `seed/`,
`requirements.txt`, and `tests/` follow the same layout as 4.2.5.

## Requirements

- Python 3.11+, a MySQL-compatible CLI, and a dedicated MatrixOne 4.2.4 instance
- Enough resources for the selected scale; full `simulation` uses **1,000 workers**

```bash
python3 -m venv 4.2.4/.venv
source 4.2.4/.venv/bin/activate
python -m pip install -r 4.2.4/requirements.txt

export MO_HOST=127.0.0.1 MO_PORT=6001 MO_USER=root
export MO_PASSWORD='<your MatrixOne password>'
```

The driver also accepts `--host`, `--port`, `--user`, and `--password`.
Keep credentials out of the repository.

## Functional smoke run

Use an isolated instance. For example, start the standalone image locally:

```bash
docker run -d --name mo-branchbench-smoke \
  -p 127.0.0.1:16001:6001 matrixorigin/matrixone:4.2.4
export MO_PORT=16001
```

Wait for the SQL endpoint, then set `MO_PASSWORD` to that instance's password
(the standalone image used in our local test used `111`). Load the small seed:

```bash
MYSQL_PWD="$MO_PASSWORD" mysql -h "$MO_HOST" -P "$MO_PORT" -u "$MO_USER" \
  -e 'CREATE DATABASE bb_seed_smoke;'
MYSQL_PWD="$MO_PASSWORD" mysql -h "$MO_HOST" -P "$MO_PORT" -u "$MO_USER" \
  bb_seed_smoke < 4.2.4/seed/smoke.sql

python 4.2.4/run_branchbench.py --scale smoke --seed-db bb_seed_smoke
```

Smoke mode runs all five workflows with one step per worker and one or two
workers. It checks real branch and SQL operations; it is **not** an SF100 or
SF1000 performance result.

## SF100 / SF1000

Load the matching seed SQL into a new database. For SF100:

```bash
MYSQL_PWD="$MO_PASSWORD" mysql -h "$MO_HOST" -P "$MO_PORT" -u "$MO_USER" \
  -e 'CREATE DATABASE bb_seed_sf100;'
MYSQL_PWD="$MO_PASSWORD" mysql -h "$MO_HOST" -P "$MO_PORT" -u "$MO_USER" \
  bb_seed_sf100 < 4.2.4/seed/sf100.sql

python 4.2.4/run_branchbench.py --scale sf100 --seed-db bb_seed_sf100 --plan
python 4.2.4/run_branchbench.py --scale sf100 --seed-db bb_seed_sf100 --reps 1
```

For SF1000, use `4.2.4/seed/sf1000.sql`, a separate seed database,
and `--scale sf1000`. To select workflows, repetitions, runtime cap, and output:

```bash
python 4.2.4/run_branchbench.py --scale sf100 --seed-db bb_seed_sf100 \
  --workflows software_dev simulation --reps 3 --timeout 7200 \
  --output 4.2.4/results/my-run
```

`--plan` prints generated configurations without connecting to MatrixOne.
Full workflow parameters are in `4.2.4/configs/`; full `simulation`
uses 1,000 workers and one step. Run full-scale workloads on an isolated host.

## Validity and output

The driver checks that `SELECT VERSION()` contains `4.2.4` and verifies the
seed's `warehouse` and `order_line` row counts:

| Scale | Warehouses | `order_line` rows |
| --- | ---: | ---: |
| smoke | 10 | 10 |
| SF100 | 100 | 30,000,000 |
| SF1000 | 1,000 | 300,000,000 |

Each repetition clones the seed into a unique database. The runner normally
removes that run's clone and branches afterward; it retains the seed. If a
process is forcibly interrupted, inspect its run ID before cleaning up any
leftovers.

Output defaults to `4.2.4/results/mo_v424/`. Each run has `config.textproto`,
`run.log`, `driver_result.json`, end-to-end stats JSON, and Parquet operation
records. The output root has `runs.jsonl`. A valid run requires all workers
and steps to complete, zero operation errors, no timeout, successful cleanup,
and a zero exit code. Invalid runs make the driver exit nonzero.

## Verification scope

Run the version's tests with its environment activated:

```bash
python -m unittest discover -s 4.2.4/tests
```

On an isolated local `matrixorigin/matrixone:4.2.4` container, all five
workflows passed a smoke run: 7 worker steps, 188 recorded operations, zero
operation errors, and zero cloned databases left after cleanup. The trimmed
repository was checked for runner import and configuration generation.
Full SF100/SF1000 correctness and performance have **not** been rerun on 4.2.4.
