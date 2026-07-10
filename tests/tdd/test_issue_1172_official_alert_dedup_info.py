"""Issue #1172 — Amtliche Warn-Mail: Entdopplung + Kerninfos.

RED-Phase: die neue Dedup-Funktion `dedupe_official_alerts` und der neue
Standalone-Alert-Formatter `render_official_alert_notice_plain` existieren noch
nicht. Diese Offline-Tests treiben die Implementierung deterministisch (echte
`OfficialAlert`-Instanzen, kein Mock). Der echte Zustellnachweis (E2E, real an
gregor-test@henemm.com + Telegram) folgt in der Validate-Phase.

Der geteilte Renderer `render_official_alerts_plain` (Compare/Briefing) MUSS
byte-gleich bleiben (AC-4) — dafür der Guard-Test.
"""

from __future__ import annotations

import imaplib
import time
import uuid
from datetime import date, datetime, timezone
from email import message_from_bytes
from email.header import decode_header, make_header
from zoneinfo import ZoneInfo

import pytest

from services.official_alerts.models import OfficialAlert


def _alert(level: int, *, hazard: str = "heat", region: str = "Haute-Corse",
           label: str = "Hitze", vf=None, vt=None) -> OfficialAlert:
    return OfficialAlert(
        source="meteo-france",
        hazard=hazard,
        level=level,
        label=label,
        valid_from=vf,
        valid_to=vt,
        url="https://example.invalid/vigilance",
        region_label=region,
    )


# ---------------------------------------------------------------------------
# AC-3 — dedupe_official_alerts: kollabiert (region_label, hazard), max level
# ---------------------------------------------------------------------------


def test_dedupe_keeps_max_level_and_separates_hazards():
    """Given mehrere Warnungen gleicher (region_label, hazard) mit Levels [2,4,3]
    plus eine mit anderem hazard / When dedupe_official_alerts läuft / Then
    Länge 2, und die kollabierte Gruppe trägt level == 4 (Maximum).

    Issue #1200: Eingabe/Ausgabe sind (OfficialAlert, segment_ids)-Tupel."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    tagged = [
        (_alert(2, hazard="heat"), ["1"]),
        (_alert(4, hazard="heat"), ["2"]),
        (_alert(3, hazard="heat"), ["3"]),
        (_alert(3, hazard="thunderstorm", label="Gewitter"), ["1"]),
    ]
    result = dedupe_official_alerts(tagged)

    assert len(result) == 2, f"erwartet 2 Gruppen (heat kollabiert, thunder eigen), bekommen {len(result)}"
    heat = [entry for entry in result if entry[0].hazard == "heat"]
    assert len(heat) == 1, "heat muss zu genau EINER Warnung kollabieren"
    assert heat[0][0].level == 4, f"höchstes Level muss behalten werden, bekommen {heat[0][0].level}"


# ---------------------------------------------------------------------------
# AC-1 (offline) — Render dedupliziert identische Warnungen zu EINEM Block
# ---------------------------------------------------------------------------


def test_render_notice_plain_dedups_identical_warnings():
    """Given 12 identische Warnungen (gleiche region_label+hazard) / When
    render_official_alert_notice_plain läuft / Then die Ausgabe enthält GENAU
    EINEN Warnblock (eine Region-Zeile), nicht 12.

    Issue #1200: Eingabe sind (OfficialAlert, segment_ids)-Tupel."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    tagged = [(_alert(3), ["1"]) for _ in range(12)]
    out = "\n".join(render_official_alert_notice_plain(tagged, tz=ZoneInfo("UTC")))

    assert out.count("Haute-Corse") == 1, (
        f"erwartet genau EINE Region-Zeile (ein Warnblock), bekommen "
        f"{out.count('Haute-Corse')}:\n{out}"
    )


# ---------------------------------------------------------------------------
# AC-2 (offline) — Warnblock trägt Schwere-Wort, Region, Gültigkeitszeitraum
# ---------------------------------------------------------------------------


def test_render_notice_plain_contains_core_info():
    """Given eine Warnung level=3 (ORANGE) mit region_label und valid_from/to /
    When render_official_alert_notice_plain läuft / Then enthält der Block das
    Schwere-Wort, den Regionsnamen und beide Zeitpunkte (lokal formatiert).

    Issue #1200: Eingabe ist ein (OfficialAlert, segment_ids)-Tupel."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    vf = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    vt = datetime(2026, 7, 12, 20, 0, tzinfo=timezone.utc)
    out = "\n".join(render_official_alert_notice_plain(
        [(_alert(3, vf=vf, vt=vt), ["1"])], tz=ZoneInfo("UTC")
    ))

    assert "ORANGE" in out, f"Schwere-Wort 'ORANGE' (level 3) fehlt:\n{out}"
    assert "Haute-Corse" in out, f"Regionsname fehlt:\n{out}"
    assert "12:00" in out and "20:00" in out, f"Gültigkeitszeitraum fehlt:\n{out}"
    assert "Hitze" in out, f"Label fehlt:\n{out}"


def test_render_notice_plain_handles_missing_validity():
    """Given eine Warnung ohne valid_from/valid_to / When gerendert / Then kein
    Crash, und der Block markiert die Gültigkeit als unbekannt statt None.

    Issue #1200: Eingabe ist ein (OfficialAlert, segment_ids)-Tupel."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    out = "\n".join(render_official_alert_notice_plain([(_alert(4), ["1"])], tz=ZoneInfo("UTC")))
    assert "ROT" in out, f"level 4 muss 'ROT' ergeben:\n{out}"
    assert "None" not in out, f"None darf nicht im Body erscheinen:\n{out}"


# ---------------------------------------------------------------------------
# AC-4 (Guard) — geteilter Renderer render_official_alerts_plain UNVERÄNDERT
# ---------------------------------------------------------------------------


def test_shared_plain_renderer_unchanged():
    """Given der geteilte Compare/Briefing-Renderer / When mit einer Warnung
    aufgerufen / Then unverändertes Format 'Amtliche Warnung: {label}' (keine
    Regression durch diesen Fix)."""
    from output.renderers.alert.official_alerts import render_official_alerts_plain

    lines = render_official_alerts_plain([("Haute-Corse", [_alert(3)])])
    assert lines == ["Amtliche Warnung: Hitze"], (
        f"geteilter Renderer muss byte-gleich bleiben, bekommen: {lines}"
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2 (Validate-Phase) — ECHTER E2E-Zustellpfad: eine amtliche Warn-Mail
# REAL ueber send_official_alert() an gregor-test@henemm.com senden (Stalwart-
# Test-Postfach, KEIN Mock, KEIN Resend) und den zugestellten Plain-Body per
# IMAP (GZ_TEST_IMAP_*) verifizieren. Muster: test_issue_1087_trip_official_alerts
# (_poll_imap_for_marker, _write_user_profile) und test_issue_1150 (@pytest.mark.email
# + settings.can_send_email()-Skip). Der user_id enthaelt "tdd" -> is_test_user_id()
# erzwingt in with_user_profile() den for_testing()-Pfad (Stalwart statt Resend).
# ---------------------------------------------------------------------------

# Haute-Corse (Korsika) — passend zum region_label. Reale Koordinaten, damit
# tz_for_coords() dieselbe Zeitzone liefert wie der Produktions-Sendepfad.
_CORSICA_LAT, _CORSICA_LON = 42.30, 9.15


def _write_test_profile(user_id: str) -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    profile_dir = repo_root / "data" / "users" / user_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    import json

    (profile_dir / "user.json").write_text(
        json.dumps({"mail_to": "gregor-test@henemm.com"}), encoding="utf-8"
    )


def _cleanup_test_user(user_id: str) -> None:
    import shutil
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    user_dir = repo_root / "data" / "users" / user_id
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)


def _corsica_trip(trip_id: str, marker: str):
    """Minimal-Trip mit EINEM Wegpunkt auf Korsika (Haute-Corse). Der Marker im
    Namen macht den Betreff '[<name>] Amtliche Warnung' eindeutig auffindbar."""
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(
            id="G1", name="Haute-Corse", lat=_CORSICA_LAT, lon=_CORSICA_LON,
            elevation_m=800.0,
        )],
    )
    trip = Trip(id=trip_id, name=f"1172-E2E {marker}", stages=[stage])
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def _poll_imap_for_marker(settings, marker: str, attempts: int = 12, wait_s: int = 5):
    """Pollt INBOX nach einer Mail mit `marker` im (dekodierten) Betreff.

    Anders als der klassische #1087-Helfer wird NICHT auf die serverseitige
    IMAP-'SUBJECT'-Suche vertraut: Stalwart liefert fuer 'SEARCH SUBJECT "<tag>"'
    hier verlaesslich ein leeres Ergebnis, obwohl der Betreff den Tag woertlich
    traegt (fehlender/verzoegerter Volltext-Index). Stattdessen werden die
    juengsten Nachrichten geholt und die Betreffs in Python auf den (eindeutigen)
    Marker geprueft — race-sicher wie im #1150-Muster (eigene Mail verifizieren).

    Returns: (subject, body_text) — subject bleibt None, wenn nichts gefunden.
    """
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    if not all([imap_host, imap_user, imap_pass]):
        pytest.skip("IMAP-Credentials (GZ_TEST_IMAP_*) fehlen")

    for _ in range(attempts):
        time.sleep(wait_s)
        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port or 993)
        try:
            imap.login(imap_user, imap_pass)
            imap.select("INBOX")
            _, data = imap.search(None, "ALL")
            all_ids = data[0].split()
            # Nur die juengsten Nachrichten scannen (das gemeinsame Test-Postfach
            # enthaelt tausende Alt-Mails); die eigene liegt praktisch am Ende.
            for mid in reversed(all_ids[-40:]):
                _, msg = imap.fetch(mid, "(RFC822)")
                parsed = message_from_bytes(msg[0][1])
                subject = str(make_header(decode_header(parsed.get("Subject", ""))))
                if marker not in subject:
                    continue
                body_text = ""
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text += payload.decode("utf-8", "ignore")
                return subject, body_text
        finally:
            try:
                imap.logout()
            except Exception:
                pass
    return None, ""


@pytest.mark.email
def test_ac1_e2e_dedup_one_block():
    """AC-1 (E2E): 5 IDENTISCHE amtliche Warnungen (gleiche region_label+hazard)
    werden REAL ueber send_official_alert() an gregor-test@henemm.com zugestellt.
    Der per IMAP abgerufene Plain-Body enthaelt GENAU EINEN Warnblock
    (body.count('Haute-Corse') == 1) — nicht 5. KEIN Mock."""
    from app.config import Settings
    from services.notification_service import NotificationService

    user_id = f"tdd-1172-ac1-{uuid.uuid4().hex[:8]}"
    _write_test_profile(user_id)
    settings = Settings().with_user_profile(user_id)
    if not settings.can_send_email():
        _cleanup_test_user(user_id)
        pytest.skip("SMTP (GZ_TEST_SMTP_*) nicht konfiguriert")

    try:
        marker = uuid.uuid4().hex[:8]
        trip = _corsica_trip(f"tdd-1172-ac1-trip-{marker}", marker)

        vf = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
        vt = datetime(2026, 7, 12, 20, 0, tzinfo=timezone.utc)
        # Issue #1200: notices sind (OfficialAlert, segment_ids)-Tupel.
        notices = [
            (
                OfficialAlert(
                    source="meteo-france", hazard="heat", level=3, label="Hitze",
                    valid_from=vf, valid_to=vt, region_label="Haute-Corse",
                    url="https://example.invalid/vigilance",
                ),
                ["1"],
            )
            for _ in range(5)
        ]

        ns = NotificationService(settings, user_id)
        result = ns.send_official_alert(
            trip=trip, notices=notices, effective_channels={"email"},
        )
        assert result.sent, "send_official_alert() meldet keinen Versand"

        subject, body = _poll_imap_for_marker(settings, marker)
        assert subject is not None, f"Keine Mail mit Marker {marker} in 60s zugestellt"
        assert body.count("Haute-Corse") == 1, (
            f"AC-1: 5 identische Warnungen muessen zu GENAU EINEM Warnblock "
            f"dedupliziert werden (eine Region-Zeile), bekommen "
            f"{body.count('Haute-Corse')}x im zugestellten Body:\n{body}"
        )
    finally:
        _cleanup_test_user(user_id)


@pytest.mark.email
def test_ac2_e2e_core_info():
    """AC-2 (E2E): Eine amtliche Warnung level=3 wird REAL zugestellt. Der per
    IMAP abgerufene Plain-Body traegt das Schwere-Wort ('ORANGE'), die Region
    ('Haute-Corse') und BEIDE Gueltigkeits-Zeitpunkte (lokal formatiert, exakt
    wie der Produktions-Sendepfad sie aus den Wegpunkt-Koordinaten ableitet).
    KEIN Mock."""
    from app.config import Settings
    from services.notification_service import NotificationService
    from utils.timezone import local_fmt, tz_for_coords

    user_id = f"tdd-1172-ac2-{uuid.uuid4().hex[:8]}"
    _write_test_profile(user_id)
    settings = Settings().with_user_profile(user_id)
    if not settings.can_send_email():
        _cleanup_test_user(user_id)
        pytest.skip("SMTP (GZ_TEST_SMTP_*) nicht konfiguriert")

    try:
        marker = uuid.uuid4().hex[:8]
        trip = _corsica_trip(f"tdd-1172-ac2-trip-{marker}", marker)

        vf = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
        vt = datetime(2026, 7, 12, 20, 0, tzinfo=timezone.utc)
        # Issue #1200: notices sind (OfficialAlert, segment_ids)-Tupel.
        notices = [(OfficialAlert(
            source="meteo-france", hazard="heat", level=3, label="Hitze",
            valid_from=vf, valid_to=vt, region_label="Haute-Corse",
            url="https://example.invalid/vigilance",
        ), ["1"])]

        # Erwartete lokale Zeitpunkte exakt wie der Sendepfad: tz aus den
        # Wegpunkt-Koordinaten (send_official_alert -> tz_for_coords(first_wp)).
        alert_tz = tz_for_coords(_CORSICA_LAT, _CORSICA_LON)
        vf_local = local_fmt(vf, alert_tz)
        vt_local = local_fmt(vt, alert_tz)

        ns = NotificationService(settings, user_id)
        result = ns.send_official_alert(
            trip=trip, notices=notices, effective_channels={"email"},
        )
        assert result.sent, "send_official_alert() meldet keinen Versand"

        subject, body = _poll_imap_for_marker(settings, marker)
        assert subject is not None, f"Keine Mail mit Marker {marker} in 60s zugestellt"
        assert "ORANGE" in body, f"AC-2: Schwere-Wort 'ORANGE' fehlt im Body:\n{body}"
        assert "Haute-Corse" in body, f"AC-2: Region fehlt im Body:\n{body}"
        assert vf_local in body and vt_local in body, (
            f"AC-2: Gueltigkeitszeitraum ({vf_local}–{vt_local}, lokal) fehlt im "
            f"zugestellten Body:\n{body}"
        )
    finally:
        _cleanup_test_user(user_id)
