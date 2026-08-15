"""SMS: gefuehlte Temperatur (Tiefst unterwegs, Hoechst, Nacht am Ziel).

Spec:  docs/specs/modules/trip_min_temp_and_felt_shortforms.md (AC-3, AC-4, AC-5)
Issue: #1410 — Epic #1372, Scheibe 2 zu #1357 S4a

TDD RED. Einstiegspunkt ist ``TripReportFormatter.format_email()`` — nur
dort entsteht die Abhaengigkeit der SMS-Token von der Trip-Einstellung
„Gefuehlte Temperatur" (Bug-#944-Gating, ``trip_report.py``). Gemessen wird
also der echte Weg von der Nutzereinstellung bis zur fertigen SMS, nicht
eine Hilfsfunktion mit vorgefertigten Daten. Keine Mocks, keine
Dateiinhalt-Pruefungen.
"""
from __future__ import annotations

import pytest

from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

_MEASURED = ("N", "K", "D")
_FELT = ("FN", "FK", "FD")


def _sms(report_type: str, *, felt_enabled: bool) -> str:
    """Echt gerenderte Trip-SMS — mit bzw. ohne aktivierte gefuehlte Temperatur."""
    # #1484: die Nachtgroesse ist eigenstaendig waehlbar — hier aktiv, damit
    # die N-Assertions (Parallelitaet gemessen/gefuehlt) aussagekraeftig bleiben.
    # #1660 Scheibe A: dieselbe Eigenstaendigkeit jetzt auch auf der
    # gefuehlten Seite ("wind_chill_night") — ohne expliziten Eintrag bleibt
    # FN abgewaehlt (F.dc() baut MetricConfig direkt, ohne die
    # Bestandsableitung des Ladepfads).
    # #1728 Scheibe 1: K/D bzw. FK/FD haengen an je eigenen Groessen
    # (temperature_day_low/_high, wind_chill_day_low/_high) — ohne sie
    # erschiene keiner der Tages-Token, und die Abwesenheits-Assertion bei
    # abgewaehlter Groesse waere nicht mehr aussagekraeftig.
    _measured = ("temperature", "temperature_day_low", "temperature_day_high",
                 "temperature_night")
    _felt = ("wind_chill", "wind_chill_day_low", "wind_chill_day_high",
             "wind_chill_night")
    metrics = _measured + _felt if felt_enabled else _measured
    report = TripReportFormatter().format_email(
        [F.segment()],
        trip_name="Issue1410",
        report_type=report_type,
        night_weather=F.night_weather(),
        display_config=F.dc(*metrics),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )
    return report.sms_text


class TestAC3FeltHikingLowAndHighPresent:
    """AC-3: Given ein Trip mit aktivierter „Gefuehlte Temperatur" / When
    Morgen- ODER Abendbriefing als SMS versendet wird / Then enthaelt die SMS
    zusaetzlich zu den gemessenen Werten eine gefuehlte Tiefst-unterwegs-
    (1 °C) UND eine gefuehlte Hoechsttemperatur (18 °C)."""

    def test_felt_hiking_low_and_high_present(self):
        for report_type in ("morning", "evening"):
            sms = _sms(report_type, felt_enabled=True)

            felt_low = F.sms_token_value(sms, "FK")
            felt_high = F.sms_token_value(sms, "FD")

            assert felt_low is not None, (
                f"Die {report_type}-SMS zeigt keine gefuehlte "
                "Tiefsttemperatur unterwegs, obwohl die gefuehlte Temperatur "
                f"im Trip aktiviert ist.\nSMS: {sms}"
            )
            assert felt_high is not None, (
                f"Die {report_type}-SMS zeigt keine gefuehlte "
                "Hoechsttemperatur, obwohl die gefuehlte Temperatur im Trip "
                f"aktiviert ist.\nSMS: {sms}"
            )
            assert felt_low == str(int(F.FELT_HIKE_MIN_C)), (
                f"[{report_type}] Gefuehlte Tiefsttemperatur unterwegs zeigt "
                f"{felt_low} statt {int(F.FELT_HIKE_MIN_C)} — sie muss aus "
                "demselben Gehzeit-Fenster stammen wie die gemessene.\n"
                f"SMS: {sms}"
            )
            assert felt_high == str(int(F.FELT_HIKE_MAX_C)), (
                f"[{report_type}] Gefuehlte Hoechsttemperatur zeigt "
                f"{felt_high} statt {int(F.FELT_HIKE_MAX_C)}.\nSMS: {sms}"
            )
            # Die gemessenen Werte bleiben unveraendert daneben stehen.
            assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
                f"[{report_type}] Der gemessene Tages-Hoechstwert hat sich "
                f"veraendert.\nSMS: {sms}"
            )


class TestAC4FeltNightLowUsesDestinationNightValue:
    """AC-4: Given ein Trip mit aktivierter „Gefuehlte Temperatur" und
    Ankunft am Etappenziel / When das Abendbriefing als SMS versendet wird /
    Then zeigt der gefuehlte Nachtwert die echte gefuehlte Nachttemperatur am
    Ziel (9 °C) — nicht die gefuehlte Tiefsttemperatur unterwegs (1 °C)."""

    def test_felt_night_low_uses_destination_night_value(self):
        sms = _sms("evening", felt_enabled=True)

        felt_night = F.sms_token_value(sms, "FN")
        assert felt_night is not None, (
            "Die Abend-SMS zeigt keine gefuehlte Nacht-Tiefsttemperatur am "
            f"Ziel.\nSMS: {sms}"
        )
        assert felt_night == str(int(F.FELT_NIGHT_MIN_C)), (
            f"Die gefuehlte Nacht-Tiefsttemperatur zeigt {felt_night} statt "
            f"{int(F.FELT_NIGHT_MIN_C)} (echter Tiefpunkt der Nacht am Ziel). "
            f"{int(F.FELT_HIKE_MIN_C)} waere die gefuehlte Tiefsttemperatur "
            f"unterwegs — die falsche Quelle.\nSMS: {sms}"
        )
        assert felt_night != F.sms_token_value(sms, "FK"), (
            "Gefuehlter Nachtwert und gefuehlte Tiefsttemperatur unterwegs "
            f"sind identisch — sie stammen offenbar aus derselben Quelle.\n"
            f"SMS: {sms}"
        )
        # Parallelitaet zur gemessenen Regel (night_temp_evening_only.md DEC-1):
        # der gemessene Nachtwert bleibt unveraendert.
        assert F.sms_token_value(sms, "N") == str(int(F.NIGHT_MIN_C)), (
            f"Die gemessene Nacht-Tiefsttemperatur hat sich veraendert.\n"
            f"SMS: {sms}"
        )


class TestAC5FeltTokensAbsentWhenMetricDisabled:
    """AC-5: Given ein Trip, bei dem der Nutzer „Gefuehlte Temperatur" NICHT
    aktiviert hat / When Morgen- oder Abendbriefing als SMS versendet wird /
    Then enthaelt die SMS KEINE gefuehlten Temperaturangaben — nur die
    gemessenen Werte erscheinen."""

    def test_felt_tokens_absent_when_metric_disabled(self):
        for report_type in ("morning", "evening"):
            with_felt = _sms(report_type, felt_enabled=True)
            without_felt = _sms(report_type, felt_enabled=False)

            # Ohne diese Vorbedingung waere die Abwesenheit inhaltsleer: sie
            # muss FOLGE der Einstellung sein, nicht Folge fehlender Funktion.
            assert F.present_symbols(with_felt, _FELT), (
                "Bei aktivierter gefuehlter Temperatur erscheint kein "
                f"einziger gefuehlter Wert in der {report_type}-SMS — die "
                "Abwesenheit bei deaktivierter Metrik waere damit nicht "
                f"aussagekraeftig.\nSMS: {with_felt}"
            )

            leaked = F.present_symbols(without_felt, _FELT)
            assert not leaked, (
                f"Die {report_type}-SMS zeigt gefuehlte Temperaturwerte "
                f"{sorted(leaked)}, obwohl der Nutzer die gefuehlte "
                f"Temperatur nicht aktiviert hat.\nSMS: {without_felt}"
            )

            # Die gemessenen Werte bleiben davon unberuehrt.
            expected = {"K", "D"} | ({"N"} if report_type == "evening" else set())
            assert F.present_symbols(without_felt, _MEASURED) == expected, (
                f"[{report_type}] Die gemessenen Temperaturwerte haben sich "
                "veraendert, obwohl nur die gefuehlte Temperatur abgeschaltet "
                f"wurde.\nSMS: {without_felt}"
            )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
