"""Real CLI success/error contracts plus direct-call parser validation."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import uncertainty as u


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / "uncertainty.py"),
                               *arguments], capture_output=True, text=True,
                              encoding="utf-8")

    def test_all_commands_have_successful_direct_and_process_paths(self):
        examples = (
            (("direct", "--values", "1,3", "--delta-inst", "3", "--C", "3"), "n=2"),
            (("bridge", "--R1", "100", "--R2", "100", "--R0", "500", "--dR0", ".1"), "Rx=500"),
            (("boxerr", "--reading", "508.5", "--m", "6"), "0.59500"),
            (("prop", "--value", "-12", "--powers", "x=2,y=-1", "--rel", "x=.03,y=.08"), "1.200000"),
            (("fit", "--x", "0,1,2,3", "--y", "1,2,2,4"), "b=0.900000"),
            (("diff", "--values", "0,2,4,6", "--step", ".5"), "4.000000"),
            (("round", "--value", "123.456", "--u", "9.9", "--sig", "1"), "120 ± 10"),
            (("round", "--value", "9.99", "--sig", "2"), "10"),
            (("selftest",), "全部通过"),
        )
        for arguments, expected in examples:
            with self.subTest(arguments=arguments):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(u.main(list(arguments)), 0)
                self.assertIn(expected, output.getvalue())
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)
                self.assertEqual(result.stderr, "")

    def test_duplicate_variable_cannot_override_input(self):
        for option, text in (("--powers", "x=1,x=2"), ("--rel", "x=.1,x=.2")):
            arguments = ["prop", "--value", "2", "--powers", "x=1", "--rel", "x=.1"]
            arguments[arguments.index(option) + 1] = text
            with self.subTest(option=option):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIn("重复变量", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_extra_and_missing_uncertainty_are_errors(self):
        for relative in ("y=.1", "x=.1,y=.2"):
            with self.subTest(relative=relative):
                result = self.run_cli("prop", "--value", "2", "--powers", "x=1",
                                      "--rel", relative)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)

    def test_malformed_assignments_are_diagnostic(self):
        for text in ("", "x", "=1", "x=", "x=1,", "x=1=2", "x=NaN"):
            with self.subTest(text=text):
                result = self.run_cli("prop", "--value", "2", "--powers", text,
                                      "--rel", "x=.1")
                self.assertEqual(result.returncode, 2)
                self.assertIn("输入或计算错误", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_assignment_whitespace_is_accepted(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = u.main(["prop", "--value", "2", "--powers", " x = 2 ",
                             "--rel", " x = .1 "])
        self.assertEqual(result, 0)
        self.assertIn("0.400000", output.getvalue())

    def test_invalid_measurement_inputs_have_exit_two(self):
        for arguments in (
            ("direct", "--values", "1,,3"),
            ("direct", "--values", "1"),
            ("fit", "--x", "0,1,2", "--y", "1,2"),
            ("diff", "--values", "1,2,3"),
            ("boxerr", "--reading", "100000", "--m", "6"),
            ("round", "--value", "1", "--u", "-.1"),
        ):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIn("输入或计算错误", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_help_and_argument_parser_error_status(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("direct", result.stdout)
        result = self.run_cli("direct")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_undefined_relative_results_are_printed(self):
        result = self.run_cli("direct", "--values=-1,0,1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("未定义", result.stdout)


if __name__ == "__main__":
    unittest.main()
