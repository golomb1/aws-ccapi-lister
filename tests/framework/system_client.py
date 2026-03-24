"""External security system client boundary.

This stub is intentionally small and fully mockable for tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import ComplianceObservation, NotificationObservation


@dataclass
class SystemClient:
    """In-memory client useful for local runs.

    TODO: Replace in-memory stores with real backend SDK/API calls.
    """

    notifications: dict[str, NotificationObservation] = field(default_factory=dict)
    compliance: dict[str, ComplianceObservation] = field(default_factory=dict)

    async def get_notification(self, operation_id: str) -> NotificationObservation | None:
        return self.notifications.get(operation_id)

    async def get_scan_status(self, resource_id: str) -> ComplianceObservation:
        obs = self.compliance.get(resource_id)
        if obs is None:
            return ComplianceObservation(resource_id=resource_id, scanned=False, compliant=None, status="pending")
        return obs

    async def get_resource_compliance(self, resource_id: str) -> ComplianceObservation:
        obs = self.compliance.get(resource_id)
        if obs is None:
            return ComplianceObservation(resource_id=resource_id, scanned=False, compliant=None, status="unknown")
        return obs

    def ingest_event(self, *, operation_id: str, resource_id: str | None, denied: bool, metadata: dict[str, Any] | None = None) -> None:
        """Helper used by the skeleton tests to emulate backend side effects."""

        self.notifications[operation_id] = NotificationObservation(
            seen=True,
            operation_id=operation_id,
            notification_id=f"notif-{operation_id}",
            payload={"denied": denied, **(metadata or {})},
        )
        if resource_id:
            self.compliance[resource_id] = ComplianceObservation(
                resource_id=resource_id,
                scanned=True,
                compliant=not denied,
                status="complete",
                details=metadata or {},
            )
