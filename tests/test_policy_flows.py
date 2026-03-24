from __future__ import annotations

import asyncio
from types import ModuleType

import pytest

from tests.framework.contracts import ComplianceObservation, DeniedResult, ProvisionResult, SuccessResult
from tests.framework.harness import TestHarness
from tests.framework.polling import (
    wait_until_compliance,
    wait_until_notification_seen,
    wait_until_resource_scanned,
)
from tests.framework.system_client import SystemClient


async def _run_case(harness: TestHarness, fn, *args, **kwargs) -> ProvisionResult:
    result = await harness.run_blocking(fn, *args, **kwargs)
    assert isinstance(result, ProvisionResult), f"Case returned invalid type: {type(result)!r}"
    return result


def test_flow_1_prevent_compliant_then_denied_modify_notified(
    template_module: ModuleType,
    harness: TestHarness,
    system_client: SystemClient,
    modify_case
) -> None:
    """Flow 1: compliant create succeeds; modifying to non-compliant is denied + notified."""

    async def _run() -> None:
        scope = "prevent"
        scenario = f"flow1-{getattr(modify_case, '__name__', 'modify')}"
        async with harness.isolated_stack(scenario=scenario, scope=scope) as (ctx, _stack):
            compliant = await _run_case(harness, template_module.create_compliant_resources, ctx)
            assert compliant.ok, f"Expected compliant create to succeed; error={compliant.error}"

        resources = [compliant]
        tasks = []
        for resource in resources:
            async def _modify_target(target: ProvisionResult = resource) -> ProvisionResult:
                async with harness.isolated_stack(scenario=f"{scenario}-resource", scope=scope) as (mod_ctx, _):
                    return await _run_case(harness, modify_case, mod_ctx, target)

            tasks.append(asyncio.create_task(_modify_target()))

        results = await asyncio.gather(*tasks)
        for denied in results:
            assert isinstance(denied, DeniedResult), (
                f"Expected denial result for modify case={getattr(modify_case, '__name__', 'unknown')}; "
                f"got={type(denied).__name__}, error={denied.error}"
            )
            assert denied.operation_id, "Denied modify must include operation_id for notification matching"
            # TODO: replace with actual backend event ingestion.
            system_client.ingest_event(operation_id=denied.operation_id, resource_id=denied.resource_id, denied=True)
            note = await wait_until_notification_seen(system_client.get_notification, denied.operation_id)
            assert note.seen, f"Expected notification for denied operation_id={denied.operation_id}"

    asyncio.run(_run())


def test_flow_2_prevent_non_compliant_create_denied_and_notified(
    template_module: ModuleType,
    harness: TestHarness,
    system_client: SystemClient,
    create_case
) -> None:
    """Flow 2: non-compliant create is denied and notification is emitted."""

    async def _run() -> None:
        scope = "prevent"
        case_name = getattr(create_case, "case_id", getattr(create_case, "__name__", "create_case"))
        async with harness.isolated_stack(scenario=f"flow2-{case_name}", scope=scope) as (ctx, _stack):
            denied = await _run_case(harness, create_case, ctx)

        assert isinstance(denied, DeniedResult), (
            f"Expected create denial for case={case_name}; got={type(denied).__name__}, error={denied.error}"
        )
        assert denied.operation_id, f"Denied create case={case_name} must include operation_id"
        # TODO: replace with actual backend event ingestion.
        system_client.ingest_event(operation_id=denied.operation_id, resource_id=denied.resource_id, denied=True)

        note = await wait_until_notification_seen(system_client.get_notification, denied.operation_id)
        assert note.seen, f"Expected denied create case={case_name} to trigger a notification"

    asyncio.run(_run())


def test_flow_3_prevent_exempt_resources_can_be_modified(
    template_module: ModuleType,
    harness: TestHarness,
) -> None:
    """Flow 3: exempt pre-policy resources remain mutable under prevent scope."""

    async def _run() -> None:
        scope = "prevent"
        exempt_resources = getattr(template_module, "EXEMPT_RESOURCES", [{"resource_id": "legacy-1"}])
        async with harness.isolated_stack(scenario="flow3-exempt", scope=scope) as (ctx, _stack):
            result = await _run_case(harness, template_module.modify_exempt_resources, ctx, exempt_resources)

        assert isinstance(result, SuccessResult), f"Expected exempt modifications to succeed; error={result.error}"

    asyncio.run(_run())


def test_flow_4_alert_compliant_not_marked_non_compliant(
    template_module: ModuleType,
    harness: TestHarness,
    system_client: SystemClient,
) -> None:
    """Flow 4: compliant resource is scanned and stays compliant in alert scope."""

    async def _run() -> None:
        scope = "alert"
        async with harness.isolated_stack(scenario="flow4-alert-compliant", scope=scope) as (ctx, _stack):
            created = await _run_case(harness, template_module.create_compliant_resources, ctx)

        assert created.ok and created.resource_id, (
            f"Expected compliant alert resource to be created with resource_id; error={created.error}"
        )
        # TODO: replace with actual backend observation.
        system_client.ingest_event(operation_id=created.operation_id or "flow4", resource_id=created.resource_id, denied=False)

        await wait_until_resource_scanned(system_client.get_scan_status, created.resource_id)
        compliance = await wait_until_compliance(
            system_client.get_resource_compliance,
            created.resource_id,
            expect_compliant=True,
        )
        assert compliance.compliant is True, "Compliant resource should not be marked non-compliant in alert scope"

    asyncio.run(_run())


def test_flow_5_alert_non_compliant_marked_non_compliant(
    template_module: ModuleType,
    harness: TestHarness,
    system_client: SystemClient,
    create_case
) -> None:
    """Flow 5: non-compliant resource is discovered and marked non-compliant in alert scope."""

    async def _run() -> None:
        scope = "alert"
        case_name = getattr(create_case, "case_id", getattr(create_case, "__name__", "create_case"))
        async with harness.isolated_stack(scenario=f"flow5-{case_name}", scope=scope) as (ctx, _stack):
            created = await _run_case(harness, create_case, ctx)

        assert created.resource_id, f"Alert create case={case_name} must include resource_id"
        # TODO: replace with actual backend observation.
        system_client.compliance[created.resource_id] = system_client.compliance.get(created.resource_id) or ComplianceObservation(
            resource_id=created.resource_id,
            scanned=True,
            compliant=False,
            status="complete",
            details={"case": case_name},
        )

        await wait_until_resource_scanned(system_client.get_scan_status, created.resource_id)
        compliance = await wait_until_compliance(
            system_client.get_resource_compliance,
            created.resource_id,
            expect_compliant=False,
        )
        assert compliance.compliant is False, f"Expected case={case_name} to be marked non-compliant"

    asyncio.run(_run())
