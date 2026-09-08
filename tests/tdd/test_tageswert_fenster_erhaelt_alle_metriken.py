"""
TDD RED — Tagesaggregat ab Anfragezeitpunkt: die Rechenkette bleibt VOLLSTAENDIG.

SPEC: docs/specs/modules/feat_2186_tagesaggregat_ab_jetzt.md v1.0 (Issue #2186)
Deckt AC-3, AC-6, AC-7, AC-8.

Beweist gegen ECHTE, auf Platte persistierte Snapshots (kein Mock, kein
Dateiinhalt-Check) ueber den realen ``WeatherSnapshotService.save/load``-
Roundtrip, dass die Fensterung eines Segments dessen Aggregat NEU rechnet —
und zwar ueber BEIDE Rechenstufen (``compute_basis_metrics`` UND
``compute_extended_metrics``). Faellt die zweite Stufe weg, werden 18 Felder
still ``None``: sichtbar als „keine Daten", ohne dass irgendetwas fehlschlaegt.
Genau diese Stille bewacht AC-6.

Diese Tests MUESSEN initial fehlschlagen:
  * ``WeatherExtractor.timeline()`` kennt den Parameter ``from_time`` noch
    nicht -> ``TypeError`` (alle Tests dieser Datei).

Die Erwartungswerte sind LITERALE, nicht aus derselben Rechenkette abgeleitet:
sie wurden einmalig gegen ``compute_basis_metrics``/``compute_extended_metrics``
nachgemessen und hier fest eingetragen. Ein Test, der seinen Sollwert aus dem
Prueflings-Code holt, bewacht nichts.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

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
from services.weather_snapshot import WeatherSnapshotService

TAG = date(2026, 2, 14)

# London im Februar ist GMT — Ortszeit == UTC. Damit ist die Tagesfenster-
# Stunde aus AC-7 ohne Zonen-Umrechnung nachvollziehbar; ein Ort mit Versatz
# wuerde die Aussage des Tests mit einer zweiten Frage vermischen.
ORT_LAT, ORT_LON = 51.5, -0.13

# Zwei kontrastreiche Stundenprofile. Die Zahlen sind bewusst weit auseinander,
# damit „alter Wert durchgereicht" und „neu ueber das Restfenster gerechnet"
# an JEDEM geprueften Feld unterscheidbar sind.
FRUEH = dict(
    t2m_c=3.0, wind10m_kmh=45.0, gust_kmh=70.0, precip_1h_mm=5.0, pop_pct=95,
    cape_jkg=2500.0, uv_index=2.0, cloud_low_pct=90, cloud_mid_pct=80,
    cloud_high_pct=70, cloud_total_pct=95, snowfall_limit_m=1500,
    precip_type=PrecipType.SNOW, dewpoint_c=1.0, pressure_msl_hpa=995.0,
    freezing_level_m=1400, humidity_pct=95, visibility_m=600,
)
SPAET = dict(
    t2m_c=15.0, wind10m_kmh=8.0, gust_kmh=15.0, precip_1h_mm=0.0, pop_pct=20,
    cape_jkg=400.0, uv_index=7.0, cloud_low_pct=30, cloud_mid_pct=20,
    cloud_high_pct=10, cloud_total_pct=35, snowfall_limit_m=2800,
    precip_type=PrecipType.RAIN, dewpoint_c=6.0, pressure_msl_hpa=1018.0,
    freezing_level_m=2900, humidity_pct=50, visibility_m=25000,
)

# Ein gespeichertes Aggregat mit unverwechselbaren Werten. Taucht eine dieser
# Zahlen dort auf, wo eine Neuberechnung erwartet wird, ist der alte Wert
# durchgereicht worden — und umgekehrt.
UNVERWECHSELBAR = dict(
    temp_max_c=21.5, temp_min_c=11.5, wind_max_kmh=33.0, precip_sum_mm=12.5,
    pop_max_pct=77, cape_max_jkg=1234.0, uv_index_max=4.4,
    cloud_low_avg_pct=55, snowfall_limit_m=2222, precip_type_dominant=PrecipType.MIXED,
)


def _punkt(stunde: int, **werte) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TAG.year, TAG.month, TAG.day, stunde, 0, tzinfo=timezone.utc),
        **werte,
    )


def _segment(
    segment_id: int,
    stunde_start: int,
    stunde_ende: int,
    *,
    aggregiert: SegmentWeatherSummary,
    stunden: list[ForecastDataPoint] | None,
    day_window: tuple[int | None, int | None] = (None, None),
) -> SegmentWeatherData:
    """Ein Segment mit gespeichertem Aggregat und optionaler Stundenreihe."""
    fenster_start, fenster_ende = day_window
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=ORT_LAT, lon=ORT_LON, elevation_m=50.0),
        end_point=GPXPoint(lat=ORT_LAT, lon=ORT_LON, elevation_m=120.0),
        start_time=datetime(TAG.year, TAG.month, TAG.day, stunde_start, 0, tzinfo=timezone.utc),
        end_time=datetime(TAG.year, TAG.month, TAG.day, stunde_ende, 0, tzinfo=timezone.utc),
        duration_hours=float(stunde_ende - stunde_start),
        distance_km=6.0,
        ascent_m=250.0,
        descent_m=180.0,
        day_window_start_hour=fenster_start,
        day_window_end_hour=fenster_ende,
    )
    timeseries = None
    if stunden is not None:
        timeseries = NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0,
            ),
            data=stunden,
        )
    return SegmentWeatherData(
        segment=segment,
        timeseries=timeseries,
        aggregated=aggregiert,
        fetched_at=datetime(TAG.year, TAG.month, TAG.day, 5, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _extractor(tmp_path: Path, user_id: str = "default"):
    from services.weather_extractor import WeatherExtractor

    ex = WeatherExtractor(user_id=user_id)
    ex._snapshots._snapshots_dir = tmp_path
    return ex


def _speichere(tmp_path: Path, segmente: list[SegmentWeatherData]) -> None:
    svc = WeatherSnapshotService(user_id="default")
    svc._snapshots_dir = tmp_path
    svc.save("tour-2186", segmente, TAG)


def _um_zehn() -> datetime:
    return datetime(TAG.year, TAG.month, TAG.day, 10, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# AC-6 — beide Rechenstufen, ueber das beschnittene Fenster
# ---------------------------------------------------------------------------

class TestBeschnittenesSegmentTraegtBeideRechenstufen:
    def test_ac6_alle_felder_beider_stufen_tragen_die_restfenster_werte(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein Segment 06-12 Uhr, dessen Vormittag (06-09) Schnee, Gewitterluft
              und hohe Regenwahrscheinlichkeit trug und dessen Rest (10-11) ruhig ist,
        WHEN die Tages-Aggregation ab 10:00 laeuft,
        THEN traegt das neue Aggregat die Felder BEIDER Rechenstufen — und jedes
             davon den Wert des RESTfensters, nicht den des vollen Tages.
        """
        _speichere(tmp_path, [_segment(
            1, 6, 12,
            # Bewusst leer bis auf eine Marke: jedes gepruefte Feld kann nur
            # durch die Neuberechnung entstehen, nicht durch Durchreichen.
            aggregiert=SegmentWeatherSummary(temp_max_c=99.9),
            stunden=[_punkt(h, **FRUEH) for h in (6, 7, 8, 9)]
                    + [_punkt(h, **SPAET) for h in (10, 11)],
        )])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())

        assert len(ergebnis.points) == 1
        m = ergebnis.points[0].metrics

        # Stufe 2 (compute_extended_metrics) — ohne sie waeren diese still None.
        assert m.pop_max_pct == 20, "pop_max_pct traegt noch den Vormittag"
        assert m.cape_max_jkg == 400.0, "cape_max_jkg traegt noch den Vormittag"
        assert m.uv_index_max == 7.0, "uv_index_max ist nicht belegt"
        assert m.cloud_low_avg_pct == 30, "cloud_low_avg_pct traegt noch den Vormittag"
        assert m.precip_type_dominant == PrecipType.RAIN, (
            "precip_type_dominant meldet noch den Schnee des Vormittags"
        )
        assert m.snowfall_limit_m == 2800, "snowfall_limit_m traegt noch den Vormittag"

        # Stufe 1 (compute_basis_metrics) — dieselbe Aussage am anderen Ende
        # der Kette: faellt Stufe 1 weg, kann Stufe 2 gar nicht erst laufen.
        assert m.precip_sum_mm == 0.0, "der Vormittagsregen steckt noch im Tageswert"
        assert m.temp_min_c == 15.0
        assert m.wind_max_kmh == 8.0
        assert m.gust_max_kmh == 15.0
        assert m.cloud_avg_pct == 35
        assert m.humidity_avg_pct == 50
        assert m.visibility_min_m == 25000

    def test_ac6_kein_geprueftes_feld_faellt_still_auf_none(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein beschnittenes Segment mit vollstaendiger Stundenreihe,
        WHEN sein Aggregat neu berechnet wird,
        THEN ist KEINES der sechs Leitfelder ``None`` — der stille Ausfall
             einer halben Rechenkette sieht sonst aus wie „keine Daten".
        """
        _speichere(tmp_path, [_segment(
            1, 6, 12,
            aggregiert=SegmentWeatherSummary(),
            stunden=[_punkt(h, **FRUEH) for h in (6, 7, 8, 9)]
                    + [_punkt(h, **SPAET) for h in (10, 11)],
        )])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())
        m = ergebnis.points[0].metrics

        leer = [
            feld for feld in (
                "pop_max_pct", "cape_max_jkg", "uv_index_max", "cloud_low_avg_pct",
                "precip_type_dominant", "snowfall_limit_m",
            )
            if getattr(m, feld) is None
        ]
        assert leer == [], f"Felder still auf None gefallen: {leer}"


# ---------------------------------------------------------------------------
# AC-3 — noch nicht begonnenes Segment bleibt unangetastet
# ---------------------------------------------------------------------------

class TestNochNichtBegonnenesSegment:
    def test_ac3_segment_nach_dem_anfragezeitpunkt_behaelt_sein_aggregat(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein Segment 16-18 Uhr, das zum Anfragezeitpunkt 10:00 noch gar
              nicht begonnen hat,
        WHEN die Tages-Aggregation laeuft,
        THEN behaelt es sein GESPEICHERTES Aggregat unveraendert — Wert fuer
             Wert identisch zum ungefensterten Abruf, keine Neuberechnung.
        """
        _speichere(tmp_path, [_segment(
            2, 16, 18,
            aggregiert=SegmentWeatherSummary(**UNVERWECHSELBAR),
            # Die Stundenreihe traegt ABWEICHENDE Werte: wuerde faelschlich
            # gerechnet, kaeme etwas anderes heraus als das Gespeicherte.
            stunden=[_punkt(h, **SPAET) for h in (16, 17)],
        )])
        extractor = _extractor(tmp_path)

        gefenstert = extractor.timeline("tour-2186", from_time=_um_zehn())
        ungefenstert = extractor.timeline("tour-2186")

        m = gefenstert.points[0].metrics
        for feld, erwartet in UNVERWECHSELBAR.items():
            assert getattr(m, feld) == erwartet, (
                f"{feld} wurde veraendert, obwohl das Segment noch nicht begonnen hat"
            )
        assert m == ungefenstert.points[0].metrics, (
            "gefensterter und ungefensterter Abruf liefern verschiedene Aggregate"
        )


# ---------------------------------------------------------------------------
# AC-7 — die Fensterstunden des Segments werden durchgereicht
# ---------------------------------------------------------------------------

class TestFensterstundenWerdenDurchgereicht:
    @pytest.mark.parametrize(
        "day_window, erwarteter_onset",
        [
            # Eigenes Fenster 6-21: die Gewitterstunde 20 Uhr liegt DRIN.
            ((6, 21), datetime(TAG.year, TAG.month, TAG.day, 20, 0)),
            # Ohne eigenes Fenster gilt der Default 4-19 — 20 Uhr liegt DRAUSSEN.
            # Diese Haelfte ist die Positivkontrolle: sie zeigt, dass der Test
            # tatsaechlich am Fenster haengt und nicht an irgendetwas anderem.
            ((None, None), None),
        ],
        ids=["eigenes_fenster_6_21", "default_fenster_4_19"],
    )
    def test_ac7_thunder_onset_folgt_dem_segmentfenster(
        self, tmp_path: Path, day_window, erwarteter_onset,
    ) -> None:
        """
        GIVEN ein beschnittenes Segment mit eigenem Tagesfenster und einem
              Gewitter um 20:00 Ortszeit,
        WHEN sein Aggregat neu berechnet wird,
        THEN richtet sich ``thunder_onset_utc`` nach DIESEM Fenster und faellt
             nicht still auf den 04-19-Uhr-Default zurueck.
        """
        stunden = (
            [_punkt(h, **SPAET) for h in range(6, 20)]
            + [_punkt(20, thunder_level=ThunderLevel.HIGH, **SPAET)]
            + [_punkt(21, **SPAET)]
        )
        _speichere(tmp_path, [_segment(
            3, 6, 22,
            # Weder Onset noch Stufe vorbelegt: was unten steht, ist gerechnet.
            aggregiert=SegmentWeatherSummary(temp_max_c=99.9),
            stunden=stunden,
            day_window=day_window,
        )])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())
        m = ergebnis.points[0].metrics

        # Beweist, dass ueberhaupt neu gerechnet wurde — sonst waere die
        # ``None``-Haelfte oben auch durch blosses Durchreichen erfuellt.
        assert m.thunder_level_max == ThunderLevel.HIGH, (
            "das Segment wurde gar nicht neu gerechnet"
        )
        assert m.thunder_onset_utc == erwarteter_onset


# ---------------------------------------------------------------------------
# AC-8 — Segment ohne Stundenreihe
# ---------------------------------------------------------------------------

class TestSegmentOhneStundenreihe:
    def test_ac8_ohne_timeseries_bleibt_das_aggregat_und_nichts_faellt_um(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein Segment ohne Stundenreihe (``timeseries is None``), das zum
              Anfragezeitpunkt bereits laeuft,
        WHEN die Tages-Aggregation fuer dieses Segment laeuft,
        THEN bleibt sein gespeichertes Aggregat unveraendert und es entsteht
             kein Fehler — kein ``ValueError`` aus der leeren Rechenkette.
        """
        _speichere(tmp_path, [_segment(
            4, 6, 12,
            aggregiert=SegmentWeatherSummary(**UNVERWECHSELBAR),
            stunden=None,
        )])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())

        assert ergebnis.available is True
        assert len(ergebnis.points) == 1
        m = ergebnis.points[0].metrics
        for feld, erwartet in UNVERWECHSELBAR.items():
            assert getattr(m, feld) == erwartet, (
                f"{feld} wurde veraendert, obwohl es keine Stundenreihe gibt"
            )


# ---------------------------------------------------------------------------
# Die beiden GLEICHHEITS-Grenzen
#
# Die Spec entscheidet sie ausdruecklich (Pseudocode Zeilen 76/78): ``jetzt ==
# Segmentstart`` gilt als „noch nicht begonnen" (Aggregat unveraendert),
# ``jetzt == Segmentende`` als „vollstaendig vergangen" (Segment entfaellt).
# Beide Faelle treten real auf — Segmentgrenzen liegen auf vollen Stunden und
# ein Abruf zur vollen Stunde trifft sie genau. Ohne diese beiden Tests
# ueberlebt jede der beiden Grenzen eine Verschiebung um einen Punkt
# unbemerkt (Adversary-Befund M3).
# ---------------------------------------------------------------------------

class TestGleichheitsgrenzen:
    def test_ac3_anfrage_exakt_zum_segmentstart_rechnet_nicht_neu(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein Segment 10-14 Uhr und einen Abruf um GENAU 10:00,
        WHEN die Tages-Aggregation laeuft,
        THEN behaelt es sein gespeichertes Aggregat — die Etappe hat noch
             keine Minute hinter sich, es gibt nichts zu beschneiden.

        Die Stundenreihe traegt ABWEICHENDE Werte: wuerde faelschlich
        gerechnet, kaeme etwas anderes heraus als das Gespeicherte.
        """
        _speichere(tmp_path, [_segment(
            5, 10, 14,
            aggregiert=SegmentWeatherSummary(**UNVERWECHSELBAR),
            stunden=[_punkt(h, **SPAET) for h in (10, 11, 12, 13)],
        )])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())

        assert len(ergebnis.points) == 1, (
            "das Segment beginnt erst jetzt und darf nicht entfallen"
        )
        m = ergebnis.points[0].metrics
        for feld, erwartet in UNVERWECHSELBAR.items():
            assert getattr(m, feld) == erwartet, (
                f"{feld} wurde neu gerechnet, obwohl die Anfrage exakt auf dem "
                f"Segmentstart liegt"
            )

    def test_ac5_anfrage_exakt_zum_segmentende_laesst_das_segment_entfallen(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein Segment 06-10 Uhr, das um GENAU 10:00 zu Ende ist, und
              daneben eines, das erst um 12:00 beginnt,
        WHEN die Wegpunkte gebildet werden,
        THEN entfaellt das abgelaufene Segment — und nur dieses.

        Das zweite Segment ist die Positivkontrolle: ohne es bestuende der
        Test auch, wenn die Fensterung ALLES verschluckte.
        """
        _speichere(tmp_path, [
            _segment(
                5, 6, 10,
                aggregiert=SegmentWeatherSummary(**UNVERWECHSELBAR),
                stunden=[_punkt(h, **FRUEH) for h in (6, 7, 8, 9)],
            ),
            _segment(
                6, 12, 16,
                aggregiert=SegmentWeatherSummary(temp_max_c=99.9),
                stunden=[_punkt(h, **SPAET) for h in (12, 13, 14, 15)],
            ),
        ])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())

        assert [p.label for p in ergebnis.points] == ["6"], (
            f"das um 10:00 abgelaufene Segment steht noch in den Wegpunkten: "
            f"{[p.label for p in ergebnis.points]}"
        )


# ---------------------------------------------------------------------------
# Die Gewitter-HERKUNFT ueberlebt die Neuberechnung
#
# ``compute_extended_metrics`` baut ein neues Summary und kopiert
# ``thunder_level_max_signals`` NICHT mit (dieselbe Naht wie #1391/#1392/
# #1468). Die Neuberechnung holt den Wert deshalb von Hand aus der ersten
# Stufe zurueck. Bislang haengt dieser Schutz nur an vier fremden Tests in
# ``test_thunder_origin_*`` — er gehoert dorthin, wo er wirkt.
# ---------------------------------------------------------------------------

class TestGewitterHerkunftUeberlebtDieNeuberechnung:
    def test_traeger_der_hoechststufe_bleiben_am_neu_gerechneten_aggregat(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein beschnittenes Segment, dessen Restfenster eine Gewitter-
              stunde mit benannter Zutat traegt,
        WHEN sein Aggregat neu berechnet wird,
        THEN nennt das neue Aggregat diese Zutat — sonst verliert die
             Ad-hoc-Antwort die Herkunft ("⛈ Gewitter heute: hoch · CAPE")
             und meldet nur noch die nackte Stufe.
        """
        _speichere(tmp_path, [_segment(
            7, 6, 14,
            # Weder Stufe noch Traeger vorbelegt: was unten steht, ist gerechnet.
            aggregiert=SegmentWeatherSummary(temp_max_c=99.9),
            stunden=(
                [_punkt(h, **FRUEH) for h in (6, 7, 8, 9)]
                + [_punkt(10, thunder_level=ThunderLevel.HIGH,
                          thunder_level_signals=["cape"], **SPAET)]
                + [_punkt(h, **SPAET) for h in (11, 12, 13)]
            ),
        )])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())
        m = ergebnis.points[0].metrics

        # Beweist, dass ueberhaupt neu gerechnet wurde.
        assert m.thunder_level_max == ThunderLevel.HIGH, (
            "das Segment wurde gar nicht neu gerechnet"
        )
        assert m.thunder_level_max_signals == ["cape"], (
            f"die Traeger der Hoechststufe sind bei der Neuberechnung "
            f"verlorengegangen: {m.thunder_level_max_signals!r}"
        )


# ---------------------------------------------------------------------------
# Das Hagel-Kennzeichen ueberlebt die Neuberechnung
#
# ``compute_extended_metrics`` kopiert ``hail_flag`` NICHT mit (dieselbe Naht
# wie ``thunder_level_max_signals`` oben, #1391/#1392/#1468). Anders als
# dieses Feld hing der Schutz dafuer bislang an KEINEM Test in dieser Datei —
# nur an den Kanal-Renderern in ``test_hail_flag_channel_rendering.py``, die
# das Symptom (fehlender Hinweistext), nicht die Ursache (Restfenster-
# Neuberechnung) bewachen.
# ---------------------------------------------------------------------------

class TestHagelKennzeichenUeberlebtDieNeuberechnung:
    def test_hail_flag_bleibt_am_neu_gerechneten_aggregat(
        self, tmp_path: Path,
    ) -> None:
        """
        GIVEN ein beschnittenes Segment, dessen Restfenster eine bestaetigte
              Hagelstunde traegt,
        WHEN sein Aggregat neu berechnet wird,
        THEN bleibt ``hail_flag`` True am neu gerechneten Aggregat.
        """
        _speichere(tmp_path, [_segment(
            8, 6, 12,
            # Weder Flag noch sonst etwas vorbelegt: was unten steht, ist
            # gerechnet, nicht durchgereicht.
            aggregiert=SegmentWeatherSummary(temp_max_c=99.9),
            stunden=(
                [_punkt(h, **FRUEH) for h in (6, 7, 8, 9)]
                + [_punkt(10, hail_flag=True, **SPAET)]
                + [_punkt(11, **SPAET)]
            ),
        )])

        ergebnis = _extractor(tmp_path).timeline("tour-2186", from_time=_um_zehn())
        m = ergebnis.points[0].metrics

        # Beweist, dass ueberhaupt neu gerechnet wurde -- sonst waere
        # ``hail_flag`` auch durch blosses Durchreichen des Alt-Werts erfuellt.
        assert m.temp_min_c == 15.0, "das Segment wurde gar nicht neu gerechnet"
        assert m.hail_flag is True, (
            "hail_flag ist bei der Neuberechnung verlorengegangen"
        )
