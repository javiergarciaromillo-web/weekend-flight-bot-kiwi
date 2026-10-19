import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from src import store
from src.decisions import FILTER_VERSION, recommend, backtest


class DecisionTests(unittest.TestCase):
    def test_deadline_and_missing_coverage(self):
        now, departure = date(2026, 11, 1), date(2026, 11, 22)
        self.assertEqual(recommend(now, departure, 200, [])['action'], 'CERRAR DECISIÓN')
        self.assertEqual(recommend(now, departure, 200, [], coverage_complete=False)['action'], 'VERIFICAR')
        self.assertEqual(recommend(now, departure, None, [])['action'], 'VERIFICAR')
        holiday = recommend(now, date(2026, 12, 22), 200, [], holiday=True)
        self.assertEqual(holiday['deadline'], '2026-11-10')
        self.assertEqual(holiday['review_on'], '2026-11-04')
        self.assertEqual(holiday['action'], 'OBSERVAR')

    def test_only_distinct_past_comparable_complete_days_count(self):
        history = [dict(run_date='2026-10-20', price=400, filter_version=FILTER_VERSION, coverage_complete=True)] * 20
        history += [dict(run_date='2026-12-01', price=400, filter_version=FILTER_VERSION, coverage_complete=True)]
        history += [dict(run_date='2026-10-21', price=400, filter_version='old', coverage_complete=True)]
        history += [dict(run_date='2026-10-22', price=400, filter_version=FILTER_VERSION, coverage_complete=False)]
        result = recommend(date(2026, 11, 1), date(2027, 1, 1), 100, history)
        self.assertEqual(result['history_days'], 1)
        self.assertEqual(result['action'], 'OBSERVAR')

    def test_meaningful_discount_requires_seven_prior_days(self):
        history = [dict(run_date=str(date(2026, 10, 20)+timedelta(days=i)), price=200,
                        filter_version=FILTER_VERSION, coverage_complete=True) for i in range(7)]
        result = recommend(date(2026, 11, 1), date(2027, 1, 1), 175, history)
        self.assertEqual(result['action'], 'CONSIDERAR COMPRA')
        self.assertEqual(result['saving_vs_median'], 25)
        self.assertEqual(recommend(date(2026, 11, 1), date(2027, 1, 1), 190, history)['action'], 'ESPERAR CON LÍMITE')

    def test_backtest_future_prices_do_not_change_purchase_date(self):
        rows = [dict(run_date=str(date(2026, 11, 1)+timedelta(days=i)),
                     outbound='2026-11-30', inbound='2026-12-03', price=200,
                     filter_version=FILTER_VERSION, coverage_complete=True) for i in range(29)]
        before = backtest(rows)[0]
        rows[-1]['price'] = 50
        after = backtest(rows)[0]
        self.assertEqual(before['buy_date'], '2026-11-09')
        self.assertEqual(after['buy_date'], before['buy_date'])
        self.assertEqual(after['observed_regret'], 150)
        self.assertEqual(backtest(rows[:10]), [])


class DetailedStoreTests(unittest.TestCase):
    def test_observations_deduplicate_and_reruns_replace_scope(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(store, 'DB_PATH', Path(folder)/'prices.db'):
            store.init_db()
            store.init_db()  # additive migration is idempotent
            row = dict(outbound='2026-12-03', inbound='2026-12-06', leg_type='outbound',
                       origin='RTM', destination='BCN', airline='Transavia',
                       outbound_departure='5:00 PM', outbound_arrival='7:00 PM', price=100)
            key = ('RTM', 'BCN', '2026-12-03')
            store.save_flight_observations('2026-10-19', [row, dict(row, inbound='2026-12-07')], {key:'ok'})
            with store.get_conn() as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM flight_observations').fetchone()[0], 1)
                self.assertEqual(conn.execute('SELECT departure FROM flight_observations').fetchone()[0], '17:00')
            store.save_flight_observations('2026-10-19', [], {key:'failed'})
            with store.get_conn() as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM flight_observations').fetchone()[0], 0)
                self.assertEqual(conn.execute('SELECT status FROM query_observations').fetchone()[0], 'failed')

    def test_decision_roundtrip_and_report(self):
        from src.report import build_html_report
        pair = (date(2026, 12, 3), date(2026, 12, 6))
        rows = [dict(outbound=pair[0], inbound=pair[1], origin='AMS' if leg=='outbound' else 'BCN',
                     destination='BCN' if leg=='outbound' else 'AMS', leg_type=leg, airline='KLM',
                     outbound_departure='17:00', outbound_arrival='19:00', price=100)
                for leg in ['outbound', 'inbound']]
        diagnostics = {(a,'BCN',pair[0]):'ok' for a in ['AMS','RTM']}
        diagnostics.update({('BCN',a,pair[1]):'ok' for a in ['AMS','RTM']})
        with tempfile.TemporaryDirectory() as folder, patch.object(store, 'DB_PATH', Path(folder)/'prices.db'):
            store.init_db()
            decisions = store.record_booking_decisions(date(2026, 10, 19), rows, [pair], diagnostics)
            history = store.get_decision_history(*pair)
            self.assertEqual(history[0]['price'], 200)
            self.assertTrue(history[0]['coverage_complete'])
            html = build_html_report(date(2026, 10, 19), rows, pairs=[pair], diagnostics=diagnostics, decisions=decisions)
            self.assertIn('OBSERVAR', html)
            self.assertIn('2026-11-12', html)
            self.assertIn('noches', html)
            self.assertIn('TT', html)
