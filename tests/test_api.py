"""Tests for the RepRapFirmware HTTP API client."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from typing import Any

import pytest

from custom_components.reprapfirmware.api import (
    RepRapFirmwareAuthenticationError,
    RepRapFirmwareClient,
    RepRapFirmwareProtocolError,
    RepRapFirmwareReplyLostError,
    RepRapFirmwareResponseError,
)


class FakeResponse:
    """Minimal aiohttp response stand-in."""

    def __init__(
        self,
        *,
        status: int = 200,
        json_data: Any = None,
        text_data: str = "",
    ) -> None:
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        self.released = False

    async def json(self, *, content_type: None = None) -> Any:
        """Return the configured JSON body."""
        return self._json_data

    async def text(self) -> str:
        """Return the configured text body."""
        return self._text_data

    def release(self) -> None:
        """Mark the fake response as released."""
        self.released = True


class FakeSession:
    """Queue-backed aiohttp ClientSession stand-in."""

    def __init__(
        self,
        responses: list[FakeResponse | Callable[..., FakeResponse]],
    ) -> None:
        self.responses = deque(responses)
        self.requests: list[dict[str, Any]] = []

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        """Return the next queued response and record the request."""
        self.requests.append({"url": url, **kwargs})
        response = self.responses.popleft()
        if callable(response):
            return response(url=url, **kwargs)
        return response


def make_client(session: FakeSession) -> RepRapFirmwareClient:
    """Create a test client."""
    return RepRapFirmwareClient(
        host="printer.local",
        port=80,
        use_ssl=False,
        password="secret",
        session=session,  # type: ignore[arg-type]
    )


def test_connect_obtains_session_key_and_get_model_sends_header() -> None:
    """A successful connect stores the key used by subsequent requests."""
    session = FakeSession(
        [
            FakeResponse(
                json_data={
                    "err": 0,
                    "sessionKey": 123456,
                    "sessionTimeout": 8000,
                    "boardType": "duet5lcwifi",
                }
            ),
            FakeResponse(json_data={"key": "state", "result": {"status": "idle"}}),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        info = await client.connect()
        state = await client.get_model("state")

        assert info.board_type == "duet5lcwifi"
        assert info.session_timeout_ms == 8000
        assert state == {"status": "idle"}
        assert session.requests[0]["params"] == {
            "password": "secret",
            "sessionKey": "yes",
        }
        assert session.requests[1]["headers"] == {"X-Session-Key": "123456"}

    asyncio.run(run())


def test_invalid_password_raises_authentication_error() -> None:
    """rr_connect error code 1 maps to an authentication failure."""
    client = make_client(FakeSession([FakeResponse(json_data={"err": 1})]))

    with pytest.raises(RepRapFirmwareAuthenticationError):
        asyncio.run(client.connect())


def test_missing_session_key_is_rejected() -> None:
    """P0 requires session-key authentication rather than IP-only sessions."""
    client = make_client(FakeSession([FakeResponse(json_data={"err": 0})]))

    with pytest.raises(RepRapFirmwareProtocolError, match="sessionKey"):
        asyncio.run(client.connect())


def test_get_model_reconnects_once_after_401() -> None:
    """An expired session is replaced and the safe Object Model read is retried."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 111}),
            FakeResponse(status=401),
            FakeResponse(json_data={"err": 0, "sessionKey": 222}),
            FakeResponse(json_data={"key": "state", "result": {"status": "idle"}}),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        state = await client.get_model("state")
        assert state == {"status": "idle"}
        assert session.requests[-1]["headers"] == {"X-Session-Key": "222"}

    asyncio.run(run())


def test_send_gcode_waits_for_sequence_then_fetches_reply() -> None:
    """M115-style commands wait for seqs.reply before reading rr_reply."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(json_data={"key": "seqs", "result": {"reply": 10}}),
            FakeResponse(json_data={"buff": 2048}),
            FakeResponse(json_data={"key": "seqs", "result": {"reply": 10}}),
            FakeResponse(json_data={"key": "seqs", "result": {"reply": 11}}),
            FakeResponse(text_data="FIRMWARE_NAME: RepRapFirmware 3.5"),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        result = await client.send_gcode(
            "M115",
            wait_for_reply=True,
            reply_timeout=0.5,
            poll_interval=0.001,
        )
        assert result.buffer_space == 2048
        assert result.reply == "FIRMWARE_NAME: RepRapFirmware 3.5"
        assert session.requests[2]["params"] == {"gcode": "M115"}

    asyncio.run(run())


def test_command_is_not_replayed_if_session_expires_after_acceptance() -> None:
    """Losing the session while awaiting a reply must not duplicate a command."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(json_data={"key": "seqs", "result": {"reply": 10}}),
            FakeResponse(json_data={"buff": 2048}),
            FakeResponse(status=401),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        with pytest.raises(RepRapFirmwareReplyLostError):
            await client.send_gcode(
                "G28",
                wait_for_reply=True,
                reply_timeout=0.5,
                poll_interval=0.001,
            )

        gcode_requests = [
            request
            for request in session.requests
            if request["url"].endswith("/rr_gcode")
        ]
        assert len(gcode_requests) == 1

    asyncio.run(run())


def test_list_files_follows_rr_filelist_pagination() -> None:
    """File enumeration follows next offsets until the list is complete."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(
                json_data={
                    "dir": "/macros/",
                    "first": 0,
                    "files": [
                        {"type": "f", "name": "Home.g", "size": 12},
                    ],
                    "next": 1,
                    "err": 0,
                }
            ),
            FakeResponse(
                json_data={
                    "dir": "/macros/",
                    "first": 1,
                    "files": [
                        {
                            "type": "f",
                            "name": "PID Tune.g",
                            "size": 34,
                            "date": "2026-08-19T20:00:00",
                        },
                    ],
                    "next": 0,
                    "err": 0,
                }
            ),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        items = await client.list_files("/macros/")
        assert [item.name for item in items] == ["Home.g", "PID Tune.g"]
        assert session.requests[1]["params"] == {"dir": "/macros/", "first": "0"}
        assert session.requests[2]["params"] == {"dir": "/macros/", "first": "1"}

    asyncio.run(run())


def test_list_files_reports_missing_directory() -> None:
    """rr_filelist error 2 maps to a controlled API response error."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(json_data={"err": 2}),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        with pytest.raises(RepRapFirmwareResponseError, match="does not exist"):
            await client.list_files("/macros/")

    asyncio.run(run())


def test_list_files_accepts_success_payload_without_err_field() -> None:
    """Some standalone RRF builds omit err on successful file listings."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(
                json_data={
                    "dir": "/macros/",
                    "first": 0,
                    "files": [
                        {
                            "type": "f",
                            "name": "Calibrate Printer",
                            "size": 131,
                        },
                        {"type": "f", "name": "Wifi Reset", "size": 330},
                    ],
                    "next": 0,
                }
            ),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        items = await client.list_files("/macros/")
        assert [item.name for item in items] == [
            "Calibrate Printer",
            "Wifi Reset",
        ]

    asyncio.run(run())


def test_list_files_rejects_missing_err_and_files() -> None:
    """Missing err is tolerated only when a valid files array is present."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(json_data={"dir": "/macros/", "first": 0}),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        with pytest.raises(
            RepRapFirmwareProtocolError, match="omitted both err and a files array"
        ):
            await client.list_files("/macros/")

    asyncio.run(run())


def test_get_model_sends_requested_flags() -> None:
    """Object Model verbose/frequent flags are passed through to RRF."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(json_data={"key": "heat", "result": {"heaters": []}}),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        await client.get_model("heat", flags="v")
        assert session.requests[1]["params"] == {"key": "heat", "flags": "v"}

    asyncio.run(run())


def test_get_file_info_returns_active_job_metadata() -> None:
    """rr_fileinfo can recover file size omitted from Object Model responses."""
    session = FakeSession(
        [
            FakeResponse(json_data={"err": 0, "sessionKey": 123}),
            FakeResponse(
                json_data={
                    "err": 0,
                    "fileName": "/gcodes/cube.gcode",
                    "size": 123456,
                    "printDuration": 42.0,
                }
            ),
        ]
    )
    client = make_client(session)

    async def run() -> None:
        await client.connect()
        info = await client.get_file_info()
        assert info["size"] == 123456
        assert session.requests[1]["url"].endswith("/rr_fileinfo")
        assert session.requests[1]["params"] is None

    asyncio.run(run())
