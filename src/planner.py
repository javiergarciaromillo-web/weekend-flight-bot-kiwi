from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Tuple


@dataclass(frozen=True)
class QueryKey:
    week_start: date        # Thursday
    pattern: str            # THU_SUN, THU_MON, FRI_SUN, FRI_MON
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
    this_thu = _next_weekday(today, 3)  # Thu=3
    first_thu = this_thu if today.weekday() <= 1 else (this_thu + timedelta(days=7))

    patterns: List[Tuple[str, int, int]] = [
        ("THU_SUN", 0, 3),
        ("THU_MON", 0, 4),
        ("FRI_SUN", 1, 3),
        ("FRI_MON", 1, 4),
    ]

    out: List[QueryKey] = []
    for w in range(weeks):
        week_thu = first_thu + timedelta(days=7 * w)
        for pattern, out_offset, in_offset in patterns:
            out.append(
                QueryKey(
                    week_start=week_thu,
                    pattern=pattern,
                    outbound_date=week_thu + timedelta(days=out_offset),
                    inbound_date=week_thu + timedelta(days=in_offset),
                )
            )
    return out
