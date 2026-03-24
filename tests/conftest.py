from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from tests.framework.harness import TestHarness
from tests.framework.pulumi_runner import PulumiRunner
from tests.framework.system_client import SystemClient


def _load_template(value: str) -> ModuleType:
    if value.endswith(".py") or "/" in value:
        path = Path(value).resolve()
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load policy template from path: {value}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return importlib.import_module(value)


def _case_id(case) -> str:
    return getattr(case, "case_id", getattr(case, "__name__", repr(case)))


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("policy-framework")
    group.addoption(
        "--policy-template",
        action="store",
        default="tests.policy_templates.example_policy",
        help="Import path or file path to policy module implementing the extension contract.",
    )
    group.addoption("--project-name", action="store", default="policy-tests")
    group.addoption("--work-dir", action="store", default=".")
    group.addoption("--max-cloud-concurrency", action="store", type=int, default=4)


@pytest.fixture(scope="session")
def template_module(pytestconfig: pytest.Config) -> ModuleType:
    return _load_template(pytestconfig.getoption("policy_template"))


@pytest.fixture(scope="session")
def harness(pytestconfig: pytest.Config) -> TestHarness:
    return TestHarness(
        project_name=pytestconfig.getoption("project_name"),
        work_dir=pytestconfig.getoption("work_dir"),
        max_cloud_concurrency=pytestconfig.getoption("max_cloud_concurrency"),
        runner=PulumiRunner(),
    )


@pytest.fixture
def system_client() -> SystemClient:
    return SystemClient()


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    template_opt = metafunc.config.getoption("policy_template")
    module = _load_template(template_opt)

    if "create_case" in metafunc.fixturenames:
        cases = list(module.non_compliant_create_cases())
        metafunc.parametrize("create_case", cases, ids=[_case_id(c) for c in cases])

    if "modify_case" in metafunc.fixturenames:
        cases = list(module.non_compliant_modify_cases())
        metafunc.parametrize("modify_case", cases, ids=[_case_id(c) for c in cases])
