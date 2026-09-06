"""TDD RED — Issue #2134 (Epic #2133 S1): der Formatierer eines Ad-hoc-Abrufs
folgt der EIGENSCHAFT des Katalogeintrags, nicht seinem Namen.

SPEC: docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md
      AC-13, AC-14, AC-15, AC-16 (Sektion "Formatierer folgt aus dem
      Katalogeintrag").

RED-Ursache: es gibt heute nur `_DRILLDOWN_METRICS`
(trip_command_processor.py:287-291) mit drei fest verdrahteten Formatierern;
`Thdr`/`WDir`/`PType`/`Visib` sind ueberhaupt keine Abrufwoerter. Zusaetzlich
fehlt `PRECIP_TYPE_LABEL_DE` in `src/output/metric_format.py`, und
`format_value("wind_direction", 315)` liefert heute die Gradzahl `'315 °'`
statt einer Himmelsrichtung.

Mock-frei: echter Snapshot-Roundtrip, echter `process()`-Aufruf. Die
Gegenprobe zu AC-13 veraendert den Katalog ueber `dataclasses.replace`
(siehe `tests/helpers/adhoc_metrik_fixtures.katalog_eintrag_ersetzt`).
"""
from __future__ import annotations

import re

from app.models import PrecipType, ThunderLevel

from tests.helpers.adhoc_metrik_fixtures import (
    ist_unbekannt,
    katalog_eintrag_ersetzt,
    lege_trip_an,
    sende,
    standard_felder,
)

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
