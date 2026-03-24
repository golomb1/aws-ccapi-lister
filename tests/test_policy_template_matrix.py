from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOWS = ROOT / "tests" / "test_policy_flows.py"


def _run_for_template(template: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(FLOWS),
            f"--policy-template={template}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_fake_pass_template_passes_framework_flows() -> None:
    template = ROOT / "tests" / "policy_templates" / "fake_pass_policy.py"
    result = _run_for_template(template)
    assert result.returncode == 0, (
        "Expected fake pass policy template to pass framework flows.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_fake_fail_template_fails_framework_flows() -> None:
    template = ROOT / "tests" / "policy_templates" / "fake_fail_policy.py"
    result = _run_for_template(template)
    assert result.returncode != 0, (
        "Expected fake fail policy template to fail framework flows.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
