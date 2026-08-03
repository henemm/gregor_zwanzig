"""TDD RED — Issue #1474 (S3 zu #1419), AC-1 und AC-4.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3

AC-1: `ThunderLevel.LOW` ist der einzige neue Enum-Wert (der seit jeher
unbesetzte Platz `L`). `thunder_ordinal()` und `thunder_label_value()` liefern
fuer alle vier Werte {NONE:0, LOW:1, MED:2, HIGH:3} — additive Erweiterung,
KEINE Umdeutung von MED/HIGH.

AC-4: `_parse_thunder_level()` liefert bei fehlendem Wettercode `None`
("keine Aussage"), nicht `ThunderLevel.NONE` ("geprueft, unauffaellig").

RED-Ursache (heute): `ThunderLevel` kennt kein `LOW` -> `AttributeError` bei
jedem Zugriff auf `ThunderLevel.LOW`. AC-4 ist unabhaengig davon bereits rot,
weil `_parse_thunder_level(None)` heute `ThunderLevel.NONE` statt `None`
liefert.

Keine Mocks: reine Funktionsaufrufe auf dem echten Enum/den echten
Skalenfunktionen, kein Netz.
"""
from __future__ import annotations

from app.models import ThunderLevel
from output.metric_format import thunder_label_value, thunder_ordinal


def test_ac1_ordinal_scale_covers_all_four_levels_in_order():
    """AC-1: thunder_ordinal() liefert {NONE:0, LOW:1, MED:2, HIGH:3}."""
    assert thunder_ordinal(ThunderLevel.NONE) == 0
    assert thunder_ordinal(ThunderLevel.LOW) == 1
    assert thunder_ordinal(ThunderLevel.MED) == 2
    assert thunder_ordinal(ThunderLevel.HIGH) == 3


def test_ac1_render_scale_covers_all_four_levels_in_order():
    """AC-1: thunder_label_value() liefert {NONE:0, LOW:1, MED:2, HIGH:3} —
    LOW belegt endlich den bisher unerreichbaren Render-Platz 1."""
    assert thunder_label_value(ThunderLevel.NONE) == 0
    assert thunder_label_value(ThunderLevel.LOW) == 1
    assert thunder_label_value(ThunderLevel.MED) == 2
    assert thunder_label_value(ThunderLevel.HIGH) == 3


def test_ac1_bestandswerte_med_high_render_unveraendert():
    """AC-1 (Vorher/Nachher-Beweis): Der Render-Wert von MED/HIGH darf sich
    durch die Erweiterung NICHT verschieben — kein nutzersichtbarer
    Render-Sprung fuer Bestandswerte. Vor dieser Scheibe war
    thunder_label_value(MED) == 2 und thunder_label_value(HIGH) == 3
    (_THUNDER_LABEL_VALUE = {NONE:0, MED:2, HIGH:3}, metric_format.py:236)."""
    assert thunder_label_value(ThunderLevel.MED) == 2, (
        "MED darf seinen bisherigen Render-Wert 2 nicht verlieren"
    )
    assert thunder_label_value(ThunderLevel.HIGH) == 3, (
        "HIGH darf seinen bisherigen Render-Wert 3 nicht verlieren"
    )


def test_ac4_fehlender_wettercode_liefert_none_nicht_kein_gewitter():
    """AC-4: `weather_code=None` -> `_parse_thunder_level()` liefert `None`
    ("keine Aussage"), nicht `ThunderLevel.NONE` ("geprueft, unauffaellig")."""
    from providers.openmeteo import OpenMeteoProvider

    parse = OpenMeteoProvider()._parse_thunder_level
    assert parse(None) is None, (
        "Fehlender Wettercode muss 'keine Aussage' (None) liefern, nicht "
        "die gepruefte Entwarnung ThunderLevel.NONE"
    )


def test_ac4_vorhandener_nicht_gewitter_code_bleibt_none_level():
    """AC-4 (Gegenprobe): ein VORHANDENER, nicht-Gewitter-Code bleibt weiterhin
    die gepruefte Entwarnung ThunderLevel.NONE (KEINE Aenderung an diesem
    Fall)."""
    from providers.openmeteo import OpenMeteoProvider

    parse = OpenMeteoProvider()._parse_thunder_level
    assert parse(1) == ThunderLevel.NONE, (
        "Ein vorhandener, nicht-Gewitter-Wettercode muss weiterhin "
        "ThunderLevel.NONE liefern (geprueft, unauffaellig)"
    )
    assert parse(95) == ThunderLevel.HIGH, (
        "WMO 95 (Gewitter) muss weiterhin ThunderLevel.HIGH liefern"
    )
