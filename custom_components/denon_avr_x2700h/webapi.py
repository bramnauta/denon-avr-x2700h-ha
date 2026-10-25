"""Read-only access to the receiver's HTTP API (port 8080).

Only used for what Telnet cannot tell us: the model and the MAC address
(the unique id). Source names come from Telnet (SSFUN / SSSOD).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import xml.etree.ElementTree as ET

import aiohttp

from .protocol import HTTP_PORT

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=8)


@dataclass
class DeviceInfo:
    """Static information about the receiver."""

    model: str = "AVR-X2700H"
    mac: str | None = None
    firmware: str | None = None


def _text(root: ET.Element, path: str) -> str | None:
    node = root.find(path)
    if node is None or node.text is None:
        return None
    return node.text.strip() or None


def _format_mac(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isalnum()).lower()
    if len(digits) != 12:
        return None
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


def parse_device_info(xml: str, info: DeviceInfo) -> None:
    """Fill ``info`` from /goform/Deviceinfo.xml."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return
    if model := _text(root, "ModelName") or _text(root, "ManualModelName"):
        info.model = model.lstrip("*").strip()
    info.mac = _format_mac(_text(root, "MacAddress")) or info.mac
    # The X2700H reports "00" here; only keep a real version string.
    version = _text(root, "UpgradeVersion")
    if version and version.strip("0"):
        info.firmware = version


async def async_get_device_info(
    session: aiohttp.ClientSession, host: str, port: int = HTTP_PORT
) -> DeviceInfo:
    """Collect device information; falls back to defaults on any error."""
    info = DeviceInfo()
    url = f"http://{host}:{port}/goform/Deviceinfo.xml"
    try:
        async with session.get(url, timeout=TIMEOUT) as resp:
            if resp.status == 200:
                parse_device_info(await resp.text(), info)
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.debug("GET %s failed: %s", url, err)
    return info
