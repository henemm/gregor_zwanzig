"""TDD RED — Issue #1012: Kein Briefing bei komplettem Wetterdaten-Ausfall.

Root Cause: `_send_trip_report_outcome()`s Guard `if not segment_weather`
greift nie, weil `_fetch_weather()` bei Provider-Fehlern pro Segment einen
`has_error=True`-Platzhalter statt einer leeren Liste liefert (die Liste ist
also nie leer, selbst wenn ALLE Segmente fehlgeschlagen sind).

Mock-frei: echte Trips unter `data/users/tdd-1012-*`, echter Versand über den
Stalwart-Test-Account (`gregor-test@henemm.com`, IMAP-Verifikation), echte
Fixture-Provider-Dateisubstitution (`# fake-provider-seam`) statt Mocks der
eigenen Logik — die bereits etablierte Offline-Test-Infrastruktur (Issue #346,
`GZ_TEST_FIXTURE_DIR`) wird gezielt auf "Datei fehlt" umgeleitet, um einen
echten Provider-Fehler (`ProviderError`, von `SegmentWeatherService` generisch
abgefangen und in `has_error=True` übersetzt) zu erzeugen — keine Mock()/
patch()/MagicMock-Nutzung, keine Ersetzung eigener Geschäftslogik.

Sicherheit: report_config bleibt in allen Tests `None` (Trip-Default) bzw.
enthält nur `send_email=True` — send_sms/send_telegram werden NIE aktiviert,
Test-User-Profile setzen NIE `telegram_chat_id`. Einziger Kanal: E-Mail an
`gregor-test@henemm.com` (Stalwart), automatisch geroutet über die
"tdd"-Substring-Erkennung in `Settings.with_user_profile()` — nie Resend.

Marker-Format-Kontrakt (von der Spec nicht auf Container-Ebene festgelegt,
hier als Testkontrakt festgeschrieben, analog `briefing_log.json`):
`data/users/<uid>/pending_briefings.json` == `{"entries": [ {trip_id,
report_type, date, slot_hour, failed_segment_ids, attempts, created_at}, ... ]}`.

SPEC: docs/specs/modules/issue_1012_briefing_no_data_guard.md (AC-1..AC-7)
"""
from __future__ import annotations

import email
import imaplib
import json
import os
import shutil
import time as time_mod
from datetime import date, time, timedelta
from email.header import decode_header
from pathlib import Path


from app.loader import save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.trip_report_scheduler import TripReportSchedulerService

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_ENV = _REPO_ROOT / ".env"
_MAIN_ENV = Path("/home/hem/gregor_zwanzig/.env")
_DATA_USERS = _REPO_ROOT / "data" / "users"
_TEST_MAILBOX = "gregor-test@henemm.com"
_REAL_FIXTURES_DIR = str(_REPO_ROOT / "fixtures" / "openmeteo")

# Zwei der drei fest verdrahteten Fixture-Standorte (siehe
# providers/fixture.py::_FIXTURE_LOCATIONS) — exakte Koordinaten garantieren
# das nearest-neighbor-Matching auf einen bestimmten Standort/Dateinamen.
_INNSBRUCK = (47.2692, 11.4041)
_STUBAI = (47.1015, 11.2958)


def _load_env_file(path: Path) -> None:
    """Lädt SMTP-/IMAP-Creds aus einer .env-Datei (setdefault — überschreibt nicht)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(_LOCAL_ENV)
_load_env_file(_MAIN_ENV)


def _make_user(user_id: str) -> None:
    """Frischer Test-User mit Test-Postfach als Empfänger — KEIN telegram_chat_id."""
    udir = _DATA_USERS / user_id
    if udir.exists():
        shutil.rmtree(udir)
    udir.mkdir(parents=True)
    (udir / "user.json").write_text(json.dumps({
        "id": user_id,
        "created_at": "2026-07-05T00:00:00Z",
        "mail_to": _TEST_MAILBOX,
    }))


def _make_trip(
    user_id: str, trip_id: str, name: str, stage_date: date,
    coords: list[tuple[float, float]],
) -> Trip:
    """Trip mit einer Etappe; jedes coords-Paar wird zu einem Wegpunkt.

    2 Wegpunkte -> 1 Streckensegment + 1 Ziel-Segment (beide mit
    start_point == jeweiligem Wegpunkt) — reicht, um pro Segment gezielt
    einen bestimmten Fixture-Standort (und damit Erfolg/Fehlschlag) zu steuern.
    """
    hours = [7, 9, 11, 13][: len(coords)]
    wps = [
        Waypoint(
            id=f"G{i + 1}", name=f"WP{i + 1}", lat=lat, lon=lon,
            elevation_m=600 + i * 50,
            time_window=TimeWindow(start=time(h, 0), end=time(h, 0)),
        )
        for i, ((lat, lon), h) in enumerate(zip(coords, hours))
    ]
    stage = Stage(id="T1", name=f"{name}-Etappe", date=stage_date,
                  start_time=time(hours[0], 0), waypoints=wps)
    trip = Trip(id=trip_id, name=name, stages=[stage])
    save_trip(trip, user_id=user_id)
    return trip


def _make_trip_two_stages(
    user_id: str, trip_id: str, name: str, date_today: date, date_tomorrow: date,
) -> Trip:
    """Zwei-Etappen-Trip (heute + morgen) — für den AC-7-Marker-Verfall-Test."""
    wps_today = [
        Waypoint(id="G1", name="Start", lat=_INNSBRUCK[0], lon=_INNSBRUCK[1],
                  elevation_m=600, time_window=TimeWindow(start=time(7, 0), end=time(7, 0))),
        Waypoint(id="G2", name="Ziel", lat=_INNSBRUCK[0], lon=_INNSBRUCK[1],
                  elevation_m=650, time_window=TimeWindow(start=time(9, 0), end=time(9, 0))),
    ]
    wps_tomorrow = [
        Waypoint(id="G1", name="Start Tag2", lat=_INNSBRUCK[0], lon=_INNSBRUCK[1],
                  elevation_m=650, time_window=TimeWindow(start=time(9, 0), end=time(9, 0))),
        Waypoint(id="G2", name="Ziel Tag2", lat=_INNSBRUCK[0], lon=_INNSBRUCK[1],
                  elevation_m=700, time_window=TimeWindow(start=time(11, 0), end=time(11, 0))),
    ]
    stage1 = Stage(id="T1", name=f"{name}-Etappe1", date=date_today,
                   start_time=time(7, 0), waypoints=wps_today)
    stage2 = Stage(id="T2", name=f"{name}-Etappe2", date=date_tomorrow,
                   start_time=time(9, 0), waypoints=wps_tomorrow)
    trip = Trip(id=trip_id, name=name, stages=[stage1, stage2])
    save_trip(trip, user_id=user_id)
    return trip


def _briefing_log(user_id: str) -> list:
    p = _DATA_USERS / user_id / "briefing_log.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("entries", [])


def _pending_markers(user_id: str) -> list:
    """Testkontrakt: {"entries": [...]} — siehe Modul-Docstring."""
    p = _DATA_USERS / user_id / "pending_briefings.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return data.get("entries", []) if isinstance(data, dict) else data


def _empty_fixture_dir(tmp_path: Path) -> str:
    """Fixture-Dir OHNE jede Datei -> jeder Abruf schlägt real fehl."""
    d = tmp_path / "fx_empty"
    d.mkdir()
    return str(d)


def _partial_fixture_dir(tmp_path: Path) -> str:
    """Fixture-Dir NUR mit innsbruck.json -> Innsbruck-Koordinaten liefern echte
    Daten, Stubai-/Zillertal-Koordinaten schlagen real fehl (Datei fehlt)."""
    d = tmp_path / "fx_partial"
    d.mkdir()
    shutil.copy(Path(_REAL_FIXTURES_DIR) / "innsbruck.json", d / "innsbruck.json")
    return str(d)


def _imap():
    m = imaplib.IMAP4_SSL(os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
                           int(os.environ.get("GZ_IMAP_PORT", "993")))
    m.login(os.environ["GZ_TEST_IMAP_USER"], os.environ["GZ_TEST_IMAP_PASS"])
    m.select("INBOX")
    return m


def _subject(msg) -> str:
    raw = decode_header(msg.get("Subject", ""))[0][0]
    return raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)


def _find_mails(trip_name: str, min_uid: int, timeout_s: int = 90) -> list:
    """Alle Mails mit UID > min_uid, deren Subject den Trip-Namen enthält."""
    deadline = time_mod.time() + timeout_s
    while True:
        m = _imap()
        try:
            _, data = m.uid("search", None, f"UID {min_uid + 1}:*")
            hits = []
            for uid in (data[0].split() if data and data[0] else []):
                if int(uid) <= min_uid:
                    continue
                _, md = m.uid("fetch", uid, "(RFC822)")
                mail = email.message_from_bytes(md[0][1])
                if trip_name in _subject(mail):
                    hits.append(mail)
            if hits or time_mod.time() > deadline:
                return hits
        finally:
            m.logout()
        time_mod.sleep(10)


def _max_uid() -> int:
    m = _imap()
    try:
        _, data = m.uid("search", None, "ALL")
        uids = data[0].split() if data and data[0] else []
        return int(uids[-1]) if uids else 0
    finally:
        m.logout()


def _html_body(mail) -> str:
    for part in mail.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", errors="replace")
    return ""


def _plain_body(mail) -> str:
    for part in mail.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", errors="replace")
    return ""


def _any_body(mail) -> str:
    return _html_body(mail) or _plain_body(mail)


# ---------------------------------------------------------------------------
# AC-1 — Kompletter Ausfall: Guard unterdrückt Versand + briefing_log
# ---------------------------------------------------------------------------

def test_all_failed_weather_suppresses_send_and_briefing_log(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac1"
    trip_name = "TDD1012 AC1 AllFailed"
    _make_user(user_id)
    # fake-provider-seam: leeres Fixture-Dir -> ProviderError für jedes Segment
    # (echte Substitution der externen Abhängigkeit Open-Meteo, kein Mock).
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _empty_fixture_dir(tmp_path))

    trip = _make_trip(user_id, "tdd-1012-ac1-trip", trip_name, date.today(),
                       [_INNSBRUCK, _STUBAI])

    baseline_uid = _max_uid()
    service = TripReportSchedulerService(user_id=user_id)
    outcome = service._send_trip_report_outcome(trip, "morning")

    assert outcome == "no_weather", (
        f"Erwartetes Outcome 'no_weather' bei komplettem Ausfall, war {outcome!r} "
        f"— der Guard `if not segment_weather` greift nicht, weil has_error=True-"
        f"Platzhalter statt einer leeren Liste geliefert werden (Root Cause #1012)"
    )
    assert _briefing_log(user_id) == [], (
        "Trotz komplettem Wetter-Ausfall wurde ein briefing_log-Eintrag geschrieben"
    )

    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    briefing_mails = [m for m in mails if m.get("X-GZ-Mail-Type") == "trip-briefing"]
    assert briefing_mails == [], (
        f"Trotz komplettem Wetter-Ausfall wurde eine reguläre Briefing-Mail mit "
        f"leeren Tabellen zugestellt: {[_subject(m) for m in briefing_mails]}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Hinweis-Nachricht statt leerem Briefing
# ---------------------------------------------------------------------------

def test_all_failed_weather_sends_hint_message_via_imap(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac2"
    trip_name = "TDD1012 AC2 HinweisMail"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _empty_fixture_dir(tmp_path))

    trip = _make_trip(user_id, "tdd-1012-ac2-trip", trip_name, date.today(),
                       [_INNSBRUCK, _STUBAI])

    baseline_uid = _max_uid()
    service = TripReportSchedulerService(user_id=user_id)
    service._send_trip_report_outcome(trip, "morning")

    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    assert mails, (
        "Keine Mail beim kompletten Wetter-Ausfall zugestellt — erwartet die "
        "Hinweis-Mail 'Wetterdienst aktuell nicht erreichbar'"
    )
    mail = mails[0]
    subj = _subject(mail)
    assert trip_name in subj, f"Trip-Name fehlt im Betreff der Hinweis-Mail: {subj!r}"
    body = _any_body(mail)
    assert "nicht erreichbar" in body, (
        f"Hinweistext 'Wetterdienst aktuell nicht erreichbar' fehlt im Mail-Body: "
        f"{body[:300]!r}"
    )
    assert "Briefing nach" in body, (
        f"Nachliefer-Ankündigung ('...liefern das Briefing nach...') fehlt im "
        f"Mail-Body: {body[:300]!r}"
    )
    assert mail.get("X-GZ-Mail-Type") != "trip-briefing", (
        "Hinweis-Mail trägt den Marker-Header eines regulären Tabellen-Briefings"
    )


# ---------------------------------------------------------------------------
# AC-3 — Teilausfall: pünktlich senden + Segment kennzeichnen + Marker
# ---------------------------------------------------------------------------

def test_partial_failure_sends_on_time_with_labels_and_marker(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac3"
    trip_name = "TDD1012 AC3 Teilausfall"
    _make_user(user_id)
    # fake-provider-seam: nur Innsbruck-Fixture vorhanden.
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    trip = _make_trip(user_id, "tdd-1012-ac3-trip", trip_name, date.today(),
                       [_INNSBRUCK, _STUBAI])

    baseline_uid = _max_uid()
    service = TripReportSchedulerService(user_id=user_id)
    outcome = service._send_trip_report_outcome(trip, "morning")

    assert outcome == "sent", f"Teilausfall soll trotzdem 'sent' liefern, war {outcome!r}"
    log = _briefing_log(user_id)
    assert len(log) == 1, f"Kein regulärer briefing_log-Eintrag bei Teilausfall: {log}"

    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    assert len(mails) == 1, f"{len(mails)} Mails statt 1 bei Teilausfall"
    body = _html_body(mails[0])
    assert "nicht verfuegbar" in body or "nicht verfügbar" in body, (
        f"Fehlendes Segment ist nicht ausdrücklich als 'Wetterdaten nicht "
        f"verfügbar' gekennzeichnet: {body[:500]!r}"
    )

    markers = _pending_markers(user_id)
    entry = next((m for m in markers if m.get("trip_id") == trip.id), None)
    assert entry is not None, (
        f"Kein Nachliefer-Marker für das Teilausfall-Segment geschrieben: {markers}"
    )
    assert entry.get("failed_segment_ids"), (
        f"Marker enthält keine failed_segment_ids: {entry}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Job-Zählung + API (zwei Test-Funktionen laut Testplan)
# ---------------------------------------------------------------------------

def test_send_reports_for_hour_counts_all_failed_as_failed(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac4"
    name_fail = "TDD1012 AC4 AllFailed"
    name_ok = "TDD1012 AC4 Healthy"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    # Stubai-Fixture fehlt -> beide Segmente dieses Trips schlagen fehl.
    _make_trip(user_id, "tdd-1012-ac4-fail-trip", name_fail, date.today(),
               [_STUBAI, _STUBAI])
    # Innsbruck-Fixture vorhanden -> beide Segmente liefern echte Daten.
    _make_trip(user_id, "tdd-1012-ac4-ok-trip", name_ok, date.today(),
               [_INNSBRUCK, _INNSBRUCK])

    service = TripReportSchedulerService(user_id=user_id)
    sent, failed = service.send_reports_for_hour(7)

    assert (sent, failed) == (1, 1), (
        f"Erwartet (sent=1, failed=1) bei einem All-Failed- und einem gesunden "
        f"Trip zur selben fälligen Stunde, war (sent={sent}, failed={failed}) — "
        f"send_reports_for_hour zählt All-Failed-Trips heute fälschlich als 'sent'"
    )


def test_trip_reports_endpoint_returns_partial_status(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app

    user_id = "tdd-1012-ac4b"
    name_fail = "TDD1012 AC4B AllFailed"
    name_ok = "TDD1012 AC4B Healthy"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    _make_trip(user_id, "tdd-1012-ac4b-fail-trip", name_fail, date.today(),
               [_STUBAI, _STUBAI])
    _make_trip(user_id, "tdd-1012-ac4b-ok-trip", name_ok, date.today(),
               [_INNSBRUCK, _INNSBRUCK])

    client = TestClient(app)
    resp = client.post(f"/api/scheduler/trip-reports?hour=7&user_id={user_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "partial", (
        f"Erwartet status='partial' bei mindestens einem All-Failed-Trip, "
        f"Response war {data}"
    )
    assert data.get("failed", 0) > 0, f"Erwartet failed>0, Response war {data}"


# ---------------------------------------------------------------------------
# AC-6 — Nachliefern bei Erholung (Komplett- und Teilausfall) + Lärmschutz
# ---------------------------------------------------------------------------

def test_pending_marker_written_and_briefing_delivered_on_recovery(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac6"
    trip_name = "TDD1012 AC6 Recovery"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _empty_fixture_dir(tmp_path))

    trip = _make_trip(user_id, "tdd-1012-ac6-trip", trip_name, date.today(),
                       [_INNSBRUCK, _INNSBRUCK])

    service = TripReportSchedulerService(user_id=user_id)
    sent1, failed1 = service.send_reports_for_hour(7)
    assert (sent1, failed1) == (0, 1), (
        f"Erster Lauf (All-Failed) soll (sent=0, failed=1) liefern, war "
        f"(sent={sent1}, failed={failed1})"
    )

    markers = _pending_markers(user_id)
    entry = next((m for m in markers if m.get("trip_id") == trip.id), None)
    assert entry is not None, (
        f"Kein Nachliefer-Marker nach komplettem Ausfall geschrieben: {markers}"
    )

    # Erholung: echte Fixture-Daten stehen jetzt zur Verfügung. Absichtlich ein
    # NICHT fälliger Slot (weder morning_time=7 noch evening_time=18) — nur der
    # Catch-up-Mechanismus (nicht der reguläre Due-Check) darf hier etwas tun.
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _REAL_FIXTURES_DIR)
    baseline_uid = _max_uid()
    sent2, failed2 = service.send_reports_for_hour(10)

    assert sent2 == 1, (
        f"Nachlieferung nach Erholung soll als 'sent' zählen, war sent={sent2}"
    )
    log = _briefing_log(user_id)
    assert len(log) == 1, f"Kein regulärer briefing_log-Eintrag nach Nachlieferung: {log}"

    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    assert mails, "Keine Nachlieferungs-Mail nach Erholung zugestellt"
    body = _any_body(mails[0])
    assert "Nachgeliefert" in body, (
        f"Nachlieferungs-Hinweis 'Nachgeliefert' fehlt im Mail-Body: {body[:300]!r}"
    )

    markers_after = _pending_markers(user_id)
    assert not any(m.get("trip_id") == trip.id for m in markers_after), (
        "Marker wurde nach erfolgreicher Nachlieferung nicht entfernt"
    )


def test_partial_marker_redelivers_updated_briefing_on_recovery(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac6b"
    trip_name = "TDD1012 AC6B TeilRecovery"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    trip = _make_trip(user_id, "tdd-1012-ac6b-trip", trip_name, date.today(),
                       [_INNSBRUCK, _STUBAI])

    service = TripReportSchedulerService(user_id=user_id)
    outcome1 = service._send_trip_report_outcome(trip, "morning")
    assert outcome1 == "sent", f"Vorbedingung verletzt: outcome war {outcome1!r}"

    markers = _pending_markers(user_id)
    entry = next((m for m in markers if m.get("trip_id") == trip.id), None)
    assert entry is not None, f"Kein Marker nach Teilausfall geschrieben: {markers}"

    # Erholung: jetzt liefert auch Stubai echte Daten (nicht-fälliger Slot,
    # reines Catch-up).
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _REAL_FIXTURES_DIR)
    baseline_uid = _max_uid()
    sent2, failed2 = service.send_reports_for_hour(10)

    assert sent2 == 1, (
        f"Nachlieferung nach Teil-Erholung soll 'sent' zählen, war sent={sent2}"
    )
    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    assert mails, "Keine Aktualisierungs-Mail nach Teil-Erholung zugestellt"
    body = _any_body(mails[0])
    assert "Aktualisiert" in body, (
        f"Aktualisierungs-Hinweis 'Aktualisiert' fehlt im Mail-Body: {body[:300]!r}"
    )
    assert "nicht verfuegbar" not in body and "nicht verfügbar" not in body, (
        "Nachgelieferte Mail enthält weiterhin eine 'nicht verfügbar'-"
        "Kennzeichnung — alle Segmente sollten jetzt vollständige Daten haben"
    )

    markers_after = _pending_markers(user_id)
    assert not any(m.get("trip_id") == trip.id for m in markers_after), (
        "Marker wurde nach erfolgreicher Teil-Nachlieferung nicht entfernt"
    )


def test_no_resend_while_segments_still_failing(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac6c"
    trip_name = "TDD1012 AC6C Laermschutz"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _empty_fixture_dir(tmp_path))

    trip = _make_trip(user_id, "tdd-1012-ac6c-trip", trip_name, date.today(),
                       [_INNSBRUCK, _INNSBRUCK])

    service = TripReportSchedulerService(user_id=user_id)
    service.send_reports_for_hour(7)  # 1. Lauf: All-Failed, erzeugt Marker

    markers = _pending_markers(user_id)
    entry = next((m for m in markers if m.get("trip_id") == trip.id), None)
    assert entry is not None, "Kein Marker nach erstem All-Failed-Lauf geschrieben"
    attempts_before = entry.get("attempts", 0)

    baseline_uid = _max_uid()
    # 2. Lauf: Fixture-Dir bleibt leer -> weiterhin All-Failed -> kein Re-Send.
    sent2, failed2 = service.send_reports_for_hour(10)

    assert sent2 == 0, (
        f"Ohne Erholung darf keine Nachlieferung als 'sent' zählen, war sent={sent2}"
    )
    mails = _find_mails(trip_name, baseline_uid, timeout_s=20)
    briefing_mails = [m for m in mails if m.get("X-GZ-Mail-Type") == "trip-briefing"]
    assert briefing_mails == [], (
        f"Trotz weiterhin fehlenden Daten wurde ein reguläres Briefing "
        f"nachgeliefert: {[_subject(m) for m in briefing_mails]}"
    )

    markers_after = _pending_markers(user_id)
    entry_after = next((m for m in markers_after if m.get("trip_id") == trip.id), None)
    assert entry_after is not None, (
        "Marker wurde trotz weiterhin fehlender Daten entfernt — Lärmschutz verletzt"
    )
    assert entry_after.get("attempts", 0) == attempts_before + 1, (
        f"attempts wurde nicht erhöht: vorher {attempts_before}, "
        f"nachher {entry_after.get('attempts')}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Marker-Verfall zum nächsten regulären Termin, kein Doppel-Briefing
# ---------------------------------------------------------------------------

def test_pending_marker_expires_at_next_regular_slot_no_double_briefing(tmp_path, monkeypatch):
    user_id = "tdd-1012-ac7"
    trip_name = "TDD1012 AC7 MarkerVerfall"
    _make_user(user_id)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _empty_fixture_dir(tmp_path))

    trip = _make_trip_two_stages(user_id, "tdd-1012-ac7-trip", trip_name, today, tomorrow)

    service = TripReportSchedulerService(user_id=user_id)
    sent1, failed1 = service.send_reports_for_hour(7)  # Morning (heute), All-Failed
    assert (sent1, failed1) == (0, 1), (
        f"Vorbedingung verletzt: Morning-Lauf war (sent={sent1}, failed={failed1})"
    )

    markers = _pending_markers(user_id)
    assert any(
        m.get("trip_id") == trip.id and m.get("report_type") == "morning"
        for m in markers
    ), f"Kein Morning-Marker nach All-Failed-Lauf geschrieben: {markers}"

    # Nächster regulärer Termin desselben Trips: Evening (morgen) — mit
    # funktionierendem Provider.
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _REAL_FIXTURES_DIR)
    sent2, failed2 = service.send_reports_for_hour(18)

    assert sent2 == 1, (
        f"Regulärer Evening-Versand soll genau 1x 'sent' zählen, war sent={sent2}"
    )
    log = _briefing_log(user_id)
    trip_entries = [e for e in log if e.get("trip_id") == trip.id]
    assert len(trip_entries) == 1, (
        f"Erwartet GENAU 1 briefing_log-Eintrag (nur das reguläre Evening-"
        f"Briefing), sah {len(trip_entries)}: {trip_entries} — ein verfallener "
        f"Morning-Marker hat offenbar ein zusätzliches (veraltetes) Briefing "
        f"ausgelöst"
    )

    markers_after = _pending_markers(user_id)
    assert not any(
        m.get("trip_id") == trip.id and m.get("report_type") == "morning"
        for m in markers_after
    ), "Veralteter Morning-Marker wurde nicht beim nächsten regulären Termin entfernt"


# ---------------------------------------------------------------------------
# Adversary-Finding F001 — korrupte pending_briefings.json darf den regulären
# Versand nicht blockieren
# ---------------------------------------------------------------------------

def test_corrupt_pending_file_does_not_block_regular_send(tmp_path, monkeypatch):
    """Root Cause: `_process_pending_markers()` liest pending_briefings.json via
    ungeschütztem `json.loads(path.read_text())`. Eine kaputte Datei (z.B.
    abgebrochener Schreibvorgang) wirft eine ungefangene JSONDecodeError, die
    `send_reports_for_hour()` VOR dem regulären Versand crasht -> HTTP 500,
    KEIN Trip des Users bekommt ein Briefing in diesem Lauf."""
    from fastapi.testclient import TestClient

    from api.main import app

    user_id = "tdd-1012-f001"
    trip_name = "TDD1012 F001 CorruptPending"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _REAL_FIXTURES_DIR)

    trip = _make_trip(user_id, "tdd-1012-f001-trip", trip_name, date.today(),
                       [_INNSBRUCK, _INNSBRUCK])

    # Simuliert einen abgebrochenen Schreibvorgang.
    pending_path = _DATA_USERS / user_id / "pending_briefings.json"
    pending_path.write_text("{corrupted, not json!!")

    due_hour = 7  # Default morning_time-Stunde ohne report_config

    baseline_uid = _max_uid()
    client = TestClient(app)
    resp = client.post(f"/api/scheduler/trip-reports?hour={due_hour}&user_id={user_id}")

    assert resp.status_code == 200, (
        f"Korrupte pending_briefings.json crasht den Endpoint statt regulär zu "
        f"senden: HTTP {resp.status_code}, Body {resp.text[:300]!r}"
    )
    data = resp.json()
    assert data.get("count", 0) >= 1, (
        f"Regulärer Versand lief trotz korrupter pending_briefings.json nicht "
        f"durch: {data}"
    )

    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    briefing_mails = [m for m in mails if m.get("X-GZ-Mail-Type") == "trip-briefing"]
    assert briefing_mails, (
        "Trotz HTTP 200 wurde keine reguläre Briefing-Mail zugestellt"
    )

    # Folge-Lauf: die weiterhin korrupte Datei darf einen zweiten Lauf nicht
    # ebenfalls crashen lassen.
    resp2 = client.post(f"/api/scheduler/trip-reports?hour={due_hour}&user_id={user_id}")
    assert resp2.status_code == 200, (
        f"Folge-Lauf nach korrupter pending_briefings.json crasht ebenfalls: "
        f"HTTP {resp2.status_code}, Body {resp2.text[:300]!r}"
    )
