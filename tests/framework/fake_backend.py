"""Deterministic in-memory backend used by CI policy framework tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class SuccessResult:
    operation_id: str
    resource_ids: List[str] = field(default_factory=list)
    non_compliant_resource_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeniedResult:
    operation_id: str
    reason: str


@dataclass
class OperationRecord:
    operation_id: str
    operation: str
    resource_id: str
    scope: str
    status: str
    is_exempt: bool


class FakeSystemClient:
    """A fake backend that simulates policy outcomes across framework flows."""

    def __init__(self) -> None:
        self._resources: Dict[str, Dict[str, object]] = {}
        self._operations: Dict[str, OperationRecord] = {}
        self._notifications: Dict[str, str] = {}
        self._scan_polls: Dict[str, int] = {}
        self._next_operation_id = 1

    def _new_operation_id(self) -> str:
        op_id = f"op-{self._next_operation_id:04d}"
        self._next_operation_id += 1
        return op_id

    def execute(self, operation: str, resource_id: str, *, scope: str, compliant: bool, exempt: bool = False):
        operation_id = self._new_operation_id()
        denied = scope == "prevent" and (not compliant) and (not exempt)

        if denied:
            status = "denied"
            self._notifications[operation_id] = f"{resource_id}:{operation}:prevented"
            result = DeniedResult(operation_id=operation_id, reason="Denied by prevent scope")
        else:
            status = "applied"
            self._resources[resource_id] = {
                "compliant": compliant,
                "last_operation": operation,
                "exempt": exempt,
            }
            if scope == "alert" and not compliant:
                self._scan_polls[operation_id] = 0
                self._notifications[operation_id] = f"{resource_id}:{operation}:scan_scheduled"
                result = SuccessResult(
                    operation_id=operation_id,
                    resource_ids=[resource_id],
                    non_compliant_resource_ids=[resource_id],
                )
            else:
                self._notifications[operation_id] = f"{resource_id}:{operation}:ok"
                result = SuccessResult(operation_id=operation_id, resource_ids=[resource_id])

        self._operations[operation_id] = OperationRecord(
            operation_id=operation_id,
            operation=operation,
            resource_id=resource_id,
            scope=scope,
            status=status,
            is_exempt=exempt,
        )
        return result

    def get_operation(self, operation_id: str) -> OperationRecord:
        return self._operations[operation_id]

    def lookup_notification(self, operation_id: str) -> str:
        return self._notifications[operation_id]

    def is_scan_complete(self, operation_id: str) -> bool:
        if operation_id not in self._scan_polls:
            return True
        self._scan_polls[operation_id] += 1
        return self._scan_polls[operation_id] >= 2

    def compliance_state(self, resource_id: str) -> str:
        record = self._resources[resource_id]
        return "compliant" if bool(record["compliant"]) else "non-compliant"

    @property
    def resources(self) -> Dict[str, Dict[str, object]]:
        return self._resources
