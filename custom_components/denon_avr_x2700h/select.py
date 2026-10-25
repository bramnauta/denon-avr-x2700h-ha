"""Selects for multiple-choice receiver settings."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DenonConfigEntry
from .entity import DenonSettingEntity, async_setup_setting_entities
from .protocol import SELECT, Setting

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DenonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects."""
    async_setup_setting_entities(hass, entry, async_add_entities, SELECT, DenonSelect)


class DenonSelect(DenonSettingEntity, SelectEntity):
    """A multiple-choice setting."""

    def __init__(self, entry: DenonConfigEntry, setting: Setting) -> None:
        """Initialize."""
        super().__init__(entry, setting)
        self._attr_options = list(setting.options)

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self._value

    async def async_select_option(self, option: str) -> None:
        """Change the option."""
        await self._async_set(option)
