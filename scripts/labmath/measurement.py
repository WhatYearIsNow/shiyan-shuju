"""Independent standard-uncertainty components and legacy reporting recipes.

The two direct-result algorithms preserve historical classroom formulas. A
requested t-table probability does not guarantee coverage of the final interval.
"""

from __future__ import annotations


from decimal import Decimal
from .numbers import D, _nonnegative, _positive, align_result, round_sig, fmt, calculation


T95 = {
    1: Decimal("12.706"),
    2: Decimal("4.303"),
    3: Decimal("3.182"),
    4: Decimal("2.776"),
    5: Decimal("2.571"),
    6: Decimal("2.447"),
    7: Decimal("2.365"),
    8: Decimal("2.306"),
    9: Decimal("2.262"),
    10: Decimal("2.228"),
    11: Decimal("2.201"),
    12: Decimal("2.179"),
    13: Decimal("2.160"),
    14: Decimal("2.145"),
    15: Decimal("2.131"),
    16: Decimal("2.120"),
    17: Decimal("2.110"),
    18: Decimal("2.101"),
    19: Decimal("2.093"),
    20: Decimal("2.086"),
}


@calculation
def mean(xs):
    xs = [D(x) for x in xs]
    if not xs:
        raise ValueError("测量列不能为空")
    return sum(xs) / len(xs)


@calculation
def std_dev(xs):
    """测量列标准偏差 Sx，贝塞尔公式，分母 n-1。"""
    xs = [D(x) for x in xs]
    n = len(xs)
    if n < 2:
        raise ValueError("标准偏差需要 n≥2")
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (n - 1)).sqrt()


@calculation
def std_dev_mean(xs):
    """平均值的标准偏差 Sx̄ = Sx/√n，即 uA（简单算法）。"""
    xs = [D(x) for x in xs]
    return std_dev(xs) / D(len(xs)).sqrt()


@calculation
def type_b(delta, C):
    """B 类不确定度 uB = Δ/C。C 由分布定（正态3、均匀√3 等）。"""
    return _nonnegative(delta, "误差限 Δ") / _positive(C, "分布因数 C")


@calculation
def combine(*us):
    """无相关输入的合成标准不确定度 uc = √Σuᵢ²；空和为 0。"""
    return sum((_nonnegative(u) ** 2 for u in us), Decimal(0)).sqrt()


@calculation
def direct_result(
    values, delta_inst=None, delta_est=None, C=None, algo: int = 1, t_value=None, conf: str = "0.95"
):
    """
    直接测量全链路。

    values     : 测量列
    delta_inst : 仪器误差限 Δ仪
    delta_est  : 估计误差 Δ估（可选，与 Δ仪 平方合成）
    C          : 分布因数（正态 3、均匀 √3…），uB = Δ/C
    algo       : 1 → U = 2·uc（课件正文口径，默认）
                 2 → U = √((t·Sx̄)² + uB²)（少次测量 t 分布口径）
    t_value    : algo=2 时显式指定 t；缺省按 df=n-1 查 T95

    返回 dict，含全部中间量、三种有效数字表述及方法元数据。
    algo=2 是课程历史公式，不是一般的有效自由度覆盖因子法。
    conf 只用于算法2选择 t 表；coverage_probability=None 表示未保证区间覆盖率。
    """
    xs = [D(v) for v in values]
    n = len(xs)
    if isinstance(algo, bool) or not isinstance(algo, int) or algo not in (1, 2):
        raise ValueError("algo 只能是 1 或 2")
    conf = D(conf)
    if not 0 < conf < 1:
        raise ValueError("置信概率 conf 必须介于 0 与 1 之间")
    if delta_inst is not None:
        delta_inst = _nonnegative(delta_inst, "仪器误差限")
    if delta_est is not None:
        delta_est = _nonnegative(delta_est, "估计误差限")
    if C is not None:
        C = _positive(C, "分布因数 C")
    if t_value is not None:
        t_value = _positive(t_value, "t 值")
    if algo == 2 and t_value is None and conf != Decimal("0.95"):
        raise ValueError("内置 t 表仅支持双侧 95%；其他置信概率须显式给 t_value")
    xbar = mean(xs)
    Sx = std_dev(xs) if n >= 2 else None
    Sxbar = std_dev_mean(xs) if n >= 2 else None

    out = {
        "n": n,
        "xbar": xbar,
        "Sx": Sx,
        "Sxbar": Sxbar,
        "deviations": [x - xbar for x in xs],
        "sum_sq_dev": sum((x - xbar) ** 2 for x in xs),
        "method": "course_k2" if algo == 1 else "course_t_rss",
        "coverage_factor": Decimal(2) if algo == 1 else None,
        "coverage_probability": None,
        "t_probability": conf if algo == 2 else None,
    }

    # Δ 合成
    delta = None
    if delta_inst is not None and delta_est is not None:
        delta = combine(delta_inst, delta_est)
    elif delta_inst is not None:
        delta = D(delta_inst)
    elif delta_est is not None:
        delta = D(delta_est)
    out["delta"] = delta

    uB = None
    if delta is not None:
        if C is None:
            raise ValueError("给了 Δ 就必须给分布因数 C（正态 3、均匀 √3…）")
        uB = type_b(delta, C)
    out["uB"] = uB

    uA = Sxbar
    out["uA"] = uA

    # 合成
    parts = [u for u in (uA, uB) if u is not None]
    if not parts:
        raise ValueError("单次测量无法估计 A 类不确定度；请提供误差限和分布因数 C")
    uc = combine(*parts) if parts else None
    out["uc"] = uc

    # 展伸 / 结果不确定度
    if uc is not None:
        if algo == 1:
            U = D(2) * uc
            out["algo"] = "1: U=2·uc"
        elif algo == 2:
            if Sxbar is None:
                raise ValueError("算法2 需要 n≥2")
            if t_value is None:
                df = n - 1
                if df not in T95:
                    raise ValueError(f"t 表无 df={df}，请显式给 t_value")
                t_value = T95[df]
            out["t"] = D(t_value)
            out["df"] = n - 1
            U = combine(D(t_value) * Sxbar, uB) if uB is not None else D(t_value) * Sxbar
            out["algo"] = f"2: U=√((t·Sx̄)²+uB²), t={fmt(t_value)}"
        else:
            raise ValueError("algo 只能是 1 或 2")
        out["U"] = U
        # 均值为零时相对不确定度未定义；负值的相对不确定度仍为非负。
        out["Ur"] = U / abs(xbar) * D(100) if xbar else None
        out["Ur_from_rounded"] = round_sig(U, 1) / abs(xbar) * D(100) if xbar else None
        out["result_auto"] = align_result(xbar, U, "auto")
        out["result_1sf"] = align_result(xbar, U, 1)
        out["result_2sf"] = align_result(xbar, U, 2)

    return out
