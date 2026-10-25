"""Base entities for the Denon AVR-X2700H integration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DenonConfigEntry
from .const import CONF_ZONE2, DEFAULT_ZONE2, DOMAIN, MANUFACTURER
from .protocol import CONFIG, DIAGNOSTIC, SETTINGS, ZONE_2, Setting


def entry_unique_id(entry: DenonConfigEntry) -> str:
    """Return the base unique id for entities of an entry."""
    return entry.unique_id or entry.entry_id


def zone2_enabled(entry: DenonConfigEntry) -> bool:
    """Return True if zone 2 entities are wanted."""
    return entry.options.get(CONF_ZONE2, DEFAULT_ZONE2)


def device_info(entry: DenonConfigEntry, zone: str | None = None) -> DeviceInfo:
    """Return device info for the main unit or a zone."""
    info = entry.runtime_data.info
    base = entry_unique_id(entry)
    if zone == ZONE_2:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{base}-zone2")},
            name=f"{entry.title} Zone 2",
            manufacturer=MANUFACTURER,
            model=f"{info.model} Zone 2",
            via_device=(DOMAIN, base),
        )
    return DeviceInfo(
        identifiers={(DOMAIN, base)},
        connections={(CONNECTION_NETWORK_MAC, info.mac)} if info.mac else set(),
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=info.model,
        sw_version=info.firmware,
        configuration_url=f"http://{entry.runtime_data.client.host}",
    )


class DenonEntity(Entity):
    """Common behaviour: push updates from the Telnet client."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # Keys whose change should trigger a state write; None means all keys.
    _watch_keys: set[str] | None = None

    def __init__(self, entry: DenonConfigEntry, zone: str | None = None) -> None:
        """Initialize."""
        self._entry = entry
        self._client = entry.runtime_data.client
        self._attr_device_info = device_info(entry, zone)

    @property
    def available(self) -> bool:
        """Return True while connected."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to client updates."""
        self.async_on_remove(self._client.add_listener(self._handle_client_update))

    @callback
    def _handle_client_update(self, keys: set[str] | None) -> None:
        if keys is None or self._watch_keys is None or keys & self._watch_keys:
            self.async_write_ha_state()

    async def _async_send(self, *commands: str) -> None:
        try:
            await self._client.async_send(*commands)
        except (ConnectionError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err


class DenonSettingEntity(DenonEntity):
    """Entity bound to one protocol setting."""

    def __init__(self, entry: DenonConfigEntry, setting: Setting) -> None:
        """Initialize."""
        super().__init__(entry, setting.zone)
        self._setting = setting
        self._watch_keys = {setting.key}
        self._attr_unique_id = f"{entry_unique_id(entry)}-{setting.key}"
        self._attr_translation_key = setting.translation_key or setting.key
        if setting.placeholders:
            self._attr_translation_placeholders = setting.placeholders
        if setting.icon:
            self._attr_icon = setting.icon
        self._attr_entity_registry_enabled_default = setting.enabled_default
        if setting.category == CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG
        elif setting.category == DIAGNOSTIC:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        """Available while connected and the receiver reported a value."""
        return self._client.connected and self._client.has(self._setting.key)

    @property
    def _value(self) -> Any:
        return self._client.get(self._setting.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """For DRC / LFE: whether the shown value is in effect right now."""
        if not self._setting.reports_effective:
            return None
        key = self._setting.key
        return {
            "active": key not in self._client.stored,
            "effective_value": self._client.get_reported(key),
        }

    async def _async_set(self, value: Any) -> None:
        try:
            accepted = await self._client.async_set_confirmed(self._setting, value)
        except (ConnectionError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err
        if not accepted:
            # The receiver kept its value, typically because the setting is not
            # available for the current input signal or surround mode.
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_accepted",
                translation_placeholders={
                    "entity": self.name or self._setting.key,
                    "value": str(value),
                },
            )


def settings_for(entry: DenonConfigEntry, platform: str) -> Iterable[Setting]:
    """Return the settings shown on ``platform`` for this entry."""
    with_zone2 = zone2_enabled(entry)
    return (
        s
        for s in SETTINGS
        if s.platform == platform and (with_zone2 or s.zone != ZONE_2)
    )


def async_setup_setting_entities(
    hass: HomeAssistant,
    entry: DenonConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: str,
    factory: Callable[[DenonConfigEntry, Setting], Entity],
) -> None:
    """Add entities for settings, as soon as the receiver reports them.

    Settings the receiver never reports (not supported or not configured, such
    as unused speaker channels) never get an entity.
    """
    client = entry.runtime_data.client
    pending = {s.key: s for s in settings_for(entry, platform)}

    def is_ready(setting: Setting) -> bool:
        if not client.has(setting.key):
            return False
        if setting.requires is None:
            return True
        return client.raw.get(setting.requires) not in (None, "NON")

    @callback
    def add_reported(keys: set[str] | None = None) -> None:
        ready = [s for s in pending.values() if is_ready(s)]
        if not ready:
            return
        for setting in ready:
            del pending[setting.key]
        async_add_entities([factory(entry, s) for s in ready])

    add_reported()
    if pending:
        entry.async_on_unload(client.add_listener(add_reported))
