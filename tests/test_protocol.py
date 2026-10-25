"""Tests for the Telnet protocol table and conversions."""

from __future__ import annotations

import pytest

from denon_pkg import protocol as p


def parsed(line: str) -> dict[str, str]:
    return {s.key: v for s, v in p.parse_line(line)}


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("PWON", {"power": "ON"}),
        ("PWSTANDBY", {"power": "STANDBY"}),
        ("ZMON", {"main_power": "ON"}),
        ("MV505", {"volume": "505"}),
        ("MVMAX 98", {"max_volume": "98"}),
        ("MUOFF", {"mute": "OFF"}),
        ("SISAT/CBL", {"source": "SAT/CBL"}),
        ("MSDOLBY ATMOS", {"sound_mode": "DOLBY ATMOS"}),
        ("MSSMART1", {"smart_select": "1"}),
        ("PSDYNEQ ON", {"dynamic_eq": "ON"}),
        ("PSDIL ON", {"dialog_level_adjust": "ON"}),
        ("PSDIL 55", {"dialog_level": "55"}),
        ("PSSWL 485", {"subwoofer_level": "485"}),
        ("PSSWL2 50", {"subwoofer2_level": "50"}),
        ("PSTONE CTRL OFF", {"tone_control": "OFF"}),
        ("PSCINEMA EQ.ON", {"cinema_eq": "ON"}),
        ("PSMULTEQ:BYP.LR", {"multeq": "BYP.LR"}),
        ("PSREFLEV 10", {"reference_level_offset": "10"}),
        ("PSLFE 03", {"lfe_level": "03"}),
        ("PSDELAY 040", {"audio_delay": "040"}),
        ("CVFL 505", {"channel_level_fl": "505"}),
        ("CVSW2 50", {"channel_level_sw2": "50"}),
        ("CVSBL 50", {"channel_level_sbl": "50"}),
        ("CVSB 50", {"channel_level_sb": "50"}),
        ("CVEND", {}),
        ("Z2ON", {"zone2_power": "ON"}),
        ("Z245", {"zone2_volume": "45"}),
        ("Z2SOURCE", {"zone2_source": "SOURCE"}),
        ("Z2SAT/CBL", {"zone2_source": "SAT/CBL"}),
        ("Z2MUON", {"zone2_mute": "ON"}),
        ("Z2CVFL 52", {"zone2_channel_level_fl": "52"}),
        ("Z2SLPOFF", {"zone2_sleep_timer": "OFF"}),
        ("Z2STBY2H", {"zone2_auto_standby": "2H"}),
        ("Z2PSBAS 48", {"zone2_bass": "48"}),
        ("SLP030", {"sleep_timer": "030"}),
        ("SLPOFF", {"sleep_timer": "OFF"}),
        ("ECOAUTO", {"eco_mode": "AUTO"}),
        ("STBY30M", {"auto_standby": "30M"}),
        ("DIM DAR", {"dimmer": "DAR"}),
        ("VSSCH10P", {"hdmi_resolution": "10P"}),
        ("VSSC4K", {"video_resolution": "4K"}),
        ("VSASPFUL", {"aspect_ratio": "FUL"}),
        ("VSAUDIO AMP", {"hdmi_audio_output": "AMP"}),
        ("VSVPMGAME", {"video_processing_mode": "GAME"}),
        ("TFAN008750", {"tuner_frequency": "008750"}),
        # Captured from a real AVR-X2700H.
        ("MSDOLBY AUDIO-DSUR", {"sound_mode": "DOLBY AUDIO-DSUR"}),
        ("MSQUICK0", {"quick_select": "0"}),
        ("Z2QUICK0", {"zone2_quick_select": "0"}),
        ("MVMAX 60", {"max_volume": "60"}),
        ("SYSMI Dolby Audio - Dolby Surround", {"sound_mode_info": "Dolby Audio - Dolby Surround"}),
        ("SYSDA PCM                  ", {"audio_format": "PCM"}),
        ("SSINFAISFOR 2/0/.0", {"audio_channels": "2/0/.0"}),
        ("SSINFAISFSV 48K", {"audio_sampling_rate": "48K"}),
        ("SSINFAISSIG 02", {"audio_input_signal": "02"}),
        ("PSSPV ON", {"speaker_virtualizer": "ON"}),
        ("BTTX OFF", {"bluetooth_transmitter": "OFF"}),
        ("BTTX SP", {"bluetooth_output": "SP"}),
        ("PVOFF", {"picture_mode": "OFF"}),
        ("VSSCHAUTO", {"hdmi_resolution": "AUTO"}),
        ("PSREFLEV 0", {"reference_level_offset": "0"}),
        ("PSMULTEQ:OFF", {"multeq": "OFF"}),
        ("CVSL 53", {"channel_level_sl": "53"}),
        ("Z2OFF", {"zone2_power": "OFF"}),
        ("Z240", {"zone2_volume": "40"}),
        ("OPSMLALL MOV010Stereo", {}),
        ("SSSPCFRO SMA", {"speaker_size_fro": "SMA"}),
        ("SSSPCSBK NON", {"speaker_size_sbk": "NON"}),
        ("SSSPCSBK 2SP", {"surround_back_speakers": "2SP"}),
        ("SSSPCSWF YES", {"subwoofer_present": "YES"}),
        ("SSSDEFL 0360", {"speaker_distance_fl": "0360"}),
        ("SSSDESBL 0300", {"speaker_distance_sbl": "0300"}),
        ("SSSDESB 0300", {"speaker_distance_sb": "0300"}),
        ("SSSDESW 0360", {"speaker_distance_sw": "0360"}),
        ("SSSDESTP 01M", {}),
        ("SSCFRFRO 080", {"crossover_fro": "080"}),
        ("SSCFR ALL", {"crossover_mode": "ALL"}),
        ("SSCFRALL 090", {"crossover_all": "090"}),
        ("SSCFR END", {}),
        ("SSLEVC 545", {"speaker_level_c": "545"}),
        ("SSLEV END", {}),
        ("PSEFF 00", {"effect_level": "00"}),
        ("VSMONIAUTO", {"monitor_output": "AUTO"}),
        ("SVOFF", {"video_select": "OFF"}),
        ("SVSAT/CBL", {"video_select": "SAT/CBL"}),
        ("TFANNAMERADIO 2", {"tuner_station": "RADIO 2"}),
        ("TPAN03", {"tuner_preset": "03"}),
        ("TMANFM", {"tuner_band": "FM"}),
        ("TMANAUTO", {"tuner_mode": "AUTO"}),
        ("SPPR 2", {"speaker_preset": "2"}),
        ("SDHDMI", {"input_mode": "HDMI"}),
        ("DCAUTO", {"digital_input": "AUTO"}),
        ("NSE1\x01Some Title", {"nse1": "Some Title"}),
        ("MNMEN OFF", {"setup_menu": "OFF"}),
        ("XYZUNKNOWN", {}),
        ("MVGARBAGE", {}),
    ],
)
def test_parse_line(line: str, expected: dict[str, str]) -> None:
    assert parsed(line) == expected


def test_volume_conversion() -> None:
    assert p.parse_volume("50") == 50.0
    assert p.parse_volume("505") == 50.5
    assert p.parse_volume("00") == 0.0
    assert p.format_volume(50.5) == "505"
    assert p.format_volume(50) == "50"
    assert p.format_volume(0.5) == "005"
    assert p.format_volume(-3) == "00"


@pytest.mark.parametrize(
    ("key", "raw", "value"),
    [
        ("volume", "505", -29.5),
        ("volume", "80", 0.0),
        ("max_volume", "98", 18.0),
        ("bass", "44", -6.0),
        ("channel_level_c", "535", 3.5),
        ("lfe_level", "05", -5),
        ("audio_delay", "120", 120),
        ("sleep_timer", "OFF", 0),
        ("sleep_timer", "090", 90),
        ("power", "STANDBY", False),
        ("power", "ON", True),
        ("multeq", "BYP.LR", "bypass_lr"),
        ("dimmer", "BRI", "bright"),
    ],
)
def test_decode(key: str, raw: str, value: object) -> None:
    assert p.SETTINGS_BY_KEY[key].decode(raw) == value


@pytest.mark.parametrize(
    ("key", "value", "command"),
    [
        ("volume", -29.5, "MV505"),
        ("volume", -80, "MV00"),
        ("zone2_volume", -35, "Z245"),
        ("bass", 2, "PSBAS 52"),
        ("dialog_level", -1.5, "PSDIL 485"),
        ("channel_level_fl", 1, "CVFL 51"),
        ("lfe_level", -7, "PSLFE 07"),
        ("audio_delay", 5, "PSDELAY 005"),
        ("sleep_timer", 0, "SLPOFF"),
        ("sleep_timer", 60, "SLP060"),
        ("power", False, "PWSTANDBY"),
        ("dynamic_eq", True, "PSDYNEQ ON"),
        ("cinema_eq", False, "PSCINEMA EQ.OFF"),
        ("multeq", "audyssey", "PSMULTEQ:AUDYSSEY"),
        ("dimmer", "dark", "DIM DAR"),
        ("speaker_preset", "preset_2", "SPPR 2"),
        ("video_processing_mode", "movie", "VSVPMMOVI"),
        ("zone2_hpf", True, "Z2HPFON"),
        ("tuner_band", "am", "TMANAM"),
        ("zone2_auto_standby", "off", "Z2STBYOFF"),
    ],
)
def test_encode(key: str, value: object, command: str) -> None:
    assert p.SETTINGS_BY_KEY[key].encode(value) == command


def test_encode_rejects_bad_option() -> None:
    with pytest.raises(ValueError):
        p.SETTINGS_BY_KEY["dimmer"].encode("nope")


def test_read_only_cannot_be_set() -> None:
    with pytest.raises(ValueError):
        p.SETTINGS_BY_KEY["sound_mode"].encode("STEREO")


def test_every_exposed_value_round_trips() -> None:
    """Every select option and number step must parse back to itself."""
    for setting in p.SETTINGS:
        if setting.read_only or setting.platform is None:
            continue
        if setting.kind == p.KIND_SELECT:
            for option in setting.options:
                line = setting.encode(option)
                assert setting.key in parsed(line), line
                assert setting.decode(parsed(line)[setting.key]) == option
        if setting.kind == p.KIND_NUMBER:
            for value in (setting.min_value, setting.max_value):
                line = setting.encode(value)
                assert setting.key in parsed(line), line
                assert setting.decode(parsed(line)[setting.key]) == value, line


def test_unique_keys_and_queries() -> None:
    keys = [s.key for s in p.SETTINGS]
    assert len(keys) == len(set(keys))
    queries = p.all_queries()
    assert len(queries) == len(set(queries))
    assert "PW?" in queries
    assert all(not q.startswith("Z2") for q in p.all_queries(include_zone2=False))


def test_tuner_frequency() -> None:
    assert p.format_tuner_frequency("008750") == "87.50 MHz"
    assert p.format_tuner_frequency("010120") == "101.20 MHz"
    assert p.format_tuner_frequency("074700") == "747 kHz"
    assert p.encode_tuner_frequency(101.2) == "TFAN010120"
    assert p.encode_tuner_frequency(87.5) == "TFAN008750"
    assert p.encode_tuner_frequency(747) == "TFAN074700"


def test_volume_level_mapping() -> None:
    assert p.volume_to_level(-80, 0) == 0.0
    assert p.volume_to_level(0, 0) == 1.0
    assert p.volume_to_level(10, 0) == 1.0
    assert p.level_to_volume(0.5, 0) == -40.0
    assert p.level_to_volume(1.0, -10) == -10.0


def test_source_info() -> None:
    assert p.parse_source_info("SSFUNMPLAY TV Streamer     ") == ("name", "MPLAY", "TV Streamer")
    assert p.parse_source_info("SSFUNSAT/CBL CBL/SAT         ") == ("name", "SAT/CBL", "CBL/SAT")
    assert p.parse_source_info("SSSODDVD DEL") == ("usage", "DVD", "DEL")
    assert p.parse_source_info("SSSOD8K DEL") == ("usage", "8K", "DEL")
    assert p.parse_source_info("SSFUN END") is None
    assert p.parse_source_info("SSSOD END") is None
    assert p.parse_source_info("SIMPLAY") is None


def test_speaker_setup_decoding() -> None:
    assert p.SETTINGS_BY_KEY["speaker_distance_fl"].decode("0360") == 3.6
    assert p.SETTINGS_BY_KEY["speaker_level_c"].decode("545") == 4.5
    assert p.SETTINGS_BY_KEY["crossover_fro"].decode("080") == 80
    assert p.SETTINGS_BY_KEY["speaker_size_sbk"].decode("NON") == "none"
    assert p.SETTINGS_BY_KEY["crossover_fro"].requires == "speaker_size_fro"


def test_sound_mode_list() -> None:
    assert p.parse_sound_mode_item("OPSMLALL MOV021Dolby Audio - Dolby Surround") == (
        2,
        "Dolby Audio - Dolby Surround",
        True,
    )
    assert p.parse_sound_mode_item("OPSMLALL PUR110Pure Direct") == (11, "Pure Direct", False)
    assert p.parse_sound_mode_item("OPSMLALL END") is None
    assert p.parse_sound_mode_item("OPSML 010Stereo") is None


@pytest.mark.parametrize(
    ("name", "command"),
    [
        # Verified on an AVR-X2700H.
        ("Stereo", "STEREO"),
        ("Dolby Audio - Dolby Surround", "DOLBY DIGITAL"),
        ("Multi Ch Stereo", "MCH STEREO"),
        ("Direct", "DIRECT"),
        # From the fallback list / raw values.
        ("Pure Direct", "PURE DIRECT"),
        ("Movie", "MOVIE"),
        ("MCH STEREO", "MCH STEREO"),
        ("DTS Neural:X", "DTS SURROUND"),
    ],
)
def test_sound_mode_command(name: str, command: str) -> None:
    assert p.sound_mode_command(name) == command


def test_sound_modes() -> None:
    assert p.sound_mode_from_raw("PURE DIRECT") == "Pure Direct"
    assert p.sound_mode_from_raw("DOLBY ATMOS") == "DOLBY ATMOS"
