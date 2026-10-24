"""Rounding and environment isolation with independently specified results."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from decimal import Decimal, Inexact, ROUND_DOWN, localcontext

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import uncertainty as u


class RoundingTests(unittest.TestCase):
    def test_half_even_both_signs_and_negative_places(self):
        for value, places, expected in (
            ("2.675", 2, "2.68"), ("2.685", 2, "2.68"),
            ("-2.675", 2, "-2.68"), ("-2.685", 2, "-2.68"),
            ("1250", -2, "1.2E+3"), ("1350", -2, "1.4E+3"),
        ):
            with self.subTest(value=value):
                self.assertEqual(str(u.round_half_even(value, places)), expected)

    def test_significant_rounding_carries_change_exponent(self):
        for value, count, expected in (
            ("9.9", 1, "1E+1"), ("9.99", 2, "10"),
            ("-9.95", 2, "-10"), ("999", 1, "1E+3"),
            ("0.0999", 2, "0.10"), ("1.005", 3, "1.00"),
            ("1.015", 3, "1.02"),
        ):
            with self.subTest(value=value, count=count):
                self.assertEqual(str(u.round_sig(value, count)), expected)

    def test_explicit_uncertainty_precision_after_carry(self):
        for uncertainty, count, expected in (
            ("9.9", 1, ("1.2E+2", "1E+1")),
            ("9.99", 2, ("123", "10")),
            ("0.0999", 2, ("123.46", "0.10")),
        ):
            with self.subTest(uncertainty=uncertainty):
                result = u.align_result("123.456", uncertainty, count)
                self.assertEqual(tuple(map(str, result)), expected)

    def test_auto_carry_is_an_explicit_compatibility_policy(self):
        automatic = u.align_result("507.81", "0.95512", "auto")
        strict = u.align_result("507.81", "0.95512", 1)
        self.assertEqual(tuple(map(str, automatic)), ("507.8", "1.0"))
        self.assertEqual(tuple(map(str, strict)), ("508", "1"))

    def test_zero_uncertainty_preserves_scientific_precision(self):
        self.assertEqual(tuple(map(str, u.align_result("1.20E+3", "0"))),
                         ("1.20E+3", "0E+1"))

    def test_scientific_addition_uses_coarsest_recorded_place(self):
        for values, expected, places in (
            (["1.2e3", "11"], "1.2E+3", -2),
            (["1.20e3", "11"], "1.21E+3", -1),
            (["1.20", "-0.003"], "1.20", 2),
            (["-1.2e3", "-11"], "-1.2E+3", -2),
        ):
            with self.subTest(values=values):
                result, nd = u.add_sub(values)
                self.assertEqual((str(result), nd), (expected, places))

    def test_recorded_digits_and_exact_formatting(self):
        self.assertEqual(u.sig_figs("1.00e3"), 3)
        self.assertEqual(u.sig_figs("0.0100"), 3)
        self.assertEqual(u.fmt_exact(u.round_sig("0.0999", 2)), "0.10")
        self.assertEqual(u.fmt("1234", -2), "1200")
        self.assertEqual(u.mul_div(["9.99", "1.00"]), (Decimal("9.99"), 3))

    def test_invalid_precision_arguments(self):
        for value in (True, False, "2", 2.5, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                u.round_half_even("1.25", value)
        for value in (True, False, "2", 2.5):
            with self.subTest(fmt=value), self.assertRaises(ValueError):
                u.fmt("1", value)
        self.assertEqual(u.fmt("1", None), "1")
        for value in (True, 0, -1, 1.5, "2"):
            with self.subTest(sig=value), self.assertRaises(ValueError):
                u.round_sig("1.2", value)

    def test_invalid_nonfinite_values_rejected_across_formatting(self):
        for value in ("NaN", "sNaN", "Infinity", "-Infinity", None, True, ""):
            for function in (u.D, u.round_sig, u.fmt, u.fmt_exact):
                with self.subTest(value=value, function=function.__name__):
                    with self.assertRaises(ValueError):
                        function(value)


class ContextIsolationTests(unittest.TestCase):
    def test_import_preserves_context_and_streams_in_fresh_process(self):
        code = """
import sys
from decimal import getcontext, Inexact, ROUND_DOWN
getcontext().prec = 17
getcontext().rounding = ROUND_DOWN
getcontext().flags[Inexact] = True
before = repr(getcontext())
streams = sys.stdout, sys.stderr
import uncertainty
assert repr(getcontext()) == before
assert (sys.stdout, sys.stderr) == streams
print('unchanged')
"""
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=SCRIPTS,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "unchanged")
        self.assertEqual(result.stderr, "")

    def test_calculations_ignore_host_precision_rounding_and_traps(self):
        for precision in (8, 28, 60):
            with self.subTest(precision=precision), localcontext() as context:
                context.prec = precision
                context.rounding = ROUND_DOWN
                context.traps[Inexact] = True
                context.flags[Inexact] = True
                before = repr(context)
                result = u.linear_fit(
                    ["1000000000000", "1000000000001", "1000000000002"],
                    ["1", "3", "5"],
                )
                self.assertEqual(result["b"], 2)
                self.assertEqual(u.round_half_even("2.675", 2), Decimal("2.68"))
                self.assertEqual(u.mean([1, 2, 3]), 2)
                self.assertEqual(u.selftest(verbose=False), 0)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(u.main(["prop", "--value", "10", "--powers",
                                             "x=2", "--rel", "x=.1"]), 0)
                self.assertEqual(repr(context), before)

    def test_context_restored_after_failure(self):
        with localcontext() as context:
            context.prec = 11
            before = repr(context)
            with self.assertRaises(ValueError):
                u.propagate_numeric(lambda x: x, {"x": ("1", ".1")}, "1e-100")
            self.assertEqual(repr(context), before)


if __name__ == "__main__":
    unittest.main()
