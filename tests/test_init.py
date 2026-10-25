"""End-to-end setup test inside Home Assistant against a fake receiver.

Skipped unless pytest-homeassistant-custom-component is installed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.denon_avr_x2700h import client as ha_client
from custom_components.denon_avr_x2700h.const import DOMAIN
from custom_components.denon_avr_x2700h.webapi import DeviceInfo
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .test_client import STATE, FakeReceiver


@pytest.fixture(autouse=True)
def _custom(enable_custom_integrations):
    yield


async def test_setup_and_control(
    socket_enabled, hass: HomeAssistant, monkeypatch
) -> None:
    monkeypatch.setattr(ha_client, "COMMAND_INTERVAL", 0.001)
    STATE["Z2?"] = ["Z2ON", "Z2TUNER", "Z240"]
    fake = FakeReceiver()
    port = await fake.start()

    real_client = ha_client.DenonClient

    def make_client(host, **kwargs):
        return real_client(host, port, **kwargs)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Denon AVR-X2700H",
        data={CONF_HOST: "127.0.0.1"},
        unique_id="00:05:cd:aa:bb:cc",
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.denon_avr_x2700h.DenonClient", make_client),
        patch(
            "custom_components.denon_avr_x2700h.async_get_device_info",
            return_value=DeviceInfo(mac="00:05:cd:aa:bb:cc"),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("media_player.denon_avr_x2700h")
    assert state is not None, sorted(hass.states.async_entity_ids())
    assert state.state == "on"
    assert state.attributes["source"] == "TV Audio"
    assert state.attributes["volume_db"] == -35.0
    assert state.attributes["sound_mode"] == "Stereo"
    assert "TV Streamer" in state.attributes["source_list"]
    assert "DVD" not in state.attributes["source_list"]
    assert state.attributes["sound_mode_list"] == [
        "Stereo",
        "Dolby Audio - Dolby Surround",
        "Direct",
    ]

    # Speaker setup sensors exist only for speakers that are present.
    assert hass.states.get("sensor.denon_avr_x2700h_distance_front_left").state == "3.6"
    assert hass.states.get("sensor.denon_avr_x2700h_distance_top_front_left") is None
    assert hass.states.get("sensor.denon_avr_x2700h_crossover_front").state == "80"
    assert hass.states.get("sensor.denon_avr_x2700h_crossover_surround_back") is None
    assert hass.states.get("sensor.denon_avr_x2700h_speaker_front").state == "small"

    zone2 = hass.states.get("media_player.denon_avr_x2700h_zone_2")
    assert zone2 is not None and zone2.state == "on"
    assert zone2.attributes["source"] == "Tuner"

    assert hass.states.get("switch.denon_avr_x2700h_audyssey_dynamic_eq").state == "on"
    assert hass.states.get("number.denon_avr_x2700h_channel_level_center").state == "2.0"
    assert hass.states.get("sensor.denon_avr_x2700h_surround_mode").state == "STEREO"
    # Not reported by the receiver -> no entity.
    assert hass.states.get("number.denon_avr_x2700h_channel_level_surround_left") is None

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.denon_avr_x2700h_audyssey_dynamic_eq"},
        blocking=True,
    )
    # The receiver keeps DRC off for PCM; the user gets an error, not silence.
    drc = "select.denon_avr_x2700h_dynamic_range_compression"
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "select", "select_option", {"entity_id": drc, "option": "low"}, blocking=True
        )
    assert err.value.translation_key == "not_accepted"
    assert hass.states.get(drc).state == "off"

    await hass.services.async_call(
        "media_player",
        "select_source",
        # Blu-ray is renamed to "BD" on the (fake) receiver.
        {"entity_id": "media_player.denon_avr_x2700h", "source": "BD"},
        blocking=True,
    )
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": "media_player.denon_avr_x2700h", "volume_level": 0.5},
        blocking=True,
    )
    response = await hass.services.async_call(
        DOMAIN,
        "send_command",
        {"entity_id": "media_player.denon_avr_x2700h", "command": "MV?", "wait": 0.2},
        blocking=True,
        return_response=True,
    )
    assert "MV45" in response["media_player.denon_avr_x2700h"]["response"]
    await hass.async_block_till_done()
    assert "PSDYNEQ OFF" in fake.received
    assert "SIBD" in fake.received
    assert "MV40" in fake.received  # 50% of -80..0 dB = -40 dB

    assert await hass.config_entries.async_unload(entry.entry_id)
    await fake.stop()
    del STATE["Z2?"]
