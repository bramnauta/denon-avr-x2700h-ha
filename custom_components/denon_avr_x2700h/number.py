"""Numbers for level / time receiver settings."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DenonConfigEntry
from .entity import DenonSettingEntity, async_setup_setting_entities
from .protocol import NUMBER, Setting

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DenonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers."""
    async_setup_setting_entities(hass, entry, async_add_entities, NUMBER, DenonNumber)


class DenonNumber(DenonSettingEntity, NumberEntity):
    """A numeric setting."""

    def __init__(self, entry: DenonConfigEntry, setting: Setting) -> None:
        """Initialize."""
        super().__init__(entry, setting)
        self._attr_native_min_value = setting.min_value
        self._attr_native_max_value = setting.max_value
        self._attr_native_step = setting.step
        self._attr_native_unit_of_measurement = setting.unit
        self._attr_mode = NumberMode.SLIDER if setting.unit == "dB" else NumberMode.BOX

    @property
    def native_value(self) -> float | None:
        """Return the value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self._async_set(value)
