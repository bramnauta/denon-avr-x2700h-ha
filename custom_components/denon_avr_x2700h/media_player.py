"""Media players for the main zone and zone 2."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DenonConfigEntry
from .const import (
    ATTR_COMMAND,
    ATTR_FREQUENCY,
    ATTR_SLOT,
    ATTR_WAIT,
    CONF_MAX_VOLUME,
    CONF_VOLUME_STEP,
    DEFAULT_MAX_VOLUME,
    DEFAULT_VOLUME_STEP,
    SERVICE_REFRESH,
    SERVICE_SAVE_QUICK_SELECT,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_TUNER_FREQUENCY,
)
from .entity import DenonEntity, entry_unique_id, zone2_enabled
from .protocol import (
    NETWORK_SOURCES,
    SETTINGS_BY_KEY,
    SOUND_MODES,
    ZONE_2,
    ZONE_SOURCE_FOLLOW,
    encode_tuner_frequency,
    format_tuner_frequency,
    level_to_volume,
    sound_mode_command,
    sound_mode_from_raw,
    volume_to_level,
)

PARALLEL_UPDATES = 0

BASE_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
)
MAIN_FEATURES = (
    BASE_FEATURES
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DenonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media players."""
    entities: list[DenonMediaPlayer] = [DenonMainZone(entry)]
    if zone2_enabled(entry):
        entities.append(DenonZone2(entry))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_WAIT, default=1.0): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=10)
            ),
        },
        "async_send_command",
        supports_response=SupportsResponse.OPTIONAL,
    )
    platform.async_register_entity_service(
        SERVICE_SAVE_QUICK_SELECT,
        {vol.Required(ATTR_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1, max=4))},
        "async_save_quick_select",
    )
    platform.async_register_entity_service(
        SERVICE_SET_TUNER_FREQUENCY,
        {vol.Required(ATTR_FREQUENCY): vol.All(vol.Coerce(float), vol.Range(min=0.1))},
        "async_set_tuner_frequency",
    )
    platform.async_register_entity_service(SERVICE_REFRESH, {}, "async_refresh")


class DenonMediaPlayer(DenonEntity, MediaPlayerEntity):
    """Shared media player logic."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _power_key: str
    _volume_key: str
    _mute_key: str
    _source_key: str
    # Command prefixes for power, mute, volume, source and Quick Select.
    _prefix: str
    _mute_prefix: str
    _volume_prefix: str
    _source_prefix: str
    _quick_prefix: str

    def __init__(self, entry: DenonConfigEntry, zone: str | None = None) -> None:
        """Initialize."""
        super().__init__(entry, zone)
        self._option_max_volume: float = entry.options.get(
            CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME
        )
        self._volume_step: float = entry.options.get(
            CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state."""
        power = self._client.get(self._power_key)
        if power is None:
            return None
        return MediaPlayerState.ON if power else MediaPlayerState.OFF

    @property
    def _volume_db(self) -> float | None:
        return self._client.get(self._volume_key)

    @property
    def _max_volume(self) -> float:
        """Volume at 100%: the configured option, capped by the receiver limit."""
        limit = self._client.get("max_volume")
        if limit is None:
            return self._option_max_volume
        return min(self._option_max_volume, limit)

    @property
    def _sources(self) -> dict[str, str]:
        return self._client.sources()

    @property
    def volume_level(self) -> float | None:
        """Return volume 0..1, scaled to the configured maximum."""
        if (volume := self._volume_db) is None:
            return None
        return volume_to_level(volume, self._max_volume)

    @property
    def is_volume_muted(self) -> bool | None:
        """Return mute state."""
        return self._client.get(self._mute_key)

    @property
    def source_list(self) -> list[str]:
        """Return selectable sources."""
        return list(self._sources.values())

    @property
    def source(self) -> str | None:
        """Return the current source name."""
        code = self._client.get(self._source_key)
        if code is None:
            return None
        return self._sources.get(code, code)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw values for automations."""
        return {
            "volume_db": self._volume_db,
            "source_code": self._client.get(self._source_key),
        }

    def _source_code(self, source: str) -> str:
        for code, name in self._sources.items():
            if source in (name, code):
                return code
        raise ServiceValidationError(f"Unknown source: {source}")

    async def async_turn_on(self) -> None:
        """Turn the zone on."""
        await self._async_send(f"{self._prefix}ON")

    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self._async_send(f"{self._prefix}OFF")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._async_send(f"{self._mute_prefix}{'ON' if mute else 'OFF'}")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume 0..1."""
        await self._async_set_volume_db(level_to_volume(volume, self._max_volume))

    async def _async_set_volume_db(self, volume_db: float) -> None:
        setting = SETTINGS_BY_KEY[self._volume_key]
        volume_db = min(max(volume_db, -80.0), self._max_volume)
        await self._async_send(setting.encode(volume_db))

    async def async_volume_up(self) -> None:
        """Increase volume by the configured step."""
        current = self._volume_db
        if self._volume_step == 0.5 or current is None:
            if current is not None and current >= self._max_volume:
                return
            await self._async_send(f"{self._volume_prefix}UP")
        else:
            await self._async_set_volume_db(current + self._volume_step)

    async def async_volume_down(self) -> None:
        """Decrease volume by the configured step."""
        current = self._volume_db
        if self._volume_step == 0.5 or current is None:
            await self._async_send(f"{self._volume_prefix}DOWN")
        else:
            await self._async_set_volume_db(current - self._volume_step)

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self._async_send(f"{self._source_prefix}{self._source_code(source)}")

    # ---------------------------------------------------------- services

    async def async_send_command(
        self, command: list[str], wait: float = 1.0
    ) -> ServiceResponse:
        """Send raw Telnet commands and return what the receiver answered."""
        try:
            lines = await self._client.async_send_and_collect(command, wait)
        except (ConnectionError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err
        return {"response": lines}

    async def async_save_quick_select(self, slot: int) -> None:
        """Store the current settings in a Quick Select slot."""
        await self._async_send(f"{self._quick_prefix}{slot} MEMORY")

    async def async_set_tuner_frequency(self, frequency: float) -> None:
        """Tune to a frequency (MHz for FM, kHz for AM)."""
        await self._async_send(encode_tuner_frequency(frequency))

    async def async_refresh(self) -> None:
        """Re-read every status value from the receiver."""
        try:
            await self._client.async_refresh()
        except ConnectionError as err:
            raise HomeAssistantError(str(err)) from err


class DenonMainZone(DenonMediaPlayer):
    """Main zone."""

    _attr_name = None
    _attr_supported_features = MAIN_FEATURES
    _power_key = "main_power"
    _volume_key = "volume"
    _mute_key = "mute"
    _source_key = "source"
    _prefix = "ZM"
    _mute_prefix = "MU"
    _volume_prefix = "MV"
    _source_prefix = "SI"
    _quick_prefix = "MSQUICK"

    def __init__(self, entry: DenonConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry_unique_id(entry)}-main"

    @property
    def sound_mode_list(self) -> list[str]:
        """Return the surround modes available for the current input signal."""
        return self._client.sound_modes or list(SOUND_MODES)

    @property
    def sound_mode(self) -> str | None:
        """Return the current surround mode, as named in the mode list."""
        if self._client.sound_modes and (info := self._client.get("sound_mode_info")):
            return info
        return sound_mode_from_raw(self._client.get("sound_mode"))

    @property
    def sound_mode_raw(self) -> str | None:
        """Return the surround mode exactly as reported."""
        return self._client.get("sound_mode")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw values for automations."""
        return {**super().extra_state_attributes, "sound_mode_raw": self.sound_mode_raw}

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a surround mode."""
        # Accepts names from the receiver's list ("Dolby Audio - Dolby Surround"),
        # the fallback list ("Movie") and raw MS values ("MCH STEREO").
        await self._async_send(f"MS{sound_mode_command(sound_mode)}")

    # ---------------------------------------------------- now playing

    @property
    def _is_tuner(self) -> bool:
        return self._client.get("source") == "TUNER"

    @property
    def _is_network(self) -> bool:
        return self._client.get("source") in NETWORK_SOURCES

    def _nse(self, line: int) -> str | None:
        value = self._client.get(f"nse{line}")
        return value or None

    @property
    def media_content_type(self) -> MediaType | None:
        """Return the content type."""
        if self._is_tuner:
            return MediaType.CHANNEL
        if self._is_network:
            return MediaType.MUSIC
        return None

    @property
    def media_title(self) -> str | None:
        """Return the title: track or radio station."""
        if self._is_tuner:
            station = self._client.get("tuner_station")
            freq = self._client.get("tuner_frequency")
            return station or (format_tuner_frequency(freq) if freq else None)
        if self._is_network:
            return self._nse(1)
        return None

    @property
    def media_artist(self) -> str | None:
        """Return the artist."""
        return self._nse(2) if self._is_network else None

    @property
    def media_album_name(self) -> str | None:
        """Return the album."""
        return self._nse(4) if self._is_network else None

    @property
    def media_channel(self) -> str | None:
        """Return the tuner preset."""
        if self._is_tuner and (preset := self._client.get("tuner_preset")):
            return f"Preset {preset}"
        return None

    async def async_media_play(self) -> None:
        """Play."""
        await self._async_send("NS9A")

    async def async_media_pause(self) -> None:
        """Pause."""
        await self._async_send("NS9B")

    async def async_media_stop(self) -> None:
        """Stop."""
        await self._async_send("NS9C")

    async def async_media_next_track(self) -> None:
        """Next track, or next tuner preset."""
        await self._async_send("TPANUP" if self._is_tuner else "NS9D")

    async def async_media_previous_track(self) -> None:
        """Previous track, or previous tuner preset."""
        await self._async_send("TPANDOWN" if self._is_tuner else "NS9E")


class DenonZone2(DenonMediaPlayer):
    """Zone 2."""

    _attr_name = None
    _attr_supported_features = BASE_FEATURES
    _power_key = "zone2_power"
    _volume_key = "zone2_volume"
    _mute_key = "zone2_mute"
    _source_key = "zone2_source"
    _prefix = "Z2"
    _mute_prefix = "Z2MU"
    _volume_prefix = "Z2"
    _source_prefix = "Z2"
    _quick_prefix = "Z2QUICK"

    def __init__(self, entry: DenonConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, ZONE_2)
        self._attr_unique_id = f"{entry_unique_id(entry)}-zone2"

    @property
    def _sources(self) -> dict[str, str]:
        return {ZONE_SOURCE_FOLLOW: "Source", **self._client.sources()}
