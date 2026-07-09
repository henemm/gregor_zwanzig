"""TDD RED — Issue #1007: „heute"/„morgen" liefern das volle Tages-Briefing.

PO-Entscheidung (Issue #1007): Antwort `heute`/`morgen` auf ein Briefing löst das
KOMPLETTE Tages-Briefing über die konfigurierten Kanäle aus (wie `report`, aber
tag-genau, ohne [TEST]-Präfix, ohne Etappen-Fallback, ohne separate
Bestätigungs-Mail). Kurzform bleibt unter `glance`.

RED, weil `heute`/`morgen` aktuell den `_fmt_day()`-Einzeiler zurückgeben und
keinerlei Versand auslösen (kein briefing_log-Eintrag, keine Mail, kein
`suppress_email_reply`-Flag).

Mock-frei: echte Persistenz unter data/users/, echter `TripCommandProcessor`,
echter SMTP-Versand (Resend) an das Stalwart-Test-Postfach
gregor-test@henemm.com, echte IMAP-Verifikation. Env-Creds werden aus der
Hauptrepo-.env geladen (Worktree hat keine eigene .env).

SPEC: docs/specs/modules/issue_1007_heute_voll_briefing.md
(AC-1..AC-6, AC-8 — AC-7/Telegram-Live-Beweis erfolgt auf Staging im E2E-Schritt)
"""
from __future__ import annotations

import email
import imaplib
import json
import os
import shutil
import time as time_mod
from datetime import date, datetime, time, timedelta, timezone
from email.header import decode_header
from pathlib import Path


from app.loader import save_trip
from app.models import TripReportConfig
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.trip_command_processor import (
    InboundMessage, TripCommandProcessor, _on_demand_failure_body,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAIN_ENV = Path("/home/hem/gregor_zwanzig/.env")
_DATA_USERS = _REPO_ROOT / "data" / "users"
_TEST_MAILBOX = "gregor-test@henemm.com"


def _load_main_env() -> None:
    """Lädt SMTP-/IMAP-Creds aus der Hauptrepo-.env (Worktree hat keine)."""
    if not _MAIN_ENV.exists():
        return
    for line in _MAIN_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_main_env()


LAT, LON = 47.2692, 11.4041

# Issue #1044: FESTES Mittagsfenster, keine now()-Abhängigkeit. Das Voll-Briefing
# filtert die Timeline nach `arrival_time.date() == target_date` (siehe
# TripCommandProcessor._aggregate_day / _fmt_timeline) — NICHT nach "jetzt aktiv".
# 08:00-18:00 Ortszeit entspricht bei den Alpen-/Korsika-Zeitzonen (UTC+1/+2)
# 06:00-17:00 UTC und liegt damit zu JEDER Testlaufzeit vollständig im selben
# UTC-Tag wie stage.date. Damit ist der Test uhrzeit-unabhängig. Der frühere
# now()-basierte Ansatz rutschte 00:00-02:00 und 23:00-24:00 Ortszeit doch in
# den Nachbar-UTC-Tag (24h-Simulation belegt).
_WIN_START = "08:00"
_WIN_END = "18:00"
_STAGE_START = time(8, 0)


def _make_user(user_id: str) -> None:
    """Frischer Test-User mit Test-Postfach als Empfänger."""
    udir = _DATA_USERS / user_id
    if udir.exists():
        shutil.rmtree(udir)
    udir.mkdir(parents=True)
    (udir / "user.json").write_text(json.dumps({
        "id": user_id,
        "created_at": "2026-07-04T00:00:00Z",
        "mail_to": _TEST_MAILBOX,
    }))


def _make_trip(
    user_id: str, trip_id: str, name: str, stage_date: date,
    report_config: TripReportConfig | None = None,
) -> Trip:
    """Etappe mit einem Segment im festen Mittagsfenster (uhrzeit-unabhängig, #1044)."""
    wps = [
        Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
                 time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
                 arrival_override=_WIN_START),
        Waypoint(id="G2", name="Seg 2 Start", lat=47.2820, lon=11.4230,
                 elevation_m=700,
                 time_window=TimeWindow(start=time(12, 0), end=time(12, 0))),
        Waypoint(id="G3", name="Ziel", lat=47.2950, lon=11.4420, elevation_m=800,
                 time_window=TimeWindow(start=time(23, 59), end=time(23, 59)),
                 arrival_override=_WIN_END),
    ]
    stage = Stage(id="T1", name=f"{name}-Etappe", date=stage_date,
                  start_time=_STAGE_START, waypoints=wps)
    trip = Trip(id=trip_id, name=name, stages=[stage], report_config=report_config)
    save_trip(trip, user_id=user_id)
    return trip


def _make_trip_two_stages(
    user_id: str, trip_id: str, name: str, date_today: date, date_tomorrow: date,
) -> Trip:
    """Zwei-Etappen-Trip (heute + morgen) für Snapshot-Regressionstests.

    Beide Etappen im festen Mittagsfenster, damit der Test uhrzeit-unabhängig
    läuft (#1044).
    """
    wps_today = [
        Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
                 time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
                 arrival_override=_WIN_START),
        Waypoint(id="G2", name="Ziel", lat=47.2950, lon=11.4420, elevation_m=800,
                 time_window=TimeWindow(start=time(23, 59), end=time(23, 59)),
                 arrival_override=_WIN_END),
    ]
    wps_tomorrow = [
        Waypoint(id="G1", name="Start Tag2", lat=47.2950, lon=11.4420, elevation_m=800,
                 time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
                 arrival_override=_WIN_START),
        Waypoint(id="G2", name="Ziel Tag2", lat=47.3100, lon=11.4600, elevation_m=900,
                 time_window=TimeWindow(start=time(23, 59), end=time(23, 59)),
                 arrival_override=_WIN_END),
    ]
    stage1 = Stage(id="T1", name=f"{name}-Etappe1", date=date_today,
                   start_time=_STAGE_START, waypoints=wps_today)
    stage2 = Stage(id="T2", name=f"{name}-Etappe2", date=date_tomorrow,
                   start_time=_STAGE_START, waypoints=wps_tomorrow)
    trip = Trip(id=trip_id, name=name, stages=[stage1, stage2])
    save_trip(trip, user_id=user_id)
    return trip


def _snapshot_path(user_id: str, trip_id: str) -> Path:
    # Issue #1133: WeatherSnapshotService liest/schreibt via get_snapshots_dir()
    # -> get_data_dir() (isoliert durch die autouse-Fixture) — der Prüfpfad
    # muss identisch aufgelöst werden statt der hartkodierten _DATA_USERS-
    # Konstante (echter Baum). briefing_log.json/user.json bleiben real-tree-
    # basiert, da trip_report_scheduler.py diese Pfade bewusst nicht migriert
    # (Known Limitations #1133).
    from app.loader import get_snapshots_dir
    return get_snapshots_dir(user_id) / f"{trip_id}.json"


def _briefing_log(user_id: str) -> list:
    p = _DATA_USERS / user_id / "briefing_log.json"
    if not p.exists():
        return []
    return json.loads(p.read_text())


def _process(user_id: str, trip_name: str, body: str):
    msg = InboundMessage(
        trip_name=trip_name, body=body, sender=_TEST_MAILBOX,
        channel="email", received_at=datetime.now(timezone.utc),
        user_id=user_id,
    )
    return TripCommandProcessor().process(msg)


def _imap():
    m = imaplib.IMAP4_SSL(os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
                          int(os.environ.get("GZ_IMAP_PORT", "993")))
    m.login(os.environ["GZ_TEST_IMAP_USER"], os.environ["GZ_TEST_IMAP_PASS"])
    m.select("INBOX")
    return m


def _subject(msg) -> str:
    raw = decode_header(msg.get("Subject", ""))[0][0]
    return raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)


def _find_mails(trip_name: str, min_uid: int, timeout_s: int = 120) -> list:
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


# ---------------------------------------------------------------------------
# AC-1 + AC-3 + AC-5 — heute → volles Briefing, ohne [TEST], genau EINE Mail
# ---------------------------------------------------------------------------

def test_ac1_ac3_ac5_heute_sendet_volles_briefing_genau_eine_mail():
    """AC-1: `heute` versendet das volle HTML-Briefing für HEUTE.
    AC-3: ohne [TEST]-Präfix, gekennzeichnet als „auf Anfrage".
    AC-5: genau EINE Mail — keine separate Bestätigungs-Mail."""
    user_id = "tdd-1007-ac1"
    trip_name = "TDD1007 AC1 HeuteVoll"
    _make_user(user_id)
    _make_trip(user_id, "tdd-1007-ac1-trip", trip_name, date.today())

    baseline_uid = _max_uid()
    result = _process(user_id, trip_name, "heute")

    assert result.success, f"Kommando fehlgeschlagen: {result.confirmation_body}"
    assert getattr(result, "suppress_email_reply", None) is True, (
        "CommandResult.suppress_email_reply fehlt/False — es würde eine "
        "zusätzliche Bestätigungs-Mail verschickt (AC-5)"
    )
    log = _briefing_log(user_id)
    assert len(log) == 1, (
        f"Kein Voll-Briefing-Versand ausgelöst (briefing_log={log}) — "
        f"`heute` liefert offenbar weiter den Einzeiler"
    )

    mails = _find_mails(trip_name, baseline_uid)
    assert len(mails) == 1, (
        f"{len(mails)} Mails für '{trip_name}' angekommen — erwartet GENAU 1 "
        f"(das Briefing, keine Bestätigungs-Mail)"
    )
    mail = mails[0]
    assert mail.get("X-GZ-Mail-Type") == "trip-briefing", (
        f"Mail ist kein volles Trip-Briefing (X-GZ-Mail-Type="
        f"{mail.get('X-GZ-Mail-Type')})"
    )
    subj = _subject(mail)
    assert "[TEST]" not in subj, f"[TEST]-Präfix im Betreff: {subj}"
    html = _html_body(mail)
    assert "Anfrage" in html or "Anfrage" in subj, (
        "Kennzeichnung 'auf Anfrage' fehlt in Betreff und Body"
    )
    today_str = date.today().strftime("%d.%m.%Y")
    assert today_str in html, (
        f"Briefing nennt nicht das heutige Datum {today_str}"
    )


# ---------------------------------------------------------------------------
# AC-2 — morgen → volles Briefing für MORGEN
# ---------------------------------------------------------------------------

def test_ac2_morgen_sendet_volles_briefing_fuer_morgen():
    user_id = "tdd-1007-ac2"
    trip_name = "TDD1007 AC2 MorgenVoll"
    _make_user(user_id)
    tomorrow = date.today() + timedelta(days=1)
    _make_trip(user_id, "tdd-1007-ac2-trip", trip_name, tomorrow)

    baseline_uid = _max_uid()
    result = _process(user_id, trip_name, "morgen")

    assert result.success, f"Kommando fehlgeschlagen: {result.confirmation_body}"
    assert len(_briefing_log(user_id)) == 1, (
        "Kein Voll-Briefing-Versand für 'morgen' ausgelöst"
    )
    mails = _find_mails(trip_name, baseline_uid)
    assert len(mails) == 1, f"{len(mails)} Mails statt genau 1"
    html = _html_body(mails[0])
    tomorrow_str = tomorrow.strftime("%d.%m.%Y")
    assert tomorrow_str in html, (
        f"Briefing nennt nicht das morgige Datum {tomorrow_str}"
    )


# ---------------------------------------------------------------------------
# AC-4 — keine Etappe am Zieltag: klare Antwort, KEIN Versand, KEIN Fallback
# ---------------------------------------------------------------------------

def test_ac4_keine_etappe_keine_mail_klare_antwort():
    user_id = "tdd-1007-ac4"
    trip_name = "TDD1007 AC4 KeineEtappe"
    _make_user(user_id)
    _make_trip(user_id, "tdd-1007-ac4-trip", trip_name,
               date.today() + timedelta(days=10))

    result = _process(user_id, trip_name, "heute")

    assert "Keine Etappe geplant" in result.confirmation_body, (
        f"Klare 'Keine Etappe geplant'-Antwort fehlt: {result.confirmation_body!r}"
    )
    assert _briefing_log(user_id) == [], (
        "Trotz fehlender Etappe wurde ein Briefing versendet — der "
        "#768-Fallback darf für heute/morgen NICHT greifen (AC-4)"
    )


# ---------------------------------------------------------------------------
# AC-6 — glance bleibt Kurzform ohne Versand
# ---------------------------------------------------------------------------

def test_ac6_glance_bleibt_kurzform_ohne_versand():
    user_id = "tdd-1007-ac6"
    trip_name = "TDD1007 AC6 Glance"
    _make_user(user_id)
    _make_trip(user_id, "tdd-1007-ac6-trip", trip_name, date.today())

    result = _process(user_id, trip_name, "glance")

    assert result.command == "glance"
    assert "Glance" in result.confirmation_body, (
        f"Glance-Kurzform verändert: {result.confirmation_body!r}"
    )
    assert _briefing_log(user_id) == [], (
        "glance darf KEIN Briefing versenden (AC-6)"
    )


# ---------------------------------------------------------------------------
# AC-8 — Zwei-Nutzer-Isolation
# ---------------------------------------------------------------------------

def test_ac8_zwei_nutzer_isolation():
    user_a, user_b = "tdd-1007-usera", "tdd-1007-userb"
    name_a, name_b = "TDD1007 IsoUserA", "TDD1007 IsoUserB"
    _make_user(user_a)
    _make_user(user_b)
    _make_trip(user_a, "tdd-1007-iso", name_a, date.today())
    _make_trip(user_b, "tdd-1007-iso", name_b, date.today())

    baseline_uid = _max_uid()
    result = _process(user_a, name_a, "heute")

    assert result.success, f"Kommando fehlgeschlagen: {result.confirmation_body}"
    assert len(_briefing_log(user_a)) == 1, (
        "Nutzer A: kein Voll-Briefing-Versand ausgelöst"
    )
    assert _briefing_log(user_b) == [], (
        "Cross-User-Leck: Nutzer Bs briefing_log wurde verändert"
    )
    mails_b = _find_mails(name_b, baseline_uid, timeout_s=30)
    assert mails_b == [], (
        f"Cross-User-Leck: {len(mails_b)} Mail(s) für Nutzer Bs Trip versendet"
    )


# ---------------------------------------------------------------------------
# F001 (Adversary-Fix) — kein Kanal aktiv: kein Versand, kein suppress,
# erkennbare Antwort, kein briefing_log-Eintrag.
# ---------------------------------------------------------------------------

def test_f001_keine_kanaele_aktiv_keine_stille_ohne_versand():
    user_id = "tdd-1007-f001"
    trip_name = "TDD1007 F001 KeineKanaele"
    _make_user(user_id)
    rc = TripReportConfig(
        trip_id="tdd-1007-f001-trip",
        send_email=False, send_sms=False, send_telegram=False,
    )
    _make_trip(user_id, "tdd-1007-f001-trip", trip_name, date.today(), report_config=rc)

    baseline_uid = _max_uid()
    result = _process(user_id, trip_name, "heute")

    assert result.success, f"Kommando fehlgeschlagen: {result.confirmation_body}"
    assert getattr(result, "suppress_email_reply", None) is not True, (
        "F001: Ohne aktive Kanäle darf suppress_email_reply NICHT True sein "
        "— sonst bekommt der Nutzer gar keine Antwort (totale Stille)"
    )
    assert "kanäle" in result.confirmation_body.lower(), (
        f"F001: Antwort muss die fehlenden Versandkanäle nennen: "
        f"{result.confirmation_body!r}"
    )
    assert _briefing_log(user_id) == [], (
        "F001: Ohne aktive Kanäle darf kein briefing_log-Eintrag entstehen"
    )
    mails = _find_mails(trip_name, baseline_uid, timeout_s=20)
    assert mails == [], f"F001: Trotz 0 Kanälen wurde eine Mail versendet: {len(mails)}"


# ---------------------------------------------------------------------------
# F002 (Adversary-Fix) — reine Outcome→Text-Mapping-Funktion, mock-frei
# ---------------------------------------------------------------------------

def test_f002_no_weather_body_nennt_wetterdaten_nicht_keine_etappe():
    body = _on_demand_failure_body("no_weather", "Heute", date(2026, 7, 10))
    assert "Wetterdaten" in body, body
    assert "Keine Etappe geplant" not in body, body


def test_f002_no_stage_body_nennt_keine_etappe_geplant():
    body = _on_demand_failure_body("no_stage", "Heute", date(2026, 7, 10))
    assert "Keine Etappe geplant" in body, body


# ---------------------------------------------------------------------------
# Regressionstest (Runde 3) — On-Demand-'heute' darf die kombinierte
# heute+morgen-Momentaufnahme NICHT mit nur dem Zieltag überschreiben.
# ---------------------------------------------------------------------------

def test_snapshot_bleibt_kombiniert_nach_heute():
    """Regression: 'heute' darf die kombinierte Momentaufnahme (heute+morgen)
    aus 'glance' nicht mit nur dem heutigen Tag überschreiben — sonst meldet
    ein nachfolgendes 'glance' für 'morgen' fälschlich 'Keine Etappe geplant',
    bis der Cache-Check in _fetch_and_save_snapshot am Folgetag von selbst
    heilt."""
    user_id = "tdd-1007-adv-verify"
    trip_name = "TDD1007 SnapshotBleibtKombiniert"
    today = date.today()
    tomorrow = today + timedelta(days=1)
    _make_user(user_id)
    trip = _make_trip_two_stages(
        user_id, "tdd-1007-adv-verify-trip", trip_name, today, tomorrow,
    )

    # 1. glance erzeugt real die kombinierte Momentaufnahme (heute+morgen).
    result_glance = _process(user_id, trip_name, "glance")
    assert result_glance.command == "glance"
    assert "Keine Etappe geplant" not in result_glance.confirmation_body, (
        f"Vorbedingung verletzt — glance sieht bereits keine Etappe: "
        f"{result_glance.confirmation_body!r}"
    )

    snap_path = _snapshot_path(user_id, trip.id)
    assert snap_path.exists(), "glance hat keine Momentaufnahme angelegt"
    baseline_content = snap_path.read_text()

    # 2. heute verarbeiten — echter Versand ans Test-Postfach.
    baseline_uid = _max_uid()
    result_heute = _process(user_id, trip_name, "heute")
    assert result_heute.success, f"Kommando fehlgeschlagen: {result_heute.confirmation_body}"
    assert len(_briefing_log(user_id)) == 1, "Kein Voll-Briefing-Versand für 'heute' ausgelöst"
    mails = _find_mails(trip_name, baseline_uid)
    assert len(mails) == 1, f"{len(mails)} Mails statt genau 1"

    # 3a. Momentaufnahme unverändert (identischer Inhalt).
    after_content = snap_path.read_text()
    assert after_content == baseline_content, (
        "Regression #1007: On-Demand-'heute' hat die kombinierte "
        "Momentaufnahme überschrieben (nur noch heutiger Tag enthalten)"
    )

    # 3b. Ein erneutes glance nennt weiterhin Morgen-Daten.
    result_glance2 = _process(user_id, trip_name, "glance")
    assert "morgen" in result_glance2.confirmation_body.lower()
    morgen_line = next(
        (l for l in result_glance2.confirmation_body.splitlines() if "morgen" in l.lower()),
        "",
    )
    assert "Keine Etappe geplant" not in morgen_line, (
        f"Regression #1007: 'morgen' meldet nach 'heute' fälschlich keine "
        f"Etappe: {morgen_line!r}"
    )
