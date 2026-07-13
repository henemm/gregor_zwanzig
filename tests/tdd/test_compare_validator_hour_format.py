"""Issue #1242 — `validate_hourly_table` des Ortsvergleichs-Pruefers muss das
Zeit-Format erwarten, das der Renderer laut freigegebener Spec zu #1237 auch
wirklich erzeugt: die nackte Stunde (`09`), nicht `09:00`.

Die Stunden-Vollstaendigkeitspruefung war bis hierher von KEINEM Test gedeckt
(die Bestandstests in `test_issue_1150_compare_validator_hourly.py` rufen nur
`validate_structure`). Genau deshalb blieb die Format-Kollision unbemerkt, bis
sie an einer echt zugestellten Mail auffiel. Diese Datei schliesst die Luecke:
gepruefft wird gegen den ECHTEN `render_compare_html`-Output, kein Fixture-Text.
"""
import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

VALIDATOR_PATH = ROOT / ".claude" / "hooks" / "email_spec_validator.py"

# Das Pruef-Fenster folgt dem, was der geteilte Fixture-Helfer
# (`_make_comparison_result`) tatsaechlich an Stunden-Datenpunkten erzeugt: 09
# und 10. Ein weiteres Fenster wuerde nicht das Zeit-FORMAT pruefen (worum es
# hier geht), sondern die Laenge der Fixture.
TIME_START, TIME_END = 9, 10


def _load_validator():
    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator nicht gefunden: {VALIDATOR_PATH}")
    spec = importlib.util.spec_from_file_location("email_spec_validator", VALIDATOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _real_compare_html(names: list[str]) -> str:
    """Eine echt gerenderte Ortsvergleichs-Mail mit Stundentabellen."""
    from app.profile import ActivityProfile
    from output.renderers.email.compare_html import render_compare_html

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_issue_1150_compare_validator_hourly import _make_comparison_result

    result = _make_comparison_result(names)
    return render_compare_html(
        result, profile=ActivityProfile.ALLGEMEIN, hourly_enabled=True
    )


def test_hour_completeness_accepts_the_format_the_renderer_emits():
    """Given eine echt gerenderte Vergleichs-Mail, deren Zeit-Zellen laut
    PO-Freigabe (#1237) nur die Stunde tragen (`09`) / When
    `validate_hourly_table` darueber laeuft / Then meldet der Pruefer KEINE
    fehlenden Stunden — er darf eine korrekte Mail nicht zurueckweisen."""
    mod = _load_validator()
    html = _real_compare_html(["Ort A", "Ort B", "Ort C"])

    errors = mod.validate_hourly_table(html, TIME_START, TIME_END)

    assert errors == [], (
        "Der Pruefer weist eine korrekt gerenderte Mail zurueck — er erwartet "
        f"noch das alte HH:MM-Format. Fehler: {errors}"
    )


def test_hour_completeness_still_flags_a_genuinely_missing_hour():
    """Given dieselbe Mail, aus der eine Stunden-ZEILE entfernt wurde / When
    `validate_hourly_table` darueber laeuft / Then meldet der Pruefer die
    fehlende Stunde — die Vollstaendigkeitspruefung bleibt scharf und wird
    nicht etwa dadurch 'gruen', dass sie nichts mehr findet."""
    import re

    mod = _load_validator()
    html = _real_compare_html(["Ort A", "Ort B", "Ort C"])

    # Genau die Datenzeile der Stunde 10 aus der ERSTEN Stundentabelle loeschen.
    row_re = re.compile(r"<tr[^>]*>\s*<td[^>]*>\s*10\s*</td>.*?</tr>", re.S)
    mutilated, n = row_re.subn("", html, count=1)
    assert n == 1, "Testaufbau: Stunden-Zeile '10' nicht gefunden — Renderer-Format geprueft?"

    errors = mod.validate_hourly_table(mutilated, TIME_START, TIME_END)

    assert errors, "Eine fehlende Stunde MUSS gemeldet werden"
    assert any("10" in e for e in errors), f"Fehlende Stunde 10 nicht benannt: {errors}"
