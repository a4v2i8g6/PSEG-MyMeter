"""Pure-Python chart parser. No credentials or Home Assistant dependency.

MyMeter's Highcharts timestamps appear to encode local calendar time as UTC.
We do not interpret these as actual UTC instants: convert their UTC clock
components to America/New_York time before writing Home Assistant statistics.
This mapping needs a DST-boundary validation with real MyMeter readings.
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


class ChartDataError(ValueError):
    """Unexpected data format or chart selection."""


def extract_intervals(payload: dict) -> list[tuple[datetime, float]]:
    """Return (local-wall-time, kWh) from *actual* 15-minute meter series.

    Note: Returned wall-times are naive intentionally; chart timestamps are
    encoded as UTC but represent local calendar labels (see docstring).
    """
    try:
        data = payload["Data"]
        if data.get("usageType", "").casefold() != "consumption":
            raise ChartDataError("Chart is not set to Consumption (kWh)")
        if data.get("tooltipOptions", {}).get("storageType", "").casefold() not in (
            "fifteenminute", "15-minute", "15minute"
        ):
            raise ChartDataError("Chart is not set to 15-minute intervals")
        series = [
            s for s in data["series"]
            if s.get("type") == "areaspline"
            and s.get("tooltip", {}).get("valueSuffix", "").strip() == "kWh"
            and isinstance(s.get("data"), list)
        ]
        if len(series) != 1:
            raise ChartDataError("Expected exactly one electric meter series")
        points = series[0]["data"]
    except (KeyError, TypeError, AttributeError) as exc:
        raise ChartDataError("MyMeter response format not recognized") from exc

    parsed = {}
    for point in points:
        if not isinstance(point, dict):
            raise ChartDataError("Unexpected meter point shape")
        try:
            stamp_ms = int(point["x"])
            kwh = float(point["y"])
            if kwh < 0 or not (kwh < float("inf")):
                raise ChartDataError("Negative or invalid energy reading")
            # Deliberately *not* datetime.fromtimestamp(..., NEW_YORK):
            # MyMeter uses UTC-looking epoch ms for a local chart-clock label.
            wall_time = datetime.fromtimestamp(stamp_ms / 1000, timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, KeyError, OverflowError, OSError) as exc:
            raise ChartDataError("Invalid meter timestamp or kWh") from exc
        if wall_time.minute not in (0, 15, 30, 45) or wall_time.second != 0:
            raise ChartDataError("Unexpected meter interval alignment")
        if wall_time in parsed and parsed[wall_time] != kwh:
            raise ChartDataError("Conflicting readings for same timestamp")
        parsed[wall_time] = kwh

    if not parsed:
        raise ChartDataError("No electricity readings in response")
    return sorted(parsed.items())


def completed_hours(intervals: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """Aggregate complete four-quarter hours; reject ambiguous fall DST hour.

    Output is (UTC-aware hour start, kWh). Incomplete hours are excluded so that
    delayed source updates do not double-count them. The ambiguous fall-back
    local hour is skipped pending source behavior validation.
    """
    groups: dict[datetime, dict[int, float]] = defaultdict(dict)
    for wall, kwh in intervals:
        groups[wall.replace(minute=0)][wall.minute] = kwh

    result = []
    for wall_hour, quarters in sorted(groups.items()):
        if set(quarters) != {0, 15, 30, 45}:
            continue
        # Refuse to place a fall-back ambiguous hour on either UTC hour blindly.
        fold0 = wall_hour.replace(tzinfo=NEW_YORK, fold=0)
        fold1 = wall_hour.replace(tzinfo=NEW_YORK, fold=1)
        if fold0.utcoffset() != fold1.utcoffset():
            continue
        # Also reject nonexistent spring-forward local time.
        utc = fold0.astimezone(timezone.utc)
        if utc.astimezone(NEW_YORK).replace(tzinfo=None) != wall_hour:
            continue
        result.append((utc, sum(quarters.values())))
    return sorted(result)
