import unittest
from unittest.mock import patch

from macrobench.validation import summarize_run_validity


class ValidityTests(unittest.TestCase):
    def test_clean_run(self):
        work = {0: {"steps": 2, "status": "completed", "operation_errors": {}}}
        self.assertTrue(summarize_run_validity(work, 1, 2, False)["valid"])

    def test_completed_steps_with_sql_error_is_invalid(self):
        work = {0: {"steps": 2, "status": "completed_with_errors",
                    "operation_errors": {"dml": 1}}}
        result = summarize_run_validity(work, 1, 2, False)
        self.assertFalse(result["valid"])
        self.assertEqual(result["total_operation_errors"], 1)
        self.assertIn("operation_errors", result["invalid_reasons"])

    def test_missing_worker_and_timeout_are_invalid(self):
        result = summarize_run_validity({}, 2, 1, True)
        self.assertEqual(result["invalid_reasons"],
                         ["runtime_cap", "missing_workers", "incomplete_steps"])

    def test_worker_exception_is_invalid_even_when_steps_finished(self):
        work = {0: {"steps": 1, "status": "completed", "operation_errors": {}}}
        result = summarize_run_validity(work, 1, 1, False, worker_exceptions=1)
        self.assertEqual(result["invalid_reasons"], ["worker_exceptions"])


class CleanupTests(unittest.TestCase):
    def test_matrixone_cleanup_matches_normalized_database_names(self):
        from microbench import task_pb2
        from microbench.runner import BackendInfo, cleanup_backend

        class Cursor:
            def __init__(self):
                self.sql = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, sql):
                self.sql.append(sql)

            def fetchall(self):
                return [("run1",), ("run1_br_a",), ("run1_other",)]

        class Connection:
            def __init__(self):
                self.cur = Cursor()

            def cursor(self):
                return self.cur

            def close(self):
                pass

        config = task_pb2.TaskConfig()
        config.backend = task_pb2.Backend.MATRIXONE
        config.database_setup.db_name = "Run1"
        config.database_setup.cleanup = True
        conn = Connection()
        with patch("microbench.runner.mo._connect", return_value=conn):
            cleanup_backend(config, BackendInfo())
        self.assertEqual(conn.cur.sql[1:], [
            "DROP DATABASE IF EXISTS `run1`;",
            "DROP DATABASE IF EXISTS `run1_br_a`;",
        ])


if __name__ == "__main__":
    unittest.main()
