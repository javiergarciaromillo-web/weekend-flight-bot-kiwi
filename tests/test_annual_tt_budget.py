"""Annual allowance is a shared 46-day budget, not 46 days per ticket."""
import unittest
from datetime import date

from src.budget import (annual_tt_outlook, projected_annual_tt,
                        projected_selection_tt, trip_work_dates)
from src.family import build_coverage, render_coverage


def sample(out, back, amount=100):
    return dict(outbound=out, inbound=back, total=amount,
                out=[dict(price=40, outbound_departure='17:00',
                          outbound_arrival='19:00')],
                inc=[dict(price=60, outbound_departure='17:00',
                          outbound_arrival='19:00')])


class AnnualPlanningTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'required_from': '2027-02-01'}
        self.year = annual_tt_outlook(self.plan)
        self.assertEqual(self.year['baseline_tt'], 45)

    def test_one_weekend_monday_evening_uses_last_budget_buffer(self):
        saturday = date(2027, 2, 6)
        proposal = sample(date(2027, 2, 4), date(2027, 2, 8))
        workdays, _ = trip_work_dates(proposal)
        self.assertEqual(len(workdays), 2)
        projection = projected_annual_tt(workdays, [saturday], self.year)
        self.assertEqual(projection['projected'], 46)
        self.assertFalse(projection['exceeds_cap'])

    def test_two_weekends_with_late_monday_use_more_than_46(self):
        trips = [sample(date(2027, 2, 4), date(2027, 2, 8), 120),
                 sample(date(2027, 2, 11), date(2027, 2, 15), 125)]
        cov = build_coverage(trips, {}, self.plan)
        proj = projected_selection_tt(cov, self.year)
        self.assertEqual(proj['priced_weeks'], 2)
        self.assertEqual(proj['projected'], 47)
        self.assertTrue(proj['exceeds_cap'])
        html = render_coverage(cov, [], annual_outlook=self.year)
        self.assertIn('47/46 TT', html)
        self.assertIn('cupo teórico se supera', html)

    def test_best_weekly_choice_prefers_budget_compatible_option(self):
        cheaper = sample(date(2027, 2, 4), date(2027, 2, 8), 90)
        regular = sample(date(2027, 2, 4), date(2027, 2, 7), 110)
        # Within a single week, an extra TT still fits 46, so the cheaper
        # Monday-return flight remains a valid choice; comparison displays 46.
        coverage = build_coverage([cheaper, regular], {}, self.plan)
        self.assertEqual(coverage[0]['best']['total'], 90)
        html = render_coverage(coverage, [], annual_outlook=self.year)
        self.assertIn('46/46 TT', html)

    def test_two_weekend_join_is_annual_budget_risk_even_if_cheaper(self):
        a = sample(date(2027, 2, 4), date(2027, 2, 7), 130)
        b = sample(date(2027, 2, 11), date(2027, 2, 14), 130)
        together = sample(date(2027, 2, 4), date(2027, 2, 14), 145)
        dates = trip_work_dates(together)[0]
        p = projected_annual_tt(dates,
                                [date(2027, 2, 6), date(2027, 2, 13)],
                                self.year)
        self.assertEqual(p['projected'], 49)
        self.assertTrue(p['exceeds_cap'])


if __name__ == '__main__':
    unittest.main()
