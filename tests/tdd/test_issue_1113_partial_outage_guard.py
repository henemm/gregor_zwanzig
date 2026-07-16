"""TDD RED — Issue #1113: Trip-Briefing Teilausfall-Guard (>75 %-Schwelle +
Retry + Hinweis).

Root Cause (Incident 2026-07-08): `_send_trip_report_outcome()`s Guard prüft
bislang nur den Totalausfall aller Segmente (`all(s.has_error ...)` — #1012).
Bei 5 von 6 Segmenten ohne Wetterdaten (open-meteo 503) ging das Briefing
trotzdem unverändert mit 5 "nicht verfügbar"-Zeilen raus. Diese Datei
erweitert den Guard um eine >75 %-Schwelle, einen Teilausfall-Hinweis
(`TripReportRequest.partial_outage_hint`) und ein Retry/Backoff für
transiente Fehler in `_fetch_weather()`.

Mock-frei: echte Trips unter `data/users/tdd-1113-*`, echter Versand über
den Stalwart-Test-Account (`gregor-test@henemm.com`, IMAP-Verifikation, wie
`test_issue_1012_no_data_guard.py`), echte Fixture-Provider-
Dateisubstitution (`# fake-provider-seam`) für die Schwellen-Tests (AC-1/2/3)
sowie ein echtes, zustandsbehaftetes Provider-Objekt (`_FlakyProvider`,
Muster Issue #483 Demo-Mode / FixtureProvider) für die Retry-Tests (AC-4) —
keine Mock()/patch()/MagicMock-Nutzung, keine Ersetzung eigener
Geschäftslogik.

Segment-Zählung (siehe `services/trip_segments.py::convert_trip_to_segments`):
N Wegpunkte -> (N-1) Streckensegmente + 1 Ziel-Segment = N Segmente gesamt.
Jedes Segment hat `start_point == <sein zugehöriger Wegpunkt>` — Streckensegment
i (0-basiert) startet bei Wegpunkt i, das Ziel-Segment startet beim letzten
Wegpunkt. Damit lässt sich die Fehlerquote präzise über die Wegpunkt-
Koordinaten (Innsbruck = Erfolg, Stubai = Fehlschlag, da nur
`innsbruck.json` im Fixture-Verzeichnis liegt) steuern.

Sicherheit: report_config bleibt in allen Tests `None` (Trip-Default) bzw.
enthält nur `send_email=True` — send_sms/send_telegram werden NIE aktiviert,
Test-User-Profile setzen NIE `telegram_chat_id`. Einziger Kanal: E-Mail an
`gregor-test@henemm.com` (Stalwart).

SPEC: docs/specs/modules/issue_1113_partial_outage_guard.md (AC-1..AC-6)
"""
from __future__ import annotations

import email
import imaplib
import json
import os
import shutil
from datetime import date, datetime, time, timedelta, timezone
from email.header import decode_header
from pathlib import Path
import time as time_mod

import httpx

from app.loader import get_data_dir, save_trip
from app.models import GPXPoint, TripSegment
from app.trip import Stage, TimeWindow, Trip, Waypoint
from providers.base import ProviderError, ProviderRequestError
from providers.fixture import FixtureProvider
from services.trip_report_scheduler import TripReportSchedulerService

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_ENV = _REPO_ROOT / ".env"
_MAIN_ENV = Path("/home/hem/gregor_zwanzig/.env")
_TEST_MAILBOX = "gregor-test@henemm.com"


def _data_users(user_id: str) -> Path:
    """Issue #1265 Teil C: get_data_dir() statt hartkodiertem Repo-Pfad --
    respektiert die pytest-Isolation (tests/conftest.py, #1133/#1265)."""
    return get_data_dir(user_id)


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
    udir = _data_users(user_id)
    if udir.exists():
        shutil.rmtree(udir)
    udir.mkdir(parents=True)
    (udir / "user.json").write_text(json.dumps({
        "id": user_id,
        "created_at": "2026-07-08T00:00:00Z",
        "mail_to": _TEST_MAILBOX,
    }))


def _make_trip(
    user_id: str, trip_id: str, name: str, stage_date: date,
    coords: list[tuple[float, float]],
) -> Trip:
    """Trip mit einer Etappe; jedes coords-Paar wird zu einem Wegpunkt.

    N Wegpunkte -> N Segmente (N-1 Streckensegmente + 1 Ziel-Segment) — jedes
    Segment startet bei genau einem der übergebenen Wegpunkte, damit die
    Fehlerquote präzise über die Koordinatenliste gesteuert werden kann.
    """
    hours = [7 + 2 * i for i in range(len(coords))]
    wps = [
        Waypoint(
            id=f"G{i + 1}", name=f"WP{i + 1}", lat=lat, lon=lon,
            elevation_m=600 + i * 50,
            time_window=TimeWindow(start=time(h % 24, 0), end=time(h % 24, 0)),
        )
        for i, ((lat, lon), h) in enumerate(zip(coords, hours))
    ]
    stage = Stage(id="T1", name=f"{name}-Etappe", date=stage_date,
                  start_time=time(hours[0] % 24, 0), waypoints=wps)
    trip = Trip(id=trip_id, name=name, stages=[stage])
    save_trip(trip, user_id=user_id)
    return trip


def _briefing_log(user_id: str) -> list:
    p = _data_users(user_id) / "briefing_log.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("entries", [])


def _pending_markers(user_id: str) -> list:
    """Testkontrakt (identisch #1012): {"entries": [ {trip_id, ...} ]}."""
    p = _data_users(user_id) / "pending_briefings.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return data.get("entries", []) if isinstance(data, dict) else data


def _partial_fixture_dir(tmp_path: Path) -> str:
    """Fixture-Dir NUR mit innsbruck.json -> Innsbruck-Koordinaten liefern echte
    Daten, Stubai-Koordinaten schlagen real fehl (Datei fehlt)."""
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
# AC-1 — >75 % Ausfall (5 von 6): zurückhalten wie Totalausfall (#1012)
# ---------------------------------------------------------------------------

def test_more_than_75pct_failure_withholds_like_total_outage(tmp_path, monkeypatch):
    user_id = "tdd-1113-ac1"
    trip_name = "TDD1113 AC1 UeberSchwelle"
    _make_user(user_id)
    # fake-provider-seam: nur innsbruck.json vorhanden -> Stubai-Segmente
    # schlagen real fehl (ProviderError: Datei fehlt).
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    # 6 Wegpunkte: die ersten 5 (-> 5 Streckensegmente) auf Stubai (Fehler),
    # der letzte (-> Ziel-Segment) auf Innsbruck (Erfolg) = 5/6 = 83,3 % > 75 %.
    coords = [_STUBAI] * 5 + [_INNSBRUCK]
    trip = _make_trip(user_id, "tdd-1113-ac1-trip", trip_name, date.today(), coords)

    baseline_uid = _max_uid()
    service = TripReportSchedulerService(user_id=user_id)
    outcome = service._send_trip_report_outcome(trip, "morning")

    assert outcome == "no_weather", (
        f"Erwartetes Outcome 'no_weather' bei 5/6 (83 %) Ausfall, war "
        f"{outcome!r} — die >75 %-Schwelle ist noch nicht implementiert, der "
        f"bestehende Guard greift nur bei 100 % Ausfall (#1012)"
    )
    assert _briefing_log(user_id) == [], (
        "Trotz 83 % Wetter-Ausfall wurde ein briefing_log-Eintrag geschrieben"
    )

    markers = _pending_markers(user_id)
    entry = next((m for m in markers if m.get("trip_id") == trip.id), None)
    assert entry is not None, (
        f"Kein Nachliefer-Marker bei 83 % Ausfall geschrieben: {markers}"
    )
    assert len(entry.get("failed_segment_ids", [])) >= 5, (
        f"Marker enthält nicht die 5 fehlgeschlagenen Segment-IDs: {entry}"
    )

    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    assert mails, (
        "Keine Hinweis-Mail bei 83 % Wetter-Ausfall zugestellt — erwartet "
        "identisches Verhalten zum Totalausfall (#1012)"
    )
    body = _any_body(mails[0])
    assert "nicht erreichbar" in body, (
        f"Hinweistext 'Wetterdienst aktuell nicht erreichbar' fehlt im "
        f"Mail-Body bei 83 % Ausfall: {body[:300]!r}"
    )
    briefing_mails = [m for m in mails if m.get("X-GZ-Mail-Type") == "trip-briefing"]
    assert briefing_mails == [], (
        f"Trotz 83 % Wetter-Ausfall wurde eine reguläre Briefing-Mail mit "
        f"größtenteils leeren Tabellen zugestellt: {[_subject(m) for m in briefing_mails]}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Teilausfall unterhalb der Schwelle (1 von 6): Hinweis im Briefing
# ---------------------------------------------------------------------------

def test_partial_failure_below_threshold_embeds_hint_in_report(tmp_path, monkeypatch):
    user_id = "tdd-1113-ac2"
    trip_name = "TDD1113 AC2 Teilausfall"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    # 6 Wegpunkte: nur der erste (-> Streckensegment 1) auf Stubai (Fehler),
    # die restlichen 5 auf Innsbruck (Erfolg) = 1/6 ≈ 16,7 % <= 75 %.
    coords = [_STUBAI] + [_INNSBRUCK] * 5
    trip = _make_trip(user_id, "tdd-1113-ac2-trip", trip_name, date.today(), coords)

    baseline_uid = _max_uid()
    service = TripReportSchedulerService(user_id=user_id)
    outcome = service._send_trip_report_outcome(trip, "morning")
    assert outcome == "sent", (
        f"Teilausfall unterhalb der Schwelle soll trotzdem 'sent' liefern, "
        f"war {outcome!r}"
    )

    mails = _find_mails(trip_name, baseline_uid, timeout_s=90)
    assert len(mails) == 1, f"{len(mails)} Mails statt 1 bei Teilausfall"
    plain = _plain_body(mails[0])
    html = _html_body(mails[0])

    for label, body in (("Plain", plain), ("HTML", html)):
        assert "keine Wetterdaten vor" in body, (
            f"Teilausfall-Hinweis ('...liegen aktuell keine Wetterdaten "
            f"vor...') fehlt im {label}-Teil — request.partial_outage_hint "
            f"ist noch nicht implementiert: {body[:400]!r}"
        )
        assert "nachgeliefert" in body, (
            f"Nachlieferungs-Ankündigung im Teilausfall-Hinweis fehlt im "
            f"{label}-Teil: {body[:400]!r}"
        )

    # Plain-Text: Hinweis muss an oberster Stelle stehen (erste 600 Zeichen).
    assert "Segment 1" in plain[:600], (
        f"Teilausfall-Hinweis nennt nicht das betroffene Segment "
        f"('Segment 1', Konvention aus html.py:911) im Plain-Teil an "
        f"oberster Stelle: {plain[:600]!r}"
    )

    # HTML: strukturelle Prüfung statt reiner String-Position (Adversary-Finding
    # F001) — der Hinweis darf NICHT vor <!DOCTYPE html>/<html> stehen (das
    # zwingt den Browser-Parser sonst in den Quirks-Modus, per echtem
    # Chromium-Parse nachgewiesen), sondern muss direkt nach <body> und vor
    # dem ersten inhaltlichen Element folgen.
    lower_html = html.lower()
    doctype_idx = lower_html.find("<!doctype")
    html_tag_idx = lower_html.find("<html")
    candidates = [i for i in (doctype_idx, html_tag_idx) if i != -1]
    assert candidates, f"Weder <!DOCTYPE> noch <html> im HTML gefunden: {html[:200]!r}"
    first_marker_idx = min(candidates)
    assert first_marker_idx == 0, (
        f"Vor <!DOCTYPE>/<html> steht bereits Inhalt (erzwingt Quirks-Modus "
        f"statt Standards-Modus im Browser-Parser): {html[:first_marker_idx + 80]!r}"
    )

    body_tag_idx = lower_html.find("<body")
    assert body_tag_idx != -1, f"Kein <body>-Tag im HTML gefunden: {html[:400]!r}"
    body_open_end = html.find(">", body_tag_idx) + 1
    assert body_open_end > 0

    after_body = html[body_open_end:]
    first_content_idx = min(
        (i for i in (after_body.find("<div"), after_body.find("<table")) if i != -1),
        default=len(after_body),
    )
    hint_idx = after_body.find("Segment 1")
    assert hint_idx != -1, (
        f"Teilausfall-Hinweis ('Segment 1') nicht im HTML nach <body> "
        f"gefunden: {after_body[:400]!r}"
    )
    assert hint_idx < first_content_idx, (
        f"Teilausfall-Hinweis liegt nicht vor dem ersten Inhalts-Element "
        f"(<div>/<table>) nach <body>: Hinweis bei Position {hint_idx}, "
        f"Inhalt bei Position {first_content_idx}, Ausschnitt: "
        f"{after_body[:max(hint_idx, first_content_idx) + 100]!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Grenzfälle: exakt 75 % sendet noch, mehr als 75 % wird zurückgehalten
# ---------------------------------------------------------------------------

def test_exactly_75pct_sends_more_than_75pct_withholds(tmp_path, monkeypatch):
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    # --- Grenzfall 1: 4 Segmente, 3 Fehler = exakt 75 % -> senden ---
    user_id_a = "tdd-1113-ac3a"
    trip_name_a = "TDD1113 AC3A Genau75"
    _make_user(user_id_a)
    coords_a = [_STUBAI] * 3 + [_INNSBRUCK]
    trip_a = _make_trip(user_id_a, "tdd-1113-ac3a-trip", trip_name_a, date.today(), coords_a)

    baseline_uid_a = _max_uid()
    service_a = TripReportSchedulerService(user_id=user_id_a)
    outcome_a = service_a._send_trip_report_outcome(trip_a, "morning")
    assert outcome_a == "sent", (
        f"Exakt 75 % Ausfall (3 von 4) soll noch gesendet werden (Schwelle "
        f"ist strikt 'mehr als 75 %'), war {outcome_a!r}"
    )
    mails_a = _find_mails(trip_name_a, baseline_uid_a, timeout_s=90)
    assert mails_a, "Keine Mail bei exakt 75 % Ausfall zugestellt"
    body_a = _any_body(mails_a[0])
    assert "keine Wetterdaten vor" in body_a, (
        f"Teilausfall-Hinweis fehlt bei exakt 75 % Ausfall (grenzwertig noch "
        f"'gesendet mit Hinweis'): {body_a[:400]!r}"
    )

    # --- Grenzfall 2: 6 Segmente, 5 Fehler = 83,3 % -> zurückhalten ---
    user_id_b = "tdd-1113-ac3b"
    trip_name_b = "TDD1113 AC3B Ueber75"
    _make_user(user_id_b)
    coords_b = [_STUBAI] * 5 + [_INNSBRUCK]
    trip_b = _make_trip(user_id_b, "tdd-1113-ac3b-trip", trip_name_b, date.today(), coords_b)

    baseline_uid_b = _max_uid()
    service_b = TripReportSchedulerService(user_id=user_id_b)
    outcome_b = service_b._send_trip_report_outcome(trip_b, "morning")
    assert outcome_b == "no_weather", (
        f"83,3 % Ausfall (5 von 6) soll zurückgehalten werden, war {outcome_b!r}"
    )
    briefing_mails_b = [
        m for m in _find_mails(trip_name_b, baseline_uid_b, timeout_s=90)
        if m.get("X-GZ-Mail-Type") == "trip-briefing"
    ]
    assert briefing_mails_b == [], (
        "Trotz 83,3 % Ausfall wurde eine reguläre Briefing-Mail zugestellt"
    )


# ---------------------------------------------------------------------------
# AC-4 — Retry/Backoff bei transientem Fehler in _fetch_weather()
# ---------------------------------------------------------------------------

class _FlakyProvider:
    """Echtes WeatherProvider-Objekt (kein Mock()/patch()): wirft für die
    ersten `fail_times` Aufrufe eine ProviderError (simulierter 503) und
    delegiert danach an einen echten FixtureProvider für valide Daten.
    Belegt den Injection-Seam `_fetch_weather(provider=...)`
    (Muster Issue #483 Demo-Mode)."""

    def __init__(self, fixture_dir: str, fail_times: int) -> None:
        self._delegate = FixtureProvider(fixture_dir)
        self._fail_times = fail_times
        self.calls = 0

    @property
    def name(self) -> str:
        return "flaky-test"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ProviderError(
                "flaky-test", f"Simulierter transienter 503 (Aufruf {self.calls})"
            )
        return self._delegate.fetch_forecast(
            location, start=start, end=end, enrich_ensemble=enrich_ensemble
        )


def _make_segment_at(coords: tuple[float, float]) -> TripSegment:
    lat, lon = coords
    now = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=800),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=850),
        start_time=now,
        end_time=now + timedelta(hours=2),
        duration_hours=2.0,
        distance_km=3.0,
        ascent_m=50,
        descent_m=0,
    )


def _make_scheduler(user_id: str = "default") -> TripReportSchedulerService:
    """Minimaler Scheduler ohne volle Settings-Initialisierung — _fetch_weather()
    braucht nur self über die Methode selbst, keine Instanzattribute."""
    svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
    svc._user_id = user_id
    return svc


def test_transient_error_retried_before_marking_has_error():
    segment = _make_segment_at(_INNSBRUCK)
    fake = _FlakyProvider(_REAL_FIXTURES_DIR, fail_times=2)
    service = _make_scheduler()

    result = service._fetch_weather([segment], provider=fake)

    assert len(result) == 1
    assert result[0].has_error is False, (
        f"Segment soll nach 2 Fehlschlägen beim 3. Versuch valide Daten "
        f"liefern (has_error=False), war has_error={result[0].has_error!r}, "
        f"error_message={result[0].error_message!r} — Retry/Backoff in "
        f"_fetch_weather() ist noch nicht implementiert"
    )
    assert fake.calls == 3, (
        f"Erwartet genau 3 Versuche (1 initial + 2 Retries) bevor valide "
        f"Daten geliefert werden, tatsächlich {fake.calls} Aufruf(e)"
    )


def test_transient_error_marks_has_error_after_retry_exhaustion():
    segment = _make_segment_at(_INNSBRUCK)
    # Schlägt durchgehend fehl -> auch nach Retry-Erschöpfung has_error=True.
    fake = _FlakyProvider(_REAL_FIXTURES_DIR, fail_times=99)
    service = _make_scheduler()

    result = service._fetch_weather([segment], provider=fake)

    assert len(result) == 1
    assert result[0].has_error is True, (
        "Segment soll nach Erschöpfung der Retries (3 Versuche) als "
        "fehlerhaft markiert werden"
    )
    assert fake.calls == 3, (
        f"Erwartet genau 3 Versuche (1 initial + 2 Retries) vor Erschöpfung, "
        f"tatsächlich {fake.calls} Aufruf(e) — ohne Retry-Logik bricht "
        f"_fetch_weather() bereits nach dem 1. Fehlschlag ab"
    )


class _AlwaysNonTransientProvider:
    """Echtes WeatherProvider-Objekt (kein Mock()/patch()): wirft für JEDEN
    Aufruf einen NICHT-transienten Fehler (kein 5xx/Timeout/Overloaded im
    Fehlertext, z. B. ungültige Koordinaten). Beweist Adversary Finding
    F002 (a): nicht-transiente Fehler dürfen nicht wiederholt werden."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "non-transient-test"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        self.calls += 1
        raise ProviderError("non-transient-test", "Ungueltige Koordinaten uebergeben")


def test_non_transient_error_not_retried():
    segment = _make_segment_at(_INNSBRUCK)
    fake = _AlwaysNonTransientProvider()
    service = _make_scheduler()

    result = service._fetch_weather([segment], provider=fake)

    assert len(result) == 1
    assert result[0].has_error is True
    assert fake.calls == 1, (
        f"Ein nicht-transienter Fehler (kein 5xx/Timeout/Overloaded im "
        f"Fehlertext) darf NICHT wiederholt werden (Adversary Finding F002), "
        f"tatsächlich {fake.calls} Aufruf(e) statt 1"
    )


class _AlwaysTransientProvider:
    """Echtes WeatherProvider-Objekt (kein Mock()/patch()): wirft für JEDEN
    Aufruf einen transienten Fehler (simulierter dauerhafter 503-Ausfall).
    Zählt Aufrufe GLOBAL über alle Segmente eines einzigen
    _fetch_weather()-Aufrufs hinweg — beweist Adversary Finding F002 (b):
    das Fail-Fast-Budget nach dem ersten endgültig gescheiterten Segment."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "always-transient-test"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        self.calls += 1
        raise ProviderError("always-transient-test", "Simulierter dauerhafter 503-Ausfall")


def test_fail_fast_budget_after_first_segment_exhausted():
    segments = [
        _make_segment_at(_INNSBRUCK),
        _make_segment_at(_STUBAI),
        _make_segment_at(_INNSBRUCK),
    ]
    fake = _AlwaysTransientProvider()
    service = _make_scheduler()

    result = service._fetch_weather(segments, provider=fake)

    assert len(result) == 3
    assert all(r.has_error for r in result)
    # Segment 1: volles Retry-Budget (3 Versuche) ausgeschöpft -> fail_fast
    # aktiviert. Segmente 2+3: je nur noch 1 Versuch (kein Sleep, kein
    # Retry) -> insgesamt 3 + 1 + 1 = 5 Aufrufe statt 3 + 3 + 3 = 9.
    assert fake.calls == 5, (
        f"Erwartet 3 Versuche für Segment 1 (volles Retry-Budget) + je 1 "
        f"Versuch für die Folgesegmente (Fail-Fast-Budget, Adversary Finding "
        f"F002), tatsächlich {fake.calls} Aufruf(e) insgesamt — ohne "
        f"Fail-Fast-Budget skaliert ein andauernder Ausfall über viele "
        f"Segmente/User ungebremst (45-Minuten-Rechnung im Adversary-Fund)"
    )


class _TimeoutFlakyProvider:
    """Echtes WeatherProvider-Objekt (kein Mock()/patch()): wirft beim 1.
    Aufruf eine ECHTE `httpx.ReadTimeout` (str(exc) == "timed out"), gewrappt
    exakt wie im Provider-Code (`providers/openmeteo.py:484-487`:
    `ProviderRequestError("...", f"Request failed: {e}") from e`), und
    liefert ab dem 2. Aufruf valide Daten. Beweist Adversary Finding F005:
    Timeout-Erkennung muss über den Exception-TYP laufen, weil der Text
    "timed out" den Marker "timeout" nicht enthält."""

    def __init__(self, fixture_dir: str) -> None:
        self._delegate = FixtureProvider(fixture_dir)
        self.calls = 0

    @property
    def name(self) -> str:
        return "timeout-flaky-test"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        self.calls += 1
        if self.calls == 1:
            real_timeout = httpx.ReadTimeout("timed out")
            raise ProviderRequestError(
                "timeout-flaky-test", f"Request failed: {real_timeout}"
            ) from real_timeout
        return self._delegate.fetch_forecast(
            location, start=start, end=end, enrich_ensemble=enrich_ensemble
        )


def test_transient_timeout_retried_via_exception_type_not_text_match():
    segment = _make_segment_at(_INNSBRUCK)
    fake = _TimeoutFlakyProvider(_REAL_FIXTURES_DIR)
    service = _make_scheduler()

    result = service._fetch_weather([segment], provider=fake)

    assert len(result) == 1
    assert result[0].has_error is False, (
        f"Ein echter httpx.ReadTimeout ('timed out') muss als transient "
        f"erkannt werden (Adversary Finding F005) und wiederholt werden, "
        f"war has_error={result[0].has_error!r}, "
        f"error_message={result[0].error_message!r} — der Text-Marker "
        f"'timeout' matcht 'timed out' nicht, Erkennung muss über den "
        f"Exception-Typ (httpx.TimeoutException via __cause__) laufen"
    )
    assert fake.calls == 2, (
        f"Erwartet genau 2 Versuche (1 initial + 1 Retry bis valide Daten "
        f"kommen), tatsächlich {fake.calls} Aufruf(e) — ohne Exception-Typ-"
        f"Erkennung wird ein echter Timeout nie als transient erkannt und "
        f"nach genau 1 Versuch als has_error markiert (Adversary Finding F005)"
    )


class _MixedFailureProvider:
    """Echtes WeatherProvider-Objekt (kein Mock()/patch()): Segment 1
    (Innsbruck) schlägt SOFORT nicht-transient fehl (0 Retries verbraucht,
    kein andauernder Provider-Ausfall). Segment 2 (Stubai) schlägt beim 1.
    Versuch transient fehl und liefert beim 2. Versuch valide Daten — sein
    eigener Fehlerverlauf ist identisch zu
    `test_transient_error_retried_before_marking_has_error`. Beweist
    Adversary Finding F004: Segment 1s sofortiger, providerunabhängiger
    Fehler darf `fail_fast` nicht auslösen und Segment 2 den Retry-Anspruch
    nicht kosten."""

    def __init__(self, fixture_dir: str) -> None:
        self._delegate = FixtureProvider(fixture_dir)
        self.calls = 0
        self.seg2_calls = 0

    @property
    def name(self) -> str:
        return "mixed-test"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        self.calls += 1
        is_stubai = (
            abs(location.latitude - _STUBAI[0]) < 0.001
            and abs(location.longitude - _STUBAI[1]) < 0.001
        )
        if not is_stubai:
            raise ProviderError("mixed-test", "Ungueltige Koordinaten uebergeben")
        self.seg2_calls += 1
        if self.seg2_calls == 1:
            raise ProviderError("mixed-test", "Simulierter transienter 503")
        return self._delegate.fetch_forecast(
            location, start=start, end=end, enrich_ensemble=enrich_ensemble
        )


def test_fail_fast_not_triggered_by_non_transient_first_segment():
    segments = [
        _make_segment_at(_INNSBRUCK),  # Segment 1: sofortiger, nicht-transienter Fehler
        _make_segment_at(_STUBAI),  # Segment 2: transient, sollte retried werden
    ]
    fake = _MixedFailureProvider(_REAL_FIXTURES_DIR)
    service = _make_scheduler()

    result = service._fetch_weather(segments, provider=fake)

    assert len(result) == 2
    assert result[0].has_error is True, "Segment 1 (nicht-transient) bleibt fehlerhaft"
    assert result[1].has_error is False, (
        f"Segment 2s transienter Fehler muss trotz Segment 1s sofortigem "
        f"nicht-transienten Fehler wiederholt werden (Adversary Finding "
        f"F004: fail_fast darf nur bei erschöpftem Retry-Budget UND "
        f"transientem Fehler greifen), war has_error="
        f"{result[1].has_error!r}, error_message={result[1].error_message!r}"
    )
    assert fake.seg2_calls == 2, (
        f"Erwartet genau 2 Versuche für Segment 2 (1 initial + 1 Retry bis "
        f"valide Daten), tatsächlich {fake.seg2_calls} Aufruf(e) — Segment 1s "
        f"nicht-transienter Sofortfehler darf `fail_fast` nicht auslösen und "
        f"damit Segment 2s Retry-Anspruch nicht zerstören (Adversary Finding "
        f"F004)"
    )


# ---------------------------------------------------------------------------
# AC-5 — On-Demand (#1007): weder Hinweis-Versand noch Nachliefer-Marker
# ---------------------------------------------------------------------------

def test_on_demand_suppresses_hint_mail_and_marker_above_threshold(tmp_path, monkeypatch):
    user_id = "tdd-1113-ac5"
    trip_name = "TDD1113 AC5 OnDemand"
    _make_user(user_id)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _partial_fixture_dir(tmp_path))

    # Gleicher 5/6-Ausfall (83 %) wie AC-1, aber on_demand=True.
    coords = [_STUBAI] * 5 + [_INNSBRUCK]
    trip = _make_trip(user_id, "tdd-1113-ac5-trip", trip_name, date.today(), coords)

    baseline_uid = _max_uid()
    service = TripReportSchedulerService(user_id=user_id)
    outcome = service._send_trip_report_outcome(trip, "morning", on_demand=True)

    assert outcome == "no_weather", (
        f"On-Demand-Abruf bei 83 % Ausfall soll ebenfalls 'no_weather' "
        f"liefern (Guard wirkt, nur die Seiteneffekte werden unterdrückt), "
        f"war {outcome!r}"
    )
    assert _pending_markers(user_id) == [], (
        "On-Demand-Abruf hat trotz #1007-Ausnahme einen Nachliefer-Marker "
        "geschrieben"
    )

    mails = _find_mails(trip_name, baseline_uid, timeout_s=20)
    assert mails == [], (
        f"On-Demand-Abruf hat trotz #1007-Ausnahme eine Hinweis-Mail "
        f"versendet: {[_subject(m) for m in mails]}"
    )
