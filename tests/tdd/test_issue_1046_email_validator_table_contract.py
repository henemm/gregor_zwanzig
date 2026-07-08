"""TDD RED — Issue #1108: Compare-Mail-Validator auf v2-Vertrag umgestellt.

Beweist Verhalten (kein Mock, keine Dateiinhalt-Checks) direkt gegen die
reinen Parsing-/Pruef-Funktionen aus `.claude/hooks/email_spec_validator.py`.

Die v2-Fixtures stammen — mit Ausnahme der bewusst synthetischen ALT-Struktur-
Fixture (AC-2, Anti-Erosion: eine Alt-Mail darf niemals als vertragskonform
durchgehen) — direkt aus `render_compare_html()` (echte ComparisonResult/
LocationResult/OfficialAlert-Objekte, Issue #1110). Der Renderer ist die
Quelle der Wahrheit fuer den v2-Vertrag, keine handgeschriebenen HTML-Strings.

AC-8 (Gate-Nachweis gegen eine echte, frisch zugestellte Staging-Mail) ist
hier bewusst NICHT als pytest-Test enthalten — der End-to-End-Nachweis wird
erst nach Deploy im Post-Push-Workflow gegen die echte IMAP-Mail erbracht
(SPEC: docs/specs/modules/issue_1108_email_spec_validator_v2.md, AC-8).

SPEC: docs/specs/modules/issue_1108_email_spec_validator_v2.md
"""
from __future__ import annotations

import importlib.util
import re
from datetime import date, datetime
from pathlib import Path

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.email.compare_html import render_compare_html


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"


def _load_validator():
    """Lade den Validator als isoliertes Modul (vermeidet sys.modules-Kontamination)."""
    spec = importlib.util.spec_from_file_location("esv1046v2", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# v2-Fixture-Erzeugung ueber den ECHTEN Renderer (kein Mock, kein Handbau)
# --------------------------------------------------------------------------- #

def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=43.1, lon=6.2, elevation_m=200)


def _dp(hour: int) -> ForecastDataPoint:
    """Ein plausibler, vollstaendiger Datenpunkt (alle 8 Stundentabellen-Spalten)."""
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0),
        t2m_c=24.0,
        wind_chill_c=23.0,
        wind10m_kmh=12.0,
        gust_kmh=22.0,
        precip_1h_mm=0.0,
        cloud_total_pct=40,
        uv_index=5.0,
    )


def _make_three_location_result(*, hourly_names: list[str] | None = None) -> ComparisonResult:
    """3 Orte (Collobrières, Marseille, Fréjus), je 3 Stunden Daten.

    hourly_names: welche Orte eine Stundentabelle bekommen (hourly_data
    nicht-leer) -- ein Ort ohne hourly_data faellt aus dem Stunden-Block,
    bleibt aber in der Uebersichtstabelle gelistet (AC-3-Grundlage,
    _render_location_section() liefert bei leerem hourly_data "").
    """
    names = ["Collobrières", "Marseille", "Fréjus"]
    if hourly_names is None:
        hourly_names = names
    locations = [
        LocationResult(
            location=_loc(name.lower(), name),
            temp_max=26.0,
            wind_max=14.0,
            sunny_hours=5.0,
            cloud_avg=40,
            official_alerts=[],
            hourly_data=[_dp(h) for h in (9, 10, 11)] if name in hourly_names else [],
        )
        for name in names
    ]
    return ComparisonResult(
        locations=locations,
        time_window=(9, 16),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 1),
    )


def _render_v2(**kwargs) -> str:
    result = _make_three_location_result()
    return render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, **kwargs)


# --------------------------------------------------------------------------- #
# ALT-Struktur-Fixture (bewusst synthetisch, Anti-Erosion — AC-2): bildet den
# alten #460/#1046-Vertrag VOLLSTAENDIG nach (2 Header-Stats-Tabellen + 1
# class="matrix-table"-Tabelle mit den 8 alten englischen Zeilen-Labels +
# Stunden-Tabellen + Winner-Box/"Recommendation"-Pflichtsektion). Damit gilt
# sie unter dem HEUTIGEN (unmigrierten) Validator als vollstaendig
# vertragskonform (0 Fehler) -- genau DAS beweist die eigentliche
# Anti-Regressions-Anforderung von AC-2: eine solche Alt-Mail darf nach der
# v2-Migration NIE MEHR als fehlerfrei durchgehen. Ein synthetisches Fixture,
# das schon unter dem alten Validator Fehler zeigt (z. B. unvollstaendige
# Zeilenanzahl), wuerde AC-2 nicht echt beweisen.
# --------------------------------------------------------------------------- #

_ALT_HEADER_GRID_ROW = "<tr><th>Profil</th><th>Orte</th><th>Horizont</th><th>Erstellt</th></tr>"

_ALT_MATRIX_ROWS = (
    "<tr><th>Metric</th><th>#1 LocationA</th><th>#2 LocationB</th><th>#3 LocationC</th></tr>"
    "<tr><td>Score</td><td>71</td><td>68</td><td>75</td></tr>"
    "<tr><td>Snow Depth</td><td>-</td><td>-</td><td>-</td></tr>"
    "<tr><td>New Snow</td><td>-</td><td>-</td><td>-</td></tr>"
    "<tr><td>Wind/Gusts</td><td>10/25 SW</td><td>12/30 NW</td><td>8/20 N</td></tr>"
    "<tr><td>Temperature (felt)</td><td>18</td><td>16</td><td>20</td></tr>"
    "<tr><td>Sunny Hours</td><td>~5h</td><td>0h</td><td>~3h</td></tr>"
    "<tr><td>Cloud Cover</td><td>42%</td><td>60%*</td><td>30%</td></tr>"
)

_ALT_REQUIRED_SECTION_MARKERS = "<div>Time Window</div><div>Hourly Overview</div><div>Recommendation</div>"


def _alt_structure_body() -> str:
    """Vollstaendig vertragskonforme Alt-Mail (Vor-#1110-Vertrag): 2
    Header-Stats-Varianten + 1 class='matrix-table' mit 8 Zeilen (englische
    Labels, u. a. 'Snow Depth') + 3 Stunden-Tabellen + Winner-Box/
    'Recommendation'-Pflichtsektion."""
    header_desktop = f'<table class="header-stats-desktop">{_ALT_HEADER_GRID_ROW}</table>'
    header_mobile = f'<table class="header-stats-mobile">{_ALT_HEADER_GRID_ROW}</table>'
    matrix = f'<table class="matrix-table" cellspacing="0" cellpadding="0">{_ALT_MATRIX_ROWS}</table>'
    hourly_tables = "".join(
        f"<table><tr><td>{h:02d}:00</td><td>12°</td><td>10</td><td>20%</td></tr></table>"
        for h in (9, 10, 11)
    )
    return header_desktop + header_mobile + matrix + hourly_tables + _ALT_REQUIRED_SECTION_MARKERS


# --------------------------------------------------------------------------- #
# AC-1 — echte v2-Render-Output (render_compare_html) -> keine Strukturfehler
# --------------------------------------------------------------------------- #

def test_ac1_echter_v2_render_output_liefert_keine_strukturfehler():
    mod = _load_validator()
    html = _render_v2()

    errors = mod.validate_structure(html)

    assert errors == [], f"Erwartet: keine Strukturfehler gegen echten v2-Render-Output, bekommen: {errors}"


# --------------------------------------------------------------------------- #
# AC-2 — Alt-Struktur (Winner-Box + matrix-table + englische Labels) -> Fehler
# --------------------------------------------------------------------------- #

def test_ac2_alte_struktur_mit_winner_box_und_matrix_table_wird_abgelehnt():
    mod = _load_validator()
    body = _alt_structure_body()

    errors = mod.validate_structure(body)

    assert errors, (
        "Erwartet: eine Alt-Struktur-Mail (Winner-Box + class='matrix-table' + "
        "englische Labels) darf niemals als vertragskonform (leere Fehlerliste) durchgehen"
    )


# --------------------------------------------------------------------------- #
# AC-3 — Uebersicht listet 3 Orte, nur 2 Stundentabellen -> Fehler nennt Ort
# --------------------------------------------------------------------------- #

def test_ac3_fehlende_stundentabelle_fuer_gelisteten_ort_wird_benannt():
    mod = _load_validator()
    # Fréjus bleibt in der Uebersichtstabelle (LocationResult ohne Fehler),
    # bekommt aber keine Stundentabelle (hourly_data leer).
    html = _render_v2()
    result_no_frejus_hours = _make_three_location_result(hourly_names=["Collobrières", "Marseille"])
    html = render_compare_html(result_no_frejus_hours, profile=ActivityProfile.ALLGEMEIN)

    errors = mod.validate_structure(html)

    assert errors, "Erwartet: Strukturfehler, da Fréjus in der Uebersicht gelistet ist, aber keine Stundentabelle hat"
    assert any("Fréjus" in e for e in errors), (
        f"Erwartet: Fehlermeldung benennt konkret den fehlenden Ort 'Fréjus', bekommen: {errors}"
    )


# --------------------------------------------------------------------------- #
# AC-4 — Score-/Winner-Sprache in einer v2-Mail -> Fehler (Negativ-Check)
# --------------------------------------------------------------------------- #

def test_ac4_score_winner_sprache_in_v2_mail_wird_als_fehler_gemeldet():
    mod = _load_validator()
    html = _render_v2()
    # Kuenstliche Score-/Winner-Zeile in echten v2-Render-Output injiziert
    # (kein Handbau der gesamten Mail -- nur der zu erkennende Verstoss).
    html_mit_score = html.replace(
        "</body>", "<div>Empfehlung: Fréjus (Score 87)</div></body>"
    )

    errors = mod.validate_structure(html_mit_score)

    # Spezifische Assertion (nicht nur "errors nicht leer" -- das waere schon
    # heute trivial wahr, weil der unmigrierte Validator JEDE v2-Mail wegen
    # unabhaengiger Struktur-Abweichungen ablehnt). Die Fehlerliste muss
    # konkret auf die Score-/Winner-Sprache verweisen.
    assert any(
        re.search(r"score|winner|empfehlung|bester standort|🏆", e, re.IGNORECASE)
        for e in errors
    ), (
        "Erwartet: mindestens eine Fehlermeldung referenziert konkret die "
        f"Score-/Winner-Sprache ('Empfehlung: ... (Score 87)'), bekommen: {errors}"
    )


# --------------------------------------------------------------------------- #
# AC-5 — gefilterte Uebersicht (Warn-Zeile + nur Wind) -> keine Fehler
# --------------------------------------------------------------------------- #

def test_ac5_gefilterte_uebersicht_warnzeile_plus_wind_bleibt_fehlerfrei():
    mod = _load_validator()
    html = _render_v2(enabled_metrics={"wind_max"})

    errors = mod.validate_structure(html)

    assert errors == [], (
        f"Erwartet: keine Strukturfehler bei preset-gefilterter Uebersicht "
        f"(nur Warn-Zeile + Wind-Zeile), bekommen: {errors}"
    )


# --------------------------------------------------------------------------- #
# AC-6 — verkuerzte/umsortierte Stunden-Spalten -> Fehler mit Spalten-/
# Ort-Kontext
# --------------------------------------------------------------------------- #

def test_ac6_verkuerzte_stundentabellen_spalten_werden_mit_ort_kontext_gemeldet():
    mod = _load_validator()
    html = _render_v2()

    # Marseilles Stundentabelle (per 'Zeit'-Header identifiziert) auf 3 statt
    # 8 Spalten verkuerzen -- reiner String-Eingriff am echten Render-Output,
    # kein Handbau der gesamten Mail.
    zeit_positions = [m.start() for m in re.finditer(r">Zeit<", html)]
    assert len(zeit_positions) == 3, f"Erwartet 3 Stundentabellen, gefunden: {len(zeit_positions)}"
    marseille_pos = zeit_positions[2]  # alphabetisch: Collobrières, Fréjus, Marseille
    table_start = html.rfind("<table", 0, marseille_pos)
    table_end = html.find("</table>", marseille_pos) + len("</table>")
    truncated_table = (
        "<table><tr><th>Zeit</th><th>Temp</th><th>Wind</th></tr>"
        "<tr><td>09:00</td><td>24°</td><td>12</td></tr></table>"
    )
    broken_html = html[:table_start] + truncated_table + html[table_end:]

    errors = mod.validate_structure(broken_html)

    assert errors, "Erwartet: Strukturfehler bei verkuerzter/umsortierter Stundentabellen-Spaltenreihenfolge"
    assert any("Marseille" in e for e in errors), (
        f"Erwartet: Fehlermeldung referenziert den betroffenen Ort 'Marseille', bekommen: {errors}"
    )


# --------------------------------------------------------------------------- #
# Adversary F001 (Fix-Runde) -- Score-/Winner-Negativ-Check braucht Wortgrenzen
# statt ungebundener Substring-Suche, sonst false positives bei Ortsnamen wie
# "Scoresbysund"/"Gewinnerort".
# --------------------------------------------------------------------------- #

def _make_two_named_location_result(name_a: str, name_b: str) -> ComparisonResult:
    locations = [
        LocationResult(
            location=_loc(name_a.lower(), name_a),
            temp_max=20.0, wind_max=10.0, sunny_hours=3.0, cloud_avg=50,
            official_alerts=[], hourly_data=[_dp(h) for h in (9, 10, 11)],
        ),
        LocationResult(
            location=_loc(name_b.lower(), name_b),
            temp_max=22.0, wind_max=12.0, sunny_hours=4.0, cloud_avg=45,
            official_alerts=[], hourly_data=[_dp(h) for h in (9, 10, 11)],
        ),
    ]
    return ComparisonResult(
        locations=locations,
        time_window=(9, 16),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 1),
    )


def test_f001_ortsnamen_mit_score_winner_teilstring_bleiben_fehlerfrei():
    mod = _load_validator()
    result = _make_two_named_location_result("Scoresbysund", "Gewinnerort")
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

    errors = mod.validate_structure(html)

    assert errors == [], (
        "Erwartet: Ortsnamen, die 'score'/'winner' nur als Teilstring enthalten "
        f"('Scoresbysund', 'Gewinnerort'), duerfen NICHT als Score-/Winner-Sprache "
        f"gemeldet werden, bekommen: {errors}"
    )


def test_f001_echte_score_winner_injection_wird_weiterhin_als_fehler_erkannt():
    mod = _load_validator()
    html = _render_v2()

    for injection in (
        "<div>Empfehlung: Fréjus (Score 87)</div>",
        "<div>Score: 87</div>",
        "<div>🏆 Fréjus</div>",
        "<div>Bester Standort: Fréjus</div>",
    ):
        html_mit_injection = html.replace("</body>", injection + "</body>")
        errors = mod.validate_structure(html_mit_injection)
        assert errors, (
            f"Erwartet: Injection '{injection}' wird trotz Wortgrenzen-Regex "
            f"weiterhin als Score-/Winner-Verstoss erkannt (leere Fehlerliste bekommen)"
        )


# --------------------------------------------------------------------------- #
# Adversary F002 (Fix-Runde) -- gleichnamige Orte muessen einzeln (per
# Vorkommen) geprueft werden, nicht nur das erste Vorkommen des Namens.
# --------------------------------------------------------------------------- #

def _make_duplicate_name_result(*, truncate_second: bool) -> str:
    name = "Duplikat-Ort"
    locations = [
        LocationResult(
            location=_loc(f"{name.lower()}-a", name),
            temp_max=20.0, wind_max=10.0, sunny_hours=3.0, cloud_avg=50,
            official_alerts=[], hourly_data=[_dp(h) for h in (9, 10, 11)],
        ),
        LocationResult(
            location=_loc(f"{name.lower()}-b", name),
            temp_max=22.0, wind_max=12.0, sunny_hours=4.0, cloud_avg=45,
            official_alerts=[], hourly_data=[_dp(h) for h in (9, 10, 11)],
        ),
    ]
    result = ComparisonResult(
        locations=locations, time_window=(9, 16),
        target_date=date(2026, 7, 8), created_at=datetime(2026, 7, 8, 4, 1),
    )
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
    if not truncate_second:
        return html

    zeit_positions = [m.start() for m in re.finditer(r">Zeit<", html)]
    assert len(zeit_positions) == 2, f"Erwartet 2 Stundentabellen, gefunden: {len(zeit_positions)}"
    second_pos = zeit_positions[1]
    table_start = html.rfind("<table", 0, second_pos)
    table_end = html.find("</table>", second_pos) + len("</table>")
    truncated_table = (
        "<table><tr><th>Zeit</th><th>Temp</th><th>Wind</th></tr>"
        "<tr><td>09:00</td><td>24°</td><td>12</td></tr></table>"
    )
    return html[:table_start] + truncated_table + html[table_end:]


def test_f002_zweiter_gleichnamiger_ort_mit_defekter_stundentabelle_wird_erkannt():
    mod = _load_validator()
    broken_html = _make_duplicate_name_result(truncate_second=True)

    errors = mod.validate_structure(broken_html)

    assert errors, (
        "Erwartet: Strukturfehler, da die Stundentabelle des ZWEITEN "
        "gleichnamigen Ortes ('Duplikat-Ort') verkuerzt ist"
    )
    assert any("Duplikat-Ort" in e for e in errors), (
        f"Erwartet: Fehlermeldung referenziert den Ortsnamen 'Duplikat-Ort', bekommen: {errors}"
    )


def test_f002_beide_gleichnamigen_orte_intakt_bleiben_fehlerfrei():
    mod = _load_validator()
    html = _make_duplicate_name_result(truncate_second=False)

    errors = mod.validate_structure(html)

    assert errors == [], (
        f"Erwartet: keine Strukturfehler, wenn beide gleichnamigen Orte "
        f"vollstaendige Stundentabellen haben, bekommen: {errors}"
    )
