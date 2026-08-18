"""Einheit/Nachkommastellen der Ortsvergleichs-Uebersichtstabelle aus dem
zentralen Wetter-Register statt aus getippten `CV2_METRICS`-Feldern (Issue
#1848, Scheibe B).

`CV2_METRICS` (`src/output/renderers/email/compare_html.py:314-380`) tippt
heute fuer 22 von 26 Zeilen ein `"unit"` und fuer 2 zusaetzlich ein
`"decimals"` -- obwohl `src/app/metric_catalog.py` beide Werte pro
`MetricDefinition` bereits fuehrt. `derive_row_labels()` wird um genau diese
Ableitung erweitert (analog zum bestehenden `"label"`, #1401 Scheibe A2b).

Zwei Testgruppen, klar markiert:

* **RED (Naht-Beweis, Abschnitt A):** heute ROT, weil `derive_row_labels()`
  `unit`/`decimals` noch NICHT ableitet -- ein verbogener Register-Eintrag hat
  deshalb keine Wirkung auf die gerenderte Mail. Nach der Implementierung
  GRUEN. Jeder Register-Patch wird VOR der eigentlichen Pruefung aktiv
  verifiziert (`get_metric(...)` liest den verbogenen Wert), damit ein Rot
  niemals aus dem falschen Grund entsteht.
* **Regressions-Waechter (Abschnitt B):** heute schon GRUEN, muessen es nach
  der Implementierung BLEIBEN (AC-3, AC-5, AC-6, AC-7).

Kern-Schicht, deterministisch: echte `LocationResult`/`ComparisonResult`-
Objekte, echte Renderer-Aufrufe, kein `Mock()`/`patch()`. Registerwerte werden
ueber `monkeypatch.setitem` auf das echte `metric_catalog._METRICS_BY_ID`-
Dict verbogen (kein Patch auf `get_metric` selbst) -- `get_metric()` liest
dieses Dict bei JEDEM Aufruf neu, unabhaengig davon, wie der Aufrufer die
Funktion importiert hat.

Alle Wächter pruefen am GERENDERTEN Ergebnis (HTML-String bzw. Klartext-
Zeile), nicht an `derive_row_labels(...)[i]["unit"]` allein -- ein Test, der
nur die zurueckgegebene Kopie liest, beweist nicht, dass die Leseseite
(`_render_overview_row`, compare_html.py:766) sie tatsaechlich benutzt.

Fixture-Muster uebernommen aus `test_compare_mail_label_source_catalog.py`.

SPEC: docs/specs/modules/feat_1848_b_einheiten_register.md
"""
from __future__ import annotations

import dataclasses
import re
from datetime import date, datetime

import pytest

from app import metric_catalog
from app.metric_catalog import get_metric
from app.models import PrecipType, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import (
    CV2_METRICS, derive_row_labels, render_compare_html,
)

TARGET_DATE = date(2026, 8, 18)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _loc(**overrides) -> LocationResult:
    """Ein Ort mit leeren Stundendaten -- alle in dieser Datei gebrauchten
    Tageswerte werden DIREKT als Attribut gesetzt (`setattr`), nicht ueber
    `hourly_data` live abgeleitet. Das trifft echte `LocationResult`-Felder
    (z. B. `wind_max`) UND die vier Klasse-B-Felder ohne eigenes Dataclass-
    Feld (z. B. `pressure_avg_hpa`) -- `LocationResult` ist ein normales
    mutables Objekt (kein `slots=True`), `_metric_value()` liest beide Faelle
    identisch per `getattr(loc, feld, None)`."""
    loc = LocationResult(
        location=SavedLocation(
            id="ort", name="Ort", lat=39.76, lon=2.71, elevation_m=200,
        ),
        hourly_data=[],
    )
    for key, value in overrides.items():
        setattr(loc, key, value)
    return loc


def _comparison_result(loc: LocationResult) -> ComparisonResult:
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 8, 18, 4, 1),
    )


# ---------------------------------------------------------------------------
# HTML-Ausgabe auslesen (Vorbild: test_compare_mail_label_source_catalog.py)
# ---------------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")


def _overview_rows(html: str) -> list[tuple[str, list[str]]]:
    """(Label, [Wertzellen-Text ohne Tags]) je Zeile der Uebersichtstabelle,
    in Dokumentreihenfolge."""
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    rows = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [
            _TAGS.sub("", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        ]
        if cells:
            rows.append((cells[0], cells[1:]))
    return rows


def _overview_rows_raw(html: str) -> list[tuple[str, list[str]]]:
    """Wie `_overview_rows`, aber OHNE Tag-Strip -- fuer Zellen, deren
    Markup selbst Teil der Zusicherung ist (Warn-Zelle, AC-5)."""
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    rows = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        if cells:
            rows.append((cells[0], cells[1:]))
    return rows


def _single_row_value(html: str) -> str:
    """Erwartet GENAU zwei Zeilen (Warn-Zeile immer zuerst + die eine ueber
    `enabled_metrics=[key]` angeforderte Zeile) und GENAU einen Ort -- liefert
    die Wertzelle der zweiten Zeile."""
    rows = _overview_rows(html)
    assert len(rows) == 2, f"Erwartet Warn-Zeile + 1 Datenzeile, bekommen: {rows}"
    _label, cells = rows[1]
    assert len(cells) == 1, f"Erwartet genau einen Ort, bekommen: {cells}"
    return cells[0]


def _render_one(loc: LocationResult, cv2_key: str) -> str:
    html = render_compare_html(
        _comparison_result(loc), enabled_metrics=[cv2_key], hourly_enabled=False,
    )
    return _single_row_value(html)


def _rows_with_metric_id() -> list[dict]:
    return [row for row in CV2_METRICS if row.get("metric_id")]


# ===========================================================================
# Abschnitt A -- ECHTE ROTE TESTS (Naht-Beweis, Mutations-Gegenprobe der Spec)
# ===========================================================================

def test_red1_overview_unit_is_derived_from_register(monkeypatch):
    """RED-1 (AC-1, Mutations-Gegenprobe 2 der Spec): Register-Eintrag `wind`
    auf eine unverwechselbare Einheit verbogen -- die gerenderte
    `wind_max`-Zelle MUSS diese zeigen, wenn `derive_row_labels()` `"unit"`
    wirklich aus `get_metric("wind").unit` ableitet.

    HEUTE (vor der Implementierung) tippt `CV2_METRICS["wind_max"]` die
    Einheit selbst (`"km/h"`), und `derive_row_labels()` ruehrt nur `"label"`
    an -- der Registerpatch hat also KEINE Wirkung auf die Mail. ROT."""
    patched = dataclasses.replace(get_metric("wind"), unit="ZZZ")
    monkeypatch.setitem(metric_catalog._METRICS_BY_ID, "wind", patched)
    # Sicherung GEGEN Rot-aus-falschem-Grund: der Patch muss ueberhaupt bei
    # get_metric() ankommen, BEVOR wir ihn ueber den Renderer pruefen.
    assert get_metric("wind").unit == "ZZZ", (
        "Registerpatch greift nicht -- get_metric('wind') liefert nicht den "
        "verbogenen Wert. Die Hauptzusicherung unten waere aus dem FALSCHEN "
        "Grund rot."
    )

    cell = _render_one(_loc(wind_max=42.0), "wind_max")

    assert "ZZZ" in cell, (
        f"AC-1: erwartet die verbogene Register-Einheit 'ZZZ' in der "
        f"wind_max-Zelle, bekommen: {cell!r} -- 'unit' kommt noch aus dem "
        f"getippten CV2_METRICS-Feld statt aus get_metric('wind').unit."
    )


def test_red2_overview_decimals_are_derived_from_register(monkeypatch):
    """RED-2 (AC-2, Mutations-Gegenprobe 1 der Spec -- WICHTIGSTER Fall):
    Register-Eintrag `precipitation` auf `decimals=3` verbogen -- die
    `precip_sum`-Zelle muss 3 Nachkommastellen zeigen, wenn
    `derive_row_labels()` `"decimals"` wirklich aus
    `get_metric("precipitation").decimals` ableitet.

    HEUTE tippt `CV2_METRICS["precip_sum"]` `decimals=1` direkt -- die Zelle
    zeigt weiterhin `"12.3 mm"` statt `"12.346 mm"`. ROT."""
    patched = dataclasses.replace(get_metric("precipitation"), decimals=3)
    monkeypatch.setitem(metric_catalog._METRICS_BY_ID, "precipitation", patched)
    assert get_metric("precipitation").decimals == 3, (
        "Registerpatch greift nicht -- get_metric('precipitation') liefert "
        "nicht decimals=3. Die Hauptzusicherung unten waere aus dem "
        "FALSCHEN Grund rot."
    )

    cell = _render_one(_loc(precip_sum_mm=12.3456), "precip_sum")

    assert cell == "12.346 mm", (
        f"AC-2: erwartet 3 Nachkommastellen aus dem verbogenen Register "
        f"(decimals=3), bekommen: {cell!r} -- 'decimals' kommt noch aus dem "
        f"getippten CV2_METRICS-Feld (heute 1) statt aus "
        f"get_metric('precipitation').decimals."
    )


def test_red3_cv2_metrics_no_longer_type_unit_or_decimals():
    """RED-3 (AC-4, erste Haelfte): nach der Implementierung traegt KEIN
    `CV2_METRICS`-Eintrag mit `metric_id` mehr ein eigenes `"unit"`- oder
    `"decimals"`-Feld -- beide werden vollstaendig entfernt, nicht nur
    ueberschrieben (Spec Implementation Details Punkt 2).

    HEUTE tragen 22 Zeilen noch `"unit"`, 2 davon zusaetzlich `"decimals"`.
    ROT."""
    offenders_unit = [row["key"] for row in _rows_with_metric_id() if "unit" in row]
    offenders_decimals = [
        row["key"] for row in _rows_with_metric_id() if "decimals" in row
    ]

    assert offenders_unit == [], (
        f"AC-4: diese CV2_METRICS-Zeilen tragen noch ein getipptes 'unit': "
        f"{offenders_unit} -- muss zur Renderzeit aus dem Register "
        f"abgeleitet werden statt eingetippt zu bleiben."
    )
    assert offenders_decimals == [], (
        f"AC-4: diese CV2_METRICS-Zeilen tragen noch ein getipptes "
        f"'decimals': {offenders_decimals} -- muss zur Renderzeit aus dem "
        f"Register abgeleitet werden statt eingetippt zu bleiben."
    )


def test_red4_derive_row_labels_call_does_not_mutate_module_constant():
    """RED-4 (AC-4, zweite Haelfte -- Mutations-Gegenprobe 4 der Spec): EIN
    echter `derive_row_labels(CV2_METRICS, form="long")`-Aufruf darf
    `CV2_METRICS` NICHT in-place mutieren -- sonst arbeitet ein zweiter Zweig
    derselben Modul-Referenz (`comparison.py`, `_CV2_BY_KEY`) mit veraenderten
    Daten. `{**row, ...}` in `derive_row_labels()` muss eine KOPIE bleiben.

    Faellt HEUTE strukturell mit RED-3 zusammen (die Felder sind ja schon vor
    dem Aufruf da) -- eigenstaendig formuliert, weil er nach der
    Implementierung eine kuenftige In-place-Mutation faengt, die RED-3 allein
    (Pruefung ohne vorherigen Aufruf) nicht mehr sehen wuerde."""
    derive_row_labels(CV2_METRICS, form="long")

    offenders_unit = [row["key"] for row in _rows_with_metric_id() if "unit" in row]
    offenders_decimals = [
        row["key"] for row in _rows_with_metric_id() if "decimals" in row
    ]

    assert offenders_unit == [] and offenders_decimals == [], (
        f"AC-4: nach einem derive_row_labels()-Aufruf traegt CV2_METRICS "
        f"weiterhin 'unit'/'decimals': unit={offenders_unit}, "
        f"decimals={offenders_decimals} -- entweder wurden die Felder nie "
        f"entfernt (RED-3-Fall) oder derive_row_labels() mutiert die "
        f"Modul-Konstante in-place statt eine Kopie zurueckzugeben."
    )


# ===========================================================================
# Abschnitt B -- REGRESSIONS-WAECHTER (heute gruen, muessen gruen bleiben)
# ===========================================================================

def test_ac3_missing_value_shows_em_dash_not_en_dash():
    """AC-3 (Mutations-Gegenprobe 3 der Spec): fehlender Wert einer Zeile
    ohne eigenes 'fmt' zeigt exakt EM DASH `"—"` (U+2014) -- nicht EN DASH
    `"–"` (U+2013). Codepoint-Pruefung, keine Sichtpruefung."""
    cell = _render_one(_loc(), "temp_max")  # temp_max bleibt None

    assert any(ord(ch) == 0x2014 for ch in cell), (
        f"AC-3: erwartet EM DASH (U+2014) fuer fehlenden Wert, Zelle: {cell!r}"
    )
    assert not any(ord(ch) == 0x2013 for ch in cell), (
        f"AC-3: EN DASH (U+2013) darf in der Zelle NICHT vorkommen: {cell!r}"
    )


# Vollstaendigkeits-Nachweis (AC-7): alle 22 CV2_METRICS-Zeilen mit
# `metric_id` und OHNE eigenes 'fmt'. Erwartungswerte sind FEST hinterlegt,
# aus dem HEUTIGEN CV2_METRICS-Stand entnommen (unit/decimals dort
# abgelesen) -- nicht aus dem Pruefling abgeleitet.
# (cv2_key, LocationResult-Attribut, Rohwert, erwartete Zelle)
_AC7_CASES: tuple[tuple[str, str, object, str], ...] = (
    ("temp_max", "temp_max", 21.0, "21°C"),
    ("wind_max", "wind_max", 42.0, "42 km/h"),
    ("precip_sum", "precip_sum_mm", 12.34, "12.3 mm"),
    ("pop_max", "pop_max_pct", 70, "70%"),
    ("sunny_hours", "sunny_hours", 5.6, "5.6 h"),
    ("cloud_avg", "cloud_avg", 55, "55%"),
    ("uv_max", "uv_index_max", 6, "6"),
    ("snow_depth_cm", "snow_depth_cm", 30, "30 cm"),
    ("snow_new_cm", "snow_new_cm", 5, "5 cm"),
    ("temp_min", "temp_min", -3, "-3°C"),
    ("gust_max", "gust_max", 55, "55 km/h"),
    ("freezing_level", "freezing_level_m", 3200, "3200 m"),
    ("wind_direction_avg", "wind_direction_avg", 180, "180 °"),
    ("wind_chill_min", "wind_chill_min", -5, "-5°C"),
    ("wind_chill_max", "wind_chill_max", 19, "19°C"),
    ("cloud_low_avg", "cloud_low_avg", 40, "40%"),
    ("cloud_mid_avg", "cloud_mid_avg", 20, "20%"),
    ("cloud_high_avg", "cloud_high_avg", 10, "10%"),
    ("humidity_avg", "humidity_avg_pct", 65, "65%"),
    ("dewpoint_avg", "dewpoint_avg_c", 8, "8°C"),
    ("pressure_avg", "pressure_avg_hpa", 1013, "1013 hPa"),
    ("snowfall_limit", "snowfall_limit_m", 1800, "1800 m"),
)

assert {c[0] for c in _AC7_CASES} == {
    row["key"] for row in CV2_METRICS
    if row.get("metric_id") and "fmt" not in row
}, "AC-7-Faelle decken nicht exakt die 22 fmt-losen CV2_METRICS-Zeilen ab"


@pytest.mark.parametrize("cv2_key,attr,value,expected", _AC7_CASES, ids=[c[0] for c in _AC7_CASES])
def test_ac7_every_metric_id_row_matches_pre_change_reference_output(cv2_key, attr, value, expected):
    """AC-7: fuer jede der 22 numerischen Zeilen (ohne eigenes 'fmt') stimmt
    die gerenderte Zelle exakt mit dem Verhalten ueberein, das `_fmt_metric`
    vor dieser Aenderung mit dem seinerzeit getippten `unit`/`decimals`
    erzeugt hat -- fest hinterlegte Erwartungswerte, nicht aus dem Pruefling
    abgeleitet."""
    cell = _render_one(_loc(**{attr: value}), cv2_key)

    assert cell == expected, (
        f"AC-7: Zeile {cv2_key!r} zeigt {cell!r}, erwartet (Referenz aus dem "
        f"heutigen CV2_METRICS-Stand) {expected!r}."
    )


# AC-5: die drei Zeilen mit eigenem 'fmt' bleiben von der neuen Ableitung
# unbeeinflusst -- ihr `fmt`-Zweig in `_render_overview_row()` ruft
# `_fmt_metric` gar nicht auf.
_AC5_OWN_FMT_CASES = (
    ("thunder_max", "thunder_level_max", ThunderLevel.MED, "mittel"),
    ("visibility_min", "visibility_min_m", 9000, "9.0 km"),
    ("precip_type", "precip_type_dominant", PrecipType.RAIN, "Regen"),
)


@pytest.mark.parametrize(
    "cv2_key,attr,value,expected", _AC5_OWN_FMT_CASES,
    ids=[c[0] for c in _AC5_OWN_FMT_CASES],
)
def test_ac5_own_fmt_rows_unaffected_by_register_derivation(cv2_key, attr, value, expected):
    cell = _render_one(_loc(**{attr: value}), cv2_key)

    assert cell == expected, (
        f"AC-5: Zeile {cv2_key!r} (eigenes 'fmt') zeigt {cell!r}, erwartet "
        f"unveraendert {expected!r} -- die unit/decimals-Ableitung darf "
        f"diese Zeile nicht beeinflussen."
    )


def test_ac5_warn_row_without_alerts_unaffected():
    """AC-5: die Warn-Zeile ('Amtliche Warnungen', kein `metric_id`) bleibt
    exakt beim bestehenden Markup -- sie hatte nie ein 'unit'/'decimals'-Feld
    und geht ohnehin nicht durch `_fmt_metric`."""
    html = render_compare_html(
        _comparison_result(_loc()), enabled_metrics=["temp_max"], hourly_enabled=False,
    )
    rows = _overview_rows_raw(html)
    _warn_label, warn_cells = rows[0]

    assert warn_cells[0] == '<span style="color:#b8b4a8;font-size:12px;">—</span>', (
        f"AC-5: Warn-Zelle ohne Alarme weicht vom bestehenden Markup ab: "
        f"{warn_cells[0]!r}"
    )


def test_ac6_plaintext_branch_runs_and_shows_register_label_unaffected():
    """AC-6: der Klartext-Zweig (`comparison.py::render_comparison_text`,
    ruft `derive_row_labels(..., form="long")` ueber DIESELBE Funktion auf)
    laeuft nach der Erweiterung fehlerfrei durch und zeigt weiterhin
    `row["label"]" -- die zusaetzlichen Felder 'unit'/'decimals' in der
    Rueckgabe-Kopie werden vom Klartext-Zweig nicht gelesen (er formatiert
    ueber eigene Lambdas, s. `_PLAIN_ROWS`) und duerfen ihn nicht brechen."""
    text = render_comparison_text(
        _comparison_result(_loc(temp_max=21.0)),
        enabled_metrics=["temp_max"], hourly_enabled=False,
    )

    assert "Temperatur:" in text, (
        f"AC-6: der Klartext-Zweig zeigt nicht mehr das aus dem Register "
        f"abgeleitete Label 'Temperatur' fuer die temp_max-Zeile:\n{text}"
    )

