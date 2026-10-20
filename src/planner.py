from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple


def allowed_pair(outbound: date, inbound: date) -> bool:
    """Exclude ordinary Friday-Sunday trips; a free Friday can justify one."""
    if outbound.weekday() == 4 and inbound.weekday() == 6 and (inbound-outbound).days == 2:
        # Friday-Sunday is too short normally; a free Friday adds a full day.
        from src.holidays import HOLIDAYS
        return outbound in HOLIDAYS
    return outbound < inbound


# Earlier prices used different departure windows and are not comparable.
FILTER_HISTORY_START = date(2026, 10, 20)


def generate_weekend_pairs(
    start_date: date,
    weeks: int,
    skip_weeks: int = 0,
) -> List[Tuple[date, date]]:
    """
    Generate weekly date pairs, extending dates across NCIA holiday blocks.

    Example:
    - weeks=7
    - skip_weeks=1

    means:
    skip the first 7 days from today and then scan the following 7 weeks.
    """

    from src.holidays import outbound_dates_for_weekend, inbound_dates_for_weekend

    scan_start = start_date + timedelta(days=skip_weeks * 7)
    scan_end = scan_start + timedelta(weeks=weeks)
    pairs: set[tuple[date, date]] = set()

    for offset in range((scan_end - scan_start).days):
        saturday = scan_start + timedelta(days=offset)
        if saturday.weekday() != 5:
            continue
        for outbound in outbound_dates_for_weekend(saturday):
            if not (scan_start <= outbound < scan_end):
                continue
            for inbound in inbound_dates_for_weekend(saturday):
                if allowed_pair(outbound, inbound):
                    pairs.add((outbound, inbound))
    return sorted(pairs)
