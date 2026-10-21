"""2027 realistic family travel rhythm: vacation, visits and ad-hoc non-travel."""
import unittest
from datetime import date

from src.budget import annual_tt_outlook, projected_annual_tt
from src.family import load_plan
from src.horizon import monitoring_plan
from src.travel_plan import confirmed_no_flight, forecast_config


class RealisticFamilyPlanTests(unittest.TestCase):
    def test_configured_2027_scenario_is_not_every_weekend(self):
        plan = load_plan()
        assumptions = forecast_config(plan)
        self.assertEqual(plan['required_from'], '2027-02-01')
        self.assertEqual(assumptions['vacation_weeks'], 6)
        self.assertEqual(assumptions['visiting_every_weeks'], [4, 6])
        self.assertEqual(assumptions['additional_skips_range'], [0, 2])
        outlook = annual_tt_outlook(plan)
        self.assertEqual(outlook['calendar_weekends'], 47)
        self.assertEqual(outlook['confirmed_no_flight_weekends'], 1)
        self.assertEqual(outlook['all_weekend_baseline_tt'], 45)
        self.assertEqual(outlook['assumed_vacation_weeks'], 6)
        self.assertEqual(outlook['assumed_partner_visits_min'], 6)
        self.assertEqual(outlook['assumed_partner_visits_max'], 10)
        self.assertEqual(outlook['scenario_min_tt'], 27)
        self.assertEqual(outlook['scenario_max_tt'], 34)
        self.assertLess(outlook['scenario_max_tt'], outlook['cap'])
        self.assertFalse(outlook['verified_remaining'])

    def test_last_december_week_is_explicit_break_without_double_discount(self):
        plan = load_plan()
        self.assertTrue(confirmed_no_flight(plan, date(2027, 12, 25)))
        self.assertFalse(confirmed_no_flight(plan, date(2027, 12, 18)))
        # The NCIA closure already makes Friday 24 December free.
        self.assertEqual(annual_tt_outlook(plan)['all_weekend_baseline_tt'], 45)

    def test_vacation_and_visits_have_no_invented_dates_and_do_not_suppress_flights(self):
        plan = load_plan()
        self.assertEqual(set(plan['weekends']), {'2027-12-25'})
        pairs, visible, daily, due = monitoring_plan(
            date(2026, 10, 21), date(2027, 2, 1), family_plan=plan
        )
        self.assertIn(date(2027, 2, 6), visible)
        self.assertIn(date(2027, 2, 6), daily)
        self.assertIn((date(2027, 2, 4), date(2027, 2, 7)), pairs)

    def test_dated_partner_visit_suppresses_only_its_own_weekend(self):
        plan = load_plan()
        plan['weekends'] = dict(plan['weekends'], **{'2027-02-06': 'visiting_nl'})
        pairs, visible, daily, due = monitoring_plan(
            date(2026, 10, 21), date(2027, 2, 1), family_plan=plan
        )
        self.assertNotIn(date(2027, 2, 6), visible)
        self.assertIn(date(2027, 2, 13), visible)
        self.assertTrue(all(not(out <= date(2027, 2, 6) < inc)
                            for out, inc in pairs))

    def test_confirming_a_vacation_week_reduces_undated_count(self):
        plan = load_plan()
        plan['weekends'] = dict(plan['weekends'], **{'2027-06-12': 'vacation'})
        outlook = annual_tt_outlook(plan)
        self.assertEqual(outlook['assumed_vacation_weeks'], 5)
        self.assertEqual(outlook['confirmed_no_flight_weekends'], 2)

    def test_generic_plan_without_forecast_retains_prior_strict_baseline(self):
        base = annual_tt_outlook({'required_from': '2027-02-01'})
        self.assertFalse(base['forecast_used'])
        self.assertEqual(base['baseline_tt'], 45)
        self.assertEqual(base['scenario_min_tt'], 45)
        self.assertEqual(base['scenario_max_tt'], 45)
        self.assertTrue(projected_annual_tt([], [], base)['model_only'])

    def test_reject_invalid_forecast_configuration(self):
        from src.travel_plan import forecast_config
        with self.assertRaises(ValueError):
            forecast_config({'forecast_assumptions': {'vacation_weeks': -1}})
        with self.assertRaises(ValueError):
            forecast_config({'forecast_assumptions': {'visiting_every_weeks': [6, 4]}})


if __name__ == '__main__':
    unittest.main()
