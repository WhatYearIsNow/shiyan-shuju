"""Decimal experimental math with isolated contexts and no import-time I/O."""
from .numbers import D, WORKING_PRECISION, round_half_even, round_sig, align_result, leading_digit, pick_u_sig, dec_places, sig_figs, fmt, fmt_exact
from .measurement import T95, mean, std_dev, std_dev_mean, type_b, combine, direct_result
from .bridge import BOX_GRADES, resistance_box_error, bridge_row
from .analysis import propagate_power, propagate_numeric, linear_fit, successive_difference, add_sub, mul_div
from .regression import BRIDGE_BASELINE, MICRO_VALUES, selftest


__all__ = [
    "D", "WORKING_PRECISION", "round_half_even", "round_sig", "align_result",
    "leading_digit", "pick_u_sig", "dec_places", "sig_figs", "fmt", "fmt_exact",
    "T95", "mean", "std_dev", "std_dev_mean", "type_b", "combine", "direct_result",
    "BOX_GRADES", "resistance_box_error", "bridge_row", "propagate_power",
    "propagate_numeric", "linear_fit", "successive_difference", "add_sub", "mul_div",
    "BRIDGE_BASELINE", "MICRO_VALUES", "selftest",
]
