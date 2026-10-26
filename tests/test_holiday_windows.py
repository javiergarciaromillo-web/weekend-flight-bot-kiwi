"""Regression coverage for real and consecutive NCIA holiday flight windows."""
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from src import holidays
from src.family import build_coverage, joined_pairs
from src.holidays import (outbound_dates_for_weekend, inbound_dates_for_weekend,
                          is_morning_return_workday)
from src.learning import _build_pairs_for_offset
from src.planner import allowed_pair, generate_weekend_pairs
from src.scrapers.google_flights_ui import _departure_ok, _bind_leg


class HolidayWindowTests(unittest.TestCase):
    def test_normal_weekend_options_unchanged(self):
        saturday = date(2026, 10, 24)
        self.assertEqual(outbound_dates_for_weekend(saturday),
                         [date(2026, 10, 22), date(2026, 10, 23)])
        self.assertEqual(inbound_dates_for_weekend(saturday),
                         [date(2026, 10, 25), date(2026, 10, 26)])
        self.assertEqual(set(generate_weekend_pairs(date(2026, 10, 19), 1)),
                         {(date(2026, 10, 22), date(2026, 10, 25)),
                          (date(2026, 10, 22), date(2026, 10, 26)),
                          (date(2026, 10, 23), date(2026, 10, 26))})
        self.assertFalse(allowed_pair(date(2026, 10, 23), date(2026, 10, 25)))

    def test_real_2027_easter_friday_and_monday(self):
        saturday = date(2027, 3, 27)
        self.assertEqual(outbound_dates_for_weekend(saturday),
                         [date(2027, 3, 25), date(2027, 3, 26)])
        self.assertEqual(inbound_dates_for_weekend(saturday),
                         [date(2027, 3, 28), date(2027, 3, 29), date(2027, 3, 30)])
        self.assertTrue(allowed_pair(date(2027, 3, 26), date(2027, 3, 28)))
        pairs = set(generate_weekend_pairs(date(2027, 3, 22), 1))
        self.assertIn((date(2027, 3, 26), date(2027, 3, 28)), pairs)
        self.assertIn((date(2027, 3, 25), date(2027, 3, 30)), pairs)
        self.assertTrue(_departure_ok(date(2027, 3, 26), '12:00', 'outbound'))
        self.assertTrue(_departure_ok(date(2027, 3, 29), '12:00', 'inbound', '14:00'))
        self.assertTrue(_departure_ok(date(2027, 3, 30), '06:00', 'inbound', '08:59'))
        self.assertFalse(_departure_ok(date(2027, 3, 30), '06:00', 'inbound', '09:00'))
        self.assertFalse(_departure_ok(date(2027, 3, 30), '06:00', 'inbound', '08:00+1'))

    def test_consecutive_thursday_friday_holidays_shift_departure_to_wednesday(self):
        saturday = date(2027, 5, 8)
        with patch.object(holidays, 'HOLIDAYS', holidays.HOLIDAYS | {date(2027, 5, 7)}):
            self.assertEqual(outbound_dates_for_weekend(saturday),
                             [date(2027, 5, 5), date(2027, 5, 6), date(2027, 5, 7)])
            self.assertFalse(_departure_ok(date(2027, 5, 5), '16:59', 'outbound'))
            self.assertTrue(_departure_ok(date(2027, 5, 5), '17:00', 'outbound'))
            self.assertTrue(_departure_ok(date(2027, 5, 6), '11:00', 'outbound'))
            self.assertTrue(_departure_ok(date(2027, 5, 7), '11:00', 'outbound'))
            pairs = generate_weekend_pairs(date(2027, 5, 3), 1)
            self.assertIn((date(2027, 5, 5), date(2027, 5, 9)), pairs)

    def test_consecutive_monday_tuesday_holidays_shift_morning_return_to_wednesday(self):
        saturday = date(2027, 5, 1)
        with patch.object(holidays, 'HOLIDAYS', holidays.HOLIDAYS | {date(2027, 5, 4)}):
            self.assertEqual(inbound_dates_for_weekend(saturday),
                             [date(2027, 5, 2), date(2027, 5, 3),
                              date(2027, 5, 4), date(2027, 5, 5)])
            self.assertTrue(_departure_ok(date(2027, 5, 4), '12:00', 'inbound', '14:00'))
            self.assertTrue(is_morning_return_workday(date(2027, 5, 5)))
            self.assertTrue(_departure_ok(date(2027, 5, 5), '06:00', 'inbound', '08:59'))
            self.assertFalse(_departure_ok(date(2027, 5, 5), '06:00', 'inbound', '09:00'))
            pairs = set(generate_weekend_pairs(date(2027, 4, 26), 1))
            self.assertIn((date(2027, 4, 29), date(2027, 5, 5)), pairs)

    def test_real_tuesday_king_day_extends_april_family_weekend(self):
        saturday = date(2027, 4, 24)
        dates = inbound_dates_for_weekend(saturday)
        self.assertEqual(dates, [date(2027, 4, 25), date(2027, 4, 26),
                                 date(2027, 4, 27), date(2027, 4, 28)])
        self.assertTrue(_departure_ok(date(2027, 4, 27), '10:00', 'inbound', '12:00'))
        self.assertTrue(is_morning_return_workday(date(2027, 4, 28)))
        self.assertTrue(_departure_ok(date(2027, 4, 28), '06:00', 'inbound', '08:45'))
        self.assertFalse(_departure_ok(date(2027, 4, 28), '06:00', 'inbound', '09:10'))
        pairs = set(generate_weekend_pairs(date(2027, 4, 21), 1))
        self.assertIn((date(2027, 4, 22), date(2027, 4, 27)), pairs)
        self.assertIn((date(2027, 4, 23), date(2027, 4, 28)), pairs)

    def test_recovered_holiday_flight_and_family_coverage_still_visible(self):
        out, inc = date(2027, 3, 26), date(2027, 3, 30)
        legs = [{'destination': 'BCN', 'leg_date': out, 'leg_type': 'outbound',
                 'outbound_departure': '12:00', 'outbound_arrival': '14:00'}]
        self.assertEqual(len(_bind_leg(legs, out, inc)), 1)
        trips = [dict(outbound=out, inbound=inc, total=190)]
        coverage = build_coverage(trips, {}, {'required_from': '2027-03-01'})
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]['weekend'], date(2027, 3, 27))
        self.assertEqual(coverage[0]['best']['total'], 190)

    def test_long_range_learning_includes_shifted_options(self):
        samples = _build_pairs_for_offset(date(2027, 3, 1), 18)
        sample_pairs = {(out, inc) for _, out, inc in samples}
        self.assertIn((date(2027, 3, 26), date(2027, 3, 28)), sample_pairs)
        self.assertIn((date(2027, 3, 25), date(2027, 3, 30)), sample_pairs)
        self.assertEqual(len(sample_pairs), len(samples))


if __name__ == '__main__':
    unittest.main()
