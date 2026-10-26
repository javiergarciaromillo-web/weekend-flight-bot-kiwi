"""NCIA The Hague calendar transcribed from the supplied official holiday PDF.

No public-holiday inference: only published NCIA dates are treated as holidays.
"""
from datetime import date, timedelta
from src.planner import allowed_pair

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


def outbound_dates_for_weekend(saturday):
    """Thursday/Friday normally; shift to the working eve of a Friday holiday block.

    Holiday weekdays themselves are available at any time. Limit the weekly
    options to Monday-Friday; multi-week breaks are covered by holiday pairs.
    """
    friday = saturday - timedelta(days=1)
    thursday = friday - timedelta(days=1)
    first = friday
    if friday in HOLIDAYS:
        while first.weekday() > 0 and first - timedelta(days=1) in HOLIDAYS:
            first -= timedelta(days=1)
    earliest = min(thursday, max(saturday - timedelta(days=5),
                                first - timedelta(days=1)))
    return [earliest + timedelta(days=i)
            for i in range((friday - earliest).days + 1)]


def inbound_dates_for_weekend(saturday):
    """Sunday/Monday normally; extend through Monday holidays to the next workday."""
    sunday = saturday + timedelta(days=1)
    monday = sunday + timedelta(days=1)
    last = monday
    if monday in HOLIDAYS:
        while is_free_day(last):
            last += timedelta(days=1)
    elif monday + timedelta(days=1) in HOLIDAYS:
        # Example: NCIA King's Day Tuesday 27 April 2027. A Monday TT can
        # extend the family weekend; a Wednesday early return can avoid more TT.
        last = monday + timedelta(days=2)
        while is_free_day(last):
            last += timedelta(days=1)
    return [sunday + timedelta(days=i)
            for i in range((last - sunday).days + 1)]


def is_morning_return_workday(day):
    """Monday's before-09:00 arrival window follows consecutive Monday holidays."""
    if is_free_day(day):
        return False
    if day.weekday() == 0:
        return True
    monday = day - timedelta(days=day.weekday())
    if day.weekday() == 2 and monday + timedelta(days=1) in HOLIDAYS:
        return True
    return monday in HOLIDAYS and all(
        is_free_day(monday + timedelta(days=i)) for i in range(day.weekday())
    )


def workdays_affected(outbound, inbound):
    """Dates requiring an absence arrangement after evening departure.

Departure on a working day assumes work before a >=17:00 flight. Return on a
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
    return sorted(pair for pair in pairs if allowed_pair(*pair))
