"""Regression tests for the family email's readability and TT estimates."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src import report, store
from src.budget import trip_work_dates
from src.family import build_coverage, join_opportunities, render_coverage


def sample_trip(out, inc, dep='17:00', arrival='19:00',
                ret='17:50', ret_arr='20:20', price=150):
    outbound = dict(origin='AMS', destination='BCN', airline='Vueling', price=80,
                    outbound_departure=dep, outbound_arrival=arrival,
                    source_url='https://example.org/ams')
    inbound = dict(origin='BCN', destination='RTM', airline='Transavia', price=70,
                   outbound_departure=ret, outbound_arrival=ret_arr,
                   source_url='https://example.org/rtm')
    return dict(outbound=out, inbound=inc, total=price,
                out=[outbound], inc=[inbound])


class TravelTimeTests(unittest.TestCase):
    def test_monday_early_arrival_does_not_consume_tt(self):
        thu, mon = date(2027, 2, 4), date(2027, 2, 8)
        evening = sample_trip(thu, mon)
        morning = sample_trip(thu, mon, ret='06:00', ret_arr='08:30')
        self.assertEqual(trip_work_dates(evening)[0],
                         [date(2027, 2, 5), date(2027, 2, 8)])
        self.assertEqual(trip_work_dates(morning)[0], [date(2027, 2, 5)])
        self.assertIn('Regreso con llegada', trip_work_dates(morning)[1][0])

    def test_friday_early_departure_marks_friday_tt_or_partial_leave(self):
        t = sample_trip(date(2027, 2, 5), date(2027, 2, 8),
                        dep='07:00', arrival='09:20')
        self.assertEqual(trip_work_dates(t)[0],
                         [date(2027, 2, 5), date(2027, 2, 8)])
        self.assertIn('permiso parcial', trip_work_dates(t)[1][0])

    def test_join_compares_tt_between_one_stay_and_two_returns(self):
        a = sample_trip(date(2027, 2, 4), date(2027, 2, 7), price=160)
        b = sample_trip(date(2027, 2, 11), date(2027, 2, 14), price=160)
        joined = sample_trip(date(2027, 2, 4), date(2027, 2, 14), price=220)
        from src.family import build_coverage
        weeks = build_coverage([a, b, joined], {})
        options = join_opportunities(weeks, [a, b, joined])
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]['separate_tt'], 2)
        self.assertEqual(options[0]['joined_tt'], 6)
        self.assertEqual(options[0]['extra_workdays'], 4)
        html = render_coverage(weeks, options)
        self.assertIn('dos viajes 2 días → estancia unida 6 días', html)
        self.assertIn('+4 TT adicionales', html)

    def test_email_card_has_flight_times_and_tt_dates_not_monthly_budget(self):
        a = sample_trip(date(2027, 2, 4), date(2027, 2, 8))
        b = sample_trip(date(2027, 2, 5), date(2027, 2, 8),
                        dep='07:00', arrival='09:20', price=175)
        coverage = build_coverage([a, b], {}, {'required_from': '2027-02-01'})
        html = render_coverage(coverage, [])
        self.assertIn('Opción más barata', html)
        self.assertIn('17:00–19:00', html)
        self.assertIn('VUELTA', html.upper())
        self.assertIn('TT/permiso a prever: vie. 05/02, lun. 08/02', html)
        self.assertIn('Alternativa', html)
        self.assertNotIn('Presupuesto orientativo por mes', html)


class BudgetRadarTests(unittest.TestCase):
    def test_month_denominator_includes_weekends_without_quote(self):
        weeks = [date(2027, 4, d) for d in (3, 10, 17, 24)]
        tracking = [dict(weekend=w, best_price=140 if i == 0 else None,
                         checked_at='2026-10-21' if i == 0 else None,
                         outbound=None, inbound=None)
                    for i, w in enumerate(weeks)]
        html = report._monthly_budget(tracking, [], {'required_from': '2027-02-01'})
        self.assertIn('1/4 fines de semana con precio', html)
        self.assertIn('140 €', html)
        self.assertIn('PARCIAL', html)
        self.assertNotIn('4/4 fines de semana', html)
        radar = report._horizon_radar(tracking)
        self.assertIn('ABR.', radar)
        self.assertEqual(radar.count('Fin de semana sáb.'), 4)
        self.assertIn('Todavía sin consultar', radar)

    def test_weekly_radar_does_not_include_joined_two_weekend_price(self):
        saturday = date(2027, 3, 13)
        with tempfile.TemporaryDirectory() as folder, patch.object(
            store, 'DB_PATH', Path(folder) / 'prices.db'
        ):
            store.init_db()
            store.save_weekend_snapshot('2026-10-21', date(2027, 3, 12),
                                        date(2027, 3, 15), 100, 116, 216)
            store.save_weekend_snapshot('2026-10-21', date(2027, 3, 12),
                                        date(2027, 3, 22), 50, 90, 140)
            quoted = store.get_horizon_tracking([saturday])[0]
            self.assertEqual(quoted['best_price'], 216)
            self.assertEqual(quoted['inbound'], date(2027, 3, 15))

    def test_distant_week_does_not_repeat_in_detailed_first_block(self):
        near = sample_trip(date(2027, 2, 4), date(2027, 2, 7))
        far = sample_trip(date(2027, 4, 8), date(2027, 4, 11))
        radar = [
            dict(weekend=date(2027, 2, 6), best_price=150,
                 checked_at='2026-10-21', outbound=near['outbound'],
                 inbound=near['inbound']),
            dict(weekend=date(2027, 4, 10), best_price=140,
                 checked_at='2026-10-21', outbound=far['outbound'],
                 inbound=far['inbound']),
        ]
        with patch.object(report, 'get_weekend_history', return_value=[]), patch.object(
            report, 'get_latest_learning_opportunities', return_value=[]
        ):
            html = report.build_html_report(
                date(2026, 10, 21), [], pairs=[(near['outbound'], near['inbound']),
                                                 (far['outbound'], far['inbound'])],
                family_plan={'required_from': '2027-02-01'},
                horizon_tracking=radar, daily_saturdays=[date(2027, 2, 6)],
            )
        self.assertEqual(html.count('Opción más barata'), 0)
        self.assertIn('Radar de precios a largo plazo', html)
        self.assertIn('Presupuesto orientativo por mes', html)
        self.assertIn('1/1 fines de semana con precio', html)
        self.assertIn('Fin de semana sáb. 10/04', html)


if __name__ == '__main__':
    unittest.main()
