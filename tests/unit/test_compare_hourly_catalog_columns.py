"""Stundenverlauf des Ortsvergleichs schoepft aus dem zentralen Wetterkatalog.

Issue #1406 Scheibe B (Epic #1372 / Etappe E2 von #1435, Dach #1374).
SPEC: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md — AC-1 (Backend-
Haelfte), AC-2, AC-3, AC-5, AC-6.

Heute bietet der Stundenverlauf 10 Groessen an, obwohl alle 24 waehlbaren
Katalog-Groessen einen echten Stundenwert (``dp_field``) tragen. Diese Datei
prueft die WIRKUNG in der fertigen Mail, nicht die Bestueckung einer Liste:
eine neu gewaehlte Groesse muss als Spalte im HTML- UND im Klartext-Teil
derselben Mail erscheinen, mit uebereinstimmenden Werten.

Die Soll-Spaltenmenge wird aus dem Register abgeleitet
(``tests/helpers/hourly_columns.py``), NICHT im Test getippt — eine getippte
Liste waere die fuenfte Kopie genau des Vokabulars, das diese Scheibe
zusammenfuehrt. Abgezogen werden nur zwei ausgesprochene Ausnahmen: das
Merge-Signal Windrichtung und die vom Produktivcode selbst benannten
ausgenommenen Groessen (AC-11, ``sunshine``).

Kern-Schicht, deterministisch: echte ``ForecastDataPoint``-Objekte, echte
Renderer-Aufrufe, kein Netz, keine Mocks/``patch()``.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from app.metric_catalog import get_all_metrics, get_metric
from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_email, render_comparison_text
from output.renderers.compare_hourly_metric_ids import (
    HOURLY_EXCLUDED_METRIC_IDS,
    resolve_hourly_metrics,
)
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.email.compare_html import (
    HOUR_METRICS, has_visible_hour_columns, render_compare_html,
)
from services.report_config_resolver import resolve_compare_render_options
from tests.helpers.hourly_columns import (
    MERGE_ONLY_METRIC_ID, assert_soll_menge_ist_plausibel,
    hourly_excluded_metric_ids, hourly_excluded_metric_ids_for_parametrize,
)

_TAGS = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Fixture — ein Ort mit einer Stunde, jede Katalog-Groesse mit einem Rohwert
# ---------------------------------------------------------------------------

def _dp() -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, 8, 0),
        t2m_c=18.0, wind_chill_c=16.0, wind10m_kmh=12.0, wind_direction_deg=270,
        gust_kmh=25.0, precip_1h_mm=0.4, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=40, visibility_m=20000,
        humidity_pct=65, dewpoint_c=11.0, cape_jkg=300.0, snowfall_limit_m=2400,
        cloud_total_pct=50, cloud_low_pct=20, cloud_mid_pct=15, cloud_high_pct=10,
        dni_wm2=420.0, pressure_msl_hpa=1013.0, freezing_level_m=3600,
        snow_depth_cm=0.0, snow_new_24h_cm=0.0,
    )


def _result() -> ComparisonResult:
    loc = LocationResult(
        location=SavedLocation(id="a", name="Innsbruck", lat=47.0, lon=11.0,
                               elevation_m=600),
        score=1, temp_max=20.0, wind_max=15.0, cloud_avg=40, sunny_hours=5,
        official_alerts=[],
    )
    loc.hourly_data = [_dp()]
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 0),
    )


def _html_hour_header(html: str) -> list[str]:
    for head in re.findall(r"<thead>(.*?)</thead>", html, re.S):
        cols = [_TAGS.sub("", c).strip()
                for c in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]
        if cols and cols[0] == "Zeit":
            return cols
    return []


def _html_hour_cells(html: str) -> list[str]:
    """Werte der ersten Stundenzeile (ohne die feste Zeit-Spalte)."""
    body = html.split("<thead>", 1)[-1]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S)
    for row in rows:
        cells = [_TAGS.sub("", c).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if cells and re.fullmatch(r"\d{2}", cells[0]):
            return cells[1:]
    return []


def _plain_hour_cells(text: str) -> list[tuple[str, str]]:
    """(Beschriftung, Wert) je Zelle der ersten Klartext-Stundenzeile."""
    lines = text.splitlines()
    start = lines.index("STUNDENVERLAUF")
    for line in lines[start:]:
        if re.match(r"^\s+\d{2}:\d{2}\s\s", line):
            cells = [c.strip() for c in line.strip().split("  ") if c.strip()]
            out = []
            for cell in cells[1:]:
                label, _, value = cell.partition(" ")
                out.append((label, value.strip()))
            return out
    pytest.fail(f"Keine Klartext-Stundenzeile gefunden:\n{text}")


# ---------------------------------------------------------------------------
# AC-1 (Backend-Haelfte) — die Spaltenliste IST der Katalog
# ---------------------------------------------------------------------------

def test_hour_columns_cover_every_catalog_metric_except_merge_signal_and_exemptions():
    """AC-1/AC-11: Given der zentrale Wetterkatalog fuehrt seine waehlbaren
    Groessen, fast alle mit einem brauchbaren Stundenwert / When die
    Stundentabellen-Spaltenliste gebildet wird / Then traegt sie genau eine
    Spalte je Katalog-Groesse — abzueglich der Windrichtung (reines
    Merge-Signal, Spec Implementation Details 5) und der ausdruecklich
    ausgenommenen Groessen (AC-11).

    Die Soll-Menge wird gerechnet, nicht getippt; die Rechnung selbst wird in
    ``assert_soll_menge_ist_plausibel()`` behauptet (Katalog gross genug,
    genau zwei Abzuege, Ergebnis > 0).
    """
    soll_metriken = assert_soll_menge_ist_plausibel()
    soll = {m.dp_field for m in soll_metriken}

    ist = {m["key"] for m in HOUR_METRICS}
    assert ist == soll, (
        "Die Stundentabelle bietet nicht dieselben Groessen an wie der zentrale "
        f"Katalog. Fehlen: {sorted(soll - ist)}; unbekannt: {sorted(ist - soll)}"
    )


def test_every_hour_column_key_is_the_dp_field_of_its_catalog_metric():
    """AC-1 (Gegenprobe): jede Spalte nennt eine Katalog-Groesse und liest
    genau deren ``dp_field`` — sonst zeigte die Spalte den Wert einer anderen
    Groesse unter fremdem Namen."""
    assert HOUR_METRICS, "Spaltenliste ist leer — Vakuum."
    for row in HOUR_METRICS:
        metric = get_metric(row["metric_id"])
        assert row["key"] == metric.dp_field, (
            f"Spalte '{row['key']}' behauptet die Groesse '{row['metric_id']}', "
            f"deren Stundenwert aber in '{metric.dp_field}' steht."
        )


# ---------------------------------------------------------------------------
# AC-2 — neu waehlbare Groesse erscheint in HTML *und* Klartext
# ---------------------------------------------------------------------------

def test_newly_selectable_metric_appears_in_html_and_plaintext_with_same_values():
    """AC-2: Given ein Nutzer waehlt zusaetzlich „Luftfeuchtigkeit" / When die
    Vergleichs-Mail erzeugt wird / Then erscheint sie als eigene Spalte im
    HTML-TEIL UND im KLARTEXT-TEIL derselben Mail, mit demselben Wert.

    Gespeichert wird die Katalog-ID (``humidity``) — nach dieser Scheibe ist
    das das Format, das die Bedienflaeche liefert.
    """
    preset = {"id": "p-humid", "display_config": {
        "hourly_metrics": ["temperature", "humidity"]}}
    options = resolve_compare_render_options(preset)

    html, plain = render_compare_email(
        _result(), hourly_metrics=options.hourly_metrics,
        hourly_enabled=options.hourly_enabled,
    )

    humid_label = get_metric("humidity").col_label
    header = _html_hour_header(html)
    assert humid_label in header, (
        f"Spalte '{humid_label}' fehlt im HTML-Stundenkopf: {header}"
    )

    html_values = dict(zip(header[1:], _html_hour_cells(html)))
    plain_values = dict(_plain_hour_cells(plain))
    assert humid_label in plain_values, (
        f"Spalte '{humid_label}' fehlt in der Klartext-Stundenzeile: "
        f"{sorted(plain_values)}"
    )
    assert html_values[humid_label] == plain_values[humid_label], (
        f"HTML zeigt '{html_values[humid_label]}', Klartext "
        f"'{plain_values[humid_label]}' fuer dieselbe Stunde"
    )
    assert html_values[humid_label] not in ("", "–"), (
        "Die neue Spalte steht zwar da, traegt aber keinen Wert — eine leere "
        "Spalte ist kein erfuellter Wunsch."
    )


def test_catalog_id_selection_resolves_for_every_selectable_metric():
    """AC-2 (Breite statt Einzelfall): Given eine Auswahl aus lauter
    Katalog-IDs / When der Aufloeser sie uebersetzt / Then geht KEINE
    verloren, ausser den ausdruecklich ausgenommenen — sonst hakt der Nutzer
    Groessen an, von denen nur ein Teil ankommt (stiller Verlust, Invariante 2
    aus Epic #1372)."""
    ausgenommen = hourly_excluded_metric_ids()
    catalog_ids = [m.id for m in get_all_metrics() if m.id not in ausgenommen]
    assert catalog_ids, "Katalog leer — Vakuum."

    resolved = resolve_hourly_metrics(catalog_ids)

    assert resolved is not None
    erwartet = [get_metric(mid).dp_field for mid in catalog_ids]
    assert resolved == erwartet, (
        f"Beim Aufloesen verworfen: {sorted(set(erwartet) - set(resolved))}; "
        f"unerwartet dazugekommen: {sorted(set(resolved) - set(erwartet))}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Ab-/Anwahl wirkt auch fuer die neuen Groessen
# ---------------------------------------------------------------------------

def test_deselecting_a_new_metric_removes_its_column_again():
    """AC-3: Given eine der 14 neuen Groessen war gewaehlt und wird abgewaehlt
    / When die Mail erneut erzeugt wird / Then fehlt ihre Spalte wieder."""
    humid_label = get_metric("humidity").col_label
    dp_humid = get_metric("humidity").dp_field

    mit = render_compare_html(_result(), hourly_metrics=["t2m_c", dp_humid])
    ohne = render_compare_html(_result(), hourly_metrics=["t2m_c"])

    assert humid_label in _html_hour_header(mit)
    assert humid_label not in _html_hour_header(ohne), (
        f"Spalte '{humid_label}' steht noch in der Mail, obwohl abgewaehlt: "
        f"{_html_hour_header(ohne)}"
    )


def test_a_new_metric_alone_still_counts_as_a_visible_column():
    """AC-3 (Kehrseite der Leerauswahl-Regel): Given ausschliesslich eine der
    14 neuen Groessen ist gewaehlt / When ``has_visible_hour_columns()``
    entscheidet, ob die Stundentabelle ueberhaupt entsteht / Then sagt sie
    „ja" — sonst faellt die Tabelle weg, obwohl der Nutzer etwas gewaehlt hat.
    """
    assert has_visible_hour_columns([get_metric("humidity").dp_field]) is True
    assert has_visible_hour_columns([]) is False
    assert has_visible_hour_columns(
        [get_metric(MERGE_ONLY_METRIC_ID).dp_field]) is False


# ---------------------------------------------------------------------------
# AC-11 — ausgenommene Groessen erzeugen auch erzwungen keine Spalte
# ---------------------------------------------------------------------------

def test_the_exemption_set_is_named_in_production_code():
    """AC-11 (Vorbedingung): Given eine Groesse soll vom Stundenverlauf
    ausgenommen sein / When man im Produktivcode nachsieht / Then steht sie in
    einer BENANNTEN Ausnahme-Menge — nicht als stilles Fehlen in einer Liste.
    Nur so koennen Bedienflaeche, Aufloeser und Tests dieselbe Auskunft geben.
    """
    ausgenommen = hourly_excluded_metric_ids()

    assert "sunshine" in ausgenommen, (
        f"AC-11: 'sunshine' fehlt in der Ausnahme-Menge {sorted(ausgenommen)}"
    )
    assert ausgenommen <= {m.id for m in get_all_metrics()}, (
        "Die Ausnahme-Menge nennt Kennungen, die das Register nicht kennt: "
        f"{sorted(ausgenommen - {m.id for m in get_all_metrics()})}"
    )


def test_the_catalog_answer_tells_the_editor_why_a_metric_is_exempt():
    """AC-11 (Datenweg zur Bedienflaeche): Given eine Groesse ist vom
    Stundenverlauf ausgenommen / When die Bedienflaeche ihre Katalogantwort
    holt / Then steht die Ausnahme dort maschinenlesbar drin, samt Begruendung
    — sonst muesste das Frontend die Ausnahme selbst wissen, und wir haetten
    den fuenften Vokabular-Ort (AC-10), gegen den diese Scheibe antritt.

    Der Feldname ist bewusst nicht vorgeschrieben; geprueft wird der Vertrag
    (Muster: ``test_ac6_transition_union_carries_a_review_date``). Die
    Begruendung muss den Grund nennen und auf Bewoelkung und UV-Index
    verweisen (Spec AC-11).
    """
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog

    ausgenommen = hourly_excluded_metric_ids()
    eintraege = [e for e in get_compare_metric_catalog()
                 if e.get("metric_id") in ausgenommen]
    assert eintraege, (
        f"Keine Katalogzeile fuer die ausgenommenen Groessen {sorted(ausgenommen)} "
        "gefunden — der Vertrag waere nicht pruefbar."
    )

    for eintrag in eintraege:
        marker = next(
            (eintrag[f] for f in ("hourlySelectable", "hourly_selectable")
             if f in eintrag), None,
        )
        assert marker is False, (
            f"Katalogzeile {eintrag.get('key')!r} ({eintrag['metric_id']}) nennt "
            "keine maschinenlesbare Stundenverlauf-Ausnahme (erwartet z. B. "
            f"hourlySelectable=False): {sorted(eintrag)}"
        )
        grund = next(
            (eintrag[f] for f in ("hourlyNotSelectableReason",
                                  "hourly_not_selectable_reason", "hourlyHint")
             if f in eintrag), "",
        )
        assert grund and grund.strip(), (
            f"Katalogzeile {eintrag.get('key')!r} nennt keinen Grund fuer die "
            "Ausnahme — AC-11 verlangt einen sichtbaren Hinweis statt "
            "kommentarlosen Fehlens."
        )
        klein = grund.lower()
        assert "bewölk" in klein or "bewoelk" in klein, (
            f"Der Hinweis verweist nicht auf die Bewoelkung: {grund!r}"
        )
        assert "uv" in klein, (
            f"Der Hinweis verweist nicht auf den UV-Index: {grund!r}"
        )


@pytest.mark.parametrize(
    "metric_id", sorted(hourly_excluded_metric_ids_for_parametrize())
)
def test_an_exempt_metric_never_produces_an_hour_column(metric_id):
    """AC-11: Given eine ausdruecklich ausgenommene Groesse steht — ueber
    gespeicherte Altdaten oder von Hand — in der Stundenauswahl / When die
    Mail gerendert wird / Then entsteht daraus KEINE Spalte.

    ``sunshine`` traegt im Register die Einheit „h" (Sonnenstunden, eine
    Tagesgroesse), ihr Stundenwert ist aber ``dni_wm2`` — die Direkt-
    einstrahlung in W/m². Eine Spalte „Sun" mit Watt-Werten waere in beiden
    Lesarten falsch (PO-Entscheid 2026-08-01).
    """
    metric = get_metric(metric_id)

    # #1484: eine Ausnahme darf sich ein dp_field mit einer NICHT
    # ausgenommenen Groesse teilen (temperature_night nutzt t2m_c wie die
    # Temperatur) — dann gehoert die Spalte dem legitimen Eigentuemer und
    # der Feld-Check waere ein Fehlalarm. Nur ohne solchen Eigentuemer muss
    # das Feld komplett fehlen.
    _owners = [
        m for m in get_all_metrics()
        if m.dp_field == metric.dp_field
        and m.id not in HOURLY_EXCLUDED_METRIC_IDS
    ]
    if not _owners:
        assert metric.dp_field not in {m["key"] for m in HOUR_METRICS}, (
            f"'{metric_id}' hat trotz Ausnahme einen Eintrag in der "
            "Spaltenliste — sie wuerde als Spalte erscheinen."
        )
    assert resolve_hourly_metrics([metric_id]) == [], (
        f"Der Aufloeser laesst die ausgenommene Groesse '{metric_id}' durch: "
        f"{resolve_hourly_metrics([metric_id])}"
    )

    # Render-Nachweis nur fuer Ausnahmen mit EIGENEM Feld: bei geteiltem
    # dp_field (temperature_night -> t2m_c) waere ["t2m_c", "t2m_c"] kein
    # Nachweis ueber die Ausnahme, sondern nur ein Duplikat der
    # Temperatur-Spalte. Der Aufloeser-Check oben deckt diesen Fall ab.
    if not _owners:
        html = render_compare_html(
            _result(), hourly_metrics=["t2m_c", metric.dp_field],
        )
        assert _html_hour_header(html) == ["Zeit", get_metric("temperature").col_label], (
            f"Die ausgenommene Groesse '{metric_id}' hat doch eine Spalte "
            f"erzeugt: {_html_hour_header(html)}"
        )


# ---------------------------------------------------------------------------
# AC-5 — die drei Bereiche bleiben unabhaengig voneinander
# ---------------------------------------------------------------------------

def test_hourly_overview_and_outlook_orders_stay_independent():
    """AC-5: Given Stundenverlauf, Uebersicht und Ausblick haben jeweils eine
    eigene Auswahl/Reihenfolge / When alle drei in derselben Mail gerendert
    werden / Then bleibt jede fuer sich — die Zusammenfuehrung der
    Vokabular-Stellen darf die drei Speicherfelder nicht verkoppeln."""
    result = _result()
    result.locations[0].outlook_hourly_data = [
        ForecastDataPoint(ts=datetime(2026, 7, 9 + tag, stunde, 0),
                          t2m_c=14.0 + stunde, wind10m_kmh=10.0)
        for tag in range(2) for stunde in (9, 15)
    ]

    hourly = [get_metric("humidity").dp_field, "t2m_c"]
    overview = resolve_enabled_metrics(["wind_max_kmh", "temp_max_c"])
    outlook = [{"metric_id": "wind", "aggregation": "max"},
               {"metric_id": "temperature", "aggregation": "max"}]

    html = render_compare_html(
        result, enabled_metrics=overview, hourly_metrics=hourly,
        outlook_enabled=True, outlook_metrics=outlook,
    )

    header = _html_hour_header(html)
    assert header[1:3] == [get_metric("humidity").col_label,
                           get_metric("temperature").col_label], (
        f"Die Stundenspalten folgen nicht der Stundenverlauf-Reihenfolge: {header}"
    )

    overview_labels = [
        _TAGS.sub("", m).strip()
        for m in re.findall(r"<td[^>]*>(.*?)</td>", html, re.S)
    ]
    wind_at = overview_labels.index(get_metric("wind").col_label)
    temp_at = next(i for i, label in enumerate(overview_labels)
                   if label.startswith(get_metric("temperature").col_label))
    assert wind_at < temp_at, (
        "Die Uebersichtsreihenfolge (Wind vor Temperatur) hat sich der "
        "Stundenverlauf-Reihenfolge angeglichen"
    )


# ---------------------------------------------------------------------------
# AC-6 — Windrichtungs-Merge ueberlebt die Erweiterung
# ---------------------------------------------------------------------------

def test_wind_direction_still_merges_into_the_wind_cell_next_to_a_new_metric():
    """AC-6: Given Wind, Windrichtung UND eine der 14 neuen Groessen sind
    gleichzeitig gewaehlt / When die Stundenzeile gerendert wird / Then steht
    die Windrichtung weiterhin als Kompasstext in der Wind-Zelle und bekommt
    keine eigene Spalte — die Erweiterung stoert den Merge nicht."""
    dp_humid = get_metric("humidity").dp_field
    html = render_compare_html(
        _result(),
        hourly_metrics=["wind10m_kmh", "wind_direction_deg", dp_humid],
    )

    header = _html_hour_header(html)
    assert get_metric(MERGE_ONLY_METRIC_ID).col_label not in header, (
        f"Die Windrichtung hat eine eigene Spalte bekommen: {header}"
    )
    wind_cell = _html_hour_cells(html)[header[1:].index(get_metric("wind").col_label)]
    assert "W" in wind_cell, (
        f"Kompasstext fehlt in der Wind-Zelle: {wind_cell!r}"
    )


def test_plaintext_hour_row_carries_the_same_columns_as_html():
    """AC-2/AC-6 (kein blinder Fleck): HTML und Klartext derselben Mail zeigen
    dieselben Stundenspalten in derselben Reihenfolge — auch mit einer der 14
    neuen Groessen im Spiel."""
    dp_humid = get_metric("humidity").dp_field
    selection = ["t2m_c", dp_humid, "wind10m_kmh"]

    html = render_compare_html(_result(), hourly_metrics=selection)
    plain = render_comparison_text(_result(), hourly_metrics=selection)

    html_columns = _html_hour_header(html)[1:]
    assert get_metric("humidity").col_label in html_columns, (
        f"Ohne die neue Spalte im HTML prueft dieser Vergleich nichts: "
        f"{html_columns}"
    )
    assert [label for label, _ in _plain_hour_cells(plain)] == html_columns, (
        "Klartext und HTML zeigen unterschiedliche Stundenspalten"
    )
