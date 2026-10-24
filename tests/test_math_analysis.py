"""Analytic oracles, transformation invariants, and numerical failure cases."""
from pathlib import Path
import sys
import unittest
from decimal import Decimal, localcontext

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uncertainty as u


class PropagationTests(unittest.TestCase):
    def test_power_law_independent_known_components(self):
        result = u.propagate_power({"x": 2, "y": -1}, {"x": ".03", "y": ".08"}, -12)
        self.assertEqual(result["rel_u"], Decimal(".10"))
        self.assertEqual(result["u"], Decimal("1.20"))

    def test_fractional_and_zero_exponents(self):
        result = u.propagate_power({"x": ".5", "y": 0}, {"x": ".2", "y": 100}, 4)
        self.assertEqual(result["rel_u"], Decimal(".1"))
        self.assertEqual(result["u"], Decimal(".4"))

    def test_power_variable_sets_cannot_silently_drop_input(self):
        for powers, relative in (({"x": 1}, {}),
                                 ({"x": 1}, {"x": ".1", "z": ".2"})):
            with self.subTest(powers=powers, relative=relative), self.assertRaises(ValueError):
                u.propagate_power(powers, relative, 2)
        self.assertEqual(u.propagate_power({}, {}, 2)["u"], 0)

    def test_exact_linear_numeric_derivative(self):
        result = u.propagate_numeric(lambda x, y: x + 2 * y,
                                    {"x": (1, ".3"), "y": (2, ".2")})
        self.assertEqual(result["value"], 5)
        self.assertEqual(result["u"], Decimal(".5"))
        self.assertEqual([item["partial"] for item in result["detail"]], [1, 2])

    def test_product_numeric_derivative_against_analytic_result(self):
        result = u.propagate_numeric(lambda x, y: x * y,
                                    {"x": (2, ".1"), "y": (3, ".2")})
        self.assertEqual((result["value"], result["u"]), (6, Decimal(".5")))
        analytic = u.propagate_power({"x": 1, "y": 1}, {"x": ".05", "y": "0.0666666666666666666666666666666666666666666666666666666666667"}, 6)
        with localcontext() as context:
            context.prec = 60
            self.assertLess(abs(result["u"] - analytic["u"]), Decimal("1e-57"))

    def test_nonlinear_reciprocal_has_bounded_finite_difference_error(self):
        result = u.propagate_numeric(lambda x: 1 / x, {"x": (2, ".1")})
        with localcontext() as context:
            context.prec = 60
            self.assertLess(abs(result["u"] - Decimal(".025")), Decimal("1e-14"))

    def test_unrepresentable_step_raises_instead_of_fabricating_zero(self):
        for value in ("1", "-1", "1e40"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "不可分辨"):
                u.propagate_numeric(lambda x: x, {"x": (value, ".1")}, "1e-100")

    def test_zero_uncertainty_at_boundary_is_not_perturbed(self):
        calls = []

        def root(x):
            calls.append(x)
            return x.sqrt()

        result = u.propagate_numeric(root, {"x": ("0", "0")})
        self.assertEqual(calls, [0])
        self.assertEqual((result["value"], result["u"]), (0, 0))
        self.assertIsNone(result["detail"][0]["partial"])
        self.assertEqual(result["detail"][0]["term"], 0)

    def test_uncertain_domain_boundary_fails_with_variable_context(self):
        with self.assertRaisesRegex(ValueError, "x 的中心差分"):
            u.propagate_numeric(lambda x: x.sqrt(), {"x": ("0", ".1")})

    def test_invalid_numeric_uncertainty_and_step(self):
        for step in (0, -1, "NaN", "Infinity"):
            with self.subTest(step=step), self.assertRaises(ValueError):
                u.propagate_numeric(lambda x: x, {"x": (1, ".1")}, step)
        with self.assertRaises(ValueError):
            u.propagate_numeric(lambda x: x, {"x": (1, "-.1")})


class FittingTests(unittest.TestCase):
    def test_parameter_covariance_matches_rational_oracle(self):
        result = u.linear_fit([0, 1, 2, 3], [1, 2, 2, 4])
        self.assertEqual(result["cov_ab"], Decimal("-.105"))
        with localcontext() as context:
            context.prec = 60
            # q=-a/b: (49/200 + 7/100 + 21/100)/(81/100) = 35/54.
            a, b = result["a"], result["b"]
            variance = (result["u_a"] / b) ** 2 + (a * result["u_b"] / b ** 2) ** 2 - 2 * a * result["cov_ab"] / b ** 3
            self.assertLess(abs(variance - Decimal(35) / 54), Decimal("1e-57"))

    def test_covariance_transforms_under_coordinate_changes(self):
        base = u.linear_fit([0, 1, 2, 3], [1, 2, 2, 4])
        shifted = u.linear_fit([10, 11, 12, 13], [8, 9, 9, 11])
        scaled = u.linear_fit([0, 2, 4, 6], [-3, -6, -6, -12])
        self.assertEqual(shifted["cov_ab"], Decimal("-.805"))
        self.assertEqual(scaled["cov_ab"], base["cov_ab"] * Decimal("4.5"))
        self.assertEqual(u.linear_fit([0, 1, 2], [5, 3, 1])["cov_ab"], 0)

    def test_noisy_fit_against_exact_rational_oracle(self):
        result = u.linear_fit([0, 1, 2, 3], [1, 2, 2, 4])
        self.assertEqual((result["a"], result["b"], result["sse"]),
                         (Decimal(".9"), Decimal(".9"), Decimal(".7")))
        self.assertEqual(result["residuals"],
                         [Decimal(".1"), Decimal(".2"), Decimal("-.7"), Decimal(".4")])
        with localcontext() as context:
            context.prec = 60
            self.assertLess(abs(result["u_b"] ** 2 - Decimal(".07")), Decimal("1e-57"))
            self.assertLess(abs(result["u_a"] ** 2 - Decimal(".245")), Decimal("1e-57"))
            self.assertLess(abs(result["gamma"] ** 2 * 95 - 81), Decimal("1e-55"))

    def test_paired_permutation_preserves_fit(self):
        expected = u.linear_fit([0, 1, 2, 3], [1, 2, 2, 4])
        actual = u.linear_fit([2, 0, 3, 1], [2, 1, 4, 2])
        for field in ("a", "b", "gamma", "sse", "u_a", "u_b"):
            self.assertEqual(actual[field], expected[field])

    def test_translation_and_rescaling_transform_parameters(self):
        base = u.linear_fit([0, 1, 2, 3], [1, 2, 2, 4])
        shifted = u.linear_fit([10, 11, 12, 13], [8, 9, 9, 11])
        self.assertEqual((shifted["a"], shifted["b"], shifted["sse"]),
                         (Decimal("-1.1"), base["b"], base["sse"]))
        scaled = u.linear_fit([0, 2, 4, 6], [-3, -6, -6, -12])
        self.assertEqual((scaled["a"], scaled["b"]),
                         (Decimal("-2.7"), Decimal("-1.35")))
        with localcontext() as context:
            context.prec = 60
            self.assertLess(abs(scaled["u_b"] - base["u_b"] * Decimal("1.5")),
                            Decimal("1e-57"))
            self.assertEqual(scaled["sse"], base["sse"] * 9)

    def test_exact_constant_and_negative_lines(self):
        constant = u.linear_fit([0, 1, 2], [2, 2, 2])
        self.assertIsNone(constant["gamma"])
        self.assertEqual((constant["a"], constant["b"], constant["u_a"]), (2, 0, 0))
        descending = u.linear_fit([0, 1, 2], [5, 3, 1])
        self.assertEqual((descending["a"], descending["b"], descending["gamma"]), (5, -2, -1))

    def test_invalid_lengths_degeneracy_and_nonfinite(self):
        for xs, ys in (([], []), ([0, 1], [0, 1]), ([0, 1, 2], [0, 1]),
                       ([1, 1, 1], [1, 2, 3]), ([0, 1, 2], [0, 1, "NaN"])):
            with self.subTest(xs=xs, ys=ys), self.assertRaises(ValueError):
                u.linear_fit(xs, ys)

    def test_large_offset_with_exact_recorded_inputs(self):
        result = u.linear_fit([str(10 ** 40 + i) for i in range(4)], [1, 3, 5, 7])
        self.assertEqual(result["b"], 2)
        self.assertEqual(result["sse"], 0)


class DifferenceTests(unittest.TestCase):
    def test_noisy_odd_data_is_not_silently_truncated_or_mutated(self):
        # SYNTHETIC: unequal perturbations make two silent truncations disagree.
        values = ['10.00', '14.46', '18.88', '23.39', '27.77',
                  '32.30', '36.65', '41.19', '45.55']
        saved = values.copy()
        with self.assertRaises(ValueError):
            u.successive_difference(values)
        self.assertEqual(values, saved)
        front = u.successive_difference(values[:8])['avg_step']
        back = u.successive_difference(values[1:])['avg_step']
        self.assertNotEqual(front, back)

    def test_even_series_with_known_slope(self):
        for count in (2, 4, 6, 10):
            with self.subTest(count=count):
                result = u.successive_difference([7 + 3 * i for i in range(count)], ".5")
                self.assertEqual(result["avg_step"], 3)
                self.assertEqual(result["slope"], 6)

    def test_translated_and_descending_series(self):
        increasing = u.successive_difference([0, 2, 4, 6])
        translated = u.successive_difference([100, 102, 104, 106])
        self.assertEqual(increasing["avg_step"], translated["avg_step"])
        self.assertEqual(u.successive_difference([6, 4, 2, 0], "-.5")["slope"], 4)

    def test_invalid_count_and_step(self):
        for values, step in (([], None), ([1], None), ([1, 2, 3], None),
                             ([1, 2], 0), ([1, 2], "NaN")):
            with self.subTest(values=values, step=step), self.assertRaises(ValueError):
                u.successive_difference(values, step)


if __name__ == "__main__":
    unittest.main()
