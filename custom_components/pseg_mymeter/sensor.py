"""Read-only diagnostic sensors; historical kWh goes into Recorder statistics."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import MyMeterCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MyMeterDiagnostic(coordinator, entry.entry_id, "last_interval_kwh", "Last published 15-minute usage", UnitOfEnergy.KILO_WATT_HOUR, None),
        MyMeterDiagnostic(coordinator, entry.entry_id, "last_reading_local", "Last meter reading", None, None),
        MyMeterDiagnostic(coordinator, entry.entry_id, "last_sync", "Last MyMeter sync", None, SensorDeviceClass.TIMESTAMP),
        MyMeterDiagnostic(coordinator, entry.entry_id, "new_hours", "Hours added last sync", None, None),
    ])


class MyMeterDiagnostic(CoordinatorEntity[MyMeterCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id, key, label, unit, device_class):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = label
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

    @property
    def native_value(self):
        result = self.coordinator.data.get(self.key) if self.coordinator.data else None
        if self.key == "last_reading_local" and result is not None:
            # Avoid claiming precise UTC timestamp until DST is validated.
            return result.strftime("%Y-%m-%d %H:%M (PSE&G local)")
        return result
