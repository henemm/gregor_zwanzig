"""TDD RED -- #1531 S1 AC-9: die neuen Rohwerte aendern KEINE Ausgabe.
-- seit Issue #1757 gilt das nur noch fuer SECHS der sieben Felder,
s. Abschnitt POLITIKWECHSEL weiter unten.

Spec: docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md (AC-9)

Diese Scheibe liefert AUSSCHLIESSLICH Rohwerte ins Datenmodell (Scope-
Abgrenzung: "keine Einstufung, keine Schwellen, keine Fusion in
thunder_level, keine Katalogmetrik, keine Ausgabe in Mail/SMS/Telegram/
Compare"). Faengt schon hier eine bestehende Rendering- oder
Einstufungsfunktion an, eines der sieben neuen Felder mitzulesen, entstuende
eine zweite, konkurrierende Gewitteraussage.

Bauart des Nachweises (Muster
test_thunder_raw_signals_do_not_change_outputs.py, #1457 S2b AC-8): dieselbe
Vorhersage/derselbe Ortsvergleich wird zweimal gerendert -- einmal ohne die
sieben neuen Felder, einmal mit ABSICHTLICH EXTREMEN Werten. Wuerde
irgendeine bestehende Funktion sie mitlesen, muesste sich die Ausgabe
unterscheiden. Ein unauffaelliger Wert wuerde diesen Beweis nicht tragen.

Vier Kanaele geprueft (SMS, Gewitterstufen-Aggregation, Compare-Mail,
Trip-Briefing-Mail) -- breiter als das S2b-Vorbild (nur SMS + Aggregation),
weil die Spec hier explizit "Briefing-Mail, Compare-Mail und SMS" nennt.

RED-GRUND (heute, unveraenderter Code): `ForecastDataPoint` kennt keines der
sieben neuen Felder -> TypeError beim Bauen des Vergleichsfalls.

POLITIKWECHSEL SEIT ISSUE #1757 (PO-Entscheid Variante A, 2026-08-19):
Fuer EINES der sieben Felder gilt die Invarianz-Zusicherung nicht mehr.
``lightning_potential_max_lpi_jkg`` (das DWD-Stundenmaximum des
Blitzpotenzials) ist seit #1757 AUSDRUECKLICH ausgabewirksam -- die Fusion
``_fuse_thunder_levels()`` bevorzugt es vor dem Momentanwert
``lightning_potential_lpi_jkg``, weil ein Backtest vom 2026-08-11 fuer den
Momentanwert einen Recall von 5,6 % gemessen hat (1 von 18 echten
Gewitterstunden). Das Feld ist deshalb aus ``_EXTREME_NEUE_FELDER``
herausgenommen und hat einen EIGENEN Test bekommen, der das Gegenteil der
alten Zusicherung prueft (s. unten,
``test_1757_stundenmaximum_ist_seit_1757_ausgabewirksam_...``). Die uebrigen
SECHS Felder behalten ihre Invarianz-Zusicherung unveraendert. Wer hier eine
abgeschwaechte Ratsche vermutet: das ist ein bewusster, spezifizierter
Wechsel (docs/specs/modules/feat_1757_lpi_max_fusion.md, AC-9), kein
Wackelkontakt.

Testart: Kern-Schicht, keine Netzzugriffe, keine Mocks.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.renderers.sms_trip import SMSTripFormatter  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from services.weather_metrics import WeatherMetricsService  # noqa: E402

_JAHR, _MONAT, _TAG = 2026, 8, 11
_TZ = ZoneInfo("UTC")
_START_H, _ENDE_H = 7, 17

# Absichtlich extrem -- deutlich ausserhalb jedes real gemessenen Bereichs
# der jeweiligen Groesse (s. Modul-Docstrings der Provider-Tests dieser
# Scheibe: sdi_2 ~ -0,0001, uh_max ~ -123, cape_ml ~ 753/20).
# SEIT #1757 nur noch SECHS Felder: `lightning_potential_max_lpi_jkg` steht
# hier BEWUSST NICHT mehr -- es ist ausgabewirksam geworden (s. Modul-Docstring
# und der eigene Test am Dateiende). Wieder aufnehmen darf es nur, wer #1757
# zurueckdreht.
_EXTREME_NEUE_FELDER = {
    "supercell_index_sdi2_1s": -50.0,
    "convective_inhibition_jkg": 900.0,
    "cape_ml_jkg": 6000.0,
    "updraft_helicity_max_m2s2": 500.0,
    "updraft_helicity_max_med_m2s2": 500.0,
    "updraft_helicity_max_low_m2s2": 500.0,
}


def _dp(stunde: int, thunder: ThunderLevel, mit_neuen_feldern: bool) -> ForecastDataPoint:
    neu = _EXTREME_NEUE_FELDER if mit_neuen_feldern else {}
    return ForecastDataPoint(
        ts=datetime(_JAHR, _MONAT, _TAG, stunde, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
        cloud_total_pct=50, thunder_level=thunder, humidity_pct=55,
        **neu,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(_JAHR, _MONAT, _TAG, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _reihe(mit_neuen_feldern: bool) -> NormalizedTimeseries:
    """24 Stunden mit einem MED-Gewitter um 09:00 und HIGH um 14:00 -- so
    tragen die Ausgaben ueberhaupt eine Gewitteraussage, an der eine
    Verfaelschung sichtbar wuerde."""
    stufen = {9: ThunderLevel.MED, 14: ThunderLevel.HIGH}
    daten = [
        _dp(h, stufen.get(h, ThunderLevel.NONE), mit_neuen_feldern) for h in range(24)
    ]
    return NormalizedTimeseries(meta=_meta(), data=daten)


def _segment(mit_neuen_feldern: bool) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.40, lon=12.52, elevation_m=1800.0),
        end_point=GPXPoint(lat=46.45, lon=12.60, elevation_m=2100.0),
        start_time=datetime(_JAHR, _MONAT, _TAG, _START_H, 0, tzinfo=timezone.utc),
        end_time=datetime(_JAHR, _MONAT, _TAG, _ENDE_H, 0, tzinfo=timezone.utc),
        duration_hours=float(_ENDE_H - _START_H),
        distance_km=14.0, ascent_m=600.0, descent_m=300.0,
    )
    ts = _reihe(mit_neuen_feldern)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=15.0,
            gust_max_kmh=25.0, precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.HIGH,
        ),
        fetched_at=datetime(_JAHR, _MONAT, _TAG, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _sms(mit_neuen_feldern: bool) -> str:
    return SMSTripFormatter().format_sms(
        [_segment(mit_neuen_feldern)],
        stage_name="Karnisch-1", report_type="morning", tz=_TZ,
    )


def _briefing_mail(mit_neuen_feldern: bool):
    return TripReportFormatter().format_email(
        [_segment(mit_neuen_feldern)],
        trip_name="Test-Trip", report_type="morning", tz=_TZ,
    )


def _compare_result(mit_neuen_feldern: bool) -> ComparisonResult:
    loc = SavedLocation(id="loc-1", name="Karnischer Hoehenweg", lat=46.40, lon=12.52, elevation_m=1800)
    ts = _reihe(mit_neuen_feldern)
    lr = LocationResult(
        location=loc, score=50, temp_max=20.0, temp_min=10.0, wind_max=15.0,
        gust_max=25.0, cloud_avg=50, sunny_hours=3, official_alerts=[],
        hourly_data=ts.data,
    )
    return ComparisonResult(
        locations=[lr], time_window=(_START_H, _ENDE_H),
        target_date=date(_JAHR, _MONAT, _TAG),
        created_at=datetime(_JAHR, _MONAT, _TAG, 4, 0),
    )


def test_ac9_sms_bleibt_mit_und_ohne_die_neuen_rohwerte_identisch():
    """AC-9 (Kanal 1/4, SMS): Given dieselbe Vorhersage einmal mit und einmal
    ohne gesetzte neue Gewitter-Rohwerte, When die SMS gerendert wird, Then
    ist der Text zeichengleich."""
    ohne = _sms(False)
    mit = _sms(True)
    assert "TH:" in ohne, f"SMS traegt keine Gewitteraussage -- Vergleich pruefte nichts.\nSMS: {ohne}"
    assert mit == ohne, (
        f"SMS aendert sich, sobald die sieben neuen Rohwerte gesetzt sind.\nohne: {ohne}\nmit : {mit}"
    )


def test_ac9_gewitterstufe_bleibt_mit_und_ohne_die_neuen_rohwerte_identisch():
    """AC-9 (Kanal 2/4, Aggregation): Given dieselbe Zeitreihe mit und ohne
    die neuen Rohwerte, When die Gewitterstufe aggregiert wird, Then ist sie
    identisch -- ADR-0025 verbietet eine zweite, konkurrierende
    Gewitter-Quelle im selben Briefing."""
    dienst = WeatherMetricsService()
    ohne = dienst._compute_thunder_level(_reihe(False))
    mit = dienst._compute_thunder_level(_reihe(True))
    assert ohne is not None, "Ohne die neuen Felder kommt gar keine Stufe heraus"
    assert mit == ohne, f"Gewitterstufe aendert sich von {ohne} auf {mit}"


def test_ac9_compare_mail_bleibt_mit_und_ohne_die_neuen_rohwerte_identisch():
    """AC-9 (Kanal 3/4, Compare-Mail): Given denselben Ortsvergleich einmal
    mit und einmal ohne die neuen Rohwerte, When die Compare-Mail (HTML +
    Klartext) gerendert wird, Then sind beide Teile zeichengleich."""
    from output.renderers.comparison import render_compare_email

    html_ohne, text_ohne = render_compare_email(_compare_result(False))
    html_mit, text_mit = render_compare_email(_compare_result(True))
    assert text_ohne.strip(), "Compare-Klartext ist leer -- Vergleich pruefte nichts"
    assert html_mit == html_ohne, "Compare-Mail-HTML aendert sich durch die neuen Rohwerte"
    assert text_mit == text_ohne, "Compare-Mail-Klartext aendert sich durch die neuen Rohwerte"


def test_ac9_briefing_mail_bleibt_mit_und_ohne_die_neuen_rohwerte_identisch():
    """AC-9 (Kanal 4/4, Trip-Briefing-Mail): Given dasselbe Segment einmal mit
    und einmal ohne die neuen Rohwerte, When das Trip-Briefing (HTML +
    Klartext + Betreff) gerendert wird, Then sind alle drei Teile
    zeichengleich."""
    ohne = _briefing_mail(False)
    mit = _briefing_mail(True)
    assert ohne.email_html.strip(), "Briefing-HTML ist leer -- Vergleich pruefte nichts"
    assert mit.email_subject == ohne.email_subject, "Briefing-Betreff aendert sich durch die neuen Rohwerte"
    assert mit.email_html == ohne.email_html, "Briefing-HTML aendert sich durch die neuen Rohwerte"
    assert mit.email_plain == ohne.email_plain, "Briefing-Klartext aendert sich durch die neuen Rohwerte"


# =============================================================================
# #1757 AC-9: umgedrehte Zusicherung fuer `lightning_potential_max_lpi_jkg`
# =============================================================================

def _gefuste_reihe(lpi_max: float | None) -> NormalizedTimeseries:
    """Eine Reihe OHNE vorgesetzte ``thunder_level``, durch den ECHTEN
    Produktionspfad ``_fuse_thunder_levels()`` geschickt. Nur so wird die
    Frage ueberhaupt gestellt: die vier Invarianz-Tests oben setzen
    ``thunder_level`` von Hand und ueberspringen die Fusion -- an ihnen
    waere der Politikwechsel des #1757 UNSICHTBAR geblieben.

    Momentanwert konstant 12,0 J/kg (DE_ALPEN-Leiter 1/30/50 -> LOW),
    Stundenmaximum wahlweise 40,0 J/kg (-> MED). Die beiden Zahlen liegen
    absichtlich auf VERSCHIEDENEN Sprossen -- sonst waere das Ergebnis
    unabhaengig von der Auswahl gleich.
    """
    from app.model_registry import lpi_thresholds_jkg
    from providers.thunder_enrichment import _fuse_thunder_levels

    daten = [
        ForecastDataPoint(
            ts=datetime(_JAHR, _MONAT, _TAG, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
            cloud_total_pct=50, humidity_pct=55, thunder_level=None,
            lightning_density_per_km2_3h=None, cape_jkg=None,
            lightning_potential_lpi_jkg=12.0,
            lightning_potential_max_lpi_jkg=lpi_max,
        )
        for h in range(24)
    ]
    _fuse_thunder_levels(daten, None, lpi_thresholds_jkg("DE_ALPEN"))
    return NormalizedTimeseries(meta=_meta(), data=daten)


def test_1757_stundenmaximum_ist_seit_1757_ausgabewirksam_entgegen_der_alten_zusicherung():
    """#1757 AC-9 -- POLITIKWECHSEL, umgekehrte Erwartung.

    BIS #1757 sicherte diese Datei zu, dass ``lightning_potential_max_lpi_jkg``
    KEINE Ausgabe aendert (#1531 S1 AC-9: reine Rohwert-Scheibe, "keine
    Fusion in thunder_level"). SEIT #1757 (PO-Entscheid Variante A,
    2026-08-19, docs/specs/modules/feat_1757_lpi_max_fusion.md) gilt das
    Gegenteil: das Stundenmaximum wird VORRANGIG in die Gewitterstufe
    fusioniert, der Momentanwert ist nur noch Rueckfall.

    Given zwei identische Vorhersagen mit demselben Momentanwert (12,0 J/kg),
    von denen eine zusaetzlich ein abweichendes Stundenmaximum (40,0 J/kg)
    traegt / When beide durch die Fusion und danach durch die
    Gewitterstufen-Aggregation laufen / Then unterscheiden sich die Stufen
    (LOW gegen MED) -- das Stundenmaximum ist ausgabewirksam.

    Der Test ist die Ratsche gegen ein stilles Zurueckdrehen: faellt die
    Auswahl in ``_fuse_thunder_levels()`` wieder auf den Momentanwert, sind
    beide Stufen LOW und dieser Test wird rot.

    WARUM DIESER TEST EIGENS GEBAUT WERDEN MUSSTE -- bitte nicht als
    Redundanz zu den vier Invarianz-Tests oben wegkuerzen: **der alte
    Waechter war fuer diese Frage BLIND.** Er setzt ``thunder_level`` von
    Hand am Datenpunkt und rendert dann; der Renderpfad liest
    ``dp.thunder_level`` und nie ``lightning_potential_max_lpi_jkg``, die
    Fusion ``_fuse_thunder_levels()`` laeuft dabei ueberhaupt nicht. Alle
    vier Tests oben waeren nach der Umstellung durch #1757 unveraendert
    gruen geblieben -- sie haetten den Politikwechsel nicht bemerkt. Ein
    blosses Umdrehen ihrer Erwartung haette also nichts bewacht: geprueft
    wurde dort, wo der Code steht (der Renderer), nicht dort, wo die
    Zusicherung WIRKT (die Fusion). Deshalb geht dieser Test von einer Reihe
    OHNE vorgesetztes ``thunder_level`` aus und schickt sie durch den echten
    Produktionspfad.
    """
    dienst = WeatherMetricsService()
    ohne_max = dienst._compute_thunder_level(_gefuste_reihe(None))
    mit_max = dienst._compute_thunder_level(_gefuste_reihe(40.0))

    assert ohne_max == ThunderLevel.LOW, (
        "Vorbedingung: ohne Stundenmaximum traegt der Momentanwert 12,0 J/kg "
        f"die Stufe LOW (DE_ALPEN 1/30/50), erhalten {ohne_max!r}"
    )
    assert mit_max == ThunderLevel.MED, (
        "Das Stundenmaximum 40,0 J/kg muss die Stufe auf MED heben. Erhalten "
        f"{mit_max!r}. LOW bedeutet: die Fusion liest weiterhin den "
        "Momentanwert -- #1757 ist still zurueckgedreht."
    )


def test_1757_stundenmaximum_veraendert_auch_die_gerenderte_sms():
    """#1757 AC-9, zweiter Teil: der Wechsel ist nicht nur in der Aggregation,
    sondern bis in eine ECHTE Ausgabe hinein sichtbar -- sonst waere
    "ausgabewirksam" nur behauptet. Dieselben zwei Reihen wie oben, durch den
    SMS-Renderer geschickt: die Texte muessen sich unterscheiden.

    WARUM NICHT EINFACH DIE VIER TESTS OBEN UMDREHEN -- bitte nicht als
    Doppelung wegkuerzen: **der alte Waechter war fuer diese Frage BLIND**,
    weil er ``thunder_level`` von Hand setzt und damit die Fusion
    ueberspringt (ausfuehrlich im Docstring des vorigen Tests). Er prueft
    den Renderpfad, nicht die Fusion. Dieser Test schliesst die Luecke an
    genau der Naht: er laesst die Fusion die Stufe BESTIMMEN und rendert
    erst danach -- so haengt die SMS nachweisbar am Stundenmaximum und nicht
    an einem von Hand gesetzten Wert.
    """
    def _sms_aus(reihe: NormalizedTimeseries) -> str:
        seg = _segment(False)
        stufe = WeatherMetricsService()._compute_thunder_level(reihe)
        seg.timeseries = reihe
        seg.aggregated.thunder_level_max = stufe
        return SMSTripFormatter().format_sms(
            [seg], stage_name="Karnisch-1", report_type="morning", tz=_TZ,
        )

    ohne = _sms_aus(_gefuste_reihe(None))
    mit = _sms_aus(_gefuste_reihe(40.0))

    assert "TH:" in ohne, (
        f"SMS traegt keine Gewitteraussage -- der Vergleich pruefte nichts.\nSMS: {ohne}"
    )
    assert mit != ohne, (
        "Die SMS ist mit und ohne Stundenmaximum zeichengleich -- das Signal "
        f"erreicht die Ausgabe nicht.\nohne: {ohne}\nmit : {mit}"
    )
