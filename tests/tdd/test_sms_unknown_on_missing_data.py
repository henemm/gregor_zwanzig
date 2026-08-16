"""SMS: `?` (unbekannt) statt `-` (Fehl-Entwarnung) bei Teilausfall (#1328).

Spec: docs/specs/modules/sms_unknown_on_missing_data.md

Bei einem teilweisen Wetterdaten-Ausfall (mindestens ein Segment
`has_error=True` bzw. ohne Zeitreihe) rendert die SMS-Aggregation heute
still `-` ("kein Risiko") fuer jedes Symbol, zu dem im 04-19-Uhr-Fenster
keine Stichprobe vorlag — eine falsche Entwarnung auf dem einzigen Kanal,
der Wanderer unterwegs erreicht. Diese Suite belegt AC-1..AC-4 der Spec.

TDD RED: AC-1 und AC-4 muessen mit dem heutigen Code fehlschlagen (SMS zeigt
`TH:-` statt `TH:?`). AC-2/AC-3 sind Regressionsschutz und duerfen bereits
gruen sein.

Keine Mocks, keine Dateiinhalt-Checks. Reale Fixtures (echte
`SegmentWeatherData`, wie `segment_weather.py:150-158` sie bei
Provider-Fehlern real erzeugt), reale Aufrufe von
`SMSTripFormatter().format_sms()`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from src.output.renderers.sms_trip import SMSTripFormatter
from src.output.tokens.dto import MetricSpec
from src.services.notification_service import compute_has_gap

_YEAR, _MONTH, _DAY = 2026, 7, 20
_TZ = ZoneInfo("UTC")


def _dp(hour: int, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    """Ein Stunden-Datenpunkt der regulaeren (fehlerfreien) Segment-Zeitreihe."""
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=5.0,
        gust_kmh=5.0,
        precip_1h_mm=0.0,
        pop_pct=0,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _trip_segment(start_h: int, end_h: int) -> TripSegment:
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(_YEAR, _MONTH, _DAY, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h),
        distance_km=8.0,
        ascent_m=200.0,
        descent_m=0.0,
    )


def _error_segment(start_h: int = 4, end_h: int = 9) -> SegmentWeatherData:
    """Wie ``segment_weather.py:150-158`` bei Provider-Fehlern real erzeugt:
    leere ``SegmentWeatherSummary()``, ``timeseries=None``, ``has_error=True``."""
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
        has_error=True,
        error_message="provider timeout",
    )


def _regular_segment(
    start_h: int = 9,
    end_h: int = 17,
    thunder_by_hour: dict[int, ThunderLevel] | None = None,
) -> SegmentWeatherData:
    """Vollstaendiges, fehlerfreies Segment mit 24h-Zeitreihe."""
    tb = thunder_by_hour or {}
    data = [_dp(h, tb.get(h, ThunderLevel.NONE)) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


# Ausdrueckliche Abwahl von Temperatur (K/D) und gefuehlter Temperatur
# (FN/FK/FD) fuer die Direktaufrufe unten. 'WC' ist Fix #1887 E6 Scheibe A
# (PO-Entscheid) ERSATZLOS entfallen -- die Abwahl eines nicht mehr
# existierenden Symbols ist wirkungslos, aber harmlos; hier stehen gelassen
# als reine Dokumentation der historischen Symbolliste. ``format_sms()``
# ist die
# Low-Level-API: sie kennt vertragsgemaess KEINE ``display_config``, die
# Metrik-Auswahl wird ihr als ``disabled_specs`` uebergeben (genau so baut
# ``trip_report.py:272-287`` sie aus der Nutzer-Konfiguration). Fuer die
# R/PR/W/G/TH:-Tests unten (#1328) gehoeren die Temperatur-Token nicht zum
# Pruefgegenstand und werden deshalb abgewaehlt, statt den erwarteten Text
# um sie zu verlaengern. Issue #1483 (weiter unten in dieser Datei) prueft
# die Temperatur-Token selbst und baut dafuer eigene, gezielt aktivierte
# ``MetricSpec``-Listen statt dieser Konstante.
_TEMPERATURE_OFF: list[MetricSpec] = [
    MetricSpec(symbol=sym, enabled=False)
    for sym in ("N", "K", "D", "FN", "FK", "FD", "WC")
]

# Issue #1660 Scheibe B: dieselbe Abwahl-Notwendigkeit fuer die 14 neuen
# Metriken -- ohne Trip-Kontext (kein `display_config`) sind sie "gewaehlt",
# sobald `_dp()` zufaellig unrelated Felder (humidity_pct/cloud_total_pct)
# traegt (DEC-1/DEC-2c). Fuer die Byte-Identitaets-Assertion unten (#1328)
# gehoeren sie nicht zum Pruefgegenstand.
_NEW_14_OFF: list[MetricSpec] = [
    MetricSpec(symbol=sym, enabled=False) for sym in (
        "HU", "DP", "WD", "CP", "PT", "CT", "CL", "CM", "CH", "VS", "SU",
        "UV", "HP", "NL",
    )
]


def _format(
    segments: list[SegmentWeatherData],
    night_weather: NormalizedTimeseries | None = None,
    *,
    disabled_specs: list[MetricSpec] | None = None,
    report_type: str = "morning",
) -> str:
    """Issue #1331/#1334 F008: die Ziel-Datenluecke wird nicht mehr in
    ``format_sms()`` selbst berechnet (einziger Berechnungspunkt ist jetzt
    ``notification_service.compute_has_gap()``) -- dieser Helper bildet
    genau den echten Versandpfad nach, statt eine feste Konstante zu raten.

    ``disabled_specs`` reicht die Metrik-Auswahl durch (Default: keine
    Abwahl, also alle Kuerzel, die der Renderer aus den Daten bilden kann).
    ``report_type`` (Issue #1483): Default bleibt "morning" (bit-identisches
    Verhalten fuer alle bestehenden Aufrufer) -- "evening" wird gebraucht,
    damit N/FN ueberhaupt sichtbar werden (sie sind evening_only)."""
    has_gap = compute_has_gap(segments, night_weather, _TZ)
    return SMSTripFormatter().format_sms(
        segments, stage_name="E1", report_type=report_type, tz=_TZ,
        night_weather=night_weather, has_gap=has_gap,
        disabled_specs=disabled_specs,
    )


def _complete_night_weather(start_h: int = 17, end_h: int = 23) -> NormalizedTimeseries:
    """Vollstaendige (ereignislose) Nacht-Zeitreihe -- Issue #1331: ohne sie
    meldet ``compute_has_gap`` bei Ankunft <= 19 Uhr faelschlich eine
    Ziel-Luecke, auch wenn der Test gar keine Segment-Datenluecke pruefen
    will."""
    data = [_dp(h) for h in range(start_h, end_h + 1)]
    return NormalizedTimeseries(meta=_meta(), data=data)


class TestAC1ShowsUnknownTokenOnSegmentError:
    """AC-1: Ein Segment mit ``has_error=True`` im Fenster plus ein
    reguläres Segment ohne Gewitter-Ereignis -> `TH:?` statt `TH:-`.

    Verschaerfte Regel (PO-Entscheidung 2026-07-20): jede Entwarnung `-` im
    Fenster wird bei einer Datenluecke zu `?`, nicht nur bei fehlender
    Stichprobe -> auch `R?`/`PR?`/`W?`/`G?` erwartet."""

    def test_sms_shows_unknown_token_when_segment_has_error(self):
        # Vollstaendige Nacht-Zeitreihe: damit ist der Segment-Fehler die
        # EINZIGE Luecken-Quelle. Ohne sie waere (Ankunft 17:00 <= Fensterende
        # 19:00, night_weather=None) bereits das unbeobachtete Zielfenster eine
        # Luecke -- der Test waere auch mit zwei fehlerfreien Segmenten gruen
        # und wuerde `has_error` gar nicht pruefen (Mutations-Gegenprobe
        # 2026-08-03: Ersetzen des Fehler-Segments blieb unbemerkt).
        segments = [_error_segment(), _regular_segment()]
        sms = _format(
            segments,
            night_weather=_complete_night_weather(),
            disabled_specs=_TEMPERATURE_OFF + _NEW_14_OFF,
        )

        assert "TH:?" in sms, (
            f"Erwartet `TH:?` (unbekannt, weil eine Etappe wegen "
            f"Provider-Fehler keine Daten beitragen konnte), stattdessen "
            f"faelschliche Entwarnung.\nSMS: {sms}"
        )
        assert "TH:-" not in sms, f"Fehl-Entwarnung `TH:-` darf nicht erscheinen.\nSMS: {sms}"
        assert sms == "E1: R? PR? W? G? TH:? TH+:-", (
            f"Erwartet, dass die verschaerfte Regel jede Entwarnung im "
            f"lueckenhaften Fenster zu `?` macht (R/PR/W/G/TH:) -- und dass "
            f"ausser den abgewaehlten Temperatur-Token nichts sonst in der "
            f"SMS steht.\nSMS: {sms}"
        )


class TestAC2KeepsFoundRiskDespiteGap:
    """AC-2 (sicherheitskritisch): ein gefundener Wert wird NIE durch `?`
    ersetzt, auch wenn andere Segmente im Fenster Datenluecken haben."""

    def test_sms_keeps_found_risk_despite_other_segment_gap(self):
        segments = [
            _error_segment(),
            _regular_segment(thunder_by_hour={10: ThunderLevel.HIGH}),
        ]
        sms = _format(segments)

        assert "TH:H@10" in sms, f"Erwartet den gefundenen Gewitter-Wert.\nSMS: {sms}"
        assert "TH:?" not in sms, (
            f"Ein erkanntes Gewitter darf nie durch `?` verschluckt werden "
            f"(Sicherheitsprinzip der Spec).\nSMS: {sms}"
        )


class TestAC3RegressionNoGapStaysDash:
    """AC-3 (Regressionsschutz): ohne Datenluecke bleibt `-` unveraendert."""

    def test_sms_shows_dash_when_no_gap(self):
        """Issue #1331 (semantisch gewollt): Ankunft 17:00 <= Fensterende
        19:00 erwartet Nach-Ankunft-Stunden am Ziel -- ohne ``night_weather``
        waere das jetzt selbst eine Ziel-Luecke. Um ausschliesslich die
        urspruengliche Aussage (keine SEGMENT-Datenluecke -> `-` bleibt)
        zu pruefen, liefert der Test eine vollstaendige Nacht-Zeitreihe."""
        segments = [_regular_segment(start_h=4, end_h=9), _regular_segment(start_h=9, end_h=17)]
        sms = _format(segments, night_weather=_complete_night_weather())

        assert "TH:-" in sms, f"Erwartet weiterhin `-` ohne Datenluecke.\nSMS: {sms}"
        assert "TH:?" not in sms, f"Kein `?` ohne Datenluecke erwartet.\nSMS: {sms}"


def _regular_segment_with_multiple_warnings(
    start_h: int = 9, end_h: int = 17,
) -> SegmentWeatherData:
    """Regulaeres, fehlerfreies Segment mit MEHREREN echten Warnwerten ueber
    Schwelle an Stunde 10 (Gewitter HIGH, Wind 45 km/h, Regen 5mm). Boen und
    Regenwahrscheinlichkeit bleiben unterschwellig/0 (kein Fund -> `?`)."""
    data = []
    for h in range(0, 24):
        if h == 10:
            data.append(ForecastDataPoint(
                ts=datetime(_YEAR, _MONTH, _DAY, h, 0, tzinfo=timezone.utc),
                t2m_c=15.0, wind10m_kmh=45.0, gust_kmh=5.0,
                precip_1h_mm=5.0, pop_pct=0, cloud_total_pct=50,
                thunder_level=ThunderLevel.HIGH, humidity_pct=55,
            ))
        else:
            data.append(_dp(h))
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=45.0,
            gust_max_kmh=25.0, precip_sum_mm=5.0,
            thunder_level_max=ThunderLevel.HIGH,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


class TestSMSKeepsFoundValuesDespiteGapForMultipleMetrics:
    """Verschaerfte Regel (PO 2026-07-20): eine Datenluecke im Fenster
    entwertet JEDE Entwarnung `-` zu `?` — aber unterdrueckt NIE einen
    tatsaechlich gefundenen Warnwert, auch nicht bei mehreren Metriken
    gleichzeitig (Gewitter, Wind, Regen)."""

    def test_sms_shows_found_values_despite_gap_for_multiple_metrics(self):
        segments = [_error_segment(), _regular_segment_with_multiple_warnings()]
        sms = _format(segments)

        # Gefundene Warnwerte erscheinen unveraendert mit echtem Wert.
        assert "TH:H@10" in sms, f"Erwartet gefundenes Gewitter.\nSMS: {sms}"
        assert "W45@10" in sms, f"Erwartet gefundenen Wind-Wert.\nSMS: {sms}"
        assert "R5.0@10" in sms, f"Erwartet gefundenen Regen-Wert.\nSMS: {sms}"

        # Fuer diese drei Groessen darf trotz Luecke KEIN `?` erscheinen.
        assert " TH:?" not in sms, f"Gewitter-Fund darf nicht zu `?` werden.\nSMS: {sms}"
        assert " W?" not in sms, f"Wind-Fund darf nicht zu `?` werden.\nSMS: {sms}"
        assert " R?" not in sms, f"Regen-Fund darf nicht zu `?` werden.\nSMS: {sms}"

        # Groessen OHNE Fund (Boeen, Regenwahrscheinlichkeit) zeigen `?`.
        assert "PR?" in sms, f"Erwartet `?` fuer PR ohne Fund.\nSMS: {sms}"
        assert "G?" in sms, f"Erwartet `?` fuer G ohne Fund.\nSMS: {sms}"


class TestAC4LengthBudget:
    """AC-4: `?` belegt genau die Wertstelle, kein Zusatztext -> SMS bleibt
    innerhalb des 160-Zeichen-Budgets."""

    def test_sms_unknown_token_stays_within_length_budget(self):
        segments = [_error_segment(), _regular_segment()]
        sms = _format(segments)

        assert len(sms) <= 160, f"SMS ueberschreitet 160 Zeichen ({len(sms)}).\nSMS: {sms}"


# Issue #1483: dieselbe verschaerfte Regel wie oben (jede Entwarnung `-` wird
# bei einer Datenluecke im Fenster zu `?`) gilt bisher NICHT fuer die sechs
# Temperatur-Kuerzel N/K/D/FN/FK/FD -- sie durchlaufen render_temperature(),
# das `has_gap` nicht kennt. Eigene, gezielt aktivierte MetricSpec-Listen
# statt `_TEMPERATURE_OFF` (siehe Kommentar oben).
_TEMPERATURE_ON: list[MetricSpec] = [
    MetricSpec(symbol=sym, enabled=True)
    for sym in ("N", "K", "D", "FN", "FK", "FD")
]


def _total_segment_failure() -> list[SegmentWeatherData]:
    """Zwei ``_error_segment()``s ohne reguläres Segment dazwischen -- echter
    Komplettausfall der Etappe. Anders als die Mischform (ein Error- + ein
    Regular-Segment, wie ``TestAC1ShowsUnknownTokenOnSegmentError`` sie
    nutzt) liefert diese Fixture fuer ALLE sechs Temperatur-Kuerzel `None`:
    das Gehzeit-Fenster (``hiking_field_min_max()``, Quelle von N/K/D/FN/FK/
    FD) hat dann keinerlei verwertbare Datenpunkte mehr, waehrend die
    Mischform ueber das verbleibende Regular-Segment noch einen echten
    Temperaturwert liefert (siehe die zweite Testklasse unten)."""
    return [
        _error_segment(start_h=4, end_h=9),
        _error_segment(start_h=9, end_h=17),
    ]


class TestTemperatureShowsUnknownOnGap:
    """Issue #1483: N/K/D/FN/FK/FD sollen bei einer Datenluecke im Fenster
    dieselbe `?`-Kennzeichnung bekommen wie R/PR/W/G/TH: (#1328) -- bislang
    zeigen sie faelschlich `-`, nicht unterscheidbar von "geprueft, nichts
    vorhergesagt"."""

    def test_all_six_show_unknown_on_total_segment_failure(self):
        """AC-1: kompletter Etappenausfall -> alle sechs Kuerzel `?`."""
        segments = _total_segment_failure()
        sms = _format(segments, report_type="evening",
                       disabled_specs=_TEMPERATURE_ON)

        # Issue #1824 (A): Tiefst- UND Hoechstwert sind gewaehlt, also tragen
        # 'K'/'D' bzw. 'FK'/'FD' EINEN gemeinsamen Bereichs-Token -- die
        # Unbekannt-Kennzeichnung steht dort je Haelfte ('D?/?'). Die
        # Zusicherung ist unveraendert: keine der sechs Groessen darf bei
        # Komplettausfall als Entwarnung erscheinen.
        for token in ("N?", "D?/?", "FN?", "FD?/?"):
            assert token in sms.split(), (
                f"Erwartet `{token}` (unbekannt, kompletter Etappenausfall), "
                f"stattdessen faelschliche Entwarnung.\nSMS: {sms}"
            )
        # Einzelner Gesamt-Check statt sechsfacher Substring-Subtraktion:
        # "K-" ist z.B. Teilstring von "FK-", ein Ersetzen pro Symbol wuerde
        # sich gegenseitig verfaelschen. Nach dem Fix darf keines der sechs
        # Kuerzel mehr in seiner `-`-Form auftauchen.
        for dash_form in ("N-", "K-", "D-", "FN-", "FK-", "FD-"):
            assert dash_form not in sms, (
                f"Fehl-Entwarnung `{dash_form}` darf bei Komplettausfall "
                f"nicht erscheinen.\nSMS: {sms}"
            )

    def test_found_measured_value_survives_partial_gap_while_missing_felt_becomes_unknown(self):
        """Ergaenzung zu AC-1 (Sicherheitsregel, analog
        TestAC2KeepsFoundRiskDespiteGap): bei der Mischform (ein Error- + ein
        Regular-Segment) liefert das Gehzeit-Fenster fuer N/K/D einen ECHTEN
        Wert ueber das verbleibende Regular-Segment -- der darf trotz
        `has_gap=True` NIE zu `?` werden. FN/FK/FD haben in der Test-Fixture
        dagegen grundsaetzlich keine Windchill-Daten (`_dp()` setzt
        `wind_chill_c` nie) und muessen deshalb bei vorliegender
        Datenluecke zu `?` werden."""
        segments = [_error_segment(), _regular_segment()]
        sms = _format(segments, report_type="evening",
                       disabled_specs=_TEMPERATURE_ON)

        # Tokenweiser statt Substring-Vergleich: "N?" ist Teilstring von
        # "FN?" (ebenso "K?"/"FK?", "D?"/"FD?") -- eine naive `in sms`-Pruefung
        # wuerde sich an der eigenen Positiv-Erwartung fuer FN/FK/FD
        # verschlucken. Der Kommentar bei ``TestTemperatureShowsUnknownOnGap.
        # test_all_six_show_unknown_on_total_segment_failure`` beschreibt
        # dieselbe Falle fuer die `-`-Form; hier gilt sie fuer `?`.
        tokens = sms.split()
        # Issue #1824 (A): der gemessene Bereich steht als EIN Token
        # ('D15/15' -- beide Haelften tragen denselben gefundenen Wert).
        for token in ("N15", "D15/15"):
            assert token in tokens, (
                f"Erwartet den gefundenen Wert `{token}` aus dem "
                f"verbleibenden Regular-Segment.\nSMS: {sms}"
            )
        for sym in ("N", "K", "D"):
            assert f"{sym}?" not in tokens, (
                f"Ein gefundener Temperaturwert darf nie durch `?` "
                f"verschluckt werden.\nSMS: {sms}"
            )
        for token in ("FN?", "FD?/?"):
            assert token in tokens, (
                f"Erwartet `{token}` (keine Windchill-Daten UND "
                f"Datenluecke).\nSMS: {sms}"
            )

    def test_no_gap_missing_felt_temperature_stays_dash(self):
        """AC-2 (Abgrenzung): ohne Datenluecke bleibt eine echt fehlende
        gefuehlte Temperatur `-`, wird NICHT zu `?`."""
        segments = [
            _regular_segment(start_h=4, end_h=9),
            _regular_segment(start_h=9, end_h=17),
        ]
        sms = _format(segments, night_weather=_complete_night_weather(),
                       report_type="evening",
                       disabled_specs=_TEMPERATURE_ON)

        # Issue #1824 (A): 'FK'/'FD' stehen als EIN Bereichs-Token ('FD-/-'),
        # die Null-Form je Haelfte einmal.
        for token in ("FN-", "FD-/-"):
            assert token in sms.split(), (
                f"Erwartet weiterhin `{token}` ohne Datenluecke.\nSMS: {sms}"
            )
        for sym in ("FN", "FK", "FD"):
            assert f"{sym}?" not in sms, (
                f"Kein `?` ohne Datenluecke erwartet.\nSMS: {sms}"
            )

    def test_disabled_temperature_metrics_absent_despite_gap(self):
        """AC-3 (Regressionsschutz #1415): abgewaehlte Temperatur-Metrik
        bleibt bei Datenluecke komplett unsichtbar -- weder `-` noch `?`."""
        segments = _total_segment_failure()
        sms = _format(segments, report_type="evening",
                       disabled_specs=_TEMPERATURE_OFF)

        for sym in ("N", "K", "D", "FN", "FK", "FD"):
            assert f"{sym}?" not in sms, (
                f"Abgewaehltes Kuerzel `{sym}` darf auch bei Luecke nicht "
                f"als `?` erscheinen.\nSMS: {sms}"
            )
            assert f"{sym}-" not in sms, (
                f"Abgewaehltes Kuerzel `{sym}` darf auch bei Luecke nicht "
                f"als `-` erscheinen.\nSMS: {sms}"
            )

    def test_unknown_marker_stays_within_length_budget(self):
        """AC-5: `?` belegt genau die Wertstelle wie zuvor `-` -- SMS bleibt
        innerhalb des 160-Zeichen-Budgets, auch mit allen sechs `?`."""
        segments = _total_segment_failure()
        sms = _format(segments, report_type="evening",
                       disabled_specs=_TEMPERATURE_ON)

        assert len(sms) <= 160, f"SMS ueberschreitet 160 Zeichen ({len(sms)}).\nSMS: {sms}"
