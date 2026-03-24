"""Intentionally broken policy template to demonstrate failing test reporting."""

from __future__ import annotations

from tests.policy_templates import dummy_policy


def create_compliant_resources(ctx):
    return dummy_policy.create_compliant_resources(ctx)


def non_compliant_create_cases():
    return dummy_policy.non_compliant_create_cases()


def non_compliant_modify_cases():
    return dummy_policy.non_compliant_modify_cases()


def modify_exempt_resources(ctx, exempt_resources):
    return dummy_policy.modify_exempt_resources(ctx, exempt_resources)


def run_case(ctx, case, *, compliant: bool):
    # Intentionally wrong for CI-report demo: forces allow in prevent scope,
    # which causes the framework tests to fail and appear in the JUnit report.
    return ctx.system_client.execute(
        case.operation,
        case.resource_id,
        scope=ctx.scope,
        compliant=True,
    )
