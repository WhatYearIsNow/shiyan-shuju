"""Synthetic repeated-length example; never use as real laboratory data."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uncertainty as calc

# SYNTHETIC: three lengths in mm, invented solely to demonstrate the interface.
values = ["10.01", "10.02", "10.03"]
result = calc.direct_result(values, delta_inst="0.03", C="3", algo=1)
value, uncertainty = calc.align_result(result["xbar"], result["U"], "auto")
print(
    json.dumps(
        {
            "data_kind": "synthetic",
            "unit": "mm",
            "inputs": values,
            "formula": "uA=s/sqrt(n); uB=delta/C; U=2*sqrt(uA^2+uB^2)",
            "coverage_factor": "2 (no unconditional confidence claim)",
            "value": calc.fmt_exact(value),
            "uncertainty": calc.fmt_exact(uncertainty),
        },
        ensure_ascii=True,
        indent=2,
    )
)
