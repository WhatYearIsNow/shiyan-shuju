"""Decimal conversion, recorded precision, and isolated 60-digit arithmetic.

Public calculations use their own context. Importing this package never changes
the caller's Decimal context or output streams. Sixty digits are working
precision, not a claim that every numerical derivative is exact.
"""
from __future__ import annotations


from decimal import (
    Context, Decimal, DecimalException, DivisionByZero, InvalidOperation,
    Overflow, ROUND_HALF_EVEN, localcontext,
)
from functools import wraps


WORKING_PRECISION = 60
_MATH_CONTEXT = Context(
    prec=WORKING_PRECISION, rounding=ROUND_HALF_EVEN,
    Emin=-999999, Emax=999999, capitals=1, clamp=0,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)


def calculation(function):
    """Run one calculation without depending on or mutating caller context."""
    @wraps(function)
    def isolated(*args, **kwargs):
        with localcontext(_MATH_CONTEXT):
            return function(*args, **kwargs)
    return isolated


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name}必须为整数")
    return value


def D(x) -> Decimal:
    """转为有限 Decimal；测量数据优先传字符串以保留记录末位。"""
    try:
        d = x if isinstance(x, Decimal) else Decimal(str(x))
    except (DecimalException, TypeError, ValueError) as exc:
        raise ValueError(f"不是有效数值：{x!r}") from exc
    if not d.is_finite():
        raise ValueError(f"数值必须有限：{x!r}")
    return d

def _nonnegative(x, name="不确定度"):
    d = D(x)
    if d < 0:
        raise ValueError(f"{name}不能为负")
    return d

def _positive(x, name):
    d = D(x)
    if d <= 0:
        raise ValueError(f"{name}必须大于 0")
    return d

@calculation
def round_half_even(x, ndigits: int = 0) -> Decimal:
    """4舍6入遇5凑偶，保留 ndigits 位小数。"""
    _integer(ndigits, "小数位数")
    q = Decimal(1).scaleb(-ndigits)
    return D(x).quantize(q, rounding=ROUND_HALF_EVEN)

@calculation
def round_sig(x, n: int = 1) -> Decimal:
    """修约到 n 位有效数字（遇5凑偶）。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("有效数字位数必须为正整数")
    d = D(x)
    if d == 0:
        return Decimal(0)
    exp = d.adjusted()                      # 最高位的十进制指数
    q = Decimal(1).scaleb(exp - n + 1)
    rounded = d.quantize(q, rounding=ROUND_HALF_EVEN)
    # A carry can change the order of magnitude: 9.99 to two figures is
    # Decimal('10'), not Decimal('10.0'). Keep the exponent as part of precision.
    final_q = Decimal(1).scaleb(rounded.adjusted() - n + 1)
    return rounded.quantize(final_q, rounding=ROUND_HALF_EVEN)

@calculation
def align_result(value, u, u_sig="auto"):
    """
    规范表述：不确定度取 u_sig 位有效数字，测量值末位与之对齐。
    u_sig 可为 1、2，或 'auto'（见 pick_u_sig）。
    auto 保留历史报告策略：跨数量级进位时保留进位前末位，
    如 0.955 → 1.0；显式 1/2 位与 round_sig 始终严格按有效数字修约。
    返回 (value_rounded, u_rounded)。
    """
    value, u = D(value), _nonnegative(u)
    n = pick_u_sig(u, u_sig)
    if u == 0:
        # 没有非零不确定度可决定修约末位；保留传入值的末位，不伪造整数精度。
        return value, Decimal(0).quantize(Decimal(1).scaleb(value.as_tuple().exponent))
    u_r = round_sig(u, n)
    if u_sig == "auto" and u_r.adjusted() > u.adjusted():
        previous_q = Decimal(1).scaleb(u.adjusted() - n + 1)
        u_r = u_r.quantize(previous_q, rounding=ROUND_HALF_EVEN)
    exp = u_r.as_tuple().exponent          # u_r 末位所在的十进制位
    q = Decimal(1).scaleb(exp)
    v_r = value.quantize(q, rounding=ROUND_HALF_EVEN)
    return v_r, u_r

def leading_digit(x) -> int:
    """首个有效数字（1–9）。"""
    a = D(x).copy_abs()
    if a == 0:
        return 0
    return a.as_tuple().digits[0]

def pick_u_sig(u, mode="auto") -> int:
    """
    决定不确定度的初始有效数字位数。

    mode = 1      : 严格 1 位
    mode = 2      : 2 位
    mode = 'auto' : 1 位；但首位为 1 或 2 时取 2 位。

    这是保留历史输出的报告策略，不代表所有课程或计量规范的强制要求。
    本次材料另有规定时，显式指定 1 或 2。
    align_result 的 auto 跨数量级进位另保留进位前末位，见其文档。
    """
    _nonnegative(u)
    if mode == "auto":
        return 2 if leading_digit(u) in (1, 2) else 1
    if isinstance(mode, bool) or mode not in (1, 2, "1", "2"):
        raise ValueError("不确定度位数只能为 auto、1 或 2")
    return int(mode)

def dec_places(x) -> int:
    """Decimal 的小数位数（用于加减法有效数字规则）。"""
    e = D(x).as_tuple().exponent
    return max(0, -e)

def sig_figs(x) -> int:
    """
    按输入书写计有效数字，保留小数末尾零；如 1.00 → 3。
    整数末尾零有歧义时传科学计数法（如 '1.00e3'），不要由 float 推断记录精度。
    """
    d = D(x)
    if d == 0:
        return 1
    return len(d.as_tuple().digits)

@calculation
def fmt(x, nd: int | None = None) -> str:
    """十进制显示；nd 给定时固定小数位，否则去掉小数末尾零。"""
    d = D(x)
    if nd is not None:
        _integer(nd, "小数位数")
        d = d.quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_EVEN)
        return format(d, f".{max(0, nd)}f")
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"

def fmt_exact(x) -> str:
    """
    按 Decimal 自身指数输出，**保留末尾零**。
    不确定度与规范表述必须用这个：`1.0` 与 `1` 的含义不同，
    前者表示保留到 0.1 位、测量值可带一位小数。
    """
    return format(D(x), "f")
