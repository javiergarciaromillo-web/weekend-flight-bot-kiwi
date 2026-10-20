import tempfile
import json
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.scrapers import google_flights_ui as scraper
from src import report, store


class SearchTests(unittest.TestCase):
    def test_shared_legs_are_queried_once_and_rebound(self):
        thu, fri = date(2026, 10, 22), date(2026, 10, 23)
        sun, mon = date(2026, 10, 25), date(2026, 10, 26)
        pairs = [(thu, sun), (thu, mon), (fri, mon)]
        def search(page, origin, destination, leg_date, outbound, inbound, **kwargs):
            return [dict(origin=origin, destination=destination, leg_date=leg_date,
                         outbound=outbound, inbound=inbound, price=100,
                         leg_type='outbound' if destination == 'BCN' else 'inbound',
                         outbound_departure='5:00 PM')]
        with patch.object(scraper, 'sync_playwright', return_value=MagicMock()), patch.object(scraper, '_run_one_leg_search', side_effect=search) as call:
            statuses = {}
            rows = scraper.search_google_flights(pairs, diagnostics=statuses)
        self.assertEqual(call.call_count, 8)
        self.assertEqual(len(rows), 12)
        for pair in pairs:
            self.assertEqual(sum((r['outbound'], r['inbound']) == pair for r in rows), 4)
        self.assertEqual(set(statuses.values()), {'ok'})

    def test_learning_searches_all_patterns_in_one_batch(self):
        from src import learning
        with patch.object(learning, 'search_google_flights', return_value=[]) as search, patch.object(learning, 'save_learning_snapshot') as save:
            learning.run_learning_sampling(date(2026, 10, 10))
        self.assertEqual(search.call_count, 1)
        self.assertGreaterEqual(save.call_count, 21)  # holiday patterns supplement baseline
        self.assertTrue(search.call_args.kwargs['allow_klm_from_ams'])

    def test_failed_search_is_reused_and_identified(self):
        pairs = [(date(2026, 10, 22), date(2026, 10, 25)), (date(2026, 10, 22), date(2026, 10, 26))]
        with patch.object(scraper, 'sync_playwright', return_value=MagicMock()), patch.object(scraper, '_run_one_leg_search', side_effect=RuntimeError('unavailable')) as call:
            statuses = {}
            rows = scraper.search_google_flights(pairs, diagnostics=statuses)
        self.assertEqual(rows, [])
        self.assertEqual(call.call_count, 18)
        self.assertEqual(set(statuses.values()), {'failed'})

    def test_retry_recovers_every_pair_and_does_not_repeat_empty_results(self):
        pairs = [(date(2026, 10, 22), date(2026, 10, 25)),
                 (date(2026, 10, 21), date(2026, 10, 25))]
        attempts = {}
        def query(page, origin, destination, day, outbound, inbound, **kwargs):
            key = (origin, destination, day)
            attempts[key] = attempts.get(key, 0) + 1
            if origin == 'BCN' and destination == 'AMS':
                if attempts[key] == 1:
                    raise RuntimeError('Google temporary error')
                return [dict(origin=origin, destination=destination, leg_date=day,
                             outbound=outbound, inbound=inbound, price=100, leg_type='inbound',
                             outbound_departure='5:00 PM', outbound_arrival='7:00 PM')]
            return []
        with patch.object(scraper, 'sync_playwright', return_value=MagicMock()), patch.object(scraper, '_run_one_leg_search', side_effect=query):
            statuses = {}
            rows = scraper.search_google_flights(pairs, diagnostics=statuses)
        self.assertEqual(attempts[('BCN', 'AMS', pairs[0][1])], 2)
        self.assertTrue(all(n == 1 for key, n in attempts.items() if key != ('BCN', 'AMS', pairs[0][1])))
        self.assertEqual(len(rows), 2)
        self.assertEqual({(r['outbound'], r['inbound']) for r in rows}, set(pairs))
        self.assertNotIn('failed', statuses.values())

    def test_learning_recovery_allows_klm_only_via_ams_and_deduplicates(self):
        pairs = [(date(2026, 11, 12), date(2026, 11, 15)),
                 (date(2026, 11, 12), date(2026, 11, 16))]
        key = ('AMS', 'BCN', pairs[0][0])
        diagnostics = {key: 'failed'}
        base = dict(origin='AMS', destination='BCN', leg_date=key[2], leg_type='outbound',
                    outbound=pairs[0][0], inbound=pairs[0][1],
                    outbound_departure='5:00 PM', outbound_arrival='7:00 PM')
        vuelos = [dict(base, airline='Vueling', price=80), dict(base, airline='KLM', price=60)]
        rows = scraper.recover_failed_queries(pairs, [], diagnostics, vuelos + vuelos, {key: 'ok'})
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['airline'] for r in rows}, {'Vueling', 'KLM'})
        self.assertEqual(diagnostics[key], 'ok')
        rtm_key = ('RTM', 'BCN', key[2])
        diagnostics = {rtm_key: 'failed'}
        self.assertEqual(scraper.recover_failed_queries(pairs, [], diagnostics,
                         [dict(vuelos[1], origin='RTM')], {rtm_key: 'ok'}), [])
        self.assertEqual(diagnostics[rtm_key], 'filtered_empty')

    def test_weekly_time_boundaries_and_early_monday_klm(self):
        thu, mon = date(2026, 10, 22), date(2026, 10, 26)
        self.assertFalse(scraper._departure_ok(thu, '4:59 PM', 'outbound'))
        self.assertTrue(scraper._departure_ok(thu, '5:00 PM', 'outbound'))
        for departure, arrival, expected in [('6:00 AM', '8:59 AM', True),
                                             ('6:00 AM', '9:00 AM', False),
                                             ('5:00 PM', '7:00 PM', True),
                                             ('11:20 PM', '1:20 AM+1', True)]:
            self.assertEqual(scraper._departure_ok(mon, departure, 'inbound', arrival),
                             expected, (departure, arrival))
        self.assertFalse(scraper._departure_ok(mon, '7:59 AM', 'inbound'))
        row = dict(airline='KLM', departure_time='6:00 AM', arrival_time='8:30 AM',
                   stops='Nonstop', price=75)
        self.assertEqual(scraper._filter_relevant_flights([row], mon, 'BCN', 'AMS'), [row])
        self.assertEqual(scraper._filter_relevant_flights([row], mon, 'BCN', 'RTM'), [])
        self.assertEqual(scraper._filter_relevant_flights([dict(row, departure_time='10:00 AM')],
                                                        mon, 'BCN', 'AMS'), [])

    def test_friday_sunday_pairs_are_removed_everywhere(self):
        from src.planner import generate_weekend_pairs, allowed_pair
        from src.learning import _build_pairs_for_offset
        pairs = generate_weekend_pairs(date(2026, 10, 19), 1)
        self.assertEqual([(o.weekday(), i.weekday()) for o, i in pairs], [(3, 6), (3, 0), (4, 0)])
        self.assertEqual([name for name, _, _ in _build_pairs_for_offset(date(2026, 10, 12), 30)],
                         ['THU-SUN', 'THU-MON', 'FRI-MON'])
        excluded = (date(2026, 10, 23), date(2026, 10, 25))
        with patch.object(scraper, 'sync_playwright', return_value=MagicMock()), \
                patch.object(scraper, '_run_one_leg_search') as query:
            self.assertEqual(scraper.search_google_flights([excluded]), [])
        query.assert_not_called()
        self.assertTrue(allowed_pair(date(2026, 12, 25), date(2027, 1, 3)))

    def test_learning_recovery_preserves_trip_departure_constraints(self):
        pairs = [(date(2026, 10, 30), date(2026, 11, 2))]
        key = ('AMS', 'BCN', pairs[0][0])
        row = dict(origin='AMS', destination='BCN', leg_date=key[2], airline='Vueling', price=80,
                   outbound=pairs[0][0], inbound=pairs[0][1], leg_type='outbound',
                   outbound_departure='9:00 AM', outbound_arrival='11:00 AM')
        diagnostics = {key: 'failed'}
        self.assertEqual(scraper.recover_failed_queries(pairs, [], diagnostics, [row], {key: 'ok'}), [])
        self.assertEqual(diagnostics[key], 'ok')

    def test_parser_does_not_borrow_next_flight_price(self):
        text = '\n'.join(['5:00 PM', '-', '7:00 PM', 'Vueling', '2 hr', 'AMS-BCN', 'Nonstop',
                          '6:00 PM', '-', '8:00 PM', 'Transavia', '2 hr', 'AMS-BCN', 'Nonstop', '€100'])
        rows = scraper._extract_flight_blocks(text, 'AMS', 'BCN')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['airline'], 'Transavia')

    def test_connecting_flights_are_results_but_do_not_match_filters(self):
        text = '\n'.join(['7:05 PM', '-', '11:00 AM+1', 'Air Algerie', '15 hr 55 min',
                          'BCN–RTM', '1 stop', '€369', '8:00 AM', '-', '5:55 PM',
                          'Iberia, British AirwaysOperated by BA Cityflyer', '9 hr 55 min',
                          'BCN–RTM', '2 stops', '€1199'])
        rows = scraper._extract_flight_blocks(text, 'BCN', 'RTM')
        self.assertEqual(len(rows), 2)
        self.assertEqual(scraper._filter_relevant_flights(rows, date(2026, 10, 26), 'BCN', 'RTM'), [])


class ReportTests(unittest.TestCase):
    def test_removed_pattern_and_incompatible_history_are_not_reported(self):
        pair = (date(2026, 10, 22), date(2026, 10, 25))
        removed = (date(2026, 10, 23), date(2026, 10, 25))
        rows = [dict(outbound=pair[0], inbound=pair[1], origin='AMS' if leg == 'outbound' else 'BCN',
                     destination='BCN' if leg == 'outbound' else 'AMS', leg_type=leg, airline='KLM', price=100,
                     outbound_departure='5:00 PM', outbound_arrival='7:00 PM', source_url='https://example.com')
                for leg in ['outbound', 'inbound']]
        history = [dict(run_date='2026-10-11', best_combo=50),
                   dict(run_date='2026-10-12', best_combo=210)]
        old_opportunity = dict(run_date='2026-10-13', outbound=str(removed[0]), inbound=str(removed[1]), best_combo=50)
        with patch.object(report, 'get_weekend_history', return_value=history), \
                patch.object(report, 'get_latest_learning_opportunities', return_value=[old_opportunity]):
            html = report.build_html_report(date(2026, 10, 20), rows, pairs=[pair, removed])
        self.assertNotIn('-10 €', html)
        self.assertNotIn('+150 €', html)
        self.assertNotIn('23 oct.', html)
        self.assertNotIn('Precios a más largo plazo', html)

    def test_no_buy_signal_for_single_observation(self):
        self.assertEqual(report._trend_label(142, 142, 1), 'Histórico insuficiente')
        self.assertEqual(report._trend_label(142, 142, 5), 'Cerca del mínimo observado')
        self.assertEqual(report._time('11:20 PM'), '23:20')
        self.assertEqual(report._time('12:15 AM+1'), '00:15 +1')

    def test_missing_weekends_and_failures_are_visible(self):
        pair = (date(2026, 10, 22), date(2026, 10, 25))
        diagnostics = {('AMS', 'BCN', pair[0]): 'failed'}
        with patch.object(report, 'get_weekend_history', return_value=[]), patch.object(report, 'get_latest_learning_opportunities', return_value=[]):
            html = report.build_html_report(date(2026, 10, 10), [], pairs=[pair], diagnostics=diagnostics)
        self.assertIn('cobertura parcial', html)
        self.assertIn('disponibilidad sin verificar', html)
        self.assertIn('22 oct.', html)

    def test_full_report_stays_compact_and_escapes_provider_values(self):
        from src.planner import generate_weekend_pairs
        pairs = generate_weekend_pairs(date(2026, 10, 10), 7, 1)
        rows = [dict(outbound=o, inbound=i, origin='AMS' if leg == 'outbound' else 'BCN',
                     destination='BCN' if leg == 'outbound' else 'AMS', leg_type=leg,
                     airline='<bad>', price=100, outbound_departure='5:00 PM', outbound_arrival='7:00 PM',
                     source_url='https://example.com') for o, i in pairs for leg in ['outbound', 'inbound']]
        with patch.object(report, 'get_weekend_history', return_value=[]), patch.object(report, 'get_latest_learning_opportunities', return_value=[]):
            html = report.build_html_report(date(2026, 10, 10), rows, pairs=pairs)
        self.assertLess(len(html.encode()), 80000)
        self.assertNotIn('<bad>', html)
        self.assertIn('&lt;bad&gt;', html)
        self.assertNotIn('Buy now', html)

    def test_pairs_appear_once_in_comparison_and_missing_route_is_listed(self):
        pair = (date(2027, 3, 25), date(2027, 3, 29))
        diagnostics = {('BCN', 'RTM', pair[1]): 'failed'}
        rows = [dict(outbound=pair[0], inbound=pair[1], origin='AMS' if leg == 'outbound' else 'BCN',
                     destination='BCN' if leg == 'outbound' else 'AMS', leg_type=leg, airline='Vueling',
                     price=100, outbound_departure='5:00 PM', outbound_arrival='7:00 PM',
                     source_url='https://example.com') for leg in ['outbound', 'inbound']]
        with patch.object(report, 'get_weekend_history', return_value=[]), patch.object(report, 'get_latest_learning_opportunities', return_value=[]):
            html = report.build_html_report(date(2026, 10, 11), rows, pairs=[pair], diagnostics=diagnostics)
        self.assertEqual(html.count('<b>Ida</b>'), 1)
        self.assertEqual(html.count('<b>Vuelta</b>'), 1)
        self.assertIn('BCN→RTM', html)
        self.assertIn('Estancias con festivos NCIA', html)
        self.assertNotIn('Histórico insuficiente', html)


class HolidayTests(unittest.TestCase):
    def test_easter_and_christmas_bridges(self):
        from src.holidays import generate_holiday_pairs, workdays_affected, HOLIDAYS
        pairs = generate_holiday_pairs(date(2026, 10, 10))
        self.assertIn((date(2027, 3, 25), date(2027, 3, 29)), pairs)
        self.assertIn((date(2026, 12, 22), date(2027, 1, 3)), pairs)
        self.assertEqual(workdays_affected(date(2027, 3, 25), date(2027, 3, 29)), 0)
        self.assertTrue(all(workdays_affected(*pair) <= 5 for pair in pairs))
        self.assertNotIn(date(2027, 5, 5), HOLIDAYS)
        self.assertIn(date(2027, 5, 3), HOLIDAYS)

    def test_holiday_and_extended_return_times(self):
        self.assertTrue(scraper._departure_ok(date(2027, 3, 29), '8:00 AM', 'inbound'))
        self.assertTrue(scraper._departure_ok(date(2027, 3, 29), '9:00 AM', 'inbound'))
        self.assertTrue(scraper._departure_ok(date(2027, 3, 30), '6:00 AM', 'inbound', '8:30 AM'))
        self.assertFalse(scraper._departure_ok(date(2027, 3, 30), '6:00 AM', 'inbound', '9:00 AM'))
        self.assertFalse(scraper._departure_ok(date(2027, 3, 25), '9:00 AM', 'outbound'))


class BudgetTests(unittest.TestCase):
    def test_allowances_are_not_claimed_as_remaining(self):
        from src.budget import estimate_allocation
        allocation = estimate_allocation(date(2027, 3, 25), date(2027, 3, 31))
        self.assertEqual(allocation[2027]['remote'], 2)
        self.assertEqual(allocation[2027]['leave'], 0)
        self.assertTrue(allocation[2027]['verified'])
        unknown = estimate_allocation(date(2026, 10, 29), date(2026, 11, 4))
        self.assertFalse(unknown[2026]['verified'])
        used = estimate_allocation(date(2027, 3, 25), date(2027, 3, 31), {2027: {'remote': 1, 'leave': 1}})
        self.assertEqual(used[2027]['remote'], 1)
        self.assertEqual(used[2027]['leave'], 1)
        self.assertEqual(used[2027]['uncovered'], 0)

    def test_years_have_separate_budgets(self):
        from src.budget import estimate_allocation
        allocation = estimate_allocation(date(2026, 12, 20), date(2027, 1, 5))
        self.assertEqual(set(allocation), {2026, 2027})
        self.assertEqual(allocation[2026]['required'], 2)
        self.assertEqual(allocation[2027]['required'], 2)


class StoreTests(unittest.TestCase):
    def test_rerun_replaces_daily_snapshot(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(store, 'DB_PATH', Path(folder) / 'prices.db'):
            store.init_db()
            for price in [100, 90]:
                store.save_weekend_snapshot('2026-10-10', '2026-10-22', '2026-10-25', price, 50, price+50)
                store.save_learning_snapshot('2026-10-10', '30_THU-SUN', '2026-11-12', '2026-11-15', 33, 'THU-SUN', price, 50, price+50)
            history = store.get_weekend_history('2026-10-22', '2026-10-25')
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]['best_combo'], 140)
            self.assertEqual(len(store.get_latest_learning_opportunities()), 1)

    def test_main_saves_prices_and_traceability_before_email(self):
        from src import main as app
        pair = (date(2027, 2, 4), date(2027, 2, 7))
        key = ('AMS', 'BCN', pair[0])
        saturday = date(2027, 2, 6)
        out = dict(origin='AMS', destination='BCN', leg_date=pair[0],
                   airline='Vueling', price=80,
                   outbound=pair[0], inbound=pair[1], leg_type='outbound',
                   outbound_departure='5:00 PM', outbound_arrival='7:00 PM')
        inc = dict(out, origin='BCN', destination='AMS',
                   leg_date=pair[1], leg_type='inbound', price=50)
        def operational(pairs, diagnostics):
            diagnostics[key] = 'ok'
            return [out, inc]
        with (tempfile.TemporaryDirectory() as folder, patch.object(app, 'init_db'), 
                patch.object(app, 'save_flight_observations'), 
                patch.object(app, 'record_booking_decisions', return_value={}), 
                patch.object(app, 'monitoring_plan',
                             return_value=([pair], [saturday], [saturday], [saturday])), 
                patch.object(app, 'search_google_flights', side_effect=operational) as scraper, 
                patch.object(app, 'save_sampled_weekends') as learning, 
                patch.object(app, 'save_weekend_snapshot') as snapshot, 
                patch.object(app, 'get_horizon_tracking', return_value=[]) as radar, 
                patch.object(app, 'build_html_report',
                             return_value='<html>monitoring</html>') as build, 
                patch.object(app, 'get_latest_learning_opportunities', return_value=[]), 
                patch.object(app, 'send_email_html') as email):
            previous = os.getcwd()
            try:
                os.chdir(folder)
                app.main()
                payload = json.loads(Path('data/report/report.json').read_text())
            finally:
                os.chdir(previous)
        scraper.assert_called_once()
        self.assertEqual(snapshot.call_args.kwargs['best_combo'], 130)
        learning.assert_called_once()
        radar.assert_called_once_with([saturday])
        self.assertEqual(build.call_args.kwargs['diagnostics'][key], 'ok')
        self.assertEqual(payload['queries'][0]['status'], 'ok')
        self.assertEqual(len(payload['flights']), 2)
        self.assertEqual(payload['monitoring_days'], 300)
        email.assert_called_once()


if __name__ == '__main__':
    unittest.main()
