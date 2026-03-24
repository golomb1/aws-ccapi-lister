"""Fake template intentionally violating prevent behavior so tests fail."""

from __future__ import annotations

from uuid import uuid4

from tests.framework.contracts import DeniedResult, PolicyContext, ProvisionResult, SuccessResult


def _op_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _named(case_id: str, fn):
    fn.case_id = case_id
    return fn


def create_compliant_resources(ctx: PolicyContext) -> ProvisionResult:
    return SuccessResult(
        ok=True,
        operation="create",
        resource_id=f"fail-compliant-{ctx.stack_name}",
        operation_id=_op_id("fail-create"),
    )


def non_compliant_create_cases() -> list:
    def broken_case(ctx: PolicyContext) -> ProvisionResult:
        # Intentionally wrong for prevent scope: should be DeniedResult, not SuccessResult.
        return SuccessResult(
            ok=True,
            operation="create",
            resource_id=f"fail-should-have-been-denied-{ctx.stack_name}",
            operation_id=_op_id("fail-broken"),
        )

    return [_named("fake_fail_non_compliant_create", broken_case)]


def non_compliant_modify_cases() -> list:
    def deny_modify(ctx: PolicyContext, resource: ProvisionResult) -> ProvisionResult:
        return DeniedResult(
            ok=False,
            operation="modify",
            resource_id=resource.resource_id,
            operation_id=_op_id("fail-denied-modify"),
            error="Denied fake modify",
        )

    return [_named("fake_fail_non_compliant_modify", deny_modify)]


def modify_exempt_resources(ctx: PolicyContext, exempt_resources) -> ProvisionResult:
    return SuccessResult(
        ok=True,
        operation="modify",
        operation_id=_op_id("fail-exempt"),
        metadata={"count": len(exempt_resources)},
    )
