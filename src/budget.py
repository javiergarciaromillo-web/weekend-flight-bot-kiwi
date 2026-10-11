"""Annual Spain remote-work and annual-leave planning limits.

These are annual allowances, not verified remaining balances. Estimates for
separate trips must not be added when their dates overlap.
"""
from datetime import timedelta
from src.holidays import is_free_day

REMOTE_WORK_DAYS = 46
ANNUAL_LEAVE_DAYS = 30

# User confirmed full 2027 allowances; additional carried leave is unquantified.
CONFIRMED_BALANCES = {2027: {"remote": 46, "leave": 30}}


def estimate_allocation(outbound, inbound, remaining_by_year=None):
    """Prefer remote work to preserve leave, split at calendar-year boundaries.

remaining_by_year may supply verified {'remote': n, 'leave': n} balances.
Missing years use annual limits and are explicitly marked unverified.
Departure assumes an evening flight after work; return day counts conservatively.
"""
    required = {}
    for i in range(1, (inbound-outbound).days+1):
        day = outbound + timedelta(days=i)
        if not is_free_day(day):
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
