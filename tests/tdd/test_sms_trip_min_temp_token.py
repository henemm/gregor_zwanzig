"""SMS: Tiefsttemperatur unterwegs (kaelteste Gehzeit-Stunde) als eigener Wert.

Spec:  docs/specs/modules/trip_min_temp_and_felt_shortforms.md (AC-1, AC-2, AC-6)
Issue: #1410 — Epic #1372, Scheibe 2 zu #1357 S4a

TDD RED. Nachweis ueber den echten Renderer
``SMSTripFormatter.format_sms()`` mit echten Segment-/Nacht-Zeitreihen
(``tests/tdd/_min_temp_felt_fixtures.py``). Keine Mocks, keine
Dateiinhalt-Pruefungen — gelesen wird ausschliesslich die gerenderte Zeile.
"""
from __future__ import annotations

import pytest

from output.renderers.sms_trip import SMSTripFormatter

from tests.tdd import _min_temp_felt_fixtures as F


def _sms(report_type: str, *, max_length: int = 160) -> str:
    """Eine echt gerenderte Trip-SMS aus denselben Rohdaten."""
    return SMSTripFormatter().format_sms(
        [F.segment()],
        max_length=max_length,
        stage_name=F.STAGE_NAME,
        report_type=report_type,
        tz=F.TZ,
        night_weather=F.night_weather(),
    )


class TestAC1MorningShowsHikingLow:
    """AC-1: Given ein Trip ohne Einschraenkung der gefuehlten Temperatur /
    When das Morgenbriefing als SMS versendet wird / Then enthaelt die SMS
    eine eigenstaendige Tiefsttemperatur-Angabe fuer die kaelteste erwartete
    Stunde unterwegs (3 °C), obwohl das Morgenbriefing heute dort gar keinen
    Tiefstwert zeigt."""

    def test_morning_shows_hiking_low(self):
        sms = _sms("morning")

        hiking_low = F.sms_token_value(sms, "K")
        assert hiking_low is not None, (
            "Die Morgen-SMS zeigt keine Tiefsttemperatur unterwegs — der Wert "
            "der kaeltesten Gehzeit-Stunde fehlt komplett.\n"
            f"SMS: {sms}"
        )
        assert hiking_low == str(int(F.HIKE_MIN_C)), (
            f"Die Tiefsttemperatur unterwegs zeigt {hiking_low} statt "
            f"{int(F.HIKE_MIN_C)} (kaelteste Gehzeit-Stunde, lokal "
            f"{F.COLD_HOUR}:00).\nSMS: {sms}"
        )

        # Der Hoechstwert bleibt unveraendert danebenstehen.
        assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
            f"Der Tages-Hoechstwert hat sich veraendert.\nSMS: {sms}"
        )

        # night_temp_evening_only.md DEC-1 bleibt unberuehrt: die
        # Nacht-Tiefsttemperatur am Schlafplatz erscheint morgens NICHT.
        assert F.sms_token_value(sms, "N") is None, (
            "Die Morgen-SMS zeigt eine Nacht-Tiefsttemperatur am Schlafplatz "
            "— DEC-1 aus night_temp_evening_only.md wird damit umgekehrt.\n"
            f"SMS: {sms}"
        )


class TestAC2EveningShowsBothHikingAndNightLow:
    """AC-2: Given ein Trip mit Ankunft am Etappenziel / When das
    Abendbriefing als SMS versendet wird / Then enthaelt die SMS ZWEI
    unterscheidbare Tiefstwerte — die kaelteste Stunde unterwegs (3 °C) UND
    die Nacht-Tiefsttemperatur am Schlafplatz (11 °C) —, und der Nachtwert
    behaelt exakt seine bisherige Bedeutung."""

    def test_evening_shows_both_hiking_and_night_low(self):
        sms = _sms("evening")

        night_low = F.sms_token_value(sms, "N")
        hiking_low = F.sms_token_value(sms, "K")

        assert night_low == str(int(F.NIGHT_MIN_C)), (
            f"Die Nacht-Tiefsttemperatur am Schlafplatz zeigt {night_low} "
            f"statt {int(F.NIGHT_MIN_C)} — ihre Bedeutung darf sich durch den "
            f"neuen Wert nicht aendern (DEC-1).\nSMS: {sms}"
        )
        assert hiking_low is not None, (
            "Die Abend-SMS zeigt neben der Nacht-Tiefsttemperatur KEINEN "
            "zweiten Tiefstwert fuer die kaelteste Stunde unterwegs.\n"
            f"SMS: {sms}"
        )
        assert hiking_low == str(int(F.HIKE_MIN_C)), (
            f"Die Tiefsttemperatur unterwegs zeigt {hiking_low} statt "
            f"{int(F.HIKE_MIN_C)} — abends darf sie NICHT vom Nachtwert "
            f"ueberschrieben werden.\nSMS: {sms}"
        )
        assert hiking_low != night_low, (
            "Beide Tiefstwerte zeigen dieselbe Zahl — sie sind damit nicht "
            f"unterscheidbar.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
            f"Der Tages-Hoechstwert hat sich veraendert.\nSMS: {sms}"
        )


class TestAC6TruncationDropsFeltBeforeMeasured:
    """AC-6: Given eine SMS-Zeile mit gemessenen UND gefuehlten Zusatzwerten,
    die ueber der Laengengrenze liegt / When die SMS gekuerzt wird / Then
    verschwinden die gefuehlten Temperaturwerte zuerst — die gemessenen
    (kaelteste Stunde unterwegs, Nacht-Tiefst, Hoechst) bleiben so lange wie
    moeglich erhalten."""

    _MEASURED = ("N", "K", "D")
    _FELT = ("FN", "FK", "FD")

    def test_truncation_drops_felt_before_measured(self):
        full = _sms("evening", max_length=1000)

        missing = [s for s in self._MEASURED + self._FELT
                   if F.sms_token_value(full, s) is None]
        assert not missing, (
            "Die ungekuerzte Abend-SMS enthaelt nicht alle sechs "
            f"Temperaturwerte — es fehlen: {missing}. Ohne sie ist die "
            "Kuerzungsreihenfolge nicht pruefbar.\n"
            f"SMS: {full}"
        )

        seen_felt_gone_measured_intact = False
        for max_length in range(len(full), 10, -1):
            try:
                line = _sms("evening", max_length=max_length)
            except ValueError:
                # Unterhalb dieser Grenze ist die Zeile nicht mehr kuerzbar.
                break
            assert len(line) <= max_length, (
                f"Gekuerzte SMS ist mit {len(line)} Zeichen laenger als die "
                f"Grenze {max_length}.\nSMS: {line}"
            )

            felt_left = {s for s in self._FELT
                         if F.sms_token_value(line, s) is not None}
            measured_left = {s for s in self._MEASURED
                             if F.sms_token_value(line, s) is not None}

            if len(measured_left) < len(self._MEASURED):
                assert not felt_left, (
                    "Beim Kuerzen ist ein gemessener Temperaturwert "
                    f"weggefallen ({sorted(set(self._MEASURED) - measured_left)}), "
                    f"waehrend gefuehlte Werte {sorted(felt_left)} noch "
                    "dastehen — die gefuehlten Werte muessen zuerst "
                    f"verschwinden.\nGrenze {max_length}: {line}"
                )
            if not felt_left and len(measured_left) == len(self._MEASURED):
                seen_felt_gone_measured_intact = True

        assert seen_felt_gone_measured_intact, (
            "Es gibt keine Laengengrenze, bei der alle gefuehlten Werte "
            "gefallen sind und alle drei gemessenen noch stehen — die "
            "gefuehlten Werte fallen also nicht zuerst.\n"
            f"Volle SMS: {full}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
