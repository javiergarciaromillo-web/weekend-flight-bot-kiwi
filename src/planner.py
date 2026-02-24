from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Tuple


@dataclass(frozen=True)
class Pattern:
    name: str
    depart_dow: int  # Mon=0..Sun=6
    return_dow: int  # Mon=0..Sun=6


def _next_weekday(d: date, target: int) -> date:
    delta = (target - d.weekday()) % 7
    return d + timedelta(days=delta)


def generate_date_pairs(horizon_weeks: int, patterns: List[Pattern]) -> List[Tuple[str, date, date]]:
    """
    Returns list of (pattern_name, depart_date, return_date) for the next horizon_weeks.
    """
    today = date.today()
    pairs: List[Tuple[str, date, date]] = []

    for w in range(horizon_weeks):
        base = today + timedelta(days=7 * w)
        for p in patterns:
            dep = _next_weekday(base, p.depart_dow)
            ret = _next_weekday(dep, p.return_dow)
            # if return is before depart (e.g., Mon after Fri), next_weekday handles it
            if ret <= dep:
                ret = ret + timedelta(days=7)
            pairs.append((p.name, dep, ret))

    # de-dup just in case (base alignment can overlap)
    uniq = {}
    for pname, dep, ret in pairs:
        uniq[(pname, dep, ret)] = (pname, dep, ret)
    return list(uniq.values())
