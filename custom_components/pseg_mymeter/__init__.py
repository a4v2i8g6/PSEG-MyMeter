"""PSE&G MyMeter experimental Home Assistant integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MyMeterClient
from .const import CONF_SESSION_COOKIE, DOMAIN
from .coordinator import MyMeterCoordinator
from .statistics import StatisticWriter

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = MyMeterClient(async_get_clientsession(hass), entry.data[CONF_SESSION_COOKIE])
    writer = StatisticWriter(hass, entry.entry_id)
    await writer.async_load()
    coordinator = MyMeterCoordinator(hass, client, writer)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return result
