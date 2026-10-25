"""Read-only sensors: surround mode, signal, tuner and speaker setup."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DenonConfigEntry
from .entity import DenonSettingEntity, async_setup_setting_entities
from .protocol import (
    DIAGNOSTIC,
    KIND_NUMBER,
    KIND_SELECT,
    SENSOR,
    Setting,
    format_tuner_frequency,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DenonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    async_setup_setting_entities(hass, entry, async_add_entities, SENSOR, DenonSensor)


class DenonSensor(DenonSettingEntity, SensorEntity):
    """A reported value."""

    def __init__(self, entry: DenonConfigEntry, setting: Setting) -> None:
        """Initialize."""
        super().__init__(entry, setting)
        if setting.kind == KIND_NUMBER:
            self._attr_native_unit_of_measurement = setting.unit
            if setting.device_class:
                self._attr_device_class = SensorDeviceClass(setting.device_class)
            # Setup values (distances, crossovers) don't need statistics.
            if setting.category != DIAGNOSTIC:
                self._attr_state_class = SensorStateClass.MEASUREMENT
        elif setting.kind == KIND_SELECT:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(setting.options)

    @property
    def native_value(self) -> Any:
        """Return the value."""
        value = self._value
        if self._setting.key == "tuner_frequency" and value is not None:
            return format_tuner_frequency(value)
        return value
