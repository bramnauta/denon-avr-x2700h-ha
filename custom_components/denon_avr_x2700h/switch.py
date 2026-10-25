"""Switches for on/off receiver settings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DenonConfigEntry
from .entity import DenonSettingEntity, async_setup_setting_entities
from .protocol import SWITCH

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DenonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    async_setup_setting_entities(hass, entry, async_add_entities, SWITCH, DenonSwitch)


class DenonSwitch(DenonSettingEntity, SwitchEntity):
    """An on/off setting."""

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        return self._value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self._async_set(False)
