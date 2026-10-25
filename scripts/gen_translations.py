"""Generate strings.json and translations/{en,nl}.json.

Entity names and select options come from the setting table in protocol.py,
so every exposed setting is guaranteed to have a name in both languages.

Run: python scripts/gen_translations.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "denon_avr_x2700h"

spec = importlib.util.spec_from_file_location("protocol", COMPONENT / "protocol.py")
protocol = importlib.util.module_from_spec(spec)
sys.modules["protocol"] = protocol
spec.loader.exec_module(protocol)

# key: (English, Dutch)
NAMES: dict[str, tuple[str, str]] = {
    "sound_mode": ("Surround mode", "Surroundmodus"),
    "sound_mode_info": ("Surround mode (display)", "Surroundmodus (display)"),
    "audio_format": ("Audio format", "Audioformaat"),
    "audio_channels": ("Input channels", "Ingangskanalen"),
    "speaker_virtualizer": ("Speaker virtualizer", "Speaker virtualizer"),
    "bluetooth_transmitter": ("Bluetooth transmitter", "Bluetooth-zender"),
    "bluetooth_output": ("Bluetooth output", "Bluetooth-uitvoer"),
    "picture_mode": ("Picture mode", "Beeldmodus"),
    "speaker_size": ("Speaker {position}", "Luidspreker {position}"),
    "surround_back_speakers": ("Surround back speakers", "Surround back-luidsprekers"),
    "subwoofer_present": ("Subwoofer", "Subwoofer"),
    "crossover": ("Crossover {position}", "Crossover {position}"),
    "crossover_mode": ("Crossover mode", "Crossovermodus"),
    "crossover_all": ("Crossover (all)", "Crossover (alle)"),
    "speaker_distance": ("Distance {channel}", "Afstand {channel}"),
    "speaker_level": ("Calibrated level {channel}", "Gekalibreerd niveau {channel}"),
    "effect_level": ("Effect level", "Effectniveau"),
    "monitor_output": ("Monitor output", "Monitoruitgang"),
    "video_select": ("Video select", "Videoselectie"),
    "volume": ("Volume", "Volume"),
    "max_volume": ("Maximum volume", "Maximaal volume"),
    "power": ("System power", "Systeemvoeding"),
    "eco_mode": ("ECO mode", "ECO-modus"),
    "auto_standby": ("Auto standby", "Automatische stand-by"),
    "dimmer": ("Display dimmer", "Displaydimmer"),
    "sleep_timer": ("Sleep timer", "Slaaptimer"),
    "speaker_preset": ("Speaker preset", "Luidsprekerpreset"),
    "setup_menu": ("Setup menu", "Instellingenmenu"),
    "all_zone_stereo": ("All zone stereo", "All Zone Stereo"),
    "input_mode": ("Input mode", "Ingangsmodus"),
    "digital_input": ("Digital input decode", "Digitale ingang decodering"),
    "tone_control": ("Tone control", "Toonregeling"),
    "bass": ("Bass", "Lage tonen"),
    "treble": ("Treble", "Hoge tonen"),
    "dialog_level_adjust": ("Dialog level adjust", "Dialoogniveau aanpassen"),
    "dialog_level": ("Dialog level", "Dialoogniveau"),
    "subwoofer_level_adjust": ("Subwoofer level adjust", "Subwooferniveau aanpassen"),
    "subwoofer_level": ("Subwoofer level", "Subwooferniveau"),
    "subwoofer2_level": ("Subwoofer 2 level", "Subwoofer 2 niveau"),
    "cinema_eq": ("Cinema EQ", "Cinema EQ"),
    "multeq": ("Audyssey MultEQ", "Audyssey MultEQ"),
    "dynamic_eq": ("Audyssey Dynamic EQ", "Audyssey Dynamic EQ"),
    "reference_level_offset": ("Reference level offset", "Referentieniveau-offset"),
    "dynamic_volume": ("Audyssey Dynamic Volume", "Audyssey Dynamic Volume"),
    "lfc": ("Audyssey LFC", "Audyssey LFC"),
    "containment_amount": ("LFC containment amount", "LFC containment-niveau"),
    "graphic_eq": ("Graphic EQ", "Grafische EQ"),
    "headphone_eq": ("Headphone EQ", "Hoofdtelefoon-EQ"),
    "dynamic_range_compression": ("Dynamic range compression", "Dynamisch bereikcompressie"),
    "lfe_level": ("LFE level", "LFE-niveau"),
    "audio_delay": ("Audio delay", "Audiovertraging"),
    "audio_restorer": ("Compressed audio restorer", "Audio restorer"),
    "dialog_enhancer": ("Dialog enhancer", "Dialoogversterker"),
    "center_spread": ("Center spread", "Center spread"),
    "neural_x": ("DTS Neural:X", "DTS Neural:X"),
    "loudness_management": ("Loudness management", "Loudness management"),
    "subwoofer_direct": ("Subwoofer in Direct/Stereo", "Subwoofer in Direct/Stereo"),
    "aspect_ratio": ("Aspect ratio", "Beeldverhouding"),
    "video_resolution": ("Video resolution", "Videoresolutie"),
    "hdmi_resolution": ("HDMI output resolution", "HDMI-uitgangsresolutie"),
    "hdmi_audio_output": ("HDMI audio output", "HDMI-audio-uitgang"),
    "video_processing_mode": ("Video processing mode", "Videoverwerkingsmodus"),
    "vertical_stretch": ("Vertical stretch", "Verticaal uitrekken"),
    "tuner_frequency": ("Tuner frequency", "Tunerfrequentie"),
    "tuner_station": ("Tuner station", "Tunerzender"),
    "tuner_preset": ("Tuner preset", "Tunerpreset"),
    "tuner_band": ("Tuner band", "Tunerband"),
    "tuner_mode": ("Tuner tuning mode", "Tuner afstemmodus"),
    "audio_input_signal": ("Audio input signal", "Audio-ingangssignaal"),
    "audio_sampling_rate": ("Audio sampling rate", "Audio-samplefrequentie"),
    "zone2_volume": ("Volume", "Volume"),
    "zone2_channel_setting": ("Channel setting", "Kanaalinstelling"),
    "zone2_bass": ("Bass", "Lage tonen"),
    "zone2_treble": ("Treble", "Hoge tonen"),
    "zone2_hpf": ("High-pass filter", "Hoogdoorlaatfilter"),
    "zone2_sleep_timer": ("Sleep timer", "Slaaptimer"),
    "zone2_auto_standby": ("Auto standby", "Automatische stand-by"),
    "channel_level": ("Channel level {channel}", "Kanaalniveau {channel}"),
}

OPTIONS: dict[str, tuple[str, str]] = {
    "on": ("On", "Aan"),
    "off": ("Off", "Uit"),
    "auto": ("Auto", "Automatisch"),
    "15m": ("15 minutes", "15 minuten"),
    "30m": ("30 minutes", "30 minuten"),
    "60m": ("60 minutes", "60 minuten"),
    "2h": ("2 hours", "2 uur"),
    "4h": ("4 hours", "4 uur"),
    "8h": ("8 hours", "8 uur"),
    "bright": ("Bright", "Helder"),
    "dim": ("Dim", "Gedimd"),
    "dark": ("Dark", "Donker"),
    "preset_1": ("Preset 1", "Preset 1"),
    "preset_2": ("Preset 2", "Preset 2"),
    "hdmi": ("HDMI", "HDMI"),
    "digital": ("Digital", "Digitaal"),
    "analog": ("Analog", "Analoog"),
    "pcm": ("PCM", "PCM"),
    "dts": ("DTS", "DTS"),
    "audyssey": ("Audyssey", "Audyssey"),
    "bypass_lr": ("Bypass L/R", "Bypass L/R"),
    "flat": ("Flat", "Vlak"),
    "0db": ("0 dB", "0 dB"),
    "5db": ("5 dB", "5 dB"),
    "10db": ("10 dB", "10 dB"),
    "15db": ("15 dB", "15 dB"),
    "heavy": ("Heavy", "Zwaar"),
    "medium": ("Medium", "Gemiddeld"),
    "light": ("Light", "Licht"),
    "low": ("Low", "Laag"),
    "mid": ("Mid", "Midden"),
    "high": ("High", "Hoog"),
    "mode1": ("Mode 1", "Modus 1"),
    "mode2": ("Mode 2", "Modus 2"),
    "mode3": ("Mode 3", "Modus 3"),
    "normal": ("Normal", "Normaal"),
    "full": ("Full", "Volledig"),
    "480p": ("480p/576p", "480p/576p"),
    "1080i": ("1080i", "1080i"),
    "720p": ("720p", "720p"),
    "1080p": ("1080p", "1080p"),
    "1080p24": ("1080p 24 Hz", "1080p 24 Hz"),
    "4k": ("4K", "4K"),
    "4k60": ("4K 60/50 Hz", "4K 60/50 Hz"),
    "8k": ("8K", "8K"),
    "amp": ("AVR", "AVR"),
    "tv": ("TV", "TV"),
    "game": ("Game", "Game"),
    "movie": ("Movie", "Film"),
    "bypass": ("Bypass", "Bypass"),
    "am": ("AM", "AM"),
    "fm": ("FM", "FM"),
    "manual": ("Manual", "Handmatig"),
    "stereo": ("Stereo", "Stereo"),
    "mono": ("Mono", "Mono"),
    "bluetooth_speakers": ("Bluetooth + speakers", "Bluetooth + luidsprekers"),
    "bluetooth_only": ("Bluetooth only", "Alleen Bluetooth"),
    "standard": ("Standard", "Standaard"),
    "vivid": ("Vivid", "Levendig"),
    "stream": ("Streaming", "Streaming"),
    "custom": ("Custom", "Aangepast"),
    "isf_day": ("ISF Day", "ISF dag"),
    "isf_night": ("ISF Night", "ISF nacht"),
    "small": ("Small", "Klein"),
    "large": ("Large", "Groot"),
    "none": ("None", "Geen"),
    "one": ("1 speaker", "1 luidspreker"),
    "two": ("2 speakers", "2 luidsprekers"),
    "yes": ("Yes", "Ja"),
    "no": ("No", "Nee"),
    "all": ("All", "Alle"),
    "individual": ("Individual", "Individueel"),
    "monitor_1": ("Monitor 1", "Monitor 1"),
    "monitor_2": ("Monitor 2", "Monitor 2"),
    # Video select: one option per source, named after the source.
    **{
        protocol.source_slug(code): (name, name)
        for code, name in protocol.SOURCES.items()
        if protocol.source_slug(code) not in ("game", "tv")
    },
}

BUTTONS: dict[str, tuple[str, str]] = {
    "cursor_up": ("Cursor up", "Cursor omhoog"),
    "cursor_down": ("Cursor down", "Cursor omlaag"),
    "cursor_left": ("Cursor left", "Cursor links"),
    "cursor_right": ("Cursor right", "Cursor rechts"),
    "cursor_enter": ("Enter", "Enter"),
    "menu_back": ("Back", "Terug"),
    "menu_option": ("Option", "Optie"),
    "menu_info": ("Info", "Info"),
    "quick_select": ("Quick Select {slot}", "Quick Select {slot}"),
    "tuner_preset_up": ("Tuner next preset", "Tuner volgende preset"),
    "tuner_preset_down": ("Tuner previous preset", "Tuner vorige preset"),
    "tuner_frequency_up": ("Tuner frequency up", "Tunerfrequentie omhoog"),
    "tuner_frequency_down": ("Tuner frequency down", "Tunerfrequentie omlaag"),
    "channel_levels_reset": ("Reset channel levels", "Kanaalniveaus resetten"),
    "sound_mode_next": ("Next surround mode", "Volgende surroundmodus"),
    "sound_mode_previous": ("Previous surround mode", "Vorige surroundmodus"),
    "refresh": ("Refresh status", "Status verversen"),
    "panel_lock": ("Lock front panel", "Frontpaneel vergrendelen"),
    "panel_volume_lock": ("Lock front panel and volume", "Frontpaneel en volume vergrendelen"),
    "panel_unlock": ("Unlock front panel", "Frontpaneel ontgrendelen"),
    "remote_lock": ("Lock remote control", "Afstandsbediening vergrendelen"),
    "remote_unlock": ("Unlock remote control", "Afstandsbediening ontgrendelen"),
}

TEXT = {
    "en": {
        "exceptions": {
            "not_accepted": {
                "message": "The receiver did not accept {value} for {entity}. This setting is probably not available for the current input signal or surround mode.",
            },
        },
        "config": {
            "flow_title": "{name}",
            "step": {
                "user": {
                    "title": "Denon AVR-X2700H",
                    "description": "Enter the IP address of the receiver. Network control must be set to Always On, and no other Telnet client may be connected.",
                    "data": {"host": "Host", "name": "Name"},
                },
                "confirm": {
                    "title": "Denon AVR-X2700H",
                    "description": "Add {name} ({host})?",
                },
                "reconfigure": {
                    "title": "Change host",
                    "data": {"host": "Host"},
                },
            },
            "error": {
                "cannot_connect": "Cannot connect on Telnet port 23. Check the IP address, enable network control and make sure no other Telnet client is connected.",
            },
            "abort": {
                "already_configured": "This receiver is already configured.",
                "reconfigure_successful": "The receiver has been reconfigured.",
                "cannot_connect": "Cannot connect to the receiver.",
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": "Options",
                    "data": {
                        "zone2": "Enable Zone 2",
                        "max_volume": "Volume at 100% (dB)",
                        "volume_step": "Volume step (dB)",
                    },
                    "data_description": {
                        "max_volume": "Upper limit for the media player volume slider; 0 dB is a safe default.",
                    },
                }
            }
        },
        "services": {
            "send_command": {
                "name": "Send command",
                "description": "Send raw Telnet commands to the receiver and return the lines it answered.",
                "fields": {
                    "command": {"name": "Command", "description": "One or more commands, e.g. PSDYNEQ ON or MV?."},
                    "wait": {"name": "Wait", "description": "Seconds to collect answers."},
                },
            },
            "save_quick_select": {
                "name": "Save Quick Select",
                "description": "Store the current settings in a Quick Select slot.",
                "fields": {"slot": {"name": "Slot", "description": "Slot 1-4."}},
            },
            "set_tuner_frequency": {
                "name": "Set tuner frequency",
                "description": "Tune the radio to a frequency.",
                "fields": {"frequency": {"name": "Frequency", "description": "MHz for FM (e.g. 101.2), kHz for AM (e.g. 747)."}},
            },
            "refresh": {
                "name": "Refresh",
                "description": "Read every status value from the receiver again.",
            },
        },
    },
    "nl": {
        "exceptions": {
            "not_accepted": {
                "message": "De receiver heeft {value} voor {entity} niet geaccepteerd. Deze instelling is waarschijnlijk niet beschikbaar voor het huidige ingangssignaal of de surroundmodus.",
            },
        },
        "config": {
            "flow_title": "{name}",
            "step": {
                "user": {
                    "title": "Denon AVR-X2700H",
                    "description": "Vul het IP-adres van de receiver in. Netwerkbesturing moet op Altijd aan staan en er mag geen andere Telnet-client verbonden zijn.",
                    "data": {"host": "Host", "name": "Naam"},
                },
                "confirm": {
                    "title": "Denon AVR-X2700H",
                    "description": "{name} ({host}) toevoegen?",
                },
                "reconfigure": {
                    "title": "Host wijzigen",
                    "data": {"host": "Host"},
                },
            },
            "error": {
                "cannot_connect": "Kan niet verbinden op Telnet-poort 23. Controleer het IP-adres, zet netwerkbesturing aan en zorg dat er geen andere Telnet-client verbonden is.",
            },
            "abort": {
                "already_configured": "Deze receiver is al geconfigureerd.",
                "reconfigure_successful": "De receiver is opnieuw geconfigureerd.",
                "cannot_connect": "Kan niet verbinden met de receiver.",
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": "Opties",
                    "data": {
                        "zone2": "Zone 2 inschakelen",
                        "max_volume": "Volume bij 100% (dB)",
                        "volume_step": "Volumestap (dB)",
                    },
                    "data_description": {
                        "max_volume": "Bovengrens van de volumeschuif van de mediaspeler; 0 dB is een veilige standaard.",
                    },
                }
            }
        },
        "services": {
            "send_command": {
                "name": "Commando versturen",
                "description": "Stuur ruwe Telnet-commando's naar de receiver en geef de antwoorden terug.",
                "fields": {
                    "command": {"name": "Commando", "description": "Een of meer commando's, bijv. PSDYNEQ ON of MV?."},
                    "wait": {"name": "Wachttijd", "description": "Seconden om antwoorden te verzamelen."},
                },
            },
            "save_quick_select": {
                "name": "Quick Select opslaan",
                "description": "Sla de huidige instellingen op in een Quick Select-geheugen.",
                "fields": {"slot": {"name": "Geheugen", "description": "Geheugen 1-4."}},
            },
            "set_tuner_frequency": {
                "name": "Tunerfrequentie instellen",
                "description": "Stem de radio af op een frequentie.",
                "fields": {"frequency": {"name": "Frequentie", "description": "MHz voor FM (bijv. 101.2), kHz voor AM (bijv. 747)."}},
            },
            "refresh": {
                "name": "Verversen",
                "description": "Lees alle statuswaarden opnieuw uit de receiver.",
            },
        },
    },
}


def build(lang: int, code: str) -> dict:
    entity: dict[str, dict] = {}
    missing = []
    for setting in protocol.SETTINGS:
        if setting.platform is None:
            continue
        key = setting.translation_key or setting.key
        if key not in NAMES:
            missing.append(key)
            continue
        platform = entity.setdefault(setting.platform, {})
        item = platform.setdefault(key, {"name": NAMES[key][lang]})
        if setting.options:
            item["state"] = {}
            for option in setting.options:
                if option not in OPTIONS:
                    missing.append(f"option {option}")
                    continue
                item["state"][option] = OPTIONS[option][lang]
    entity["button"] = {k: {"name": v[lang]} for k, v in BUTTONS.items()}
    if missing:
        raise SystemExit(f"Missing translations: {sorted(set(missing))}")
    return {**TEXT[code], "entity": entity}


def main() -> None:
    en = build(0, "en")
    nl = build(1, "nl")
    out = COMPONENT / "translations"
    out.mkdir(exist_ok=True)
    for path, data in (
        (COMPONENT / "strings.json", en),
        (out / "en.json", en),
        (out / "nl.json", nl),
    ):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
