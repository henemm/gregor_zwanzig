"""Bestandsschutz des Ortsvergleich-Stundenverlaufs (Issue #1406 Scheibe B).

SPEC: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md — AC-4.

Zwei Bestandsfaelle, die diese Scheibe NICHT anfassen darf:

1. Ein Vergleich, der mit den zehn historischen Kurzschluesseln gespeichert
   wurde (``temp_c``, ``wind_kmh``, …), laedt unveraendert und zeigt exakt
   dieselben Spalten wie vor der Umstellung.
2. Ein Vergleich, der den Stundenverlauf NIE eingestellt hat
   (``hourly_metrics`` fehlt ⇒ ``None`` ⇒ „kein Filter"), zeigt weiterhin
   genau die bisherigen neun Spalten, NAMENTLICH — nicht ploetzlich alle 22.
   Das ist die gefaehrlichste Stelle der Scheibe: ``_visible_hour_metrics``
   (``compare_html.py:696-697``) setzt „kein Filter" heute mit „alle" gleich;
   waechst ``HOUR_METRICS`` von 9 auf 22 und bleibt diese Regel, springt jede
   Bestands-Vergleichsmail ohne Zutun des Nutzers auf 22 Spalten (Spec AC-4:
   „kein automatisches Hinzufuegen der neuen Groessen").

Beide Tests sind HEUTE BEREITS GRUEN und muessen es BLEIBEN — sie sind der
Nachweis fuer „keine ungewollte Wirkung", nicht der RED-Nachweis (Vorbild:
``tests/tdd/test_trip_outlook_parity.py``).

Die Erwartungswerte stehen als woertliche Literale im Test (aufgezeichnet vom
heutigen Stand), nicht als Vergleich des Codes mit sich selbst — ein solcher
Vergleich zoege bei jeder Erweiterung stumm mit.

Kern-Schicht, deterministisch: echte Renderer-Aufrufe, kein Netz, keine Mocks.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_email
from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics
from output.renderers.email.compare_html import render_compare_html
from services.report_config_resolver import resolve_compare_render_options

_TAGS = re.compile(r"<[^>]+>")

# Die zehn Kurzschluessel, wie ein vor dieser Aenderung gespeicherter
# Ortsvergleich sie in `display_config.hourly_metrics` traegt.
ALT_FORMAT_SELECTION = [
    "temp_c", "wind_chill_c", "wind_kmh", "gust_kmh", "precip_mm",
    "uv_index", "thunder_level", "pop_pct", "visibility_m", "wind_dir_deg",
]

# Aufgezeichnetes Ergebnis von `resolve_hourly_metrics(ALT_FORMAT_SELECTION)`
# am Stand vor Scheibe B (HEAD 1863e6c1) — Renderer-Feldnamen in
# Auswahl-Reihenfolge.
ALT_FORMAT_RESOLVED = [
    "t2m_c", "wind_chill_c", "wind10m_kmh", "gust_kmh", "precip_1h_mm",
    "uv_index", "thunder_level", "pop_pct", "visibility_m",
    "wind_direction_deg",
]

# Aufgezeichnete Spaltenueberschriften der Stundentabelle am selben Stand.
HEUTIGE_SPALTEN = [
    "Zeit", "Temp", "Feels", "Wind", "Gust", "Rain", "UV", "Thdr",
    "Rain%", "Visib",
]


def _result() -> ComparisonResult:
    loc = LocationResult(
        location=SavedLocation(id="a", name="Innsbruck", lat=47.0, lon=11.0,
                               elevation_m=600),
        score=1, temp_max=20.0, wind_max=15.0, cloud_avg=40, sunny_hours=5,
        official_alerts=[],
    )
    loc.hourly_data = [ForecastDataPoint(
        ts=datetime(2026, 7, 8, 8, 0),
        t2m_c=18.0, wind_chill_c=16.0, wind10m_kmh=12.0, wind_direction_deg=270,
        gust_kmh=25.0, precip_1h_mm=0.4, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=40, visibility_m=20000,
        humidity_pct=65, dewpoint_c=11.0, cloud_total_pct=50,
    )]
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 0),
    )


def _hour_header(html: str) -> list[str]:
    for head in re.findall(r"<thead>(.*?)</thead>", html, re.S):
        cols = [_TAGS.sub("", c).strip()
                for c in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]
        if cols and cols[0] == "Zeit":
            return cols
    return []


def test_legacy_short_keys_resolve_exactly_as_before():
    """AC-4: Given ein Vergleich wurde mit den alten Kurzschluesseln
    gespeichert / When er nach der Umstellung aufgeloest wird / Then kommt
    zeichengleich dasselbe heraus wie vorher — gleiche Menge, gleiche
    Reihenfolge, keine stillen Zusaetze."""
    assert resolve_hourly_metrics(ALT_FORMAT_SELECTION) == ALT_FORMAT_RESOLVED


def test_legacy_preset_renders_exactly_the_columns_of_today():
    """AC-4: Given derselbe Alt-Vergleich / When eine Mail dafuer erzeugt wird
    / Then zeigt die Stundentabelle exakt die bisherigen neun Wert-Spalten in
    der bisherigen Reihenfolge (die Windrichtung bleibt Merge-Signal ohne
    eigene Spalte)."""
    preset = {"id": "p-alt", "display_config": {
        "hourly_metrics": list(ALT_FORMAT_SELECTION)}}
    options = resolve_compare_render_options(preset)

    html, _plain = render_compare_email(
        _result(), hourly_metrics=options.hourly_metrics,
        hourly_enabled=options.hourly_enabled,
    )

    assert _hour_header(html) == HEUTIGE_SPALTEN, (
        "Ein unveraendert gespeicherter Alt-Vergleich zeigt andere Spalten als "
        "vor der Umstellung — das ist eine Migration durch die Hintertuer."
    )


def test_the_editor_can_recognise_a_legacy_hourly_selection():
    """AC-4 (Bedienflaechen-Haelfte): Given ein Vergleich hat ``temp_c``
    gespeichert / When der Editor nach der Umstellung seine Zeilen aus dem
    Katalog aufbaut (Zeilen-Schluessel ist dann die Katalog-ID
    ``temperature``) / Then muss er die Alt-Auswahl trotzdem als angehakt
    erkennen koennen.

    Sonst entsteht der Zustand, den kein Nutzer versteht: die Mail zeigt die
    Temperatur-Spalte, der Editor zeigt das Kaestchen leer — und der naechste
    Speichervorgang wirft die Auswahl weg.

    Der Weg ist bewusst NICHT vorgeschrieben. Zwei Loesungen sind zulaessig:
      (a) der Leseweg normalisiert die gespeicherten Werte auf Katalog-IDs —
          nachweisbar durch eine oeffentliche Normalisierungs-Funktion im
          Aufloeser-Modul, oder
      (b) die Katalogantwort, aus der die Bedienflaeche ihre Zeilen baut,
          nennt je Groesse ihre historischen Kurzschluessel.
    Mindestens eine davon muss es geben — und sie muss ``temp_c`` wirklich
    der Groesse ``temperature`` zuordnen. Beides fehlt heute.
    """
    from output.renderers import compare_hourly_metric_ids as aufloeser
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog

    # (a) oeffentliche Normalisierung im Aufloeser-Modul
    normalisiert = None
    for name in ("normalize_hourly_metrics", "to_catalog_ids",
                 "hourly_metrics_as_catalog_ids"):
        fn = getattr(aufloeser, name, None)
        if callable(fn):
            normalisiert = fn(["temp_c", "wind_kmh"])
            break

    # (b) Alias-Angabe an der Katalogantwort
    aliasse: set[str] = set()
    for eintrag in get_compare_metric_catalog():
        if eintrag.get("metric_id") != "temperature":
            continue
        for feld in ("hourly_legacy_keys", "legacy_hourly_keys",
                     "hourly_aliases"):
            wert = eintrag.get(feld)
            if wert:
                aliasse |= set(wert)

    weg_a = normalisiert == ["temperature", "wind"]
    weg_b = "temp_c" in aliasse

    assert weg_a or weg_b, (
        "Der Editor kann eine Alt-Auswahl nicht wiedererkennen: weder gibt es "
        "eine oeffentliche Normalisierung im Aufloeser-Modul (geprueft: "
        "normalize_hourly_metrics/to_catalog_ids/hourly_metrics_as_catalog_ids "
        f"-> {normalisiert!r}), noch nennt die Katalogantwort fuer "
        f"'temperature' ihre historischen Kurzschluessel (gefunden: "
        f"{sorted(aliasse)}). Ein gespeichertes 'temp_c' erscheint damit im "
        "Editor als NICHT angehakt, obwohl die Mail die Spalte zeigt."
    )


def test_never_configured_comparison_keeps_the_nine_columns_of_today():
    """AC-4 (der gefaehrliche Fall): Given ein Vergleich hat den
    Stundenverlauf nie eingestellt (``hourly_metrics`` fehlt) / When die Mail
    erzeugt wird / Then stehen weiterhin genau die neun bisherigen Spalten da.

    Waechst die Spaltenliste auf 22 und bleibt 'kein Filter' gleichbedeutend
    mit 'alle', springt hier jede Bestandsmail ungefragt auf 22 Spalten.

    Geprueft wird die Spaltenfolge NAMENTLICH und in Reihenfolge, nicht nur
    ihre Anzahl: eine gleich lange, aber anders zusammengesetzte Kopfzeile
    waere genauso ein Bruch.
    """
    assert len(HEUTIGE_SPALTEN) == 10 and HEUTIGE_SPALTEN[0] == "Zeit", (
        "Aufzeichnung beschaedigt: erwartet 'Zeit' + neun Wert-Spalten."
    )
    options = resolve_compare_render_options({"id": "p-nie", "display_config": {}})
    assert options.hourly_metrics is None, (
        "Vorbedingung: ein nie eingestellter Stundenverlauf muss als 'kein "
        "Filter' (None) beim Renderer ankommen - sonst prueft dieser Test "
        "einen anderen Fall als den gemeinten."
    )

    html = render_compare_html(_result(), hourly_metrics=None)
    ist = _hour_header(html)

    assert ist == HEUTIGE_SPALTEN, (
        "Ein nie eingestellter Vergleich hat ungefragt neue Spalten bekommen "
        "— AC-4: kein automatisches Hinzufuegen der neuen Groessen.\n"
        f"  erwartet: {HEUTIGE_SPALTEN}\n"
        f"  bekommen: {ist}\n"
        f"  ungefragt dazu: {[s for s in ist if s not in HEUTIGE_SPALTEN]}"
    )
