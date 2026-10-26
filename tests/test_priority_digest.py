"""Regression tests for NCIA 2027 holiday planning and actionable email summary."""
import unittest
from datetime import date, timedelta
from src.holidays import HOLIDAYS
from src.horizon import monitoring_plan
from src.priority_digest import holiday_weekend, render_priority_digest


class PrioritiesTests(unittest.TestCase):
    def test_all_sixteen_explicit_ncia_holidays_for_2027(self):
        expected = {(1, 1), (3, 26), (3, 29), (4, 27), (5, 3),
                    (5, 6), (5, 17), (8, 16), (11, 1),
                    (12, 23), (12, 24), (12, 27), (12, 28),
                    (12, 29), (12, 30), (12, 31)}
        actual = {(d.month, d.day) for d in HOLIDAYS if d.year == 2027}
        self.assertEqual(actual, expected)
        self.assertEqual(holiday_weekend(date(2027, 4, 27)), date(2027, 4, 24))
        self.assertEqual(holiday_weekend(date(2027, 5, 6)), date(2027, 5, 8))
        self.assertEqual(holiday_weekend(date(2027, 8, 16)), date(2027, 8, 14))

    def test_holiday_week_is_checked_daily_inside_110_day_window(self):
        monday = date(2027, 2, 1)
        holiday_sat = date(2027, 5, 1)  # NCIA Monday 3 May
        ordinary_sat = date(2027, 5, 29)
        seen = []
        for delta in range(7):
            _, visible, daily, sampled = monitoring_plan(
                monday + timedelta(days=delta), date(2027, 2, 1))
            self.assertIn(holiday_sat, visible)
            self.assertNotIn(holiday_sat, daily)
            self.assertIn(holiday_sat, sampled)
            seen.append(ordinary_sat in sampled)
        self.assertLess(sum(seen), 7)

    def test_price_drop_header_before_weekly_listing_and_one_per_weekend(self):
        saturday = date(2027, 2, 6)
        out = date(2027, 2, 5)
        back = date(2027, 2, 8)
        flight = dict(price=65, airline='Vueling', origin='AMS',
                      destination='BCN', outbound_departure='17:00',
                      outbound_arrival='19:00', source_url='https://example.org')
        trip = dict(outbound=out, inbound=back, out=[flight],
                    inc=[dict(flight, origin='BCN', destination='AMS')],
                    total=130, delta=-35, count=6, minimum=130)
        week = dict(weekend=saturday, state='unknown', best=trip,
                    decision={'action': 'OBSERVAR', 'deadline': '2027-01-15',
                              'reason': 'Sin histórico suficiente'})
        html = render_priority_digest(date(2026, 10, 26), [week], [trip, trip],
                                      {}, tracking=[], family_plan={'required_from': '2027-02-01'})
        self.assertIn('Lo importante hoy', html)
        self.assertEqual(html.count('↓ 35 €'), 1)
        self.assertIn('21%', html)
        self.assertIn('Festivos NCIA: planificar antes', html)
        self.assertIn('Fin de semana sáb. 27/03', html)
        self.assertIn('Fin de semana sáb. 24/04', html)
        self.assertIn('Cierre navideño', html)

    def test_old_radar_quotes_never_presented_as_checked_today(self):
        html = render_priority_digest(
            date(2026, 10, 26), [], [], {},
            tracking=[dict(weekend=date(2027, 3, 27), best_price=180,
                           checked_at='2026-10-20',
                           outbound=date(2027, 3, 26), inbound=date(2027, 3, 29))],
            family_plan={'required_from': '2027-02-01'})
        self.assertIn('180 € · observado 2026-10-20', html)
        self.assertNotIn('180 € · comprobado hoy', html)


if __name__ == '__main__':
    unittest.main()
