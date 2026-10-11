"""Hourly external Energy dashboard statistics with persistent append state.

This intentionally avoids exposing an invented real-time cumulative sensor:
PSE&G publishes readings late, and Home Assistant needs historical timestamps.
"""
from datetime import datetime, timedelta, timezone

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STATISTIC_ID
from .parser import completed_hours


class StatisticWriter:
    """Write new complete hourly readings, preserving cumulative sum."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self._store = Store(hass, 1, f"{DOMAIN}_{entry_id}_progress")
        self.latest_written: datetime | None = None
        self.cumulative_sum = 0.0

    async def async_load(self) -> None:
        saved = await self._store.async_load()
        if saved:
            val = saved.get("latest_written")
            self.latest_written = datetime.fromisoformat(val) if val else None
            self.cumulative_sum = float(saved.get("cumulative_sum", 0.0))

    async def async_write(self, intervals: list) -> int:
        hours = completed_hours(intervals)
        if not hours:
            return 0
        # Never skip a hole and later pretend no consumption occurred.
        # Source only returns a limited chart window; notify user if data has
        # fallen outside the window by raising instead of manufacturing zeros.
        new = [(stamp, kwh) for stamp, kwh in hours
               if self.latest_written is None or stamp > self.latest_written]
        if not new:
            return 0
        if self.latest_written is not None and new[0][0] != self.latest_written + timedelta(hours=1):
            raise ValueError("Gap between last stored hour and new MyMeter window")
        if any(next_stamp != stamp + timedelta(hours=1)
               for (stamp, _), (next_stamp, _) in zip(new, new[1:])):
            raise ValueError("Missing/incomplete meter hours; waiting for complete data")

        rows = []
        cumulative = self.cumulative_sum
        for stamp, kwh in new:
            cumulative += kwh
            rows.append({"start": stamp, "state": cumulative, "sum": cumulative})
        metadata = {
            "has_sum": True,
            "mean_type": StatisticMeanType.NONE,
            "name": "PSE&G electricity consumption",
            "source": DOMAIN,
            "statistic_id": STATISTIC_ID,
            "unit_class": "energy",
            "unit_of_measurement": "kWh",
        }
        async_add_external_statistics(self.hass, metadata, rows)
        self.latest_written = new[-1][0]
        self.cumulative_sum = cumulative
        await self._store.async_save({
            "latest_written": self.latest_written.isoformat(),
            "cumulative_sum": self.cumulative_sum,
        })
        return len(new)
