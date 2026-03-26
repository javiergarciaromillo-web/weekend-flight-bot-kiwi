from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple


def generate_weekend_pairs(
    start_date: date,
    weeks: int,
    skip_weeks: int = 0,
) -> List[Tuple[date, date]]:
    """
    Generate Thu/Fri outbound with Sun/Mon inbound pairs.

    Example:
    - weeks=7
    - skip_weeks=1

    means:
    skip the first 7 days from today and then scan the following 7 weeks.
    """

    pairs: list[tuple[date, date]] = []

    scan_start = start_date + timedelta(days=skip_weeks * 7)
    scan_days = weeks * 7

    for i in range(scan_days):
        d = scan_start + timedelta(days=i)

        # Thursday or Friday
        if d.weekday() not in [3, 4]:
            continue

        sunday = d + timedelta(days=(6 - d.weekday()))
        monday = sunday + timedelta(days=1)

        pairs.append((d, sunday))
        pairs.append((d, monday))

    # remove duplicates while preserving order
    seen = set()
    unique_pairs = []
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        unique_pairs.append(pair)

    return unique_pairs
