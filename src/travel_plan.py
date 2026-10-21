"""Explicit no-flight weekends versus unallocated 2027 planning assumptions.

Assumptions change the *forecast*, never silently remove real flight searches.
Only Saturday-specific confirmed statuses can suppress a weekend.
"""
from datetime import date

NO_TRAVEL_STATES = frozenset({'skipped', 'visiting_nl', 'vacation'})
ALL_STATES = frozenset({'pending', 'booked', 'covered', 'unknown'}) | NO_TRAVEL_STATES

DEFAULT_FORECAST = {
    'vacation_weeks': 0,
    'visiting_every_weeks': [4, 6],
    'additional_skips_range': [0, 0],
}


def confirmed_no_flight(plan, saturday):
    """Only explicit dated exclusions count, not forecast assumptions."""
    return (plan or {}).get('weekends', {}).get(str(saturday)) in NO_TRAVEL_STATES


def forecast_config(plan):
    """Validate transparent scenario inputs; zero vacation by default."""
    supplied = (plan or {}).get('forecast_assumptions') or {}
    values = {**DEFAULT_FORECAST, **supplied}
    if not isinstance(values['vacation_weeks'], int) or isinstance(values['vacation_weeks'], bool):
        raise ValueError('vacation_weeks must be a nonnegative integer')
    if not 0 <= values['vacation_weeks'] <= 52:
        raise ValueError('vacation_weeks must be between 0 and 52')
    intervals = values['visiting_every_weeks']
    skips = values['additional_skips_range']
    for name, pair, low_limit in [('visiting_every_weeks', intervals, 1),
                                  ('additional_skips_range', skips, 0)]:
        if (not isinstance(pair, list) or len(pair) != 2
                or any(type(x) is not int or x < low_limit for x in pair)
                or pair[0] > pair[1]):
            raise ValueError(f'{name} must be a two-integer ascending range')
    return values
