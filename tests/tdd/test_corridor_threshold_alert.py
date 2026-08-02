"""TDD RED — Issue #1444 Scheibe 1: Schwellen-Alarm.

SPEC: docs/specs/modules/feat_1444_s1_schwellen_alarm.md
AC-1..AC-6

Verhaltenstests aus Nutzersicht — KEINE Mocks. Echte `TripAlertService`-Laeufe,
echte `alert_state`-Persistenz, echte Renderer; ersetzt wird ausschliesslich der
SMTP-Transport ueber die vorhandene `mail_sink`-DI-Naht (Projektkonvention,
Vorbild `test_issue_1088_official_alert_triggers.py`).

Der Vergleichsstand (`cached`) ist in fast allen Faellen **wertgleich** mit dem
frischen Stand — genau das ist der Kern des Tickets: der Aenderungs-Waechter
findet nichts, der Schwellen-Waechter muss trotzdem melden.

RED-Ursache (heute, vor der Implementierung):
- `services.corridor_threshold` existiert nicht -> ImportError (AC-1).
- `TripAlertService.check_and_send_alerts()` wertet `trip.corridors` nicht aus
  -> kein Versand, `mail_calls` bleibt leer (AC-1, AC-4, AC-5, AC-6).
- Eine Tour, deren einzige Alarmquelle Wertebereiche sind, faellt durch den
  `has_active_rules`-Gate -> `check_all_trips()` meldet 0 (AC-5).
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import (
    Corridor,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from services.trip_alert import TripAlertService

# Pfadregel #1409: Pruefling relativ zur Testdatei, nicht ueber den Hauptrepo-Pfad.
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

LAT, LON = 47.0, 11.0


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1444-{prefix}-{uuid.uuid4().hex[:6]}"


def _segment(segment_id: int | str = 1) -> TripSegment:
    """Etappe im aktiven Fenster: beginnt heute, endet in der Zukunft."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1)
    end = now + timedelta(hours=3)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _corridor_trip(trip_id: str, corridors: list[Corridor], *, with_delta_source: bool = False) -> Trip:
    """Tour, deren Alarmquelle die Wertebereiche sind.

    `with_delta_source=False` (Default) bildet den Fall aus AC-5 ab: keine
    Aenderungs-Empfindlichkeiten, keine Voreinstellung, `alert_on_changes=False`
    — die Wertebereiche sind die **einzige** eingestellte Alarmquelle.
    """
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    kwargs: dict = {"official_warnings": None, "corridors": corridors}
    if with_delta_source:
        kwargs["display_config"] = UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="precipitation", enabled=True)],
            metric_alert_levels={"precipitation_sum": "standard"},
        )
    trip = Trip(id=trip_id, name="Schwellen-Trip", stages=[stage], **kwargs)
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email=True,
        alert_on_changes=with_delta_source,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def _service(user_id: str, sink: list) -> TripAlertService:
    return TripAlertService(
        user_id=user_id,
        mail_sink=lambda subject, body: sink.append((subject, body)),
    )


# --------------------------------------------------------------------------
# AC-1: Grenze gerissen bei unveraenderter Vorhersage -> genau eine Meldung
# --------------------------------------------------------------------------

def test_ac1_gewitter_grenze_gerissen_meldet_trotz_unveraenderter_vorhersage():
    """GIVEN Gewitter-Grenze "hoechstens keins", Vorhersage zeigt Gewitter,
    Vorher- und Jetzt-Stand sind wertgleich
    WHEN der Alarm-Lauf die Tour prueft
    THEN geht genau eine Meldung raus, die Groesse, Wert und Etappe benennt."""
    user_id = _fresh_user("ac1")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac1",
            [Corridor(metric="thunder_level", range=[None, 0], notify=True)],
        )
        # Wertgleich: der Aenderungs-Waechter findet hier nichts.
        cached = [_data(1, thunder_level_max=ThunderLevel.MED)]
        fresh = [_data(1, thunder_level_max=ThunderLevel.MED)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert sent is True, (
            "Gerissene Gewitter-Grenze bei unveraenderter Vorhersage muss eine "
            "Meldung ausloesen — der Aenderungs-Waechter allein bleibt hier stumm"
        )
        assert len(mail_calls) == 1, f"Erwartet genau 1 Meldung, erhalten: {len(mail_calls)}"
        _, body = mail_calls[0]
        assert "Gewitter" in body, "Die Wettergroesse fehlt in der Meldung"
    finally:
        _clean_user(user_id)


def test_ac1_auswertungsbaustein_liefert_treffer_mit_grenze_und_istwert():
    """GIVEN ein Wetterstand ueber der eingestellten Regen-Grenze
    WHEN der Auswertungs-Baustein laeuft
    THEN liefert er einen Treffer mit Metrik, Ist-Wert, gerissener Grenze und Etappe."""
    from services.corridor_threshold import evaluate_corridor_thresholds

    hits = evaluate_corridor_thresholds(
        [_data(1, precip_sum_mm=7.5)],
        [Corridor(metric="precipitation_sum", range=[None, 1], notify=True)],
    )

    assert len(hits) == 1, f"Erwartet genau 1 Treffer, erhalten: {hits!r}"
    hit = hits[0]
    assert hit.metric == "precipitation_sum"
    assert hit.value == pytest.approx(7.5)
    assert hit.bound == pytest.approx(1.0)
    assert str(hit.segment_id) == "1"


# --------------------------------------------------------------------------
# AC-2: Grenze eingehalten -> keine Meldung
# --------------------------------------------------------------------------

def test_ac2_eingehaltene_grenzen_melden_nicht():
    """GIVEN alle eingestellten Grenzen sind eingehalten
    WHEN der Alarm-Lauf die Tour prueft
    THEN geht keine Meldung raus."""
    user_id = _fresh_user("ac2")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac2",
            [
                Corridor(metric="thunder_level", range=[None, 0], notify=True),
                Corridor(metric="precipitation_sum", range=[None, 1], notify=True),
            ],
        )
        stand = dict(thunder_level_max=ThunderLevel.NONE, precip_sum_mm=0.4)
        cached = [_data(1, **stand)]
        fresh = [_data(1, **stand)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert sent is False, "Eingehaltene Grenzen duerfen keine Meldung ausloesen"
        assert mail_calls == [], f"Unerwartete Meldung: {mail_calls!r}"
    finally:
        _clean_user(user_id)


def test_ac2_grenzwert_selbst_gilt_als_eingehalten():
    """GIVEN der Wert liegt exakt auf der eingestellten Grenze
    WHEN der Auswertungs-Baustein laeuft
    THEN gilt die Grenze als eingehalten (kein Treffer)."""
    from services.corridor_threshold import evaluate_corridor_thresholds

    hits = evaluate_corridor_thresholds(
        [_data(1, gust_max_kmh=20.0)],
        [Corridor(metric="wind_gust", range=[None, 20], notify=True)],
    )
    assert hits == [], f"Der Grenzwert selbst zaehlt als eingehalten, erhalten: {hits!r}"


# --------------------------------------------------------------------------
# AC-3: unveraenderte Lage -> keine zweite Meldung
# --------------------------------------------------------------------------

def test_ac3_unveraenderte_lage_meldet_kein_zweites_mal():
    """GIVEN eine bereits gemeldete gerissene Grenze
    WHEN der Alarm-Lauf mit unveraenderter Lage erneut laeuft
    THEN geht keine zweite Meldung raus."""
    user_id = _fresh_user("ac3")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac3",
            [Corridor(metric="thunder_level", range=[None, 0], notify=True)],
        )
        cached = [_data(1, thunder_level_max=ThunderLevel.MED)]
        fresh = [_data(1, thunder_level_max=ThunderLevel.MED)]

        mail_calls: list = []
        svc = _service(user_id, mail_calls)
        svc.check_and_send_alerts(trip, cached, fresh_weather=fresh)
        svc.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert len(mail_calls) == 1, (
            f"Anhaltende, unveraenderte Lage darf nur EINE Meldung erzeugen, "
            f"erhalten: {len(mail_calls)}"
        )
    finally:
        _clean_user(user_id)


# --------------------------------------------------------------------------
# AC-4: Verschaerfung und Rueckfall melden erneut
# --------------------------------------------------------------------------

def test_ac4_verschaerfung_meldet_erneut():
    """GIVEN eine bereits gemeldete gerissene Gewitter-Grenze
    WHEN die Lage sich um eine Stufe verschaerft
    THEN geht erneut eine Meldung raus."""
    user_id = _fresh_user("ac4a")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac4a",
            [Corridor(metric="thunder_level", range=[None, 0], notify=True)],
        )
        mail_calls: list = []
        svc = _service(user_id, mail_calls)

        mittel = [_data(1, thunder_level_max=ThunderLevel.MED)]
        hoch = [_data(1, thunder_level_max=ThunderLevel.HIGH)]
        svc.check_and_send_alerts(trip, mittel, fresh_weather=mittel)
        svc.check_and_send_alerts(trip, hoch, fresh_weather=hoch)

        assert len(mail_calls) == 2, (
            f"Eine Verschaerfung um eine Stufe muss erneut melden, "
            f"erhalten: {len(mail_calls)} Meldung(en)"
        )
    finally:
        _clean_user(user_id)


def test_ac4_rueckfall_nach_entspannung_meldet_erneut():
    """GIVEN eine gemeldete Grenzverletzung, die sich zwischenzeitlich entspannt
    WHEN die Grenze spaeter erneut gerissen wird
    THEN meldet der Waechter wieder."""
    user_id = _fresh_user("ac4b")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac4b",
            [Corridor(metric="precipitation_sum", range=[None, 1], notify=True)],
        )
        mail_calls: list = []
        svc = _service(user_id, mail_calls)

        gerissen = [_data(1, precip_sum_mm=6.0)]
        ruhig = [_data(1, precip_sum_mm=0.2)]
        svc.check_and_send_alerts(trip, gerissen, fresh_weather=gerissen)
        svc.check_and_send_alerts(trip, ruhig, fresh_weather=ruhig)
        svc.check_and_send_alerts(trip, gerissen, fresh_weather=gerissen)

        assert len(mail_calls) == 2, (
            f"Nach Entspannung muss ein erneutes Reissen wieder melden, "
            f"erhalten: {len(mail_calls)} Meldung(en)"
        )
    finally:
        _clean_user(user_id)


# --------------------------------------------------------------------------
# Bugfix (Team-Lead-Befund): die Auswertung MUSS gegen die frische
# Vorhersage laufen, nicht gegen den (potenziell Stunden alten) Schnappschuss
# des letzten Briefings -- sonst dreht sich der Zweck der Funktion in beide
# Richtungen um: ein NEU aufgezogenes Gewitter wird verschwiegen, ein
# ABGEZOGENES loest einen Falschalarm aus.
# --------------------------------------------------------------------------

def test_neu_aufgezogenes_gewitter_seit_dem_schnappschuss_wird_gemeldet():
    """GIVEN der Schnappschuss (letztes Briefing) zeigt KEIN Gewitter, die
    FRISCHE Vorhersage zeigt Gewitter -- Grenze "hoechstens keins"
    WHEN der Alarm-Lauf prueft
    THEN wird gemeldet. Genau die Luecke, die #1444 schliessen soll: ein
    Bug, der gegen den alten Schnappschuss statt die frische Vorhersage
    auswertet, waere hier stumm."""
    user_id = _fresh_user("freshbug1")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-freshbug1",
            [Corridor(metric="thunder_level", range=[None, 0], notify=True)],
        )
        cached = [_data(1, thunder_level_max=ThunderLevel.NONE)]
        fresh = [_data(1, thunder_level_max=ThunderLevel.MED)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, cached, fresh_weather=fresh,
        )

        assert sent is True, (
            "Ein seit dem Schnappschuss NEU aufgezogenes Gewitter muss "
            "gemeldet werden -- die Auswertung darf nicht gegen den alten "
            "Schnappschuss laufen"
        )
        assert len(mail_calls) == 1
        assert "Gewitter" in mail_calls[0][1]
    finally:
        _clean_user(user_id)


def test_abgezogenes_gewitter_seit_dem_schnappschuss_meldet_nicht_mehr():
    """GIVEN der Schnappschuss zeigt Gewitter, die FRISCHE Vorhersage ist
    ruhig -- Grenze "hoechstens keins"
    WHEN der Alarm-Lauf prueft
    THEN wird NICHT gemeldet. Ein Bug, der gegen den alten Schnappschuss
    auswertet, wuerde hier einen Falschalarm fuer eine Lage ausloesen, die
    es nicht mehr gibt."""
    user_id = _fresh_user("freshbug2")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-freshbug2",
            [Corridor(metric="thunder_level", range=[None, 0], notify=True)],
        )
        cached = [_data(1, thunder_level_max=ThunderLevel.MED)]
        fresh = [_data(1, thunder_level_max=ThunderLevel.NONE)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, cached, fresh_weather=fresh,
        )

        assert sent is False, (
            "Ein seit dem Schnappschuss abgezogenes Gewitter darf keinen "
            "Falschalarm ausloesen -- die Auswertung darf nicht gegen den "
            "alten Schnappschuss laufen"
        )
        assert mail_calls == []
    finally:
        _clean_user(user_id)


# --------------------------------------------------------------------------
# AC-5: Wertebereiche als einzige Alarmquelle; Gewitter UND Regen
#
# Bewusst in ZWEI Teile getrennt (Team-Lead-Vorgabe): `result.checked`
# zaehlt in `check_all_trips()` JEDE iterierte Tour, UNABHAENGIG davon, ob
# der `has_active_rules`-Gate sie anschliessend per `continue` uebersprungen
# haette (`checked += 1` steht VOR dem Gate) -- ein Test auf
# `result.checked == 1` waere also immer gruen und wuerde nichts pruefen
# (Ratchet-Anti-Pattern). Stattdessen:
#
# 1. Der Gate-Nachweis fuer `check_all_trips()` laeuft ueber die REGEN-Groesse:
#    der Fixture-Provider liefert fuer den Testort deterministisch (statisches
#    JSON, kein Live-Zufall) precip_sum_mm=1.2 im aktiven Fenster -- reisst die
#    Grenze [None, 1] zuverlaessig. `alerts_sent == 1` ist damit ein echter
#    End-to-End-Nachweis: ohne den `has_active_rules`-Fix waere die Tour VOR
#    `_get_cached_weather()` per `continue` uebersprungen und alerts_sent
#    bliebe 0.
# 2. Beide Groessen (Gewitter UND Regen) werden zusaetzlich deterministisch
#    ueber `check_and_send_alerts()` mit explizitem `fresh_weather` bewiesen
#    (kein Fixture-Zufall, keine Abhaengigkeit vom Live-Wetterstand).
# --------------------------------------------------------------------------

def test_ac5_wertebereich_als_einzige_alarmquelle_wird_von_check_all_trips_geprueft():
    """GIVEN eine Tour, deren einzige eingestellte Alarmquelle ein Wertebereich
    ist (Regen, deterministisch ueber den Fixture-Provider gerissen)
    WHEN der Alarm-Lauf ueber ALLE Touren laeuft (`check_all_trips()`)
    THEN wird sie geprueft und meldet -- der `has_active_rules`-Gate in
    `check_all_trips()` (separat vom Gate in `check_and_send_alerts()`) darf
    sie nicht mehr uebersprungen haben."""
    from app.loader import save_trip
    from services.weather_snapshot import WeatherSnapshotService

    user_id = _fresh_user("ac5gate")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac5gate",
            [Corridor(metric="precipitation_sum", range=[None, 1], notify=True)],
        )
        save_trip(trip, user_id=user_id)
        # Schnappschuss-Inhalt ist fuer diesen Nachweis irrelevant (nur noch
        # als "Vorhersage vorhanden"-Gate genutzt) -- die Auswertung laeuft
        # gegen die FRISCH ueber den Fixture-Provider geholte Vorhersage.
        WeatherSnapshotService(user_id=user_id).save_dated(
            trip.id, date.today(), [_data(1, precip_sum_mm=0.0)]
        )

        mail_calls: list = []
        result = _service(user_id, mail_calls).check_all_trips()

        assert result.alerts_sent == 1, (
            "Eine Tour, deren einzige Alarmquelle ein Wertebereich ist, wird "
            f"heute vom Lauf uebersprungen — erhalten: alerts_sent={result.alerts_sent}"
        )
        assert len(mail_calls) == 1
        assert "Niedersch" in mail_calls[0][1], (
            f"'Niedersch' fehlt in der Meldung: {mail_calls[0][1][:400]!r}"
        )
    finally:
        _clean_user(user_id)


@pytest.mark.parametrize(
    "corridor,stand,erwartetes_wort",
    [
        (Corridor(metric="thunder_level", range=[None, 0], notify=True),
         dict(thunder_level_max=ThunderLevel.MED), "Gewitter"),
        # "Niedersch" = `alert_label` der Katalog-Metrik `precipitation`
        # (gegen die Wirklichkeit geprueft, nicht geraten).
        (Corridor(metric="precipitation_sum", range=[None, 1], notify=True),
         dict(precip_sum_mm=9.0), "Niedersch"),
    ],
    ids=["gewitter-stufig", "regen-stetig"],
)
def test_ac5_wertebereich_als_einzige_alarmquelle_meldet_die_gerissene_grenze(
    corridor, stand, erwartetes_wort,
):
    """GIVEN eine Tour, deren einzige eingestellte Alarmquelle Wertebereiche
    sind (Gewitter ODER Regen, deterministisch ueber explizites
    `fresh_weather`, kein Fixture-Zufall)
    WHEN `check_and_send_alerts()` laeuft
    THEN meldet sie die gerissene Grenze mit der erwarteten Groesse."""
    user_id = _fresh_user("ac5msg")
    _clean_user(user_id)
    try:
        trip = _corridor_trip("trip-ac5msg", [corridor])
        fresh = [_data(1, **stand)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, fresh, fresh_weather=fresh,
        )

        assert sent is True, (
            "Eine Tour, deren einzige Alarmquelle Wertebereiche sind, wird "
            "heute vom has_active_rules-Gate uebersprungen"
        )
        assert len(mail_calls) == 1
        assert erwartetes_wort in mail_calls[0][1], (
            f"{erwartetes_wort!r} fehlt in der Meldung: {mail_calls[0][1][:400]!r}"
        )
    finally:
        _clean_user(user_id)


# --------------------------------------------------------------------------
# AC-6: eine Nachricht, kein erfundenes "vorher"
# --------------------------------------------------------------------------

def test_ac6_schwelle_und_aenderung_ergeben_eine_nachricht_ohne_erfundenes_vorher():
    """GIVEN ein Lauf, in dem eine Grenze gerissen ist UND der Aenderungs-Waechter anschlaegt
    WHEN die Meldung erzeugt wird
    THEN geht genau eine Nachricht raus, deren Schwellen-Anteil die Grenze nennt
    und keinen Vorher-Wert von 0 behauptet."""
    user_id = _fresh_user("ac6")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac6",
            [Corridor(metric="thunder_level", range=[None, 0], notify=True)],
            with_delta_source=True,
        )
        # Regen springt deutlich (Aenderungs-Waechter), Gewitter reisst die Grenze.
        cached = [_data(1, precip_sum_mm=2.0, thunder_level_max=ThunderLevel.MED)]
        fresh = [_data(1, precip_sum_mm=18.0, thunder_level_max=ThunderLevel.MED)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert sent is True
        assert len(mail_calls) == 1, (
            f"Schwellen- und Aenderungs-Treffer eines Laufs muessen in EINER "
            f"Nachricht landen, erhalten: {len(mail_calls)}"
        )
        _, body = mail_calls[0]
        assert "Gewitter" in body, "Der Schwellen-Anteil fehlt in der gebuendelten Nachricht"
        assert "Niedersch" in body, "Der Aenderungs-Anteil fehlt in der gebuendelten Nachricht"
        assert "0 → " not in body, (
            "Der Schwellen-Anteil darf kein erfundenes Vorher (0) behaupten"
        )
    finally:
        _clean_user(user_id)


# --------------------------------------------------------------------------
# F001 (Adversary-Befund, kritisch): `snow_line` mappt auf ZWEI Katalog-IDs
# (snowfall_limit/freezing_level, Issue #961 OR-Policy), BEIDE mit cmp='unter'.
# Reisst ein snow_line-Korridor die OBERE Grenze, gab es keine cmp-
# Uebereinstimmung -> ValueError -> die Tour war in JEDEM Lauf dauerhaft
# alarm-tot (auch der Aenderungs-Alarm ging verloren, da im Sammel-try/except
# gefangen). Fix: Aufloesung ueber das Summary-Field (unzweideutig EIN
# Treffer fuer snow_line) statt ueber die AlertMetric-Enum-Mehrdeutigkeit,
# PLUS eine zweite, unabhaengige Absicherung je Treffer.
# --------------------------------------------------------------------------

def test_f001_snow_line_obere_grenze_crasht_den_lauf_nicht():
    """GIVEN eine Tour mit Korridor auf snow_line (Nullgradgrenze), deren
    OBERE Grenze gerissen ist (Hitzewelle-Fall -- BEIDE Katalog-Kandidaten
    von snow_line tragen cmp='unter', ein 'ueber'-Treffer fand vor dem Fix
    keine cmp-Uebereinstimmung)
    WHEN der Alarm-Lauf prueft
    THEN wird gemeldet statt in einer ValueError zu ersticken. Ein zweiter
    Lauf direkt danach beweist zusaetzlich, dass sich der Zustand nicht
    dauerhaft verklemmt (unveraenderte Lage schweigt im Folgelauf, aber der
    Lauf selbst bricht nicht mehr ab)."""
    user_id = _fresh_user("f001snow")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-f001snow",
            [Corridor(metric="snow_line", range=[1500, 2500], notify=True)],
        )
        stand = [_data(1, freezing_level_m=3200.0)]

        mail_calls: list = []
        svc = _service(user_id, mail_calls)
        sent1 = svc.check_and_send_alerts(trip, stand, fresh_weather=stand)

        assert sent1 is True, (
            "Ein gerissener OBERER snow_line-Korridor darf den Lauf nicht "
            "mit einer ValueError abbrechen (F001)"
        )
        assert len(mail_calls) == 1
        assert "Nullgradgrenze" in mail_calls[0][1], (
            f"Beschriftung fehlt in der Meldung: {mail_calls[0][1][:400]!r}"
        )

        # Zweiter Lauf: unveraenderte Lage schweigt, aber der Zustand darf
        # sich nicht dauerhaft verklemmen (kein erneuter Crash).
        sent2 = svc.check_and_send_alerts(trip, stand, fresh_weather=stand)
        assert sent2 is False, (
            "Unveraenderte Lage darf im Folgelauf nicht erneut melden -- "
            "der Lauf muss aber sauber durchlaufen (kein Crash)"
        )
        assert len(mail_calls) == 1
    finally:
        _clean_user(user_id)


def test_f001_nicht_abbildbarer_treffer_verschluckt_gleichzeitigen_aenderungs_alarm_nicht():
    """GIVEN ein CorridorHit mit einer Metrik, die sich nicht auf einen
    Katalogeintrag projizieren laesst (Haertungstest fuer die ZWEITE, vom
    Feld-Fix unabhaengige Absicherung -- der reguläre Auswertungspfad
    filtert unbekannte Metriken bereits VOR der Treffer-Erzeugung,
    `evaluate_corridor_thresholds()` liefert so einen Treffer nie; dieser
    Test prueft die Projektionsschicht direkt) NEBEN einem gueltigen
    Aenderungs-Alarm
    WHEN die Nachricht projiziert wird
    THEN wird der nicht abbildbare Treffer uebersprungen (protokolliert,
    ADR-0018: ausweichen ja, kaschieren nein), der Aenderungs-Alarm kommt
    trotzdem an -- kein Totalverlust der Nachricht durch einen einzelnen
    kaputten Treffer."""
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.alert.project import to_alert_message
    from services.corridor_threshold import CorridorHit

    bad_hit = CorridorHit(
        metric="__unbekannt__", value=1.0, bound=0.0, direction="above",
        segment_id="1", occurred_at=None,
    )
    change = WeatherChange(
        metric="precip_sum_mm", old_value=2.0, new_value=18.0, delta=16.0,
        threshold=5.0, severity=ChangeSeverity.MAJOR, direction="increase",
        segment_id="1",
    )
    weather = [_data(1, precip_sum_mm=18.0)]

    msg = to_alert_message(
        [change], weather, "Testtour", tz=timezone.utc, stand_at="12:00",
        corridor_hits=[bad_hit],
    )

    assert len(msg.events) == 1, "Der gueltige Aenderungs-Alarm muss ankommen"
    assert msg.corridor_events == (), (
        "Der nicht abbildbare Treffer darf nicht in die Nachricht gelangen"
    )


# --------------------------------------------------------------------------
# F002: Verschaerfung bei STETIGEN Groessen (bisher nur an Gewitter/ordinal
# nachgewiesen) -- AC-4 nennt ausdruecklich beide Faelle.
# --------------------------------------------------------------------------

def test_ac4_verschaerfung_bei_stetiger_groesse_meldet_erneut_geringfuegig_nicht():
    """GIVEN eine bereits gemeldete gerissene Regen-Grenze (stetige Groesse)
    WHEN sich die Lage nur GERINGFUEGIG verschaerft (weniger als die
    Aenderungs-Empfindlichkeit der Metrik)
    THEN schweigt der Waechter; WHEN sie sich anschliessend um MINDESTENS die
    Aenderungs-Empfindlichkeit weiter von der Grenze entfernt
    THEN meldet er erneut."""
    user_id = _fresh_user("ac4c")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-ac4c",
            [Corridor(metric="precipitation_sum", range=[None, 1], notify=True)],
        )
        mail_calls: list = []
        svc = _service(user_id, mail_calls)

        # Aenderungs-Empfindlichkeit von "precipitation_sum" = 10.0 mm
        # (Katalog default_change_threshold, gegen die Wirklichkeit
        # geprueft, nicht geraten).
        gerissen = [_data(1, precip_sum_mm=6.0)]        # Distanz zur Grenze: 5.0
        geringfuegig = [_data(1, precip_sum_mm=6.5)]     # Distanz 5.5 (+0.5 < 10.0)
        verschaerft = [_data(1, precip_sum_mm=20.0)]     # Distanz 19.0 (+14.0 >= 10.0)

        svc.check_and_send_alerts(trip, gerissen, fresh_weather=gerissen)
        svc.check_and_send_alerts(trip, geringfuegig, fresh_weather=geringfuegig)
        svc.check_and_send_alerts(trip, verschaerft, fresh_weather=verschaerft)

        assert len(mail_calls) == 2, (
            "Geringfuegige Verschaerfung darf nicht erneut melden, eine "
            "Verschaerfung um mindestens die Aenderungs-Empfindlichkeit "
            f"muss es -- erhalten: {len(mail_calls)} Meldung(en)"
        )
    finally:
        _clean_user(user_id)


# ==========================================================================
# Scheibe 2a — Schwellen-Waechter erreicht BEIDE Metrik-Namensraeume
# SPEC: docs/specs/modules/feat_1444_s2a_schwellen_namensraum.md AC-1..AC-7
#
# Der Kern des Bugs: die Tests der Scheibe 1 oben benutzen durchgaengig die
# ALTEN `AlertMetric`-Kennungen (`thunder_level`, `precipitation_sum`). Der
# Korridor-Editor schreibt seit der #1425-Migration aber die
# Katalog-Kennungen (`thunder_level_max`, `precip_sum_mm`, ...) -- und die
# loest `_ALERT_METRIC_TO_SUMMARY_FIELD` nicht auf, der Korridor wird still
# uebersprungen.
#
# RED-Lage bei Abgabe (gemessen, nicht behauptet):
#   rot   AC-1, AC-2, AC-3, AC-7 -- beweisen den Bug
#   gruen AC-4, AC-5, AC-6       -- Regression bzw. Gegenproben, muessen
#                                   VOR und NACH der Implementierung gruen sein
# ==========================================================================


def test_ac1_gewitter_grenze_im_katalog_namensraum_meldet():
    """AC-1 (ROT vor der Implementierung).

    GIVEN eine Tour mit dem Gewitter-Wertebereich unter der KATALOG-Kennung
    `thunder_level_max` (genau so, wie der Korridor-Editor seit #1425
    speichert -- NICHT die alte Kennung `thunder_level`) und einer
    Vorhersage, die im aktiven Etappenfenster Gewitter zeigt
    WHEN der Alarm-Lauf prueft
    THEN geht genau eine Sofort-Meldung raus, die Groesse, Ist-Wert und
    Etappe nennt.

    Heute still uebersprungen: `_ALERT_METRIC_TO_SUMMARY_FIELD` kennt nur den
    alten Namensraum, `evaluate_corridor_thresholds()` verlaesst den Korridor
    per `continue`."""
    user_id = _fresh_user("s2ac1")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-s2ac1",
            [Corridor(metric="thunder_level_max", range=[None, 0], notify=True)],
        )
        stand = [_data(1, thunder_level_max=ThunderLevel.MED)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, stand, fresh_weather=stand,
        )

        assert sent is True, (
            "Ein Gewitter-Wertebereich unter der Katalog-Kennung "
            "'thunder_level_max' loest heute KEINE Meldung aus -- der "
            "Waechter loest nur den alten AlertMetric-Namensraum auf"
        )
        assert len(mail_calls) == 1, (
            f"Erwartet genau 1 Meldung, erhalten: {len(mail_calls)}"
        )
        _, body = mail_calls[0]
        assert "Gewitter" in body, (
            f"Die Wettergroesse fehlt in der Meldung: {body[:400]!r}"
        )
        assert "km " in body, (
            f"Die Etappe (km-Angabe) fehlt in der Meldung: {body[:400]!r}"
        )
    finally:
        _clean_user(user_id)


def test_ac2_regen_grenze_im_katalog_namensraum_meldet():
    """AC-2 (ROT vor der Implementierung).

    GIVEN eine Tour mit dem Regen-Wertebereich unter der KATALOG-Kennung
    `precip_sum_mm` (NICHT die alte Kennung `precipitation_sum`) und einer
    Vorhersage, die die Grenze reisst
    WHEN der Alarm-Lauf prueft
    THEN geht genau eine Sofort-Meldung raus, die Groesse, Ist-Wert und
    Etappe nennt.

    Derselbe Bug wie AC-1, hier an einer STETIGEN Groesse -- damit der
    Nachweis nicht an der Gewitter-Sonderbehandlung (Ordinalwandlung) haengt."""
    user_id = _fresh_user("s2ac2")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-s2ac2",
            [Corridor(metric="precip_sum_mm", range=[None, 1], notify=True)],
        )
        stand = [_data(1, precip_sum_mm=9.0)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, stand, fresh_weather=stand,
        )

        assert sent is True, (
            "Ein Regen-Wertebereich unter der Katalog-Kennung 'precip_sum_mm' "
            "loest heute KEINE Meldung aus -- der Waechter loest nur den "
            "alten AlertMetric-Namensraum auf"
        )
        assert len(mail_calls) == 1, (
            f"Erwartet genau 1 Meldung, erhalten: {len(mail_calls)}"
        )
        _, body = mail_calls[0]
        # "Niedersch" = alert_label der Katalog-Metrik `precipitation`
        # (gegen die Wirklichkeit geprueft, nicht geraten).
        assert "Niedersch" in body, (
            f"Die Wettergroesse fehlt in der Meldung: {body[:400]!r}"
        )
        assert "9" in body, (
            f"Der Ist-Wert (9.0 mm) fehlt in der Meldung: {body[:400]!r}"
        )
    finally:
        _clean_user(user_id)


def test_ac3_nicht_alarmfaehige_groesse_schneehoehe_meldet():
    """AC-3 (ROT vor der Implementierung).

    GIVEN eine Tour mit einem Wertebereich auf der Schneehoehe
    (`snow_depth_cm`) -- eine Groesse, die das Register NICHT als
    alarmfaehig fuehrt (`alarmCapable: false`) und die im alten Namensraum
    gar nicht existiert -- und einer Vorhersage, die die Grenze reisst
    WHEN der Alarm-Lauf prueft
    THEN geht eine Sofort-Meldung raus.

    Belegt die Korrektur an der Ticket-Skizze: massgeblich ist NICHT
    `alarm_capable` (die Frage des Aenderungs-Waechters), sondern ob ein
    Zahlenwert je Etappe existiert."""
    user_id = _fresh_user("s2ac3")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-s2ac3",
            [Corridor(metric="snow_depth_cm", range=[None, 20], notify=True)],
        )
        stand = [_data(1, snow_depth_cm=80.0)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, stand, fresh_weather=stand,
        )

        assert sent is True, (
            "Ein Wertebereich auf der Schneehoehe loest heute KEINE Meldung "
            "aus, obwohl je Etappe ein Zahlenwert vorliegt"
        )
        assert len(mail_calls) == 1, (
            f"Erwartet genau 1 Meldung, erhalten: {len(mail_calls)}"
        )
        # "Schnee" = alert_label der Katalog-Metrik `snow_depth`
        # (gegen die Wirklichkeit geprueft, nicht geraten).
        assert "Schnee" in mail_calls[0][1], (
            f"Die Wettergroesse fehlt in der Meldung: {mail_calls[0][1][:400]!r}"
        )
    finally:
        _clean_user(user_id)


def test_ac4_alte_kennungen_snow_line_obere_grenze_und_wind_gust_melden_weiter():
    """AC-4 (GRUEN vor UND nach der Implementierung -- Regressionsschutz,
    KEIN RED-Nachweis).

    GIVEN eine Tour mit Wertebereichen unter den ALTEN AlertMetric-Kennungen
    `snow_line` (mit OBERER Grenze -- der Fall, dessen Mehrdeutigkeit in
    Scheibe 1 den CRITICAL ausgeloest hat) und `wind_gust` (stetige Groesse,
    haeufigster Realfall), beide gerissen
    WHEN der Alarm-Lauf prueft
    THEN melden beide unveraendert weiter -- der additive Rueckfall auf den
    Katalog-Namensraum darf den bestehenden Weg weder ueberschreiben noch
    verschieben."""
    user_id = _fresh_user("s2ac4")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-s2ac4",
            [
                Corridor(metric="snow_line", range=[1500, 2500], notify=True),
                Corridor(metric="wind_gust", range=[None, 60], notify=True),
            ],
        )
        stand = [_data(1, freezing_level_m=3200, gust_max_kmh=95.0)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, stand, fresh_weather=stand,
        )

        assert sent is True, (
            "Die alten Kennungen snow_line/wind_gust muessen unveraendert "
            "weiter melden"
        )
        assert len(mail_calls) == 1, (
            f"Beide gerissenen Grenzen gehoeren in EINE Nachricht, "
            f"erhalten: {len(mail_calls)} Meldung(en)"
        )
        body = mail_calls[0][1]
        assert "Nullgradgrenze" in body, (
            f"Der snow_line-Anteil (obere Grenze, F001-Fall) fehlt: {body[:500]!r}"
        )
        assert "Böen" in body, (
            f"Der wind_gust-Anteil fehlt in der Meldung: {body[:500]!r}"
        )
    finally:
        _clean_user(user_id)


def test_ac5_eingehaltene_grenze_im_katalog_namensraum_meldet_nicht():
    """AC-5 (GRUEN vor UND nach der Implementierung).

    GIVEN eine Tour mit einem Wertebereich im Katalog-Namensraum
    (`thunder_level_max`) und einer Vorhersage, die die Grenze EINHAELT
    WHEN der Alarm-Lauf prueft
    THEN geht keine Meldung raus.

    ACHTUNG -- dieser Test ist heute aus dem FALSCHEN Grund gruen: der
    Korridor wird derzeit ueberhaupt nicht ausgewertet (unbekannte Kennung),
    also kann auch nichts melden. Er ist damit KEIN Nachweis fuer den
    RED-Zustand, sondern die Absicherung, dass die Implementierung nicht ins
    Gegenteil kippt und ab jetzt bei eingehaltener Grenze faelschlich meldet."""
    user_id = _fresh_user("s2ac5")
    _clean_user(user_id)
    try:
        trip = _corridor_trip(
            "trip-s2ac5",
            [Corridor(metric="thunder_level_max", range=[None, 0], notify=True)],
        )
        stand = [_data(1, thunder_level_max=ThunderLevel.NONE)]

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, stand, fresh_weather=stand,
        )

        assert sent is False, (
            "Eine eingehaltene Grenze darf auch im Katalog-Namensraum keine "
            "Meldung ausloesen"
        )
        assert mail_calls == [], f"Unerwartete Meldung: {mail_calls!r}"
    finally:
        _clean_user(user_id)


def test_ac6_aenderungs_waechter_bleibt_fuer_katalog_kennungen_wirkungslos():
    """AC-6 (GRUEN vor UND nach der Implementierung -- Gegenprobe).

    GIVEN eine AlertRule des AENDERUNGS-Waechters mit einer Kennung, die es
    nur im Katalog-Namensraum gibt (`thunder_level_max`)
    WHEN die Aenderungs-Erkennung darueber laeuft (echter Aufruf von
    `detect_changes()` mit einem Sprung von KEIN auf HOCH -- kein blosser
    Konstanten-Check)
    THEN bleibt sie wirkungslos wie vor dieser Scheibe: der additive
    Rueckfall gehoert ausschliesslich in den Schwellen-Pfad.

    Zusatz-Assert in derselben Funktion (kein eigenes Gate): die beiden
    Namensraeume sind kollisionsfrei. Nur dann kann der Rueckfall keinen
    bestehenden Fall ueberschreiben; bricht ein kuenftiger Katalog-Eintrag
    die Kollisionsfreiheit, schlaegt dieser Test an, statt das Verhalten
    still zu verschieben."""
    from app.models import AlertRule, AlertRuleKind, AlertSeverity
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG
    from services.weather_change_detection import (
        _ALERT_METRIC_TO_SUMMARY_FIELD,
        WeatherChangeDetectionService,
    )

    assert _ALERT_METRIC_TO_SUMMARY_FIELD.get("thunder_level_max") is None, (
        "Die Katalog-Kennung darf im Register des Aenderungs-Waechters NICHT "
        "auftauchen -- der Rueckfall gehoert allein in den Schwellen-Pfad"
    )

    regeln = [
        AlertRule(
            id="r-abs", kind=AlertRuleKind.ABSOLUTE, metric="thunder_level_max",
            threshold=1.0, severity=AlertSeverity.WARNING, enabled=True,
        ),
        AlertRule(
            id="r-delta", kind=AlertRuleKind.DELTA, metric="thunder_level_max",
            threshold=0.5, severity=AlertSeverity.WARNING, enabled=True,
        ),
    ]
    svc = WeatherChangeDetectionService.from_alert_rules(regeln)
    changes = svc.detect_changes(
        _data(1, thunder_level_max=ThunderLevel.NONE),
        _data(1, thunder_level_max=ThunderLevel.HIGH),
    )

    assert changes == [], (
        "Der Aenderungs-Waechter darf Katalog-Kennungen weiterhin NICHT "
        f"aufloesen, erhalten: {changes!r}"
    )

    katalog_keys = {eintrag["key"] for eintrag in COMPARE_METRIC_CATALOG}
    alt_keys = {
        getattr(k, "value", k) for k in _ALERT_METRIC_TO_SUMMARY_FIELD
    }
    kollision = katalog_keys & alt_keys
    assert kollision == set(), (
        "Die beiden Metrik-Namensraeume muessen kollisionsfrei bleiben, "
        f"sonst ueberschreibt der Rueckfall bestehende Faelle -- "
        f"kollidierende Kennungen: {sorted(kollision)!r}"
    )


def test_ac7_niederschlagsart_meldet_nicht_und_stoppt_den_lauf_nicht():
    """AC-7 (ROT vor der Implementierung -- wegen des zweiten Korridors).

    GIVEN eine Tour mit ZWEI Wertebereichen: einem auf der Niederschlagsart
    (`precip_type_dominant`, eine Aufzaehlung OHNE Ordinalskala) und daneben
    einem auf Gewitter im Katalog-Namensraum, dessen Grenze gerissen ist
    WHEN der Alarm-Lauf prueft
    THEN kommt die Gewitter-Meldung an, und fuer die Niederschlagsart geht
    KEINE Meldung raus -- der Lauf bricht nicht ab.

    Der Bereich der Niederschlagsart ist bewusst "mindestens 1" gewaehlt:
    eine Implementierung, die den Katalog-Rueckfall einbaut, ohne die
    Enum-Erkennung auf `ThunderLevel` zu verengen, wandelt `PrecipType.SNOW`
    ueber `thunder_ordinal()` still in die 0 (gemessen: kein ValueError,
    sondern der Default-Rueckgabewert) -- 0 liegt unter 1, es entstuende ein
    FALSCHALARM auf einer Groesse ohne Ordinalskala. Genau den faengt dieser
    Test."""
    from app.models import PrecipType
    from services.corridor_threshold import evaluate_corridor_thresholds

    korridore = [
        Corridor(metric="precip_type_dominant", range=[1, None], notify=True),
        Corridor(metric="thunder_level_max", range=[None, 0], notify=True),
    ]
    stand = [_data(1, precip_type_dominant=PrecipType.SNOW,
                   thunder_level_max=ThunderLevel.MED)]

    treffer = evaluate_corridor_thresholds(stand, korridore)
    assert [h.metric for h in treffer] == ["thunder_level_max"], (
        "Die Niederschlagsart darf keinen Treffer erzeugen (keine "
        "Ordinalskala), das Gewitter daneben schon -- erhalten: "
        f"{[(h.metric, h.value) for h in treffer]!r}"
    )

    user_id = _fresh_user("s2ac7")
    _clean_user(user_id)
    try:
        trip = _corridor_trip("trip-s2ac7", korridore)

        mail_calls: list = []
        sent = _service(user_id, mail_calls).check_and_send_alerts(
            trip, stand, fresh_weather=stand,
        )

        assert sent is True, (
            "Der Lauf muss die uebrigen Groessen weiter melden, auch wenn ein "
            "Korridor auf einer nicht ordinalen Groesse liegt"
        )
        assert len(mail_calls) == 1, (
            f"Erwartet genau 1 Meldung, erhalten: {len(mail_calls)}"
        )
        body = mail_calls[0][1]
        assert "Gewitter" in body, (
            f"Der Gewitter-Anteil fehlt in der Meldung: {body[:400]!r}"
        )
        # "Niederschlagsart" = label_de der Katalog-Metrik `precip_type`
        # (alert_label ist leer, get_alert_label() faellt darauf zurueck).
        assert "Niederschlagsart" not in body, (
            f"Fuer die Niederschlagsart darf keine Meldung entstehen: {body[:400]!r}"
        )
    finally:
        _clean_user(user_id)
