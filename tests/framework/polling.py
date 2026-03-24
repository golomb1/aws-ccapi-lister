"""Reusable eventual consistency helpers for notification and scan assertions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .contracts import ComplianceObservation, NotificationObservation

T = TypeVar("T")


async def eventually(
    fn: Callable[[], Awaitable[T]],
    *,
    timeout_s: float = 120,
    interval_s: float = 5,
    description: str = "condition",
) -> T:
    deadline = asyncio.get_running_loop().time() + timeout_s
    last_error: Exception | None = None
    while asyncio.get_running_loop().time() < deadline:
        try:
            return await fn()
        except AssertionError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            await asyncio.sleep(interval_s)
    suffix = f" Last error: {last_error}" if last_error else ""
    raise AssertionError(f"Timed out waiting for {description}.{suffix}")


async def wait_until_notification_seen(
    get_notification: Callable[[str], Awaitable[NotificationObservation | None]],
    operation_id: str,
    *,
    timeout_s: float = 120,
    interval_s: float = 5,
) -> NotificationObservation:
    async def _probe() -> NotificationObservation:
        obs = await get_notification(operation_id)
        if obs is None or not obs.seen:
            raise RuntimeError(f"Notification not seen for operation_id={operation_id}")
        return obs

    return await eventually(_probe, timeout_s=timeout_s, interval_s=interval_s, description=f"notification for operation_id={operation_id}")


async def wait_until_resource_scanned(
    get_scan_status: Callable[[str], Awaitable[ComplianceObservation]],
    resource_id: str,
    *,
    timeout_s: float = 300,
    interval_s: float = 10,
) -> ComplianceObservation:
    async def _probe() -> ComplianceObservation:
        obs = await get_scan_status(resource_id)
        if not obs.scanned:
            raise RuntimeError(f"Resource not yet scanned: resource_id={resource_id}")
        return obs

    return await eventually(_probe, timeout_s=timeout_s, interval_s=interval_s, description=f"scan for resource_id={resource_id}")


async def wait_until_compliance(
    get_compliance: Callable[[str], Awaitable[ComplianceObservation]],
    resource_id: str,
    *,
    expect_compliant: bool,
    timeout_s: float = 300,
    interval_s: float = 10,
) -> ComplianceObservation:
    expectation = "compliant" if expect_compliant else "non-compliant"

    async def _probe() -> ComplianceObservation:
        obs = await get_compliance(resource_id)
        if obs.compliant is None:
            raise RuntimeError(f"Compliance state unknown for resource_id={resource_id}")
        if obs.compliant is not expect_compliant:
            raise RuntimeError(f"Expected {expectation} for resource_id={resource_id}, got compliant={obs.compliant}")
        return obs

    return await eventually(_probe, timeout_s=timeout_s, interval_s=interval_s, description=f"{expectation} state for resource_id={resource_id}")
