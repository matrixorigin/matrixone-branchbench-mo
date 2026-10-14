# MatrixOne BranchBench

The maintained entrypoint now targets **MatrixOne 4.2.5**, the stable release
verified on 2026-10-14. It forwards to the single implementation in
[Git4Data Benchmarks](https://github.com/matrixorigin/git4data-tutorial/pull/1),
rather than maintaining another driver here. The historical 4.2.4 source,
generated protobuf files, requirements and configs remain for provenance;
they are **not** used by the release entrypoint. Do not run the historical
`macrobench.runner` directly when reproducing this release package.

The canonical package is pinned to
[`b0d6832ad1c39c06fef6ebdf5c62f173495273a1`](https://github.com/VioletQwQ-0/git4data-tutorial/tree/b0d6832ad1c39c06fef6ebdf5c62f173495273a1/benchmarks).
PR #1 is still pending, so preparation fetches that published fork commit,
not a moving branch. Its runner is based on `dengn/matrixone-branchbench`
commit `95c18b7bf7a51029e3344a65e807df07aa28a2ea` plus the canonical checked patch.

## Prepare and Smoke

Python 3.11+, Git and Docker are required. Preparation downloads the fixed
package and builds its virtual environment/protobuf modules. It refuses to
overwrite an existing `.runtime/git4data-tutorial` directory; preparation is
explicit, never an implicit action of the run command.

```bash
python3 scripts/release_package.py --prepare
BB="$PWD/.runtime/git4data-tutorial/benchmarks"
PYTHON="$BB/.runtime/branchbench/.venv/bin/python"

docker run -d --name mo-branchbench-smoke --memory=8g \
  -p 127.0.0.1:16001:6001 \
  matrixorigin/matrixone:4.2.5@sha256:4455f6904a0cca5bb0f876d3026c407755216f91a4413a623c028495e0bba20f
export MO_HOST=127.0.0.1 MO_PORT=16001 MO_USER=root MO_PASSWORD=111
# Wait until the dedicated instance accepts SQL connections.
"$PYTHON" "$BB/load_seed.py" --scale smoke --db bb_seed_sfsmoke
python3 scripts/run_mo.py --scale smoke --seed-db bb_seed_sfsmoke \
  --container mo-branchbench-smoke --reps 2 \
  --workflows software_dev failure_repro data_cleaning mcts simulation
```

Only the named dedicated container is restarted, once at each workflow's r1.
Warm reps do not restart. Container removal and data-directory deletion are
never part of the driver. The image above is a smoke example, not a full-scale
resource recommendation. Host OS/persistent caches are not cleared by restart.

## SF100 / SF1000

```bash
"$PYTHON" "$BB/load_seed.py" --scale 100 --db bb_seed_sf100
python3 scripts/run_mo.py --scale 100 --seed-db bb_seed_sf100 \
  --container my-dedicated-mo --reps 5 --workflows software_dev failure_repro data_cleaning mcts

"$PYTHON" "$BB/load_seed.py" --scale 1000 --db bb_seed_sf1000
python3 scripts/run_mo.py --scale 1000 --seed-db bb_seed_sf1000 \
  --container my-dedicated-mo --reps 5 --workflows simulation --timeout 57600
```

All eight table counts are validated by the loader. Each large INSERT is
bounded to one warehouse (at most 300,000 order-line rows), by default.
Existing seed databases are never overwritten; failed loads remain for diagnosis.

The existing SQL links under `scripts/mo_v424_seed/` remain usable for clients
that already load them into a new database. SF100/SF1000 files are now generated
from the same canonical loader with **one warehouse per batch**; there is no
single 30M/300M-row INSERT. Those raw SQL files do not create a database or
automatically check counts. Prefer `load_seed.py` for validation/evidence.
Different batching can change physical layout and performance; record the input.

Canonical parameters are 5x20 (`software_dev`), 1x10 (`failure_repro`), 10x20
(`data_cleaning`), 10x100 (`mcts`) and 1000x1 (`simulation`). These are current
release profiles, not a claim that all old paper runs had these same parameters.

## Legacy Command Compatibility

`scripts/run_mo_v424.py` is now a CLI adapter to **4.2.5**, despite its old name:

```bash
python3 scripts/run_mo_v424.py --scale sf100 --seed-db bb_seed_sf100 --plan
python3 scripts/run_mo_v424.py --scale sf100 --seed-db bb_seed_sf100 \
  --container my-dedicated-mo --reps 1 --timeout 7200 --hard-timeout 9000
```

Old `sf100`/`sf1000` names become canonical `100`/`1000`; `--plan` becomes
`--check` (config generation only). Old connection flags become MO environment
variables, not forwarded credentials in subprocess arguments. Prefer `MO_PASSWORD`.
Old `--timeout` remains a worker-only cap; `--hard-timeout` additionally bounds
the full runner process (default worker cap + 1800 seconds). Actual runs now
require `--container`, since cold reps restart that instance. Legacy defaults
remain one rep and all five workflows; the new entrypoint defaults to five reps
and the ordinary four workflows. Outputs use canonical unique run directories,
`summary.jsonl` and `elapsed_sec`/`wall_sec`/`rep_wall_sec`, not old `runs.jsonl`.
An invalid sample stops subsequent reps. No automatic warm recovery is performed.

## Validity and Verification Scope

The canonical driver checks source/patch identity, MO version, seed counts,
the SQL endpoint's container binding, complete worker/step counts, zero SQL
operation errors, JSON/Parquet identity, process exit, container health and
cleanup. Missing results or teardown failures are invalid, even with 100/100 steps.
`elapsed_sec` excludes setup/seed/cleanup; `wall_sec` includes the runner's setup
and cleanup; `rep_wall_sec` also includes driver restart/clone/checks/cleanup.

The canonical package passed 35 offline tests and ten MO 4.2.5 smoke reps
(five workflows, one cold + one warm each) on 2026-10-14. This migration adds
16 passing tests (including retained validity/cleanup checks), exact-package
preparation from this legacy checkout, 25 generated configs across smoke/SF100/
SF1000, and deterministic seed parity checks. It does not repeat full-scale
performance measurements.
**Full SF100/SF1000 and live DoltgreSQL remain unvalidated on 4.2.5.**
Historical paper numbers and reported third-party crashes must be investigated
against their actual versions/configurations, not inferred from this smoke result.

```bash
"$PYTHON" -m unittest discover -s tests
```

For DoltgreSQL, the SQL diff/merge experiments, dependency pins and complete
failure handling, use the canonical package's README. This repository does not
keep a second implementation of those workflows.
