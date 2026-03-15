from __future__ import annotations

from datetime import date, timedelta
from src.models import DatePair


def next_n_weeks_weekend_pairs(
    start_date: date,
    weeks_ahead: int,
    outbound_days: list[int],
    inbound_days: list[int],
) -> list[DatePair]:
    """
    weekday(): Monday=0 ... Sunday=6
    outbound_days: Thursday=3, Friday=4
    inbound_days: Sunday=6, Monday=0
    """
    pairs: list[DatePair] = []

    for day_offset in range(0, weeks_ahead * 7 + 7):
        current = start_date + timedelta(days=day_offset)
        if current.weekday() not in outbound_days:
            continue

        week_anchor = current - timedelta(days=current.weekday())

        for inbound_weekday in inbound_days:
            inbound = week_anchor + timedelta(days=inbound_weekday)

            if inbound <= current:
                inbound += timedelta(days=7)

            if (inbound - current).days > 4:
                continue

            pairs.append(
                DatePair(
                    outbound_date=current,
                    inbound_date=inbound,
                )
            )

    pairs = sorted(
        set(pairs),
        key=lambda p: (p.outbound_date, p.inbound_date),
    )
    return pairs
