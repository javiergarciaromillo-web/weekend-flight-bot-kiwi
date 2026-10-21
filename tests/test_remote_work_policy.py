"""Remote work annual allocation and consecutive days approval policy."""
import unittest
from datetime import date, timedelta

from src.budget import (REMOTE_WORK_DAYS, MAX_CONSECUTIVE_REMOTE_DAYS,
                        consecutive_remote_days, assess_remote_plan,
                        annual_tt_outlook, trip_work_dates)
from src.family import build_coverage, join_opportunities, render_coverage


def trip(out, inc, total, dep='17:45', arr='19:45',
         ret='17:30', retarr='20:00'):
    return dict(outbound=out, inbound=inc, total=total,
                out=[dict(origin='AMS', destination='BCN', price=total/2,
                          outbound_departure=dep, outbound_arrival=arr)],
                inc=[dict(origin='BCN', destination='AMS', price=total/2,
                          outbound_departure=ret, outbound_arrival=retarr)])


class RemoteWorkPolicyTests(unittest.TestCase):
    def test_exact_annual_cap_is_46(self):
        self.assertEqual(REMOTE_WORK_DAYS, 46)
        self.assertEqual(MAX_CONSECUTIVE_REMOTE_DAYS, 5)
        x = assess_remote_plan([date(2027, 2, 1) + timedelta(days=i)
                                for i in range(7)])
        self.assertEqual(x['annual_cap'], 46)

    def test_5_workdays_are_permitted_and_weekend_does_not_reset_streak(self):
        dates = [date(2027, 2, 4), date(2027, 2, 5),
                 date(2027, 2, 8), date(2027, 2, 9), date(2027, 2, 10)]
        self.assertEqual(consecutive_remote_days(dates), 5)
        self.assertFalse(assess_remote_plan(dates)['requires_special_authorisation'])
        dates.append(date(2027, 2, 11))
        self.assertEqual(consecutive_remote_days(dates), 6)
        self.assertTrue(assess_remote_plan(dates)['requires_special_authorisation'])

    def test_workday_gap_breaks_a_tt_period(self):
        dates = [date(2027, 2, 4), date(2027, 2, 5),
                 date(2027, 2, 9), date(2027, 2, 10), date(2027, 2, 11)]
        self.assertEqual(consecutive_remote_days(dates), 3)

    def test_2027_yearly_family_weekend_baseline_is_close_to_limit(self):
        outlook = annual_tt_outlook({'required_from': '2027-02-01'})
        self.assertEqual(outlook['year'], 2027)
        self.assertEqual(outlook['cap'], 46)
        self.assertEqual(outlook['weekends'], 47)
        self.assertEqual(outlook['baseline_tt'], 45)
        self.assertEqual(outlook['margin'], 1)
        self.assertFalse(outlook['verified_remaining'])

    def test_annual_forecast_skips_explicit_exceptions(self):
        plan = {'required_from': '2027-02-01',
                'weekends': {'2027-02-06': 'skipped'}}
        base = annual_tt_outlook({'required_from': '2027-02-01'})
        outlook = annual_tt_outlook(plan)
        self.assertEqual(outlook['weekends'], 46)
        self.assertEqual(outlook['baseline_tt'], base['baseline_tt'] - 1)

    def test_joined_weekends_over_5_tt_require_special_authorisation(self):
        first = trip(date(2027, 2, 4), date(2027, 2, 7), 150)
        second = trip(date(2027, 2, 11), date(2027, 2, 14), 170)
        joined = trip(date(2027, 2, 4), date(2027, 2, 14), 210)
        coverage = build_coverage([first, second, joined], {})
        joins = join_opportunities(coverage, [first, second, joined])
        self.assertEqual(len(joins), 1)
        self.assertEqual(joins[0]['joined_tt'], 6)
        self.assertEqual(joins[0]['longest_streak'], 6)
        self.assertTrue(joins[0]['needs_special_authorisation'])
        html = render_coverage(coverage, joins,
                               annual_outlook=annual_tt_outlook({'required_from': '2027-02-01'}))
        self.assertIn('46 días', html)
        self.assertIn('NO PRIORITARIA', html)
        self.assertIn('autorización especial', html)
        self.assertIn('45 días', html)

    def test_holiday_interruption_does_not_require_permission_if_5_tt_days(self):
        # Good Friday is free on 26 March; it contributes no TT.
        joined = trip(date(2027, 3, 18), date(2027, 3, 28), 200)
        dates, _ = trip_work_dates(joined)
        self.assertEqual(len(dates), 5)
        self.assertEqual(consecutive_remote_days(dates), 5)
        self.assertFalse(assess_remote_plan(dates)['requires_special_authorisation'])


if __name__ == '__main__':
    unittest.main()
