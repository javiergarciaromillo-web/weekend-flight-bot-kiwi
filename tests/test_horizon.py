"""Twelve-month monitoring policy and truthful dated price radar."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from src.horizon import HORIZON_DAYS, monitoring_plan, active_promotions
from src import store
from src.learning import save_sampled_weekends
from src.report import _horizon_radar


class HorizonTests(unittest.TestCase):
    def test_first_eight_family_weekends_daily_before_start(self):
        today, family = date(2026, 10, 20), date(2027, 2, 1)
        pairs, visible, daily, sampled = monitoring_plan(today, family)
        self.assertEqual(HORIZON_DAYS, 365)
        self.assertEqual(visible[0], date(2027, 2, 6))
        self.assertEqual(len(daily), 8)
        self.assertTrue(set(daily).issubset(sampled))
        self.assertTrue(all(out >= family for out, inc in pairs))
        self.assertTrue(all(out < inc for out, inc in pairs))
        self.assertIn((date(2027, 2, 4), date(2027, 2, 7)), pairs)
        self.assertTrue(visible[-1] <= today + timedelta(days=365))

    def test_newly_visible_months_keep_staggered_checks_and_explicit_exclusions(self):
        run = date(2026, 11, 24)
        family = date(2027, 2, 1)
        november = date(2027, 11, 6)
        selections = []
        for offset in range(7):
            pairs, visible, daily, due = monitoring_plan(run + timedelta(days=offset), family)
            self.assertIn(november, visible)
            self.assertNotIn(november, daily)
            self.assertTrue(all(sat <= run + timedelta(days=offset + HORIZON_DAYS)
                                for sat in visible))
            selections.append(set(due))
        self.assertEqual(sum(november in due for due in selections), 2)
        plan = {'weekends': {'2027-11-06': 'holiday_break'}}
        _, visible, _, _ = monitoring_plan(run, family, plan)
        self.assertNotIn(november, visible)

    def test_black_friday_sampling_expires_and_respects_exclusions(self):
        family = date(2027, 2, 1)
        september = date(2027, 9, 4)
        march = date(2027, 3, 20)
        excluded = date(2027, 8, 7)
        plan = {'weekends': {excluded.isoformat(): 'vacation'}}
        for day in (27, 28, 29):
            pairs, visible, daily, due = monitoring_plan(date(2026, 11, day), family, plan)
            self.assertTrue(all(s in due for s in visible if s <= date(2027, 9, 30)))
            self.assertNotIn(september, daily)
            self.assertIn(september, due)
            self.assertNotIn(excluded, visible)
            self.assertTrue(all(not (out <= excluded <= inc) for out, inc in pairs))
        for day in (date(2026, 11, 30), date(2026, 12, 1)):
            _, visible, _, due = monitoring_plan(day, family, plan)
            self.assertIn(march, due)
            self.assertTrue(all(s in due for s in visible if s <= date(2027, 3, 31)))
            self.assertEqual([name for name, _ in active_promotions(day)],
                             ['Transavia Black Friday'])
        self.assertEqual(active_promotions(date(2026, 12, 2)), [])
        self.assertEqual(active_promotions(date(2027, 11, 27)), [])
        self.assertEqual(sum(september in monitoring_plan(date(2026, 12, 2)
                             + timedelta(days=i), family)[3] for i in range(7)), 2)

    def test_regular_long_range_cadence_each_calendar_week(self):
        # Fix the target weekends and vary only the run weekday within one week.
        start = date(2027, 1, 4)  # Monday
        family = date(2027, 2, 1)
        near = date(2027, 2, 6)
        mid = date(2027, 4, 17)   # Ordinary week >8 and <20 weeks away
        far = date(2027, 8, 7)    # >20 weeks away, inside 365d
        results = []
        for offset in range(7):
            run_day = start + timedelta(days=offset)
            _, visible, daily, selected = monitoring_plan(run_day, family)
            self.assertIn(mid, visible)
            self.assertIn(far, visible)
            self.assertIn(near, daily)
            self.assertIn(near, selected)
            results.append(set(selected))
        self.assertEqual(sum(mid in selection for selection in results), 3)
        self.assertEqual(sum(far in selection for selection in results), 2)

    def test_snapshot_history_preserves_last_actual_check_and_empty_quote(self):
        saturday = date(2027, 6, 19)
        outbound, inbound = date(2027, 6, 17), date(2027, 6, 20)
        with tempfile.TemporaryDirectory() as folder, patch.object(
            store, 'DB_PATH', Path(folder) / 'quotes.db'
        ):
            store.init_db()
            store.save_weekend_snapshot('2026-10-20', outbound, inbound, 80, 70, 150)
            observations = store.get_horizon_tracking([saturday])
            self.assertEqual(observations[0]['best_price'], 150)
            self.assertEqual(observations[0]['checked_at'], '2026-10-20')
            html = _horizon_radar(observations)
            self.assertIn('visto el 2026-10-20', html)
            store.save_weekend_snapshot('2026-10-23', outbound, inbound, None, None, None)
            current = store.get_horizon_tracking([saturday])
            self.assertIsNone(current[0]['best_price'])
            self.assertEqual(current[0]['checked_at'], '2026-10-23')
            self.assertIn('Sin precio completo verificado', _horizon_radar(current))

    def test_sample_learning_from_existing_rows_without_scraping(self):
        from src import learning
        outbound, inbound = date(2027, 6, 17), date(2027, 6, 20)
        pair = (outbound, inbound)
        out = dict(outbound=outbound, inbound=inbound, leg_type='outbound',
                   origin='AMS', destination='BCN', airline='KLM',
                   outbound_departure='17:00', outbound_arrival='19:00',
                   source_url='https://example.org', price=80)
        inc = dict(out, leg_type='inbound', origin='BCN', destination='AMS',
                   outbound_departure='18:00', outbound_arrival='20:00', price=70)
        with patch.object(learning, 'save_learning_snapshot') as save:
            count = save_sampled_weekends(date(2026, 10, 20), [out, inc], [pair])
            self.assertEqual(count, 1)
            self.assertEqual(save.call_args.kwargs['best_combo'], 150)
            self.assertEqual(save.call_args.kwargs['outbound_airline'], 'KLM')
        with patch.object(learning, 'save_learning_snapshot') as save:
            count = save_sampled_weekends(date(2026, 10, 20), [out, inc], [pair],
                                          daily_saturdays=[date(2027, 6, 19)])
            self.assertEqual(count, 0)
            save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
