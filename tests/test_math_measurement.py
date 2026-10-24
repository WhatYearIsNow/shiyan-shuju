"""Independent statistics, uncertainty recipes, and scoped instrument checks."""
from pathlib import Path
import sys
import unittest
from decimal import Decimal, localcontext

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uncertainty as u


class MeasurementTests(unittest.TestCase):
    def assertSquared(self, actual, expected):
        with localcontext() as context:
            context.prec = 60
            self.assertLess(abs(actual * actual - Decimal(expected)), Decimal("1e-55"))

    def test_sample_variance_and_mean_standard_uncertainty(self):
        self.assertEqual(u.mean([1, 2, 3, 4, 5]), 3)
        self.assertSquared(u.std_dev([1, 2, 3, 4, 5]), "2.5")
        self.assertSquared(u.std_dev_mean([1, 2, 3, 4, 5]), "0.5")
        self.assertEqual(u.std_dev_mean([1, 3]), 1)

    def test_translation_scaling_and_permutation(self):
        values = [1, 2, 3, 4, 5]
        self.assertEqual(u.std_dev(values), u.std_dev(reversed(values)))
        self.assertEqual(u.std_dev(values), u.std_dev([x + 100 for x in values]))
        with localcontext() as context:
            context.prec = 60
            self.assertLess(abs(u.std_dev([-2 * x for x in values])
                                - 2 * u.std_dev(values)), Decimal("1e-57"))

    def test_iterables_consumed_once(self):
        self.assertEqual(u.mean(str(x) for x in (1, 2, 3)), 2)
        self.assertEqual(u.std_dev_mean(str(x) for x in (1, 3)), 1)
        self.assertEqual(u.direct_result(str(x) for x in (1, 3))["n"], 2)

    def test_type_b_and_independent_rss(self):
        self.assertEqual(u.type_b("0.003", 3), Decimal("0.001"))
        self.assertEqual(u.combine(3, 4), 5)
        self.assertEqual(u.combine(), 0)
        self.assertEqual(u.combine("0", "0"), 0)

    def test_direct_k2_chain_has_independent_known_variances(self):
        result = u.direct_result([1, 3], delta_inst=3, C=3)
        self.assertEqual((result["xbar"], result["uA"], result["uB"]), (2, 1, 1))
        self.assertEqual(result["sum_sq_dev"], 2)
        self.assertEqual(result["deviations"], [-1, 1])
        self.assertSquared(result["uc"], "2")
        self.assertSquared(result["U"], "8")
        self.assertEqual(result["coverage_factor"], 2)
        self.assertIsNone(result["coverage_probability"])
        self.assertEqual(result["method"], "course_k2")

    def test_legacy_t_rss_formula_is_preserved_and_labelled(self):
        result = u.direct_result([1, 3], delta_inst=3, C=3, algo=2)
        self.assertEqual(result["t"], Decimal("12.706"))
        self.assertEqual(result["df"], 1)
        self.assertSquared(result["U"], "162.442436")
        self.assertEqual(result["method"], "course_t_rss")
        self.assertEqual(result["t_probability"], Decimal("0.95"))
        self.assertIsNone(result["coverage_probability"])
        self.assertIsNone(result["coverage_factor"])

    def test_combined_error_limits_and_estimate_only(self):
        result = u.direct_result([1, 3], delta_inst=3, delta_est=4, C=5)
        self.assertEqual((result["delta"], result["uB"]), (5, 1))
        estimate = u.direct_result([1, 3], delta_est=4, C=2)
        self.assertEqual(estimate["uB"], 2)

    def test_single_measurement_with_type_b_only(self):
        result = u.direct_result(["2.00"], delta_est="0.03", C=3)
        self.assertIsNone(result["Sx"])
        self.assertIsNone(result["uA"])
        self.assertEqual((result["uc"], result["U"]), (Decimal(".01"), Decimal(".02")))
        with self.assertRaises(ValueError):
            u.direct_result([1], delta_inst=1, C=3, algo=2)

    def test_zero_and_negative_means_have_explicit_relative_results(self):
        zero = u.direct_result([-1, 1])
        self.assertIsNone(zero["Ur"])
        negative = u.direct_result([-3, -1])
        positive = u.direct_result([1, 3])
        self.assertEqual(negative["Ur"], positive["Ur"])

    def test_no_implicit_t_table_extrapolation(self):
        with self.assertRaisesRegex(ValueError, "df=21"):
            u.direct_result(range(22), algo=2)
        result = u.direct_result(range(22), algo=2, t_value="2.08")
        self.assertEqual(result["t"], Decimal("2.08"))

    def test_invalid_parameters_and_missing_information(self):
        for arguments in (
            {"algo": True}, {"algo": 1.0}, {"algo": "1"}, {"algo": 0},
            {"delta_inst": 1}, {"delta_inst": -1, "C": 3},
            {"delta_est": -1, "C": 3}, {"delta_inst": 1, "C": 0},
            {"conf": 0}, {"conf": 1}, {"conf": "NaN"},
            {"algo": 2, "conf": ".99"}, {"algo": 2, "t_value": 0},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                u.direct_result([1, 2], **arguments)

    def test_short_samples_and_nonfinite_rejected(self):
        for function in (u.std_dev, u.std_dev_mean):
            for values in ([], [1], [1, "NaN"]):
                with self.subTest(function=function.__name__, values=values):
                    with self.assertRaises(ValueError):
                        function(values)


class InstrumentPresetTests(unittest.TestCase):
    def test_box_detail_sums_to_error_and_modes_are_explicit(self):
        total, detail = u.resistance_box_error("508.5", 6)
        self.assertEqual(total, Decimal(".595"))
        self.assertEqual(sum(row["contrib"] for row in detail), total)
        nonzero, rows = u.resistance_box_error("508.5", 6, "nonzero")
        self.assertEqual(nonzero, Decimal(".580"))
        self.assertEqual(rows[-1]["m_used"], 3)
        self.assertEqual(u.resistance_box_error(0, 6)[0], Decimal(".030"))
        self.assertEqual(u.resistance_box_error(0, 6, "nonzero")[0], 0)

    def test_custom_grade_table_validates_steps(self):
        grades = {"10": ".2", "1": ".5"}
        total, _ = u.resistance_box_error("12", 2, grades=grades)
        self.assertEqual(total, Decimal(".04"))
        for invalid in ({}, {"10": ".2", ".1": "5"}, {".5": "1"},
                        {"1": "-1"}, {"0": "1"}):
            with self.subTest(grades=invalid), self.assertRaises(ValueError):
                u.resistance_box_error("1", 2, grades=invalid)

    def test_invalid_dials_readings_and_mode_rejected(self):
        for count in (True, 0, -1, 2.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                u.resistance_box_error("100", count)
        for reading in ("-1", ".01", "100000", "Infinity"):
            with self.subTest(reading=reading), self.assertRaises(ValueError):
                u.resistance_box_error(reading, 6)
        with self.assertRaises(ValueError):
            u.resistance_box_error("100", 4, "invalid")

    def test_bridge_has_independent_sensitivity_and_rss_checks(self):
        result = u.bridge_row(100, 100, 500, ".1", delta_d=2)
        self.assertEqual((result["C"], result["Rx"], result["S"], result["delta_s"]),
                         (1, 500, 10000, Decimal(".01")))
        self.assertEqual(result["method"], "course_bridge_rss")
        self.assertIsNone(result["coverage_probability"])
        with localcontext() as context:
            context.prec = 60
            expected = result["delta_x"] ** 2 + Decimal(".0001")
            self.assertLess(abs(result["uB"] ** 2 - expected), Decimal("1e-55"))


if __name__ == "__main__":
    unittest.main()
