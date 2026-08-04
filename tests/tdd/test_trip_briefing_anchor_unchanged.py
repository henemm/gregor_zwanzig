"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG5: der Trip-Pfad verhaelt
sich nach dem Umbau EXAKT wie vorher, und der geteilte Baustein legt die
Reihenfolge Anker → Reset fest (AC-27).

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md, Abschnitt
"AG5 — Vergleichs-Bezugspunkt und Melde-Gedaechtnis als EIN geteilter
Baustein".

Der Trip haelt Δ-Anker-Schreiben UND Gedaechtnis-Reset heute gemeinsam unter
`if not on_demand` (`trip_report_scheduler.py::_send_trip_report_outcome`,
Schritt 10: erst `WeatherSnapshotService.save`/`save_dated`, DANN
`_reset_alert_state_after_briefing(trip.id)`). Genau dieses Verhalten zieht
AG5 in einen geteilten Baustein — und genau dieses Verhalten muss danach
unveraendert sein.

Zwei Arten von Tests in dieser Datei:

* **Wirkungs-Tests am Trip-Pfad** — sie beschreiben Bestandsverhalten und sind
  deshalb heute schon gruen. Ihr Zweck ist die Absicherung des Umbaus: jede
  der naheliegenden Fehl-Umsetzungen (Reset ueber mehrere Kennungen, Reset
  ohne Anker, Anker beim Ad-hoc-Abruf, amtliche Eintraege mitgeloescht) macht
  mindestens einen von ihnen rot.
* **Vertrags-Tests am neuen Baustein** — sie sind heute rot, weil
  `services/alert_briefing_anchor.py` noch nicht existiert.

Die sieben Bestandstests in `tests/tdd/test_alert_state_briefing_reset.py`
bleiben unangetastet und muessen unveraendert gruen bleiben.

Testpolitik: kein Mock-Theater. Der Zaehl-Beobachter auf
`AlertStateService.reset` fuehrt die ECHTE Methode aus und schreibt nur mit,
mit welchem Argument sie gerufen wurde; die Reihenfolge Anker → Reset wird
nicht behauptet, sondern am echten Dateizustand abgelesen (existiert der
frische Anker bereits, wenn der Reset laeuft?).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint

# Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen, nie ueber einen
# festen Hauptrepo-Pfad — sonst pruefte dieser Test aus dem Worktree die
# unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
REPO_ROOT = Path(__file__).resolve().parents[2]

LAT, LON = 47.0, 11.0

# Alle Transport-Felder ausdruecklich unbrauchbar: `Settings()` faellt bei
# fehlenden Feldern still auf die Prod-`.env` im Worktree zurueck (#1477).
_NO_TRANSPORT_FIELDS: dict = {
    "smtp_host": "", "smtp_user": "", "smtp_pass": "", "mail_to": "",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _settings_no_transport() -> Settings:
    return Settings(**_NO_TRANSPORT_FIELDS)


def _segment(segment_id: int | str = 1) -> TripSegment:
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=8.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0,
        distance_km=8.0,
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


def _trip(trip_id: str) -> Trip:
    """Trip ohne scharfen Kanal: der Briefing-Pfad laeuft vollstaendig durch
    (Ergebnis `no_channels`), es wird nichts versendet. Der Anker-/Reset-Block
    liegt VOR dem Ruecksprung — Muster aus
    `test_alert_state_briefing_reset.py::test_ac23_...`."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0),
            Waypoint(id="G2", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500.0),
        ],
    )
    trip = Trip(id=trip_id, name="AG5-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _scheduler_class(gust: float):
    """Echte Unterklasse des Schedulers (kein Mock): liefert das Wetter aus der
    Fixture statt vom Provider. Genau das Muster, das der Bestandstest
    `test_alert_state_briefing_reset.py:418` schon benutzt."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class _FixtureScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return [_data(s.segment_id, gust_max_kmh=gust) for s in segments]

    return _FixtureScheduler


class _ResetRecorder:
    """Delegierender Beobachter auf `AlertStateService.reset` — KEIN Mock:

    die echte Methode wird unveraendert ausgefuehrt (der Reset findet also
    wirklich statt und wird anschliessend am Dateizustand geprueft), es wird
    nur mitgeschrieben, WIE OFT und mit WELCHER Kennung sie gerufen wurde.
    Ohne diese Zaehlung bliebe unbemerkt, wenn der geteilte Baustein den Trip
    versehentlich ueber mehrere Kennungen zuruecksetzt (eine reine
    Zustandspruefung sieht nur die eine Datei, die sie kennt).

    `anchor_present_at_reset` haelt zusaetzlich fest, ob der frische Δ-Anker
    zum Zeitpunkt des Resets bereits auf Platte lag — daraus folgt die
    Reihenfolge Anker → Reset, abgelesen am echten Dateizustand statt
    behauptet.
    """

    def __init__(self, user_id: str, anchor_probe) -> None:
        self.user_id = user_id
        self.calls: list[str] = []
        self.anchor_present_at_reset: list[bool] = []
        self._anchor_probe = anchor_probe

    def install(self, monkeypatch) -> None:
        from services.alert_state import AlertStateService

        original = AlertStateService.reset
        recorder = self

        def _recording_reset(self, entity_id: str) -> None:
            recorder.calls.append(entity_id)
            recorder.anchor_present_at_reset.append(bool(recorder._anchor_probe()))
            return original(self, entity_id)

        monkeypatch.setattr(AlertStateService, "reset", _recording_reset)


def _trip_anchor_gust(user_id: str, trip_id: str) -> float | None:
    """Liest den Δ-Anker des Trips ueber den echten Snapshot-Service."""
    from services.weather_snapshot import WeatherSnapshotService

    cached = WeatherSnapshotService(user_id=user_id).load_dated(trip_id, date.today())
    if not cached:
        return None
    return cached[0].aggregated.gust_max_kmh


# ══════════════ AC-27 — geplantes Briefing: Verhalten unveraendert ═══════════


def test_ac27_geplantes_briefing_setzt_genau_eine_kennung_zurueck(monkeypatch):
    """AC-27 (Wirkung, Bestandsverhalten).

    GIVEN eine Tour mit einem Melde-Gedaechtnis, das einen amtlichen UND einen
          Aenderungs-Eintrag traegt, und drei weitere, FREMDE Zustandsdateien
          (eine zweite Tour sowie zwei Ortsvergleichs-Kennungen desselben
          Nutzers).
    WHEN  das geplante Briefing laeuft (`on_demand=False`).
    THEN  wird der Reset GENAU EINMAL und GENAU fuer `trip.id` gerufen; der
          amtliche Eintrag der Tour ueberlebt, ihr Aenderungs-Eintrag
          verschwindet, und keine der drei fremden Zustandsdateien wird
          angefasst.

    Die Aufruf-ZAEHLUNG ist der Kern: eine reine Zustandspruefung wuerde nicht
    auffallen lassen, dass der geteilte Baustein den Trip ueber mehrere
    Kennungen zuruecksetzt, solange die zusaetzlichen Kennungen zufaellig
    keine Datei haben.
    """
    from services.alert_state import AlertStateService

    uid = f"tdd-ag5-ac27-{uuid.uuid4().hex[:6]}"
    trip = _trip(f"trip-ag5-ac27-{uuid.uuid4().hex[:6]}")

    official_key = "official_alert:region:Gailtal:thunderstorm:none:none"
    official_value = {"last_reported_value": 3.0, "reported_at": "2026-08-04T07:00:00+00:00"}
    state = AlertStateService(user_id=uid)
    state.save(trip.id, {
        "gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"},
        official_key: dict(official_value),
    })
    fremde = {
        "trip-ag5-ac27-fremd": {"gust_max_kmh:1": {"last_reported_value": 11.0, "reported_at": "x"}},
        "cp-ag5-ac27:loc-1": {"precip_sum_mm:loc-1": {"last_reported_value": 22.0, "reported_at": "x"}},
        "cp-ag5-ac27:loc-2": {"precip_sum_mm:loc-2": {"last_reported_value": 33.0, "reported_at": "x"}},
    }
    for entity_id, payload in fremde.items():
        state.save(entity_id, dict(payload))

    recorder = _ResetRecorder(uid, lambda: _trip_anchor_gust(uid, trip.id))
    recorder.install(monkeypatch)

    scheduler = _scheduler_class(gust=25.0)(settings=_settings_no_transport(), user_id=uid)
    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert outcome in ("sent", "no_channels"), (
        f"Der Briefing-Lauf ist vorzeitig abgebrochen: {outcome!r}"
    )
    assert recorder.calls == [trip.id], (
        "Das geplante Briefing muss den Reset GENAU EINMAL und GENAU fuer die "
        f"Tour-Kennung ausloesen, erhalten: {recorder.calls!r} (AC-27)"
    )

    after = AlertStateService(user_id=uid).load(trip.id)
    assert after == {official_key: official_value}, (
        "Nach dem Briefing darf nur noch der amtliche Eintrag der Tour stehen, "
        f"gefunden: {after!r} (AC-27)"
    )
    for entity_id, payload in fremde.items():
        assert AlertStateService(user_id=uid).load(entity_id) == payload, (
            f"Die fremde Zustandsdatei {entity_id!r} wurde vom Trip-Briefing "
            f"veraendert: {AlertStateService(user_id=uid).load(entity_id)!r} (AC-27)"
        )


def test_ac27_anker_wird_vor_dem_reset_geschrieben(monkeypatch):
    """AC-27 (Reihenfolge, Bestandsverhalten).

    GIVEN eine Tour ohne vorhandenen Δ-Anker fuer heute.
    WHEN  das geplante Briefing laeuft.
    THEN  lag der frische Δ-Anker bereits auf Platte, ALS der Reset lief — und
          traegt danach den Briefing-Stand.

    Abgelesen wird das am echten Dateizustand im Moment des Reset-Aufrufs
    (`_ResetRecorder.anchor_present_at_reset`), nicht an einer behaupteten
    Aufrufreihenfolge. Zieht jemand den Reset vor den Anker, wird dieser Test
    rot.
    """
    uid = f"tdd-ag5-order-{uuid.uuid4().hex[:6]}"
    trip = _trip(f"trip-ag5-order-{uuid.uuid4().hex[:6]}")

    assert _trip_anchor_gust(uid, trip.id) is None, (
        "Vorbedingung: fuer heute darf noch kein Δ-Anker existieren"
    )

    recorder = _ResetRecorder(uid, lambda: _trip_anchor_gust(uid, trip.id) is not None)
    recorder.install(monkeypatch)

    scheduler = _scheduler_class(gust=31.0)(settings=_settings_no_transport(), user_id=uid)
    scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert recorder.calls == [trip.id], f"Kein/mehrfacher Reset: {recorder.calls!r}"
    assert recorder.anchor_present_at_reset == [True], (
        "Der Δ-Anker muss VOR dem Gedaechtnis-Reset geschrieben sein — beim "
        "Reset lag noch kein frischer Anker vor. Ein Reset vor dem Anker liesse "
        "die Aenderungen bis zum alten Vergleichspunkt still verschwinden "
        "(AC-27)"
    )
    assert _trip_anchor_gust(uid, trip.id) == pytest.approx(31.0), (
        f"Der Δ-Anker traegt nicht den Briefing-Stand: "
        f"{_trip_anchor_gust(uid, trip.id)!r}"
    )


def test_ac27_ad_hoc_abruf_laesst_anker_und_gedaechtnis_unberuehrt(monkeypatch):
    """AC-27 (Ad-hoc-Haelfte, Bestandsverhalten, Issue #1007).

    GIVEN eine Tour mit einem bestehenden Δ-Anker (20 km/h) und einem
          Melde-Gedaechtnis mit amtlichem UND Aenderungs-Eintrag.
    WHEN  ein Ad-hoc-Abruf laeuft (`on_demand=True`) und dabei ein deutlich
          anderes Wetter (48 km/h) sieht.
    THEN  wird der Reset kein einziges Mal gerufen, das Gedaechtnis steht
          unveraendert da UND der Δ-Anker traegt weiterhin die 20 km/h — der
          Ad-hoc-Abruf ist gegenueber beiden Zustaenden read-only.
    """
    from services.alert_state import AlertStateService
    from services.weather_snapshot import WeatherSnapshotService

    uid = f"tdd-ag5-adhoc-{uuid.uuid4().hex[:6]}"
    trip = _trip(f"trip-ag5-adhoc-{uuid.uuid4().hex[:6]}")

    WeatherSnapshotService(user_id=uid).save_dated(
        trip.id, date.today(), [_data(1, gust_max_kmh=20.0)]
    )
    vorher = {
        "gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"},
        "official_alert:region:Gailtal:thunderstorm:none:none": {
            "last_reported_value": 3.0, "reported_at": "x",
        },
    }
    AlertStateService(user_id=uid).save(trip.id, dict(vorher))

    recorder = _ResetRecorder(uid, lambda: _trip_anchor_gust(uid, trip.id))
    recorder.install(monkeypatch)

    scheduler = _scheduler_class(gust=48.0)(settings=_settings_no_transport(), user_id=uid)
    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=True)

    assert outcome in ("sent", "no_channels"), (
        f"Der Ad-hoc-Lauf ist vorzeitig abgebrochen: {outcome!r}"
    )
    assert recorder.calls == [], (
        f"Der Ad-hoc-Abruf darf keinen Reset ausloesen, gerufen fuer: "
        f"{recorder.calls!r} (AC-27, #1007)"
    )
    assert AlertStateService(user_id=uid).load(trip.id) == vorher, (
        f"Das Melde-Gedaechtnis muss unveraendert bleiben: "
        f"{AlertStateService(user_id=uid).load(trip.id)!r}"
    )
    assert _trip_anchor_gust(uid, trip.id) == pytest.approx(20.0), (
        "Der Ad-hoc-Abruf darf den Δ-Anker nicht ueberschreiben, gefunden: "
        f"{_trip_anchor_gust(uid, trip.id)!r} km/h statt 20.0 km/h (AC-27)"
    )


# ═════════════ AC-27 — Vertrag des geteilten Bausteins (RED heute) ══════════


def test_baustein_schreibt_anker_vor_reset():
    """AC-27 (Vertrag, RED heute).

    GIVEN ein Melde-Gedaechtnis mit einem Aenderungs-Eintrag und eine
          Anker-Schreibfunktion, die beim Aufruf festhaelt, WAS im Gedaechtnis
          zu diesem Zeitpunkt stand.
    WHEN  der geteilte Baustein mit `on_demand=False` laeuft.
    THEN  hat die Anker-Schreibfunktion das Gedaechtnis noch VOLLSTAENDIG
          vorgefunden — der Reset kommt danach — und danach ist der
          Aenderungs-Eintrag weg.

    Das ist kein `Mock(side_effect=...)`: die Anker-Schreibfunktion ist der
    vom Baustein vorgesehene Parameter, sie tut hier etwas Echtes (sie liest
    den tatsaechlichen Zustand von Platte ueber den echten
    `AlertStateService`) und ihr Befund wird gegen den ebenfalls echten
    Endzustand gehalten. Waere die Reihenfolge vertauscht, saehe sie ein
    leeres Gedaechtnis.

    RED-Grund (heute): `services/alert_briefing_anchor.py` existiert nicht.
    """
    from services.alert_briefing_anchor import write_anchor_and_reset_memory
    from services.alert_state import AlertStateService

    uid = f"tdd-ag5-contract-{uuid.uuid4().hex[:6]}"
    entity_id = "trip-ag5-contract"
    vorher = {"gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"}}
    AlertStateService(user_id=uid).save(entity_id, dict(vorher))

    gesehen: list[dict] = []

    def _write_anchor() -> None:
        gesehen.append(AlertStateService(user_id=uid).load(entity_id))

    write_anchor_and_reset_memory(
        user_id=uid, entity_ids=[entity_id], write_anchor=_write_anchor, on_demand=False,
    )

    assert gesehen == [vorher], (
        "Die Anker-Schreibfunktion muss VOR dem Reset laufen und das "
        f"Gedaechtnis noch vollstaendig vorfinden, gesehen: {gesehen!r}"
    )
    assert AlertStateService(user_id=uid).load(entity_id) == {}, (
        "Nach dem Baustein-Lauf muss der Aenderungs-Eintrag weg sein, gefunden: "
        f"{AlertStateService(user_id=uid).load(entity_id)!r}"
    )


def test_baustein_tut_bei_handversand_gar_nichts():
    """AC-27 (Vertrag, RED heute).

    GIVEN ein Melde-Gedaechtnis mit einem Aenderungs-Eintrag.
    WHEN  der geteilte Baustein mit `on_demand=True` laeuft.
    THEN  wird die Anker-Schreibfunktion GAR NICHT gerufen und das Gedaechtnis
          bleibt unveraendert — beide Zustaende haengen an EINER Bedingung.

    RED-Grund (heute): `services/alert_briefing_anchor.py` existiert nicht.
    """
    from services.alert_briefing_anchor import write_anchor_and_reset_memory
    from services.alert_state import AlertStateService

    uid = f"tdd-ag5-contract-od-{uuid.uuid4().hex[:6]}"
    entity_id = "trip-ag5-contract-od"
    vorher = {"gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"}}
    AlertStateService(user_id=uid).save(entity_id, dict(vorher))

    aufrufe: list[int] = []

    write_anchor_and_reset_memory(
        user_id=uid, entity_ids=[entity_id],
        write_anchor=lambda: aufrufe.append(1), on_demand=True,
    )

    assert aufrufe == [], (
        f"Bei on_demand=True darf der Anker nicht geschrieben werden: {aufrufe!r}"
    )
    assert AlertStateService(user_id=uid).load(entity_id) == vorher, (
        "Bei on_demand=True darf das Gedaechtnis nicht geleert werden, gefunden: "
        f"{AlertStateService(user_id=uid).load(entity_id)!r}"
    )


def test_baustein_setzt_jede_uebergebene_kennung_zurueck_und_schont_amtliche():
    """AC-27 (Vertrag, RED heute) — derselbe Baustein bedient Trip UND
    Ortsvergleich, also muss er beliebig viele Kennungen sauber abarbeiten und
    dabei `official_alert:`-Schluessel schonen (#1460 P2).

    GIVEN drei Kennungen mit unterschiedlichen Eintraegen, davon eine
          zusaetzlich mit einem amtlichen Eintrag.
    WHEN  der Baustein mit `on_demand=False` ueber alle drei laeuft.
    THEN  ist bei allen dreien der Aenderungs-Eintrag weg und der amtliche
          Eintrag unveraendert erhalten.

    RED-Grund (heute): `services/alert_briefing_anchor.py` existiert nicht.
    """
    from services.alert_briefing_anchor import write_anchor_and_reset_memory
    from services.alert_state import AlertStateService

    uid = f"tdd-ag5-contract-multi-{uuid.uuid4().hex[:6]}"
    official_key = "official_alert:region:Gailtal:thunderstorm:none:none"
    official_value = {"last_reported_value": 3.0, "reported_at": "x"}
    entity_ids = ["cp-x:loc-a", "cp-x:loc-b", "cp-x:loc-c"]
    werte = {"cp-x:loc-a": 60.0, "cp-x:loc-b": 45.0, "cp-x:loc-c": 30.0}

    state = AlertStateService(user_id=uid)
    for entity_id in entity_ids:
        payload = {
            f"precip_sum_mm:{entity_id.split(':')[1]}": {
                "last_reported_value": werte[entity_id], "reported_at": "x",
            }
        }
        if entity_id == "cp-x:loc-b":
            payload[official_key] = dict(official_value)
        state.save(entity_id, payload)

    write_anchor_and_reset_memory(
        user_id=uid, entity_ids=entity_ids, write_anchor=lambda: None, on_demand=False,
    )

    assert AlertStateService(user_id=uid).load("cp-x:loc-a") == {}
    assert AlertStateService(user_id=uid).load("cp-x:loc-c") == {}
    assert AlertStateService(user_id=uid).load("cp-x:loc-b") == {official_key: official_value}, (
        "Der amtliche Eintrag muss erhalten bleiben, der Aenderungs-Eintrag weg: "
        f"{AlertStateService(user_id=uid).load('cp-x:loc-b')!r}"
    )


def test_trip_delegiert_an_den_geteilten_baustein(monkeypatch):
    """AC-27 (Delegation, RED heute): der Trip behandelt Anker und Gedaechtnis
    nach dem Umbau NICHT mehr selbst, sondern ueber den EINEN geteilten
    Baustein — mit GENAU EINER Kennung (`trip.id`) und `on_demand=False`.

    Der Beobachter delegiert an die echte Funktion; geprueft wird zusaetzlich,
    dass die Wirkung (Gedaechtnis geleert, Anker gesetzt) danach eintritt —
    ein Beobachter allein wuerde eine wirkungslose Delegation nicht bemerken.

    RED-Grund (heute): `services/alert_briefing_anchor.py` existiert nicht.
    """
    import services.alert_briefing_anchor as anchor_mod
    import services.trip_report_scheduler as trs_mod
    from services.alert_state import AlertStateService

    uid = f"tdd-ag5-tripdeleg-{uuid.uuid4().hex[:6]}"
    trip = _trip(f"trip-ag5-tripdeleg-{uuid.uuid4().hex[:6]}")
    AlertStateService(user_id=uid).save(trip.id, {
        "gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"},
    })

    calls: list[dict] = []
    original = anchor_mod.write_anchor_and_reset_memory

    def _spy(*args, **kwargs):
        calls.append(dict(kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(anchor_mod, "write_anchor_and_reset_memory", _spy)
    if hasattr(trs_mod, "write_anchor_and_reset_memory"):
        monkeypatch.setattr(trs_mod, "write_anchor_and_reset_memory", _spy)

    scheduler = _scheduler_class(gust=33.0)(settings=_settings_no_transport(), user_id=uid)
    scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert len(calls) == 1, (
        f"Der geteilte Baustein muss genau einmal je Briefing laufen: {len(calls)}"
    )
    assert list(calls[0].get("entity_ids") or []) == [trip.id], (
        f"Der Trip liefert GENAU EINE Kennung: {calls[0].get('entity_ids')!r}"
    )
    assert calls[0].get("on_demand") is False, f"on_demand muss False sein: {calls[0]!r}"
    assert calls[0].get("user_id") == uid, (
        f"Die echte user_id muss durchgereicht werden (nie 'default'): {calls[0]!r}"
    )
    assert AlertStateService(user_id=uid).load(trip.id) == {}, (
        "Die Delegation muss auch wirken: das Gedaechtnis ist nicht geleert"
    )
    assert _trip_anchor_gust(uid, trip.id) == pytest.approx(33.0), (
        f"Die Delegation muss auch den Anker setzen: {_trip_anchor_gust(uid, trip.id)!r}"
    )
