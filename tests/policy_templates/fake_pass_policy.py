"""Fake template that should pass all framework flows in mock mode."""

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
        resource_id=f"pass-compliant-{ctx.stack_name}",
        operation_id=_op_id("pass-create"),
    )


def non_compliant_create_cases() -> list:
    def case_public(ctx: PolicyContext) -> ProvisionResult:
        if ctx.scope == "alert":
            return SuccessResult(
                ok=True,
                operation="create",
                resource_id=f"pass-alert-public-{ctx.stack_name}",
                operation_id=_op_id("pass-alert"),
            )
        return DeniedResult(
            ok=False,
            operation="create",
            resource_id=f"pass-denied-public-{ctx.stack_name}",
            operation_id=_op_id("pass-denied"),
            error="Denied by fake policy",
        )

    return [_named("fake_pass_non_compliant_create", case_public)]


def non_compliant_modify_cases() -> list:
    def case_modify(ctx: PolicyContext, resource: ProvisionResult) -> ProvisionResult:
        return DeniedResult(
            ok=False,
            operation="modify",
            resource_id=resource.resource_id,
            operation_id=_op_id("pass-denied-modify"),
            error="Denied fake modify",
        )

    return [_named("fake_pass_non_compliant_modify", case_modify)]


def modify_exempt_resources(ctx: PolicyContext, exempt_resources) -> ProvisionResult:
    return SuccessResult(
        ok=True,
        operation="modify",
        operation_id=_op_id("pass-exempt"),
        metadata={"count": len(exempt_resources)},
    )
