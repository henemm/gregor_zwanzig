"""Issue #2050 Scheibe S2a — Waechter 1: Szenario 2 als Zeitreihe MIT Gedaechtnis.

SPEC: docs/specs/modules/alarm_szenarien_waechter_2_3.md (AC-1, AC-2, AC-4 —
AC-3 ist nach Issue #2065 ausgelagert, s. Kommentarblock in der Dateimitte)

Was die 17 bestehenden Tests in `test_nowcast_briefing_overtake.py` NICHT
pruefen: jeder von ihnen ist ein EINZELAUFRUF auf einem leeren Datentraeger,
der Sperrzeit-Mechanismus (`ThrottleStore`) kommt dort strukturell nie zum
Tragen. Diese Datei faehrt dieselbe Ueberholungs-Lage als FOLGE mehrerer
Prueflaeufe auf EINER `user_id` ueber die `AlarmPruefstrecke` — die
Kontinuitaet kommt vom Datentraeger unter `get_data_dir(user_id)`, genau wie
bei jedem Cron-Tick in Produktion.

Kein Mock()/patch()/MagicMock: echter `RadarNowcastService` an seiner DI-Naht
`frame_source=`, Briefing-Anker ueber den produktiven Schreibweg
`WeatherSnapshotService.save_dated()` (genau die Datei, die
`check_radar_alerts()` per `load_dated()` liest), Unterdrueckungsgrund ueber
`alert_log.read_undelivered()` — kein Dateiinhalt-Check.

Keine Wanduhr: alle Zeitpunkte haengen an `_AT` (gestellte Uhr).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary,
)
from services import alert_log
from services.radar_cache import reset_shared_radar_cache_for_tests
from services.radar_service import RadarNowcastService
from services.weather_snapshot import WeatherSnapshotService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)

# Ankuendigung des Briefings fuer JEDE Stunde des Snapshot-Tages: der Onset
# faellt aus dem Radar-Ergebnis, nicht aus dem Test — ein stundenweise
# gesetzter Wert waere ein zweiter, stiller Freiheitsgrad.
BRIEFING_MM = 1.0

# Kleinste Menge, die noch als Ankuendigung zaehlt (`_briefing_announced`
# verlangt >= 0.5 mm, `trip_alert.py:1365`). Damit liegt die FAKTOR-Schwelle
# bei nur 1,0 mm — die absolute Untergrenze wird zur allein wirksamen
# Bedingung (AC-8).
BRIEFING_KLEIN_MM = 0.5


def _uid(tag: str) -> str:
    return f"tdd-2050-s2a-w1-{tag}-{uuid.uuid4().hex[:6]}"


def _gelesene_briefing_werte(uid: str, trip, seit: datetime) -> list:
    """Die Briefing-Mengen, die der PRUEFLING selbst gelesen hat — aus seinem
    Unterdrueckungs-Protokoll zurueckgelesen (`gate_reason`
    `briefing_announced:<mm>mm`, `trip_alert.py:1393`).

    Bewusst NICHT ueber einen eigenen `load_dated()`-Aufruf im Testcode: der
    liefe an dem Lesepfad vorbei, den `check_radar_alerts()` benutzt, und
    bliebe gruen, wenn genau dieser Pfad bricht. Der Protokoll-Eintrag traegt
    den Wert, den die Ueberholungspruefung TATSAECHLICH in der Hand hatte —
    an dem Ort gemessen, an dem die Zusicherung wirkt."""
    vorfaelle = alert_log.read_undelivered(
        uid, entity_id=trip.id, entity_type="trip", since=seit,
    )
    werte = []
    for vorfall in vorfaelle:
        for grund in vorfall.reasons:
            text = str(grund)
            if text.startswith("briefing_announced:") and text.endswith("mm"):
                werte.append(float(text[len("briefing_announced:"):-2]))
    return werte


def _dauerregen(rate_mm_h: float):
    """Vier Frames im 15-Min-Raster: jeder steht fuer hoechstens 15 Min
    (`_MAX_FRAME_COVERAGE`), der letzte wird am Fensterende (60 Min) gekappt
    -> akkumuliert `rate * 55/60` mm im 60-Min-Vergleichsfenster."""
    def _quelle(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        jetzt = datetime.now(timezone.utc)
        return [
            RadarFrame(timestamp=jetzt + timedelta(minutes=m), precip_mm_h=rate_mm_h)
            for m in (5, 20, 35, 50)
        ]
    return _quelle


def _kurze_spitze(rate_mm_h: float):
    """Nur 10 Minuten Regen, danach trocken -> `rate * 10/60` mm im
    60-Min-Vergleichsfenster. 11 mm/h ~ 1,83 mm (AC-4, unter BEIDEN
    Ueberholungs-Bedingungen), 9 mm/h ~ 1,5 mm (AC-8, ueber der Faktor-,
    unter der absoluten Bedingung), 3 mm/h ~ 0,5 mm (AC-1-Sonde)."""
    def _quelle(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        jetzt = datetime.now(timezone.utc)
        return [
            RadarFrame(timestamp=jetzt + timedelta(minutes=5), precip_mm_h=rate_mm_h),
            RadarFrame(timestamp=jetzt + timedelta(minutes=15), precip_mm_h=0.0),
        ]
    return _quelle


def _radar(rate_quelle) -> RadarNowcastService:
    """Frische Instanz je Lauf — den geteilten Frame-Cache setzt die
    Pruefstrecke selbst zurueck (`reset_shared_radar_cache_for_tests`)."""
    return RadarNowcastService(frame_source=rate_quelle)


def _briefing_anker(uid: str, trip, mm: float) -> None:
    """Datierter Briefing-Schnappschuss ueber `save_dated()` — genau die
    Datei, die `check_radar_alerts()` per `load_dated(trip.id, segment_date)`
    liest. Segment und Segment-Datum kommen aus DEMSELBEN produktiven
    Aufloeser (`resolve_current_segment`) wie beim Pruefling; ein von Hand
    getippter `segment_id` waere nur zufaellig richtig."""
    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    with freeze_time(_AT):
        jetzt = datetime.now(timezone.utc)
        aufgeloest = resolve_current_segment(trip, jetzt, trip_local_today(trip, jetzt))
        assert aufgeloest is not None, (
            "Vorbedingung: der Trip muss zur gestellten Uhr ein aktives Segment "
            "haben — sonst bricht check_radar_alerts() vor dem Nowcast-Abruf ab."
        )
        segment, segment_datum = aufgeloest
        tagesbeginn = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
        reihe = NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=[ForecastDataPoint(ts=tagesbeginn + timedelta(hours=h),
                                    precip_1h_mm=mm) for h in range(48)],
        )
        WeatherSnapshotService(uid).save_dated(trip.id, segment_datum, [
            SegmentWeatherData(
                segment=segment, timeseries=reihe,
                aggregated=SegmentWeatherSummary(),
                fetched_at=jetzt, provider="openmeteo",
            )])


def _aufbau(uid: str, tag: str, briefing_mm: float = BRIEFING_MM):
    """Nutzer (Premium-Profil fuer den vierten Kanal), Trip mit allen vier
    Kanaelen, Briefing-Anker mit `briefing_mm`."""
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    # Auch das SPEICHERN laeuft unter der gestellten Uhr: `app.loader.save_trip()`
    # rechnet Ankunftszeiten beim Schreiben neu (Compute-on-Save, #802). Ohne
    # den Rahmen haenge der gespeicherte Stand an der Wanduhr des Testlaufs.
    with freeze_time(_AT):
        trip = _radar_trip(
            uid, f"trip-2050-s2a-{tag}", send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True,
        )
        _briefing_anker(uid, trip, briefing_mm)
    return trip


def test_ac1_briefing_kuendigte_1mm_an_radar_zeigt_11mm_loest_aus():
    """AC-1: Briefing 1 mm, Radar ~10 mm im 60-Min-Vergleichsfenster
    (11 mm/h ueber 55 Min) -> genau ein Alarm, alle vier Kanaele tragen den
    gerenderten Inhalt.

    Vorgeschaltet ein SONDEN-Lauf, der die Ankuendigung positiv nachweist:
    ohne ihn kann der Waechter "Alarm, weil die Ueberholung griff" nicht von
    "Alarm, weil gar kein Briefing gefunden wurde" unterscheiden — bricht der
    Lesepfad (`load_dated`, `trip_alert.py:1363`), greift die Unterdrueckung
    nie und der Alarm faellt trivial an."""
    uid = _uid("ac1")
    try:
        trip = _aufbau(uid, "ac1")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        # Sonde: ~0,5 mm (3 mm/h ueber 10 Min) ueberholt die Ankuendigung
        # NICHT -> der Prueflauf muss schweigen UND protokollieren, welchen
        # Briefing-Wert er dabei gelesen hat. Bucht keine Sperrzeit (die
        # entsteht erst nach Zustellung, `trip_alert.py:1607`), der
        # Ausloese-Lauf darunter bleibt also unbeeinflusst.
        sonde = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(_kurze_spitze(3.0)),
        )
        assert sonde.triggered_count == 0, (
            f"AC-1 Sonde: ~0,5 mm gegen eine Ankuendigung von {BRIEFING_MM} mm "
            f"duerfen NICHT ausloesen. Loest es doch aus, wurde die Ankuendigung "
            f"nicht gelesen — dann bewacht der Ausloese-Lauf unten nichts "
            f"(triggered_count={sonde.triggered_count})."
        )
        assert _gelesene_briefing_werte(uid, trip, _AT) == [BRIEFING_MM], (
            f"AC-1 Sonde: der Prueflauf muss GENAU die angekuendigten "
            f"{BRIEFING_MM} mm gelesen haben. Protokolliert wurde "
            f"{_gelesene_briefing_werte(uid, trip, _AT)!r}."
        )

        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(_dauerregen(11.0)),
        )
        assert lauf.triggered_count == 1, (
            f"AC-1: Briefing kuendigte {BRIEFING_MM} mm an, der Radar zeigt ~10 mm "
            f"fuer dasselbe Fenster — die Ueberholung MUSS ausloesen. "
            f"War triggered_count={lauf.triggered_count}."
        )
        assert lauf.mail and lauf.telegram and lauf.sms and lauf.premium_sms, (
            f"AC-1: alle vier Kanaele muessen Inhalt tragen: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
    finally:
        _clean_user(uid)


def test_ac2_zweiter_lauf_schweigt_nachweislich_wegen_der_gebuchten_sperrzeit():
    """AC-2: Lauf 2 faehrt dieselbe (unveraenderte) Ueberholungs-Lage 30 Min
    spaeter, schweigt — und das Alarmprotokoll benennt die SPERRZEIT als
    Grund, nicht die Briefing-Ankuendigung. Ohne diesen Nachweis waere der
    Test trivial gruen: "schweigt wegen Sperre" und "schweigt, weil die Lage
    die Ankuendigung nicht ueberholt" sehen am `triggered_count == 0`
    identisch aus."""
    uid = _uid("ac2")
    try:
        trip = _aufbau(uid, "ac2")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(_dauerregen(11.0)),
        )
        assert lauf1.triggered_count == 1, (
            "AC-2 Vorbedingung: Lauf 1 muss ausloesen und dabei die Sperrzeit "
            f"buchen (war {lauf1.triggered_count})."
        )

        at2 = _AT + timedelta(minutes=30)
        lauf2 = strecke.lauf(
            at=at2, zweig="radar", trip=trip, radar_service=_radar(_dauerregen(11.0)),
        )
        assert lauf2.triggered_count == 0, (
            f"AC-2: Lauf 2 muss durch die von Lauf 1 gebuchte Sperrzeit "
            f"unterdrueckt sein (war {lauf2.triggered_count})."
        )

        vorfaelle = alert_log.read_undelivered(
            uid, entity_id=trip.id, entity_type="trip", since=at2,
        )
        nowcast = [v for v in vorfaelle if v.trigger == alert_log.REASON_NOWCAST]
        assert nowcast, (
            f"AC-2: erwarte einen Unterdrueckungs-Eintrag mit "
            f"reason={alert_log.REASON_NOWCAST!r} fuer Lauf 2. "
            f"Gefunden: {vorfaelle!r}"
        )
        gruende = {g for v in nowcast for g in v.reasons}
        assert alert_log.REASON_COOLDOWN in gruende, (
            f"AC-2: der Unterdrueckungsgrund muss die SPERRZEIT "
            f"({alert_log.REASON_COOLDOWN!r}) sein. Gefunden: {gruende!r}"
        )
        assert not any(str(g).startswith("briefing_announced:") for g in gruende), (
            f"AC-2: Lauf 2 darf NICHT an der Briefing-Ankuendigung scheitern — "
            f"dann waere die Zusicherung 'schweigt wegen der Sperre' nicht "
            f"belegt. Gefunden: {gruende!r}"
        )
    finally:
        _clean_user(uid)


# ---------------------------------------------------------------------------
# LUECKE — hier fehlt AC-3 (Anforderung A-3), und zwar mit Absicht.
#
# Szenario 2 aus Issue #2050 verlangt nicht nur "die Ueberholung loest aus"
# (AC-1) und "die gebuchte Sperre schweigt korrekt" (AC-2), sondern AUCH:
# eine deutliche VERSCHAERFUNG der Lage muss eine noch laufende Sperrzeit
# ueberholen. Dieser Teil ist auf genau dieser Strecke am 2026-08-22
# GEMESSEN ROT: ein dritter Lauf 90 Min nach Lauf 1 (30 mm/h statt 11 mm/h,
# ~27,5 mm statt ~10 mm) liefert `triggered_count=0`, und das Alarmprotokoll
# nennt als Grund `cooldown` — nicht `briefing_announced:`. Ursache:
# `check_nowcast_gate` prueft die Sperrzeit unbedingt VOR jeder
# Eskalations-/Ueberholungsbewertung (`trip_alert.py:1239-1273` gegen
# `:1380-1384`) und kennt keine Ausnahme fuer verschaerfte Lagen.
#
# Der Waechter dafuer braucht Produktivcode und lebt deshalb in Issue #2065
# weiter (Testkoerper, pytest-Ausgabe und Code-Ursache sind dort abgelegt).
# Die Nummerierung der uebrigen Tests bleibt bewusst deckungsgleich mit der
# Spec (AC-1, AC-2, AC-4) — die Luecke ist ausgelagert, nicht vergessen.
# ---------------------------------------------------------------------------


def test_ac4_kurze_spitze_mit_gleicher_spitzenrate_loest_nicht_aus():
    """AC-4: EIGENE `user_id` (kein geerbter Zustand aus AC-1/AC-2).
    Spitzenrate wie im ausloesenden Fall (11 mm/h), Gesamtmenge mit ~1,83 mm
    unter der Ueberholungs-Untergrenze -> kein Alarm. Die Gleichheit der
    Spitzenrate wird am ECHTEN Nowcast-Ergebnis gemessen, nicht behauptet:
    ohne sie waere das nur ein zweiter "kein Alarm"-Test ohne Aussage
    darueber, WORAN es lag."""
    uid = _uid("ac4")
    try:
        trip = _aufbau(uid, "ac4")
        lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
        with freeze_time(_AT):
            # Der Frame-Cache ist ein PROZESS-Singleton mit Koordinaten-
            # Schluessel (TTL 300 s): ohne Reset dazwischen liefert der zweite
            # Abruf die Frames des ersten zurueck — beide Messungen waeren dann
            # zufaellig gleich und die Gegenprobe wertlos (gemessen).
            reset_shared_radar_cache_for_tests()
            spitze = _radar(_kurze_spitze(11.0)).get_nowcast(lat, lon)
            reset_shared_radar_cache_for_tests()
            dauer = _radar(_dauerregen(11.0)).get_nowcast(lat, lon)
            reset_shared_radar_cache_for_tests()
        assert spitze.max_rate_mm_h == dauer.max_rate_mm_h, (
            f"AC-4 Testkonstruktion: die Spitzenrate muss der des ausloesenden "
            f"Falls GLEICHEN ({spitze.max_rate_mm_h} vs. {dauer.max_rate_mm_h})."
        )
        assert spitze.window_precip_mm < dauer.window_precip_mm, (
            f"AC-4 Testkonstruktion: die Gesamtmenge muss deutlich kleiner sein "
            f"({spitze.window_precip_mm} vs. {dauer.window_precip_mm})."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(_kurze_spitze(11.0)),
        )
        assert lauf.triggered_count == 0, (
            f"AC-4: gleiche Spitzenrate, aber nur ~{spitze.window_precip_mm:.2f} mm "
            f"gegen eine Ankuendigung von {BRIEFING_MM} mm — die Sperre muss "
            f"bestehen bleiben. War triggered_count={lauf.triggered_count}."
        )
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms), (
            f"AC-4: kein Kanal darf etwas ausliefern: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
    finally:
        _clean_user(uid)


def test_ac8_absolute_untergrenze_sperrt_obwohl_der_faktor_ueberholt_ist():
    """AC-8: die Ueberholung ist eine UND-Verknuepfung aus Faktor-Schwelle UND
    absoluter Untergrenze (`trip_alert.py:1381-1385`). AC-4 haelt nur die
    Faktor-Haelfte fest — seine ~1,83 mm scheitern schon an der Faktorschwelle
    (2x1,0 mm), die absolute Untergrenze wird dort nie zur wirksamen Bedingung
    und ihr Wegfall bliebe unbemerkt.

    Hier liegt die Ankuendigung bei 0,5 mm: die Faktor-Schwelle liegt damit bei
    1,0 mm und ist von den gemessenen ~1,5 mm LOCKER ueberholt. Verhindert wird
    der Alarm allein von der absoluten Untergrenze (2,0 mm)."""
    uid = _uid("ac8")
    try:
        trip = _aufbau(uid, "ac8", briefing_mm=BRIEFING_KLEIN_MM)
        lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
        with freeze_time(_AT):
            reset_shared_radar_cache_for_tests()
            lage = _radar(_kurze_spitze(9.0)).get_nowcast(lat, lon)
            reset_shared_radar_cache_for_tests()

        # Modul-Referenz statt gebundener Kopie: eine Aenderung des Faktors
        # soll hier auffallen, nicht stillschweigend mitwandern.
        from services import trip_alert as trip_alert_mod
        faktor_schwelle = BRIEFING_KLEIN_MM * trip_alert_mod._BRIEFING_OVERTAKE_FACTOR
        assert lage.window_precip_mm >= faktor_schwelle, (
            f"AC-8 Testkonstruktion: die Faktor-Bedingung MUSS erfuellt sein, "
            f"sonst prueft der Fall wieder nur den Faktor "
            f"({lage.window_precip_mm} < {faktor_schwelle})."
        )
        assert 1.4 <= lage.window_precip_mm <= 1.6, (
            f"AC-8 Testkonstruktion: erwartet ~1,5 mm (9 mm/h ueber 10 Min), "
            f"gemessen {lage.window_precip_mm} — liegt die Menge ueber der "
            f"absoluten Untergrenze, bewacht der Fall nichts mehr."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(_kurze_spitze(9.0)),
        )
        assert lauf.triggered_count == 0, (
            f"AC-8: ~{lage.window_precip_mm:.2f} mm ueberholen zwar den Faktor "
            f"({faktor_schwelle} mm), bleiben aber unter der absoluten "
            f"Relevanz-Untergrenze — kein Alarm erlaubt. War "
            f"triggered_count={lauf.triggered_count}."
        )
        assert _gelesene_briefing_werte(uid, trip, _AT) == [BRIEFING_KLEIN_MM], (
            f"AC-8: die Stille muss von der Ueberholungspruefung kommen (der "
            f"Protokolleintrag traegt die gelesenen {BRIEFING_KLEIN_MM} mm), "
            f"nicht von Sperrzeit oder fehlendem Briefing."
        )
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms), (
            f"AC-8: kein Kanal darf etwas ausliefern: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r}"
        )
    finally:
        _clean_user(uid)
