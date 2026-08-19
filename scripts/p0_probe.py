#!/usr/bin/env python3
"""Run the P0 acceptance probe against a real RepRapFirmware controller."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from getpass import getpass

import aiohttp

from custom_components.reprapfirmware.api import (
    RepRapFirmwareClient,
    RepRapFirmwareError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate the P0 RepRapFirmware API client: connect, read state.status, "
            "send M115, receive its firmware reply, and disconnect."
        )
    )
    parser.add_argument("host", help="RepRapFirmware hostname or IP address")
    parser.add_argument(
        "--port", type=int, default=None, help="Controller HTTP(S) port"
    )
    parser.add_argument(
        "--https", action="store_true", help="Use HTTPS instead of HTTP"
    )
    parser.add_argument(
        "--password-env",
        default="RRF_PASSWORD",
        help=(
            "Environment variable containing the machine password "
            "(default: RRF_PASSWORD)"
        ),
    )
    return parser


async def run_probe(args: argparse.Namespace, password: str) -> int:
    """Execute the P0 acceptance probe."""
    port = args.port if args.port is not None else (443 if args.https else 80)

    async with aiohttp.ClientSession() as session:
        client = RepRapFirmwareClient(
            host=args.host,
            port=port,
            use_ssl=args.https,
            password=password,
            session=session,
        )

        try:
            connection = await client.connect()
            state = await client.get_model("state")
            if not isinstance(state, dict) or "status" not in state:
                raise RuntimeError(
                    "state.status was not present in the Object Model response"
                )

            result = await client.send_gcode(
                "M115",
                wait_for_reply=True,
            )

            print("P0 RepRapFirmware API probe passed")
            print(f"Endpoint: {client.base_url}")
            print(f"Board type: {connection.board_type or 'not reported'}")
            timeout = connection.session_timeout_ms
            timeout_display = timeout if timeout is not None else "not reported"
            print(f"Session timeout: {timeout_display} ms")
            print(f"state.status: {state['status']}")
            print(f"M115 reply: {result.reply or '<empty reply>'}")
            return 0
        except (RepRapFirmwareError, RuntimeError) as err:
            print(f"P0 probe failed: {err}", file=sys.stderr)
            return 1
        finally:
            try:
                await client.disconnect()
            except RepRapFirmwareError as err:
                print(f"Warning: disconnect failed: {err}", file=sys.stderr)


def main() -> int:
    """Run the CLI."""
    args = build_parser().parse_args()
    password = os.environ.get(args.password_env)
    if password is None:
        password = getpass("RepRapFirmware machine password (blank if none): ")
    return asyncio.run(run_probe(args, password))


if __name__ == "__main__":
    raise SystemExit(main())
