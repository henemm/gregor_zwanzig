"""TDD RED — Issue #952 (reopened) AC-9: echte E2E-Verifikation Onset-Alert.

Fake-Radar-Seam (`radar_service=` DI, kein Mock) treibt `check_radar_alerts()`
gegen die echte SMTP/IMAP-Kette (Stalwart-Testpostfach `gregor-test@henemm.com`)
und — separat — gegen den echten Staging-Telegram-Bot.

Rot vor Fix: heutige Ad-hoc-HTML-Struktur (kein "Radar-Nowcast"-Badge), Float-km
im Body, dupliziertes Intensitäts-Satzformat sind im zugestellten Mail-Body
nachweisbar UND widersprechen den neuen Assertions. Grün nach Fix: Vorlagen-
Struktur/gerundete km/kurzes Intensitäts-Label sind im echten Mail-Body
nachweisbar.

Telegram-Teil separat begründet: `check_radar_alerts()` hat (anders als
`_mail_sink`) KEINEN Seam, der die gesendete `message_id` für Cleanup nach
aussen reicht — ein voller Live-Dispatch+Cleanup wie `test_ac4_live_delivery_
and_cleanup` (#686) würde ungelöschten Chat-Müll im Staging-Bot hinterlassen.
Stattdessen wird der kanonische Onset-Renderer-Output real über
`TelegramOutput.send(parse_mode="HTML", suppress_subject_line=True)` an den
Staging-Bot gesendet (derselbe Codepfad, den `check_radar_alerts` nach dieser
Spec intern nutzen wird) und per `delete_message()` sofort wieder entfernt —
echte Zustellung, kein Müll.

Skip nur bei fehlender Infrastruktur (SMTP/IMAP bzw. Telegram-Live-Creds nicht
konfiguriert) — niemals stiller Erfolg.

SPEC: docs/specs/modules/issue_952_onset_alert_fidelity.md
"""
from __future__ import annotations

import email
import imaplib
import logging
import os
import re
import time
import uuid
from datetime import date as date_type
from pathlib import Path

import pytest

from app.config import Settings
from app.models import TripReportConfig
from services.radar_service import NowcastResult

from tests.tdd.test_952_onset_alert_fidelity import (
    _GuaranteedWetRadar, _trip_with_active_segment,
)

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

logger = logging.getLogger("trip_alert")


def _clean_user(uid: str) -> None:
    import shutil
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _test_settings() -> Settings | None:
    """Vorbild test_773_alert_e2e._test_settings."""
    s = Settings().for_testing()
    if not s.can_send_email():
        return None
    return s.model_copy(update={
        "mail_to": "gregor-test@henemm.com",
        "telegram_bot_token": "", "telegram_chat_id": "",
    })


def _imap_has_subject_token(settings: Settings, token: str, *, attempts: int = 24,
                             delay: float = 5.0) -> str | None:
    """Poll das Stalwart-Testpostfach; liefert den Plain-Text-Body der Mail
    mit `token` im Betreff zurück (oder None). Vorbild test_773.

    attempts×delay = 120s: das geteilte Testpostfach (aktuell >5500 Mails,
    Issue #952-Messung) zeigt unter Last spürbar höhere SMTP→IMAP-Latenz als
    test_773s 36s-Default — knapp bemessen führte zu False-Rot trotz
    tatsächlich zugestellter Mail (mit attempts=1 sofort auffindbar, sobald
    sie eingetroffen war).
    """
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    for _ in range(attempts):
        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
        try:
            imap.login(imap_user, imap_pass)
            imap.select("INBOX")
            _, data = imap.search(None, f'SUBJECT "{token}"')
            ids = data[0].split() if data and data[0] else []
            if not ids:
                _, recent = imap.search(None, "ALL")
                ids = recent[0].split()[-20:] if recent and recent[0] else []
            for i in reversed(ids):
                _, md = imap.fetch(i, "(RFC822)")
                if not md or not md[0]:
                    continue
                raw = md[0][1]
                msg = email.message_from_bytes(raw)
                subj_hdr = str(email.header.make_header(
                    email.header.decode_header(msg.get("Subject", "")),
                ))
                if token not in subj_hdr:
                    continue
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            return part.get_payload(decode=True).decode(
                                part.get_content_charset() or "utf-8", errors="replace",
                            )
                else:
                    return msg.get_payload(decode=True).decode(
                        msg.get_content_charset() or "utf-8", errors="replace",
                    )
        finally:
            try:
                imap.logout()
            except Exception:
                pass
        time.sleep(delay)
    return None


# ===========================================================================
# AC-9 (Mail-Teil): echte Zustellung + IMAP-Nachweis der Vorlagen-Struktur
# ===========================================================================


def test_ac9_onset_alert_real_email_delivery_shows_template_structure(caplog):
    """AC-9: Fake-Radar-Seam → check_radar_alerts() → echte Mail an
    gregor-test@henemm.com. IMAP-Beweis: Badge-Text, Datenblock-Struktur,
    gerundete km, kurzes Intensitäts-Label — kein Mock, kein Gmail."""
    settings = _test_settings()
    if settings is None:
        pytest.skip("SMTP nicht konfiguriert — realer E-Mail-E2E nicht möglich")

    from services.trip_alert import TripAlertService

    uid = "tdd-952-e2e"
    token = uuid.uuid4().hex[:8]
    trip_id = f"trip-952-e2e-{token}"
    _clean_user(uid)
    try:
        config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            send_sms=False, alert_on_changes=True,
        )
        trip = _trip_with_active_segment(trip_id, config)
        trip.name = f"E2E952 {token}"
        from app.loader import save_trip
        save_trip(trip, user_id=uid)

        service = TripAlertService(
            settings=settings, throttle_hours=0, user_id=uid,
            radar_service=_GuaranteedWetRadar(
                onset_minutes=12, intensity_label="leichter Regen",
                is_convective=False,
            ),
        )

        with caplog.at_level(logging.ERROR, logger="trip_alert"):
            sent = service.check_radar_alerts()
        assert sent == 1, (
            f"check_radar_alerts() hat keinen Alert versendet (sent={sent}) — "
            "Fake-Radar-Seam oder Trip-Fixture liefert kein fälliges Onset-Ereignis."
        )

        if "rate limit" in caplog.text.lower() or "452" in caplog.text:
            pytest.skip("SMTP-Relay rate-limited (452) — transiente Infra, Pfad erreicht")

        body = _imap_has_subject_token(settings, token)
        assert body is not None, (
            f"Alert-Mail mit Token {token} nicht im Test-Postfach gefunden — "
            "keine echte Zustellung."
        )

        assert "Radar-Nowcast" in body, f"Badge-Text fehlt im echten Mail-Body: {body!r}"
        for label in ("Wo & wann", "Intensität", "Quelle"):
            assert label in body, f"Datenblock-Zeile {label!r} fehlt: {body!r}"

        intensity_line = next(
            (l for l in body.splitlines() if l.startswith("Intensität")), None,
        )
        assert intensity_line == "Intensität: leichter Regen", (
            f"Intensitäts-Zeile nicht exakt 'leichter Regen' — alte Duplikat-Struktur "
            f"noch vorhanden: {intensity_line!r}"
        )
        assert "ab ca." not in body, f"Alter Satzbau noch im echten Mail-Body: {body!r}"
        assert not re.search(r"km \d+\.\d", body), (
            f"Float-Rauschen (unrunde km) im echten Mail-Body: {body!r}"
        )
    finally:
        _clean_user(uid)


# ===========================================================================
# AC-9 (Telegram-Teil): echte Zustellung an den Staging-Bot + Cleanup
# ===========================================================================


@pytest.mark.skipif(
    not (os.environ.get("GZ_TELEGRAM_BOT_TOKEN") and os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID")),
    reason="GZ_TELEGRAM_BOT_TOKEN + GZ_TELEGRAM_TEST_CHAT_ID nicht gesetzt — "
           "Telegram-Live-Zustellung übersprungen",
)
def test_ac9_onset_alert_real_telegram_delivery_bold_no_subject_duplicate():
    """AC-9 (Telegram): kanonischer Onset-Renderer-Output real an den
    Staging-Bot gesendet — fette erste Zeile (<b>) sichtbar, kein
    '[Betreff]'-Duplikat. Sofortiger Cleanup via delete_message()."""
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    from output.renderers.alert.render import render_subject, render_telegram
    from outputs.telegram import TelegramOutput

    onset = OnsetEvent(
        onset_minutes=12, onset_time="14:35", km_from=5.0, km_to=18.0,
        is_convective=False, intensity_label="leichter Regen",
        source_label="Radar (DWD)",
    )
    msg = AlertMessage(
        trip_short="E2E952", stand_at="14:23", events=(onset,),
        source="Radar (DWD)", cooldown_display="2 Stunden",
    )
    subject = render_subject(msg)
    body = render_telegram(msg)

    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]
    settings = Settings(
        telegram_bot_token=os.environ["GZ_TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=chat_id,
    )
    output = TelegramOutput(settings)

    # RED vor Fix: send() kennt parse_mode/suppress_subject_line nicht -> TypeError.
    message_id = output.send(
        subject, body, parse_mode="HTML", suppress_subject_line=True,
    )
    try:
        assert message_id is not None, "Telegram-Zustellung fehlgeschlagen (keine message_id)"
        assert "<b>" in body and "</b>" in body, f"Kein <b>-Tag im Onset-Telegram: {body!r}"
        assert "**" not in body, f"Noch '**'-Markdown im Onset-Telegram: {body!r}"
        assert f"[{subject}]" not in body, f"Betreff-Duplikat im Telegram-Body: {body!r}"
    finally:
        deleted = output.delete_message(chat_id, message_id) if message_id else False
        assert deleted or message_id is None, "Cleanup (deleteMessage) fehlgeschlagen — Chat-Müll"
