"""The Denon AVR-X2700H integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import DenonClient
from .const import CONF_ZONE2, DEFAULT_ZONE2
from .webapi import DeviceInfo, async_get_device_info

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BUTTON,
]


@dataclass
class DenonData:
    """Runtime data for a config entry."""

    client: DenonClient
    info: DeviceInfo


type DenonConfigEntry = ConfigEntry[DenonData]


async def async_setup_entry(hass: HomeAssistant, entry: DenonConfigEntry) -> bool:
    """Set up the receiver from a config entry."""
    host: str = entry.data[CONF_HOST]
    zone2: bool = entry.options.get(CONF_ZONE2, DEFAULT_ZONE2)

    client = DenonClient(host, include_zone2=zone2)
    await client.async_start()
    if not await client.async_wait_connected(15):
        await client.async_stop()
        raise ConfigEntryNotReady(
            f"Cannot reach {host} on Telnet port 23. Is network control enabled "
            "and no other client connected?"
        )

    info = await async_get_device_info(async_get_clientsession(hass), host)
    # Give the initial status round time to finish so entities start with state.
    await client.async_wait_synced(20)

    entry.runtime_data = DenonData(client=client, info=info)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DenonConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.async_stop()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: DenonConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
