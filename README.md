# BranchBench — MatrixOne 4.2.4

本仓库包含 BranchBench 的五个 workflow（software_dev、failure_repro、data_cleaning、mcts、simulation），支持 SF100 和 SF1000。`microbench/` 是宏基准 runner 复用的内部运行依赖；已包含生成好的 protobuf 代码。

## 准备

需要 Python 3.11+ 和已加载的 MatrixOne 种子数据库。`scripts/mo_v424_seed/` 提供 SF100、SF1000 的 SQL。以 SF100 为例：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-mo-v424.txt

export MO_HOST=127.0.0.1 MO_PORT=6001 MO_USER=root MO_PASSWORD='你的密码'
MYSQL_PWD="$MO_PASSWORD" mysql -h "$MO_HOST" -P "$MO_PORT" -u "$MO_USER" -e 'CREATE DATABASE ch_sf100;'
MYSQL_PWD="$MO_PASSWORD" mysql -h "$MO_HOST" -P "$MO_PORT" -u "$MO_USER" ch_sf100 < scripts/mo_v424_seed/ch_benchmark_seed_mo_sf100.sql
```

## 轻量实测

`scripts/mo_v424_seed/ch_benchmark_seed_mo_smoke.sql` 是专用小数据集。在独立 MO 4.2.4 实例上导入到 `ch_smoke` 数据库后运行：

```bash
python scripts/run_mo_v424.py --scale smoke --seed-db ch_smoke --reps 1
```

这会对五个 workflow 各执行一次缩小 workers/steps 的真实 SQL，检查操作错误与清理；`smoke` 结果不是 SF100/SF1000 性能数据。

## 运行

```bash
python scripts/run_mo_v424.py --scale sf100 --seed-db ch_sf100 --plan
python scripts/run_mo_v424.py --scale sf100 --seed-db ch_sf100 --reps 1
```

SF1000 使用对应的 SQL、独立种子库与 `--scale sf1000`。可用 `--workflows simulation` 等只跑指定 workflow。默认是完整 workload，simulation 为 1000 workers × 1 step。仅在隔离的 MO 实例运行完整规模。

Driver 会检查 MO 版本含 `4.2.4` 及种子表行数，然后为每次运行克隆数据库。运行结果和日志保存在 `results/mo_v424/`；`runs.jsonl` 标记每次运行是否有效。runner 会在结束时清理本次克隆和分支，保留种子库。

同一版驱动在本机隔离容器 `matrixorigin/matrixone:4.2.4` 上完成五个 workflow 的轻量 smoke：SQL 操作错误 0，克隆库残留 0。本仓库仅保留 MO 所需的 backend 和基准文件，已核对 runner 导入及计划生成；未重复数据库测试。完整 SF100/SF1000 性能仍需专门环境重测。

源码基线：[dengn/matrixone-branchbench](https://github.com/dengn/matrixone-branchbench)，commit `95c18b7bf7a51029e3344a65e807df07aa28a2ea`；MO 4.2.4 适配和严格错误检查是本包改动。
