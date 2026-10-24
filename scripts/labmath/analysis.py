"""First-order independent propagation, unweighted fitting, and arithmetic."""


from __future__ import annotations


from decimal import Decimal
from .numbers import D, _nonnegative, _positive, fmt, sig_figs, round_half_even, round_sig, calculation
from .measurement import mean


@calculation
def propagate_power(powers: dict, rel_unc: dict, value):
    """
    幂律 w = x^k · y^m / z^n 的相对不确定度合成：
        u_w/w = √( Σ (kᵢ·u_xᵢ/xᵢ)² )

    powers   : {'x': 2, 'y': -1}         指数（可为负、可为分数）
    rel_unc  : {'x': Decimal(..), 'y': ..}  各量相对不确定度（无量纲）
    value    : w 的最佳估计值（用于给出绝对不确定度 u_w）
    仅适用于一阶近似、无相关输入；两份映射的变量必须一致。
    """
    missing = powers.keys() - rel_unc.keys()
    extra = rel_unc.keys() - powers.keys()
    if missing:
        raise ValueError(f"缺少 {', '.join(sorted(missing))} 的相对不确定度")
    if extra:
        raise ValueError(f"存在未使用的相对不确定度：{', '.join(sorted(extra))}")
    var = Decimal(0)
    detail = []
    for k, p in powers.items():
        if k not in rel_unc:
            raise ValueError(f"缺少 {k} 的相对不确定度")
        r = _nonnegative(rel_unc[k], f"{k} 的相对不确定度")
        term = (D(p) * r) ** 2
        var += term
        detail.append({"var": k, "power": fmt(p),
                       "rel_u": r, "term": term})
    rel = var.sqrt()
    return {
        "rel_u": rel,
        "u": abs(D(value)) * rel,
        "detail": detail,
    }

@calculation
def propagate_numeric(f, variables: dict, rel_step=Decimal("1e-7")):
    """
    通用数值传递（中心差分求偏导）：
        u_w = √( Σ (∂w/∂xᵢ · u_xᵢ)² )

    f         : 可调用，接受关键字参数，返回 Decimal
    variables : {'x': (标称值, 不确定度), ...}
    假设输入无相关项且一阶近似适用；有限差分不是解析求导。
    中心差分需两侧均在定义域内；步长不可分辨时明确报错。
    不确定度为零的确定量不扰动，partial=None、term=0。
    """
    rel_step = _positive(rel_step, "数值偏导步长系数")
    variables = {k: (D(v), _nonnegative(u, f"{k} 的不确定度"))
                 for k, (v, u) in variables.items()}
    base = D(f(**{k: v[0] for k, v in variables.items()}))
    var = Decimal(0)
    detail = []
    for k, (v, u) in variables.items():
        v, u = D(v), D(u)
        if u == 0:
            detail.append({"var": k, "partial": None, "u": u,
                           "term": Decimal(0), "reason": "zero_uncertainty"})
            continue
        h = abs(v) * rel_step if v != 0 else rel_step
        hi = {kk: D(vv[0]) for kk, vv in variables.items()}
        lo = dict(hi)
        hi[k] = v + h
        lo[k] = v - h
        if hi[k] == v or lo[k] == v or hi[k] == lo[k]:
            raise ValueError(f"{k} 的数值偏导步长在工作精度下不可分辨；请增大 rel_step")
        try:
            f_hi, f_lo = D(f(**hi)), D(f(**lo))
        except (ArithmeticError, ValueError) as exc:
            raise ValueError(f"{k} 的中心差分无法求值；请核对定义域和步长：{exc}") from exc
        # Use the actual representable span instead of assuming symmetric
        # rounding at the last working digit.
        df = (f_hi - f_lo) / (hi[k] - lo[k])
        term = (df * u) ** 2
        var += term
        detail.append({"var": k, "partial": df, "u": u, "term": term})
    return {"value": base, "u": var.sqrt(), "detail": detail}

@calculation
def linear_fit(xs, ys):
    """
    最小二乘 y = a + b·x。
    返回 b（斜率）、a（截距）、γ（相关系数）、u_b、u_a、cov_ab、残差平方和。

    u_a/u_b 采用最小二乘参数标准不确定度（σ_y 乘相应因子）；
    若课程课件另有指定公式，请以课件为准——本函数只给标准数学结果。
    假设纵坐标残差独立且等方差、横坐标误差可忽略；非加权拟合。
    """
    xs = [D(x) for x in xs]
    ys = [D(y) for y in ys]
    n = len(xs)
    if n != len(ys):
        raise ValueError("x、y 数据个数必须相同，不能丢弃未配对数据")
    if n < 3:
        raise ValueError("含参数不确定度的最小二乘需要 n≥3")
    # 先中心化，避免大偏置下 nΣx²-(Σx)² 的抵消损失。
    xm, ym = mean(xs), mean(ys)
    dx, dy = [x - xm for x in xs], [y - ym for y in ys]
    sxx = sum(x * x for x in dx)
    syy = sum(y * y for y in dy)
    sxy = sum(x * y for x, y in zip(dx, dy))
    if sxx == 0:
        raise ValueError("x 全相等，无法拟合")
    b = sxy / sxx
    a = ym - b * xm
    r_den = (sxx * syy).sqrt()
    r = sxy / r_den if r_den != 0 else None

    residuals = [y - b * x for x, y in zip(dx, dy)]
    sse = sum(e * e for e in residuals)
    sigma_y = (sse / D(n - 2)).sqrt() if n > 2 else None

    u_b = u_a = None
    if sigma_y is not None:
        u_b = sigma_y / sxx.sqrt()
        u_a = sigma_y * (D(1) / D(n) + xm * xm / sxx).sqrt()
    # Intercept and slope share observations; retain their covariance for
    # downstream functions such as the zero crossing -a/b.
    cov_ab = -xm * (sse / D(n - 2)) / sxx

    return {
        "n": n, "a": a, "b": b, "gamma": r,
        "sse": sse, "sigma_y": sigma_y,
        "u_a": u_a, "u_b": u_b, "cov_ab": cov_ab,
        "residuals": residuals,
    }

@calculation
def successive_difference(vals, step=None):
    """
    逐差法。数据分成前后两半，对应项相减，再除以总步数。

    平均每步增量 = Σ(v_{i+m} − v_i) / (m·m)，  m = n/2

    step 可指定真实的自变量间隔（如砝码质量 m），用于把结果换算成物理斜率。
    """
    vs = [D(v) for v in vals]
    n = len(vs)
    if n < 2 or n % 2 != 0:
        raise ValueError("逐差法要求至少 2 个数据且个数为偶数")
    m = n // 2
    diffs = [vs[i + m] - vs[i] for i in range(m)]
    total = sum(diffs)
    avg = total / (D(m) * D(m))
    out = {
        "n": n, "m": m, "diffs": diffs,
        "sum_diffs": total, "avg_step": avg,
        "denominator": D(m) * D(m),
    }
    if step is not None:
        step = D(step)
        if step == 0:
            raise ValueError("自变量间隔 step 不能为 0")
        out["slope"] = avg / step
    return out

@calculation
def add_sub(vals):
    """带符号求和，末位对齐最粗输入精度；返回的位数可为负。

    例如 '1.2e3' 的末位是百位，返回 nd=-2，不能按整数个位处理。
    """
    vs = [D(v) for v in vals]
    if not vs:
        raise ValueError("运算数不能为空")
    nd = -max(v.as_tuple().exponent for v in vs)
    s = sum(vs)
    return round_half_even(s, nd), nd

@calculation
def mul_div(vals):
    """历史兼容名称：将给定因子相乘，并按最少有效数字修约。

    此接口没有隐含的分母或除法解析；vals 中每一项都是乘数。
    """
    vs = [D(v) for v in vals]
    if not vs:
        raise ValueError("运算数不能为空")
    n = min(sig_figs(v) for v in vs)
    p = Decimal(1)
    for v in vs:
        p *= v
    return round_sig(p, n), n
