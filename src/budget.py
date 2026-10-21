"""Annual Spain remote-work and annual-leave planning limits.

These are annual allowances, not verified remaining balances. Estimates for
separate trips must not be added when their dates overlap.
"""
from datetime import datetime, timedelta
from src.holidays import is_free_day

REMOTE_WORK_DAYS = 46
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
