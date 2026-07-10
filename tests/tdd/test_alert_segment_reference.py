"""Segment-/Etappen-Bezug in der amtlichen Standalone-Alert-Mail (#1200).

RED-Phase: `format_segment_reference()` existiert noch nicht,
`render_official_alert_notice_plain()` und `dedupe_official_alerts()` erwarten
noch keine `(OfficialAlert, segment_ids)`-Tupel. Reale `OfficialAlert`-
Instanzen, kein Mock.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from services.official_alerts.models import OfficialAlert


def _alert(level: int = 3, *, hazard: str = "heat", region: str = "Haute-Corse",
           label: str = "Hitze") -> OfficialAlert:
    return OfficialAlert(
        source="meteo-france", hazard=hazard, level=level, label=label,
        valid_from=None, valid_to=None,
        url="https://example.invalid/vigilance", region_label=region,
    )


# ---------------------------------------------------------------------------
# format_segment_reference() — Range/Aufzaehlung/Verdichtung/Ziel-Sonderfall
# ---------------------------------------------------------------------------


def test_single_segment_gets_segment_prefix():
    """Ein einzelnes betroffenes Segment traegt den 'Segment N'-Praefix."""
    from output.renderers.alert.official_alerts import format_segment_reference

    assert format_segment_reference(["3"]) == "Segment 3"


def test_consecutive_segments_render_as_range():
    """AC-2: zusammenhaengende Segmente 3,4,5 -> Range statt Aufzaehlung."""
    from output.renderers.alert.official_alerts import format_segment_reference

    assert format_segment_reference(["3", "4", "5"]) == "Segment 3–5"


def test_non_consecutive_segments_render_as_enumeration():
    """AC-3: nicht zusammenhaengende Segmente 3,5 -> Aufzaehlung mit Komma,
    kein Bindestrich (kein Range-Format)."""
    from output.renderers.alert.official_alerts import format_segment_reference

    result = format_segment_reference(["3", "5"])
    assert result == "Segment 3, 5"
    assert "–" not in result


def test_more_than_four_segments_condense_to_count():
    """AC-4: >4 betroffene Segmente -> Verdichtung 'N Segmente'. Begriff
    bewusst 'Segmente', nicht 'Etappen' (PO-Korrektur 2026-07-09: der Bezug
    ist strukturell immer auf Segmente, nie auf Etappen)."""
    from output.renderers.alert.official_alerts import format_segment_reference

    assert format_segment_reference(["3", "4", "5", "6", "7"]) == "5 Segmente"


def test_condensation_applies_regardless_of_range_or_enumeration():
    """AC-4 (Zusatz): Verdichtung greift auch bei nicht-zusammenhaengenden
    IDs, nicht nur bei echten Ranges."""
    from output.renderers.alert.official_alerts import format_segment_reference

    assert format_segment_reference(["1", "3", "5", "7", "9"]) == "5 Segmente"


def test_ziel_only_has_no_segment_prefix():
    """AC-5: ausschliesslich Ziel-Segment -> nur '🏁 Ziel', kein
    'Segment'-Praefix, keine numerische Range."""
    from output.renderers.alert.official_alerts import format_segment_reference

    assert format_segment_reference(["Ziel"]) == "🏁 Ziel"


def test_mixed_range_and_ziel_appends_ziel_separately():
    """AC-6: Segmente 3,4,5 + Ziel -> 'Segment 3–5, 🏁 Ziel'; Ziel wird NIE in
    die numerische Range gemischt."""
    from output.renderers.alert.official_alerts import format_segment_reference

    assert format_segment_reference(["3", "4", "5", "Ziel"]) == "Segment 3–5, 🏁 Ziel"


# ---------------------------------------------------------------------------
# render_official_alert_notice_plain() zeigt den Segment-Bezug in der Zeile
# ---------------------------------------------------------------------------


def test_render_notice_plain_includes_segment_reference():
    """AC-1: eine Warnung, die genau Segment 3 betrifft -> die Region-Zeile
    traegt den Segment-Bezug."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    out = "\n".join(render_official_alert_notice_plain(
        [(_alert(3), ["3"])], tz=ZoneInfo("UTC"),
    ))
    assert "Region: Haute-Corse — Segment 3" in out, out


def test_render_notice_plain_mixed_segments_and_ziel():
    """AC-6 (voller Render-Pfad): Segmente 3-5 + Ziel im tatsaechlichen
    Mail-Text."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    out = "\n".join(render_official_alert_notice_plain(
        [(_alert(3), ["3", "4", "5", "Ziel"])], tz=ZoneInfo("UTC"),
    ))
    assert "Region: Haute-Corse — Segment 3–5, 🏁 Ziel" in out, out


# ---------------------------------------------------------------------------
# dedupe_official_alerts() vereinigt Segment-ID-Mengen gruppierter Alerts
# ---------------------------------------------------------------------------


def test_dedupe_merges_segment_ids_of_grouped_alerts():
    """Given zwei Rohalerts derselben Gruppe (region_label, hazard) aus
    unterschiedlichen Segmenten (3 bzw. 5) / When dedupe_official_alerts
    laeuft / Then traegt der eine verbleibende Eintrag BEIDE Segment-IDs und
    das hoechste Level."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    tagged = [
        (_alert(2), ["3"]),
        (_alert(4), ["5"]),
    ]
    result = dedupe_official_alerts(tagged)

    assert len(result) == 1, (
        f"gleiche (region_label,hazard) muss zu 1 Eintrag kollabieren, "
        f"bekommen {len(result)}"
    )
    alert, segment_ids = result[0]
    assert alert.level == 4, "hoechstes Level muss erhalten bleiben"
    assert set(segment_ids) == {"3", "5"}, (
        f"Segment-IDs beider Rohalerts muessen vereinigt werden, "
        f"bekommen {segment_ids}"
    )
