from __future__ import annotations

from decimal import Decimal, getcontext

getcontext().prec = 12


def american_to_implied_probability(odds: int) -> Decimal:
    """
    Convert American odds to implied probability.
    """
    if odds is None:
        return Decimal("0")

    odds_decimal = Decimal(odds)

    if odds_decimal > 0:
        return Decimal(100) / (odds_decimal + Decimal(100))
    return -odds_decimal / (-odds_decimal + Decimal(100))

