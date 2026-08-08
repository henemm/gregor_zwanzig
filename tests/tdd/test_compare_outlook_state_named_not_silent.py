"""Fix #1505 (TDD RED) — Orts-Vergleich: Ausblick-Zeile verschwindet still.

Spec: docs/specs/modules/fix_1505_compare_outlook_silent_exit.md (AC-1..AC-7)
Kontext: docs/context/fix-1505-compare-ausblick-zustand.md

RED heute: `_render_location_outlook()` (compare_html.py) gibt bei Fehler,
leeren Rohdaten und leeren Zeilen nach Filterung jeweils `""` zurueck; der
Klartext-Ausblick-Block (comparison.py) laesst den Ort bei leerem Ausblick
ganz aus der Mail entfallen. `comparison_engine.py` protokolliert weder den
Fehlerfall noch leere Ausblicksdaten. Alle drei Ursachen sind fuer den
Empfaenger identisch: eine unerklaerte Leerstelle bzw. ein fehlender Ort.

KEINE Mocks: echte LocationResult-/ComparisonResult-/SavedLocation-DTOs,
echte Renderer. Einzige Netz-Grenze (`fetch_forecast_for_location`) per
Attribut-Rebind ersetzt (Muster
`tests/tdd/test_comparison_engine_midnight_window.py`), in `finally`
restauriert.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

_ENGINE_LOGGER = "comparison_engine"
_STATE_TEXT = "Vorhersage derzeit nicht abrufbar."


# ---------------------------------------------------------------------------
# Helpers — echte Domaenen-Objekte
# ---------------------------------------------------------------------------

def _location(name="Innsbruck", loc_id="innsbruck"):
    from app.user import SavedLocation

    return SavedLocation(id=loc_id, name=name, lat=47.27, lon=11.39,
                          elevation_m=574, timezone="UTC")


def _day_points(day: date, temp: float = 10.0):
    from app.models import ForecastDataPoint, ThunderLevel

    return [
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0, tzinfo=timezone.utc),
            t2m_c=temp, wind10m_kmh=10.0, gust_kmh=15.0,
            precip_1h_mm=0.0, pop_pct=10, cloud_total_pct=30,
            thunder_level=ThunderLevel.NONE, visibility_m=20000,
        )
        for h in (2, 8, 14, 20)
    ]


def _run_engine_with_fetch(locations, fetch_fn, *, time_window=(9, 16),
                            target_date=None):
    """Echte ComparisonEngine; einzige Netz-Grenze per Attribut-Rebind
    ersetzt (kein Mock), in `finally` restauriert."""
    import services.comparison_engine as ce_mod

    target_date = target_date or date.today()
    original = ce_mod.fetch_forecast_for_location
    ce_mod.fetch_forecast_for_location = fetch_fn
    try:
        return ce_mod.ComparisonEngine.run(
            locations=locations, time_window=time_window,
            target_date=target_date, official_alerts_enabled=False,
        )
    finally:
        ce_mod.fetch_forecast_for_location = original


def _error_fetch(location, hours=96, settings=None):
    return {"location": location, "error": "Kontingent erschoepft",
            "forecast_hours": hours, "snow_source": None, "raw_data": []}


def _raising_fetch(location, hours=96, settings=None):
    """Zweiter Weg zu `LocationResult(error=...)`: eine Exception statt eines
    strukturierten `error`-Feldes (Adversary F002 — dieser Zweig war
    ungetestet, sein WARNING liess sich spurlos entfernen)."""
    raise RuntimeError("Netzwerkfehler")


def _today_only_fetch(location, hours=96, settings=None):
    """Erfolgreicher Fetch, aber alle Punkte liegen am Detailtag selbst —
    kein Datenpunkt jenseits davon, `outlook_hourly_data` bleibt leer."""
    return {"location": location, "error": None, "forecast_hours": hours,
            "snow_source": None, "raw_data": _day_points(date.today())}


def _multi_day_fetch(location, hours=96, settings=None):
    """Erfolgreicher Fetch mit Detailtag + 3 Folgetagen (Normalfall)."""
    today = date.today()
    points = list(_day_points(today))
    for offset in (1, 2, 3):
        points.extend(_day_points(today + timedelta(days=offset)))
    return {"location": location, "error": None, "forecast_hours": hours,
            "snow_source": None, "raw_data": points}


def _loc_result_direct(*, error=None, outlook_hourly_data=None,
                        hourly_data=None, name="Innsbruck"):
    from app.user import LocationResult

    return LocationResult(
        location=_location(name, name.lower()),
        error=error,
        hourly_data=hourly_data or [],
        outlook_hourly_data=outlook_hourly_data or [],
    )


def _comparison_result(locations):
    from app.user import ComparisonResult

    return ComparisonResult(
        locations=locations, time_window=(9, 16), target_date=date.today(),
        created_at=datetime.now(),
    )


def _engine_warnings(caplog, name=None):
    """WARNINGs, die AUS `comparison_engine` stammen (Namensfilter)."""
    recs = [r for r in caplog.records
            if r.levelno >= logging.WARNING and r.name == _ENGINE_LOGGER]
    if name:
        recs = [r for r in recs if name in r.getMessage()]
    return recs


def _all_warnings(caplog, name=None):
    """WARNINGs aus JEDEM Logger — ohne Namensfilter (Adversary F001).

    `_engine_warnings()` beantwortet nur "wie oft hat die Engine geloggt?".
    Spec §4 verlangt aber mehr: der Zustand darf ueberhaupt nur EINMAL je
    Ort und Lauf protokolliert werden, egal aus welchem Modul — ein
    zusaetzliches `logger.warning(...)` in einem der beiden Renderer unter
    EIGENEM Loggernamen (`compare_html`, `comparison`) ist genau der
    Doppel-Log, den AC-6 verbietet, und rutschte am Namensfilter vorbei.
    Renderer-Logs propagieren zum Root-Logger und landen damit in `caplog`.
    """
    recs = [r for r in caplog.records if r.levelno >= logging.WARNING]
    if name:
        recs = [r for r in recs if name in r.getMessage()]
    return recs


# ---------------------------------------------------------------------------
# AC-1 — HTML: Fehlerfall
# ---------------------------------------------------------------------------

def test_ac1_html_error_location_shows_state_text_and_logs_warning(caplog):
    """AC-1: Given ein Ort mit Fetch-Fehler / When der HTML-Ausblick-Block
    gerendert wird / Then erscheint der Zustandstext statt einer Leerstelle,
    UND `comparison_engine.py` erzeugt genau einen WARNING-Log-Eintrag."""
    from output.renderers.email.compare_html import render_compare_html

    with caplog.at_level(logging.DEBUG, logger=_ENGINE_LOGGER):
        result = _run_engine_with_fetch([_location()], _error_fetch)

    loc_result = result.locations[0]
    assert loc_result.error is not None, "Vorbedingung: Fetch muss fehlschlagen"

    html = render_compare_html(result, outlook_enabled=True)
    assert _STATE_TEXT in html, (
        "Bei einem Fehler muss der Ausblick-Block einen Zustandstext zeigen "
        f"statt zu verschwinden. HTML-Ausschnitt: ...{html[-400:]}"
    )
    warnings = _engine_warnings(caplog, "Innsbruck")
    assert len(warnings) == 1, (
        f"Erwartete genau 1 WARNING fuer den Fehler-Ort, sah "
        f"{len(warnings)}: {[r.getMessage() for r in warnings]}"
    )


def test_ac1b_html_exception_during_fetch_shows_state_text_and_logs_warning(caplog):
    """AC-1, zweiter Codepfad (Adversary F002): Given ein Ort, dessen Abruf
    mit einer EXCEPTION abbricht (statt ein `error`-Feld zu liefern) / When
    der HTML-Ausblick-Block gerendert wird / Then erscheint derselbe
    Zustandstext, UND es entsteht genau ein WARNING mit Ortsbezug.

    Ohne diesen Fall bewachte die Suite nur die `raw_result["error"]`-Stelle;
    das WARNING in der `except`-Klausel liess sich ersatzlos loeschen, ohne
    dass ein Test rot wurde."""
    from output.renderers.email.compare_html import render_compare_html

    with caplog.at_level(logging.DEBUG, logger=_ENGINE_LOGGER):
        result = _run_engine_with_fetch([_location()], _raising_fetch)

    loc_result = result.locations[0]
    assert loc_result.error is not None, (
        "Vorbedingung: die Exception muss zu einem Fehler-Ergebnis werden"
    )
    assert "Netzwerkfehler" in loc_result.error, (
        f"Vorbedingung: der Exception-Text traegt den Fehler, war: "
        f"{loc_result.error!r}"
    )

    html = render_compare_html(result, outlook_enabled=True)
    assert _STATE_TEXT in html, (
        "Auch ein Abbruch per Exception muss den Zustandstext zeigen statt "
        f"zu verschwinden. HTML-Ausschnitt: ...{html[-400:]}"
    )
    warnings = _all_warnings(caplog, "Innsbruck")
    assert len(warnings) == 1, (
        f"Erwartete genau 1 WARNING fuer den abgebrochenen Abruf, sah "
        f"{len(warnings)}: {[(r.name, r.getMessage()) for r in warnings]}"
    )
    assert "Netzwerkfehler" in warnings[0].getMessage(), (
        "Die Meldung muss den Grund nennen, sonst ist sie im Betrieb "
        f"wertlos: {warnings[0].getMessage()!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — HTML: leeres outlook_hourly_data nach erfolgreichem Fetch
# ---------------------------------------------------------------------------

def test_ac2_html_empty_outlook_data_shows_state_text_and_logs_warning(caplog):
    """AC-2: Given ein Ort mit erfolgreichem Fetch, aber leerem
    `outlook_hourly_data` / When der HTML-Ausblick-Block gerendert wird /
    Then erscheint derselbe Zustandstext, UND ein WARNING-Log entsteht."""
    from output.renderers.email.compare_html import render_compare_html

    with caplog.at_level(logging.DEBUG, logger=_ENGINE_LOGGER):
        result = _run_engine_with_fetch([_location()], _today_only_fetch)

    loc_result = result.locations[0]
    assert loc_result.error is None, "Vorbedingung: Fetch war erfolgreich"
    assert loc_result.outlook_hourly_data == [], (
        f"Vorbedingung: outlook_hourly_data muss leer sein, war: "
        f"{loc_result.outlook_hourly_data}"
    )

    html = render_compare_html(result, outlook_enabled=True)
    assert _STATE_TEXT in html, (
        "Bei leeren Ausblicksdaten muss ein Zustandstext erscheinen statt "
        f"einer Leerstelle. HTML-Ausschnitt: ...{html[-400:]}"
    )
    warnings = _engine_warnings(caplog, "Innsbruck")
    assert len(warnings) == 1, (
        f"Erwartete genau 1 WARNING fuer leere Ausblicksdaten, sah "
        f"{len(warnings)}: {[r.getMessage() for r in warnings]}"
    )


# ---------------------------------------------------------------------------
# AC-3 — HTML: leere rows trotz vorhandenem outlook_hourly_data
# ---------------------------------------------------------------------------

def test_ac3_html_empty_rows_after_filtering_shows_state_text_no_engine_log(caplog):
    """AC-3: Given ein Ort mit nicht-leerem `outlook_hourly_data`, aber
    `_build_location_outlook_rows()` liefert (durch eine geleerte
    Metrik-Auswahl) keine Zeile / When der HTML-Ausblick-Block gerendert
    wird / Then erscheint derselbe Zustandstext wie in AC-1/AC-2, UND es
    entsteht KEIN zusaetzliches WARNING in `comparison_engine.py` (dieser
    Pfad ist Renderer-intern, die Engine wird gar nicht aufgerufen)."""
    from output.renderers.email.compare_html import _render_location_outlook

    loc = _loc_result_direct(
        outlook_hourly_data=_day_points(date.today() + timedelta(days=1)),
    )

    with caplog.at_level(logging.DEBUG, logger=_ENGINE_LOGGER):
        html = _render_location_outlook(loc, 0, outlook_metrics=[])

    assert _STATE_TEXT in html, (
        "Eine durch Metrik-Filterung leere Zeilenliste muss trotz "
        f"vorhandener Rohdaten den Zustandstext zeigen. Ergebnis: {html!r}"
    )
    assert _engine_warnings(caplog) == [], (
        "Dieser Pfad ist Renderer-intern (comparison_engine wurde gar nicht "
        f"aufgerufen) und darf keine Engine-WARNINGs erzeugen: "
        f"{[r.getMessage() for r in _engine_warnings(caplog)]}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Klartext: dieselben zwei Ursachen, Fehlerfall ausgenommen
# ---------------------------------------------------------------------------

def test_ac4_plain_empty_outlook_no_error_shows_state_text_location_stays():
    """AC-4: Given ein Ort mit `error is None`, aber leerem
    `outlook_hourly_data` / When `render_comparison_text()` rendert / Then
    erscheint der Zustandstext im Klartext-Ausblick-Abschnitt, UND der Ort
    bleibt in der Mail sichtbar (nicht `continue`-uebersprungen)."""
    from output.renderers.comparison import render_comparison_text

    loc = _loc_result_direct(error=None, outlook_hourly_data=[],
                              name="Alphaville")
    result = _comparison_result([loc])

    text = render_comparison_text(result, outlook_enabled=True)

    assert "Alphaville" in text, (
        "Ein fehlerfreier Ort mit leerem Ausblick darf im Klartext NICHT "
        f"komplett verschwinden. Text: {text!r}"
    )
    assert _STATE_TEXT in text, (
        "Der Klartext muss den Zustandstext zeigen statt eines fehlenden "
        f"Ausblick-Abschnitts. Text: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Normalfall unveraendert (Regressionstest)
# ---------------------------------------------------------------------------

def test_ac5_found_state_unchanged_no_state_text_no_warning(caplog):
    """AC-5: Given ein Ort mit erfolgreichem Fetch und Daten fuer 3
    Folgetage / When HTML UND Klartext gerendert werden / Then erscheint
    unveraendert die Ausblick-Tabelle (kein neuer Zustandstext), UND es
    entsteht KEIN WARNING fuer diesen Ort."""
    from output.renderers.comparison import render_comparison_text
    from output.renderers.email.compare_html import (
        OUTLOOK_HEADING, render_compare_html,
    )

    with caplog.at_level(logging.DEBUG, logger=_ENGINE_LOGGER):
        result = _run_engine_with_fetch([_location()], _multi_day_fetch)

    loc_result = result.locations[0]
    assert loc_result.error is None
    assert loc_result.outlook_hourly_data, (
        "Vorbedingung: outlook_hourly_data darf fuer den Normalfall nicht "
        "leer sein"
    )

    html = render_compare_html(result, outlook_enabled=True)
    text = render_comparison_text(result, outlook_enabled=True)

    assert OUTLOOK_HEADING in html, (
        f"Normalfall muss die Ausblick-Tabelle zeigen. HTML-Ausschnitt: "
        f"...{html[-400:]}"
    )
    assert _STATE_TEXT not in html, (
        "Im Normalfall darf KEIN Zustandstext erscheinen — Daten sind "
        f"vorhanden. HTML enthaelt faelschlich: {_STATE_TEXT!r}"
    )
    assert _STATE_TEXT not in text, (
        "Im Normalfall darf KEIN Zustandstext im Klartext erscheinen — "
        f"Daten sind vorhanden. Text: {text!r}"
    )
    warnings = _engine_warnings(caplog, "Innsbruck")
    assert warnings == [], (
        f"Der Normalfall ist kein Stoerfall und darf NICHT protokolliert "
        f"werden: {[r.getMessage() for r in warnings]}"
    )


# ---------------------------------------------------------------------------
# AC-6 — kein Doppel-Logging (HTML + Klartext in einem Mail-Aufbau)
# ---------------------------------------------------------------------------

def test_ac6_no_duplicate_warning_across_html_and_plain_render(caplog):
    """AC-6: Given ein Vergleichslauf mit einem Fehler-Ort / When
    `ComparisonEngine.run()` einmal laeuft und anschliessend
    `render_compare_email()` (HTML + Klartext in einem Aufruf) auf dem
    Ergebnis ausgefuehrt wird / Then entsteht GENAU EIN WARNING-Log-Eintrag
    fuer diesen Ort — nicht zwei, obwohl beide Renderer ueber den Zustand
    entscheiden."""
    from output.renderers.comparison import render_compare_email

    with caplog.at_level(logging.DEBUG, logger=_ENGINE_LOGGER):
        result = _run_engine_with_fetch([_location()], _error_fetch)
        render_compare_email(result, outlook_enabled=True)

    # Adversary F001: OHNE Logger-Namensfilter. Der frueher hier benutzte
    # `_engine_warnings()` haette einen zweiten Log-Aufruf aus einem der
    # Renderer (eigener Loggername) nicht gesehen — die Mutation "zusaetzliches
    # logger.warning('compare_html') in `_render_outlook_unavailable`" liess
    # alle sieben Tests gruen. Geprueft wird jetzt die Zusicherung selbst:
    # genau EINE Meldung zu diesem Ort im gesamten Lauf, aus welchem Modul
    # auch immer.
    warnings = _all_warnings(caplog, "Innsbruck")
    assert len(warnings) == 1, (
        f"Erwartete GENAU 1 WARNING (ueber ALLE Logger) trotz HTML+Klartext "
        f"im selben Mail-Aufbau, sah {len(warnings)}: "
        f"{[(r.name, r.getMessage()) for r in warnings]}"
    )
    assert warnings[0].name == _ENGINE_LOGGER, (
        "Die eine Meldung muss aus der Datenschicht kommen "
        f"({_ENGINE_LOGGER}), nicht aus einem Renderer — sah "
        f"{warnings[0].name!r}."
    )


# ---------------------------------------------------------------------------
# AC-7 — Mehrort-Fall: keine falsche Ganz-Auslassung im HTML
# ---------------------------------------------------------------------------

def test_ac7_multi_location_html_shows_all_three_with_correct_state():
    """AC-7: Given ein Vergleich mit 3 Orten (A: FOUND, B: error != None,
    C: error=None mit leerem outlook_hourly_data) / When
    `render_compare_html()` gerendert wird / Then erscheinen alle drei Orte
    mit ihrem jeweils korrekten Zustand — kein Ort verschwindet komplett aus
    der HTML-Mail. Im Klartext verschwindet Ort B (Fehlerfall) laut
    Scope-Grenze weiterhin GANZ (comparison.py:275, PO-Entscheidung
    2026-08-08); A und C erscheinen."""
    from output.renderers.comparison import render_comparison_text
    from output.renderers.email.compare_html import render_compare_html

    loc_a = _loc_result_direct(
        error=None,
        outlook_hourly_data=_day_points(date.today() + timedelta(days=1)),
        hourly_data=_day_points(date.today()),
        name="OrtA",
    )
    loc_b = _loc_result_direct(error="Kontingent erschoepft", name="OrtB")
    loc_c = _loc_result_direct(error=None, outlook_hourly_data=[], name="OrtC")
    result = _comparison_result([loc_a, loc_b, loc_c])

    html = render_compare_html(result, outlook_enabled=True)
    for name in ("OrtA", "OrtB", "OrtC"):
        assert name in html, (
            f"Ort {name} muss in der HTML-Mail erscheinen — kein Ort darf "
            f"komplett fehlen. HTML-Laenge: {len(html)}"
        )
    assert html.count(_STATE_TEXT) == 2, (
        "Erwartete den Zustandstext genau bei den zwei betroffenen Orten "
        f"(B, C), fand ihn {html.count(_STATE_TEXT)}x. "
        f"HTML-Ausschnitt: ...{html[-600:]}"
    )

    text = render_comparison_text(result, outlook_enabled=True)
    assert "OrtA" in text and "OrtC" in text, (
        f"Orte A und C muessen im Klartext erscheinen. Text: {text!r}"
    )
    # Scope-Grenze (comparison.py:275, PO-Entscheidung 2026-08-08): der
    # Fehler-Ort faellt aus dem Stundenverlauf-/Ausblick-Abschnitt heraus --
    # dort bekommt er weder Tabelle noch Zustandstext.
    #
    # GEMESSEN am Basis-Commit (vor diesem Fix): der Ortsname erscheint im
    # Klartext trotzdem, naemlich im Uebersichtsblock DARUEBER, mit eigener
    # Fehlerzeile ("OrtB / Fehler: Kontingent erschoepft",
    # comparison.py:216-222). Die urspruengliche Fassung dieser Zeile
    # (`"OrtB" not in text`) war deshalb schon vor der Implementierung
    # unerfuellbar und haette nur durch eine Aenderung ausserhalb dieses
    # Fixes gruen werden koennen. Geprueft wird jetzt der Abschnitt, den die
    # Scope-Grenze tatsaechlich betrifft.
    section = text[text.index("STUNDENVERLAUF"):]
    assert "OrtB" not in section, (
        "Ort B (Fehlerfall) muss laut Scope-Grenze (comparison.py:275) "
        f"aus dem Stundenverlauf-/Ausblick-Abschnitt entfallen. "
        f"Abschnitt: {section!r}"
    )
    assert section.count(_STATE_TEXT) == 1, (
        "Im Klartext-Abschnitt darf NUR Ort C den Zustandstext tragen (Ort B "
        f"entfaellt dort ganz), fand ihn {section.count(_STATE_TEXT)}x. "
        f"Abschnitt: {section!r}"
    )
    assert "Fehler: Kontingent erschoepft" in text, (
        "Der Fehler von Ort B bleibt im Uebersichtsblock sichtbar "
        f"(Bestandsverhalten, unveraendert). Text: {text!r}"
    )
