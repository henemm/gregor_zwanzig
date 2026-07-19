# doc-compliance-test
"""Struktur-Test: Compare-E2E-Suite nutzt storageState statt Pro-Test-Login.

Spec: docs/specs/modules/issue_1321_e2e_storagestate_migration.md

AC-3 (struktureller Teilnachweis). Diese Tests pruefen per Quelltext-
Introspektion, dass die sechs betroffenen Playwright-Spec-Dateien das alte
Pro-Test-UI-Login-Muster nicht mehr enthalten und die Staging-Config sie
ausschliesslich im storageState-Projekt referenziert (CLAUDE.md-Ausnahme
`# doc-compliance-test` fuer Quelltext-Introspektion statt Verhaltensnachweis).

Der eigentliche Verhaltensnachweis fuer AC-1/AC-2 (Login-Budget, Laufzeit,
zwei Volllaeufe hintereinander gruen) ist Live-E2E und laeuft gegen Staging
im Rahmen von /e2e-verify - nicht Teil dieser Kern-Schicht.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = REPO_ROOT / "frontend" / "e2e"
CONFIG_FILE = REPO_ROOT / "frontend" / "playwright.1273-s4c.staging.config.ts"

MIGRATED_FILES = [
    "compare-radar-toggle.spec.ts",
    "compare-alarm-config.spec.ts",
    "compare-legacy-fields-survive-save.spec.ts",
    "versand-tab-vergleich.spec.ts",
    "layout-tab-vergleich.spec.ts",
    "issue-718-idealwert-validation.spec.ts",
]


def test_migrated_files_no_longer_import_or_call_login():  # doc-compliance-test
    """AC-3: Keiner der sechs migrierten Testfaelle importiert/ruft noch login() auf."""
    offenders = []
    for name in MIGRATED_FILES:
        text = (E2E_DIR / name).read_text(encoding="utf-8")
        if "login(" in text or "{ login }" in text:
            offenders.append(name)
    assert offenders == [], (
        "Diese Dateien rufen/importieren noch login(), obwohl sie auf "
        f"storageState migriert sein sollten: {offenders}"
    )


def test_config_no_longer_has_chromium_login_project():  # doc-compliance-test
    """AC-3: Das obsolete chromium-login-Projekt existiert nicht mehr in der Config."""
    text = CONFIG_FILE.read_text(encoding="utf-8")
    assert "chromium-login" not in text, (
        "playwright.1273-s4c.staging.config.ts enthaelt noch das obsolete "
        "chromium-login-Projekt - migrierte Dateien gehoeren ausschliesslich "
        "ins chromium-storagestate-Projekt."
    )


def test_config_storagestate_project_lists_all_migrated_files():  # doc-compliance-test
    """AC-3: Das storageState-Projekt referenziert alle sechs migrierten Dateien.

    Toleriert beide gueltigen Regex-Schreibweisen fuer den Punkt (`.` oder `\\.`)
    - beides matcht den literalen Dateinamen, nur die Escaping-Strenge unterscheidet
    sich. Ein reiner Substring-Check waere hier zu eng gewesen.
    """
    text = CONFIG_FILE.read_text(encoding="utf-8")
    assert "chromium-storagestate" in text, "chromium-storagestate-Projekt fehlt in der Config."
    storagestate_block = text[text.index("chromium-storagestate"):]
    missing = [
        name
        for name in MIGRATED_FILES
        if not re.search(re.escape(name).replace(r"\.", r"\\?\."), storagestate_block)
    ]
    assert missing == [], (
        f"chromium-storagestate-Projekt referenziert nicht alle migrierten Dateien: {missing}"
    )
