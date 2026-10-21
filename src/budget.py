"""Annual Spain remote-work and annual-leave planning limits.

These are annual allowances, not verified remaining balances. Estimates for
separate trips must not be added when their dates overlap.
"""
from datetime import date, datetime, timedelta
from src.holidays import is_free_day

REMOTE_WORK_DAYS = 46
MAX_CONSECUTIVE_REMOTE_DAYS = 5
ANNUAL_LEAVE_DAYS = 30

# User confirmed full 2027 allowances; additional carried leave is unquantified.
CONFIRMED_BALANCES = {2027: {"remote": 46, "leave": 30}}


def _clock(value):
    """Flight local wall time; dates are tracked separately."""
    if not value:
        return None
    value = str(value).replace('+1', '').strip().upper()
    for fmt in ('%H:%M', '%I:%M %p'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    return None


def trip_work_dates(trip):
    """Dates potentially needing Spain TT or leave for a specific flight choice.

    The departure day is assumed worked in NL for after-work flights. Early
    Friday departures may require TT or leave after arrival in Barcelona.
    An eligible return landing in NL before 09:00 is assumed to allow
    working that day in NL; transfer practicality is deliberately not checked.
    Does not assert that TT/leave has been requested or approved.
    """
    out, inc = trip['outbound'], trip['inbound']
    required = {out + timedelta(days=i)
                for i in range(1, (inc-out).days + 1)
                if not is_free_day(out + timedelta(days=i))}
    outbound_rows = trip.get('out') or []
    inbound_rows = trip.get('inc') or []
    notes = []
    if outbound_rows and not is_free_day(out):
        flight = min(outbound_rows, key=lambda r: r['price'])
        departure = _clock(flight.get('outbound_departure'))
        if departure is not None and departure.hour < 8:
            required.add(out)
            notes.append('Salida antes de las 08:00: el día de salida puede necesitar TT o permiso parcial.')

    if inbound_rows and not is_free_day(inc):
        flight = min(inbound_rows, key=lambda r: r['price'])
        departure = _clock(flight.get('outbound_departure'))
        arrival = _clock(flight.get('outbound_arrival'))
        overnight = '+1' in str(flight.get('outbound_arrival') or '')
        from datetime import time
        if (not overnight and departure is not None and arrival is not None
                and departure < arrival < time(9, 0)):
            required.discard(inc)
            notes.append('Regreso con llegada a NL antes de las 09:00: no se cuenta TT ese día.')
    return sorted(required), notes


def consecutive_remote_days(dates):
    """Longest uninterrupted block of teleworking WORKDAYS.

    Weekends and NCIA holidays do not by themselves reset a block of TT: a
    Friday followed by the next Monday is a continuous workday sequence.
    An unassigned *working* day between TT dates interrupts the block.
    Treat all 'TT/leave to organise' dates as TT until actual leave is known.
    """
    ordered = sorted(set(dates))
    longest = run = 0
    previous = None
    for day in ordered:
        if previous is not None:
            between = [previous + timedelta(days=i)
                       for i in range(1, (day-previous).days)]
            run = run + 1 if all(is_free_day(other) for other in between) else 1
        else:
            run = 1
        longest = max(longest, run)
        previous = day
    return longest


def assess_remote_plan(dates):
    """Individual scenario review; never claim remaining annual balances."""
    by_year = {}
    for day in sorted(set(dates)):
        by_year[day.year] = by_year.get(day.year, 0) + 1
    longest = consecutive_remote_days(dates)
    return {
        'tt_days': len(set(dates)),
        'longest_consecutive_tt': longest,
        'requires_special_authorisation': longest > MAX_CONSECUTIVE_REMOTE_DAYS,
        'annual_cap': REMOTE_WORK_DAYS,
        'annual_excess_in_scenario': {
            year: max(0, count - REMOTE_WORK_DAYS) for year, count in by_year.items()
        },
    }


def annual_tt_outlook(plan, year=2027):
    """Rough yearly baseline: one Friday working remotely for each family weekend.

    Excludes explicitly skipped weekends and NCIA-holiday Fridays. It is NOT a
    booking record, approved TT schedule, or proof of enough remaining days.
    """
    from datetime import date
    if not plan or not plan.get('required_from'):
        return None
    start = max(date.fromisoformat(plan['required_from']), date(year, 1, 1))
    end = min(date.fromisoformat(plan['required_until'])
              if plan.get('required_until') else date(year, 12, 31),
              date(year, 12, 31))
    if start > end:
        return None
    saturday = start + timedelta(days=(5-start.weekday()) % 7)
    weekends = 0
    baseline = 0
    while saturday <= end:
        if plan.get('weekends', {}).get(str(saturday)) != 'skipped':
            weekends += 1
            friday = saturday - timedelta(days=1)
            baseline += int(not is_free_day(friday))
        saturday += timedelta(days=7)
    return dict(year=year, weekends=weekends, baseline_tt=baseline,
                cap=REMOTE_WORK_DAYS, margin=REMOTE_WORK_DAYS-baseline,
                verified_remaining=False)


def projected_annual_tt(workdates, saturdays, outlook):
    """Sensitivity test for alternatives against the 1-Friday-TT annual baseline.

    Not a running booked/approved balance. It substitutes the proposal's TT
    dates for the corresponding Saturdays in an illustrative full-year plan.
    """
    if not outlook:
        return None
    year = outlook['year']
    unique_saturdays = {sat for sat in saturdays if sat.year == year
                        and sat >= date(year, 1, 1)}
    originally_expected = sum(
        int(not is_free_day(saturday - timedelta(days=1)))
        for saturday in unique_saturdays
    )
    proposed = sum(day.year == year for day in set(workdates))
    total = outlook['baseline_tt'] - originally_expected + proposed
    return dict(projected=total, annual_cap=outlook['cap'],
                additional=proposed - originally_expected,
                exceeds_cap=total > outlook['cap'],
                model_only=True)


def projected_selection_tt(coverage, outlook):
    """Combine the priced, unbooked weekly alternatives against the yearly baseline.

    Unknown/booked coverage is NOT confirmed: this is an illustrative
    sensitivity result, not an annual TT ledger or approved balance.
    """
    if not outlook:
        return None
    added = 0
    considered = 0
    for week in coverage:
        saturday = week['weekend']
        if saturday.year != outlook['year'] or week.get('state') not in ('pending', 'unknown'):
            continue
        best = week.get('best')
        if not best:
            continue
        dates = trip_work_dates(best)[0]
        base = int(not is_free_day(saturday - timedelta(days=1)))
        days = sum(day.year == outlook['year'] for day in set(dates))
        added += days - base
        considered += 1
    projected = outlook['baseline_tt'] + added
    return dict(projected=projected, annual_cap=outlook['cap'],
                deviation_from_baseline=added, priced_weeks=considered,
                exceeds_cap=projected > outlook['cap'], model_only=True)


def estimate_allocation(outbound, inbound, remaining_by_year=None, workdates=None):
    """Prefer remote work to preserve leave, split at calendar-year boundaries.

remaining_by_year may supply verified {'remote': n, 'leave': n} balances.
Missing years use annual limits and are explicitly marked unverified.
Departure assumes an evening flight after work; return day counts conservatively.
"""
    required = {}
    dates = (workdates if workdates is not None else
             [outbound + timedelta(days=i) for i in range(1, (inbound-outbound).days+1)
              if not is_free_day(outbound + timedelta(days=i))])
    for day in dates:
        required[day.year] = required.get(day.year, 0) + 1
    result = {}
    for year, count in sorted(required.items()):
        balances = (CONFIRMED_BALANCES if remaining_by_year is None else remaining_by_year).get(year)
        verified = balances is not None
        remote_limit = balances['remote'] if verified else REMOTE_WORK_DAYS
        leave_limit = balances['leave'] if verified else ANNUAL_LEAVE_DAYS
        if min(remote_limit, leave_limit) < 0:
            raise ValueError('Balances must not be negative')
        remote = min(count, remote_limit)
        leave = min(count-remote, leave_limit)
        result[year] = dict(remote=remote, leave=leave, uncovered=count-remote-leave,
                            verified=verified, required=count)
    return result
