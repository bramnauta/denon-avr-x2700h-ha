"""Tests for the HTTP API parser."""

from __future__ import annotations

import pytest

pytest.importorskip("aiohttp")

from denon_pkg import webapi

# Trimmed from a real AVR-X2700H.
DEVICE_INFO = """<?xml version="1.0" encoding="utf-8" ?>
<Device_Info>
<DeviceInfoVers>0001</DeviceInfoVers>
<CommApiVers>0301</CommApiVers>
<ManualModelName>AVR-X2700H</ManualModelName>
<ModelName>AVR-X2700H</ModelName>
<MacAddress>0005CDAABBCC</MacAddress>
<UpgradeVersion>00</UpgradeVersion>
<DeviceZones>2</DeviceZones>
</Device_Info>"""


def test_device_info() -> None:
    info = webapi.DeviceInfo()
    webapi.parse_device_info(DEVICE_INFO, info)
    assert info.model == "AVR-X2700H"
    assert info.mac == "00:05:cd:aa:bb:cc"
    assert info.firmware is None


def test_bad_xml() -> None:
    info = webapi.DeviceInfo()
    webapi.parse_device_info("<not xml", info)
    assert info.mac is None
