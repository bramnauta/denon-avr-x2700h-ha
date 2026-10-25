"""Diagnostics for the Denon AVR-X2700H integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import DenonConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DenonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client = entry.runtime_data.client
    return {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "device": asdict(entry.runtime_data.info),
        "connected": client.connected,
        "state": dict(sorted(client.raw.items())),
        "source_names": client.source_names,
        "source_usage": client.source_usage,
        "recent_lines": list(client.recent_lines),
        "unknown_lines": list(client.unknown_lines),
    }
