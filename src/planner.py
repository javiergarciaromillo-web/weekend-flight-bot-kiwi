from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


@dataclass(frozen=True)
class QueryKey:
    origin: str
    destination: str
    pattern: str  # THU_SUN, THU_MON, FRI_SUN, FRI_MON
    outbound_date: date
    inbound_date: date


def _next_weekday(d: date, weekday: int) -> date:
    """Return next date (including d) with weekday (Mon=0..Sun=6)."""
    delta = (weekday - d.weekday()) % 7
    return d + timedelta(days=delta)


def generate_queries(today: date, weeks: int) -> List[QueryKey]:
    """
    Generate next N weeks of weekend patterns.
    Include current week's Thu/Fri if today is Monday or Tuesday.
    """
    this_thu = _next_weekday(today, 3)  # Thu
    # If today is Wed-Sun, start from next week
    first_thu = this_thu if today.weekday() <= 1 else (this_thu + timedelta(days=7))

    patterns = [
        ("THU_SUN", 0, 3),
        ("THU_MON", 0, 4),
        ("FRI_SUN", 1, 3),
        ("FRI_MON", 1, 4),
    ]

    out: List[QueryKey] = []
    for w in range(weeks):
        week_thu = first_thu + timedelta(days=7 * w)
        for pattern, out_offset, in_offset in patterns:
            outbound = week_thu + timedelta(days=out_offset)
            inbound = week_thu + timedelta(days=in_offset)
            out.append(QueryKey(origin="", destination="", pattern=pattern, outbound_date=outbound, inbound_date=inbound))
    return out
