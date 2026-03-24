"""Dummy policy template for CI that does not use real cloud APIs."""

from __future__ import annotations

from dataclasses import dataclass

from tests.framework.fake_backend import DeniedResult, SuccessResult


@dataclass(frozen=True)
class DummyCase:
    name: str
    operation: str
    resource_id: str


def create_compliant_resources(ctx):
    return [
        ctx.system_client.execute(
            "create_private_bucket",
            "bucket-private-001",
            scope=ctx.scope,
            compliant=True,
        ),
        ctx.system_client.execute(
            "create_instance_with_imdsv2",
            "instance-imdsv2-001",
            scope=ctx.scope,
            compliant=True,
        ),
    ]


def non_compliant_create_cases():
    return [
        DummyCase(
            name="create_public_bucket",
            operation="create_public_bucket",
            resource_id="bucket-public-001",
        ),
        DummyCase(
            name="create_instance_with_imdsv1",
            operation="create_instance_with_imdsv1",
            resource_id="instance-imdsv1-001",
        ),
    ]


def non_compliant_modify_cases():
    return [
        DummyCase(
            name="make_bucket_public",
            operation="make_bucket_public",
            resource_id="bucket-private-001",
        ),
        DummyCase(
            name="enable_imdsv1",
            operation="enable_imdsv1",
            resource_id="instance-imdsv2-001",
        ),
    ]


def modify_exempt_resources(ctx, exempt_resources):
    results = []
    for resource_id in exempt_resources:
        results.append(
            ctx.system_client.execute(
                "edit_legacy_exempt_instance",
                resource_id,
                scope=ctx.scope,
                compliant=False,
                exempt=True,
            )
        )
    return results


def run_case(ctx, case: DummyCase, *, compliant: bool):
    result = ctx.system_client.execute(
        case.operation,
        case.resource_id,
        scope=ctx.scope,
        compliant=compliant,
    )
    if ctx.scope == "prevent" and not compliant:
        assert isinstance(result, DeniedResult)
    else:
        assert isinstance(result, SuccessResult)
    return result
