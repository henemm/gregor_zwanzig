"""TDD RED — Issue #1439: Starkregen-Kurzfristhinweis im planmaessigen Trip-Briefing.

SPEC: docs/specs/modules/feat_1439_starkregen_kurzfristhinweis.md (AC-1 … AC-8)

RED-Grund heute (gemessen): die Einbindung existiert noch nicht.
- `services.trip_report_scheduler.TripReportSchedulerService._build_starkregen_hint`
  (o.ae.) fehlt -> der Kurzfristhinweis erscheint nie, `RadarNowcastService.get_nowcast()`
  wird fuer den Scheduler-Pfad nie aufgerufen.
- `services.radar_service.NOWCAST_HORIZON_MIN` (oeffentlicher Alias) fehlt (AC-2).
- `docs/specs/data_sources.md` hat noch keinen `minutely_15`-Eintrag (AC-8).

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"):
- Kein Mock-Theater: kein `Mock()`/`patch()`/`MagicMock`. `RadarNowcastService.get_nowcast`
  wird per `monkeypatch.setattr` durch eine echte Python-Funktion ersetzt, die ein echtes
  `NowcastResult`-Dataclass-Objekt liefert (Transport-Grenze, analog dem projektweiten
  `mail_sink`-Muster) — kein Live-Netz, kein Objekt-Double, das nur die eigene Annahme
  zurueckspiegelt.
- Wirkung statt Faehigkeit: AC-3/AC-7 pruefen den ECHTEN gerenderten Text (E-Mail HTML+Plain,
  Telegram-Bubbles) ueber den echten Versandpfad `_send_trip_report_outcome`, abgegriffen
  per DELEGIERENDEM Beobachter auf `TripReportFormatter.format_email` (Muster
  `tests/tdd/test_alert_undelivered_hint.py::_ReportRecorder` /
  `tests/tdd/test_trip_briefing_anchor_unchanged.py`) — kein Dateiinhalt-Grep.
- AC-6 (Mutations-Pflicht, PFLICHT laut Spec): der Test laeuft ueber den ECHTEN
  `TripAlertService.check_radar_alerts()`-Pfad (Muster
  `tests/tdd/test_issue_818_radar_briefing_integration.py`) — wird die
  `ThrottleStore.record("radar", trip.id, ...)`-Zeile im Scheduler entfernt, feuert der
  zweite Radar-Alert-Lauf wirklich (count >= 1 statt 0).

Pfadregel #1409: `REPO_ROOT` wird relativ zu DIESER Datei aufgeloest.
Isolation: `tests/conftest.py::_isolate_data_root` (autouse, #1133) — keine manuelle
Aufraeumung noetig.
"""
from __future__ import annotations

import re
import uuid
from datetime import date as date_type, datetime, time, timedelta, timezone
from pathlib import Path

from freezegun import freeze_time

from app.config import Settings
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services import alert_daily_limit
from utils.timezone import tz_for_coords
from services.radar_service import (
    INTENSITY_CONVECTIVE, INTENSITY_DRY, INTENSITY_HEAVY, INTENSITY_MODERATE,
    NowcastResult, RadarNowcastService,
)

from tests.helpers.alert_log_fixtures import settings_email_only, weather

REPO_ROOT = Path(__file__).resolve().parents[2]

# Island: UTC+0 ganzjaehrig (kein DST) — vereinfacht Zeit-Arithmetik fuer
# arrival_override-Zeitstrings (Muster test_issue_818_radar_briefing_integration.py).
LAT, LON = 64.0, -22.0

_HINT_MARKER = "Starker Regen ab ca."

# Adversary-Finding F001 (#1439): `format_starkregen_hint()` baut den Text aus
# dem UEBERGEBENEN `intensity_label`, nicht aus einer festen Konstante — ein
# entfernter Intensitaets-Filter in `_build_starkregen_hint` wuerde weiterhin
# einen Hinweistext erzeugen (nur mit einem ANDEREN Label als Praefix), den
# der feste `_HINT_MARKER`-Substring-Check nicht saehe. Fuer "Hinweis darf
# NICHT erscheinen"-Assertions bei nicht-HEAVY-Intensitaeten (AC-4b/AC-7) wird
# deshalb das intensitaetsunabhaengige Zeitformat geprueft, nicht der feste String.
_HINT_TIME_PATTERN = re.compile(r"ab ca\. \d{2}:\d{2} \(in ~\d+ Min\)\.")

_NO_TRANSPORT_FIELDS: dict = {
    "smtp_host": "", "smtp_user": "", "smtp_pass": "", "mail_to": "",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _uid(prefix: str) -> str:
    return f"tdd-1439-{prefix}-{uuid.uuid4().hex[:6]}"


def _settings_no_transport() -> Settings:
    return Settings(**_NO_TRANSPORT_FIELDS)


# ═══════════════════════════ Trip-Fixtures ═══════════════════════════


def _active_trip(trip_id: str) -> Trip:
    """2-Waypoint-Trip mit ganztaegig aktivem Segment (00:00-23:59 Ortszeit).

    Muster: test_issue_818_radar_briefing_integration.py::_make_active_trip.
    """
    today = date_type.today()
    wp0 = Waypoint(
        id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=100.0,
        arrival_override="00:00",
    )
    wp1 = Waypoint(
        id="WP1", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=200.0,
        arrival_override="23:59",
    )
    stage = Stage(id="S1", name="Tag 1", date=today, start_time=time(0, 0), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name=f"Starkregen {trip_id}", stages=[stage], official_alerts_enabled=False)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False,
    )
    return trip


def _trip_with_segment_offset(trip_id: str, *, start_in_min: float, duration_min: float = 20.0) -> Trip:
    """Aktives/naechstes Segment beginnt in `start_in_min` Minuten ab jetzt (UTC).

    Issue #2096: der frueher hier stehende Selbst-Skip ("Testzeitpunkt zu nah
    an einer Mitternachtsgrenze") ist ERSATZLOS entfallen. Er fing einen
    Zufall der Wanduhr ab; die Aufrufer stellen die Uhr inzwischen fest
    (`freeze_time`), damit gibt es diesen Zufall nicht mehr. Ein Test, der
    sich still selbst ueberspringt, ist ein Waechter-Loch: er meldet Gruen,
    ohne etwas geprueft zu haben. Wer diese Fixture kuenftig ohne gestellte
    Uhr aufruft, bekommt einen Fehlschlag statt eines stillen Skips -- und
    das ist die richtige Meldung.
    """
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now + timedelta(minutes=start_in_min)
    end = start + timedelta(minutes=duration_min)

    wp0 = Waypoint(
        id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=100.0,
        arrival_override=start.strftime("%H:%M"),
    )
    wp1 = Waypoint(
        id="WP1", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=200.0,
        arrival_override=end.strftime("%H:%M"),
    )
    stage = Stage(id="S1", name="Tag 1", date=start.date(), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name=f"Starkregen {trip_id}", stages=[stage], official_alerts_enabled=False)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False,
    )
    return trip


def _save_trip_direct(trip: Trip, user_id: str) -> None:
    """Schreibt die Trip-JSON direkt — noetig fuer TripAlertService.check_radar_alerts()
    (liest ueber app.loader.load_all_trips(), nicht aus dem In-Memory-Objekt).

    Muster: test_issue_818_radar_briefing_integration.py::_save_trip_direct.
    """
    import json

    from app.loader import get_briefings_dir

    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    stage = trip.stages[0]
    wp_list = []
    for wp in stage.waypoints:
        d: dict = {"id": wp.id, "name": wp.name, "lat": wp.lat, "lon": wp.lon}
        if wp.elevation_m is not None:
            d["elevation_m"] = wp.elevation_m
        if wp.arrival_override is not None:
            d["arrival_override"] = wp.arrival_override
        wp_list.append(d)
    data = {
        "id": trip.id,
        "name": trip.name,
        "official_alerts_enabled": False,
        "stages": [{
            "id": stage.id, "name": stage.name,
            "date": stage.date.isoformat(), "waypoints": wp_list,
        }],
        "report_config": {"trip_id": trip.id, "send_email": True, "send_telegram": False},
    }
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data, indent=2))


# ═══════════════════════════ Scheduler / Recorder ═══════════════════════════


def _scheduler_class():
    """Echte Unterklasse (kein Mock): Wetter kommt aus der Fixture, kein Netz."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class _FixtureScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return [weather(s.segment_id) for s in segments]

    return _FixtureScheduler


class _ReportRecorder:
    """DELEGIERENDER Beobachter auf `TripReportFormatter.format_email`.

    Kein Mock: die echte Methode laeuft unveraendert, es wird nur festgehalten,
    WAS sie zurueckgegeben hat. Muster: test_alert_undelivered_hint.py::_ReportRecorder.
    """

    def __init__(self) -> None:
        self.reports: list = []

    def install(self, monkeypatch) -> None:
        from output.renderers.trip_report import TripReportFormatter

        original = TripReportFormatter.format_email
        recorder = self

        def _recording_format_email(self, *args, **kwargs):
            report = original(self, *args, **kwargs)
            recorder.reports.append(report)
            return report

        monkeypatch.setattr(TripReportFormatter, "format_email", _recording_format_email)


def _run_briefing(recorder: _ReportRecorder, uid: str, trip: Trip, *, settings: Settings | None = None):
    """Fuehrt den ECHTEN Briefing-Pfad aus und liefert (outcome, report)."""
    scheduler = _scheduler_class()(settings=settings or _settings_no_transport(), user_id=uid)
    outcome = scheduler._send_trip_report_outcome(trip, "morning")
    assert recorder.reports, "Voraussetzung: es wurde keine Briefing-Mail gebaut"
    return outcome, recorder.reports[-1]


# ═══════════════════════════ Nowcast-DI-Naht (kein Mock) ═══════════════════════════


def _install_fake_nowcast(
    monkeypatch,
    calls: list,
    *,
    onset_minutes: int | None = None,
    intensity_label: str = INTENSITY_DRY,
    is_convective: bool = False,
    raise_exc: Exception | None = None,
    source_reach_minutes: int | None = None,
) -> None:
    """Ersetzt `RadarNowcastService.get_nowcast` durch eine echte Funktion, die ein
    echtes `NowcastResult` liefert (Transport-Grenze, kein Live-Netz, kein Mock-Objekt).
    `calls` haelt (lat, lon, priority)-Tupel jedes Aufrufs fest (AC-1/AC-2-Nachweis).

    `source_reach_minutes` additiv (Issue #2051 S3): ohne sie bleibt das
    `NowcastResult` unveraendert (`None`, Bestandsverhalten)."""

    def _fake_get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
        calls.append((lat, lon, priority))
        if raise_exc is not None:
            raise raise_exc
        return NowcastResult(
            onset_minutes=onset_minutes, intensity_label=intensity_label,
            source="radar", is_convective=is_convective,
            source_reach_minutes=source_reach_minutes,
        )

    monkeypatch.setattr(RadarNowcastService, "get_nowcast", _fake_get_nowcast)


def _install_fake_email_send(monkeypatch, sent: list) -> None:
    """Ersetzt den Transport-Rand `EmailOutput.send` — echte Funktion, kein Netz,
    kein Mock-Objekt. Noetig fuer AC-6 (echtes outcome='sent')."""
    from output.channels.email import EmailOutput

    def _fake_send(self, *, subject, body, **kwargs):
        sent.append((subject, body))

    monkeypatch.setattr(EmailOutput, "send", _fake_send)


def _wet_frames(lat: float, lon: float) -> list:
    """Deterministische Regen-Frames (onset in 5 Min) — DI-Seam, kein Mock.

    Muster: test_issue_818_radar_briefing_integration.py::_wet_frames.
    """
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0),
    ]


# ══════════════════════════════════ AC-1 ══════════════════════════════════


def test_ac1_budget_erschoepft_blockiert_fetch_und_hinweis(monkeypatch):
    """AC-1: ausgeschoepftes Tagesbudget (reason='nowcast') -> kein get_nowcast()-
    Aufruf, keine Hinweiszeile.

    Nicht-Leerlauf zuerst (Muster test_alert_undelivered_hint.py AC-10): OHNE
    ausgeschoepftes Budget MUSS derselbe Trigger einen Hinweis erzeugen — sonst
    prueft der Budget-Vergleich gegen ein bereits leeres Ergebnis (Feature fehlt
    komplett) und waere nie in der Lage, rot zu werden.
    """
    calls_frei: list = []
    _install_fake_nowcast(monkeypatch, calls_frei, onset_minutes=10, intensity_label=INTENSITY_HEAVY)
    uid_frei = _uid("ac1-frei")
    trip_frei = _active_trip(f"trip-ac1-frei-{uuid.uuid4().hex[:6]}")
    rec_frei = _ReportRecorder()
    rec_frei.install(monkeypatch)
    _outcome_frei, report_frei = _run_briefing(rec_frei, uid_frei, trip_frei)
    assert len(calls_frei) >= 1 and _HINT_MARKER in report_frei.email_plain, (
        "Testvoraussetzung (Nicht-Leerlauf): OHNE ausgeschoepftes Budget MUSS "
        f"derselbe Trigger get_nowcast() aufrufen und einen Hinweis erzeugen "
        f"— calls={calls_frei!r}\n{report_frei.email_plain}"
    )

    uid = _uid("ac1")
    trip = _active_trip(f"trip-ac1-{uuid.uuid4().hex[:6]}")

    now = datetime.now(timezone.utc)
    # Issue #1726: der Zaehler laeuft in der Ortszone der TOUR — `LAT`/`LON`
    # liegen auf Island. Wer hier eine andere Zone belegt als der Pruefling
    # liest, erschoepft ein Kontingent, das nie geprueft wird.
    trip_zone = tz_for_coords(LAT, LON)
    alert_daily_limit.increment(uid, now, trip_zone)
    alert_daily_limit.increment(uid, now, trip_zone)
    assert alert_daily_limit.is_allowed(uid, now, trip_zone, reason="nowcast") is False, (
        "Testvoraussetzung: Free-Tier-Tageslimit (2) muss ausgeschoepft sein."
    )

    calls: list = []
    _install_fake_nowcast(monkeypatch, calls, onset_minutes=10, intensity_label=INTENSITY_HEAVY)

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    _outcome, report = _run_briefing(recorder, uid, trip)

    assert calls == [], (
        "AC-1: RadarNowcastService.get_nowcast() darf bei ausgeschoepftem "
        f"Tagesbudget NICHT aufgerufen werden, war {calls!r}. "
        "RED: Budget-Gate vor dem Fetch ist noch nicht implementiert."
    )
    assert _HINT_MARKER not in report.email_plain, (
        "AC-1: Bei ausgeschoepftem Budget darf keine Starkregen-Kurzfristhinweis-"
        f"Zeile erscheinen.\n--- Klartext ---\n{report.email_plain}"
    )


# ══════════════════════════════════ AC-2 ══════════════════════════════════


def test_ac2_zeitfenster_guard_kein_fetch_ausserhalb_horizon(monkeypatch):
    """AC-2: Segment > NOWCAST_HORIZON_MIN entfernt -> kein Fetch/Hinweis;
    Segment innerhalb -> Fetch UND Hinweis (Gegenprobe im selben Test)."""
    from services.radar_service import NOWCAST_HORIZON_MIN

    assert NOWCAST_HORIZON_MIN == 180, (
        f"Testvoraussetzung: NOWCAST_HORIZON_MIN muss 180 sein, war {NOWCAST_HORIZON_MIN!r}."
    )

    # Fern: Segment beginnt in 200 Minuten (> 180) -> kein Fetch, kein Hinweis.
    # Feste Uhr (#1945): mit 200 Min Offset wuerde der Mitternachts-Guard in
    # `_trip_with_segment_offset` den Fall ab ~20:20 UTC wegskippen statt beweisen.
    with freeze_time("2026-08-17T10:00:00+00:00"):
        uid_fern = _uid("ac2-fern")
        trip_fern = _trip_with_segment_offset(
            f"trip-ac2-fern-{uuid.uuid4().hex[:6]}", start_in_min=200
        )
        calls_fern: list = []
        _install_fake_nowcast(
            monkeypatch, calls_fern, onset_minutes=10, intensity_label=INTENSITY_HEAVY
        )
        rec_fern = _ReportRecorder()
        rec_fern.install(monkeypatch)
        _outcome_fern, report_fern = _run_briefing(rec_fern, uid_fern, trip_fern)

        assert calls_fern == [], (
            "AC-2: Segment beginnt erst in 200 Minuten (> NOWCAST_HORIZON_MIN=180) -> "
            f"get_nowcast() darf NICHT aufgerufen werden, war {calls_fern!r}."
        )
        assert _HINT_MARKER not in report_fern.email_plain, (
            f"AC-2: kein Hinweis erwartet ausserhalb des Horizonts.\n{report_fern.email_plain}"
        )

    # Nah: Segment beginnt in 30 Minuten (<= 180) -> Fetch UND Hinweis.
    # Feste Uhr auch hier (#2096): frueher lief dieser Zweig auf der Wanduhr
    # und uebersprang sich ab ~23:30 UTC still selbst. Ein Test, der abends
    # nichts prueft und trotzdem gruen meldet, bewacht nichts.
    with freeze_time("2026-08-17T10:00:00+00:00"):
        uid_nah = _uid("ac2-nah")
        trip_nah = _trip_with_segment_offset(
            f"trip-ac2-nah-{uuid.uuid4().hex[:6]}", start_in_min=30
        )
        calls_nah: list = []
        _install_fake_nowcast(
            monkeypatch, calls_nah, onset_minutes=10, intensity_label=INTENSITY_HEAVY
        )
        rec_nah = _ReportRecorder()
        rec_nah.install(monkeypatch)
        _outcome_nah, report_nah = _run_briefing(rec_nah, uid_nah, trip_nah)

        assert len(calls_nah) >= 1, (
            "AC-2 (Gegenprobe): Segment beginnt in 30 Minuten (<= Horizont) -> "
            f"get_nowcast() MUSS aufgerufen werden, war {calls_nah!r}."
        )
        assert _HINT_MARKER in report_nah.email_plain, (
            "AC-2 (Gegenprobe): innerhalb des Horizonts MUSS der Hinweis erscheinen.\n"
            f"{report_nah.email_plain}"
        )


# ══════════════════════════════════ AC-3 ══════════════════════════════════


def test_ac3_email_und_telegram_zeigen_identische_hinweiszeile(monkeypatch):
    """AC-3: HTML, Plain und Telegram tragen dieselbe Hinweiszeile mit
    identischer Uhrzeit — echte Renderer-Ausgabe, kein Dateiinhalt-Grep."""
    uid = _uid("ac3")
    trip = _active_trip(f"trip-ac3-{uuid.uuid4().hex[:6]}")

    calls: list = []
    _install_fake_nowcast(monkeypatch, calls, onset_minutes=15, intensity_label=INTENSITY_HEAVY)

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    _outcome, report = _run_briefing(recorder, uid, trip)

    assert len(calls) >= 1, "Testvoraussetzung: get_nowcast() muss aufgerufen worden sein."

    match = re.search(r"Starker Regen ab ca\. \d{2}:\d{2} \(in ~15 Min\)\.", report.email_plain)
    assert match is not None, (
        "AC-3: Der Klartext-Teil muss die Hinweiszeile im Format "
        f"'Starker Regen ab ca. HH:MM (in ~15 Min).' enthalten.\n{report.email_plain}"
    )
    hint_line = match.group(0)

    html_text = re.sub(r"<[^>]+>", "\n", report.email_html)
    assert hint_line in html_text, (
        f"AC-3: Dieselbe Hinweiszeile muss im HTML-Teil erscheinen.\n--- HTML als Text ---\n{html_text}"
    )

    telegram_text = "\n".join(report.telegram_bubbles)
    assert hint_line in telegram_text, (
        f"AC-3: Dieselbe Hinweiszeile muss in der Telegram-Ausgabe erscheinen.\n{telegram_text}"
    )


# ═══════════════════════ Issue #2051 S3 (Adversary-Fund F002) ═══════════════════════


def test_2051s3_briefing_hinweis_traegt_die_reichweite_ueber_den_echten_scheduler_pfad(
    monkeypatch,
):
    """Issue #2051 S3, Adversary-Fund F002: `_build_starkregen_hint()` gab bis
    zu diesem Fix ein Fuenf-Tupel zurueck, das `result.source_reach_minutes`
    NICHT enthielt -- die Reichweite kam am Briefing-Kurzfristhinweis nie an,
    obwohl genau dieser Pfad (ohne Vorlauf-Deckel) der Ticket-Realfall ist.

    Der bisherige Test fuer `source_reach_minutes` in `format_starkregen_hint`
    (`test_nowcast_source_reach_textstellen.py`) ruft die Funktion DIREKT auf
    und umgeht damit den einzigen produktiven Aufrufer
    (`NotificationService`s Tupel-Entpackung) -- eine gestubbte Naht. DIESER
    Test faehrt stattdessen den ECHTEN Scheduler-Pfad
    (`_send_trip_report_outcome` -> `_build_starkregen_hint` -> Tupel ->
    `NotificationService` -> `format_starkregen_hint` -> echter Renderer),
    Muster AC-3 oben.

    GIVEN ein `NowcastResult` mit `intensity_label=INTENSITY_HEAVY`,
    `onset_minutes` gesetzt UND `source_reach_minutes=120`
    WHEN der echte Briefing-Pfad laeuft
    THEN traegt der Klartext-Teil zusaetzlich zur bestehenden Hinweiszeile
    `Radar reicht bis HH:MM` MIT der aus den injizierten 120 Minuten
    HERGELEITETEN Uhrzeit -- nicht nur irgendeine.

    Adversary-Fund F003 (Adversary-Runde 2): eine reine Format-Pruefung
    (`\\d{2}:\\d{2}`) liess ein auf `9999` verfaelschtes sechstes Tupelglied
    unbemerkt durch -- der Test bewachte, DASS etwas dasteht, nicht DASS es
    stimmt. Island (LAT/LON dieser Datei) ist UTC+0 ganzjaehrig, deshalb
    entspricht die erwartete Uhrzeit direkt `datetime.now(UTC) + 120 Min`,
    mit einer Wanduhr-Toleranz von 1 Minute (Muster
    `test_onset_reichweite_guete_kanalparitaet.py`).

    RED vor dem Fix: das Fuenf-Tupel transportierte `source_reach_minutes`
    nicht -- `NotificationService` uebergab es folglich nie an
    `format_starkregen_hint`, die Reichweite fehlte im Text."""
    uid = _uid("s3-reach")
    trip = _active_trip(f"trip-s3-reach-{uuid.uuid4().hex[:6]}")

    calls: list = []
    _install_fake_nowcast(
        monkeypatch, calls, onset_minutes=15, intensity_label=INTENSITY_HEAVY,
        source_reach_minutes=120,
    )

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    _outcome, report = _run_briefing(recorder, uid, trip)

    assert len(calls) >= 1, "Testvoraussetzung: get_nowcast() muss aufgerufen worden sein."
    assert _HINT_MARKER in report.email_plain, (
        f"Vorbedingung: die bestehende Hinweiszeile muss weiterhin stehen: "
        f"{report.email_plain}"
    )
    treffer = re.search(r"Radar reicht bis (\d{2}:\d{2})", report.email_plain)
    assert treffer is not None, (
        f"F002: die Reichweite kommt ueber den echten Scheduler-Pfad nicht "
        f"am Briefing-Hinweis an: {report.email_plain}"
    )

    # F003: der WERT muss aus den injizierten 120 Minuten hergeleitet sein,
    # nicht nur irgendeine HH:MM-Zeichenkette. `datetime.now()` erst NACH
    # dem Lauf gelesen (Island ist ganzjaehrig UTC+0, keine Zonenumrechnung
    # noetig) -- die 1-Minuten-Toleranz deckt den Zeitversatz zwischen
    # diesem Aufruf und dem `datetime.now()` im Produktivcode ab (Muster
    # `test_onset_reichweite_guete_kanalparitaet.py::_abstand_minuten`).
    def _minuten(hhmm: str) -> int:
        stunde, _, minute = hhmm.partition(":")
        return int(stunde) * 60 + int(minute)

    erwartet = (datetime.now(timezone.utc) + timedelta(minutes=120)).strftime("%H:%M")
    abstand = abs(_minuten(treffer.group(1)) - _minuten(erwartet))
    abstand = min(abstand, 24 * 60 - abstand)
    assert abstand <= 1, (
        f"F003: die Reichweiten-Uhrzeit {treffer.group(1)!r} stammt nicht "
        f"aus den injizierten 120 Minuten (erwartet nahe {erwartet!r} UTC, "
        f"Island ist ganzjaehrig UTC+0): {report.email_plain}"
    )


# ══════════════════════════════════ AC-4 ══════════════════════════════════


def _assert_hint_control_case_works(monkeypatch, prefix: str) -> None:
    """Nicht-Leerlauf-Voraussetzung (Muster test_alert_undelivered_hint.py AC-10):
    ein regulaerer INTENSITY_HEAVY-Trigger MUSS einen Hinweis erzeugen — sonst
    pruefen die Negativ-Faelle unten gegen ein strukturell immer leeres Ergebnis
    (Feature fehlt komplett) und koennten nie rot werden."""
    calls: list = []
    _install_fake_nowcast(monkeypatch, calls, onset_minutes=10, intensity_label=INTENSITY_HEAVY)
    uid = _uid(f"{prefix}-kontrolle")
    trip = _active_trip(f"trip-{prefix}-kontrolle-{uuid.uuid4().hex[:6]}")
    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    _outcome, report = _run_briefing(recorder, uid, trip)
    assert len(calls) >= 1 and _HINT_MARKER in report.email_plain, (
        "Testvoraussetzung (Nicht-Leerlauf): ein INTENSITY_HEAVY-Trigger MUSS "
        f"einen Hinweis erzeugen — calls={calls!r}\n{report.email_plain}"
    )


def test_ac4_nowcast_fehler_kein_absturz_kein_hinweis(monkeypatch):
    """AC-4 (Fail-soft, ADR-0018): get_nowcast() wirft -> Versand laeuft
    unveraendert durch, keine Hinweiszeile, kein Crash."""
    _assert_hint_control_case_works(monkeypatch, "ac4")

    uid = _uid("ac4")
    trip = _active_trip(f"trip-ac4-{uuid.uuid4().hex[:6]}")

    calls: list = []
    _install_fake_nowcast(monkeypatch, calls, raise_exc=RuntimeError("simulierter Nowcast-Ausfall"))

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    outcome, report = _run_briefing(recorder, uid, trip)

    assert outcome in ("sent", "no_channels"), (
        f"AC-4: der Versand-Lauf darf trotz Nowcast-Fehler nicht abbrechen, war {outcome!r}."
    )
    assert _HINT_MARKER not in report.email_plain
    assert _HINT_MARKER not in report.email_html
    assert _HINT_MARKER not in "\n".join(report.telegram_bubbles)


def test_ac4b_kein_treffer_oder_unterschwellig_kein_hinweis(monkeypatch):
    """AC-4 (Rest): onset_minutes=None bzw. Intensitaet unter INTENSITY_HEAVY
    -> ebenfalls kein Hinweis."""
    _assert_hint_control_case_works(monkeypatch, "ac4b")

    for label, kwargs in (
        ("kein_treffer", dict(onset_minutes=None, intensity_label=INTENSITY_DRY)),
        ("unterschwellig", dict(onset_minutes=10, intensity_label=INTENSITY_MODERATE)),
    ):
        uid = _uid(f"ac4b-{label}")
        trip = _active_trip(f"trip-ac4b-{label}-{uuid.uuid4().hex[:6]}")
        calls: list = []
        _install_fake_nowcast(monkeypatch, calls, **kwargs)
        recorder = _ReportRecorder()
        recorder.install(monkeypatch)
        _outcome, report = _run_briefing(recorder, uid, trip)
        assert _HINT_TIME_PATTERN.search(report.email_plain) is None, (
            f"AC-4 ({label}): kwargs={kwargs!r} darf keinen Hinweis (in keinem "
            f"Intensitaets-Wortlaut) erzeugen.\n{report.email_plain}"
        )


# ══════════════════════════════════ AC-5 ══════════════════════════════════


def test_ac5_sms_bleibt_zeichengleich_trotz_trigger(monkeypatch):
    """AC-5: SMS-Text bleibt byte-identisch, egal ob der Starkregen-Trigger
    vorliegt oder nicht (SMS ist bewusst ausserhalb des MVP-Scopes)."""
    trip_id = f"trip-ac5-{uuid.uuid4().hex[:6]}"

    uid_mit = _uid("ac5-mit")
    trip_mit = _active_trip(trip_id)
    trip_mit.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=True,
    )
    _install_fake_nowcast(monkeypatch, [], onset_minutes=10, intensity_label=INTENSITY_HEAVY)
    rec_mit = _ReportRecorder()
    rec_mit.install(monkeypatch)
    _outcome_mit, report_mit = _run_briefing(rec_mit, uid_mit, trip_mit)

    assert _HINT_MARKER in report_mit.email_plain, (
        "Testvoraussetzung: der Trigger muss die E-Mail-Ausgabe DIESES Laufs "
        f"beeinflussen, sonst prueft der SMS-Vergleich nichts.\n{report_mit.email_plain}"
    )

    uid_ohne = _uid("ac5-ohne")
    trip_ohne = _active_trip(trip_id)
    trip_ohne.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=True,
    )
    _install_fake_nowcast(monkeypatch, [], onset_minutes=None, intensity_label=INTENSITY_DRY)
    rec_ohne = _ReportRecorder()
    rec_ohne.install(monkeypatch)
    _outcome_ohne, report_ohne = _run_briefing(rec_ohne, uid_ohne, trip_ohne)

    assert report_mit.sms_text == report_ohne.sms_text, (
        "AC-5: Der SMS-Text muss trotz Starkregen-Trigger byte-identisch bleiben.\n"
        f"mit:  {report_mit.sms_text!r}\nohne: {report_ohne.sms_text!r}"
    )


# ══════════════════════════════════ AC-6 (Mutations-Pflicht) ══════════════════════════════════


def test_ac6_versendeter_hinweis_wirft_throttle_der_folgealarm_unterdrueckt(monkeypatch):
    """AC-6 (PFLICHT laut Spec — Mutations-Gegenprobe): nach einem versendeten
    Kurzfristhinweis unterdrueckt der bestehende Radar-Throttle einen erneuten
    Radar-Alert im Cooldown-Fenster.

    Wird `ThrottleStore.record("radar", trip.id, ...)` im Scheduler entfernt,
    MUSS genau dieser Test rot werden: `_is_radar_throttled` findet dann keinen
    Eintrag, der zweite Lauf faehrt bis zum injizierten Nowcast durch und sendet
    tatsaechlich (count >= 1 statt 0).
    """
    from services.throttle_store import ThrottleStore
    from services.trip_alert import TripAlertService

    uid = _uid("ac6")
    trip_id = f"trip-ac6-{uuid.uuid4().hex[:6]}"
    trip = _active_trip(trip_id)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False, send_sms=False,
    )
    _save_trip_direct(trip, uid)

    calls: list = []
    _install_fake_nowcast(monkeypatch, calls, onset_minutes=15, intensity_label=INTENSITY_HEAVY)
    sent_mails: list = []
    _install_fake_email_send(monkeypatch, sent_mails)

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)

    outcome, report = _run_briefing(recorder, uid, trip, settings=settings_email_only())

    assert outcome == "sent", (
        f"Testvoraussetzung: der Briefing-Versand muss als 'sent' durchlaufen, war {outcome!r}."
    )
    assert _HINT_MARKER in report.email_plain, (
        "Testvoraussetzung: der Kurzfristhinweis muss im versendeten Briefing stehen.\n"
        f"--- Klartext ---\n{report.email_plain}"
    )

    last_sent = ThrottleStore(uid).last_sent("radar", trip.id)
    assert last_sent is not None, (
        "AC-6: Nach einem versendeten Kurzfristhinweis MUSS der Radar-Throttle "
        "gesetzt sein (ThrottleStore.record('radar', trip.id, ...)). "
        "RED: Der Scheduler schreibt den Throttle noch nicht."
    )

    captured: list = []
    svc = TripAlertService(
        throttle_hours=2, user_id=uid,
        radar_service=RadarNowcastService(frame_source=_wet_frames),
        mail_sink=lambda subject, body: captured.append((subject, body)),
    )
    count = svc.check_radar_alerts()

    assert count == 0, (
        "AC-6 (Mutations-Pflicht): Ein Radar-Alert innerhalb des Cooldown-Fensters "
        "MUSS durch denselben Throttle-Eintrag unterdrueckt werden, den der "
        f"Kurzfristhinweis geschrieben hat — war count={count}. Wird "
        "ThrottleStore.record('radar', trip.id, ...) im Scheduler entfernt (oder nie "
        "erreicht), feuert dieser zweite Lauf tatsaechlich einen Alert."
    )
    assert captured == [], (
        "AC-6: mail_sink darf nicht aufgerufen werden — der Folge-Alert muss "
        f"unterdrueckt bleiben, war {captured!r}."
    )


# ══════════════════════════════════ AC-7 ══════════════════════════════════


def test_ac7_gewitter_erzeugt_keinen_starkregen_hinweis(monkeypatch):
    """AC-7: Gewitter/Hagel (is_convective=True, INTENSITY_CONVECTIVE) erzeugt
    KEINEN Starkregen-Kurzfristhinweis — der ist ausschliesslich fuer
    INTENSITY_HEAVY reserviert."""
    _assert_hint_control_case_works(monkeypatch, "ac7")

    uid = _uid("ac7")
    trip = _active_trip(f"trip-ac7-{uuid.uuid4().hex[:6]}")

    calls: list = []
    _install_fake_nowcast(
        monkeypatch, calls, onset_minutes=10,
        intensity_label=INTENSITY_CONVECTIVE, is_convective=True,
    )

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    _outcome, report = _run_briefing(recorder, uid, trip)

    assert _HINT_TIME_PATTERN.search(report.email_plain) is None, (
        "AC-7: Gewitter/Hagel darf keinen Starkregen-Hinweis (in keinem "
        f"Intensitaets-Wortlaut) im Klartext erzeugen.\n{report.email_plain}"
    )
    assert _HINT_TIME_PATTERN.search(report.email_html) is None, (
        "AC-7: Gewitter/Hagel darf keinen Starkregen-Hinweis (in keinem "
        "Intensitaets-Wortlaut) im HTML erzeugen."
    )
    telegram_text = "\n".join(report.telegram_bubbles)
    assert _HINT_TIME_PATTERN.search(telegram_text) is None, (
        "AC-7: Gewitter/Hagel darf keinen Starkregen-Hinweis (in keinem "
        f"Intensitaets-Wortlaut) in Telegram erzeugen.\n{telegram_text}"
    )


# ══════════════════════════════════ AC-8 ══════════════════════════════════


def test_ac8_data_sources_doku_traegt_minutely15_nachtrag():
    """AC-8. # doc-compliance-test"""
    path = REPO_ROOT / "docs" / "specs" / "data_sources.md"
    text = path.read_text(encoding="utf-8")
    assert "minutely_15" in text, (
        "AC-8: docs/specs/data_sources.md muss einen Eintrag fuer 'minutely_15' "
        "enthalten (Nachtrag — bereits seit #656 produktiv genutzt)."
    )
