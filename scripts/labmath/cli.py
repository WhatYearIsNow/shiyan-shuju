"""cli helpers for experimental data processing."""


from __future__ import annotations


import argparse
from .numbers import D, fmt, fmt_exact, align_result, round_sig, calculation
from .measurement import direct_result
from .bridge import bridge_row, resistance_box_error
from .analysis import propagate_power, linear_fit, successive_difference
from .regression import selftest


def _p(x, nd=None):
    return "未定义" if x is None else fmt(x, nd)

def _csv_values(text):
    values = [item.strip() for item in text.split(",")]
    if any(not item for item in values):
        raise ValueError("测量列存在空项；请核对原始数据，不自动删除缺项")
    return values


def _assignments(text, label):
    """Parse assignments without losing duplicate, empty, or malformed data."""
    values = {}
    for item in text.split(","):
        if item.count("=") != 1:
            raise ValueError(f"{label}必须使用逗号分隔的 变量=数值 格式")
        key, raw_value = (part.strip() for part in item.split("="))
        if not key or not raw_value:
            raise ValueError(f"{label}存在空变量或空数值")
        if key in values:
            raise ValueError(f"{label}存在重复变量：{key}")
        values[key] = D(raw_value)
    return values


@calculation
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="大学物理实验数据处理计算内核（agent 自动调用，用户无需手敲）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # direct
    d = sub.add_parser("direct", help="直接测量全链路")
    d.add_argument("--values", required=True, help="逗号分隔测量列，如 14.842,14.861,...")
    d.add_argument("--delta-inst", default=None, help="仪器误差限 Δ仪")
    d.add_argument("--delta-est", default=None, help="估计误差 Δ估")
    d.add_argument("--C", default=None, help="分布因数（正态3、均匀√3）")
    d.add_argument("--algo", type=int, default=1, choices=(1, 2))
    d.add_argument("--t", default=None, help="algo=2 时显式指定 t")
    d.add_argument("--conf", default="0.95", help="算法2查 t 表的双侧置信概率，非95%%须给 --t")

    # bridge
    b = sub.add_parser("bridge", help="惠斯通电桥一行")
    b.add_argument("--R1", required=True)
    b.add_argument("--R2", required=True)
    b.add_argument("--R0", required=True)
    b.add_argument("--dR0", required=True, help="实测 |R0''-R0|")
    b.add_argument("--dd", default="2", help="偏转格数")
    b.add_argument("--mR1", default="4"); b.add_argument("--mR2", default="4")
    b.add_argument("--mR0", default="6")
    b.add_argument("--m-mode", default="total", choices=("total", "nonzero"))
    b.add_argument("--threshold", default="0.2")

    # boxerr
    e = sub.add_parser("boxerr", help="电阻箱示值误差限")
    e.add_argument("--reading", required=True)
    e.add_argument("--m", required=True, help="档位总数")
    e.add_argument("--m-mode", default="total", choices=("total", "nonzero"))

    # prop
    p = sub.add_parser("prop", help="幂律传递 u_w/w=√Σ(kᵢ u_xᵢ/xᵢ)²")
    p.add_argument("--value", required=True, help="w 的最佳估计值")
    p.add_argument("--powers", required=True, help="如 x=2,y=-1")
    p.add_argument("--rel", required=True, help="如 x=0.0012,y=0.0010")

    # fit
    f = sub.add_parser("fit", help="最小二乘")
    f.add_argument("--x", required=True)
    f.add_argument("--y", required=True)

    # diff
    df = sub.add_parser("diff", help="逐差法")
    df.add_argument("--values", required=True)
    df.add_argument("--step", default=None)

    # round
    r = sub.add_parser("round", help="修约与规范表述")
    r.add_argument("--value", required=True)
    r.add_argument("--u", default=None, help="给出不确定度则做末位对齐")
    r.add_argument("--sig", default="auto", choices=("auto", "1", "2"),
                   help="不确定度位数（默认 auto）；无 --u 时 auto 为1位有效数字")

    sub.add_parser("selftest", help="回归自检")

    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        return 0 if selftest() == 0 else 1

    if a.cmd == "direct":
        vals = _csv_values(a.values)
        res = direct_result(vals, delta_inst=a.delta_inst,
                            delta_est=a.delta_est, C=a.C,
                            algo=a.algo, t_value=a.t, conf=a.conf)
        print(f"n={res['n']}  x̄={_p(res['xbar'],6)}")
        print(f"Sx={_p(res['Sx'],6)}  Sx̄={_p(res['Sxbar'],6)}")
        if res.get("delta") is not None:
            print(f"Δ={_p(res['delta'],6)}  uB={_p(res['uB'],6)}")
        print(f"uA={_p(res['uA'],6)}  uc={_p(res['uc'],6)}")
        print(f"算法 {res['algo']}")
        print(f"U={_p(res['U'],6)}  Ur={_p(res['Ur'],4)}%")
        v1, u1 = res["result_1sf"]; v2, u2 = res["result_2sf"]
        va, ua = res["result_auto"]
        print(f"规范表述(auto)：{fmt_exact(va)} ± {fmt_exact(ua)}")
        print(f"规范表述(1位)：{fmt_exact(v1)} ± {fmt_exact(u1)}")
        print(f"规范表述(2位)：{fmt_exact(v2)} ± {fmt_exact(u2)}")
        return 0

    if a.cmd == "bridge":
        res = bridge_row(a.R1, a.R2, a.R0, a.dR0, delta_d=a.dd,
                         m_R1=int(a.mR1), m_R2=int(a.mR2), m_R0=int(a.mR0),
                         m_mode=a.m_mode, threshold=a.threshold)
        print(f"C={_p(res['C'])}  Rx={_p(res['Rx'],4)}")
        print(f"ΔR1={_p(res['dR1'],4)}  ΔR2={_p(res['dR2'],4)}  ΔR0(示值)={_p(res['dR0_box'],4)}")
        print(f"Δx={_p(res['delta_x'],4)}")
        print(f"S={_p(res['S'],2)}  Δs={_p(res['delta_s'],5)}")
        print(f"uB={_p(res['uB'],5)}  Er={_p(res['Er'],4)}%")
        v1, u1 = res["result_auto"]
        print(f"结果(auto)：({fmt_exact(v1)} ± {fmt_exact(u1)}) Ω")
        return 0

    if a.cmd == "boxerr":
        total, detail = resistance_box_error(a.reading, int(a.m), a.m_mode)
        print(f"ΔR = {_p(total,5)} Ω")
        for it in detail:
            if it.get("const_term"):
                print(f"  常数项 0.005×{it['m_used']} = {_p(it['contrib'],5)}  "
                      f"(m_mode={it['m_mode']})")
            else:
                print(f"  ×{it['place']} 档 {it['digit']} → "
                      f"{it['grade_pct']}%×{it['value']} = {_p(it['contrib'],5)}")
        return 0

    if a.cmd == "prop":
        powers = _assignments(a.powers, "powers")
        rel = _assignments(a.rel, "rel")
        res = propagate_power(powers, rel, a.value)
        print(f"u_w/w = {_p(res['rel_u'],6)} = {_p(res['rel_u']*100,4)}%")
        print(f"u_w = {_p(res['u'],6)}")
        return 0

    if a.cmd == "fit":
        xs = _csv_values(a.x)
        ys = _csv_values(a.y)
        res = linear_fit(xs, ys)
        print(f"n={res['n']}  b={_p(res['b'],6)}  a={_p(res['a'],6)}")
        print(f"γ={_p(res['gamma'],8)}")
        print(f"u_b={_p(res['u_b'],6)}  u_a={_p(res['u_a'],6)}  σ_y={_p(res['sigma_y'],6)}")
        return 0

    if a.cmd == "diff":
        vals = _csv_values(a.values)
        res = successive_difference(vals, a.step)
        print(f"n={res['n']}  m={res['m']}  分母={_p(res['denominator'])}")
        print("差值：" + "  ".join(_p(x,4) for x in res["diffs"]))
        print(f"Σ差值={_p(res['sum_diffs'],4)}")
        print(f"平均每步增量={_p(res['avg_step'],6)}")
        if "slope" in res:
            print(f"斜率={_p(res['slope'],6)}")
        return 0

    if a.cmd == "round":
        if a.u is None:
            n = 1 if a.sig == "auto" else int(a.sig)
            print(f"修约到 {n} 位有效数字：{fmt_exact(round_sig(a.value, n))}")
        else:
            v, u = align_result(a.value, a.u, a.sig)
            print(f"{fmt_exact(v)} ± {fmt_exact(u)}")
        return 0

    return 0
