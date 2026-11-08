"""Contextual price learning must avoid pseudo-history and future-data leakage."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from src.decisions import FILTER_VERSION
from src.market_learning import (comparable_price, booking_window_evidence,
                                 market_movement, lead_bucket)
from src import store
from src.report import _market_learning_panel


def quote(on, outbound, price, *, holiday=False, complete=True,
          inbound=None, version=FILTER_VERSION):
    back = inbound or outbound + timedelta(days=3)
    return dict(run_date=str(on), outbound=str(outbound), inbound=str(back),
                price=price, coverage_complete=complete, holiday=holiday,
                filter_version=version)


class MarketEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.as_of = date(2027, 3, 10)
        self.out = date(2027, 6, 4)  # Friday
        self.back = date(2027, 6, 7)  # Monday
        self.other_fridays = [date(2027, 4, 9) + timedelta(days=7*i)
                              for i in range(8)]
        self.peers = [quote(d-timedelta(days=90), d, 160+i*4)
                      for i, d in enumerate(self.other_fridays)]

    def test_independent_weekend_prices_not_raw_daily_row_count(self):
        many_repeats = []
        for p in self.peers:
            for i in range(3):
                row = dict(p)
                row['run_date'] = str(date.fromisoformat(p['run_date']) + timedelta(days=i))
                many_repeats.append(row)
        evidence = comparable_price(self.out, self.back, 140, False,
                                    many_repeats, self.as_of)
        self.assertEqual(evidence['independent_weekends'], 8)
        self.assertTrue(evidence['favourable'])
        self.assertFalse(evidence['seasonally_matched'])
        self.assertLess(evidence['vs_reference_pct'], 0)

    def test_fewer_than_six_independent_weekends_gives_no_judgement(self):
        self.assertIsNone(comparable_price(self.out, self.back, 100, False,
                                           self.peers[:5], self.as_of))

    def test_future_prices_own_itinerary_wrong_pattern_and_holidays_excluded(self):
        rows = list(self.peers)
        rows.extend(quote(self.as_of+timedelta(days=1), d, 1)
                    for d in self.other_fridays)
        rows.extend(quote(d-timedelta(days=90), d, 1, holiday=True)
                    for d in self.other_fridays)
        rows.append(quote(self.out-timedelta(days=90), self.out, 1))
        actual = comparable_price(self.out, self.back, 140, False,
                                  rows, self.as_of)
        baseline = comparable_price(self.out, self.back, 140, False,
                                    self.peers, self.as_of)
        self.assertEqual(actual, baseline)

    def test_matured_cohorts_only_multiple_lead_intervals(self):
        cutoff = date(2027, 8, 1)
        departures = [date(2027, 1, 1) + timedelta(days=7*i)
                      for i in range(8)]
        rows = []
        for out in departures:
            rows += [quote(out-timedelta(days=90), out, 100),
                     quote(out-timedelta(days=45), out, 150),
                     quote(out-timedelta(days=7), out, 200)]
        result = booking_window_evidence(rows, cutoff)
        self.assertEqual(result['status'], 'observational')
        self.assertEqual(result['mature_trips'], 8)
        self.assertEqual(result['bands'][0]['range_days'], (84, 111))
        self.assertEqual(result['bands'][0]['median_above_observed_best_pct'], 0)
        self.assertEqual(result['bands'][0]['journeys'], 8)
        self.assertEqual(booking_window_evidence(rows[:7*3], cutoff)['status'], 'insufficient')
        self.assertEqual(booking_window_evidence(rows, date(2026, 12, 1))['status'],
                         'insufficient')

    def test_mature_booking_horizon_must_match_season_pattern_and_holidays(self):
        as_of = date(2027, 8, 1)
        departures = [date(2027, 1, 1) + timedelta(days=7*i)
                      for i in range(8)]
        rows = []
        for departure in departures:
            rows.extend([
                quote(departure-timedelta(days=90), departure, 100),
                quote(departure-timedelta(days=45), departure, 150),
                quote(departure-timedelta(days=7), departure, 190),
            ])
        near_january = booking_window_evidence(
            rows, as_of, travel_month=1, weekday_pattern=(4,0), holiday=False)
        self.assertEqual(near_january['status'], 'observational')
        not_autumn = booking_window_evidence(
            rows, as_of, travel_month=10, weekday_pattern=(4,0), holiday=False)
        self.assertEqual(not_autumn['status'], 'insufficient')
        not_thursday = booking_window_evidence(
            rows, as_of, travel_month=1, weekday_pattern=(3,0), holiday=False)
        self.assertEqual(not_thursday['status'], 'insufficient')
        not_holiday = booking_window_evidence(
            rows, as_of, travel_month=1, weekday_pattern=(4,0), holiday=True)
        self.assertEqual(not_holiday['status'], 'insufficient')

    def test_market_direction_only_uses_same_trip_pairs(self):
        today = date(2027, 3, 10)
        dates = [date(2027, 5, 7) + timedelta(days=7*i) for i in range(6)]
        records = []
        for d in dates:
            records.append(quote(today-timedelta(days=8), d, 100))
            records.append(quote(today-timedelta(days=2), d, 110))
        result = market_movement(records, today)
        self.assertEqual(result['weekends'], 6)
        self.assertEqual(result['median_change_pct'], 10)

    def test_report_explicitly_says_timing_not_ready(self):
        week = dict(weekend=date(2027, 6, 5), state='unknown',
                    best=dict(outbound=self.out, inbound=self.back, total=140))
        html = _market_learning_panel(self.as_of, [week], self.peers)
        self.assertIn('PRECIO COMPETITIVO EN LA MUESTRA', html)
        self.assertIn('Antelación óptima: todavía no calibrada', html)
        self.assertIn('estacionalidad no calibrada', html)


class LearningStoreTests(unittest.TestCase):
    def test_only_prior_complete_versioned_fares_are_exported(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            store, 'DB_PATH', Path(directory) / 'prices.db'
        ):
            store.init_db()
            with store.get_conn() as conn:
                for quoted, amount, complete, version in [
                    ('2026-11-01', 100, 1, FILTER_VERSION),
                    ('2026-11-08', 10, 1, FILTER_VERSION),
                    ('2026-11-03', 90, 0, FILTER_VERSION),
                    ('2026-11-04', 50, 1, 'old'),
                ]:
                    conn.execute(
                        'INSERT OR REPLACE INTO booking_decisions '
                        'VALUES (?,?,?,?,?,?,?,?)',
                        (quoted, version, '2027-03-05', '2027-03-08',
                         amount, complete, 0, '{}'),
                    )
            data = store.get_market_learning_history(date(2026, 11, 8))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['price'], 100)
            self.assertEqual(data[0]['run_date'], '2026-11-01')


if __name__ == '__main__':
    unittest.main()
