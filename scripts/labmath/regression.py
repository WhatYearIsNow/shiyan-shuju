"""regression helpers for experimental data processing."""

from __future__ import annotations


from .numbers import (
    D,
    fmt,
    fmt_exact,
    align_result,
    round_half_even,
    round_sig,
    pick_u_sig,
    calculation,
)
from .measurement import direct_result
from .bridge import bridge_row


BRIDGE_BASELINE = [
    (
        "行1 3.0V 1000:1000",
        "1000",
        "1000",
        "508.4",
        "0.1",
        2,
        "508.4",
        "10168",
        "0.01",
        "508.4±0.9",
        "0.19",
    ),
    (
        "行2 1.5V 1000:1000",
        "1000",
        "1000",
        "508.4",
        "0.1",
        2,
        "508.4",
        "10168",
        "0.01",
        "508.4±0.9",
        "0.19",
    ),
    (
        "行3 1.5V 100:100",
        "100",
        "100",
        "508.5",
        "0.1",
        2,
        "508.5",
        "10170",
        "0.01",
        "508.5±1.0",
        "0.21",
    ),
    (
        "行4 1.5V 100:1000",
        "100",
        "1000",
        "5078.1",
        "2.6",
        2,
        "507.8",
        "3906",
        "0.026",
        "507.8±1.0",
        "0.19",
    ),
    (
        "行5 1.5V 10:1000",
        "10",
        "1000",
        "50150.2",
        "160.0",
        2,
        "501.5",
        "627",
        "0.16",
        "501.5±2.1",
        "0.43",
    ),
]

MICRO_VALUES = ["14.842", "14.861", "14.852", "14.877", "14.854"]


def _selftest_bridge(verbose: bool = True) -> int:
    fails = 0
    if verbose:
        print("=" * 74)
        print("基准一：脱敏历史基准：电桥")
        print("=" * 74)
    for label, R1, R2, R0, dR0, dd, eRx, eS, eds, epm, eEr in BRIDGE_BASELINE:
        r = bridge_row(R1, R2, R0, dR0, delta_d=dd, m_R1=4, m_R2=4, m_R0=6, m_mode="total")
        v, u = align_result(r["Rx"], r["uB"], "auto")
        got_pm = f"{fmt_exact(v)}±{fmt_exact(u)}"
        checks = [
            ("Rx", fmt(round_half_even(r["Rx"], 1)), eRx),
            ("S", fmt(round_half_even(r["S"], 0)), eS),
            ("Δs", fmt(round_sig(r["delta_s"], 2)), eds),
            ("uB", fmt_exact(u), epm.split("±")[1]),
            ("表述", got_pm, epm),
            ("Er", fmt(round_sig(r["Er"], 2)), eEr),
        ]
        bad = [f"{n}: 得 {g} / 期望 {w}" for n, g, w in checks if g != w]
        if bad:
            fails += 1
        if verbose:
            print(f"\n[{'PASS' if not bad else 'DIFF'}] {label}")
            print(
                f"   Δx={fmt(r['delta_x'], 4)}  S={fmt(r['S'], 2)}  "
                f"Δs={fmt(r['delta_s'], 5)}  uB={fmt(r['uB'], 5)}  Er={fmt(r['Er'], 4)}%"
            )
            print(f"   规范表述 {got_pm}")
            for b in bad:
                print(f"   ⚠ {b}")
    return fails


def _selftest_micro(verbose: bool = True) -> int:
    fails = 0
    if verbose:
        print("\n" + "=" * 74)
        print("基准二：脱敏历史基准：直接测量")
        print("=" * 74)
    res = direct_result(MICRO_VALUES, delta_inst="0.004", C="3", algo=1)
    v, u = align_result(res["xbar"], res["U"], "auto")

    num_checks = [
        ("x̄", res["xbar"], "14.8572"),
        ("Sx", res["Sx"], "0.01299"),
        ("Sx̄", res["Sxbar"], "0.005809"),
        ("uB", res["uB"], "0.001333"),
        ("uc", res["uc"], "0.005960"),
        ("U", res["U"], "0.011919"),
        ("Ur%", res["Ur"], "0.0802"),
    ]
    bad = []
    for name, got, want in num_checks:
        w = D(want)
        if w == 0:
            ok = abs(got) < D("1e-9")
        else:
            ok = abs(got - w) <= abs(w) * D("2e-3")
        if not ok:
            bad.append(f"{name}: 得 {fmt(got, 6)} / 期望 {want}")

    got_pm = f"{fmt_exact(v)}±{fmt_exact(u)}"
    if got_pm != "14.857±0.012":
        bad.append(f"表述: 得 {got_pm} / 期望 14.857±0.012")

    if bad:
        fails += 1
    if verbose:
        print(f"   x̄={fmt(res['xbar'], 6)}  Sx={fmt(res['Sx'], 6)}  Sx̄={fmt(res['Sxbar'], 6)}")
        print(f"   uA={fmt(res['uA'], 6)}  uB={fmt(res['uB'], 6)}  uc={fmt(res['uc'], 6)}")
        print(f"   U={fmt(res['U'], 6)}  Ur={fmt(res['Ur'], 4)}%")
        print(f"   [{'PASS' if not bad else 'DIFF'}] 规范表述 {got_pm}")
        for b in bad:
            print(f"   ⚠ {b}")
    return fails


@calculation
def selftest(verbose: bool = True) -> int:
    """两套基准回归；返回失败组数。"""
    fails = _selftest_bridge(verbose) + _selftest_micro(verbose)
    if verbose:
        print("\n" + "-" * 74)
        print(f"结果：{'全部通过' if fails == 0 else str(fails) + ' 组存在差异'}")
    return fails
