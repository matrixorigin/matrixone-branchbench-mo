# MatrixOne BranchBench

This is the canonical repository for these benchmarks, including the
[MatrixOne](https://github.com/matrixorigin/matrixone) 4.2.4 and 4.2.5 workflows.

Shared files live in `common/`; files that differ remain under their MatrixOne release:

| Directory | Version | Contents |
| --- | --- | --- |
| `common/seed/smoke.sql` | Both | One shared smoke seed, linked from both version directories |
| [4.2.4](4.2.4/README.md) | MatrixOne 4.2.4 | Preserved original runner, configs, seed SQL, and tests |
| [4.2.5](4.2.5/README.md) | MatrixOne 4.2.5 | Updated drivers, batched seed loader, pinned runner patch, and DoltgreSQL support |

Both versions use the same layout:

```text
<version>/
  README.md
  run_branchbench.py
  requirements.txt
  configs/<workflow>.textproto
  seed/smoke.sql -> ../../common/seed/smoke.sql
  tests/test_drivers.py
```

Version-specific tools live alongside these entries. The 4.2.4 directory includes
its runner modules and `seed/sf100.sql` / `seed/sf1000.sql`; 4.2.5 includes a seed
loader, preparation script, runner patch, and additional experiment scripts.
CLI options and workload settings remain specific to each version.

Follow either version's README from the repository root. For 4.2.4, begin with:

```bash
python3 -m venv 4.2.4/.venv
source 4.2.4/.venv/bin/activate
python -m pip install -r 4.2.4/requirements.txt
python 4.2.4/run_branchbench.py --scale smoke --seed-db bb_seed_smoke --plan
```

For 4.2.5, follow its README from the repository root, starting with:

```bash
bash 4.2.5/prepare_branchbench.sh
export PYTHON="$PWD/4.2.5/.runtime/branchbench/.venv/bin/python"
```

Preparation creates an independent, pinned upstream runner under `4.2.5/.runtime/`.
The drivers, configs, dependencies, and runner setup differ between versions, so
those remain version-specific. Each version keeps its own results. Keep the
`common/` directory alongside both version directories so the relative symlinks
resolve. See the version-specific READMEs for setup, execution, and validation
scope. Run each version's tests in a separate Python process with its dependencies.
