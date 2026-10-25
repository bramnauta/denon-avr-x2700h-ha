"""Buttons for one-shot commands: menu navigation, Quick Select, tuner."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DenonConfigEntry
from .entity import DenonEntity, entry_unique_id, zone2_enabled
from .protocol import ZONE_2, ZONE_MAIN, all_queries

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DenonButtonDescription(ButtonEntityDescription):
    """Describes a command button."""

    command: str
    zone: str = ZONE_MAIN
    placeholders: dict[str, str] | None = None


def _cursor(key: str, command: str, icon: str) -> DenonButtonDescription:
    return DenonButtonDescription(
        key=key, translation_key=key, command=command, icon=icon
    )


BUTTONS: tuple[DenonButtonDescription, ...] = (
    _cursor("cursor_up", "MNCUP", "mdi:chevron-up"),
    _cursor("cursor_down", "MNCDN", "mdi:chevron-down"),
    _cursor("cursor_left", "MNCLT", "mdi:chevron-left"),
    _cursor("cursor_right", "MNCRT", "mdi:chevron-right"),
    _cursor("cursor_enter", "MNENT", "mdi:keyboard-return"),
    _cursor("menu_back", "MNRTN", "mdi:arrow-u-left-top"),
    _cursor("menu_option", "MNOPT", "mdi:dots-horizontal"),
    _cursor("menu_info", "MNINF", "mdi:information-outline"),
    # Locks can be set but not read back, hence buttons instead of switches.
    *(
        DenonButtonDescription(
            key=key,
            translation_key=key,
            command=command,
            icon=icon,
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        )
        for key, command, icon in (
            ("panel_lock", "SYPANEL LOCK ON", "mdi:lock"),
            ("panel_volume_lock", "SYPANEL+V LOCK ON", "mdi:lock"),
            ("panel_unlock", "SYPANEL LOCK OFF", "mdi:lock-open-variant"),
            ("remote_lock", "SYREMOTE LOCK ON", "mdi:remote-off"),
            ("remote_unlock", "SYREMOTE LOCK OFF", "mdi:remote"),
        )
    ),
    *(
        DenonButtonDescription(
            key=f"quick_select_{slot}",
            translation_key="quick_select",
            placeholders={"slot": str(slot)},
            command=f"MSQUICK{slot}",
            icon="mdi:star-outline",
        )
        for slot in range(1, 5)
    ),
    *(
        DenonButtonDescription(
            key=f"zone2_quick_select_{slot}",
            translation_key="quick_select",
            placeholders={"slot": str(slot)},
            command=f"Z2QUICK{slot}",
            icon="mdi:star-outline",
            zone=ZONE_2,
            entity_registry_enabled_default=False,
        )
        for slot in range(1, 5)
    ),
    DenonButtonDescription(
        key="tuner_preset_up",
        translation_key="tuner_preset_up",
        command="TPANUP",
        icon="mdi:skip-next",
    ),
    DenonButtonDescription(
        key="tuner_preset_down",
        translation_key="tuner_preset_down",
        command="TPANDOWN",
        icon="mdi:skip-previous",
    ),
    DenonButtonDescription(
        key="tuner_frequency_up",
        translation_key="tuner_frequency_up",
        command="TFANUP",
        icon="mdi:arrow-up",
        entity_registry_enabled_default=False,
    ),
    DenonButtonDescription(
        key="tuner_frequency_down",
        translation_key="tuner_frequency_down",
        command="TFANDOWN",
        icon="mdi:arrow-down",
        entity_registry_enabled_default=False,
    ),
    DenonButtonDescription(
        key="channel_levels_reset",
        translation_key="channel_levels_reset",
        command="CVZRL",
        icon="mdi:restore",
        entity_category=EntityCategory.CONFIG,
    ),
    DenonButtonDescription(
        key="sound_mode_next",
        translation_key="sound_mode_next",
        command="MSRIGHT",
        icon="mdi:surround-sound",
        entity_registry_enabled_default=False,
    ),
    DenonButtonDescription(
        key="sound_mode_previous",
        translation_key="sound_mode_previous",
        command="MSLEFT",
        icon="mdi:surround-sound",
        entity_registry_enabled_default=False,
    ),
    DenonButtonDescription(
        key="refresh",
        translation_key="refresh",
        command="",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DenonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    with_zone2 = zone2_enabled(entry)
    async_add_entities(
        DenonButton(entry, description)
        for description in BUTTONS
        if with_zone2 or description.zone != ZONE_2
    )


class DenonButton(DenonEntity, ButtonEntity):
    """Sends a fixed command."""

    entity_description: DenonButtonDescription
    def __init__(
        self, entry: DenonConfigEntry, description: DenonButtonDescription
    ) -> None:
        """Initialize."""
        super().__init__(entry, description.zone)
        # Buttons don't show state; only connection changes matter.
        self._watch_keys = set()
        self.entity_description = description
        self._attr_unique_id = f"{entry_unique_id(entry)}-{description.key}"
        if description.placeholders:
            self._attr_translation_placeholders = description.placeholders

    async def async_press(self) -> None:
        """Send the command."""
        if self.entity_description.key == "refresh":
            await self._async_send(*all_queries(self._client.include_zone2))
            return
        await self._async_send(self.entity_description.command)
