import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "pseg_mymeter"))
from parser import extract_intervals, completed_hours, ChartDataError


def payload(base=1790121600000, values=(0.25, 0.5, 0.75, 1.0), *, usage="Consumption", storage="fifteenminute"):
    return {"Data": {"usageType": usage, "tooltipOptions": {"storageType": storage}, "series": [
        {"name": "Comparison", "type": "line", "data": [[base, 9.0]]},
        {"name": "Meter #redacted", "type": "areaspline", "tooltip": {"valueSuffix": " kWh"},
         "data": [{"x": base + 900000 * i, "y": v} for i, v in enumerate(values)]},
        {"name": "Temperature", "type": "spline", "data": [{"x": base, "y": 50}]},
    ]}}


class ParserTests(unittest.TestCase):
    def test_hour_aggregation(self):
        vals = extract_intervals(payload())
        hours = completed_hours(vals)
        self.assertEqual(len(hours), 1)
        self.assertAlmostEqual(hours[0][1], 2.5)
        self.assertEqual(hours[0][0], datetime(2026, 9, 23, 4, tzinfo=timezone.utc))

    def test_cost_chart_rejected(self):
        with self.assertRaises(ChartDataError):
            extract_intervals(payload(usage="Dollar"))

    def test_daily_chart_rejected(self):
        with self.assertRaises(ChartDataError):
            extract_intervals(payload(storage="daily"))

    def test_missing_quarter_excluded(self):
        vals = extract_intervals(payload(values=(.2, .3, .4)))
        self.assertEqual(completed_hours(vals), [])

    def test_multiple_meter_series_rejected(self):
        p = payload()
        p["Data"]["series"].append(p["Data"]["series"][1].copy())
        with self.assertRaises(ChartDataError):
            extract_intervals(p)

    def test_zero_valid(self):
        vals = extract_intervals(payload(values=(0, 0, 0, 0)))
        self.assertEqual(completed_hours(vals)[0][1], 0)


if __name__ == '__main__':
    unittest.main()
