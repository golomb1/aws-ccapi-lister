"""Small synchronous wrapper over Pulumi Automation API.

The wrapper is intentionally minimal and returns predictable dict payloads so the
async harness can run it in worker threads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class PulumiResult:
    ok: bool
    outputs: dict[str, Any]
    summary: str
    error: str | None = None


class PulumiRunner:
    """Synchronous Pulumi operations wrapper.

    Falls back to a no-op mode when Pulumi Automation API is unavailable, making
    this framework runnable as a skeleton in lightweight CI environments.
    """

    def __init__(self) -> None:
        try:
            from pulumi import automation as auto  # type: ignore
        except Exception:
            auto = None
        self._auto = auto

    def create_or_select_stack(
        self,
        *,
        stack_name: str,
        project_name: str,
        program: Callable[[], None] | None = None,
        work_dir: str | None = None,
    ) -> Any:
        if self._auto is None:
            return {
                "name": stack_name,
                "project_name": project_name,
                "work_dir": work_dir,
                "mock": True,
            }
        if program is not None:
            return self._auto.create_or_select_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=program,
            )
        return self._auto.LocalWorkspace.create_or_select_stack(
            stack_name=stack_name,
            work_dir=work_dir or ".",
            project_name=project_name,
        )

    def up(self, stack: Any) -> PulumiResult:
        if isinstance(stack, dict) and stack.get("mock"):
            return PulumiResult(ok=True, outputs={}, summary="mock up")
        try:
            result = stack.up(on_output=lambda _: None)
            outputs = {k: v.value for k, v in result.outputs.items()}
            return PulumiResult(ok=True, outputs=outputs, summary=result.summary.result)
        except Exception as exc:  # noqa: BLE001
            return PulumiResult(ok=False, outputs={}, summary="up failed", error=str(exc))

    def refresh(self, stack: Any) -> PulumiResult:
        if isinstance(stack, dict) and stack.get("mock"):
            return PulumiResult(ok=True, outputs={}, summary="mock refresh")
        try:
            result = stack.refresh(on_output=lambda _: None)
            return PulumiResult(ok=True, outputs={}, summary=result.summary.result)
        except Exception as exc:  # noqa: BLE001
            return PulumiResult(ok=False, outputs={}, summary="refresh failed", error=str(exc))

    def destroy(self, stack: Any) -> PulumiResult:
        if isinstance(stack, dict) and stack.get("mock"):
            return PulumiResult(ok=True, outputs={}, summary="mock destroy")
        try:
            result = stack.destroy(on_output=lambda _: None)
            return PulumiResult(ok=True, outputs={}, summary=result.summary.result)
        except Exception as exc:  # noqa: BLE001
            return PulumiResult(ok=False, outputs={}, summary="destroy failed", error=str(exc))
