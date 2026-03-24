from __future__ import annotations

import importlib
from dataclasses import dataclass

import pytest

from tests.framework.fake_backend import FakeSystemClient


@dataclass
class PolicyContext:
    scope: str
    system_client: FakeSystemClient


def pytest_addoption(parser):
    parser.addoption(
        "--policy-template",
        action="store",
        default="tests.policy_templates.dummy_policy",
        help="Dotted import path for policy template module",
    )


@pytest.fixture(scope="session")
def policy_template_module(pytestconfig):
    module_path = pytestconfig.getoption("policy_template")
    return importlib.import_module(module_path)


@pytest.fixture
def fake_system_client():
    return FakeSystemClient()


@pytest.fixture
def make_ctx(fake_system_client):
    def _make_ctx(scope: str) -> PolicyContext:
        return PolicyContext(scope=scope, system_client=fake_system_client)

    return _make_ctx
