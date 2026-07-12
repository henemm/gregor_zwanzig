"""source -> Anzeigename-Mapping für amtliche Warnungen (#1216, AC-7).

SPEC: docs/specs/modules/issue_1216_embedded_warnblock.md (AC-7)

RED-Phase: Bisher ist die Quelle in `notification_service.py` hartkodiert
(„GeoSphere Austria" für ALLE Quellen, Zeilen 481/574). Die Spec verlangt eine
Mapping-Funktion `official_alert_source_label(source)`, die den echten
Anzeigenamen je Quelle liefert — diese Funktion existiert noch nicht in
`output.renderers.alert.official_alerts` -> ImportError.

Verhaltenstest — KEINE Mocks. Reine Mapping-Funktion, kein Netzwerk.
"""
from __future__ import annotations


def test_geosphere_warn_maps_to_geosphere_austria():
    from output.renderers.alert.official_alerts import official_alert_source_label
    assert official_alert_source_label("geosphere_warn") == "GeoSphere Austria"


def test_meteofrance_vigilance_maps_to_meteo_france():
    from output.renderers.alert.official_alerts import official_alert_source_label
    assert official_alert_source_label("meteofrance_vigilance") == "Météo-France"


def test_meteo_forets_maps_to_meteo_france_waldbrand():
    """Waldbrand-Gefahrenstufen (source="meteo_forets") sind eine eigene
    Produktivquelle (services/official_alerts/meteo_forets.py) — der Compare-
    Aggregat-Banner rendert erstmals eine Quelle-Zeile und darf nicht den rohen
    Identifier „meteo_forets" zeigen."""
    from output.renderers.alert.official_alerts import official_alert_source_label
    label = official_alert_source_label("meteo_forets")
    assert label == "Météo-France (Waldbrand)"
    assert "meteo_forets" not in label


def test_massif_closure_maps_to_praefektur_label():
    """Präfektur-Zugangssperren (source="massif_closure") sind eine eigene
    Produktivquelle (services/official_alerts/massif_closure.py) — nie den rohen
    Identifier „massif_closure" zeigen."""
    from output.renderers.alert.official_alerts import official_alert_source_label
    label = official_alert_source_label("massif_closure")
    assert label == "Präfektur (Zugangssperre)"
    assert "massif_closure" not in label


def test_all_known_production_sources_have_human_label():
    """AC-7 „für ALLE Quellen": jeder tatsächlich in
    src/services/official_alerts/*.py per OfficialAlert(source=...) erzeugte Wert
    muss einen menschenlesbaren Namen liefern, der NICHT der rohe Identifier ist."""
    from output.renderers.alert.official_alerts import official_alert_source_label
    known_sources = [
        "geosphere_warn",
        "meteofrance_vigilance",
        "meteo_forets",
        "massif_closure",
    ]
    for src in known_sources:
        label = official_alert_source_label(src)
        assert label != src, f"Quelle {src!r} zeigt den rohen Identifier statt Klarnamen"
        assert "_" not in label, f"Quelle {src!r} -> {label!r} sieht nach rohem Identifier aus"


def test_distinct_sources_do_not_collapse_to_single_hardcoded_label():
    """Der Bestands-Bug war: ALLE Quellen zeigten „GeoSphere Austria". Nach dem
    Fix müssen mindestens GeoSphere und Météo-France UNTERSCHIEDLICHE Namen
    liefern."""
    from output.renderers.alert.official_alerts import official_alert_source_label
    geosphere = official_alert_source_label("geosphere_warn")
    vigilance = official_alert_source_label("meteofrance_vigilance")
    assert geosphere != vigilance, (
        f"Quellen dürfen nicht auf denselben hartkodierten Namen kollabieren: "
        f"{geosphere!r} == {vigilance!r}"
    )
    assert "Météo" in vigilance and "GeoSphere" in geosphere
