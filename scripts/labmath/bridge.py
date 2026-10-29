"""Historical instrument and classroom bridge formulas, explicitly scoped.

The default dial grades, additive term, and bridge RSS of error limits are a
course preset. Verify the instrument and source before using this preset; the
reported uB must not be reinterpreted as a universal standard-uncertainty model.
"""

from __future__ import annotations


from decimal import Decimal
from .numbers import D, _nonnegative, _positive, fmt, align_result, calculation
from .measurement import combine


BOX_GRADES = {
    Decimal("10000"): Decimal("0.1"),
    Decimal("1000"): Decimal("0.1"),
    Decimal("100"): Decimal("0.1"),
    Decimal("10"): Decimal("0.2"),
    Decimal("1"): Decimal("0.5"),
    Decimal("0.1"): Decimal("5"),
}


def _digit_at(reading: Decimal, place: Decimal) -> int:
    """取读数在指定位上的数字（0-9）。"""
    q = (reading / place).to_integral_value(rounding="ROUND_FLOOR")
    return int(q % 10)


@calculation
def resistance_box_error(reading, m: int, m_mode: str = "total", grades: dict | None = None):
    """
    电阻箱示值误差限 ΔR = Σ aᵢ%·Rᵢ + 0.005m

    reading : 电阻箱读数（Ω）
    m       : 档位总数（四档小箱 4、六档大箱 6）
    m_mode  : 'total'   → 常数项用 m（档位总数，课件/板书口径）
              'nonzero' → 常数项只用非零档位数（部分往届口径）
    grades  : 可覆盖等级表（如仪器铭牌不同时）

    返回 (ΔR, 明细列表)。明细便于把拆位过程写进计算说明。
    """
    if isinstance(m, bool) or not isinstance(m, int) or m < 1:
        raise ValueError("档位总数 m 必须为正整数")
    if m_mode not in ("total", "nonzero"):
        raise ValueError("m_mode 只能为 total 或 nonzero")
    source = BOX_GRADES if grades is None else grades
    if not source:
        raise ValueError("等级表不能为空")
    g = {
        _positive(place, "档位权值"): _nonnegative(pct, "准确度等级")
        for place, pct in source.items()
    }
    places = sorted(g, reverse=True)
    if any(p.scaleb(-p.adjusted()) != 1 for p in places):
        raise ValueError("档位权值必须为十进制位权（如 100、10、1、0.1）")
    if any(a != b * 10 for a, b in zip(places, places[1:])):
        raise ValueError("等级表必须覆盖连续十进制档位")
    rd = _nonnegative(reading, "电阻箱读数")
    if rd >= max(g) * 10 or rd % min(g) != 0:
        raise ValueError("电阻箱读数超出等级表范围或小于其最小步进，不能静默截位")
    total = Decimal(0)
    detail = []
    nonzero = 0
    for place in sorted(g.keys(), reverse=True):
        pct = D(g[place])
        digit = _digit_at(rd, place)
        if digit:
            contrib = pct / D(100) * (Decimal(digit) * place)
            total += contrib
            nonzero += 1
            detail.append(
                {
                    "place": fmt(place),
                    "digit": digit,
                    "grade_pct": fmt(pct),
                    "value": fmt(Decimal(digit) * place),
                    "contrib": contrib,
                }
            )
    m_used = m if m_mode == "total" else nonzero
    const = Decimal("0.005") * m_used
    total += const
    detail.append({"const_term": True, "m_mode": m_mode, "m_used": m_used, "contrib": const})
    return total, detail


@calculation
def bridge_row(
    R1,
    R2,
    R0,
    delta_R0_measured,
    delta_d=2,
    m_R1=4,
    m_R2=4,
    m_R0=6,
    m_mode="total",
    threshold=Decimal("0.2"),
):
    """
    惠斯通电桥一行。

    R1, R2      : 比例臂读数
    R0          : 比较臂读数（平衡时）
    delta_R0_measured : |R0'' − R0|，即偏转 Δd 格后比较臂改变量（**实测值**）
    delta_d     : 偏转格数（老师约定，全表常为 2）
    m_R1/m_R2/m_R0 : 各电阻箱档位总数
    threshold   : 人眼可辨阈（格），常用于 0.2

    注意区分两个 ΔR0：
      · 灵敏阈用**实测**的 delta_R0_measured
      · 示值误差用**电阻箱误差限** resistance_box_error(R0)
    这两者物理意义不同，混用是最常见的错。

    返回 dict，含 Decimal 结果、修约元组与课程方法标签。
    此处保持课程误差限合成公式，不对输入误差限擅自增加分布换算。
    """
    r1, r2, r0 = (_positive(R1, "R1"), _positive(R2, "R2"), _positive(R0, "R0"))
    delta_R0_measured = _positive(delta_R0_measured, "实测比较臂改变量")
    delta_d = _positive(delta_d, "偏转格数")
    threshold = _nonnegative(threshold, "可辨阈值")
    dR1, _ = resistance_box_error(r1, m_R1, m_mode)
    dR2, _ = resistance_box_error(r2, m_R2, m_mode)
    dR0_box, _ = resistance_box_error(r0, m_R0, m_mode)

    C = r1 / r2
    Rx = C * r0

    # 示值误差限 Δx：相对式传递
    rel = combine(dR1 / r1, dR2 / r2, dR0_box / r0)
    delta_x = Rx * rel

    # 灵敏度 S = (Δd/ΔR0)·R0
    S = (D(delta_d) / D(delta_R0_measured)) * r0

    # 灵敏阈误差 Δs = C·(阈值/Δd)·ΔR0
    delta_s = C * (D(threshold) / D(delta_d)) * D(delta_R0_measured)

    uB = combine(delta_x, delta_s)
    Er = uB / Rx * D(100)

    return {
        "C": C,
        "Rx": Rx,
        "dR1": dR1,
        "dR2": dR2,
        "dR0_box": dR0_box,
        "rel": rel,
        "delta_x": delta_x,
        "S": S,
        "delta_s": delta_s,
        "uB": uB,
        "Er": Er,
        "method": "course_bridge_rss",
        "coverage_probability": None,
        "result_auto": align_result(Rx, uB, "auto"),
        "result_1sf": align_result(Rx, uB, 1),
        "result_2sf": align_result(Rx, uB, 2),
    }
