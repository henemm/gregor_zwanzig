"""Trip-Briefing- und amtlicher-Alarm-SMS bleiben im GSM-7-Zeichensatz (#1533 S4).

Pendant zu ``tests/tdd/test_compare_sms_gsm7_charset.py`` (#1362 S5b) fuer die
zwei bisher UNBEWACHTEN SMS-Pfade: ``sms_trip.py::format_sms`` und
``official_alerts.py::render_official_alert_sms``. Die Zeichensatz-Definition
kommt aus ``tests/tdd/_gsm7_charset.py`` -- eine zweite eigene Tabelle koennte
gruen sein und trotzdem eine andere Welt pruefen.

AC-1/AC-2 sind Regressionsschutz fuer heute korrekten Code. Der bei der
Spec-Erstellung vermutete und in der RED-Phase bestaetigte Fund (Zeichen der
GSM-7-Extension-Tabelle im Trip-Namen ueberleben ``_ascii()``) hat ein eigenes
Issue: **#1796**.

KEINE Mocks: echte ``SegmentWeatherData``/``OfficialAlert``/
``OfficialAlertNotice``-Objekte, echte Renderer-Aufrufe, kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    PrecipType,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from output.renderers.alert.official_alerts import (
    OfficialAlertNotice,
    render_official_alert_sms,
)
from output.renderers.sms_trip import SMSTripFormatter, _sms_stage_prefix
from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS
from services.official_alerts.models import OfficialAlert
from tests.tdd._gsm7_charset import GSM7_EXTENDED_TWO_SEPTET_CHARS, assert_gsm7_clean

_YEAR, _MONTH, _DAY = 2026, 8, 12
_UTC = ZoneInfo("UTC")


def _dp(hour: int, *, day: int = _DAY) -> ForecastDataPoint:
    """Stundenpunkt, in dem JEDE vom SMS-Pfad gelesene Groesse gesetzt ist --
    sonst faellt das zugehoerige Token stillschweigend aus und wird nie
    geprueft."""
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=8.0 + hour * 0.5, wind_chill_c=4.0 + hour * 0.5,
        wind10m_kmh=32.0, wind_direction_deg=225, gust_kmh=58.0,
        precip_1h_mm=3.4, pop_pct=85, thunder_level=ThunderLevel.HIGH,
        hail_flag=True, cape_jkg=2400.0, humidity_pct=88, dewpoint_c=14.5,
        uv_index=7.5, pressure_msl_hpa=1004.5, visibility_m=1800,
        freezing_level_m=3200, snowfall_limit_m=2600,
        precip_type=PrecipType.MIXED, cloud_total_pct=90, cloud_low_pct=70,
        cloud_mid_pct=55, cloud_high_pct=40,
    )


def _dense_segment() -> SegmentWeatherData:
    alert = OfficialAlert(
        source="meteoalarm", hazard="thunderstorm", level=4, label="Gewitter",
        valid_from=datetime(_YEAR, _MONTH, _DAY, 10, 0),
        valid_to=datetime(_YEAR, _MONTH, _DAY, 16, 0), region_label="Region",
    )
    return SegmentWeatherData(
        segment=TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=46.6, lon=12.9, elevation_m=1800.0),
            end_point=GPXPoint(lat=46.7, lon=13.0, elevation_m=2100.0),
            start_time=datetime(_YEAR, _MONTH, _DAY, 7, 0, tzinfo=timezone.utc),
            end_time=datetime(_YEAR, _MONTH, _DAY, 17, 0, tzinfo=timezone.utc),
            duration_hours=10.0, distance_km=14.0, ascent_m=900.0, descent_m=600.0,
        ),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="test",
                run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
                grid_res_km=1.0, interp="point_grid",
            ),
            data=[_dp(h) for h in range(24)],
        ),
        aggregated=SegmentWeatherSummary(
            temp_min_c=8.0, temp_max_c=19.5, wind_chill_min_c=4.0,
            wind_chill_max_c=15.5, wind_max_kmh=32.0, gust_max_kmh=58.0,
            precip_sum_mm=12.0, pop_max_pct=85, thunder_level_max=ThunderLevel.HIGH,
            snow_depth_cm=45.0, snowfall_limit_m=2600, snow_new_sum_cm=12.0,
            confidence_pct_min=55,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 5, 0, tzinfo=timezone.utc),
        provider="openmeteo",
        official_alerts=[alert],
        official_alerts_unavailable=True,
    )


def _night() -> NormalizedTimeseries:
    return NormalizedTimeseries(
        meta=ForecastMeta(
            provider=Provider.OPENMETEO, model="test",
            run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
            grid_res_km=1.0, interp="point_grid",
        ),
        data=(
            [_dp(h) for h in range(17, 24)]
            + [_dp(h, day=_DAY + 1) for h in range(0, 7)]
        ),
    )


def _notice(hazard: str, level: int, scope: str = "E1") -> OfficialAlertNotice:
    return OfficialAlertNotice(
        alert=OfficialAlert(
            source="meteoalarm", hazard=hazard, level=level, label=hazard,
            valid_from=datetime(_YEAR, _MONTH, _DAY, 10, 0),
            valid_to=datetime(_YEAR, _MONTH, _DAY, 16, 0), region_label="Region",
        ),
        scope_label=f"Etappe {scope}", sms_scope=scope,
        affected_chips=[scope], free_chips=[],
    )


# ---------------------------------------------------------------------------
# AC-1 -- Trip-Briefing
# ---------------------------------------------------------------------------

def test_trip_briefing_sms_stays_gsm7_clean_with_dense_token_line():
    """Ein Tagesfixture mit moeglichst vielen gleichzeitig aktiven Token muss
    GSM-7-rein rendern.

    Zwei Renderlaeufe, weil ``render_sms`` bei 160 Zeichen Token in der
    ``DROP_ORDER``-Reihenfolge WEGWIRFT (``tokens/render.py``): der 160er-Lauf
    ist der echte Versandtext, der grosszuegige Lauf stellt sicher, dass die
    weggeworfenen Token ueberhaupt einmal geprueft werden. Genau diese Luecke
    war der F001-Fund des Compare-Waechters -- 12 von 26 Groessen fielen dort
    IMMER in den Ueberlauf und wurden nie geprueft.

    Der Etappenname traegt bewusst ein Diakritikum AUSSERHALB des
    GSM-7-Basisalphabets (``Ś``, U+015A). Deutsche Umlaute reichen dafuer
    nicht: ``ae/oe/ue`` SIND GSM-7-nativ -- mit ihnen bliebe ein Faltungs-
    Ausfall hier unentdeckt.

    Was dieser Test NICHT leistet: den Etappennamen falten ZWEI Stellen
    nacheinander -- ``_sms_stage_prefix`` (sms_trip.py:55) und
    ``_sanitize_stage_name`` (builder.py:37, aus ``build_token_line``). Faellt
    eine davon isoliert aus, faengt die andere den Ausfall auf und dieser Test
    bleibt gruen. Die einzelne Stelle bewacht deshalb der eigene Test
    darunter."""
    formatter = SMSTripFormatter()
    kwargs = dict(
        report_type="evening", tz=_UTC, night_weather=_night(),
        thunder_forecast={"+1": {"level": "HIGH", "hour": 15, "hail": True}},
        stage_name="Świnica", sms_alert_min_level=3,
    )
    sms = formatter.format_sms([_dense_segment()], **kwargs)
    full = formatter.format_sms([_dense_segment()], max_length=2000, **kwargs)

    assert full.startswith("Swinica: "), (
        f"Der Etappenname wurde nicht gefaltet: {full[:20]!r}. Ohne Faltung "
        "traegt die SMS das GSM-7-fremde Zeichen weiter -- der Zeichensatz-"
        "Check unten muss dann rot werden, nicht diese Zusicherung."
    )

    fehlend = [
        # Issue #1824 (A): 'K'/'FK' stehen bei gewaehltem Tiefst- UND
        # Hoechstwert nicht mehr eigenstaendig in der Zeile -- ihre Werte
        # sind die erste Haelfte von 'D{min}/{max}' bzw. 'FD{min}/{max}',
        # die hier ueber 'D'/'FD' geprueft werden.
        sym for sym in ("N", "D", "FN", "FD", "R", "PR", "W", "G",
                        # Issue #1703 Scheibe 6: Marker fuer "amtliche Warnungen
                        # nicht verfuegbar" heisst "X?", vormals "W?"
                        # (UNAVAILABLE_SYMBOL, builder.py:84).
                        "TH:", "TH+:", "X?", "HU", "DP", "CP", "UV", "CT",
                        "VS", "SU", "HP", "FZ", "WD", "PT", "SD", "SL")
        if sym not in full
    ]
    assert not fehlend, (
        f"Testaufbau defekt: {fehlend} fehlen in der ungekuerzten Token-Zeile "
        f"{full!r} -- der Waechter pruefte dann eine duennere Zeile als "
        "behauptet und koennte ein Fremdzeichen uebersehen."
    )
    assert_gsm7_clean(sms, "Trip-Briefing-SMS (Versandtext, 160 Zeichen)")
    assert_gsm7_clean(full, "Trip-Briefing-SMS (ungekuerzt, alle Token)")


def test_stage_prefix_folds_non_gsm7_letters_on_its_own():
    """``_sms_stage_prefix`` einzeln geprueft, ohne Umweg ueber ``format_sms``.

    Ueber die volle Pipeline ist sein Ausfall unsichtbar, weil
    ``_sanitize_stage_name`` (builder.py:37) denselben Namen ein zweites Mal
    faltet. Diese Doppelung sieht wie toter Code aus -- wer sie aufraeumt,
    bekaeme ohne diesen Test kein rotes Signal, obwohl je nach entfernter
    Stelle ein GSM-7-fremder Etappenname durchginge."""
    assert _sms_stage_prefix("Świnica") == "Swinica"
    assert _sms_stage_prefix("Höhenweg") == "Hoehenweg"


# ---------------------------------------------------------------------------
# AC-2 -- amtlicher Alarm, Regressionsschutz
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hazard", sorted(HAZARD_SMS_SYMBOLS))
def test_official_alert_sms_stays_gsm7_clean_for_every_hazard_and_umlaut_scope(
    hazard: str,
):
    """Jede Katalog-Gefahr, uniforme UND gemischte Warnstufe -- ``_ascii()``/
    ``fold_ascii()`` faltet Buchstaben, deshalb kein Fund erwartet
    (Regressionsschutz).

    FORTGESCHRIEBEN (#1948 S5): der Trip-Name (``sms_prefix``) ist ersatzlos
    entfallen. Der nutzereingegebene Text erreicht die amtliche Alarm-SMS jetzt
    ueber den ORTSKOPF (``sms_scope``) -- dort sitzt dieselbe Fehlerklasse, und
    dorthin wandert diese Zusicherung. Der Ort traegt Umlaute UND ein
    Diakritikum ausserhalb des GSM-7-Basisalphabets (`Ś`, U+015A). Der Umlaut
    allein wuerde die Zusicherung wertlos machen: `ö` IST GSM-7-nativ, ein
    Ausfall von ``fold_ascii()`` (alert/render.py:706) bliebe unentdeckt."""
    ort = "Höhenweg Świnica"
    uniform = render_official_alert_sms(
        [_notice(hazard, 4, ort), _notice("wind_gust", 4, ort)],
    )
    gemischt = render_official_alert_sms(
        [_notice(hazard, 4, ort), _notice("wind_gust", 3, "E2")],
    )
    for text, stufe in ((uniform, "uniforme Stufe"), (gemischt, "gemischte Stufe")):
        assert "Hoehenweg Swinica" in text, (
            f"Ortsname wurde nicht gefaltet ({hazard}, {stufe}): {text!r}"
        )
        assert_gsm7_clean(text, f"amtlicher Alarm ({hazard}, {stufe})")


# ---------------------------------------------------------------------------
# fix_1796 AC-1 + AC-3 -- GSM-7-Extension-Zeichen im Trip-Namen (Issue #1796)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ext_char", list(GSM7_EXTENDED_TWO_SEPTET_CHARS))
def test_official_alert_sms_filters_gsm7_extension_char_in_scope(ext_char: str):
    """fix_1796 AC-1: jedes der 9 GSM-7-Extension-Zeichen (Form-Feed, ^ { } \\
    [ ~ ] | €) im nutzereingegebenen Text darf die gerenderte amtliche
    Alarm-SMS nicht verlassen -- sonst schaltet der Betreiber die GANZE SMS
    still auf UCS-2 um (67 statt 153 Zeichen je Teil, 3GPP TS 23.040). Diese
    Zeichen sind GSM-7-KODIERBAR (daher kein Fund fuer die reine
    `_GSM7_CHARSET`-Pruefung im Compare-Waechter), kosten aber je zwei
    Septets -- eine stille Budget-Verletzung, die `_ascii()` nicht abfaengt.

    FORTGESCHRIEBEN (#1948 S5): Eintrittstor ist der ORTSKOPF (``sms_scope``)
    statt des entfallenen Trip-Namens."""
    sms = render_official_alert_sms([_notice("thunderstorm", 4, f"Tour{ext_char}Nord")])
    assert_gsm7_clean(sms, f"amtlicher Alarm (Extension-Zeichen {ext_char!r})")


@pytest.mark.parametrize("ortsname", ["KHW [Test]", "Tour~Nord", "Weg|Nord"])
def test_official_alert_sms_with_gsm7_extension_char_in_scope(ortsname: str):
    """fix_1796 AC-3 (Bug-Nachweis): die drei in Issue #1796 gemessenen
    Beispiel-Namen, direkt aus dem Issue uebernommen -- reproduziert den
    urspruenglich gemeldeten Fund, jetzt am Ortskopf statt am Trip-Namen."""
    sms = render_official_alert_sms([_notice("thunderstorm", 4, ortsname)])
    assert_gsm7_clean(sms, f"amtlicher Alarm (Ortsname {ortsname!r})")
