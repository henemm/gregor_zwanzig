"""RED-Tests für Issue #201 — Mocks aus tests/tdd/test_html_email.py entfernen.

Spec: docs/specs/bugfix/issue_201_html_email_mocks_removal.md
Test-Manifest: docs/specs/tests/bug_201_html_email_mocks_tests.md
"""
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "tests/tdd/test_html_email.py"


def test_ac1_no_mock_imports_or_calls():
    """AC-1: 0 Mock-Imports oder MockSMTP/patch-Calls in target file."""
    content = TARGET.read_text()
    forbidden = [
        "from unittest.mock",
        "import mock",
        "MockSMTP",
        'patch("smtplib',
        'patch("time',
        "settings = Mock()",
        "= Mock()",
    ]
    found = [pat for pat in forbidden if pat in content]
    assert found == [], f"Verbotene Mock-Patterns gefunden: {found}"


def test_ac2_only_two_test_classes():
    """AC-2: Genau 2 Test-Klassen (TestSubscriptionEmailGeneration + TestRealStalwartE2E)."""
    content = TARGET.read_text()
    classes = re.findall(r"^class (Test\w+)", content, re.MULTILINE)
    assert sorted(classes) == sorted([
        "TestSubscriptionEmailGeneration",
        "TestRealStalwartE2E",
    ]), f"Erwartet [TestSubscriptionEmailGeneration, TestRealStalwartE2E], got {classes}"


def test_ac3_imports_point_to_services():
    """AC-3: 0 Imports von web.pages.compare; statt dessen services.* Imports vorhanden."""
    content = TARGET.read_text()
    # String-Konkat verhindert, dass dieser Negativ-Check selbst vom
    # Epic-#129-A.3-Grep als Import-Treffer gemeldet wird.
    assert ("from " + "web.pages.compare") not in content
    assert ("from " + "src.web.pages.compare") not in content
    assert (
        "from services.comparison_renderers" in content
        or "from services.compare_subscription" in content
    )


def test_ac4_collect_only_returns_two_tests():
    """AC-4: pytest --collect-only sammelt genau 2 Tests (inkl. via marker deselected)."""
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/tdd/test_html_email.py", "--collect-only"],
        capture_output=True, text=True, cwd=REPO,
    )
    # Parse footer: "N/M tests collected (X deselected)" oder "M tests collected"
    # M = total count vor Marker-Filter (das wollen wir = 2)
    match = re.search(
        r"(\d+)/(\d+)\s+tests?\s+collected|(\d+)\s+tests?\s+collected",
        result.stdout,
    )
    assert match, f"Konnte 'tests collected' nicht parsen aus:\n{result.stdout}"
    if match.group(2):
        total = int(match.group(2))
    else:
        total = int(match.group(3))
    assert total == 2, (
        f"Erwartet 2 Tests gesammelt, got {total}\nOutput:\n{result.stdout}"
    )


def test_ac5_scoped_run_one_pass_one_skip():
    """AC-5: scoped pytest läuft mit 1 PASS und 1 SKIP, 0 FAIL."""
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/tdd/test_html_email.py", "-v", "--tb=short"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert "0 failed" in result.stdout or "failed" not in result.stdout, (
        f"Es gibt failed Tests:\n{result.stdout[-2000:]}"
    )
    assert "1 deselected" in result.stdout, (
        "TestRealGmailE2E muss via @pytest.mark.email deselected sein "
        f"(spec: 1 PASS + 1 SKIP/deselected). Output:\n{result.stdout[-1500:]}"
    )
