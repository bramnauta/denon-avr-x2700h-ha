"""Tests for the Telnet client against a fake receiver."""

from __future__ import annotations

import asyncio

from denon_pkg import client as client_mod
from denon_pkg.client import DenonClient, async_probe

STATE = {
    "PW?": ["PWON"],
    "ZM?": ["ZMON"],
    "MV?": ["MV45", "MVMAX 98"],
    "MU?": ["MUOFF"],
    "SI?": ["SITV"],
    "MS?": ["MSSTEREO"],
    "CV?": ["CVFL 50", "CVFR 50", "CVC 52", "CVSW 485", "CVEND"],
    "PSDYNEQ ?": ["PSDYNEQ ON"],
    # As reported by a real AVR-X2700H.
    "SSSOD ?": ["SSSODDVD DEL", "SSSODBD USE", "SSSODTV USE", "SSSODMPLAY USE", "SSSOD END"],
    # With a stereo PCM signal DRC is forced off and LFE changes are ignored.
    "PSDRC ?": ["PSDRC OFF"],
    "PSDRC LOW": ["PSDRC OFF"],
    "PSDRC OFF": ["PSDRC OFF"],
    "PSLFE ?": ["PSLFE 00"],
    "PSLFE 05": [],
    # A setting the receiver really refuses: answers with its kept value.
    "DIM ?": ["DIM DIM"],
    "DIM BRI": ["DIM DIM"],
    "SSFUN ?": ["SSFUNBD BD              ", "SSFUNMPLAY TV Streamer     ", "SSFUN END"],
    "OPSML ?": [
        "OPSML 010Stereo",
        "OPSML END",
        "OPSMLALL MOV010Stereo",
        "OPSMLALL MOV021Dolby Audio - Dolby Surround",
        "OPSMLALL MUS040Stereo",
        "OPSMLALL PUR100Direct",
        "OPSMLALL END",
    ],
    "SSSPC ?": ["SSSPCFRO SMA", "SSSPCSBK NON", "SSSPCSWF YES"],
    "SSCFR ?": ["SSCFRFRO 080", "SSCFRSBK 080", "SSCFR END"],
    "SSSDE ?": ["SSSDEFL 0360", "SSSDETFL 0300", "SSSDESTP 01M", "SSSDE END"],
}


class FakeReceiver:
    """Minimal Denon Telnet emulation."""

    def __init__(self) -> None:
        self.received: list[str] = []
        self.server: asyncio.Server | None = None
        self.writers: list[asyncio.StreamWriter] = []

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for writer in self.writers:
            writer.close()
        assert self.server is not None
        self.server.close()
        await self.server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.writers.append(writer)
        try:
            while data := await reader.readuntil(b"\r"):
                command = data.decode().strip()
                self.received.append(command)
                replies = STATE.get(command, [])
                if command == "PSDYNEQ OFF":
                    replies = ["PSDYNEQ OFF"]
                if command == "MV50":
                    replies = ["MV50", "MVMAX 98"]
                for reply in replies:
                    writer.write(reply.encode() + b"\r")
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass

    async def push(self, line: str) -> None:
        for writer in self.writers:
            writer.write(line.encode() + b"\r")
            await writer.drain()


def run(coro):
    return asyncio.run(coro)


def test_probe() -> None:
    async def scenario() -> None:
        fake = FakeReceiver()
        port = await fake.start()
        assert await async_probe("127.0.0.1", port, timeout=2)
        await fake.stop()
        assert not await async_probe("127.0.0.1", port, timeout=1)

    run(scenario())


def test_sync_commands_and_push(monkeypatch) -> None:
    monkeypatch.setattr(client_mod, "COMMAND_INTERVAL", 0.001)
    monkeypatch.setattr(client_mod, "REFRESH_DELAY", 0.05)

    async def scenario() -> None:
        fake = FakeReceiver()
        port = await fake.start()
        client = DenonClient("127.0.0.1", port)
        events: list[set[str] | None] = []
        client.add_listener(events.append)
        await client.async_start()
        assert await client.async_wait_connected(2)
        assert await client.async_wait_synced(10)

        assert client.get("power") is True
        assert client.get("volume") == -35.0
        assert client.get("max_volume") == 18.0
        assert client.get("source") == "TV"
        assert client.get("channel_level_c") == 2.0
        assert client.get("channel_level_sw") == -1.5
        assert client.get("dynamic_eq") is True
        assert not client.has("channel_level_sl")
        assert None in events  # connection notification

        sources = client.sources()
        assert "DVD" not in sources  # hidden on the receiver
        assert sources["MPLAY"] == "TV Streamer"  # renamed
        assert sources["BD"] == "BD"
        assert sources["NET"] == "HEOS Music"  # default name
        assert list(sources)[:2] == ["SAT/CBL", "BD"]

        # Sound mode list: categories merged, duplicates removed, in order.
        assert client.sound_modes == ["Stereo", "Dolby Audio - Dolby Surround", "Direct"]
        assert client.get("speaker_distance_fl") == 3.6
        assert client.get("crossover_fro") == 80
        assert not client.unknown_lines, list(client.unknown_lines)

        await client.async_set(client_mod.SETTINGS_BY_KEY["dynamic_eq"], False)
        await client.async_set(client_mod.SETTINGS_BY_KEY["volume"], -30)
        await asyncio.sleep(0.2)
        assert client.get("dynamic_eq") is False
        assert client.get("volume") == -30.0
        assert "PSDYNEQ OFF" in fake.received

        # Spontaneous change from the remote triggers an audio refresh.
        fake.received.clear()
        await fake.push("SIBD")
        await asyncio.sleep(0.3)
        assert client.get("source") == "BD"
        assert "PSDYNEQ ?" in fake.received

        lines = await client.async_send_and_collect(["CV?"], 0.2)
        assert "CVFL 50" in lines and "CVEND" in lines

        await client.async_stop()
        await fake.stop()
        assert not client.connected

    run(scenario())


def test_set_confirmed(monkeypatch) -> None:
    monkeypatch.setattr(client_mod, "COMMAND_INTERVAL", 0.001)

    async def scenario() -> None:
        fake = FakeReceiver()
        port = await fake.start()
        client = DenonClient("127.0.0.1", port)
        await client.async_start()
        assert await client.async_wait_connected(2)
        assert await client.async_wait_synced(10)
        settings = client_mod.SETTINGS_BY_KEY

        drc = settings["dynamic_range_compression"]

        # Echoed -> accepted.
        assert await client.async_set_confirmed(settings["dynamic_eq"], False, 1)
        assert await client.async_set_confirmed(drc, "off", 1)

        # Answered with another value -> refused, without waiting for a timeout.
        loop = asyncio.get_running_loop()
        start = loop.time()
        assert not await client.async_set_confirmed(settings["dimmer"], "bright", 1)
        assert loop.time() - start < 0.5
        assert client.get("dimmer") == "dim"

        # DRC with a PCM signal: the receiver stores LOW but keeps reporting
        # OFF (seen on a real AVR-X2700H). Accepted, shown as stored, inactive.
        assert await client.async_set_confirmed(drc, "low", 1)
        assert client.get(drc.key) == "low"
        assert client.get_reported(drc.key) == "off"
        assert drc.key in client.stored
        # A refresh repeating the effective value keeps the stored value ...
        await fake.push("PSDRC OFF")
        await asyncio.sleep(0.1)
        assert client.get(drc.key) == "low"
        # ... until the receiver reports it (e.g. a Dolby signal arrives).
        await fake.push("PSDRC LOW")
        await asyncio.sleep(0.1)
        assert drc.key not in client.stored
        assert client.get(drc.key) == "low"

        # LFE silently ignored, then answered with the effective value on the
        # follow-up query -> stored as well.
        assert await client.async_set_confirmed(settings["lfe_level"], -5, 0.3)
        assert fake.received[-1] == "PSLFE ?"
        assert client.get("lfe_level") == -5
        assert client.get_reported("lfe_level") == 0
        assert not client._waiters

        await client.async_stop()
        await fake.stop()

    run(scenario())


def test_reconnect(monkeypatch) -> None:
    monkeypatch.setattr(client_mod, "COMMAND_INTERVAL", 0.001)
    monkeypatch.setattr(client_mod, "RECONNECT_MIN", 0.05)

    async def scenario() -> None:
        fake = FakeReceiver()
        port = await fake.start()
        client = DenonClient("127.0.0.1", port)
        await client.async_start()
        assert await client.async_wait_connected(2)
        for writer in fake.writers:
            writer.close()
        fake.writers.clear()
        await asyncio.sleep(0.2)
        assert await client.async_wait_connected(3)
        await client.async_stop()
        await fake.stop()

    run(scenario())


def test_send_rejects_control_chars(monkeypatch) -> None:
    async def scenario() -> None:
        fake = FakeReceiver()
        port = await fake.start()
        client = DenonClient("127.0.0.1", port)
        await client.async_start()
        assert await client.async_wait_connected(2)
        try:
            await client.async_send("PW?\rPWSTANDBY")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")
        await client.async_stop()
        await fake.stop()

    run(scenario())
