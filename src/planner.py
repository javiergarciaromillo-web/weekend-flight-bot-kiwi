from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


@dataclass(frozen=True)
class WeekendWindow:
    week_start: date
    thu: date
    fri: date
    sun: date
    mon: date  # next Monday


def generate_weekend_windows(today: date, weeks: int) -> List[WeekendWindow]:
    base_monday = today - timedelta(days=today.weekday())
    out: List[WeekendWindow] = []

    for w in range(weeks):
        wk_monday = base_monday + timedelta(days=7 * w)
        out.append(
            WeekendWindow(
                week_start=wk_monday,
                thu=wk_monday + timedelta(days=3),
                fri=wk_monday + timedelta(days=4),
                sun=wk_monday + timedelta(days=6),
                mon=wk_monday + timedelta(days=7),
            )
        )
    return out
