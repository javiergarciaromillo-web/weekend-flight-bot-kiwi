"""Staggered monitoring of every family weekend, beginning far before departure.

A 300-day horizon covers early fare releases. Sampling is per target weekend
and spread over the seven calendar weekdays so daily jobs stay affordable.
Never present unqueried weeks as live fare checks.
"""
from datetime import date, timedelta

from src.family import weekend_of
from src.holidays import generate_holiday_pairs
from src.planner import generate_weekend_pairs


HORIZON_DAYS = 300
DAILY_WEEKS = 8
TWICE_WEEKLY_UNTIL_WEEKS = 20


def monitoring_plan(run_date: date, planning_start: date):
    """Return (operational pairs, all target Saturdays, daily Saturdays, due Saturdays).

    First eight family weekends remain daily even when the family start is
    several months away. Beyond that, <=8 weeks are daily, 9-20 weeks get
    three samples per week, and more distant weeks get two samples per week.
    Holiday long stays and adjacent-weekend joins are considered only for
    weekends sampled on this run.
    """
    if planning_start < run_date:
        planning_start = run_date
    horizon_end = max(run_date + timedelta(days=HORIZON_DAYS),
                      planning_start + timedelta(weeks=DAILY_WEEKS))
    weeks = (horizon_end - planning_start).days // 7 + 2
    all_pairs = generate_weekend_pairs(planning_start, weeks=weeks)
    visible = sorted({weekend_of(out) for out, inc in all_pairs
                      if weekend_of(out) <= horizon_end and inc <= horizon_end + timedelta(days=4)})
    daily = set(visible[:DAILY_WEEKS])
    due = set()
    today_bucket = run_date.toordinal() % 7
    for sat in visible:
        days_ahead = (sat - run_date).days
        if sat in daily or days_ahead <= DAILY_WEEKS * 7:
            daily.add(sat)
            due.add(sat)
        elif days_ahead <= TWICE_WEEKLY_UNTIL_WEEKS * 7:
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
        if (out >= planning_start and inc <= horizon_end
                and any(out <= sat <= inc for sat in due)):
            chosen.add((out, inc))
    return sorted(chosen), visible, sorted(daily), sorted(due)
