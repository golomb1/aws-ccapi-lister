"""Example policy module implementing the developer extension contract.

How to add a new policy test module:
- Copy this file.
- Keep functions declarative; return case callables and basic result objects.
- Let framework manage stacks, orchestration, retries, and reporting.
"""

from __future__ import annotations

from uuid import uuid4

from tests.framework.contracts import DeniedResult, PolicyContext, ProvisionResult, SuccessResult

EXEMPT_RESOURCES = [
    {"resource_id": "legacy-bucket-001", "type": "s3"},
    {"resource_id": "legacy-sg-001", "type": "security-group"},
]


def _op_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def named_case(case_id: str, fn):
    fn.case_id = case_id
    return fn


def create_compliant_resources(ctx: PolicyContext) -> ProvisionResult:
    """Create one compliant sample resource."""

    return SuccessResult(
        ok=True,
        operation="create",
        resource_id=f"compliant-{ctx.stack_name}",
        operation_id=_op_id("create-ok"),
        metadata={"scope": ctx.scope, "template": "example"},
    )


def non_compliant_create_cases() -> list:
    def deny_public_bucket(ctx: PolicyContext) -> ProvisionResult:
        if ctx.scope == "alert":
            return SuccessResult(
                ok=True,
                operation="create",
                resource_id=f"bucket-public-{ctx.stack_name}",
                operation_id=_op_id("alert-create-public"),
                metadata={"reason": "public bucket", "scope": "alert"},
            )
        return DeniedResult(
            ok=False,
            operation="create",
            resource_id=f"bucket-public-{ctx.stack_name}",
            operation_id=_op_id("deny-create-public"),
            error="Bucket ACL allows public access",
            metadata={"reason": "public bucket"},
        )

    def deny_open_security_group(ctx: PolicyContext) -> ProvisionResult:
        if ctx.scope == "alert":
            return SuccessResult(
                ok=True,
                operation="create",
                resource_id=f"sg-open-{ctx.stack_name}",
                operation_id=_op_id("alert-create-sg"),
                metadata={"reason": "0.0.0.0/0 ssh", "scope": "alert"},
            )
        return DeniedResult(
            ok=False,
            operation="create",
            resource_id=f"sg-open-{ctx.stack_name}",
            operation_id=_op_id("deny-create-sg"),
            error="Security group exposes SSH to internet",
            metadata={"reason": "0.0.0.0/0 ssh"},
        )

    return [
        named_case("create_public_bucket", deny_public_bucket),
        named_case("create_open_security_group", deny_open_security_group),
    ]


def non_compliant_modify_cases() -> list:
    def make_bucket_public(ctx: PolicyContext, resource: ProvisionResult) -> ProvisionResult:
        return DeniedResult(
            ok=False,
            operation="modify",
            resource_id=resource.resource_id,
            operation_id=_op_id("deny-modify-public"),
            error="Prevent policy denied making bucket public",
            metadata={"source": resource.resource_id, "scope": ctx.scope},
        )

    def open_ingress_to_world(ctx: PolicyContext, resource: ProvisionResult) -> ProvisionResult:
        return DeniedResult(
            ok=False,
            operation="modify",
            resource_id=resource.resource_id,
            operation_id=_op_id("deny-modify-sg"),
            error="Prevent policy denied broad ingress rule",
            metadata={"source": resource.resource_id, "scope": ctx.scope},
        )

    return [
        named_case("modify_bucket_to_public", make_bucket_public),
        named_case("modify_sg_to_open_ingress", open_ingress_to_world),
    ]


def modify_exempt_resources(ctx: PolicyContext, exempt_resources) -> ProvisionResult:
    return SuccessResult(
        ok=True,
        operation="modify",
        operation_id=_op_id("modify-exempt"),
        metadata={"scope": ctx.scope, "modified": len(exempt_resources)},
    )
