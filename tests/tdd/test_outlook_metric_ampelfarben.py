"""TDD RED — #1849: Ausblick-Metrikzweig verliert alle Ampelfarben bei
Spaltenauswahl.

SPEC: docs/specs/modules/fix_1849_ausblick_ampelfarben.md AC-1..AC-8
KONTEXT: docs/context/fix-1849-ausblick-ampelfarben.md

Getroffen wird ausschliesslich der Metrik-Zweig von ``render_outlook_table()``
(``metrics is not None``) -- direkt ueber ``build_outlook_row()`` +
``render_outlook_table()``, dem echten Aufrufpfad von Trip (``show_acc=True``)
UND Ortsvergleich (``show_acc=False``, ``compare_html.py:1242``). Der Altpfad
(``metrics=None``) wird von diesem Fix nicht angefasst -- AC-8 belegt das nur
noch als Regressionswaechter, nicht als RED-Demonstration.

RED-Erwartung: AC-1, AC-2, der LOW/MED/HIGH-Teil von AC-3/AC-4/AC-5 sowie der
Wind-Teil der gemischten Faelle in AC-6/AC-7 scheitern -- der Metrik-Zweig
setzt heute (``outlook.py:128-152``) fuer KEINE Zelle ein ``background:``.
Die "bleibt farblos"-Teilaussagen von AC-3 (NONE)/AC-6 (snow_depth)/AC-7
(precip_type) sind bereits heute wahr (nichts ist gefaerbt); sie werden
deshalb NICHT isoliert getestet, sondern zusammen mit einer gefaerbten Spalte
im selben Testfall gefordert, damit jeder Testfall insgesamt rot ist.

Kern-Schicht, deterministisch. Kein Mock-Framework, kein Netz.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

from app.models import PrecipType, SegmentWeatherSummary, ThunderLevel  # noqa: E402
from output.renderers.email.design_tokens import tone_css  # noqa: E402
from output.renderers.email.outlook import (  # noqa: E402
    _metric_column_bg, build_outlook_row, render_outlook_table,
)

TZ = ZoneInfo("Europe/Berlin")

# Auswahl-Bausteine im Neuformat (#1373), identisch zu den Katalog-Paaren aus
# compare_metric_catalog.py.
WIND = {"metric_id": "wind", "aggregation": "max"}          # yellow30/orange50/red70
SNOW = {"metric_id": "snow_depth", "aggregation": "max"}    # display_thresholds == {}
GEWITTER = {"metric_id": "thunder", "aggregation": "max"}   # ordinal
NIEDERSCHLAGSART = {"metric_id": "precip_type", "aggregation": "max"}  # enum


def _summary(**overrides) -> SegmentWeatherSummary:
    """Minimal-Fixture: alle Felder sind Optional mit Default None."""
    return SegmentWeatherSummary(**overrides)


def _row(summary: SegmentWeatherSummary, metrics: list[dict], weekday: str = "Mo") -> dict:
    """Row-Dict wie ``aggregate_stage``/``summarize_points`` es lieferten --
    ``points=[]`` ist unschaedlich, die Stundenreihen sind fuer diese Tests
    ohne Bedeutung (kein Trip-Tagesfenster im Spiel, #1841 bleibt unberuehrt)."""
    return build_outlook_row(summary, [], weekday, TZ, metrics=metrics)


def _cell_styles(table_html: str) -> list[str]:
    """``style``-Attribute aller ``<td>``-Zellen der Ausblick-Tabelle, in
    Dokumentreihenfolge (Index 0 = Wochentags-Zelle)."""
    return re.findall(r'<td style="([^"]*)"', table_html)


def _bg_of(style: str) -> str:
    """Der ``background:...;``-Teil eines Zellenstils, oder ``""`` wenn keiner
    gesetzt ist. ``bg`` wird in ``_otd()`` immer als ERSTER Bestandteil des
    ``style``-Attributs eingefuegt (outlook.py:87-98)."""
    if not style.startswith("background:"):
        return ""
    return style[: style.index(";") + 1]


# ══════════════════ AC-1 / AC-2 — numerische Spalte ueber Schwelle ══════════

def test_ac1_numerische_spalte_ueber_schwelle_bekommt_ampelfarbe_im_trip():
    """AC-1: Wind 55 km/h liegt zwischen der orange- (50) und der red-Schwelle
    (70) aus dem Katalog (``get_metric("wind").display_thresholds``) -- die
    Windspalte muss ``background:{tone_css('orange')[0]};`` tragen.
    """
    row = _row(_summary(wind_max_kmh=55.0), [WIND])
    html = render_outlook_table([row], show_acc=True, metrics=[WIND])

    styles = _cell_styles(html)
    # #2098: seit der Behebung traegt der Trip-Zweig (show_acc=True) hinter
    # den gewaehlten Spalten die fest angehaengte ACC-Zelle.
    assert len(styles) == 3, (
        f"Erwartet Wochentag + 1 Metrikspalte + ACC: {styles!r}"
    )
    assert _bg_of(styles[1]) == f"background:{tone_css('orange')[0]};", (
        f"Windspalte (55 km/h, orange-Schwelle 50) traegt {styles[1]!r} -- "
        "der Metrik-Zweig faerbt heute KEINE Zelle (AC-1)."
    )


def test_ac2_ortsvergleich_bekommt_dieselbe_farbe_wie_der_trip():
    """AC-2: derselbe Rohwert liefert ueber den Compare-Aufrufweg
    (``show_acc=False``, wie ``compare_html.py:1242``) dieselbe Farbe wie
    AC-1 -- Beweis fuer den geteilten Codepfad, nicht nur zufaellige
    Parallelitaet.
    """
    row = _row(_summary(wind_max_kmh=55.0), [WIND])

    trip_html = render_outlook_table([row], show_acc=True, metrics=[WIND])
    compare_html = render_outlook_table([row], show_acc=False, metrics=[WIND])

    trip_bg = _bg_of(_cell_styles(trip_html)[1])
    compare_bg = _bg_of(_cell_styles(compare_html)[1])
    assert compare_bg == trip_bg == f"background:{tone_css('orange')[0]};", (
        f"Trip-Hintergrund {trip_bg!r} vs. Compare-Hintergrund {compare_bg!r} "
        "-- beide muessen identisch sein (AC-2)."
    )


# ══════════════ AC-3 / AC-4 / AC-5 — Gewitterstufen NONE..HIGH ══════════════

def test_ac3_ac4_ac5_gewitterspalte_folgt_der_ampelband_zuordnung_je_stufe():
    """AC-3: NONE bleibt farblos (kein gruener Teppich trotz
    ``thunder_ampel_band(NONE) == "green"``).
    AC-4: LOW traegt exakt ``background:#fbe6c3;`` (Altpfad-Hellgelbton),
    NICHT ``tone_css('yellow')``.
    AC-5: MED/HIGH tragen ``tone_css('orange')``/``tone_css('red')``.
    """
    stufen = ["NONE", "LOW", "MED", "HIGH"]
    rows = [
        _row(_summary(thunder_level_max=getattr(ThunderLevel, stufe)), [GEWITTER],
             weekday=f"T{i}")
        for i, stufe in enumerate(stufen)
    ]
    html = render_outlook_table(rows, show_acc=True, metrics=[GEWITTER])

    styles = _cell_styles(html)
    # Gewitterspalte ist Index 1 JEDER Zeile. Die Zahl der Zellen je Zeile
    # wird abgeleitet statt festgeschrieben -- seit #2098 traegt der
    # Trip-Zweig hinter der Auswahl zusaetzlich die feste ACC-Zelle.
    je_zeile = len(styles) // len(stufen)
    gewitter_bg = [_bg_of(styles[i * je_zeile + 1]) for i in range(len(stufen))]

    erwartet = [
        "",  # NONE
        "background:#fbe6c3;",  # LOW -- Altpfad-Hellgelbton, kein tone_css('yellow')
        f"background:{tone_css('orange')[0]};",  # MED
        f"background:{tone_css('red')[0]};",  # HIGH
    ]
    assert gewitter_bg == erwartet, (
        f"Gewitter-Hintergruende {gewitter_bg!r} statt {erwartet!r} fuer die "
        "Stufen NONE/LOW/MED/HIGH (AC-3/AC-4/AC-5). Vorsicht bei tone_css('yellow') "
        f"({tone_css('yellow')[0]!r}) statt des LOW-Sonderfarbtons #fbe6c3."
    )


# ═══════════════ AC-6 / AC-7 — dauerhaft farblose Spalten ═══════════════════

def test_ac6_metrik_ohne_katalogschwellen_bleibt_farblos_trotz_hohem_wert():
    """AC-6: ``snow_depth`` hat ``display_thresholds == {}``
    (``severity_from_thresholds`` liefert dafuer ``None``, NICHT "green" --
    metric_format.py:141-174). Selbst ein hoher Wert (150 cm) darf keine
    Farbe erzeugen und keinen Fehler werfen.

    Gemeinsam mit einer gefaerbten Windspalte getestet, damit dieser
    Testfall insgesamt rot ist (der farblose Teil allein waere schon heute
    gruen, da der Metrik-Zweig aktuell ueberhaupt nichts faerbt).
    """
    auswahl = [WIND, SNOW]
    row = _row(_summary(wind_max_kmh=80.0, snow_depth_cm=150.0), auswahl)
    html = render_outlook_table([row], show_acc=True, metrics=auswahl)

    styles = _cell_styles(html)
    # #2098: + die fest angehaengte ACC-Zelle (show_acc=True, Trip).
    assert len(styles) == 4, (
        f"Erwartet Wochentag + 2 Metrikspalten + ACC: {styles!r}"
    )
    assert _bg_of(styles[1]) == f"background:{tone_css('red')[0]};", (
        f"Windspalte (80 km/h, red-Schwelle 70) traegt {styles[1]!r} statt rot."
    )
    assert _bg_of(styles[2]) == "", (
        f"Schneehoehe-Spalte (150 cm, keine Katalog-Schwellen) traegt "
        f"{styles[2]!r} -- muesste farblos bleiben (AC-6)."
    )


def test_ac7_niederschlagsart_bleibt_immer_farblos():
    """AC-7: die Enum-Spalte "Niederschlagsart" (``kind=="enum"``) hat kein
    Altpfad-Vorbild fuer eine Faerbung und bleibt fuer JEDEN Wert farblos --
    geprueft mit zwei verschiedenen Werten, gemeinsam mit einer gefaerbten
    Windspalte (Begruendung wie AC-6)."""
    auswahl = [WIND, NIEDERSCHLAGSART]
    for wert in (PrecipType.RAIN, PrecipType.SNOW):
        row = _row(_summary(wind_max_kmh=80.0, precip_type_dominant=wert), auswahl)
        html = render_outlook_table([row], show_acc=True, metrics=auswahl)
        styles = _cell_styles(html)

        assert _bg_of(styles[1]) == f"background:{tone_css('red')[0]};", (
            f"Windspalte traegt {styles[1]!r} statt rot (Vorbedingung fuer "
            f"einen insgesamt roten Testfall, Wert={wert!r})."
        )
        assert _bg_of(styles[2]) == "", (
            f"Niederschlagsart-Spalte (Wert={wert!r}) traegt {styles[2]!r} -- "
            "muss immer farblos bleiben (AC-7)."
        )


def test_ac7_enum_zweig_greift_vor_der_numerischen_auswertung():
    """AC-7, Mutations-Waechter (Adversary F001): der ``enum``-Zweig darf nicht
    nur ZUFAELLIG dasselbe liefern wie sein numerischer Nachbar. Der einzige
    echte Enum-Katalogeintrag (``precip_type``) hat leere
    ``display_thresholds`` und bliebe auch ohne den Zweig farblos -- an echten
    Daten faellt ein entfernter ``enum``-Zweig deshalb nicht auf.

    Geprueft wird darum die reine Funktion mit einer gueltigen, im
    Produktivpfad so nicht vorkommenden Kombination: ``kind="enum"`` mit einer
    ``metric_id``, die sehr wohl Katalog-Schwellen hat (``wind``). Der erste
    Assert stellt sicher, dass derselbe Wert im numerischen Zweig tatsaechlich
    faerbt -- ohne ihn wuerde der zweite nichts beweisen.
    """
    numerisch = _metric_column_bg({"kind": "range", "metric_id": "wind"}, 80.0)
    assert numerisch == f"background:{tone_css('red')[0]};", (
        f"Vorbedingung verletzt: derselbe Wert traegt im numerischen Zweig "
        f"{numerisch!r} statt rot -- der Enum-Vergleich unten wuerde dann "
        "nichts unterscheiden."
    )
    assert _metric_column_bg({"kind": "enum", "metric_id": "wind"}, 80.0) == "", (
        "kind=='enum' muss VOR der numerischen Auswertung greifen und "
        "unabhaengig von vorhandenen Katalog-Schwellen farblos bleiben (AC-7)."
    )


# ═══════════════════ AC-8 — Altpfad bleibt unveraendert ═════════════════════

def test_ac8_altpfad_ohne_auswahl_faerbt_weiterhin_wie_bisher():
    """AC-8: ``metrics=None`` (Altbestand, keine Spaltenauswahl) durchlaeuft
    den unangetasteten Altpfad -- dessen Faerbelogik (``_outlook_cell_bg``/
    ``_THUNDER_LEVEL_BG``) bleibt exakt wie vor diesem Fix.

    🔴 Regressionswaechter, kein RED-Beweis: der Altpfad wird von diesem Fix
    nicht veraendert, dieser Test ist schon vor der Implementierung gruen
    (analog test_trip_outlook_parity.py:96/117). Er sichert ab, dass der neue
    Metrik-Zweig-Code den Altpfad nicht versehentlich mitreisst.
    """
    row = _row(_summary(wind_max_kmh=55.0, thunder_level_max=ThunderLevel.MED),
               metrics=None)
    html = render_outlook_table([row], show_acc=True, metrics=None)

    # Altpfad-Spalten: Tag, N, D, R, PR, Wind, Böen, Gew, ACC -- Wind ist
    # Index 5, Gewitter Index 7 (outlook.py:154-167).
    styles = _cell_styles(html)
    assert len(styles) == 9, f"Erwartet die neun festen Altpfad-Spalten: {styles!r}"
    assert _bg_of(styles[5]) == f"background:{tone_css('orange')[0]};", (
        f"Altpfad-Windspalte (55 km/h) traegt {styles[5]!r} -- der Altpfad "
        "darf sich durch diesen Fix nicht aendern (AC-8)."
    )
    assert _bg_of(styles[7]) == f"background:{tone_css('orange')[0]};", (
        f"Altpfad-Gewitterspalte (MED) traegt {styles[7]!r} -- unveraendert "
        "erwartet (AC-8)."
    )
