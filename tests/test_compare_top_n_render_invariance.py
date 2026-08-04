"""TDD RED — Rueckbau des toten `top_n`-Reglers im Auflösungs- und Renderpfad
des Ortsvergleichs (Fundament fuer AC-7) sowie AC-7 selbst: die gerenderte
Vergleichs-Mail bleibt inhaltlich unveraendert.

Spec: `docs/specs/modules/compare_layout_tab_dissolution.md`
(Scheibe S1a von Epic #1372, deckt #1360).

Ausgangslage (Ist-Stand, verifiziert):
- `resolve_compare_render_options()` liest `display_config.top_n`, setzt Default
  3 und clampt auf 1..10 (`src/services/report_config_resolver.py:200-216`) und
  gibt das Ergebnis als `CompareRenderOptions.top_n_details` weiter (`:156`).
- `render_compare_html()` nimmt den Parameter an und wirft ihn sofort weg
  (`src/output/renderers/email/compare_html.py:1097`: `_ = top_n_details`).
- `render_compare_email()` reicht ihn nur durch
  (`src/output/renderers/comparison.py:235,270`), ebenso
  `compare_preview_service.py:177` und `scheduler_dispatch_service.py:373`.

Der Regler ist also seit #1104/PO-Entscheidung 2026-07-08 vollstaendig
wirkungslos. Diese Scheibe raeumt ihn weg. Was hier nachgewiesen wird:

1. VERHALTEN statt Grep: ein gespeicherter Vergleich MIT `top_n` und ein
   ansonsten identischer OHNE `top_n` ergeben nach der Auflösung dieselben
   Render-Optionen — heute unterscheiden sie sich (3 vs. 5) -> ROT.
2. Der Regler ist aus dem Render-Vertrag verschwunden: `render_compare_email()`
   und `render_compare_html()` nehmen `top_n_details` nicht mehr an -> heute
   nehmen sie ihn an, kein `TypeError` -> ROT.
3. AC-7: die gerenderte Mail bleibt strukturell und inhaltlich identisch —
   Nachweis gegen ein VERSIONIERTES Fixture mit aufgezeichneten Wetterdaten
   (`tests/fixtures/compare_mail_structure.json`, Quelle
   `fixtures/openmeteo/*.json`) und eine aufgezeichnete Soll-Struktur
   (`tests/fixtures/compare_mail_structure_golden.json`). Verglichen wird die
   ausgewertete Struktur (Ortsspalten, Metrikzeilen samt Reihenfolge,
   Stundentabellen-Spalten), NICHT die Bytes — Kopf-/Fusszeilen mit
   Zeitstempeln bleiben aussen vor.
4. Die beiden Durchreicher-Aufrufpfade laufen nach dem Rueckbau durch — echt
   ausgefuehrt, kein Mock, kein Netz: `ComparePreviewService._render_email` und
   `send_one_compare_preset` (Versandpfad, mit echtem Engine-Lauf gegen den
   Offline-Fixture-Provider und Sentinel-Abbruch vor SMTP).

KEINE Mocks/patch/MagicMock. Kein Netzwerk. Kein I/O auf Modul-Ebene.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from services.report_config_resolver import resolve_compare_render_options

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
WEATHER_FIXTURE = FIXTURE_DIR / "compare_mail_structure.json"
GOLDEN_FIXTURE = FIXTURE_DIR / "compare_mail_structure_golden.json"


# ---------------------------------------------------------------------------
# Fixture -> echte Domaenen-Objekte (aufgezeichnete Daten, kein Live-Abruf)
# ---------------------------------------------------------------------------

def _datapoint(raw: dict) -> ForecastDataPoint:
    kwargs = dict(raw)
    kwargs["ts"] = datetime.fromisoformat(kwargs["ts"]).replace(tzinfo=None)
    if "thunder_level" in kwargs:
        kwargs["thunder_level"] = ThunderLevel[kwargs["thunder_level"]]
    return ForecastDataPoint(**kwargs)


def _load_comparison_result() -> ComparisonResult:
    """Baut das `ComparisonResult` aus dem versionierten Fixture.

    I/O bewusst NUR innerhalb der Funktion (Modul-Level-I/O wuerde bei einem
    fehlenden Fixture die gesamte pytest-Suite mit einem Collect-Error killen).
    """
    fixture = json.loads(WEATHER_FIXTURE.read_text(encoding="utf-8"))
    locations = [
        LocationResult(
            location=SavedLocation(
                id=entry["id"],
                name=entry["name"],
                lat=entry["lat"],
                lon=entry["lon"],
                elevation_m=entry["elevation_m"],
            ),
            hourly_data=[_datapoint(h) for h in entry["hourly"]],
            official_alerts=[],
            **entry["aggregates"],
        )
        for entry in fixture["locations"]
    ]
    return ComparisonResult(
        locations=locations,
        time_window=tuple(fixture["time_window"]),
        target_date=date.fromisoformat(fixture["target_date"]),
        created_at=datetime.fromisoformat(fixture["created_at"]),
    )


def _preset(preset_id: str, *, top_n: int | None) -> dict:
    """Zwei ansonsten IDENTISCHE Vergleichs-Presets — einmal mit, einmal ohne
    den toten `top_n`-Schluessel."""
    display_config: dict = {
        "active_metrics": ["temp_max_c", "wind_max_kmh", "sunny_hours_h"],
        "hourly_metrics": ["t2m_c", "wind_kmh"],
    }
    if top_n is not None:
        display_config["top_n"] = top_n
    return {
        "id": preset_id,
        "name": "Struktur-Vergleich",
        "kind": "vergleich",
        "schedule": "daily",
        "weekday": 2,
        "hourly_enabled": True,
        "outlook_enabled": False,
        "corridors": [{"metric": "temp_max_c", "range": [15, 35], "mark": True}],
        "display_config": display_config,
    }


# ---------------------------------------------------------------------------
# Struktur-Extraktion (AC-7: "ausgewertete Struktur, nicht Bytes")
# ---------------------------------------------------------------------------

def extract_compare_mail_structure(html: str, plain: str) -> dict:
    """Wertet die gerenderte Vergleichs-Mail zu einer vergleichbaren Struktur aus.

    Erfasst:
    - `overview`: die Uebersichtsmatrix (Kopfzeile = Ortsspalten, danach je
      Metrikzeile Label + Werte) in Reihenfolge.
    - `hourly_tables`: je Ort die Stundentabelle (Spaltenkoepfe + Zeilen).
    - `plain_lines`: der Klartext-Teil ohne die Zeitstempel-Zeile.

    Kopf-/Fussbereich der HTML-Mail bleibt bewusst aussen vor: dort steht ein
    Render-Zeitpunkt ("Erstellt HH:MM"), der sich zwischen zwei Laeufen aendert
    und einen Struktur-Vergleich sonst unbrauchbar machen wuerde.
    """
    soup = BeautifulSoup(html, "html.parser")
    overview: list[list[str]] | None = None
    hourly_tables: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows = [
            [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
            for tr in table.find_all("tr")
        ]
        rows = [r for r in rows if r]
        if not rows or not rows[0]:
            continue
        first_cell = rows[0][0]
        if first_cell == "Metrik" and overview is None:
            overview = rows
        elif first_cell == "Zeit":
            hourly_tables.append(rows)

    plain_lines = [
        line.rstrip()
        for line in plain.splitlines()
        if not line.startswith("Erstellt:")
    ]
    return {
        "overview": overview,
        "hourly_tables": hourly_tables,
        "plain_lines": plain_lines,
    }


def _render_from_options(result: ComparisonResult, preset: dict) -> tuple[str, str]:
    """Rendert die Vergleichs-Mail ueber den ECHTEN Auflösungs-Pfad — ohne
    `top_n_details` zu uebergeben (so soll der Aufrufer nach dem Rueckbau
    aussehen, vgl. `compare_preview_service._render_email`)."""
    from output.renderers.comparison import render_compare_email

    opts = resolve_compare_render_options(preset)
    return render_compare_email(
        result,
        enabled_metrics=opts.enabled_metrics,
        hourly_metrics=opts.hourly_metrics,
        hourly_enabled=opts.hourly_enabled,
        preset_name=preset.get("name"),
        preset_schedule=preset.get("schedule"),
        preset_weekday=preset.get("weekday"),
        corridors=opts.corridors,
        outlook_enabled=opts.outlook_enabled,
    )


# ===========================================================================
# Rueckbau in der Auflösung — VERHALTENS-Nachweis (heute ROT)
# ===========================================================================

def test_preset_with_and_without_top_n_resolve_to_identical_options():
    """GIVEN zwei ansonsten identische Vergleiche, einer mit `top_n: 5`, einer
    ohne / WHEN beide aufgeloest werden / THEN sind die Render-Optionen
    identisch — der Schluessel hat keinerlei Einfluss mehr.

    RED heute: `top_n_details` ist 5 bzw. 3 -> die Optionen unterscheiden sich.
    """
    with_key = resolve_compare_render_options(_preset("p-with", top_n=5))
    without_key = resolve_compare_render_options(_preset("p-without", top_n=None))

    assert with_key == without_key, (
        "Ein gespeichertes 'top_n' darf die aufgeloesten Render-Optionen nicht "
        f"mehr beeinflussen.\nmit top_n:  {with_key!r}\nohne top_n: {without_key!r}"
    )


def test_resolved_options_no_longer_expose_top_n_details():
    """GIVEN ein Vergleich mit `top_n: 5` / WHEN er aufgeloest wird / THEN
    tragen die Optionen keinen `top_n_details`-Regler mehr — der Wert wurde
    seit #1104 von jedem Renderer verworfen und taeuschte eine Wirkung vor.

    RED heute: `CompareRenderOptions.top_n_details` existiert (report_config_
    resolver.py:156).
    """
    opts = resolve_compare_render_options(_preset("p-attr", top_n=5))

    assert not hasattr(opts, "top_n_details"), (
        "Die aufgeloesten Compare-Render-Optionen duerfen keinen "
        "'top_n_details'-Regler mehr fuehren — er ist in allen Render-Pfaden "
        f"wirkungslos. Vorhandener Wert: {getattr(opts, 'top_n_details', None)!r}"
    )


def test_out_of_range_top_n_is_no_longer_clamped_but_simply_ignored():
    """GIVEN ein Bestandsvergleich mit unsinnigem `top_n` (0, 15, "abc") / WHEN
    er aufgeloest wird / THEN entsteht dasselbe Ergebnis wie ohne den Schluessel
    — es gibt keine Default-/Clamp-Regel mehr, die einen toten Wert veredelt.

    RED heute: Default 3 / Clamp 1..10 sind noch aktiv und erzeugen je Eingabe
    unterschiedliche Optionen.
    """
    baseline = resolve_compare_render_options(_preset("p-base", top_n=None))
    for junk in (0, 15, -5):
        resolved = resolve_compare_render_options(_preset("p-junk", top_n=junk))
        assert resolved == baseline, (
            f"top_n={junk!r} darf keinen Unterschied mehr machen.\n"
            f"mit Wert: {resolved!r}\nohne Wert: {baseline!r}"
        )
    # Nicht-int-Werte (heute: logger.warning + Default 3) duerfen ebenfalls
    # keinen Regler mehr erzeugen.
    preset_with_junk_string = _preset("p-str", top_n=None)
    preset_with_junk_string["display_config"]["top_n"] = "abc"
    junk_string = resolve_compare_render_options(preset_with_junk_string)
    assert junk_string == baseline, (
        f"top_n='abc' darf keinen Unterschied mehr machen.\nmit Wert: {junk_string!r}"
    )


# ===========================================================================
# Rueckbau im Render-Vertrag — heute ROT
# ===========================================================================

def test_render_compare_email_rejects_top_n_details_argument():
    """GIVEN der Vergleichs-Mail-Renderer / WHEN ein Aufrufer noch
    `top_n_details=` mitgibt / THEN scheitert der Aufruf sichtbar (TypeError)
    statt das Argument stillschweigend zu schlucken.

    Ein stillschweigend geschluckter Parameter ist genau die Attrappe, die
    #1360 beklagt: der Aufrufer glaubt, etwas eingestellt zu haben.

    RED heute: der Parameter existiert (comparison.py:235) -> kein TypeError.
    """
    from output.renderers.comparison import render_compare_email

    result = _load_comparison_result()
    with pytest.raises(TypeError):
        render_compare_email(result, top_n_details=3)


def test_render_compare_html_rejects_top_n_details_argument():
    """Wie oben fuer den HTML-Renderer, der den Wert heute explizit wegwirft
    (`_ = top_n_details`, compare_html.py:1097).

    RED heute: kein TypeError.
    """
    from output.renderers.email.compare_html import render_compare_html

    result = _load_comparison_result()
    with pytest.raises(TypeError):
        render_compare_html(result, top_n_details=3)


class _RenderCallRecorded(Exception):
    """Sentinel: bricht `send_one_compare_preset` gezielt NACH dem
    `render_compare_email`-Aufruf ab, bevor SMTP beruehrt wird.

    Muster uebernommen aus `tests/tdd/test_issue_1104_compare_config_foundation.py`
    (`_capture_render_call`) — echtes Attribut-Rebind auf dem Modul, kein
    `patch()`/`Mock()`. Der vorgelagerte `ComparisonEngine`-Lauf laeuft
    vollstaendig echt gegen den Offline-Fixture-Provider (autouse-Fixture in
    `tests/conftest.py`).
    """

    def __init__(self, kwargs: dict):
        self.kwargs = kwargs
        super().__init__(f"recorded render kwargs: {sorted(kwargs)}")


def test_scheduler_dispatch_path_renders_without_top_n_details(tmp_path):
    """GIVEN der ECHTE Compare-Versandpfad (`send_one_compare_preset`) und ein
    Bestands-Preset, in dessen `display_config` noch ein `top_n` steht / WHEN der
    Versand laeuft / THEN erreicht er den Renderer und uebergibt KEIN
    `top_n_details` mehr.

    Warum echt ausgefuehrt und nicht per Quelltext-Analyse: bliebe in
    `scheduler_dispatch_service.py` ein `opts.top_n_details` stehen, nachdem das
    Feld entfallen ist, scheitert genau dieser Aufruf mit `AttributeError` — und
    zwar erst im Produktivbetrieb. Der Lauf hier faengt das ab. (Die RED-Fassung
    pruefte das per AST ueber den Modul-Quelltext; das verstiess gegen das
    Backend-Hygiene-Gate #765, `tests/tdd/test_765_backend_hygiene_compliance.py`
    — Quelltext-Lesen in Tests ist projektweit verboten. Aussage identisch,
    Nachweis jetzt am laufenden Pfad.)

    Deckt `scheduler_dispatch_service.py`; der Vorschau-Zwilling
    (`compare_preview_service.py`) ist unten separat abgedeckt, die beiden
    Renderer ueber die `TypeError`-Tests oben.
    """
    import output.renderers.comparison as compare_render_mod
    from app.config import Settings
    from app.loader import SavedLocation
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id = "test1360-dispatch"
    location = SavedLocation(
        id="loc-1360", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574
    )
    preset = {
        "id": "cp-1360-dispatch",
        "name": "Vergleich 1360",
        "location_ids": ["loc-1360"],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
        # Bestandsdaten: der tote Schluessel steckt noch drin.
        "display_config": {"active_metrics": ["temp_max_c"], "top_n": 5},
    }

    original_render = compare_render_mod.render_compare_email

    def _recording_render_compare_email(*args, **kwargs):
        raise _RenderCallRecorded(dict(kwargs))

    # Empfaenger explizit setzen (#1452): seit der Umstellung auf die Konto-
    # Settings ist `mail_to` eine harte Vorbedingung von send_one_compare_preset;
    # das Preset-Feld `empfaenger` ist inert. Muster wie in
    # tests/tdd/test_compare_outlook.py::_dispatch_kwargs.
    settings = Settings().with_user_profile(user_id).model_copy(
        update={"mail_to": "gregor-test@henemm.com"}
    )
    compare_render_mod.render_compare_email = _recording_render_compare_email
    try:
        with pytest.raises(_RenderCallRecorded) as exc:
            send_one_compare_preset(
                preset,
                settings,
                user_id,
                str(tmp_path),
                all_locations_cache=[location],
            )
    finally:
        compare_render_mod.render_compare_email = original_render

    assert "top_n_details" not in exc.value.kwargs, (
        "Der Versandpfad uebergibt dem Renderer noch 'top_n_details' — der "
        f"Parameter existiert nicht mehr. Uebergeben: {sorted(exc.value.kwargs)}"
    )
    # Gegenprobe, dass der Aufruf wirklich der echte Render-Aufruf war und der
    # Test nicht an einer frueheren Stelle abgebrochen ist.
    assert "enabled_metrics" in exc.value.kwargs
    assert exc.value.kwargs["enabled_metrics"] == ["temp_max"]


# ===========================================================================
# AC-7 — Mail-Inhalt unveraendert (versioniertes Fixture, ausgewertete Struktur)
# ===========================================================================

def test_mail_structure_identical_with_and_without_stored_top_n():
    """AC-7 GIVEN derselbe aufgezeichnete Wetterbestand / WHEN die Mail einmal
    aus einem Vergleich MIT `top_n` und einmal aus einem OHNE gerendert wird /
    THEN sind Ortsspalten, Metrikzeilen (samt Reihenfolge) und
    Stundentabellen-Spalten identisch.
    """
    result = _load_comparison_result()
    struct_with = extract_compare_mail_structure(*_render_from_options(result, _preset("s1", top_n=1)))
    struct_without = extract_compare_mail_structure(*_render_from_options(result, _preset("s2", top_n=None)))

    assert struct_with["overview"] is not None, "Uebersichtsmatrix nicht gefunden"
    assert struct_with == struct_without, (
        "AC-7: ein gespeichertes 'top_n' darf den Mail-Inhalt nicht veraendern"
    )


def test_rendered_compare_mail_matches_recorded_structure():
    """AC-7 GIVEN der aufgezeichnete Wetterbestand und die aufgezeichnete
    Soll-Struktur der Mail (vor dem Rueckbau abgenommen) / WHEN die Mail nach
    dem Rueckbau erzeugt wird / THEN stimmen Ortsblöcke, Tabellenspalten und
    Zeilenfolge exakt ueberein.

    Das ist der eigentliche AC-7-Waechter: er faellt, sobald der Rueckbau
    versehentlich Inhalt mitnimmt (z.B. eine Metrikzeile oder eine
    Stunden-Spalte).
    """
    golden = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["structure"]
    result = _load_comparison_result()
    actual = extract_compare_mail_structure(*_render_from_options(result, _preset("s3", top_n=None)))

    assert actual["overview"] == golden["overview"], (
        "AC-7: Uebersichtsmatrix (Ortsspalten / Metrikzeilen / Reihenfolge) "
        "hat sich veraendert"
    )
    assert len(actual["hourly_tables"]) == len(golden["hourly_tables"]), (
        "AC-7: Anzahl der Orts-Stundentabellen hat sich veraendert"
    )
    assert actual["hourly_tables"] == golden["hourly_tables"], (
        "AC-7: Stundentabellen (Spalten / Zeilenfolge / Werte) haben sich veraendert"
    )
    assert actual["plain_lines"] == golden["plain_lines"], (
        "AC-7: der Klartext-Teil der Mail hat sich veraendert"
    )


def test_compare_preview_render_path_runs_without_top_n_details():
    """GIVEN der Vorschau-Pfad (`ComparePreviewService._render_email`) / WHEN er
    mit den aufgeloesten Optionen rendert / THEN laeuft er durch und liefert
    dieselbe Struktur wie der direkte Renderer-Aufruf.

    Heute liest er `opts.top_n_details` (compare_preview_service.py:177) — nach
    dem Rueckbau des Feldes wuerde genau dieser Aufruf mit `AttributeError`
    brechen, wenn er nicht mitgezogen wird. Echter Aufruf, kein Mock, kein Netz
    (die Engine laeuft hier nicht — `_render_email` bekommt den fertigen ctx).
    """
    from services.compare_preview_service import ComparePreviewService

    result = _load_comparison_result()
    preset = _preset("p-preview", top_n=7)
    opts = resolve_compare_render_options(preset)
    ctx = {
        "preset": preset,
        "result": result,
        "profile": None,
        "opts": opts,
        "name": preset["name"],
        "target_date": result.target_date,
    }

    html, plain = ComparePreviewService()._render_email(ctx)

    via_preview = extract_compare_mail_structure(html, plain)
    direct = extract_compare_mail_structure(*_render_from_options(result, preset))
    assert via_preview == direct, (
        "Der Vorschau-Pfad muss nach dem Rueckbau dieselbe Mail erzeugen wie "
        "der direkte Renderer-Aufruf"
    )
