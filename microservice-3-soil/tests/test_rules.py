import datetime as dt
import unittest

from soil_service import rules
from soil_service.errors import ApiError


class RangeTests(unittest.TestCase):
    def test_ph_out_of_possible_range_is_refused(self):
        with self.assertRaises(ApiError) as cm:
            rules.check_value("ph", 15)
        self.assertEqual(cm.exception.status, 422)

    def test_ph_needs_one_decimal(self):
        with self.assertRaises(ApiError):
            rules.check_value("ph", 6.84)
        self.assertEqual(rules.check_value("ph", 6.8), 6.8)

    def test_boundaries_of_possible_ranges(self):
        self.assertEqual(rules.check_value("nitrogen", 0), 0.0)
        self.assertEqual(rules.check_value("nitrogen", 1000), 1000.0)
        with self.assertRaises(ApiError):
            rules.check_value("nitrogen", 1000.5)
        with self.assertRaises(ApiError):
            rules.check_value("moisture", 101)

    def test_bool_and_text_are_not_numbers(self):
        with self.assertRaises(ApiError) as cm:
            rules.check_value("nitrogen", True)
        self.assertEqual(cm.exception.status, 400)

    def test_depth(self):
        self.assertEqual(rules.check_depth(100), 100.0)
        with self.assertRaises(ApiError):
            rules.check_depth(101)


class UnitTests(unittest.TestCase):
    def test_fixed_units_are_accepted(self):
        rules.check_units({"nitrogen": "mg/kg", "moisture": "%", "ph": "none"})

    def test_other_units_are_refused_never_converted(self):
        with self.assertRaises(ApiError) as cm:
            rules.check_units({"nitrogen": "ppm"})
        self.assertEqual(cm.exception.code, "UNIT_MISMATCH")

    def test_unknown_measurement_is_refused(self):
        with self.assertRaises(ApiError):
            rules.check_units({"sodium": "mg/kg"})


class DateTests(unittest.TestCase):
    today = dt.date(2026, 11, 19)

    def test_today_is_allowed(self):
        self.assertEqual(rules.check_sample_date("2026-11-19", self.today), "2026-11-19")

    def test_future_refused(self):
        with self.assertRaises(ApiError):
            rules.check_sample_date("2026-11-20", self.today)

    def test_older_than_five_years_refused(self):
        with self.assertRaises(ApiError):
            rules.check_sample_date("2021-11-18", self.today)
        self.assertEqual(rules.check_sample_date("2021-11-19", self.today), "2021-11-19")


class FlagTests(unittest.TestCase):
    def test_boundaries_from_the_specification(self):
        cases = {
            ("ph", 5.9): "LOW", ("ph", 6.0): "OK", ("ph", 7.5): "OK", ("ph", 7.6): "HIGH",
            ("moisture", 14): "LOW", ("moisture", 15): "OK", ("moisture", 45): "OK", ("moisture", 46): "HIGH",
            ("nitrogen", 19.9): "LOW", ("nitrogen", 20): "OK", ("nitrogen", 40): "OK", ("nitrogen", 40.1): "HIGH",
        }
        for (name, value), expected in cases.items():
            self.assertEqual(rules.flag_level(name, value), expected, (name, value))

    def test_nutrient_states(self):
        self.assertEqual(rules.nutrient_state("nitrogen", "LOW"), "DEFICIENT")
        self.assertEqual(rules.nutrient_state("potassium", "HIGH"), "EXCESS")
        self.assertEqual(rules.nutrient_state("ph", "LOW"), "LOW")

    def test_severity_bands(self):
        self.assertEqual(rules.severity("nitrogen", 18, "LOW"), "slight")     # exactly 10 %
        self.assertEqual(rules.severity("nitrogen", 17, "LOW"), "moderate")   # 15 %
        self.assertEqual(rules.severity("nitrogen", 15, "LOW"), "moderate")   # exactly 25 %
        self.assertEqual(rules.severity("nitrogen", 14, "LOW"), "severe")     # 30 %
        self.assertIsNone(rules.severity("nitrogen", 30, "OK"))


class HealthTests(unittest.TestCase):
    def flags(self, *pairs):
        return [{"level": level, "severity": sev} for level, sev in pairs]

    def test_good_when_all_in_range(self):
        self.assertEqual(rules.health_status(self.flags(("OK", None), ("OK", None))), "GOOD")

    def test_fair_for_one_not_severe(self):
        self.assertEqual(rules.health_status(self.flags(("OK", None), ("LOW", "moderate"))), "FAIR")

    def test_poor_for_two_or_more(self):
        self.assertEqual(rules.health_status(self.flags(("LOW", "slight"), ("HIGH", "slight"))), "POOR")

    def test_poor_for_one_severe(self):
        self.assertEqual(rules.health_status(self.flags(("OK", None), ("LOW", "severe"))), "POOR")


if __name__ == "__main__":
    unittest.main()
