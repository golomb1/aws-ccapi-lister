from __future__ import annotations

from tests.framework.fake_backend import DeniedResult, SuccessResult


def test_flow_1_compliant_create(policy_template_module, make_ctx):
    """Flow 1: compliant creates should succeed in prevent scope."""
    ctx = make_ctx("prevent")
    results = policy_template_module.create_compliant_resources(ctx)

    assert results
    assert all(isinstance(result, SuccessResult) for result in results)
    for result in results:
        operation = ctx.system_client.get_operation(result.operation_id)
        assert operation.status == "applied"
        assert ctx.system_client.lookup_notification(result.operation_id).endswith(":ok")


def test_flow_2_prevent_non_compliant_creates(policy_template_module, make_ctx):
    """Flow 2: non-compliant creates should be denied in prevent scope."""
    ctx = make_ctx("prevent")

    for case in policy_template_module.non_compliant_create_cases():
        result = policy_template_module.run_case(ctx, case, compliant=False)
        assert isinstance(result, DeniedResult)
        op = ctx.system_client.get_operation(result.operation_id)
        assert op.status == "denied"
        assert "prevented" in ctx.system_client.lookup_notification(result.operation_id)


def test_flow_3_prevent_non_compliant_modifications(policy_template_module, make_ctx):
    """Flow 3: non-compliant modifications should be denied in prevent scope."""
    ctx = make_ctx("prevent")
    policy_template_module.create_compliant_resources(ctx)

    for case in policy_template_module.non_compliant_modify_cases():
        result = policy_template_module.run_case(ctx, case, compliant=False)
        assert isinstance(result, DeniedResult)


def test_flow_4_allow_exempt_modifications(policy_template_module, make_ctx):
    """Flow 4: exempt modifications are allowed even when non-compliant."""
    ctx = make_ctx("prevent")
    exempt_ids = ["legacy-instance-001"]

    results = policy_template_module.modify_exempt_resources(ctx, exempt_ids)

    assert all(isinstance(result, SuccessResult) for result in results)
    for result in results:
        op = ctx.system_client.get_operation(result.operation_id)
        assert op.status == "applied"
        assert op.is_exempt is True
        assert ctx.system_client.lookup_notification(result.operation_id).endswith(":ok")


def test_flow_5_alert_scope_scanning_and_compliance(policy_template_module, make_ctx):
    """Flow 5: alert scope allows action, then scan/classification eventually completes."""
    ctx = make_ctx("alert")
    case = policy_template_module.non_compliant_create_cases()[0]

    result = policy_template_module.run_case(ctx, case, compliant=False)

    assert isinstance(result, SuccessResult)
    assert result.non_compliant_resource_ids == [case.resource_id]
    assert ctx.system_client.lookup_notification(result.operation_id).endswith(":scan_scheduled")

    # Poll until scan completes.
    assert ctx.system_client.is_scan_complete(result.operation_id) is False
    assert ctx.system_client.is_scan_complete(result.operation_id) is True

    assert ctx.system_client.compliance_state(case.resource_id) == "non-compliant"
