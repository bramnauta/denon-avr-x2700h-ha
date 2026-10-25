"""Denon AVR-X2700H control protocol: command tables, parsing and value conversion.

This module has no Home Assistant imports so it can be unit tested on its own.

The receiver speaks a line based ASCII protocol on TCP port 23. Every command
and every event is terminated by a carriage return. Setting a value is done by
sending ``<prefix><value>``; the receiver answers (and also spontaneously
reports changes made with the remote or front panel) with the same format.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import re
from typing import Any

TELNET_PORT = 23
HTTP_PORT = 8080

ON = "ON"
OFF = "OFF"

# Platforms a setting can be exposed on. ``None`` means internal state only
# (used by the media players).
SWITCH = "switch"
SELECT = "select"
NUMBER = "number"
SENSOR = "sensor"

# Kinds of values.
KIND_SWITCH = "switch"
KIND_SELECT = "select"
KIND_NUMBER = "number"
KIND_TEXT = "text"

# Number conversions.
CONV_VOLUME_DB = "volume_db"  # "50" / "505" -> -30.0 / -29.5 dB (0 dB = 80)
CONV_LEVEL50 = "level50"  # "50" / "505" -> 0.0 / +0.5 dB (0 dB = 50)
CONV_INT = "int"  # "005" -> 5
CONV_NEG_INT = "neg_int"  # "05" -> -5 (LFE level)
CONV_SLEEP = "sleep"  # "OFF" / "030" -> 0 / 30 minutes
CONV_CENTI = "centi"  # "0360" -> 3.6 (speaker distance in metres)

ZONE_MAIN = "main"
ZONE_2 = "zone2"

_DIGITS = re.compile(r"\d+")
_SLEEP = re.compile(r"OFF|\d+")


@dataclass(frozen=True, kw_only=True)
class Setting:
    """A single receiver parameter that can be read and (usually) written."""

    key: str
    prefix: str
    query: str | None = None
    platform: str | None = None
    kind: str = KIND_TEXT
    zone: str = ZONE_MAIN
    # Separator between prefix and value when sending a command.
    sep: str = ""
    # Switches.
    on_value: str = ON
    off_value: str = OFF
    # Selects: option slug -> device value.
    options: dict[str, str] = field(default_factory=dict)
    # Numbers.
    conv: str = CONV_INT
    min_value: float = 0
    max_value: float = 100
    step: float = 1
    unit: str | None = None
    width: int = 2
    # Text: optional regex the value must fully match.
    pattern: str | None = None
    # Entity presentation.
    category: str | None = None  # "config" / "diagnostic"
    enabled_default: bool = True
    icon: str | None = None
    read_only: bool = False
    placeholders: dict[str, str] | None = None
    translation_key: str | None = None
    # Only create the entity once this other key is reported with a value
    # other than "NON" (e.g. no crossover sensor for an absent speaker).
    requires: str | None = None
    # Sensor device class ("distance", "frequency").
    device_class: str | None = None

    def accepts(self, value: str) -> bool:
        """Return True if ``value`` is a valid response value for this setting."""
        if self.kind == KIND_SWITCH:
            return value in (self.on_value, self.off_value)
        if self.kind == KIND_SELECT:
            return value.upper() in (v.upper() for v in self.options.values())
        if self.kind == KIND_NUMBER:
            regex = _SLEEP if self.conv == CONV_SLEEP else _DIGITS
            return regex.fullmatch(value) is not None
        if self.pattern is not None:
            return re.fullmatch(self.pattern, value) is not None
        return True

    def decode(self, raw: str) -> Any:
        """Convert a raw device value into a Python value."""
        if self.kind == KIND_SWITCH:
            return raw == self.on_value
        if self.kind == KIND_SELECT:
            for slug, value in self.options.items():
                if value.upper() == raw.upper():
                    return slug
            return None
        if self.kind == KIND_NUMBER:
            return decode_number(self.conv, raw)
        return raw

    def encode(self, value: Any) -> str:
        """Build the command that sets this setting to ``value``."""
        if self.read_only:
            raise ValueError(f"{self.key} is read only")
        if self.kind == KIND_SWITCH:
            raw = self.on_value if value else self.off_value
        elif self.kind == KIND_SELECT:
            if value not in self.options:
                raise ValueError(f"Invalid option {value!r} for {self.key}")
            raw = self.options[value]
        elif self.kind == KIND_NUMBER:
            raw = encode_number(self.conv, float(value), self.width)
        else:
            raw = str(value)
        return f"{self.prefix}{self.sep}{raw}"


# --------------------------------------------------------------------------
# Value conversion
# --------------------------------------------------------------------------


def parse_volume(raw: str) -> float:
    """Parse a Denon two/three digit level ("50" -> 50.0, "505" -> 50.5)."""
    raw = raw.strip()
    if len(raw) == 3:
        return int(raw[:2]) + (0.5 if raw[2] == "5" else 0.0)
    return float(int(raw))


def format_volume(value: float) -> str:
    """Format a level in 0.5 steps as Denon expects ("50", "505")."""
    value = round(value * 2) / 2
    value = max(value, 0.0)
    whole = int(value)
    if value - whole >= 0.5:
        return f"{whole:02d}5"
    return f"{whole:02d}"


def decode_number(conv: str, raw: str) -> float | int:
    """Decode a raw numeric value according to ``conv``."""
    if conv == CONV_VOLUME_DB:
        return parse_volume(raw) - 80
    if conv == CONV_LEVEL50:
        return parse_volume(raw) - 50
    if conv == CONV_NEG_INT:
        return -int(raw)
    if conv == CONV_SLEEP:
        return 0 if raw == OFF else int(raw)
    if conv == CONV_CENTI:
        return int(raw) / 100
    return int(raw)


def encode_number(conv: str, value: float, width: int = 2) -> str:
    """Encode a numeric value according to ``conv``."""
    if conv == CONV_VOLUME_DB:
        return format_volume(value + 80)
    if conv == CONV_LEVEL50:
        return format_volume(value + 50)
    if conv == CONV_NEG_INT:
        return f"{round(-value):0{width}d}"
    if conv == CONV_SLEEP:
        minutes = round(value)
        return OFF if minutes <= 0 else f"{minutes:03d}"
    if conv == CONV_CENTI:
        return f"{round(value * 100):0{width}d}"
    return f"{round(value):0{width}d}"


def volume_to_level(volume_db: float, max_volume_db: float) -> float:
    """Map dB (-80 .. max) to a Home Assistant volume level (0 .. 1)."""
    span = max_volume_db + 80
    if span <= 0:
        return 0.0
    return min(max((volume_db + 80) / span, 0.0), 1.0)


def level_to_volume(level: float, max_volume_db: float) -> float:
    """Map a Home Assistant volume level (0 .. 1) to dB, in 0.5 dB steps."""
    volume = level * (max_volume_db + 80) - 80
    return round(volume * 2) / 2


# TFAN reports six digits with two implied decimals: FM in MHz ("008750" is
# 87.50 MHz), AM in kHz ("052200" is 522 kHz).
_FM_MAX = 200  # anything below this (after scaling) is an FM frequency in MHz


def format_tuner_frequency(raw: str) -> str | None:
    """Format a TFAN frequency ("010120" -> "101.20 MHz", "074700" -> "747 kHz")."""
    if not raw.isdigit():
        return None
    value = int(raw) / 100
    if value < _FM_MAX:
        return f"{value:.2f} MHz"
    return f"{value:.0f} kHz"


def encode_tuner_frequency(frequency: float) -> str:
    """Encode a frequency (MHz for FM, kHz for AM) as a TFAN command."""
    return f"TFAN{round(frequency * 100):06d}"


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(value: str) -> str:
    """Strip control characters the receiver uses as cursor/icon markers."""
    return _CONTROL_CHARS.sub("", value).strip()


# --------------------------------------------------------------------------
# Sources and surround modes
# --------------------------------------------------------------------------

# Telnet source code -> factory default display name, in front panel order.
SOURCES: dict[str, str] = {
    "SAT/CBL": "CBL/SAT",
    "DVD": "DVD",
    "BD": "Blu-ray",
    "GAME": "Game",
    "8K": "8K",
    "AUX1": "AUX1",
    "MPLAY": "Media Player",
    "TV": "TV Audio",
    "CD": "CD",
    "PHONO": "Phono",
    "TUNER": "Tuner",
    "NET": "HEOS Music",
    "BT": "Bluetooth",
}

ZONE_SOURCE_FOLLOW = "SOURCE"

# Sources on which the network transport commands (NS9x) work.
NETWORK_SOURCES = {"NET", "BT", "USB/IPOD", "USB", "SERVER", "IRADIO", "FAVORITES"}

# "SSFUN<code> <name>" reports a renamed source, "SSSOD<code> USE|DEL" whether
# a source is shown or hidden. Codes can contain "/", so split on the space.
SOURCE_NAME = "name"
SOURCE_USAGE = "usage"
SOURCE_INFO_QUERIES = ("SSSOD ?", "SSFUN ?")


def parse_source_info(line: str) -> tuple[str, str, str] | None:
    """Parse SSFUN / SSSOD lines into (kind, source code, value)."""
    for prefix, kind in (("SSFUN", SOURCE_NAME), ("SSSOD", SOURCE_USAGE)):
        if not line.startswith(prefix):
            continue
        code, _, value = line[len(prefix) :].partition(" ")
        if not code or code == "END" or not value.strip():
            return None
        return kind, code, value.strip()
    return None


# Lines the receiver sends unasked that carry nothing we expose (per-category
# sound mode lists, input/speaker flag strings, list terminators). Not logged
# as unknown.
IGNORED_PREFIXES = (
    "OPSML ",
    "OPINF",
    "SSLAN",
    "SSSOD END",
    "SSFUN END",
    "SSSDE END",
    "SSCFR END",
    "SSLEV END",
    "SSSDESTP",
)

# "OPSMLALL MOV021Dolby Audio - Dolby Surround": the full list of surround modes
# available for the current input signal, as <category><index:2><active:1><name>.
# The list ends with "OPSMLALL END". "OPSML ..." is the same for the current
# category only and is ignored.
SOUND_MODE_LIST_PREFIX = "OPSMLALL "
SOUND_MODE_LIST_END = "OPSMLALL END"
SOUND_MODE_LIST_QUERY = "OPSML ?"
_SOUND_MODE_ITEM = re.compile(r"([A-Z]{3})(\d{2})([01])(.+)")


def parse_sound_mode_item(line: str) -> tuple[int, str, bool] | None:
    """Parse one OPSMLALL line into (index, name, active)."""
    if not line.startswith(SOUND_MODE_LIST_PREFIX) or line == SOUND_MODE_LIST_END:
        return None
    match = _SOUND_MODE_ITEM.fullmatch(line[len(SOUND_MODE_LIST_PREFIX) :].strip())
    if match is None:
        return None
    return int(match.group(2)), match.group(4).strip(), match.group(3) == "1"


# Surround mode names as the receiver lists them -> MS command value. Verified
# on an AVR-X2700H: Stereo, Dolby Surround (via "DOLBY DIGITAL"), Multi Ch
# Stereo and Direct. "MSDOLBY SURROUND" is NOT accepted.
_SOUND_MODE_COMMANDS: dict[str, str] = {
    "STEREO": "STEREO",
    "MULTI CH STEREO": "MCH STEREO",
    "DIRECT": "DIRECT",
    "PURE DIRECT": "PURE DIRECT",
    "AUTO": "AUTO",
}


def sound_mode_command(name: str) -> str:
    """Return the MS command value that selects the listed mode ``name``."""
    key = name.strip().upper()
    if key in _SOUND_MODE_COMMANDS:
        return _SOUND_MODE_COMMANDS[key]
    if key in (v.upper() for v in SOUND_MODES.values()):
        return key
    for display, value in SOUND_MODES.items():
        if display.upper() == key:
            return value
    # Dolby family ("Dolby Audio - Dolby Surround", "Dolby Atmos", ...) is
    # selected with the Dolby mode key, DTS family likewise.
    if key.startswith("DOLBY"):
        return "DOLBY DIGITAL"
    if key.startswith(("DTS", "NEURAL")):
        return "DTS SURROUND"
    return key


# Fallback list of selectable surround modes until the receiver sent its
# own list: display name -> MS command value.
SOUND_MODES: dict[str, str] = {
    "Auto": "AUTO",
    "Movie": "MOVIE",
    "Music": "MUSIC",
    "Game": "GAME",
    "Direct": "DIRECT",
    "Pure Direct": "PURE DIRECT",
    "Stereo": "STEREO",
    "Dolby Digital": "DOLBY DIGITAL",
    "DTS Surround": "DTS SURROUND",
    "Multi Ch Stereo": "MCH STEREO",
    "Rock Arena": "ROCK ARENA",
    "Jazz Club": "JAZZ CLUB",
    "Mono Movie": "MONO MOVIE",
    "Matrix": "MATRIX",
    "Video Game": "VIDEO GAME",
    "Virtual": "VIRTUAL",
}


def sound_mode_from_raw(raw: str | None) -> str | None:
    """Map a reported MS value to a selectable sound mode name when possible."""
    if raw is None:
        return None
    for name, value in SOUND_MODES.items():
        if value == raw.upper():
            return name
    return raw


# --------------------------------------------------------------------------
# Setting table
# --------------------------------------------------------------------------

CONFIG = "config"
DIAGNOSTIC = "diagnostic"


def _switch(key: str, prefix: str, query: str | None = None, **kw: Any) -> Setting:
    return Setting(
        key=key,
        prefix=prefix,
        query=query if query is not None else f"{prefix.rstrip()} ?",
        platform=kw.pop("platform", SWITCH),
        kind=KIND_SWITCH,
        category=kw.pop("category", CONFIG),
        **kw,
    )


def _select(
    key: str, prefix: str, options: dict[str, str], query: str | None = None, **kw: Any
) -> Setting:
    return Setting(
        key=key,
        prefix=prefix,
        query=query if query is not None else f"{prefix.rstrip()} ?",
        platform=kw.pop("platform", SELECT),
        kind=KIND_SELECT,
        options=options,
        category=kw.pop("category", CONFIG),
        **kw,
    )


def _number(key: str, prefix: str, query: str | None = None, **kw: Any) -> Setting:
    return Setting(
        key=key,
        prefix=prefix,
        query=query if query is not None else f"{prefix.rstrip()} ?",
        platform=kw.pop("platform", NUMBER),
        kind=KIND_NUMBER,
        category=kw.pop("category", CONFIG),
        **kw,
    )


def _level(key: str, prefix: str, limit: float, step: float = 0.5, **kw: Any) -> Setting:
    return _number(
        key,
        prefix,
        conv=CONV_LEVEL50,
        min_value=-limit,
        max_value=limit,
        step=step,
        unit="dB",
        **kw,
    )


# Speaker channels reported by CV? (only configured speakers are reported).
CHANNELS: dict[str, str] = {
    "FL": "Front Left",
    "FR": "Front Right",
    "C": "Center",
    "SW": "Subwoofer",
    "SW2": "Subwoofer 2",
    "SL": "Surround Left",
    "SR": "Surround Right",
    "SBL": "Surround Back Left",
    "SBR": "Surround Back Right",
    "SB": "Surround Back",
    "FHL": "Front Height Left",
    "FHR": "Front Height Right",
    "FWL": "Front Wide Left",
    "FWR": "Front Wide Right",
    "TFL": "Top Front Left",
    "TFR": "Top Front Right",
    "TML": "Top Middle Left",
    "TMR": "Top Middle Right",
    "TRL": "Top Rear Left",
    "TRR": "Top Rear Right",
    "RHL": "Rear Height Left",
    "RHR": "Rear Height Right",
    "FDL": "Front Dolby Left",
    "FDR": "Front Dolby Right",
    "SDL": "Surround Dolby Left",
    "SDR": "Surround Dolby Right",
    "BDL": "Back Dolby Left",
    "BDR": "Back Dolby Right",
}

# Speaker positions in the speaker configuration (SSSPC / SSCFR).
SPEAKER_POSITIONS: dict[str, str] = {
    "FRO": "Front",
    "CEN": "Center",
    "SUA": "Surround",
    "SBK": "Surround Back",
    "FRH": "Front Height",
    "FRW": "Front Wide",
    "TFR": "Top Front",
    "TPM": "Top Middle",
    "TPR": "Top Rear",
    "RHE": "Rear Height",
    "FRD": "Front Dolby",
    "SUD": "Surround Dolby",
    "BKD": "Back Dolby",
}
SPEAKER_SIZES: dict[str, str] = {"small": "SMA", "large": "LAR", "none": "NON"}


def source_slug(code: str) -> str:
    """Option slug for a source code ("SAT/CBL" -> "sat_cbl")."""
    return code.lower().replace("/", "_")


_ON_OFF_ICON = "mdi:tune-variant"

SETTINGS: tuple[Setting, ...] = (
    # ---- Main zone core state (used by the media player) ----
    Setting(key="main_power", prefix="ZM", query="ZM?", kind=KIND_SWITCH),
    Setting(key="mute", prefix="MU", query="MU?", kind=KIND_SWITCH),
    Setting(key="source", prefix="SI", query="SI?", kind=KIND_TEXT),
    Setting(
        key="sound_mode",
        prefix="MS",
        query="MS?",
        platform=SENSOR,
        kind=KIND_TEXT,
        icon="mdi:surround-sound",
        read_only=True,
    ),
    # Readable surround mode and input format, pushed by the receiver.
    Setting(
        key="sound_mode_info",
        prefix="SYSMI ",
        query="",
        platform=SENSOR,
        icon="mdi:surround-sound",
        read_only=True,
    ),
    Setting(
        key="audio_format",
        prefix="SYSDA ",
        query="",
        platform=SENSOR,
        icon="mdi:waveform",
        read_only=True,
    ),
    Setting(
        key="audio_channels",
        prefix="SSINFAISFOR ",
        query="",
        platform=SENSOR,
        category=DIAGNOSTIC,
        icon="mdi:speaker-multiple",
        read_only=True,
    ),
    # Quick Select (and Smart Select on other models) reports start with MS
    # too; capture them so they do not overwrite the surround mode. "0" means
    # no Quick Select memory is active.
    Setting(key="quick_select", prefix="MSQUICK", query="MSQUICK ?", kind=KIND_TEXT),
    Setting(key="smart_select", prefix="MSSMART", kind=KIND_TEXT),
    _number(
        "volume",
        "MV",
        query="MV?",
        conv=CONV_VOLUME_DB,
        min_value=-80,
        max_value=18,
        step=0.5,
        unit="dB",
        category=None,
        icon="mdi:volume-high",
    ),
    _number(
        "max_volume",
        "MVMAX",
        query="MV?",
        platform=SENSOR,
        conv=CONV_VOLUME_DB,
        unit="dB",
        category=DIAGNOSTIC,
        read_only=True,
        icon="mdi:volume-plus",
    ),
    # ---- System ----
    _switch(
        "power",
        "PW",
        query="PW?",
        on_value="ON",
        off_value="STANDBY",
        category=None,
        zone=ZONE_MAIN,
        icon="mdi:power",
    ),
    _select(
        "eco_mode",
        "ECO",
        {"on": "ON", "auto": "AUTO", "off": "OFF"},
        query="ECO?",
        icon="mdi:leaf",
    ),
    _select(
        "auto_standby",
        "STBY",
        {"15m": "15M", "30m": "30M", "60m": "60M", "off": "OFF"},
        query="STBY?",
        icon="mdi:timer-sand",
    ),
    _select(
        "dimmer",
        "DIM ",
        {"bright": "BRI", "dim": "DIM", "dark": "DAR", "off": "OFF"},
        query="DIM ?",
        icon="mdi:brightness-6",
    ),
    _number(
        "sleep_timer",
        "SLP",
        query="SLP?",
        conv=CONV_SLEEP,
        min_value=0,
        max_value=120,
        step=10,
        unit="min",
        category=None,
        icon="mdi:sleep",
    ),
    _select(
        "speaker_preset",
        "SPPR",
        {"preset_1": "1", "preset_2": "2"},
        query="SPPR ?",
        sep=" ",
        icon="mdi:speaker-multiple",
    ),
    _switch("setup_menu", "MNMEN ", query="MNMEN?", icon="mdi:menu", category=None),
    _switch("all_zone_stereo", "MNZST ", query="MNZST?", icon="mdi:speaker-wireless"),
    # ---- Input ----
    _select(
        "input_mode",
        "SD",
        {"auto": "AUTO", "hdmi": "HDMI", "digital": "DIGITAL", "analog": "ANALOG"},
        query="SD?",
        icon="mdi:import",
    ),
    _select(
        "digital_input",
        "DC",
        {"auto": "AUTO", "pcm": "PCM", "dts": "DTS"},
        query="DC?",
        icon="mdi:import",
    ),
    # ---- Audio (PS) ----
    _switch("tone_control", "PSTONE CTRL ", icon=_ON_OFF_ICON),
    _level("bass", "PSBAS ", 6, step=1, icon="mdi:music-clef-bass"),
    _level("treble", "PSTRE ", 6, step=1, icon="mdi:music-clef-treble"),
    _switch("dialog_level_adjust", "PSDIL ", icon="mdi:account-voice"),
    _level("dialog_level", "PSDIL ", 12, icon="mdi:account-voice"),
    _switch("subwoofer_level_adjust", "PSSWL ", icon="mdi:speaker"),
    _level("subwoofer_level", "PSSWL ", 12, icon="mdi:speaker"),
    _level("subwoofer2_level", "PSSWL2 ", 12, icon="mdi:speaker", enabled_default=False),
    _switch("cinema_eq", "PSCINEMA EQ.", query="PSCINEMA EQ. ?", icon="mdi:movie-open"),
    _select(
        "multeq",
        "PSMULTEQ:",
        {
            "audyssey": "AUDYSSEY",
            "bypass_lr": "BYP.LR",
            "flat": "FLAT",
            "off": "OFF",
        },
        query="PSMULTEQ: ?",
        icon="mdi:equalizer",
    ),
    _switch("dynamic_eq", "PSDYNEQ ", icon="mdi:equalizer"),
    _select(
        "reference_level_offset",
        "PSREFLEV ",
        {"0db": "0", "5db": "5", "10db": "10", "15db": "15"},
        icon="mdi:equalizer",
    ),
    _select(
        "dynamic_volume",
        "PSDYNVOL ",
        {"heavy": "HEV", "medium": "MED", "light": "LIT", "off": "OFF"},
        icon="mdi:volume-equal",
    ),
    _switch("lfc", "PSLFC ", icon="mdi:home-sound-out"),
    _number(
        "containment_amount",
        "PSCNTAMT ",
        min_value=1,
        max_value=7,
        icon="mdi:home-sound-out",
    ),
    _switch("graphic_eq", "PSGEQ ", icon="mdi:equalizer-outline"),
    _switch("headphone_eq", "PSHEQ ", icon="mdi:headphones", enabled_default=False),
    _select(
        "dynamic_range_compression",
        "PSDRC ",
        {"auto": "AUTO", "low": "LOW", "mid": "MID", "high": "HI", "off": "OFF"},
        icon="mdi:waveform",
    ),
    _number(
        "lfe_level",
        "PSLFE ",
        conv=CONV_NEG_INT,
        min_value=-10,
        max_value=0,
        unit="dB",
        icon="mdi:speaker",
    ),
    _number(
        "audio_delay",
        "PSDELAY ",
        min_value=0,
        max_value=200,
        unit="ms",
        width=3,
        icon="mdi:timer-outline",
    ),
    _select(
        "audio_restorer",
        "PSRSTR ",
        {"off": "OFF", "mode1": "MODE1", "mode2": "MODE2", "mode3": "MODE3"},
        icon="mdi:auto-fix",
    ),
    _select(
        "dialog_enhancer",
        "PSDEH ",
        {"off": "OFF", "low": "LOW", "medium": "MED", "high": "HIGH"},
        icon="mdi:account-voice",
    ),
    _switch("center_spread", "PSCES ", icon=_ON_OFF_ICON, enabled_default=False),
    _switch("neural_x", "PSNEURAL ", icon=_ON_OFF_ICON, enabled_default=False),
    _switch(
        "loudness_management", "PSLOM ", icon="mdi:volume-vibrate", enabled_default=False
    ),
    _switch(
        "subwoofer_direct", "PSSWR ", icon="mdi:speaker", enabled_default=False
    ),
    _switch("speaker_virtualizer", "PSSPV ", icon="mdi:speaker-wireless"),
    # ---- Bluetooth transmitter (headphones) ----
    _switch("bluetooth_transmitter", "BTTX ", icon="mdi:bluetooth-audio"),
    _select(
        "bluetooth_output",
        "BTTX ",
        {"bluetooth_speakers": "SP", "bluetooth_only": "BT"},
        query="BTTX ?",
        icon="mdi:bluetooth-audio",
    ),
    # ---- Video (VS / PV) ----
    _select(
        "picture_mode",
        "PV",
        {
            "off": "OFF",
            "standard": "STD",
            "movie": "MOV",
            "vivid": "VVD",
            "stream": "STM",
            "custom": "CTM",
            "isf_day": "DAY",
            "isf_night": "NGT",
        },
        query="PV?",
        icon="mdi:television",
        enabled_default=False,
    ),
    _select(
        "aspect_ratio",
        "VSASP",
        {"normal": "NRM", "full": "FUL"},
        query="VSASP ?",
        icon="mdi:aspect-ratio",
        enabled_default=False,
    ),
    _select(
        "video_resolution",
        "VSSC",
        {
            "480p": "48P",
            "1080i": "10I",
            "720p": "72P",
            "1080p": "10P",
            "1080p24": "10P24",
            "4k": "4K",
            "4k60": "4KF",
            "8k": "8K",
            "auto": "AUTO",
        },
        query="VSSC ?",
        icon="mdi:monitor-screenshot",
        enabled_default=False,
    ),
    _select(
        "hdmi_resolution",
        "VSSCH",
        {
            "480p": "48P",
            "1080i": "10I",
            "720p": "72P",
            "1080p": "10P",
            "1080p24": "10P24",
            "4k": "4K",
            "4k60": "4KF",
            "8k": "8K",
            "auto": "AUTO",
        },
        query="VSSCH ?",
        icon="mdi:monitor-screenshot",
    ),
    _select(
        "hdmi_audio_output",
        "VSAUDIO ",
        {"amp": "AMP", "tv": "TV"},
        icon="mdi:television-speaker",
    ),
    _select(
        "video_processing_mode",
        "VSVPM",
        {"auto": "AUTO", "game": "GAME", "movie": "MOVI", "bypass": "BYP"},
        query="VSVPM ?",
        icon="mdi:video-image",
    ),
    _switch(
        "vertical_stretch",
        "VSVST ",
        icon="mdi:arrow-expand-vertical",
        enabled_default=False,
    ),
    # ---- Tuner ----
    Setting(
        key="tuner_frequency",
        prefix="TFAN",
        query="TFAN?",
        platform=SENSOR,
        kind=KIND_TEXT,
        pattern=r"\d{6}",
        icon="mdi:radio",
        read_only=True,
    ),
    Setting(
        key="tuner_station",
        prefix="TFANNAME",
        query="TFANNAME?",
        platform=SENSOR,
        kind=KIND_TEXT,
        icon="mdi:radio",
        read_only=True,
    ),
    _number(
        "tuner_preset",
        "TPAN",
        query="TPAN?",
        min_value=1,
        max_value=56,
        category=None,
        icon="mdi:radio",
    ),
    _select(
        "tuner_band",
        "TMAN",
        {"am": "AM", "fm": "FM"},
        query="TMAN?",
        category=None,
        icon="mdi:radio",
    ),
    _select(
        "tuner_mode",
        "TMAN",
        {"auto": "AUTO", "manual": "MANUAL"},
        query="TMAN?",
        icon="mdi:radio",
    ),
    # ---- Signal information ----
    Setting(
        key="audio_input_signal",
        prefix="SSINFAISSIG ",
        query="SSINFAISSIG ?",
        platform=SENSOR,
        category=DIAGNOSTIC,
        enabled_default=False,
        read_only=True,
        icon="mdi:waveform",
    ),
    Setting(
        key="audio_sampling_rate",
        prefix="SSINFAISFSV ",
        query="SSINFAISFSV ?",
        platform=SENSOR,
        category=DIAGNOSTIC,
        enabled_default=False,
        read_only=True,
        icon="mdi:sine-wave",
    ),
    # ---- Zone 2 ----
    Setting(key="zone2_power", prefix="Z2", query="Z2?", kind=KIND_SWITCH, zone=ZONE_2),
    _number(
        "zone2_volume",
        "Z2",
        query="Z2?",
        conv=CONV_VOLUME_DB,
        min_value=-80,
        max_value=18,
        step=0.5,
        unit="dB",
        zone=ZONE_2,
        category=None,
        icon="mdi:volume-high",
    ),
    Setting(
        key="zone2_source",
        prefix="Z2",
        query="Z2?",
        kind=KIND_TEXT,
        zone=ZONE_2,
        pattern=r"(?!ON$|OFF$|UP$|DOWN$|\d+$)[A-Z0-9/ .\-]+",
    ),
    Setting(key="zone2_mute", prefix="Z2MU", query="Z2MU?", kind=KIND_SWITCH, zone=ZONE_2),
    _select(
        "zone2_channel_setting",
        "Z2CS",
        {"stereo": "ST", "mono": "MONO"},
        query="Z2CS?",
        zone=ZONE_2,
        icon="mdi:speaker-multiple",
    ),
    _level("zone2_bass", "Z2PSBAS ", 10, step=1, zone=ZONE_2, icon="mdi:music-clef-bass"),
    _level(
        "zone2_treble", "Z2PSTRE ", 10, step=1, zone=ZONE_2, icon="mdi:music-clef-treble"
    ),
    _level(
        "zone2_channel_level_fl",
        "Z2CVFL ",
        12,
        query="Z2CV?",
        zone=ZONE_2,
        icon="mdi:speaker",
        translation_key="channel_level",
        placeholders={"channel": "Front Left"},
    ),
    _level(
        "zone2_channel_level_fr",
        "Z2CVFR ",
        12,
        query="Z2CV?",
        zone=ZONE_2,
        icon="mdi:speaker",
        translation_key="channel_level",
        placeholders={"channel": "Front Right"},
    ),
    _switch("zone2_hpf", "Z2HPF", query="Z2HPF?", zone=ZONE_2, icon="mdi:filter"),
    _number(
        "zone2_sleep_timer",
        "Z2SLP",
        query="Z2SLP?",
        conv=CONV_SLEEP,
        min_value=0,
        max_value=120,
        step=10,
        unit="min",
        zone=ZONE_2,
        category=None,
        icon="mdi:sleep",
    ),
    _select(
        "zone2_auto_standby",
        "Z2STBY",
        {"2h": "2H", "4h": "4H", "8h": "8H", "off": "OFF"},
        query="Z2STBY?",
        zone=ZONE_2,
        icon="mdi:timer-sand",
    ),
    Setting(
        key="zone2_quick_select",
        prefix="Z2QUICK",
        query="Z2QUICK ?",
        kind=KIND_TEXT,
        zone=ZONE_2,
    ),
    Setting(key="zone2_smart_select", prefix="Z2SMART", kind=KIND_TEXT, zone=ZONE_2),
    # ---- Channel levels (main zone) ----
    *(
        _level(
            f"channel_level_{code.lower()}",
            f"CV{code} ",
            12,
            query="CV?",
            icon="mdi:speaker",
            translation_key="channel_level",
            placeholders={"channel": name},
        )
        for code, name in CHANNELS.items()
    ),
    # ---- Speaker configuration (read only, from the setup menu) ----
    *(
        Setting(
            key=f"speaker_size_{code.lower()}",
            prefix=f"SSSPC{code} ",
            query="SSSPC ?",
            platform=SENSOR,
            kind=KIND_SELECT,
            options=SPEAKER_SIZES,
            category=DIAGNOSTIC,
            read_only=True,
            icon="mdi:speaker",
            translation_key="speaker_size",
            placeholders={"position": name},
        )
        for code, name in SPEAKER_POSITIONS.items()
    ),
    Setting(
        key="surround_back_speakers",
        prefix="SSSPCSBK ",
        query="SSSPC ?",
        platform=SENSOR,
        kind=KIND_SELECT,
        options={"one": "1SP", "two": "2SP"},
        category=DIAGNOSTIC,
        read_only=True,
        icon="mdi:speaker-multiple",
        requires="speaker_size_sbk",
    ),
    Setting(
        key="subwoofer_present",
        prefix="SSSPCSWF ",
        query="SSSPC ?",
        platform=SENSOR,
        kind=KIND_SELECT,
        options={"yes": "YES", "no": "NO"},
        category=DIAGNOSTIC,
        read_only=True,
        icon="mdi:speaker",
    ),
    *(
        _number(
            f"crossover_{code.lower()}",
            f"SSCFR{code} ",
            query="SSCFR ?",
            platform=SENSOR,
            unit="Hz",
            device_class="frequency",
            category=DIAGNOSTIC,
            read_only=True,
            icon="mdi:sine-wave",
            translation_key="crossover",
            placeholders={"position": name},
            requires=f"speaker_size_{code.lower()}",
        )
        for code, name in SPEAKER_POSITIONS.items()
    ),
    Setting(
        key="crossover_mode",
        prefix="SSCFR ",
        query="SSCFR ?",
        platform=SENSOR,
        kind=KIND_SELECT,
        options={"all": "ALL", "individual": "IND"},
        category=DIAGNOSTIC,
        read_only=True,
        icon="mdi:sine-wave",
    ),
    _number(
        "crossover_all",
        "SSCFRALL ",
        query="SSCFR ?",
        platform=SENSOR,
        unit="Hz",
        device_class="frequency",
        category=DIAGNOSTIC,
        read_only=True,
        icon="mdi:sine-wave",
    ),
    *(
        _number(
            f"speaker_distance_{code.lower()}",
            f"SSSDE{code} ",
            query="SSSDE ?",
            platform=SENSOR,
            conv=CONV_CENTI,
            width=4,
            unit="m",
            device_class="distance",
            category=DIAGNOSTIC,
            read_only=True,
            icon="mdi:ruler",
            translation_key="speaker_distance",
            placeholders={"channel": name},
            requires=f"channel_level_{code.lower()}",
        )
        for code, name in CHANNELS.items()
    ),
    *(
        _level(
            f"speaker_level_{code.lower()}",
            f"SSLEV{code} ",
            12,
            query="SSLEV ?",
            platform=SENSOR,
            category=DIAGNOSTIC,
            read_only=True,
            icon="mdi:speaker",
            translation_key="speaker_level",
            placeholders={"channel": name},
            requires=f"channel_level_{code.lower()}",
        )
        for code, name in CHANNELS.items()
    ),
    # ---- Misc ----
    _number(
        "effect_level",
        "PSEFF ",
        min_value=0,
        max_value=15,
        icon="mdi:tune-vertical",
        enabled_default=False,
    ),
    _select(
        "monitor_output",
        "VSMONI",
        {"auto": "AUTO", "monitor_1": "1", "monitor_2": "2"},
        query="VSMONI ?",
        icon="mdi:monitor",
        enabled_default=False,
    ),
    _select(
        "video_select",
        "SV",
        {"off": "OFF", **{source_slug(code): code for code in SOURCES}},
        query="SV?",
        icon="mdi:video-input-hdmi",
        enabled_default=False,
    ),
    # ---- Network audio on-screen display (now playing) ----
    *(
        Setting(key=f"nse{line}", prefix=f"NSE{line}", query="", kind=KIND_TEXT)
        for line in range(9)
    ),
)

SETTINGS_BY_KEY: dict[str, Setting] = {s.key: s for s in SETTINGS}

# Queries that are not tied to a single setting.
EXTRA_QUERIES: tuple[str, ...] = ("NSE", SOUND_MODE_LIST_QUERY, *SOURCE_INFO_QUERIES)

# Queries re-sent after the source or surround mode changed, because those
# change which audio parameters are active.
AUDIO_REFRESH_QUERIES: tuple[str, ...] = (
    "MS?",
    "SD?",
    "DC?",
    "CV?",
    *(s.query for s in SETTINGS if s.prefix.startswith("PS") and s.query),
    "SSINFAISSIG ?",
    "SSINFAISFSV ?",
)


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def all_queries(include_zone2: bool = True) -> list[str]:
    """Return every status query, ordered core state first."""
    queries = [
        s.query
        for s in SETTINGS
        if s.query and (include_zone2 or s.zone != ZONE_2)
    ]
    extra = [q for q in EXTRA_QUERIES if include_zone2 or not q.startswith("Z2")]
    return _dedupe([*queries, *extra])


# Settings grouped by prefix, longest prefix first, for parsing.
_BY_PREFIX: dict[str, list[Setting]] = {}
for _setting in SETTINGS:
    _BY_PREFIX.setdefault(_setting.prefix.rstrip(), []).append(_setting)
_PREFIXES = sorted(_BY_PREFIX, key=len, reverse=True)


def parse_line(line: str) -> list[tuple[Setting, str]]:
    """Parse one line from the receiver into ``(setting, raw value)`` pairs.

    Returns an empty list for lines that are not state reports (e.g. ``CVEND``)
    or that are unknown.
    """
    line = line.rstrip("\r\n")
    if not line or line in ("CVEND", "Z2CVEND"):
        return []
    for prefix in _PREFIXES:
        if not line.startswith(prefix):
            continue
        rest = line[len(prefix) :]
        candidates = _BY_PREFIX[prefix]
        if prefix.startswith("NSE"):
            # Keep leading/trailing spaces out but preserve the text itself.
            return [(candidates[0], clean_text(rest))]
        value = rest.strip()
        # The longest prefix decides; never fall back to a shorter prefix when
        # the value is not accepted (e.g. "MVMAX 98" must not become "MV").
        return [(s, value) for s in candidates if s.accepts(value)]
    return []
