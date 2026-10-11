"""Poll MyMeter and update external statistics."""
from datetime import datetime, timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant

from .api import AuthenticationRequired, MyMeterClient, SourceUnavailable
from .const import DOMAIN, NAME, SCAN_INTERVAL_HOURS
from .statistics import StatisticWriter

_LOGGER = logging.getLogger(__name__)


class MyMeterCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, client: MyMeterClient, writer: StatisticWriter) -> None:
        super().__init__(hass, _LOGGER, name=NAME, update_interval=timedelta(hours=SCAN_INTERVAL_HOURS))
        self.client = client
        self.writer = writer

    async def _async_update_data(self) -> dict:
        try:
            _payload, intervals = await self.client.fetch_usage()
            written = await self.writer.async_write(intervals)
            stamp, kwh = intervals[-1]
            return {
                "last_interval_kwh": kwh,
                "last_reading_local": stamp,
                "last_sync": datetime.now().astimezone(),
                "new_hours": written,
                "cumulative_kwh": self.writer.cumulative_sum,
            }
        except AuthenticationRequired as exc:
            raise ConfigEntryAuthFailed("PSE&G MyMeter session expired") from exc
        except (SourceUnavailable, ValueError) as exc:
            raise UpdateFailed(str(exc)) from exc
