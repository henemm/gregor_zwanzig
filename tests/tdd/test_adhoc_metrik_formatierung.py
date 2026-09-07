"""TDD RED — Issue #2134 (Epic #2133 S1): der Formatierer eines Ad-hoc-Abrufs
folgt der EIGENSCHAFT des Katalogeintrags, nicht seinem Namen.

SPEC: docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md
      AC-13, AC-14, AC-15, AC-16 (Sektion "Formatierer folgt aus dem
      Katalogeintrag").
SPEC: docs/specs/modules/fix_2167_sonnenstunden_einheit.md
      AC-1, AC-2, AC-3 (Issue #2167 — `Sun` liefert Sonnenstunden statt
      roher Direktstrahlung).

RED-Ursache (#2134): es gibt heute nur `_DRILLDOWN_METRICS`
(trip_command_processor.py:287-291) mit drei fest verdrahteten Formatierern;
`Thdr`/`WDir`/`PType`/`Visib` sind ueberhaupt keine Abrufwoerter. Zusaetzlich
fehlt `PRECIP_TYPE_LABEL_DE` in `src/output/metric_format.py`, und
`format_value("wind_direction", 315)` liefert heute die Gradzahl `'315 °'`
statt einer Himmelsrichtung.

RED-Ursache (#2167): `_metric_formatter()` hat fuer `dp_field == "dni_wm2"`
keinen eigenen Zweig, der Rohwert laeuft unveraendert durch `format_value()`
und wird mit der Katalog-Einheit "h" beschriftet (`781.5 h` statt `1.0 h`).

Mock-frei: echter Snapshot-Roundtrip, echter `process()`-Aufruf. Die
Gegenprobe zu AC-13 veraendert den Katalog ueber `dataclasses.replace`
(siehe `tests/helpers/adhoc_metrik_fixtures.katalog_eintrag_ersetzt`).
"""
from __future__ import annotations

import re

from app.metric_catalog import build_default_display_config
from app.models import ForecastDataPoint, PrecipType, ThunderLevel
from output.renderers.email.helpers import dp_to_row, fmt_val

from tests.helpers.adhoc_metrik_fixtures import (
    TRIP_TZ,
    ist_unbekannt,
    katalog_eintrag_ersetzt,
    lege_trip_an,
    sende,
    standard_felder,
    stundenzeilen,
)

# Zahlenwert einer Stundenzeile, unabhaengig von deren Praefix/Emoji — z.B.
# "08:00  Sonne: 0.5 h" -> 0.5. Bewusst KEIN fester "h"-Anker im Präfix, damit
# derselbe Helfer auch andere Ad-hoc-Groessen lesen könnte.
_ZAHL_VOR_H = re.compile(r"(\d+(?:[.,]\d+)?)\s*h\b")


def _sonnenstundenwerte(body: str) -> list[float]:
    """Je Stundenzeile den ersten '<Zahl> h'-Treffer als float."""
    werte = []
    for zeile in stundenzeilen(body):
        treffer = _ZAHL_VOR_H.search(zeile)
        assert treffer is not None, (
            f"Stundenzeile ohne '<Zahl> h'-Treffer — Formatierer liefert kein "
            f"h-Format mehr:\n{zeile!r}\nGesamtantwort:\n{body}"
        )
        werte.append(float(treffer.group(1).replace(",", ".")))
    return werte

# THUNDER_LABEL_DE = {NONE:"kein", LOW:"leicht", MED:"mittel", HIGH:"hoch"}
# (src/output/metric_format.py:283) — die Woerter werden hier NICHT eingetippt,
# sondern aus derselben Quelle gelesen, aus der auch der Renderer schoepft.
def _stufenwoerter() -> dict[str, str]:
    from output.metric_format import THUNDER_LABEL_DE

    return {stufe.name: wort for stufe, wort in THUNDER_LABEL_DE.items()}


# ===========================================================================
# AC-13 — Stufengroesse erscheint als Wort, und die Regel haengt an is_level
# ===========================================================================

def test_ac13_thdr_liefert_stufenwoerter_statt_rohzahl():
    """AC-13 GIVEN `thunder` traegt is_level=True und col_label `Thdr` WHEN
    ein Nutzer `Thdr` sendet THEN erscheinen die Stundenwerte als Stufenwoerter
    aus THUNDER_LABEL_DE, nicht als Rohzahl/Enum-Bezeichner."""
    fix = lege_trip_an("ac13")  # standard_felder: MED/HIGH im Wechsel
    woerter = _stufenwoerter()

    result = sende(fix, "Thdr", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-13: `Thdr` muss als Abrufwort der Gewitterstufe erkannt werden, "
        f"erhalten command={result.command!r} / "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    for stufe in ("MED", "HIGH"):
        assert woerter[stufe] in body, (
            f"AC-13: das Stufenwort {woerter[stufe]!r} (fuer {stufe}) fehlt in "
            f"der Antwort:\n{body}"
        )
    for roh in ("MED", "HIGH", "ThunderLevel"):
        assert roh not in body, (
            f"AC-13: der interne Bezeichner {roh!r} steht in der Antwort — "
            f"die Stufe wird als Rohwert ausgeliefert:\n{body}"
        )


def test_ac13_gegenprobe_regel_haengt_an_is_level_nicht_am_namen(monkeypatch):
    """AC-13 (Mutations-Gegenprobe) GIVEN eine ANDERE Groesse wird testweise
    auf is_level=True gesetzt WHEN sie abgerufen wird THEN erscheint auch sie
    als Stufenwort — die Formatiererwahl haengt am Merkmal, nicht an der
    Kennung `thunder`.

    Traegergroesse ist `snow_depth` (col_label `SnowH`, dp_field
    `snow_depth_cm`); ihre Stundenwerte tragen hier bewusst Stufenwerte. Das
    ist fachlich unsinnig und genau deshalb der richtige Prueffall: waere die
    Formatiererwahl an `metric.id == "thunder"` festgemacht, bliebe die
    Antwort eine Rohausgabe.
    """
    fix = lege_trip_an(
        "ac13m",
        lambda i: {
            **standard_felder(i),
            "snow_depth_cm": (ThunderLevel.MED, ThunderLevel.HIGH)[i % 2],
        },
    )
    woerter = _stufenwoerter()

    with katalog_eintrag_ersetzt(monkeypatch, "snow_depth", is_level=True):
        result = sende(fix, "SnowH", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-13: `SnowH` muss als Abrufwort erkannt werden, erhalten "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    assert woerter["HIGH"] in body and woerter["MED"] in body, (
        f"AC-13-Gegenprobe: eine Groesse mit is_level=True muss ebenfalls als "
        f"Stufenwort erscheinen — erwartet {woerter['MED']!r}/"
        f"{woerter['HIGH']!r} in:\n{body}"
    )


# ===========================================================================
# AC-14 — Windrichtung als Himmelsrichtung
# ===========================================================================

def test_ac14_wdir_liefert_himmelsrichtungen_statt_gradzahl():
    """AC-14 GIVEN `wind_direction` (dp_field wind_direction_deg, col_label
    `WDir`) WHEN ein Nutzer `WDir` sendet THEN erscheinen die Stundenwerte als
    Himmelsrichtung (315 deg -> NW), nicht als Gradzahl.

    Der Erwartungswert wird ueber `degrees_to_compass()` GEBILDET, nicht als
    Buchstabe eingetippt — sonst pruefte der Test seine eigene Annahme.
    """
    from utils.geo import degrees_to_compass

    grad = 315
    erwartet = degrees_to_compass(grad)
    fix = lege_trip_an(
        "ac14", lambda i: {**standard_felder(i), "wind_direction_deg": grad},
    )

    result = sende(fix, "WDir", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-14: `WDir` muss als Abrufwort der Windrichtung erkannt werden, "
        f"erhalten command={result.command!r} / "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    treffer = re.findall(rf"\b{erwartet}\b", body)
    assert len(treffer) >= 3, (
        f"AC-14: erwartet mehrere Stundenwerte als Himmelsrichtung "
        f"{erwartet!r} ({grad} Grad), gefunden {treffer!r} in:\n{body}"
    )
    assert str(grad) not in body, (
        f"AC-14: die rohe Gradzahl {grad!r} steht in der Antwort — heute "
        f"liefert format_value('wind_direction', {grad}) genau '{grad} °':\n"
        f"{body}"
    )


# ===========================================================================
# AC-15 — Niederschlagsart als deutsches Wort
# ===========================================================================

def test_ac15_ptype_liefert_deutsches_wort_statt_enum_bezeichner():
    """AC-15 GIVEN `precip_type` (col_label `PType`) WHEN ein Nutzer `PType`
    sendet THEN erscheinen die Stundenwerte als deutsches Wort aus
    PRECIP_TYPE_LABEL_DE, nicht als interner Enum-Bezeichner."""
    fix = lege_trip_an(
        "ac15",
        lambda i: {**standard_felder(i), "precip_type": PrecipType.SNOW},
    )

    result = sende(fix, "PType", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-15: `PType` muss als Abrufwort der Niederschlagsart erkannt "
        f"werden, erhalten command={result.command!r} / "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body

    from output import metric_format

    labels = getattr(metric_format, "PRECIP_TYPE_LABEL_DE", None)
    assert labels is not None, (
        "AC-15: `PRECIP_TYPE_LABEL_DE` fehlt in src/output/metric_format.py — "
        "die deutschen Woerter der Niederschlagsart haben noch keine Quelle."
    )
    wort = labels[PrecipType.SNOW] if PrecipType.SNOW in labels else labels["SNOW"]
    treffer = re.findall(rf"\b{re.escape(wort)}\b", body)
    assert len(treffer) >= 3, (
        f"AC-15: erwartet mehrere Stundenwerte als deutsches Wort {wort!r}, "
        f"gefunden {treffer!r} in:\n{body}"
    )
    for roh in ("SNOW", "PrecipType"):
        assert roh not in body, (
            f"AC-15: der interne Bezeichner {roh!r} steht in der Antwort:\n"
            f"{body}"
        )


# ===========================================================================
# AC-16 — display_unit m -> km wird UMGERECHNET
# ===========================================================================

def test_ac16_visib_wird_in_km_umgerechnet_nicht_in_metern_gezeigt():
    """AC-16 GIVEN `visibility` hat unit=m und display_unit=km WHEN ein Nutzer
    `Visib` sendet THEN tragen die Werte die Einheit km und sind umgerechnet —
    2000 m erscheint NICHT als vierstellige Meterzahl.

    Bewusst KEINE Pruefung auf die exakte Zeichenkette "2 km":
    `format_value('visibility', 2000)` liefert (gemessen) '2.0 km', weil die
    Groesse decimals=1 traegt. Die Zusicherung des AC ist "km und
    umgerechnet", nicht eine bestimmte Nachkommastelle.
    """
    fix = lege_trip_an(
        "ac16", lambda i: {**standard_felder(i), "visibility_m": 2000},
    )

    result = sende(fix, "Visib", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-16: `Visib` muss als Abrufwort erkannt werden, erhalten "
        f"command={result.command!r} / body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    treffer = re.findall(r"\b2(?:[.,]0+)?\s*km(?!/)", body)
    assert len(treffer) >= 3, (
        f"AC-16: erwartet mehrere umgerechnete Werte '2 km'/'2.0 km' aus "
        f"2000 m, gefunden {treffer!r} in:\n{body}"
    )
    assert "2000" not in body, (
        f"AC-16: die rohe Meterzahl 2000 steht in der Antwort — die "
        f"display_unit-Umrechnung m->km hat nicht stattgefunden:\n{body}"
    )


# ===========================================================================
# Fix #2167 — `Sun` liefert Sonnenstunden statt roher Direktstrahlung
# ===========================================================================

def test_2167_ac1_sun_liefert_sonnenstunden_nicht_die_rohe_dni_zahl():
    """AC-1 GIVEN alle Stundenpunkte tragen eine Direktstrahlung deutlich
    oberhalb des oberen Bandwerts (781,5 W/m², Band 60/180) WHEN ein Nutzer
    `Sun` sendet THEN traegt jede Stundenzeile hoechstens 1,0 h, und die rohe
    W/m²-Zahl erscheint nirgends in der Antwort."""
    fix = lege_trip_an("2167ac1", lambda i: {**standard_felder(i), "dni_wm2": 781.5})

    result = sende(fix, "Sun", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-1: `Sun` muss als Abrufwort erkannt werden, erhalten "
        f"command={result.command!r} / body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    werte = _sonnenstundenwerte(body)
    assert werte, f"AC-1: keine Stundenzeilen mit '<Zahl> h' gefunden:\n{body}"
    ueberschreitung = [w for w in werte if w > 1.0]
    assert not ueberschreitung, (
        f"AC-1: Stundenwerte > 1.0 h gefunden ({ueberschreitung}) — das sind "
        f"rohe W/m²-Werte statt Sonnenstunden:\n{body}"
    )
    assert "781" not in body, (
        f"AC-1: die rohe Direktstrahlung '781' steht noch in der Antwort — "
        f"der Rohwert laeuft unveraendert durch format_value():\n{body}"
    )


def test_2167_ac2_sun_unterscheidet_truebe_und_sonnige_stunden():
    """AC-2 GIVEN Stundenpunkte im Wechsel unter dem unteren (30.0) und ueber
    dem oberen Bandwert (800.0) WHEN `Sun` abgerufen wird THEN traegt
    mindestens eine Zeile 0,0 h und mindestens eine einen Wert > 0,0 h — nicht
    ueberall derselbe Wert."""
    fix = lege_trip_an(
        "2167ac2",
        lambda i: {**standard_felder(i), "dni_wm2": (30.0, 800.0)[i % 2]},
    )

    result = sende(fix, "Sun", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-2: `Sun` muss als Abrufwort erkannt werden, erhalten "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    werte = _sonnenstundenwerte(body)
    einzigartig = set(werte)
    assert len(einzigartig) > 1, (
        f"AC-2: alle Stundenzeilen tragen denselben Wert {einzigartig} — der "
        f"Verlauf unterscheidet truebe/sonnige Stunden nicht:\n{body}"
    )
    assert 0.0 in einzigartig, (
        f"AC-2: keine Stundenzeile mit 0,0 h fuer die truebe Stunde (30 W/m² "
        f"< unterer Bandwert), gefundene Werte {einzigartig}:\n{body}"
    )


def test_2167_ac3_ad_hoc_und_briefing_nennen_denselben_wert():
    """AC-3 GIVEN konstante Direktstrahlung 120,0 W/m² (mitten im 60/180-Band)
    auf jedem Stundenpunkt WHEN einmal das Trip-Briefing die Sonne-Spalte
    rendert und einmal `Sun` ad hoc abgerufen wird THEN nennen beide fuer
    dieselbe Stunde denselben Sonnenstundenwert. Der erwartete Wert wird NICHT
    eingetippt, sondern aus beiden Pfaden gelesen (Docstring-Warnung der
    Fixtur: konstanter DNI macht den Vergleich unabhaengig vom Zeitfenster)."""
    dni = 120.0
    fix = lege_trip_an("2167ac3", lambda i: {**standard_felder(i), "dni_wm2": dni})

    # Briefing-Pfad: derselbe Produktivcode, den render_email() verwendet.
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id == "sunshine"
    dp = ForecastDataPoint(ts=fix.now, dni_wm2=dni)
    row = dp_to_row(dp, dc, tz=TRIP_TZ)
    briefing_zelle = fmt_val("sunshine", row.get("sunshine"), row=row)
    briefing_treffer = _ZAHL_VOR_H.search(briefing_zelle)
    assert briefing_treffer is not None, (
        f"AC-3: Briefing-Zelle liefert kein '<Zahl> h'-Format: {briefing_zelle!r}"
    )
    briefing_wert = float(briefing_treffer.group(1).replace(",", "."))

    # Ad-hoc-Pfad: echter Kanal-Eingang.
    result = sende(fix, "Sun", channel="telegram")
    assert not ist_unbekannt(result), (
        f"AC-3: `Sun` muss als Abrufwort erkannt werden, erhalten "
        f"body={result.confirmation_body!r}"
    )
    adhoc_werte = set(_sonnenstundenwerte(result.confirmation_body))
    assert adhoc_werte == {briefing_wert}, (
        f"AC-3: Ad-hoc-Werte {adhoc_werte} weichen vom Briefing-Wert "
        f"{briefing_wert} ab — beide Pfade muessten dieselbe Umrechnung "
        f"teilen:\n{result.confirmation_body}"
    )


def _nach_uhrzeit(zeile: str) -> str:
    """Der Teil einer Stundenzeile HINTER der Uhrzeit — die Darstellung
    selbst, ohne den je Stunde verschiedenen Zeitstempel."""
    return zeile.strip().split(None, 1)[1].strip()


def test_2167_f001_fehlende_dni_bleibt_keine_daten_und_wird_nicht_zu_null():
    """Adversary-Finding F001 GIVEN ein Fenster, in dem die Direktstrahlung
    auf geraden Stundenindizes GANZ FEHLT und auf ungeraden deutlich ueber dem
    oberen Bandwert liegt (200,0) WHEN `Sun` abgerufen wird THEN bleibt die
    fehlende Stunde als "keine Daten" kenntlich und wird NICHT zu 0,0 h.

    Warum das eine eigene Zusicherung braucht: `dni_to_sunny_fraction(None)`
    liefert selbst 0.0 (weather_metrics.py:341-342). Ohne den None-Zweig im
    Formatierer wuerde die Luecke also klanglos zu "0.0 h" — aus "keine
    Aussage" wuerde "sicher truebe". Eine Provider-Luecke ist kein
    Theoriefall: `WeatherExtractor.drilldown()` sammelt je Stundenpunkt
    `getattr(p, metric, None)`, und `_traegt_werte()` laesst das Fenster
    bereits bei EINEM Nicht-None-Wert durch.

    Der zweite Trip ist die Positivkontrolle, die beide Faelle
    UNTERSCHEIDBAR macht: 30,0 W/m² ist eine ECHTE Truebstunde und muss 0,0 h
    ergeben. Die Darstellung der fehlenden Stunde wird gegen diese echte
    Nullstunde gehalten, statt gegen eine im Test eingetippte Erwartung.
    """
    fix = lege_trip_an(
        "2167f001",
        lambda i: {
            **standard_felder(i),
            **({"dni_wm2": 200.0} if i % 2 else {}),
        },
    )

    result = sende(fix, "Sun", channel="telegram")

    assert not ist_unbekannt(result), (
        f"F001: `Sun` muss als Abrufwort erkannt werden, erhalten "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    zeilen = stundenzeilen(body)
    assert zeilen, f"F001: keine Stundenzeilen in der Antwort:\n{body}"

    ohne_wert = [z for z in zeilen if _ZAHL_VOR_H.search(z) is None]
    mit_wert = [
        float(_ZAHL_VOR_H.search(z).group(1).replace(",", "."))
        for z in zeilen
        if _ZAHL_VOR_H.search(z) is not None
    ]
    assert ohne_wert, (
        f"F001: KEINE Zeile ohne Stundenwert — die Stunden ohne "
        f"Direktstrahlung wurden zu einem Zahlenwert verrechnet, statt als "
        f"fehlend kenntlich zu bleiben. Gefundene Werte {mit_wert}:\n{body}"
    )
    assert mit_wert, (
        f"F001: keine einzige Stunde mit echtem Wert — die Fixtur oder das "
        f"Fenster traegt die 200 W/m²-Stunden nicht:\n{body}"
    )
    assert 0.0 not in set(mit_wert), (
        f"F001: eine Stundenzeile traegt 0,0 h, obwohl jede VORHANDENE "
        f"Direktstrahlung (200 W/m²) oberhalb des Bandes liegt — die fehlende "
        f"Stunde ist zu einer Nullstunde geworden. Werte {mit_wert}:\n{body}"
    )

    # Positivkontrolle: eine ECHTE Truebstunde (30 W/m² < unterer Bandwert).
    fix_trueb = lege_trip_an(
        "2167f001b", lambda i: {**standard_felder(i), "dni_wm2": 30.0},
    )
    body_trueb = sende(fix_trueb, "Sun", channel="telegram").confirmation_body
    trueb_werte = set(_sonnenstundenwerte(body_trueb))
    assert trueb_werte == {0.0}, (
        f"F001-Positivkontrolle: eine echte Truebstunde muss 0,0 h ergeben, "
        f"gefunden {trueb_werte}:\n{body_trueb}"
    )

    fehlend_dargestellt = {_nach_uhrzeit(z) for z in ohne_wert}
    trueb_dargestellt = {_nach_uhrzeit(z) for z in stundenzeilen(body_trueb)}
    assert not (fehlend_dargestellt & trueb_dargestellt), (
        f"F001: fehlende Stunde und echte Truebstunde sehen gleich aus "
        f"({fehlend_dargestellt & trueb_dargestellt}) — der Leser kann "
        f"'keine Aussage' nicht von 'sicher truebe' unterscheiden."
    )


def _fehlend_dargestellt() -> set[str]:
    """Wie eine Stunde OHNE Direktstrahlung dargestellt wird — gemessen am
    laufenden Produktivpfad, nicht als Zeichenkette eingetippt.

    Gemischtes Fenster, weil ein Fenster GANZ ohne Werte gar nicht als
    Stundenverlauf beantwortet wird (``_traegt_werte`` verlangt einen
    Nicht-None-Wert): gerade Indizes ohne Feld, ungerade mit 200,0 W/m².
    """
    fix = lege_trip_an(
        "2167ref",
        lambda i: {
            **standard_felder(i),
            **({"dni_wm2": 200.0} if i % 2 else {}),
        },
    )
    body = sende(fix, "Sun", channel="telegram").confirmation_body
    formen = {
        _nach_uhrzeit(z)
        for z in stundenzeilen(body)
        if _ZAHL_VOR_H.search(z) is None
    }
    assert formen, (
        f"Referenzmessung fehlgeschlagen: keine Zeile ohne Stundenwert — die "
        f"Darstellung der fehlenden Stunde ist nicht ablesbar:\n{body}"
    )
    return formen


def test_2167_f002_gemessene_nullstrahlung_bleibt_nullstunde():
    """Adversary-Finding F002 GIVEN jeder Stundenpunkt traegt eine EXAKT
    gemessene Nullstrahlung (`dni_wm2 == 0.0`, Feld vorhanden) WHEN `Sun`
    abgerufen wird THEN weist jede Stunde 0,0 h aus und KEINE erscheint als
    "keine Daten".

    Der Spiegelfall zu F001: waere die Fallunterscheidung des Formatierers
    ein `if not value:` statt `if value is None:`, kippte die echte Nullstunde
    in "keine Aussage" — aus "sicher truebe" wuerde "unbekannt". Es ist der
    HAEUFIGSTE Fall, nicht der seltenste: Open-Meteo liefert
    `direct_normal_irradiance` fuer Nachtstunden explizit als 0.0
    (src/providers/openmeteo.py:933), in jedem 24-Stunden-Fenster steckt also
    eine Nacht voller echter Nullen.

    Die Unterscheidung wird GEMESSEN, nicht behauptet: die Darstellung der
    fehlenden Stunde stammt aus `_fehlend_dargestellt()` (zweiter Lauf durch
    denselben Produktivpfad) und wird gegen die Nullstunden-Zeilen gehalten.
    """
    fix = lege_trip_an(
        "2167f002", lambda i: {**standard_felder(i), "dni_wm2": 0.0},
    )

    result = sende(fix, "Sun", channel="telegram")

    assert not ist_unbekannt(result), (
        f"F002: `Sun` muss als Abrufwort erkannt werden, erhalten "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    zeilen = stundenzeilen(body)
    assert zeilen, f"F002: keine Stundenzeilen in der Antwort:\n{body}"

    # `_sonnenstundenwerte` verlangt fuer JEDE Zeile einen '<Zahl> h'-Treffer —
    # eine als "keine Daten" ausgewiesene Nullstunde faellt hier bereits auf.
    werte = set(_sonnenstundenwerte(body))
    assert werte == {0.0}, (
        f"F002: eine gemessene Nullstrahlung muss 0,0 h ergeben, gefundene "
        f"Werte {werte}:\n{body}"
    )

    null_dargestellt = {_nach_uhrzeit(z) for z in zeilen}
    ueberschneidung = null_dargestellt & _fehlend_dargestellt()
    assert not ueberschneidung, (
        f"F002: die gemessene Nullstunde wird dargestellt wie eine FEHLENDE "
        f"({ueberschneidung}) — der Leser kann 'sicher truebe' nicht von "
        f"'keine Aussage' unterscheiden:\n{body}"
    )
