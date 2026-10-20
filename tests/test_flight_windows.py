import unittest
from datetime import date
from src.scrapers.google_flights_ui import _departure_ok


class FlightWindowTests(unittest.TestCase):
    def test_friday_outbound(self):
        friday = date(2026, 10, 23)
        for time, expected in [('06:00', True), ('07:59', True), ('08:00', False), ('12:00', False), ('15:29', False), ('15:30', True)]:
            with self.subTest(time=time):
                self.assertEqual(_departure_ok(friday, time, 'outbound'), expected)

    def test_monday_arrival(self):
        monday = date(2026, 10, 26)
        self.assertTrue(_departure_ok(monday, '06:30', 'inbound', '08:59'))
        self.assertFalse(_departure_ok(monday, '06:30', 'inbound', '09:00'))
        self.assertFalse(_departure_ok(monday, '06:30', 'inbound', None))
        self.assertTrue(_departure_ok(monday, '17:00', 'inbound', '19:00'))

    def test_workday_outbound(self):
        thursday = date(2026, 10, 22)
        self.assertFalse(_departure_ok(thursday, '16:59', 'outbound'))
        self.assertTrue(_departure_ok(thursday, '17:00', 'outbound'))

    def test_sunday_return(self):
        sunday = date(2026, 10, 25)
        self.assertFalse(_departure_ok(sunday, '15:59', 'inbound'))
        self.assertTrue(_departure_ok(sunday, '16:00', 'inbound'))


if __name__ == '__main__':
    unittest.main()
