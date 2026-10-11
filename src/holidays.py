"""NCIA The Hague calendar transcribed from the supplied official holiday PDF.

No public-holiday inference: only published NCIA dates are treated as holidays.
"""
from datetime import date, timedelta

HOLIDAYS = {
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 4, 3), date(2026, 4, 6),
    date(2026, 4, 27), date(2026, 5, 1), date(2026, 5, 5), date(2026, 5, 14),
    date(2026, 5, 25), date(2026, 11, 2),
    *(date(2026, 12, d) for d in [23, 24, 25, 28, 29, 30, 31]),
    date(2027, 1, 1), date(2027, 3, 26), date(2027, 3, 29), date(2027, 4, 27),
    date(2027, 5, 3), date(2027, 5, 6), date(2027, 5, 17), date(2027, 8, 16),
    date(2027, 11, 1),
    *(date(2027, 12, d) for d in [23, 24, 27, 28, 29, 30, 31]),
}


def is_free_day(day):
    return day.weekday() >= 5 or day in HOLIDAYS


def workdays_affected(outbound, inbound):
    """Dates requiring an absence arrangement after evening departure.

Departure on a working day assumes work before a >=16:00 flight. Return on a
working day is conservatively counted; this is not an approved leave balance.
"""
    return sum(not is_free_day(outbound + timedelta(days=i))
               for i in range(1, (inbound-outbound).days+1))


def holiday_dates(outbound, inbound):
    return sorted(d for d in HOLIDAYS if outbound <= d <= inbound)


def generate_holiday_pairs(start_date, horizon_days=180, max_workdays=5):
    """Sample bridges within horizon, including up to five working days.

The last day must also be within the search horizon. Depart on the eve of the
free block or up to two days earlier; return on its final day or up to two days
later. Retain one longest option per workday cost per distinct free block.
"""
    end = start_date + timedelta(days=horizon_days)
    blocks = set()
    for holiday in sorted(HOLIDAYS):
        if not start_date <= holiday <= end:
            continue
        first = last = holiday
        while is_free_day(first - timedelta(days=1)):
            first -= timedelta(days=1)
        while is_free_day(last + timedelta(days=1)):
            last += timedelta(days=1)
        blocks.add((first, last))
    pairs = set()
    for first, last in sorted(blocks):
        choices = {}
        for before in range(8):
            outbound = first - timedelta(days=1+before)
            for after in range(8):
                inbound = last + timedelta(days=after)
                if not (start_date <= outbound < inbound <= end):
                    continue
                cost = workdays_affected(outbound, inbound)
                if cost > max_workdays:
                    continue
                pair = (outbound, inbound)
                old = choices.get(cost)
                if old is None or (inbound-outbound).days > (old[1]-old[0]).days:
                    choices[cost] = pair
        pairs.update(choices.values())
    return sorted(pairs)
