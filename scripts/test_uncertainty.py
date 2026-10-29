"""计算内核回归；构造数据仅用于测试，不能用作实验测量值。"""

import contextlib
import io
import subprocess
import sys
import unittest
from decimal import Decimal, localcontext

import uncertainty as u


class KernelRegression(unittest.TestCase):
    def test_delivered_baselines(self):
        self.assertEqual(u.selftest(verbose=False), 0)

    def test_half_even_and_recorded_digits(self):
        self.assertEqual(u.round_half_even("2.675", 2), Decimal("2.68"))
        self.assertEqual(u.round_half_even("2.685", 2), Decimal("2.68"))
        self.assertEqual(u.sig_figs("1.00"), 3)
        self.assertEqual(u.sig_figs("0.0100"), 3)
        self.assertEqual(u.sig_figs("1.00e3"), 3)
        self.assertEqual(u.mul_div(["1.00", "2.00"]), (Decimal("2.00"), 3))

    def test_fixed_decimal_places(self):
        self.assertEqual(u.fmt("1", 2), "1.00")
        self.assertEqual(u.fmt("1.00"), "1")

    def test_auto_and_zero_uncertainty(self):
        v, d = u.align_result("508.5", "1.04824")
        self.assertEqual((str(v), str(d)), ("508.5", "1.0"))
        v, d = u.align_result("1.2340", "0")
        self.assertEqual((str(v), str(d)), ("1.2340", "0.0000"))

    def test_negative_uncertainty_rejected(self):
        for f in (
            lambda: u.align_result("1", "-0.1"),
            lambda: u.type_b("-1", "3"),
            lambda: u.combine("-1", "2"),
            lambda: u.propagate_power({"x": 1}, {"x": "-0.1"}, "2"),
        ):
            with self.subTest(f=f), self.assertRaises(ValueError):
                f()

    def test_invalid_rounding_modes(self):
        for mode in (0, -1, 3, 1.5, True):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                u.align_result("1", "0.1", mode)

    def test_nonfinite_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                u.mean([value, "1"])

    def test_empty_inputs(self):
        for f in (
            lambda: u.mean([]),
            lambda: u.direct_result([]),
            lambda: u.successive_difference([]),
            lambda: u.add_sub([]),
            lambda: u.mul_div([]),
        ):
            with self.subTest(f=f), self.assertRaises(ValueError):
                f()

    def test_direct_zero_and_negative_means(self):
        zero = u.direct_result(["-1", "0", "1"])
        self.assertIsNone(zero["Ur"])
        self.assertIsNone(zero["Ur_from_rounded"])
        self.assertEqual(zero["xbar"], 0)
        negative = u.direct_result(["-2", "-3", "-4"])
        self.assertGreater(negative["Ur"], 0)

    def test_identical_measurements_keep_value(self):
        r = u.direct_result(["1.234", "1.234", "1.234"])
        self.assertEqual(r["result_2sf"][0], Decimal("1.234"))
        self.assertEqual(r["U"], 0)

    def test_single_measurement(self):
        r = u.direct_result(["1.20"], delta_inst="0.03", C="3")
        self.assertIsNone(r["uA"])
        self.assertEqual(r["U"], Decimal("0.02"))
        with self.assertRaises(ValueError):
            u.direct_result(["1.20"])

    def test_direct_parameter_validation(self):
        for kw in (
            {"algo": 3},
            {"delta_inst": "-1", "C": "3"},
            {"delta_inst": "1", "C": "0"},
            {"algo": 2, "conf": "0.99"},
            {"algo": 2, "t_value": "-2"},
        ):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                u.direct_result(["1", "2", "3"], **kw)
        self.assertEqual(u.direct_result(["1", "2", "3"], algo=2)["t"], Decimal("4.303"))
        self.assertEqual(
            u.direct_result(["1", "2", "3"], algo=2, conf="0.99", t_value="9.925")["t"],
            Decimal("9.925"),
        )

    def test_box_error_and_bad_readings(self):
        self.assertEqual(u.resistance_box_error("508.5", 6)[0], Decimal("0.595"))
        for reading in ("-1", "0.01", "100000"):
            with self.subTest(reading=reading), self.assertRaises(ValueError):
                u.resistance_box_error(reading, 6)
        with self.assertRaises(ValueError):
            u.resistance_box_error("100", 0)
        with self.assertRaises(ValueError):
            u.resistance_box_error("100", 4, m_mode="typo")
        custom = {"10": "0.2", "1": "0.5"}
        self.assertEqual(u.resistance_box_error("12", 2, grades=custom)[0], Decimal("0.04"))
        with self.assertRaises(ValueError):
            u.resistance_box_error("100", 4, grades={})

    def test_bridge_requires_positive_measurements(self):
        for kw in (
            {"R1": "0"},
            {"R2": "0"},
            {"R0": "-1"},
            {"delta_R0_measured": "0"},
            {"delta_R0_measured": "-1"},
            {"delta_d": "0"},
            {"threshold": "-0.2"},
        ):
            args = dict(R1="100", R2="100", R0="508.5", delta_R0_measured="0.1")
            args.update(kw)
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                u.bridge_row(**args)

    def test_negative_value_has_positive_propagated_uncertainty(self):
        r = u.propagate_power({"x": 2}, {"x": "0.1"}, "-10")
        self.assertEqual(r["u"], Decimal("2"))

    def test_numeric_propagation(self):
        r = u.propagate_numeric(
            lambda x, y: x + 2 * y, {"x": ("1", "0.3"), "y": ("2", "0.2")}, rel_step="1e-6"
        )
        self.assertEqual(r["value"], 5)
        self.assertEqual(r["u"], Decimal("0.5"))
        for step in ("0", "-0.1"):
            with self.subTest(step=step), self.assertRaises(ValueError):
                u.propagate_numeric(lambda x: x, {"x": (1, "0.1")}, step)

    def test_fit_pairing_and_degeneracy(self):
        with self.assertRaises(ValueError):
            u.linear_fit([0, 1, 2], [1, 2])
        with self.assertRaises(ValueError):
            u.linear_fit([1, 1, 1], [0, 1, 2])
        r = u.linear_fit([0, 1, 2, 3], [1, 3, 5, 7])
        self.assertEqual((r["a"], r["b"], r["gamma"], r["sse"]), (1, 2, 1, 0))
        r = u.linear_fit([0, 1, 2], [2, 2, 2])
        self.assertEqual(r["b"], 0)
        self.assertIsNone(r["gamma"])

    def test_fit_large_offset(self):
        # Construct recorded inputs exactly, independently of caller context.
        xs = [Decimal(10**40 + i) for i in range(4)]
        r = u.linear_fit(xs, [1, 3, 5, 7])
        self.assertEqual(r["b"], 2)
        self.assertEqual(r["sse"], 0)

    def test_noisy_fit_parameter_uncertainties(self):
        r = u.linear_fit([0, 1, 2, 3], [1, 2, 2, 4])
        self.assertEqual(r["a"], Decimal("0.9"))
        self.assertEqual(r["b"], Decimal("0.9"))
        self.assertEqual(r["sse"], Decimal("0.7"))
        with localcontext() as context:
            context.prec = 60
            self.assertLess(abs(r["u_b"] ** 2 - Decimal("0.07")), Decimal("1e-55"))
            self.assertLess(abs(r["u_a"] ** 2 - Decimal("0.245")), Decimal("1e-55"))

    def test_cli_does_not_drop_missing_measurements(self):
        for args in (
            ["direct", "--values", "1,,3"],
            ["fit", "--x", "1,2,3", "--y", "1,,3"],
            ["diff", "--values", "1,2,3,4,"],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                u.main(args)

    def test_cli_input_error_exit_status(self):
        result = subprocess.run(
            [sys.executable, "-B", u.__file__, "fit", "--x", "0,1,2", "--y", "1,2"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("数据个数必须相同", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_successive_difference(self):
        r = u.successive_difference([0, 2, 4, 6, 8, 10], step="0.5")
        self.assertEqual(r["diffs"], [6, 6, 6])
        self.assertEqual(r["avg_step"], 2)
        self.assertEqual(r["slope"], 4)
        for values, step in (([1, 2, 3], None), ([1, 2], "0")):
            with self.subTest(values=values, step=step), self.assertRaises(ValueError):
                u.successive_difference(values, step)

    def test_cli_preserves_digits_and_handles_optional_values(self):
        for args, expected in (
            (["round", "--value", "508.5", "--u", "1.04824"], "508.5 ± 1.0"),
            (["round", "--value", "508.5", "--u", "1.04824", "--sig", "1"], "508 ± 1"),
            (
                ["bridge", "--R1", "100", "--R2", "100", "--R0", "508.5", "--dR0", "0.1"],
                "508.5 ± 1.0",
            ),
            (["direct", "--values", "1.20", "--delta-inst", "0.03", "--C", "3"], "0.02"),
            (["fit", "--x", "0,1,2", "--y", "2,2,2"], "未定义"),
            (["direct", "--values=-1,0,1"], "未定义"),
        ):
            with self.subTest(args=args):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(u.main(args), 0)
                self.assertIn(expected, output.getvalue())


if __name__ == "__main__":
    unittest.main()
