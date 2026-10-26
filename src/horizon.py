"""Staggered monitoring of every family weekend, beginning far before departure.

A 300-day horizon covers early fare releases. Sampling is per target weekend
and spread over the seven calendar weekdays so daily jobs stay affordable.
Never present unqueried weeks as live fare checks.
"""
from datetime import date, timedelta

from src.family import weekend_of
from src.holidays import generate_holiday_pairs, HOLIDAYS
from src.priority_digest import holiday_weekend
from src.planner import generate_weekend_pairs
from src.travel_plan import confirmed_no_flight


HORIZON_DAYS = 300
DAILY_WEEKS = 8
TWICE_WEEKLY_UNTIL_WEEKS = 20


def monitoring_plan(run_date: date, planning_start: date, family_plan=None):
    """Return (operational pairs, all target Saturdays, daily Saturdays, due Saturdays).

    First eight family weekends remain daily even when the family start is
    several months away. Beyond that, <=8 weeks are daily, 9-20 weeks get
    three samples per week, and more distant weeks get two samples per week.
    NCIA holiday weekends get three samples weekly even when distant, and
    daily samples inside 110 days.
    Holiday long stays and adjacent-weekend joins are considered only for
    weekends sampled on this run.
    """
    if planning_start < run_date:
        planning_start = run_date
    horizon_end = max(run_date + timedelta(days=HORIZON_DAYS),
                      planning_start + timedelta(weeks=DAILY_WEEKS))
    weeks = (horizon_end - planning_start).days // 7 + 2
    plan = family_plan or {}
    last_required = (date.fromisoformat(plan['required_until'])
                     if plan.get('required_until') else horizon_end)
    all_pairs = [(out, inc) for out, inc in
                 generate_weekend_pairs(planning_start, weeks=weeks)
                 if not confirmed_no_flight(plan, weekend_of(out))
                 and weekend_of(out) <= last_required]
    visible = sorted({weekend_of(out) for out, inc in all_pairs
                      if weekend_of(out) <= horizon_end
                      and inc <= horizon_end + timedelta(days=4)})
    daily = set(visible[:DAILY_WEEKS])
    due = set()
    today_bucket = run_date.toordinal() % 7
    priority_holidays = {holiday_weekend(day) for day in HOLIDAYS if day.year == 2027}
    for sat in visible:
        days_ahead = (sat - run_date).days
        if sat in daily or days_ahead <= DAILY_WEEKS * 7:
            daily.add(sat)
            due.add(sat)
        elif sat in priority_holidays and days_ahead <= 110:
            # Check NCIA holiday travel daily once the date draws closer.
            due.add(sat)
        elif days_ahead <= TWICE_WEEKLY_UNTIL_WEEKS * 7 or sat in priority_holidays:
            phase = (sat.toordinal() // 7) % 7
            if today_bucket in (phase, (phase + 2) % 7, (phase + 4) % 7):
                due.add(sat)
        else:
            phase = (sat.toordinal() // 7) % 7
            if today_bucket in (phase, (phase + 3) % 7):
                due.add(sat)

    chosen = {(out, inc) for out, inc in all_pairs
              if weekend_of(out) in due and out >= planning_start}
    # Preserve longer NCIA bridge alternatives, but do not scrape all holiday
    # dates daily when they are far outside the immediate daily window.
    for out, inc in generate_holiday_pairs(planning_start,
                                           horizon_days=(horizon_end - planning_start).days):
        # A confirmed no-flight weekend stays excluded even from a
        # long holiday or two-weekend combination. An undated forecast does
        # not suppress any fare queries.
        candidate_saturdays = [
            out + timedelta(days=i)
            for i in range((inc - out).days + 1)
            if (out + timedelta(days=i)).weekday() == 5
        ]
        if (out >= planning_start and inc <= horizon_end
                and any(out <= sat <= inc for sat in due)
                and not any(confirmed_no_flight(plan, sat)
                            for sat in candidate_saturdays)):
            chosen.add((out, inc))
    return sorted(chosen), visible, sorted(daily), sorted(due)
