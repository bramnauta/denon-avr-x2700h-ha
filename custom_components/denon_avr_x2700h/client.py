"""Async Telnet client for the Denon AVR-X2700H.

Keeps one persistent connection, reconnects automatically, paces outgoing
commands and keeps a decoded copy of every reported setting.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
import contextlib
import logging
import time
from typing import Any

from .protocol import (
    AUDIO_REFRESH_QUERIES,
    IGNORED_PREFIXES,
    SETTINGS_BY_KEY,
    SOUND_MODE_LIST_END,
    SOUND_MODE_LIST_PREFIX,
    SOURCE_NAME,
    SOURCES,
    TELNET_PORT,
    Setting,
    all_queries,
    parse_line,
    parse_sound_mode_item,
    parse_source_info,
)

_LOGGER = logging.getLogger(__name__)

# The receiver needs a short pause between commands.
COMMAND_INTERVAL = 0.06
# Power-on commands need much longer before the next command is accepted.
POWER_ON_DELAY = 1.0
POWER_ON_COMMANDS = {"PWON", "ZMON", "Z2ON"}
CONNECT_TIMEOUT = 10
HEARTBEAT_INTERVAL = 30
# No data for this long means the connection is dead.
STALE_TIMEOUT = 75
RECONNECT_MIN = 2
RECONNECT_MAX = 60
REFRESH_DELAY = 2.0
# How long to wait for the receiver to confirm a changed setting.
CONFIRM_TIMEOUT = 1.5

Listener = Callable[[set[str] | None], None]

# Pseudo state keys notified when source names / visibility or the list of
# available surround modes change.
SOURCES_KEY = "sources"
SOUND_MODES_KEY = "sound_modes"


class DenonClient:
    """Persistent Telnet connection with decoded state."""

    def __init__(
        self, host: str, port: int = TELNET_PORT, *, include_zone2: bool = True
    ) -> None:
        self.host = host
        self.port = port
        self.include_zone2 = include_zone2
        self.raw: dict[str, str] = {}
        # Source code -> renamed name / "USE" or "DEL", as reported by the receiver.
        self.source_names: dict[str, str] = {}
        self.source_usage: dict[str, str] = {}
        # Surround modes the receiver offers for the current input signal.
        self.sound_modes: list[str] = []
        self._sound_mode_items: dict[int, str] = {}
        self.recent_lines: deque[str] = deque(maxlen=100)
        self.unknown_lines: deque[str] = deque(maxlen=50)
        self._listeners: list[Listener] = []
        self._line_collectors: list[list[str]] = []
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._run_task: asyncio.Task[None] | None = None
        self._refresh_handle: asyncio.TimerHandle | None = None
        self._pending_refresh: list[str] = []
        # Setting key -> futures waiting for the receiver to report that key.
        self._waiters: dict[str, list[asyncio.Future[str]]] = {}
        # Raw values we set that the receiver stored but does not report
        # because they are not in effect for the current signal (DRC, LFE).
        self.stored: dict[str, str] = {}
        self._connected = asyncio.Event()
        self._synced = asyncio.Event()
        self._stopping = False
        self._last_rx = 0.0

    # ------------------------------------------------------------------ state

    @property
    def connected(self) -> bool:
        """Return True while the Telnet session is up."""
        return self._connected.is_set()

    def has(self, key: str) -> bool:
        """Return True if the receiver reported a value for ``key``."""
        return key in self.raw

    def get(self, key: str) -> Any:
        """Return the decoded value for ``key`` or None.

        For settings that report their effective value, a value stored on the
        receiver but not in effect (see ``stored``) takes precedence.
        """
        return self._decode(key, self.stored.get(key, self.raw.get(key)))

    def get_reported(self, key: str) -> Any:
        """Return the value exactly as the receiver last reported it."""
        return self._decode(key, self.raw.get(key))

    @staticmethod
    def _decode(key: str, raw: str | None) -> Any:
        if raw is None:
            return None
        try:
            return SETTINGS_BY_KEY[key].decode(raw)
        except (ValueError, KeyError):
            return None

    def sources(self) -> dict[str, str]:
        """Return visible sources (code -> display name) in front panel order."""
        result: dict[str, str] = {}
        for code in (*SOURCES, *self.source_usage):
            if code in result or self.source_usage.get(code) == "DEL":
                continue
            result[code] = self.source_names.get(code) or SOURCES.get(code, code)
        return result

    def add_listener(self, listener: Listener) -> Callable[[], None]:
        """Register a callback for state changes.

        The callback gets the set of changed keys, or None when the connection
        state changed.
        """
        self._listeners.append(listener)

        def remove() -> None:
            with contextlib.suppress(ValueError):
                self._listeners.remove(listener)

        return remove

    def _notify(self, keys: set[str] | None) -> None:
        for listener in list(self._listeners):
            try:
                listener(keys)
            except Exception:
                _LOGGER.exception("Error in Denon state listener")

    # -------------------------------------------------------------- lifecycle

    async def async_start(self) -> None:
        """Start the background connection task."""
        self._stopping = False
        if self._run_task is None or self._run_task.done():
            self._run_task = asyncio.create_task(self._run(), name="denon_telnet")

    async def async_stop(self) -> None:
        """Close the connection and stop reconnecting."""
        self._stopping = True
        if self._refresh_handle:
            self._refresh_handle.cancel()
        if self._run_task:
            self._run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._run_task
            self._run_task = None
        await self._close()

    async def async_wait_connected(self, timeout: float) -> bool:
        """Wait until connected; return False on timeout."""
        try:
            await asyncio.wait_for(self._connected.wait(), timeout)
        except TimeoutError:
            return False
        return True

    async def async_wait_synced(self, timeout: float) -> bool:
        """Wait until the initial status queries have been answered."""
        try:
            await asyncio.wait_for(self._synced.wait(), timeout)
        except TimeoutError:
            return False
        return True

    async def _run(self) -> None:
        delay = RECONNECT_MIN
        while not self._stopping:
            try:
                await self._connect()
            except (OSError, TimeoutError) as err:
                _LOGGER.debug("Connecting to %s failed: %s", self.host, err)
            else:
                delay = RECONNECT_MIN
                await self._session()
            if self._stopping:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _connect(self) -> None:
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), CONNECT_TIMEOUT
        )
        _LOGGER.info("Connected to Denon receiver at %s:%s", self.host, self.port)
        self._last_rx = time.monotonic()
        self._queue = asyncio.Queue()
        self._synced.clear()
        self._connected.set()
        self._notify(None)

    async def _session(self) -> None:
        tasks = [
            asyncio.create_task(self._read_loop(), name="denon_read"),
            asyncio.create_task(self._write_loop(), name="denon_write"),
            asyncio.create_task(self._heartbeat_loop(), name="denon_heartbeat"),
            asyncio.create_task(self._initial_sync(), name="denon_sync"),
        ]
        try:
            # The read loop ends when the connection drops.
            await asyncio.wait(tasks[:3], return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            await self._close()

    async def _close(self) -> None:
        was_connected = self.connected
        self._connected.clear()
        writer, self._writer, self._reader = self._writer, None, None
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        if was_connected:
            _LOGGER.info("Disconnected from Denon receiver at %s", self.host)
            self._notify(None)

    async def _initial_sync(self) -> None:
        for query in all_queries(self.include_zone2):
            self._queue.put_nowait(query)
        # Wait for the queue to drain, then allow the last answers to arrive.
        while not self._queue.empty():
            await asyncio.sleep(0.2)
        await asyncio.sleep(1.0)
        self._synced.set()

    # ------------------------------------------------------------------- I/O

    async def _read_loop(self) -> None:
        assert self._reader is not None
        while True:
            try:
                data = await self._reader.readuntil(b"\r")
            except asyncio.IncompleteReadError:
                return
            except asyncio.LimitOverrunError as err:
                # Discard an oversized line and continue.
                await self._reader.readexactly(err.consumed)
                continue
            except OSError:
                return
            self._last_rx = time.monotonic()
            self.handle_line(data.decode("utf-8", errors="replace").strip("\r\n"))

    async def _write_loop(self) -> None:
        while True:
            command = await self._queue.get()
            writer = self._writer
            if writer is None:
                return
            _LOGGER.debug("-> %s", command)
            try:
                writer.write(command.encode("utf-8") + b"\r")
                await writer.drain()
            except OSError as err:
                _LOGGER.debug("Write failed: %s", err)
                return
            await asyncio.sleep(
                POWER_ON_DELAY if command in POWER_ON_COMMANDS else COMMAND_INTERVAL
            )

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            idle = time.monotonic() - self._last_rx
            if idle > STALE_TIMEOUT:
                _LOGGER.warning("No response from %s, reconnecting", self.host)
                return
            if idle >= HEARTBEAT_INTERVAL:
                self._queue.put_nowait("PW?")

    def handle_line(self, line: str) -> None:
        """Process one line received from the receiver."""
        if not line:
            return
        _LOGGER.debug("<- %s", line)
        self.recent_lines.append(line)
        for collector in self._line_collectors:
            collector.append(line)

        if line.startswith(SOUND_MODE_LIST_PREFIX):
            self._handle_sound_mode_line(line)
            return

        if info := parse_source_info(line):
            kind, code, value = info
            target = self.source_names if kind == SOURCE_NAME else self.source_usage
            if target.get(code) != value:
                target[code] = value
                self._notify({SOURCES_KEY})
            return

        parsed = parse_line(line)
        if not parsed:
            if line not in ("CVEND", "Z2CVEND") and not line.startswith(
                IGNORED_PREFIXES
            ):
                self.unknown_lines.append(line)
            return

        changed: set[str] = set()
        for setting, value in parsed:
            for waiter in self._waiters.get(setting.key, ()):
                if not waiter.done():
                    waiter.set_result(value)
            # A stored-but-inactive value is superseded once the receiver
            # reports it, or reports any other change (signal or menu change).
            if setting.key in self.stored and (
                value == self.stored[setting.key] or value != self.raw.get(setting.key)
            ):
                del self.stored[setting.key]
                changed.add(setting.key)
            if self.raw.get(setting.key) != value:
                self.raw[setting.key] = value
                changed.add(setting.key)
        if not changed:
            return
        self._after_change(changed)
        self._notify(changed)

    def _handle_sound_mode_line(self, line: str) -> None:
        if line == SOUND_MODE_LIST_END:
            modes = [name for _, name in sorted(self._sound_mode_items.items())]
            self._sound_mode_items = {}
            # The same mode can appear in several categories; keep the first.
            modes = list(dict.fromkeys(modes))
            if modes and modes != self.sound_modes:
                self.sound_modes = modes
                self._notify({SOUND_MODES_KEY})
            return
        if item := parse_sound_mode_item(line):
            index, name, _active = item
            self._sound_mode_items[index] = name

    def _after_change(self, changed: set[str]) -> None:
        # Many audio parameters only become (in)active after a source or
        # surround mode change; ask for them again once things settle.
        if changed & {"source", "sound_mode", "audio_format", "audio_channels"}:
            self._schedule_refresh(AUDIO_REFRESH_QUERIES)
        if "main_power" in changed and self.raw.get("main_power") == "ON":
            self._schedule_refresh(tuple(all_queries(self.include_zone2)))
        if "zone2_power" in changed and self.raw.get("zone2_power") == "ON":
            self._schedule_refresh(
                tuple(q for q in all_queries(True) if q.startswith("Z2"))
            )
        if changed & {"source"} and self.raw.get("source") == "TUNER":
            self._schedule_refresh(("TFAN?", "TPAN?", "TMAN?", "TFANNAME?"))

    def _schedule_refresh(self, queries: tuple[str, ...]) -> None:
        loop = asyncio.get_running_loop()
        for query in queries:
            if query not in self._pending_refresh:
                self._pending_refresh.append(query)
        if self._refresh_handle:
            self._refresh_handle.cancel()
        self._refresh_handle = loop.call_later(REFRESH_DELAY, self._run_refresh)

    def _run_refresh(self) -> None:
        self._refresh_handle = None
        pending, self._pending_refresh = self._pending_refresh, []
        if not self.connected:
            return
        for query in pending:
            self._queue.put_nowait(query)

    # --------------------------------------------------------------- commands

    async def async_send(self, *commands: str) -> None:
        """Queue one or more raw commands."""
        if not self.connected:
            raise ConnectionError(f"Not connected to {self.host}")
        for command in commands:
            command = command.strip()
            if not command:
                continue
            if any(ord(ch) < 32 for ch in command):
                raise ValueError("Command contains control characters")
            self._queue.put_nowait(command)

    async def async_set(self, setting: Setting, value: Any) -> None:
        """Change a setting."""
        await self.async_send(setting.encode(value))

    async def async_set_confirmed(
        self, setting: Setting, value: Any, timeout: float = CONFIRM_TIMEOUT
    ) -> bool:
        """Change a setting and return whether the receiver accepted it.

        The receiver either echoes the new value, answers with the value it
        kept (e.g. "PSDRC OFF" when DRC is not available for a PCM signal), or
        ignores the command silently; in that last case ask for the value.
        """
        command = setting.encode(value)
        expected_raw = command[len(setting.prefix) + len(setting.sep) :].strip()
        expected = setting.decode(expected_raw)
        answered = await self._send_and_wait(setting.key, command, timeout)
        if not answered and setting.query:
            answered = await self._send_and_wait(setting.key, setting.query, timeout)
        if self.get_reported(setting.key) == expected:
            if self.stored.pop(setting.key, None) is not None:
                # E.g. DRC "mid" (stored) -> "off": the receiver keeps reporting
                # OFF, so nothing else tells the entities the value changed.
                self._notify({setting.key})
            return True
        if setting.reports_effective and answered:
            # Stored by the receiver but not in effect for this input signal.
            self.stored[setting.key] = expected_raw
            self._notify({setting.key})
            return True
        return False

    def restore_stored(self, setting: Setting, value: Any, effective: Any) -> bool:
        """Re-apply a stored-but-inactive value remembered from before a restart.

        Only done while the receiver still reports the same effective value as
        back then; anything else means the setting changed in the meantime.
        """
        if not setting.reports_effective or self.get_reported(setting.key) != effective:
            return False
        command = setting.encode(value)
        raw = command[len(setting.prefix) + len(setting.sep) :].strip()
        if setting.decode(raw) == effective:
            return False
        self.stored[setting.key] = raw
        self._notify({setting.key})
        return True

    async def _send_and_wait(self, key: str, command: str, timeout: float) -> bool:
        """Send ``command``; return True once the receiver reports ``key``."""
        waiter: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(key, []).append(waiter)
        try:
            await self.async_send(command)
            await asyncio.wait_for(waiter, timeout)
        except TimeoutError:
            return False
        finally:
            self._waiters[key].remove(waiter)
            if not self._waiters[key]:
                del self._waiters[key]
        return True

    async def async_send_and_collect(
        self, commands: list[str], duration: float = 1.0
    ) -> list[str]:
        """Send commands and return every line received during ``duration``."""
        collector: list[str] = []
        self._line_collectors.append(collector)
        try:
            await self.async_send(*commands)
            await asyncio.sleep(len(commands) * COMMAND_INTERVAL + duration)
        finally:
            self._line_collectors.remove(collector)
        return collector

    async def async_refresh(self) -> None:
        """Re-query all status values."""
        await self.async_send(*all_queries(self.include_zone2))


async def async_probe(host: str, port: int = TELNET_PORT, timeout: float = 8) -> bool:
    """Check that a Denon receiver answers on ``host``."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout
        )
    except (OSError, TimeoutError):
        return False
    try:
        writer.write(b"PW?\r")
        await writer.drain()
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            data = await asyncio.wait_for(reader.readuntil(b"\r"), remaining)
            if data.startswith(b"PW"):
                return True
    except (OSError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        return False
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
    return False
