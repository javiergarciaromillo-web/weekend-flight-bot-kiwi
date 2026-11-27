import unittest
from datetime import date

from src.promotions import active_campaigns, promotion_signal, render_promotions
from src.decisions import FILTER_VERSION


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.trip = dict(outbound='2027-02-18', inbound='2027-02-21', fare=130,
                         legs={'outbound': [dict(airline='Transavia', origin='RTM', destination='BCN', price=80)],
                               'inbound': [dict(airline='KLM', origin='BCN', destination='AMS', price=50)]})
        self.history = [dict(run_date=f'2026-11-{i:02}', outbound='2027-02-18', inbound='2027-02-21',
                             price=180, coverage_complete=True, filter_version=FILTER_VERSION)
                        for i in (15, 16, 17)]

    def test_route_campaign_and_savings_are_separate(self):
        signal = promotion_signal(self.trip, self.history, date(2026, 11, 27))
        self.assertEqual(signal['attribution'], 'unknown')
        self.assertEqual(signal['campaigns'][0]['legs'][0]['origin'], 'RTM')
        self.assertEqual(signal['saving'], 50)
        self.assertTrue(signal['drop'])
        signal = promotion_signal(self.trip, [], date(2026, 11, 27))
        self.assertFalse(signal['drop'])
        self.assertIsNone(signal['reference'])

    def test_generic_or_private_prime_campaign_never_marks_a_route(self):
        self.trip['legs']['outbound'][0]['airline'] = 'Vueling'
        self.assertIsNone(promotion_signal(self.trip, [], date(2026, 11, 27)))
        self.assertFalse(promotion_signal(self.trip, self.history, date(2026, 11, 27))['campaigns'])

    def test_no_wrong_direction_airport_or_travel_period(self):
        for origin, destination, outbound in [('AMS', 'BCN', '2027-02-18'),
                                               ('BCN', 'RTM', '2027-02-18'),
                                               ('RTM', 'BCN', '2027-05-18')]:
            self.trip['outbound'] = outbound
            self.trip['legs']['outbound'][0].update(origin=origin, destination=destination)
            self.assertIsNone(promotion_signal(self.trip, [], date(2026, 11, 27)))

    def test_expiry_and_observation_date_prevent_future_evidence(self):
        self.assertEqual(active_campaigns('2026-12-02'), [])
        self.assertIsNone(promotion_signal(self.trip, [], date(2026, 12, 2)))
        self.assertIsNone(promotion_signal(self.trip, [], date(2026, 11, 23)))

    def test_baseline_never_uses_future_incomplete_duplicate_or_different_dates(self):
        row = self.history[0]
        polluted = self.history[:2] + [dict(row), dict(row, run_date='2026-11-28'),
                                     dict(row, run_date='2026-11-18', coverage_complete=False),
                                     dict(row, run_date='2026-11-19', filter_version='other'),
                                     dict(row, run_date='2026-11-19', outbound='2027-02-19')]
        signal = promotion_signal(self.trip, polluted, date(2026, 11, 27))
        self.assertEqual(signal['sample_days'], 2)
        self.assertIsNone(signal['reference'])
        self.assertFalse(signal['drop'])

    def test_missing_fare_and_expired_panel(self):
        self.trip['fare'] = None
        self.assertIsNone(promotion_signal(self.trip, self.history, date(2026, 11, 27)))
        self.assertEqual(render_promotions(date(2026, 12, 2), [], []), '')


if __name__ == '__main__':
    unittest.main()
