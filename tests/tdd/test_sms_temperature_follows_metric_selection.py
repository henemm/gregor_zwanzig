"""SMS: die gemessene Temperatur (N/K/D) folgt der Metrik-Auswahl des Trips.

Issue: #1415 — abgewaehlte Temperatur muss aus der Trip-SMS verschwinden.

PO-Regel (2026-08-03), einheitlich fuer alle Kuerzel:

  * geprueft, nichts ueber der Schwelle -> Null-Form (``R-``)
  * Wert nicht abrufbar / Datenluecke   -> ``R?``
  * Metrik **abgewaehlt**               -> Kuerzel entfaellt vollstaendig

``FN``/``FK``/``FD`` (gefuehlte Temperatur) halten sich seit #1410 daran,
``N``/``K``/``D`` (gemessene Temperatur) bisher nicht — sie erschienen
unbedingt. Beleg des PO aus einer echt zugestellten Nachricht (Trip KHW 403,
2026-07-29, Temperatur AUS, gefuehlte Temperatur AN)::

    E3: K13 D16 FK13 FD16 R12.2@20 ...

Gemessen wird der echte Weg von der Nutzereinstellung bis zur fertigen SMS
(``TripReportFormatter.format_email()`` -> ``report.sms_text``) — nur dort
entsteht die Abhaengigkeit der Token von der Trip-Einstellung. Keine Mocks,
kein Netz, keine Dateiinhalt-Pruefungen.
"""
from __future__ import annotations

import dataclasses

import pytest

from app.models import ThunderLevel
from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

_MEASURED = ("N", "K", "D")
_FELT = ("FN", "FK", "FD")
# Issue #1728 Scheibe 1: „die Temperatur ist gewaehlt" heisst seither, dass
# auch ihre Tagesrichtungen gewaehlt sind -- sie tragen K/D. Die Zusicherung
# dieser Suite (die Kuerzel folgen der Auswahl) ist unveraendert, nur die
# Auswahl besteht jetzt aus drei statt einer Zeile.
_TEMP_GEWAEHLT = ("temperature", "temperature_day_low", "temperature_day_high")
_FELT_GEWAEHLT = ("wind_chill", "wind_chill_day_low", "wind_chill_day_high")
# Kuerzel, die schon heute korrekt der Auswahl folgen (Nichtregression).
_THRESHOLD_SYMBOLS = ("R", "PR", "W", "G", "TH:")


def _sms(report_type: str, *metric_ids: str, segment=None, night=None) -> str:
    """Echt gerenderte Trip-SMS mit genau den genannten aktiven Metriken."""
    report = TripReportFormatter().format_email(
        [segment if segment is not None else F.segment()],
        trip_name="Issue1415",
        report_type=report_type,
        night_weather=night if night is not None else F.night_weather(),
        display_config=F.dc(*metric_ids),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )
    return report.sms_text


def _token_present(sms: str, symbol: str) -> bool:
    """Kommt das Kuerzel in irgendeiner Wertform vor?

    ``F.sms_token_value()`` erkennt nur die Temperatur-Kurzform (``K3``,
    ``R-``); Schwellwert-Token tragen ganze Verlaeufe (``R0.5@5(8.4@11)``).
    Der Test auf „nicht-Buchstabe danach" schliesst Praefix-Verwechslungen aus
    (``R`` trifft nicht ``RH...``, ``W`` nicht ``WC12``).
    """
    for token in F.sms_body(sms).split(" "):
        rest = token[len(symbol):]
        if token.startswith(symbol) and not rest[:1].isalpha():
            return True
    return False


def _calm_points(points):
    """Stundenpunkte ohne Regen/Wind/Boeen/Gewitter ueber der Schwelle."""
    return [
        dataclasses.replace(
            dp, precip_1h_mm=0.0, pop_pct=0, wind10m_kmh=5.0, gust_kmh=8.0,
            thunder_level=ThunderLevel.NONE,
        )
        for dp in points
    ]


def _calm_segment():
    """Dasselbe Segment, aber ruhig.

    Grundlage fuer den Null-Form-Nachweis: eine GEWAEHLTE Metrik ohne
    Ueberschreitung muss ``R-`` zeigen und darf nicht verschwinden.
    """
    seg = F.segment()
    return dataclasses.replace(
        seg,
        timeseries=dataclasses.replace(
            seg.timeseries, data=_calm_points(seg.timeseries.data)),
        aggregated=dataclasses.replace(
            seg.aggregated, precip_sum_mm=0.0, pop_max_pct=0,
            wind_max_kmh=5.0, gust_max_kmh=8.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
    )


def _templess_segment():
    """Segment MIT Zeitreihe, aber ohne jede Temperaturmessung.

    Echte Datenluecke auf BEIDEN Wegen: die Gehzeit-Fensterung findet kein
    ``t2m_c`` (``hiking_field_min_max`` -> ``None``) UND der Rueckfall auf das
    Etappen-Aggregat (``temp_min_c``/``temp_max_c``) traegt ebenfalls nichts.
    Nur so entsteht der Zustand „Metrik gewaehlt, aber kein Wert" — bei
    gefuelltem Aggregat wuerde der Fail-soft-Pfad in
    ``sms_trip._segments_to_normalized_forecast`` ihn wieder auffuellen.
    """
    seg = F.segment()
    return dataclasses.replace(
        seg,
        timeseries=dataclasses.replace(
            seg.timeseries,
            data=[dataclasses.replace(dp, t2m_c=None)
                  for dp in seg.timeseries.data],
        ),
        aggregated=dataclasses.replace(
            seg.aggregated, temp_min_c=None, temp_max_c=None, temp_avg_c=None,
        ),
    )


def _templess_night():
    """Nacht-Zeitreihe ohne Temperaturmessung — sonst haette ``N`` einen Wert."""
    night = F.night_weather()
    return dataclasses.replace(
        night,
        data=[dataclasses.replace(dp, t2m_c=None) for dp in night.data],
    )


def _calm_night():
    """Die Nacht-Zeitreihe ebenso ruhig — sie fliesst ab der Ankunftsstunde
    in dasselbe Tagesfenster ein (``build_day_window_points``)."""
    night = F.night_weather()
    return dataclasses.replace(night, data=_calm_points(night.data))


class TestMeasuredTemperatureFollowsSelection:
    """Der PO-Fall: Temperatur abgewaehlt, gefuehlte Temperatur an."""

    def test_measured_tokens_absent_when_temperature_deselected(self):
        for report_type in ("morning", "evening"):
            sms = _sms(report_type, *_FELT_GEWAEHLT, "precipitation")

            # Vorbedingung: die gefuehlten Werte sind da — die Abwesenheit der
            # gemessenen ist damit Folge der Abwahl, nicht Folge fehlender
            # Daten oder einer gekuerzten Zeile.
            felt = F.present_symbols(sms, _FELT)
            assert "FK" in felt and "FD" in felt, (
                f"[{report_type}] Die gefuehlten Temperaturwerte fehlen "
                "bereits — der Nachweis ueber die gemessenen waere damit "
                f"nicht aussagekraeftig.\nSMS: {sms}"
            )

            leaked = F.present_symbols(sms, _MEASURED)
            assert not leaked, (
                f"[{report_type}] Die SMS zeigt die gemessenen "
                f"Temperaturwerte {sorted(leaked)}, obwohl der Nutzer die "
                f"Metrik „Temperatur“ abgewaehlt hat.\nSMS: {sms}"
            )

    def test_measured_tokens_present_when_temperature_selected(self):
        """Nichtregression: gewaehlt -> K/D wie bisher. ``N`` gehoert seit
        #1484 zur eigenen Groesse "temperature_night" (eigene Suite:
        test_night_temp_own_metric_selection.py)."""
        for report_type in ("morning", "evening"):
            sms = _sms(report_type, *_TEMP_GEWAEHLT, "precipitation")

            expected = {"K", "D"}
            assert F.present_symbols(sms, _MEASURED) == expected, (
                f"[{report_type}] Erwartet {sorted(expected)} bei aktivierter "
                f"Temperatur.\nSMS: {sms}"
            )
            assert F.sms_token_value(sms, "K") == str(int(F.HIKE_MIN_C)), (
                f"[{report_type}] Tiefsttemperatur unterwegs falsch.\nSMS: {sms}"
            )
            assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
                f"[{report_type}] Hoechsttemperatur falsch.\nSMS: {sms}"
            )

    def test_no_temperature_tokens_at_all_when_both_deselected(self):
        for report_type in ("morning", "evening"):
            sms = _sms(report_type, "precipitation", "wind")

            leaked = F.present_symbols(sms, _MEASURED + _FELT)
            assert not leaked, (
                f"[{report_type}] Die SMS zeigt Temperaturwerte "
                f"{sorted(leaked)}, obwohl weder „Temperatur“ noch "
                f"„Gefuehlte Temperatur“ gewaehlt sind.\nSMS: {sms}"
            )
            # Gegenprobe, dass ueberhaupt eine Zeile mit Inhalt entsteht.
            assert _token_present(sms, "R"), (
                f"[{report_type}] Der gewaehlte Regen-Token fehlt — die "
                f"Zeile ist offenbar leer oder gekuerzt.\nSMS: {sms}"
            )


class TestSelectedButNoValueKeepsNullForm:
    """Die zweite Haelfte der PO-Regel: „gewaehlt, aber kein Wert" ist NICHT
    dasselbe wie „abgewaehlt".

    Ohne diesen Nachweis waere der Fix oben trivial erfuellbar, indem
    ``N``/``K``/``D`` bei fehlendem Wert einfach verschwinden — die SMS wuerde
    dann verschweigen, dass eine gewaehlte Groesse nicht geliefert werden
    konnte (Adversary-Befund F001 zu #1415).
    """

    def test_selected_temperature_without_data_shows_null_form(self):
        for report_type in ("morning", "evening"):
            sms = _sms(
                report_type, *_TEMP_GEWAEHLT, "precipitation",
                segment=_templess_segment(), night=_templess_night(),
            )

            expected = {"K", "D"}  # N: eigene Groesse seit #1484
            present = F.present_symbols(sms, _MEASURED)
            assert present == expected, (
                f"[{report_type}] Erwartet {sorted(expected)} als Null-Form, "
                f"gefunden {sorted(present)}. Die Metrik „Temperatur“ IST "
                "gewaehlt — fehlende Daten muessen als „K-“/„D-“ sichtbar "
                f"bleiben und duerfen nicht wie eine Abwahl aussehen.\n"
                f"SMS: {sms}"
            )
            for sym in expected:
                assert F.sms_token_value(sms, sym) == "-", (
                    f"[{report_type}] „{sym}“ zeigt "
                    f"{F.sms_token_value(sms, sym)!r} statt der Null-Form "
                    f"„-“.\nSMS: {sms}"
                )

    def test_null_form_and_deselection_are_distinguishable(self):
        """Beide Zustaende am selben Datenstand — sie MUESSEN sich
        unterscheiden, sonst ist die Regel nicht umgesetzt, sondern nur
        zufaellig erfuellt."""
        selected = _sms(
            "evening", *_TEMP_GEWAEHLT, "precipitation",
            segment=_templess_segment(), night=_templess_night(),
        )
        deselected = _sms(
            "evening", "precipitation",
            segment=_templess_segment(), night=_templess_night(),
        )

        assert F.present_symbols(selected, _MEASURED) == {"K", "D"}, (
            f"Gewaehlt ohne Wert -> Null-Formen erwartet (N: eigene Groesse "
            f"seit #1484).\nSMS: {selected}"
        )
        assert not F.present_symbols(deselected, _MEASURED), (
            f"Abgewaehlt -> gar keine Temperatur-Kuerzel erwartet.\n"
            f"SMS: {deselected}"
        )


class TestNullFormsUnaffected:
    """Nichtregression fuer R/PR/W/G/TH: — die Regel gilt gleich fuer alle."""

    def test_selected_metrics_without_exceedance_keep_null_form(self):
        sms = _sms(
            "morning", *_TEMP_GEWAEHLT, "precipitation", "rain_probability",
            "wind", "gust", "thunder",
            segment=_calm_segment(), night=_calm_night(),
        )

        for sym in _THRESHOLD_SYMBOLS:
            assert F.sms_token_value(sms, sym) == "-", (
                f"Die gewaehlte Metrik zu „{sym}“ zeigt keine Null-Form "
                f"— gewaehlt ohne Ueberschreitung muss „{sym}-“ "
                f"erscheinen.\nSMS: {sms}"
            )
        # Und die gewaehlte Temperatur steht weiterhin daneben.
        assert F.present_symbols(sms, _MEASURED) == {"K", "D"}, (
            f"Die gewaehlte Temperatur ist verschwunden.\nSMS: {sms}"
        )

    def test_deselected_threshold_metrics_stay_absent(self):
        sms = _sms("morning", *_TEMP_GEWAEHLT)

        for sym in _THRESHOLD_SYMBOLS:
            # `_token_present` statt `sms_token_value`: ein voller Verlauf
            # ('R0.5@5(8.4@11)') wuerde sonst als „nicht vorhanden" durchgehen.
            assert not _token_present(sms, sym), (
                f"Die SMS zeigt „{sym}“, obwohl die Metrik nicht "
                f"gewaehlt ist.\nSMS: {sms}"
            )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
