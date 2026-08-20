"""Async RepRapFirmware HTTP API client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import (
    DEFAULT_REPLY_POLL_INTERVAL,
    DEFAULT_REPLY_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
)


class RepRapFirmwareError(Exception):
    """Base exception for RepRapFirmware API failures."""


class RepRapFirmwareConnectionError(RepRapFirmwareError):
    """Raised when the controller cannot be reached."""


class RepRapFirmwareAuthenticationError(RepRapFirmwareError):
    """Raised when authentication fails or an authenticated session is rejected."""


class RepRapFirmwareSessionError(RepRapFirmwareError):
    """Raised when RepRapFirmware cannot create a usable HTTP session."""


class RepRapFirmwareBusyError(RepRapFirmwareError):
    """Raised when RepRapFirmware reports that it cannot service the request."""


class RepRapFirmwareResponseError(RepRapFirmwareError):
    """Raised when RepRapFirmware returns an unexpected HTTP response."""


class RepRapFirmwareProtocolError(RepRapFirmwareError):
    """Raised when a RepRapFirmware response does not match the expected API shape."""


class RepRapFirmwareReplyTimeoutError(RepRapFirmwareError):
    """Raised when a command reply is not announced before the reply timeout."""


class RepRapFirmwareReplyLostError(RepRapFirmwareError):
    """Raised when a command session expires after a command was accepted."""


@dataclass(frozen=True, slots=True)
class RepRapFirmwareConnectionInfo:
    """Information returned by rr_connect."""

    board_type: str | None
    session_timeout_ms: int | None


@dataclass(frozen=True, slots=True)
class RepRapFirmwareFileItem:
    """One item returned by rr_filelist."""

    name: str
    item_type: str
    size: int
    date: str | None = None


@dataclass(frozen=True, slots=True)
class RepRapFirmwareGCodeResult:
    """Result from submitting G-code to RepRapFirmware."""

    buffer_space: int | None
    reply: str | None = None


class RepRapFirmwareClient:
    """Async client for the standalone RepRapFirmware HTTP API."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        use_ssl: bool,
        password: str,
        session: aiohttp.ClientSession,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the client."""
        self._host = host.strip()
        self._port = port
        self._use_ssl = use_ssl
        self._password = password
        self._session = session
        self._request_timeout = request_timeout

        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{self._host}:{self._port}"

        self._session_key: str | None = None
        self._board_type: str | None = None
        self._session_timeout_ms: int | None = None

        self._connect_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """Return the controller base URL."""
        return self._base_url

    @property
    def connected(self) -> bool:
        """Return whether the client currently holds a session key."""
        return self._session_key is not None

    @property
    def board_type(self) -> str | None:
        """Return the board type reported by the controller."""
        return self._board_type

    @property
    def session_timeout_ms(self) -> int | None:
        """Return the idle session timeout reported by RepRapFirmware."""
        return self._session_timeout_ms

    async def connect(self, *, force: bool = False) -> RepRapFirmwareConnectionInfo:
        """Authenticate and obtain a session key."""
        async with self._connect_lock:
            if self._session_key is not None and not force:
                return RepRapFirmwareConnectionInfo(
                    board_type=self._board_type,
                    session_timeout_ms=self._session_timeout_ms,
                )

            self._clear_session()
            payload = await self._request_json(
                "/rr_connect",
                params={"password": self._password, "sessionKey": "yes"},
                authenticated=False,
                auto_reconnect=False,
            )

            error_code = payload.get("err")
            if error_code == 1:
                raise RepRapFirmwareAuthenticationError("Invalid machine password")
            if error_code == 2:
                raise RepRapFirmwareSessionError(
                    "RepRapFirmware has no free HTTP user sessions"
                )
            if error_code != 0:
                raise RepRapFirmwareProtocolError(
                    f"rr_connect returned unexpected error code: {error_code!r}"
                )

            session_key = payload.get("sessionKey")
            if session_key is None:
                raise RepRapFirmwareProtocolError(
                    "rr_connect succeeded but did not return a sessionKey"
                )

            self._session_key = str(session_key)
            board_type = payload.get("boardType")
            self._board_type = str(board_type) if board_type is not None else None

            session_timeout = payload.get("sessionTimeout")
            self._session_timeout_ms = (
                int(session_timeout)
                if isinstance(session_timeout, int | float)
                else None
            )

            return RepRapFirmwareConnectionInfo(
                board_type=self._board_type,
                session_timeout_ms=self._session_timeout_ms,
            )

    async def reconnect(self) -> RepRapFirmwareConnectionInfo:
        """Discard the current session state and create a new session."""
        return await self.connect(force=True)

    async def disconnect(self) -> None:
        """Disconnect the current RepRapFirmware HTTP session."""
        if self._session_key is None:
            return

        try:
            payload = await self._request_json(
                "/rr_disconnect",
                authenticated=True,
                auto_reconnect=False,
            )
            if payload.get("err") != 0:
                raise RepRapFirmwareSessionError(
                    "RepRapFirmware did not confirm session disconnection"
                )
        except RepRapFirmwareAuthenticationError:
            # An expired session is already effectively disconnected.
            pass
        finally:
            self._clear_session()

    async def get_model(
        self,
        key: str,
        *,
        flags: str | None = None,
    ) -> Any:
        """Return the requested RepRapFirmware Object Model branch."""
        params: dict[str, str] = {"key": key}
        if flags:
            params["flags"] = flags

        payload = await self._request_json(
            "/rr_model",
            params=params,
            authenticated=True,
            auto_reconnect=True,
        )

        if "result" not in payload:
            raise RepRapFirmwareProtocolError(
                "rr_model response did not contain a result field"
            )
        return payload["result"]

    async def get_reply(self) -> str:
        """Retrieve the current G-code reply for this HTTP session."""
        return await self._request_text(
            "/rr_reply",
            authenticated=True,
            auto_reconnect=False,
        )

    async def list_files(self, directory: str) -> tuple[RepRapFirmwareFileItem, ...]:
        """Return all items in one RepRapFirmware directory.

        rr_filelist may paginate responses using the ``next`` field, so callers
        receive one normalized tuple regardless of controller response size.
        """
        if not directory.strip():
            raise ValueError("directory must not be empty")

        first = 0
        items: list[RepRapFirmwareFileItem] = []
        seen_offsets: set[int] = set()

        while True:
            if first in seen_offsets:
                raise RepRapFirmwareProtocolError(
                    "rr_filelist returned a repeated pagination offset"
                )
            seen_offsets.add(first)

            payload = await self._request_json(
                "/rr_filelist",
                params={"dir": directory, "first": str(first)},
                authenticated=True,
                auto_reconnect=True,
            )

            error_code = payload.get("err")
            if error_code == 1:
                raise RepRapFirmwareResponseError(
                    f"RepRapFirmware storage is not mounted for {directory}"
                )
            if error_code == 2:
                raise RepRapFirmwareResponseError(
                    f"RepRapFirmware directory does not exist: {directory}"
                )
            if error_code != 0:
                raise RepRapFirmwareProtocolError(
                    f"rr_filelist returned unexpected error code: {error_code!r}"
                )

            files = payload.get("files")
            if not isinstance(files, list):
                raise RepRapFirmwareProtocolError(
                    "rr_filelist response did not contain a files array"
                )

            for raw_item in files:
                if not isinstance(raw_item, dict):
                    raise RepRapFirmwareProtocolError(
                        "rr_filelist returned a file item that was not an object"
                    )
                name = raw_item.get("name")
                item_type = raw_item.get("type")
                size = raw_item.get("size")
                date = raw_item.get("date")
                if (
                    not isinstance(name, str)
                    or item_type not in {"f", "d"}
                    or isinstance(size, bool)
                    or not isinstance(size, int)
                    or (date is not None and not isinstance(date, str))
                ):
                    raise RepRapFirmwareProtocolError(
                        "rr_filelist returned a malformed file item"
                    )
                items.append(
                    RepRapFirmwareFileItem(
                        name=name,
                        item_type=item_type,
                        size=size,
                        date=date,
                    )
                )

            next_offset = payload.get("next", 0)
            if isinstance(next_offset, bool) or not isinstance(next_offset, int):
                raise RepRapFirmwareProtocolError(
                    "rr_filelist next field is not an integer"
                )
            if next_offset <= 0:
                return tuple(items)
            first = next_offset

    async def send_gcode(
        self,
        gcode: str,
        *,
        wait_for_reply: bool = False,
        reply_timeout: float = DEFAULT_REPLY_TIMEOUT,
        poll_interval: float = DEFAULT_REPLY_POLL_INTERVAL,
    ) -> RepRapFirmwareGCodeResult:
        """Submit G-code and optionally wait for the session's command reply.

        Commands are serialized because RepRapFirmware buffers command replies per HTTP
        session. A command that receives HTTP 401 is safe to retry after reconnect
        because the request was rejected before execution. Once a command has been
        accepted, the client will not reconnect while waiting for its reply because
        doing so would lose
        the per-session reply context and could make replaying the command unsafe.
        """
        if not gcode.strip():
            raise ValueError("gcode must not be empty")
        if reply_timeout <= 0:
            raise ValueError("reply_timeout must be greater than zero")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")

        async with self._command_lock:
            reply_sequence = (
                await self._get_reply_sequence(auto_reconnect=True)
                if wait_for_reply
                else None
            )

            payload = await self._request_json(
                "/rr_gcode",
                params={"gcode": gcode},
                authenticated=True,
                auto_reconnect=True,
            )

            buffer_space = payload.get("buff")
            if not isinstance(buffer_space, int):
                raise RepRapFirmwareProtocolError(
                    "rr_gcode response did not contain an integer buff value"
                )

            if not wait_for_reply:
                return RepRapFirmwareGCodeResult(buffer_space=buffer_space)

            assert reply_sequence is not None
            reply = await self._wait_for_reply(
                previous_sequence=reply_sequence,
                timeout=reply_timeout,
                poll_interval=poll_interval,
            )
            return RepRapFirmwareGCodeResult(
                buffer_space=buffer_space,
                reply=reply,
            )

    async def _wait_for_reply(
        self,
        *,
        previous_sequence: int,
        timeout: float,
        poll_interval: float,
    ) -> str:
        """Wait for seqs.reply to advance, then fetch rr_reply."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while True:
            try:
                current_sequence = await self._get_reply_sequence(auto_reconnect=False)
            except RepRapFirmwareAuthenticationError as err:
                self._clear_session()
                raise RepRapFirmwareReplyLostError(
                    "HTTP session expired after the command was accepted; "
                    "the command was not replayed"
                ) from err

            if current_sequence != previous_sequence:
                try:
                    return await self.get_reply()
                except RepRapFirmwareAuthenticationError as err:
                    self._clear_session()
                    raise RepRapFirmwareReplyLostError(
                        "HTTP session expired before the command reply could be fetched"
                    ) from err

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise RepRapFirmwareReplyTimeoutError(
                    f"No G-code reply was announced within {timeout:.2f} seconds"
                )
            await asyncio.sleep(min(poll_interval, remaining))

    async def _get_reply_sequence(self, *, auto_reconnect: bool) -> int:
        """Return seqs.reply for the current HTTP session."""
        payload = await self._request_json(
            "/rr_model",
            params={"key": "seqs"},
            authenticated=True,
            auto_reconnect=auto_reconnect,
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RepRapFirmwareProtocolError(
                "rr_model?key=seqs did not return an object"
            )

        reply_sequence = result.get("reply")
        if not isinstance(reply_sequence, int):
            raise RepRapFirmwareProtocolError(
                "Object Model seqs.reply is missing or is not an integer"
            )
        return reply_sequence

    async def _request_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        authenticated: bool,
        auto_reconnect: bool,
    ) -> dict[str, Any]:
        """Perform an HTTP GET and decode a JSON object response."""
        response = await self._request(
            path,
            params=params,
            authenticated=authenticated,
            auto_reconnect=auto_reconnect,
        )
        try:
            payload = await response.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise RepRapFirmwareProtocolError(f"{path} returned invalid JSON") from err
        finally:
            response.release()

        if not isinstance(payload, dict):
            raise RepRapFirmwareProtocolError(
                f"{path} returned JSON that was not an object"
            )
        return payload

    async def _request_text(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        authenticated: bool,
        auto_reconnect: bool,
    ) -> str:
        """Perform an HTTP GET and decode a text response."""
        response = await self._request(
            path,
            params=params,
            authenticated=authenticated,
            auto_reconnect=auto_reconnect,
        )
        try:
            return await response.text()
        finally:
            response.release()

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, str] | None,
        authenticated: bool,
        auto_reconnect: bool,
    ) -> aiohttp.ClientResponse:
        """Perform an HTTP GET, reconnecting once on 401 when safe."""
        if authenticated and self._session_key is None:
            await self.connect()

        for attempt in range(2):
            headers: dict[str, str] = {}
            if authenticated:
                if self._session_key is None:
                    raise RepRapFirmwareAuthenticationError(
                        "No RepRapFirmware HTTP session is available"
                    )
                headers["X-Session-Key"] = self._session_key

            try:
                response = await self._session.get(
                    f"{self._base_url}{path}",
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._request_timeout),
                )
            except (aiohttp.ClientError, TimeoutError) as err:
                raise RepRapFirmwareConnectionError(
                    f"Unable to reach RepRapFirmware at {self._base_url}"
                ) from err

            if response.status == 401:
                response.release()
                self._clear_session()
                if authenticated and auto_reconnect and attempt == 0:
                    await self.connect()
                    continue
                raise RepRapFirmwareAuthenticationError(
                    "RepRapFirmware rejected the HTTP session"
                )

            if response.status == 503:
                response.release()
                raise RepRapFirmwareBusyError(
                    "RepRapFirmware is temporarily unable to service the request"
                )

            if response.status >= 400:
                status = response.status
                response.release()
                raise RepRapFirmwareResponseError(
                    f"RepRapFirmware returned HTTP {status} for {path}"
                )

            return response

        raise RepRapFirmwareAuthenticationError(
            "RepRapFirmware rejected the reconnected HTTP session"
        )

    def _clear_session(self) -> None:
        """Clear ephemeral session state."""
        self._session_key = None
        self._board_type = None
        self._session_timeout_ms = None
