import json
import tempfile
import unittest
from pathlib import Path
from datetime import date, timedelta
from src.family import build_coverage, join_opportunities, joined_pairs, load_plan, render_coverage
from src.planner import generate_weekend_pairs


def trip(out, inc, price):
    return dict(outbound=out, inbound=inc, total=price)


class FamilyTests(unittest.TestCase):
    def setUp(self):
        self.first = date(2026, 11, 5)
        self.second = self.first + timedelta(days=7)
        self.trips = [trip(self.first, self.first+timedelta(days=3), 200),
                      trip(self.second, self.second+timedelta(days=3), 300),
                      trip(self.first, self.second+timedelta(days=3), 250)]

    def test_every_week_remains_even_if_expensive_or_missing(self):
        self.trips[1]['total'] = None
        coverage = build_coverage(self.trips, {})
        self.assertEqual(len(coverage), 2)
        html = render_coverage(coverage, [])
        self.assertIn('2026-11-14', html)
        self.assertIn('Sin precio completo', html)
        self.assertIn('Reserva sin verificar', html)
        self.assertIn('1/2 fines de semana', html)
        self.assertEqual(join_opportunities(coverage, self.trips), [])

    def test_join_saves_two_legs_and_counts_extra_workdays(self):
        coverage = build_coverage(self.trips, {})
        joins = join_opportunities(coverage, self.trips)
        self.assertEqual(len(joins), 1)
        self.assertEqual(joins[0]['saving'], 250)
        self.assertEqual(joins[0]['extra_workdays'], 4)
        self.assertFalse(joins[0]['allocation'][2026]['verified'])
        html = render_coverage(coverage, joins)
        self.assertIn('500 € para 2/2', html)
        self.assertIn('evitando dos trayectos', html)
        self.assertIn('no sumar sus ahorros', html)

    def test_booked_skipped_and_covered_do_not_generate_buy_or_join(self):
        for state in ('booked', 'skipped', 'covered'):
            with self.subTest(state=state):
                plan = {'required_from':'2026-11-01', 'weekends':{'2026-11-07':state}}
                coverage = build_coverage(self.trips, {}, plan)
                self.assertEqual(join_opportunities(coverage, self.trips), [])
                html = render_coverage(coverage, [])
                self.assertIn('Sin recomendación de nueva compra', html)
                self.assertIn('300 € para 1/1', html)
                self.assertNotIn('Inicio de la rutina familiar pendiente', html)

    def test_outside_family_period_is_not_required(self):
        coverage = build_coverage(self.trips, {}, {'required_from':'2026-11-10'})
        self.assertEqual(coverage[0]['state'], 'outside')
        self.assertEqual(join_opportunities(coverage, self.trips), [])
        self.assertNotIn('2026-11-07', render_coverage(coverage, []))

    def test_joins_reuse_dates_and_only_adjacent_weekends(self):
        pairs = generate_weekend_pairs(date(2026, 11, 2), weeks=3)
        joined = joined_pairs(pairs)
        self.assertEqual(len(joined), 8)
        self.assertTrue(all(9 <= (i-o).days <= 11 for o,i in joined))
        self.assertTrue({o for o,_ in joined} <= {o for o,_ in pairs})
        self.assertTrue({i for _,i in joined} <= {i for _,i in pairs})

    def test_invalid_booking_state_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'plan.json'
            path.write_text(json.dumps({'weekends':{'2026-11-06':'booked'}}))
            with self.assertRaises(ValueError):
                load_plan(path)

    def test_months_not_ranked_as_substitutable_trips(self):
        trips = [trip(date(2026,10,29),date(2026,11,1),350),
                 trip(date(2026,11,5),date(2026,11,8),100)]
        html = render_coverage(build_coverage(trips, {}), [])
        self.assertIn('2026-10: 350 €', html)
        self.assertIn('2026-11: 100 €', html)
        self.assertLess(html.index('2026-10-31'), html.index('2026-11-07'))


class FamilyStartTests(unittest.TestCase):
    def test_configured_february_start_selects_first_february_weekend(self):
        from src.family import load_plan, weekend_of
        plan = load_plan()
        self.assertEqual(plan['required_from'], '2027-02-01')
        start = max(date(2026,10,19), date.fromisoformat(plan['required_from']))
        pairs = generate_weekend_pairs(start, weeks=7)
        self.assertEqual(pairs[0], (date(2027,2,4),date(2027,2,7)))
        self.assertEqual(weekend_of(pairs[0][0]), date(2027,2,6))
