import contextlib
import io
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import release_package, run_mo, run_mo_v424


class LegacyAdapterTests(unittest.TestCase):
    def test_scales_and_worker_timeout_are_preserved(self):
        for old, new in run_mo_v424.SCALES.items():
            args = run_mo_v424.parse_args([
                "--scale", old, "--seed-db", "seed", "--plan", "--timeout", "45"])
            command = run_mo_v424.translate(args)
            self.assertEqual(command[command.index("--scale") + 1], new)
            self.assertEqual(command[command.index("--max-runtime-sec") + 1], "45")
            self.assertEqual(command[command.index("--timeout") + 1], "1845")
            self.assertIn("--check", command)

    def test_container_is_required_for_actual_runs(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run_mo_v424.parse_args(["--scale", "sf100", "--seed-db", "seed"])

    def test_nonpositive_limits_are_rejected(self):
        for option in ("--reps", "--timeout", "--hard-timeout"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                run_mo_v424.parse_args([
                    "--scale", "smoke", "--seed-db", "seed", "--plan", option, "0"])

    def test_credentials_use_environment_not_forwarded_argv(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(run_mo, "main", return_value=2) as forward:
            with contextlib.redirect_stderr(io.StringIO()):
                code = run_mo_v424.main([
                    "--scale", "sf100", "--seed-db", "seed", "--container", "dedicated",
                    "--host", "localhost", "--port", "16001", "--password", "test-secret",
                    "--hard-timeout", "8000", "--output", "/tmp/new-result"])
            self.assertEqual(code, 2)
            self.assertEqual(os.environ["MO_PASSWORD"], "test-secret")
            self.assertEqual(os.environ["MO_PORT"], "16001")
            self.assertNotIn("test-secret", forward.call_args.args[0])
            self.assertIn("8000", forward.call_args.args[0])


class ForwarderTests(unittest.TestCase):
    def test_forwards_exact_driver_interpreter_and_exit_code(self):
        paths = (Path("/package/benchmarks"), Path("/runner"), Path("/runner/.venv/bin/python"))
        with patch.object(run_mo, "prepared_runtime", return_value=paths), patch.object(
                subprocess, "call", return_value=124) as call:
            self.assertEqual(run_mo.main(["--scale", "smoke", "--check"]), 124)
        self.assertEqual(call.call_args.args[0], [
            "/runner/.venv/bin/python", "/package/benchmarks/run_branchbench.py",
            "--backend", "MATRIXONE", "--repo", "/runner", "--scale", "smoke", "--check"])

    def test_preparation_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "--prepare first"):
                release_package.prepared_runtime(Path(directory) / "absent")

    def test_override_cannot_select_an_unpinned_backend_runner_or_config(self):
        for flag in ("--backend=DOLT", "--back=DOLT", "--repo", "--configs=/old", "--expected-version=4.2.4"):
            with contextlib.redirect_stderr(io.StringIO()), patch.object(run_mo, "prepared_runtime") as ready:
                self.assertEqual(run_mo.main([flag]), 1)
                ready.assert_not_called()

    def test_package_head_and_local_changes_are_rejected(self):
        with patch.object(subprocess, "check_output", side_effect=["wrong-head\n", ""]):
            with self.assertRaisesRegex(RuntimeError, "pinned commit"):
                release_package.verify_package(Path("/package"))
        with patch.object(subprocess, "check_output", side_effect=[release_package.PACKAGE_COMMIT, " M benchmarks/run_branchbench.py"]):
            with self.assertRaisesRegex(RuntimeError, "pinned commit"):
                release_package.verify_package(Path("/package"))

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(RuntimeError, "destination exists"):
            release_package.prepare(Path(directory))

    def test_subprocess_failure_is_nonzero(self):
        with contextlib.redirect_stderr(io.StringIO()), patch.object(
                run_mo, "prepared_runtime", side_effect=subprocess.CalledProcessError(1, "git")):
            self.assertEqual(run_mo.main([]), 1)


class SeedParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        benchmarks, _, _ = release_package.prepared_runtime()
        spec = importlib.util.spec_from_file_location("canonical_seed", benchmarks / "load_seed.py")
        cls.loader = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(benchmarks), *sys.path]):
            spec.loader.exec_module(cls.loader)

    def test_published_sql_matches_canonical_bounded_generator(self):
        for scale in ("100", "1000"):
            with self.subTest(scale=scale):
                statements = list(self.loader.seed_statements(scale))
                expected = "".join(statement + ";\n" for statement in statements)
                path = release_package.ROOT / "scripts" / "mo_v424_seed" / f"ch_benchmark_seed_mo_sf{scale}.sql"
                self.assertEqual(path.read_text(), expected)
                self.assertEqual(sum(statement.startswith("INSERT INTO order_line ") for statement in statements),
                                 int(scale))
                self.assertEqual(self.loader.expected_counts(scale)["order_line"], int(scale) * 300000)


if __name__ == "__main__":
    unittest.main()
