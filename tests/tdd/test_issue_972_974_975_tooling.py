"""TDD RED — Bündel #974(+#915), #972, #975: Validator-/Test-Tooling.

Beweist Verhalten (kein Mock, keine Dateiinhalt-Checks):

- #974: _check_plausibility() gegen die ECHTE, real zugestellte evening-Mail
  (Trip TDD-794, Etappe 3 — dieselbe Mail wie im Issue-Nachweis) mit
  "Nacht am Ziel"-Sektion: Nachtstunden 00/02/04 dürfen keinen
  Tagesfenster-Fehler auslösen; eine Nachtstunde in der Tagestabelle
  (vor dem Nacht-Marker) muss weiterhin geflaggt werden.
- #972: Die drei Hooks müssen bei gesetzten GZ_TEST_IMAP_* die
  Test-Credentials priorisieren. Nachweis über echten IMAP-Login gegen
  mail.henemm.com:993: GZ_IMAP_* wird auf einen ungültigen Decoy gesetzt —
  wählt der Hook (falsch) die Prod-Variablen, scheitert der echte Login;
  wählt er (korrekt) die Test-Credentials, gelingt er.
- #975: `npm test` in frontend/ muss den node:test-Runner ausführen und
  mit Exit 0 + realer Pass-Anzahl enden (kein vitest, keine e2e-Specs).
"""
from __future__ import annotations

import imaplib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / ".claude" / "hooks"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "issue_974_evening_night_mail.html"

# Ungültiger Decoy: Wenn ein Hook fälschlich GZ_IMAP_* statt GZ_TEST_IMAP_*
# wählt, schlägt der echte Login mit diesen Werten sicher fehl.
DECOY_USER = "issue972-decoy-invalid-user"
DECOY_PASS = "issue972-decoy-invalid-pass"


def _load_hook(filename: str, alias: str):
    """Hook-Modul isoliert laden (Muster aus test_issue_733)."""
    spec = importlib.util.spec_from_file_location(alias, str(HOOKS / filename))
    if spec is None or spec.loader is None:
        raise ImportError(f"Hook nicht ladbar: {filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _require_test_creds():
    """Echte Test-Postfach-Credentials müssen konfiguriert sein (kein Skip-Schlupfloch:
    fehlen sie, ist das ein harter Fehler — die .env muss sie bereitstellen)."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from app.config import Settings

    settings = Settings()
    assert settings.test_imap_user and settings.test_imap_pass, (
        "GZ_TEST_IMAP_USER/GZ_TEST_IMAP_PASS fehlen in der Umgebung/.env — "
        "ohne sie ist der #972-Verhaltensnachweis nicht führbar"
    )


# --------------------------------------------------------------------------- #
# #974 — Tagesfenster-Check vs. "Nacht am Ziel"
# --------------------------------------------------------------------------- #
class TestIssue974NightWindow:
    def test_real_evening_mail_night_hours_tolerated(self):
        """AC-1 (Kernfall): Die echte evening-Mail mit Nacht-Sektion darf keinen
        Tagesfenster-Fehler produzieren — 00/02/04 liegen im Nacht-Block."""
        html = FIXTURE.read_text(encoding="utf-8")
        assert "Nacht am Ziel" in html, "Fixture muss die Nacht-Sektion enthalten"

        mod = _load_hook("briefing_mail_validator.py", "bmv974")
        errors = mod._check_plausibility(html)
        window_errors = [e for e in errors if "Tagesfenster" in e]
        assert window_errors == [], (
            f"Nachtstunden der 'Nacht am Ziel'-Sektion fälschlich geflaggt: {window_errors}"
        )

    def test_night_hour_in_day_table_still_flagged(self):
        """AC-1 (Schärfe-Erhalt): Eine Nachtstunde (03) in der TAGES-Tabelle
        (vor dem Nacht-Marker) muss weiterhin einen Fenster-Fehler auslösen."""
        html = FIXTURE.read_text(encoding="utf-8")
        marker_pos = html.index("Nacht am Ziel")
        # Echte Zeit-Zelle im Tages-Teil einfügen (identischer Anker wie der
        # Renderer: data-label="Time") — direkt vor dem Nacht-Marker.
        injected = (
            html[:marker_pos]
            + '<td data-label="Time">03 </td>'
            + html[marker_pos:]
        )
        mod = _load_hook("briefing_mail_validator.py", "bmv974b")
        errors = mod._check_plausibility(injected)
        assert any("03" in e and "Tagesfenster" in e for e in errors), (
            f"Nachtstunde 03 in der Tagestabelle wurde NICHT geflaggt — "
            f"Prüfschärfe verloren. Fehlerliste: {errors}"
        )


# --------------------------------------------------------------------------- #
# #972 — Test-Postfach-Credentials priorisieren (echte IMAP-Logins)
# --------------------------------------------------------------------------- #
class TestIssue972TestCredPriority:
    """GZ_IMAP_* zeigt auf einen ungültigen Decoy, GZ_TEST_IMAP_* ist echt.
    Vor dem Fix wählen die Hooks den Decoy → echter Login scheitert (RED).
    Nach dem Fix wählen sie die Test-Credentials → Login gelingt (GREEN)."""

    @pytest.fixture(autouse=True)
    def _decoy_prod_creds(self, monkeypatch):
        _require_test_creds()
        monkeypatch.setenv("GZ_IMAP_USER", DECOY_USER)
        monkeypatch.setenv("GZ_IMAP_PASS", DECOY_PASS)

    def test_briefing_validator_prefers_test_creds(self):
        mod = _load_hook("briefing_mail_validator.py", "bmv972")
        try:
            msg = mod.fetch_latest_message(max_scan=10)
        except imaplib.IMAP4.error as e:
            pytest.fail(
                f"IMAP-Login scheiterte — Hook hat die Prod-Variablen (Decoy) "
                f"statt GZ_TEST_IMAP_* gewählt: {e}"
            )
        except ValueError:
            # "keine passende Mail in den letzten N" — Login war erfolgreich,
            # d.h. die Test-Credentials wurden gewählt. Für diesen Test ok.
            return
        assert msg is not None

    def test_email_spec_validator_prefers_test_creds(self):
        mod = _load_hook("email_spec_validator.py", "esv972")
        try:
            html = mod.fetch_latest_email()
        except imaplib.IMAP4.error as e:
            pytest.fail(
                f"IMAP-Login scheiterte — Hook hat die Prod-Variablen (Decoy) "
                f"statt GZ_TEST_IMAP_* gewählt: {e}"
            )
        assert isinstance(html, str) and html, "Login ok, aber kein Mail-Body geliefert"

    def test_e2e_browser_test_prefers_test_creds(self):
        mod = _load_hook("e2e_browser_test.py", "ebt972")
        ok, detail = mod.run_email_test("Nacht am Ziel", send_from_ui=False)
        # run_email_test kapselt Fehler in (False, "IMAP Fehler: ..."):
        # Ein Auth-/IMAP-Fehler beweist die falsche Credential-Wahl.
        assert "IMAP Fehler" not in detail and "IMAP nicht konfiguriert" not in detail, (
            f"IMAP-Zugriff scheiterte — Hook hat die Prod-Variablen (Decoy) "
            f"statt GZ_TEST_IMAP_* gewählt: {detail}"
        )


# --------------------------------------------------------------------------- #
# #975 — `npm test` führt den node:test-Runner real aus
# --------------------------------------------------------------------------- #
class TestIssue975FrontendTestScript:
    def test_npm_test_runs_green_with_real_passes(self):
        """AC-3: `npm test` in frontend/ endet mit Exit 0, führt >0 Tests real
        aus (TAP `# pass`), meldet 0 Fehlschläge und importiert keine
        Playwright-Specs aus e2e/."""
        result = subprocess.run(
            ["npm", "test"],
            cwd=str(REPO_ROOT / "frontend"),
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"`npm test` endete mit Exit {result.returncode} — "
            f"Ausgabe (Ende): …{output[-1500:]}"
        )
        pass_match = re.search(r"^# pass (\d+)", output, re.MULTILINE)
        fail_match = re.search(r"^# fail (\d+)", output, re.MULTILINE)
        assert pass_match and int(pass_match.group(1)) > 0, (
            "Keine reale Pass-Anzahl in der TAP-Ausgabe — Runner lief nicht"
        )
        assert fail_match and int(fail_match.group(1)) == 0, (
            f"Suite hat Fehlschläge: # fail {fail_match.group(1) if fail_match else '?'}"
        )
        assert not re.search(r"^# Subtest: .*e2e/", output, re.MULTILINE), (
            "Playwright-Specs aus e2e/ wurden als Suiten importiert"
        )
