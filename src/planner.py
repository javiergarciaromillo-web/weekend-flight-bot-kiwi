from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple


def allowed_pair(outbound: date, inbound: date) -> bool:
    """Exclude Friday–Sunday weekends; retain longer holiday stays."""
    return not (outbound.weekday() == 4 and inbound.weekday() == 6
                and (inbound - outbound).days == 2)


# Earlier prices used different departure windows and are not comparable.
FILTER_HISTORY_START = date(2026, 10, 12)


def generate_weekend_pairs(
    start_date: date,
    weeks: int,
    skip_weeks: int = 0,
) -> List[Tuple[date, date]]:
    """
    Generate Thu–Sun, Thu–Mon and Fri–Mon pairs.

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

        if d.weekday() == 3:
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
