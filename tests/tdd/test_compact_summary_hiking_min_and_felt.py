"""E-Mail-Kurzzusammenfassung: Morgen-Spanne + gefuehlte Temperatur im Satz.

Spec:  docs/specs/modules/trip_min_temp_and_felt_shortforms.md (AC-7, AC-8, AC-9)
Issue: #1410 — Epic #1372, Scheibe 2 zu #1357 S4a

TDD RED. Nachweis ueber den echten Renderer
``CompactSummaryFormatter.format_stage_summary()`` mit echten Segment-/
Nacht-Zeitreihen. Gelesen wird ausschliesslich der fertige Satz. Keine
Mocks, keine Dateiinhalt-Pruefungen, kein Netz, keine Mail.
"""
from __future__ import annotations

import pytest

from output.renderers.compact_summary import CompactSummaryFormatter

from tests.tdd import _min_temp_felt_fixtures as F

_DASH = "–"  # En-Dash, wie in der bestehenden Abend-Spanne


def _summary(report_type: str, *, felt_enabled: bool = False, with_night: bool = True) -> str:
    # #1484: die Abend-Untergrenze (Nachtwert) braucht die eigene Nachtgroesse.
    # #1660 Scheibe A: dieselbe Eigenstaendigkeit jetzt auch auf der
    # gefuehlten Seite ("wind_chill_night") — ohne expliziten Eintrag bleibt
    # die gefuehlte Abend-Untergrenze beim Gehzeit-Tiefstwert (F.dc() baut
    # MetricConfig direkt, ohne die Bestandsableitung des Ladepfads).
    metrics = (
        ("temperature", "temperature_night", "wind_chill", "wind_chill_night")
        if felt_enabled else ("temperature", "temperature_night")
    )
    return CompactSummaryFormatter().format_stage_summary(
        [F.segment()],
        F.STAGE_NAME,
        F.dc(*metrics),
        F.night_weather() if with_night else None,
        tz=F.TZ,
        report_type=report_type,
    )


class TestAC7MorningShowsTemperatureRange:
    """AC-7: Given ein Trip mit Morgenbriefing / When die
    E-Mail-Kurzzusammenfassung gerendert wird / Then zeigt der
    Temperatur-Teil des Satzes eine Spanne (3–20 °C) statt wie bisher nur des
    Hoechstwerts (20 °C)."""

    def test_morning_shows_temperature_range(self):
        text = _summary("morning")
        parts = F.compact_parts(text)

        assert parts, f"Die Kurzzusammenfassung ist leer.\nSatz: {text!r}"
        temp_part = parts[0]
        expected = f"{int(F.HIKE_MIN_C)}{_DASH}{int(F.HIKE_MAX_C)}°C"
        assert temp_part == expected, (
            f"Der Temperatur-Teil des Morgensatzes lautet {temp_part!r} statt "
            f"{expected!r} — morgens fehlt die Tiefsttemperatur unterwegs, es "
            f"steht nur der Hoechstwert da.\nSatz: {text!r}"
        )


class TestAC8FeltRangeAppearsNextToMeasured:
    """AC-8: Given ein Trip mit aktivierter „Gefuehlte Temperatur" / When die
    E-Mail-Kurzzusammenfassung (Morgen ODER Abend) gerendert wird / Then
    enthaelt der Satz direkt neben dem gemessenen Temperaturteil einen
    gefuehlten Temperaturteil mit Praefix „gef." und derselben
    Spannen-Darstellung."""

    _EXPECTED = {
        # report_type: (gemessen, gefuehlt)
        "morning": (
            f"{int(F.HIKE_MIN_C)}{_DASH}{int(F.HIKE_MAX_C)}°C",
            f"gef. {int(F.FELT_HIKE_MIN_C)}{_DASH}{int(F.FELT_HIKE_MAX_C)}°C",
        ),
        "evening": (
            f"{int(F.NIGHT_MIN_C)}{_DASH}{int(F.HIKE_MAX_C)}°C",
            f"gef. {int(F.FELT_NIGHT_MIN_C)}{_DASH}{int(F.FELT_HIKE_MAX_C)}°C",
        ),
    }

    def test_felt_range_appears_next_to_measured(self):
        for report_type, (measured, felt) in self._EXPECTED.items():
            text = _summary(report_type, felt_enabled=True)
            parts = F.compact_parts(text)

            assert len(parts) >= 2, (
                f"Der {report_type}-Satz enthaelt nur {len(parts)} Teil(e) — "
                "der gefuehlte Temperaturteil fehlt komplett.\n"
                f"Satz: {text!r}"
            )
            assert parts[0] == measured, (
                f"[{report_type}] Der gemessene Temperaturteil lautet "
                f"{parts[0]!r} statt {measured!r}.\nSatz: {text!r}"
            )
            assert parts[1] == felt, (
                f"[{report_type}] Direkt neben dem gemessenen Temperaturteil "
                f"steht {parts[1]!r} statt des gefuehlten Teils {felt!r}.\n"
                f"Satz: {text!r}"
            )


class TestAC9FeltEveningUsesNightValueWithFailsoftFallback:
    """AC-9: Given ein Trip mit aktivierter „Gefuehlte Temperatur" und
    Ankunft am Etappenziel / When die abendliche E-Mail-Kurzzusammenfassung
    gerendert wird / Then basiert der gefuehlte Tiefstwert auf der echten
    gefuehlten Nachttemperatur am Ziel (9 °C); fehlen Nachtdaten, faellt er
    fail-soft auf die gefuehlte Tiefsttemperatur unterwegs (1 °C) zurueck,
    ohne dass der Satz leer bleibt oder abstuerzt."""

    def test_felt_evening_uses_night_value_with_failsoft_fallback(self):
        with_night = _summary("evening", felt_enabled=True, with_night=True)
        parts = F.compact_parts(with_night)
        assert len(parts) >= 2, (
            "Der Abendsatz enthaelt keinen gefuehlten Temperaturteil.\n"
            f"Satz: {with_night!r}"
        )
        expected_night = (
            f"gef. {int(F.FELT_NIGHT_MIN_C)}{_DASH}{int(F.FELT_HIKE_MAX_C)}°C"
        )
        assert parts[1] == expected_night, (
            f"Der gefuehlte Abendteil lautet {parts[1]!r} statt "
            f"{expected_night!r} — die Untergrenze muss die echte gefuehlte "
            f"Nachttemperatur am Ziel ({int(F.FELT_NIGHT_MIN_C)} °C) sein, "
            f"nicht die gefuehlte Tiefsttemperatur unterwegs "
            f"({int(F.FELT_HIKE_MIN_C)} °C).\nSatz: {with_night!r}"
        )

        without_night = _summary("evening", felt_enabled=True, with_night=False)
        assert without_night.strip(), (
            "Ohne Nachtdaten liefert die Kurzzusammenfassung gar keinen Satz "
            "mehr (Absturz/Leerlauf statt fail-soft)."
        )
        fallback_parts = F.compact_parts(without_night)
        assert len(fallback_parts) >= 2, (
            "Ohne Nachtdaten faellt der gefuehlte Temperaturteil ersatzlos "
            f"weg, statt fail-soft zurueckzufallen.\nSatz: {without_night!r}"
        )
        expected_fallback = (
            f"gef. {int(F.FELT_HIKE_MIN_C)}{_DASH}{int(F.FELT_HIKE_MAX_C)}°C"
        )
        assert fallback_parts[1] == expected_fallback, (
            f"Der fail-soft-Rueckfall lautet {fallback_parts[1]!r} statt "
            f"{expected_fallback!r} (gefuehlte Tiefsttemperatur unterwegs).\n"
            f"Satz: {without_night!r}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
