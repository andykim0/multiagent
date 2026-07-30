"""Regression tests for the csvstats command-line tool."""

import ast
import contextlib
import csv
import importlib.util
import io
import json
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


TEST_DIR = pathlib.Path(__file__).resolve().parent
ROOT = TEST_DIR.parent
SCRIPT = ROOT / "csvstats.py"
FIXTURES = TEST_DIR / "fixtures"

SPEC = importlib.util.spec_from_file_location("csvstats_under_test", SCRIPT)
csvstats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(csvstats)


def fixture(name):
    return FIXTURES / name


def run_main(arguments):
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = csvstats.main([str(argument) for argument in arguments])
    except SystemExit as error:
        code = error.code
    return code, stdout.getvalue(), stderr.getvalue()


class CsvstatsTests(unittest.TestCase):
    maxDiff = None

    def assert_one_line_error(self, code, stdout, stderr, expected_code):
        self.assertEqual(code, expected_code)
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("csvstats: error: "))
        self.assertTrue(stderr.endswith("\n"))
        self.assertEqual(len(stderr.splitlines()), 1)

    def test_sample_table_is_byte_exact_and_bom_is_consumed(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "sample.csv"],
            cwd=FIXTURES,
            text=True,
            capture_output=True,
            check=False,
        )
        expected = (
            "sample.csv: 4 rows, 2 columns\n"
            "\n"
            "Numeric columns:\n"
            "#  column  count  missing  min  max  mean  median  stdev\n"
            "-  ------  -----  -------  ---  ---  ----  ------  -----\n"
            "2  temp        3        1    2    6     4       4      2\n"
            "\n"
            "Text columns:\n"
            "#  column  count  missing  unique  top\n"
            "-  ------  -----  -------  ------  ------\n"
            "1  city        4        0       3  boston\n"
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, expected)
        self.assertEqual(completed.stderr, "")
        self.assertNotIn("\ufeff", completed.stdout)
        self.assertEqual(
            [len(line) for line in completed.stdout.splitlines()],
            [29, 0, 16, 56, 56, 56, 0, 13, 38, 41, 41],
        )

    def test_json_envelope_order_stats_and_count_invariant(self):
        path = fixture("sample.csv")
        code, stdout, stderr = run_main(["--json", path])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertNotIn("NaN", stdout)
        self.assertNotIn("Infinity", stdout)
        payload = json.loads(stdout)
        self.assertEqual(list(payload), ["file", "rows", "ragged", "columns"])
        self.assertEqual(payload["file"], str(path))
        self.assertEqual(payload["rows"], 4)
        self.assertFalse(payload["ragged"])
        self.assertIsInstance(payload["columns"], list)
        self.assertEqual([column["name"] for column in payload["columns"]], ["city", "temp"])
        self.assertEqual(
            list(payload["columns"][0]),
            ["name", "type", "count", "missing", "unique", "top"],
        )
        self.assertEqual(
            list(payload["columns"][1]),
            [
                "name",
                "type",
                "count",
                "missing",
                "min",
                "max",
                "mean",
                "median",
                "stdev",
            ],
        )
        for column in payload["columns"]:
            self.assertEqual(column["count"] + column["missing"], payload["rows"])

    def test_nonexistent_file_is_exit_two_with_empty_stdout(self):
        path = FIXTURES / "does-not-exist.csv"
        code, stdout, stderr = run_main([path])
        self.assertEqual(stderr, f"csvstats: error: no such file: {path}\n")
        self.assert_one_line_error(code, stdout, stderr, 2)

    def test_empty_and_newline_only_are_no_columns_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = pathlib.Path(directory) / "empty.csv"
            empty.write_bytes(b"")
            code, stdout, stderr = run_main([empty])
            self.assertEqual(
                stderr, f"csvstats: error: no columns found: {empty}\n"
            )
            self.assert_one_line_error(code, stdout, stderr, 1)

        newline = fixture("newline_only.csv")
        code, stdout, stderr = run_main([newline])
        self.assertEqual(
            stderr, f"csvstats: error: no columns found: {newline}\n"
        )
        self.assert_one_line_error(code, stdout, stderr, 1)

    def test_numeric_text_nonfinite_scientific_missing_and_strip_rules(self):
        path = fixture("types.csv")
        code, stdout, stderr = run_main(["--json", path])
        self.assertEqual((code, stderr), (0, ""))
        payload = json.loads(stdout)
        columns = {column["name"]: column for column in payload["columns"]}

        numeric = columns["numeric"]
        self.assertEqual((numeric["type"], numeric["count"], numeric["missing"]), ("numeric", 3, 1))
        self.assertEqual(
            numeric["mean"], statistics.mean([1.0, 2.5, 3.0])
        )
        self.assertEqual(numeric["median"], 2.5)

        self.assertEqual(columns["mixed"]["type"], "text")
        self.assertEqual(columns["nonfinite"]["type"], "text")
        self.assertEqual(columns["sci"]["type"], "numeric")
        self.assertEqual(columns["sci"]["min"], 2.0)
        self.assertEqual(
            columns["all_missing"],
            {
                "name": "all_missing",
                "type": "text",
                "count": 0,
                "missing": 4,
                "unique": 0,
                "top": None,
            },
        )
        self.assertEqual(columns["striptext"]["count"], 3)
        self.assertEqual(columns["striptext"]["unique"], 1)
        self.assertEqual(columns["striptext"]["top"], "a")

        code, table, stderr = run_main([path])
        self.assertEqual((code, stderr), (0, ""))
        numeric_line = next(
            line for line in table.splitlines() if line.startswith("1  numeric")
        )
        self.assertIn("2.1667", numeric_line)
        self.assertIn("2.5", numeric_line)

    def test_all_nonfinite_spellings_and_hex_are_text(self):
        code, stdout, stderr = run_main(
            ["--json", fixture("nonfinite.csv")]
        )
        self.assertEqual((code, stderr), (0, ""))
        columns = json.loads(stdout)["columns"]
        self.assertEqual(
            [column["type"] for column in columns],
            ["text", "text", "text", "text", "text", "numeric", "text"],
        )
        self.assertNotIn("NaN", stdout)
        self.assertNotIn("Infinity", stdout)

    def test_ragged_rows_pad_truncate_and_warn_once(self):
        code, stdout, stderr = run_main(
            ["--json", fixture("ragged.csv")]
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, csvstats.RAGGED_WARNING + "\n")
        self.assertEqual(len(stderr.splitlines()), 1)
        payload = json.loads(stdout)
        self.assertTrue(payload["ragged"])
        self.assertEqual(payload["rows"], 2)
        self.assertEqual(
            [(column["count"], column["missing"]) for column in payload["columns"]],
            [(2, 0), (2, 0), (1, 1)],
        )
        self.assertEqual(payload["columns"][2]["max"], 5.0)

    def test_no_header_includes_first_row_and_handles_ragged_rows(self):
        code, stdout, stderr = run_main(
            ["--no-header", "--json", fixture("no_header_ragged.csv")]
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, csvstats.RAGGED_WARNING + "\n")
        payload = json.loads(stdout)
        self.assertEqual(payload["rows"], 3)
        self.assertEqual(
            [column["name"] for column in payload["columns"]], ["col1", "col2"]
        )
        self.assertEqual(payload["columns"][0]["min"], 1.0)
        self.assertEqual(payload["columns"][1]["count"], 2)
        self.assertEqual(payload["columns"][1]["missing"], 1)

        whitespace = fixture("whitespace_only.csv")
        code, stdout, stderr = run_main(
            ["--no-header", "--json", whitespace]
        )
        self.assertEqual((code, stderr), (0, ""))
        payload = json.loads(stdout)
        self.assertEqual(payload["rows"], 1)
        self.assertEqual(
            payload["columns"],
            [
                {
                    "name": "col1",
                    "type": "text",
                    "count": 0,
                    "missing": 1,
                    "unique": 0,
                    "top": None,
                }
            ],
        )

    def test_semicolon_delimiter_and_delimiter_errors(self):
        code, stdout, stderr = run_main(
            ["--delimiter", ";", "--json", fixture("semicolon.csv")]
        )
        self.assertEqual((code, stderr), (0, ""))
        payload = json.loads(stdout)
        self.assertEqual(payload["rows"], 2)
        self.assertEqual([column["name"] for column in payload["columns"]], ["name", "score"])

        message = (
            "csvstats: error: --delimiter must be a single character other "
            "than '\"', CR or LF"
        )
        for delimiter in ["", ",,", '"']:
            with self.subTest(delimiter=delimiter):
                code, stdout, stderr = run_main(
                    ["--delimiter", delimiter, fixture("sample.csv")]
                )
                self.assert_one_line_error(code, stdout, stderr, 1)
                self.assertEqual(stderr, f"{message} (got '{delimiter}')\n")

        for delimiter, shown in [("\r", r"\r"), ("\n", r"\n")]:
            with self.subTest(delimiter=shown):
                code, stdout, stderr = run_main(
                    ["--delimiter", delimiter, fixture("sample.csv")]
                )
                self.assert_one_line_error(code, stdout, stderr, 1)
                self.assertEqual(stderr, f"{message} (got '{shown}')\n")

    def test_argparse_usage_errors_and_help(self):
        for arguments in [[], ["--nope"]]:
            with self.subTest(arguments=arguments):
                code, stdout, stderr = run_main(arguments)
                self.assert_one_line_error(code, stdout, stderr, 1)

        code, stdout, stderr = run_main(["--help"])
        self.assertEqual((code, stderr), (0, ""))
        for required in [
            "usage: csvstats",
            "Print per-column statistics for a CSV file.",
            "FILE",
            "path to the CSV file",
            "--delimiter CHAR",
            'field delimiter (default: ",")',
            "--no-header",
            "treat the first row as data and name columns col1..colN",
            "--json",
            "print JSON instead of the formatted table",
            "exit codes: 0 success, 1 data error, 2 file error",
        ]:
            self.assertIn(required, stdout)

    def test_duplicate_names_are_preserved_by_position(self):
        path = fixture("duplicates.csv")
        code, stdout, stderr = run_main(["--json", path])
        self.assertEqual((code, stderr), (0, ""))
        columns = json.loads(stdout)["columns"]
        self.assertEqual([column["name"] for column in columns], ["a", "b", "a"])
        self.assertEqual(len(columns), 3)

        code, table, stderr = run_main([path])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(
            [
                re.split(r" {2,}", line)[1]
                for line in table.splitlines()
                if line.startswith(("1  ", "3  "))
            ],
            ["a", "a"],
        )

    def test_header_only_is_success_and_matches_empty_data_rules(self):
        path = fixture("header_only.csv")
        code, stdout, stderr = run_main(["--json", path])
        self.assertEqual((code, stderr), (0, ""))
        payload = json.loads(stdout)
        self.assertEqual(payload["rows"], 0)
        for column in payload["columns"]:
            self.assertEqual(column["type"], "text")
            self.assertEqual(
                (column["count"], column["missing"], column["unique"], column["top"]),
                (0, 0, 0, None),
            )

        with tempfile.TemporaryDirectory() as directory:
            head = pathlib.Path(directory) / "head.csv"
            head.write_bytes(path.read_bytes())
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "head.csv"],
                cwd=directory,
                text=True,
                capture_output=True,
                check=False,
            )
        expected = (
            "head.csv: 0 rows, 2 columns\n"
            "\n"
            "Text columns:\n"
            "#  column  count  missing  unique  top\n"
            "-  ------  -----  -------  ------  ---\n"
            "1  city        0        0       0  N/A\n"
            "2  temp        0        0       0  N/A\n"
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, expected)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(
            [len(line) for line in completed.stdout.splitlines()],
            [27, 0, 13, 38, 38, 38, 38],
        )

    def test_enotdir_is_caught_as_generic_file_error(self):
        with tempfile.TemporaryDirectory() as directory:
            regular_file = pathlib.Path(directory) / "f.csv"
            regular_file.write_text("a\n1\n", encoding="utf-8")
            path = regular_file / "inner.csv"
            code, stdout, stderr = run_main([path])

        self.assertEqual(
            stderr, f"csvstats: error: cannot read file: {path}\n"
        )
        self.assertNotIn("Traceback", stderr)
        self.assert_one_line_error(code, stdout, stderr, 2)

    def test_oversized_field_is_caught_as_csv_parse_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "big.csv"
            path.write_text(
                "a\n" + "x" * (csv.field_size_limit() + 1) + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = run_main([path])

        self.assertEqual(
            stderr, f"csvstats: error: cannot parse as CSV: {path}\n"
        )
        self.assertNotIn("Traceback", stderr)
        self.assert_one_line_error(code, stdout, stderr, 1)

    def test_pep_515_underscores_are_numeric(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "underscores.csv"
            path.write_text("value\n1_000\n2\n", encoding="utf-8")
            code, stdout, stderr = run_main(["--json", path])

        self.assertEqual((code, stderr), (0, ""))
        column = json.loads(stdout)["columns"][0]
        self.assertEqual(column["type"], "numeric")
        self.assertEqual(column["min"], 2.0)
        self.assertEqual(column["max"], 1000.0)
        self.assertEqual(column["mean"], 501.0)

    def test_quoted_commas_and_embedded_newlines_use_real_csv_parsing(self):
        code, stdout, stderr = run_main(
            ["--json", fixture("quoted.csv")]
        )
        self.assertEqual((code, stderr), (0, ""))
        payload = json.loads(stdout)
        self.assertEqual(payload["rows"], 2)
        self.assertEqual(len(payload["columns"]), 2)
        self.assertEqual(payload["columns"][0]["type"], "text")
        self.assertEqual(payload["columns"][0]["top"], "1,000")
        self.assertEqual(payload["columns"][1]["top"], "hello\nworld")

    def test_whitespace_and_tab_only_default_mode_are_errors(self):
        for name in ["whitespace_only.csv", "tab_only.csv"]:
            with self.subTest(name=name):
                path = fixture(name)
                code, stdout, stderr = run_main([path])
                self.assertEqual(
                    stderr, f"csvstats: error: no columns found: {path}\n"
                )
                self.assert_one_line_error(code, stdout, stderr, 1)

    def test_all_blank_header_with_data_and_leading_blank_line(self):
        path = fixture("all_blank_header.csv")
        code, stdout, stderr = run_main(["--json", path])
        self.assertEqual((code, stderr), (0, ""))
        payload = json.loads(stdout)
        self.assertEqual(payload["rows"], 2)
        self.assertEqual([column["name"] for column in payload["columns"]], ["", "", ""])
        self.assertEqual([column["type"] for column in payload["columns"]], ["numeric"] * 3)

        code, table, stderr = run_main([path])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("#  column", table)
        self.assertNotIn("col1", table)

        code, stdout, stderr = run_main(
            ["--json", fixture("leading_blank.csv")]
        )
        self.assertEqual((code, stderr), (0, ""))
        payload = json.loads(stdout)
        self.assertEqual(payload["rows"], 2)
        self.assertFalse(payload["ragged"])
        self.assertEqual([column["name"] for column in payload["columns"]], ["left", "right"])

    def test_file_error_messages_for_directory_permission_and_decode(self):
        code, stdout, stderr = run_main([FIXTURES])
        self.assertEqual(stderr, f"csvstats: error: is a directory: {FIXTURES}\n")
        self.assert_one_line_error(code, stdout, stderr, 2)

        with mock.patch.object(csvstats, "read_rows", side_effect=PermissionError):
            code, stdout, stderr = run_main(["private.csv"])
        self.assertEqual(stderr, "csvstats: error: permission denied: private.csv\n")
        self.assert_one_line_error(code, stdout, stderr, 2)

        with tempfile.TemporaryDirectory() as directory:
            invalid = pathlib.Path(directory) / "invalid.csv"
            invalid.write_bytes(b"name\n\xff\n")
            code, stdout, stderr = run_main([invalid])
            self.assertEqual(
                stderr,
                f"csvstats: error: cannot decode as utf-8: {invalid}\n",
            )
            self.assert_one_line_error(code, stdout, stderr, 2)

    def test_number_and_hostile_data_display_formatting(self):
        cases = [
            (4.0, "4"),
            (2.1666666666666665, "2.1667"),
            (2.5, "2.5"),
            (-0.0, "0"),
            (1e15, "1.0000e+15"),
            (-3e-7, "-3.0000e-07"),
            (1e-4, "0.0001"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(csvstats.fmt_num(value), expected)

        self.assertEqual(csvstats.display_text("a\tb\nc\x7fd"), "a b c d")
        self.assertEqual(
            csvstats.display_text("123456789012345678901"),
            "12345678901234567...",
        )

    def test_every_import_is_from_the_standard_library(self):
        for path in [SCRIPT, pathlib.Path(__file__).resolve()]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(
                        alias.name.split(".", 1)[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".", 1)[0])
            self.assertTrue(
                imported <= sys.stdlib_module_names,
                f"{path} has non-stdlib imports: "
                f"{sorted(imported - sys.stdlib_module_names)}",
            )


if __name__ == "__main__":
    unittest.main()
