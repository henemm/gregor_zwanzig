"""Kompakt-Mail- und Telegram-Ausblick am ECHTEN Versandpfad (#1720 S2).

SPEC: docs/specs/modules/feat_1720_s2_ausblick_kompakt_telegram.md

Warum neben ``trip_outlook_selection`` (S1): jener treibt
``TripReportFormatter.format_email()`` und liest HTML/Klartext. Kompakt-Mail
und Telegram-Bubbles entstehen erst im Versand
(``_send_trip_report_outcome()`` -> ``NotificationService`` ->
``EmailOutput``/``TelegramOutput``); der Kompakt-Zweig
(``email/__init__.py:111``) und die Ausblick-Bubble (``narrow.py:832``)
werden auf dem S1-Weg nie erreicht -- der Befund, der die Testplanung
bestimmt (Spec).

Kein Mock-Framework: echte Unterklassen + Attribut-Rebind, in ``finally``
restauriert (Muster ``test_trip_outlook_dispatch_mail.py:200-212``).

Versand-Sicherheit (#1477): alle Transport-Felder ausdruecklich gesetzt,
Bot-Token/Chat-Id sind Dummy-Zeichenketten UND beide Transporte werden vor
dem Lauf durch aufzeichnende Unterklassen ersetzt -- es verlaesst nichts den
Prozess. SMS/Premium-SMS bleiben unkonfiguriert und abgeschaltet.
"""
from __future__ import annotations

import re
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Pfadregel #1409: Pruefling relativ zur eigenen Datei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

# Bewusst DIESELBE Fixture-Unterklasse wie S1 statt einer zweiten Kopie: liefen
# beide auseinander, verglichen Bestandsschutz (S1, HTML/Klartext) und diese
# Scheibe (Kompakt/Telegram) zwei verschiedene Welten.
from tests.helpers.trip_outlook_selection import (  # noqa: E402
    REFERENCE_DIR, mit_outlook_metric_formats, mit_outlook_metrics,
    utc_process_tz,
)
from tests.tdd.test_trip_outlook_dispatch_mail import (  # noqa: E402
    _fixture_scheduler_klasse,
)

REFERENCE_COMPACT = REFERENCE_DIR / "compact_block.txt"
REFERENCE_TELEGRAM = REFERENCE_DIR / "telegram_bubble.txt"

LAT, LON = 46.65, 12.85
COMPACT_OUTLOOK_HEADING = "Naechste Etappen"
TELEGRAM_OUTLOOK_HEADING = "Ausblick"

# #1848 A2: Auswahl-Bausteine sind reine Kennungen (vorher Paare, #1373).
NIEDERSCHLAG = "precipitation"
BOEEN = "gust"

_MAIL_FIELDS: dict = {
    "smtp_host": "dummy.invalid", "smtp_port": 587,
    "smtp_user": "dummy-1720", "smtp_pass": "dummy-1720",
    "mail_to": "gregor-test@henemm.com",
    "telegram_bot_token": "000000:dummy-1720-s2",
    "telegram_chat_id": "-100000000",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
    "_env_file": None,
}

# Der Wochentag ist der einzige kalenderabhaengige Bestandteil des Blocks. Er
# wird auf BEIDEN Seiten des Referenzvergleichs maskiert (laengengleich: alle
# deutschen Kuerzel sind zweistellig), alles uebrige bleibt byte-genau.
_WEEKDAY_RE = re.compile(r"^(Mo|Di|Mi|Do|Fr|Sa|So)\b", re.MULTILINE)


def maskiere_wochentage(text: str) -> str:
    return _WEEKDAY_RE.sub("XX", text)


def _settings(user_id: str):
    from app.config import Settings

    settings = Settings(**_MAIL_FIELDS).with_user_profile(user_id)
    assert settings.can_send_email() is True, "Vorbedingung: E-Mail sendefaehig."
    assert settings.can_send_telegram() is True, (
        "Vorbedingung: Telegram muss sendefaehig sein, sonst entsteht gar "
        "keine Bubble (der Transport selbst ist ersetzt)."
    )
    assert settings.can_send_sms() is False, "Sicherung (#1477): kein SMS."
    return settings


def trip(*, outlook_metrics, enabled_ids=None, telegram_layout_ids=None,
         stage_count: int = 5, email_format: str = "compact",
         outlook_metric_formats=None):
    """Tour ab heute: der Abendbericht zielt auf MORGEN, der Ausblick zeigt
    die drei Etappen danach.

    ``stage_count=2`` laesst die Tour mit dem Zieltag enden -- dann liefert
    ``_build_stage_trend()`` ``rows=None``/``state=NO_STAGES``, also den
    Zustands-Fallback-Zweig (AC-4, zweiter Fall).
    ``telegram_layout_ids`` setzt ``per_channel_layouts["telegram"]`` (AC-5).
    ``outlook_metric_formats`` (#2049): Roh/Einfach-Zuordnung je Ausblick-
    Groesse, ``{metric_id: bool}``, ``True`` = Einfach.
    """
    from app.metric_catalog import build_default_display_config
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    trip_id = f"trip-1720s2-{uuid.uuid4().hex[:8]}"
    heute = date.today()
    stages = [
        Stage(id=f"S{i}", name=f"Tag {i}", date=heute + timedelta(days=i),
              waypoints=[
                  Waypoint(id=f"W{i}a", name="Start", lat=LAT, lon=LON,
                           elevation_m=1400.0, arrival_calculated="08:00"),
                  Waypoint(id=f"W{i}b", name="Ziel", lat=LAT + 0.05,
                           lon=LON + 0.1, elevation_m=2100.0,
                           arrival_calculated="12:00"),
              ])
        for i in range(stage_count)
    ]
    dc = build_default_display_config()
    dc.trip_id = trip_id
    dc.show_night_block = False          # haelt echte Nacht-Abrufe fern
    if enabled_ids is not None:
        for mc in dc.metrics:
            mc.enabled = mc.metric_id in enabled_ids
    if telegram_layout_ids is not None:
        dc.per_channel_layouts = {
            "telegram": [mc for mc in dc.metrics
                         if mc.metric_id in telegram_layout_ids],
        }
    if outlook_metrics is not None:
        dc = mit_outlook_metrics(dc, outlook_metrics)
    if outlook_metric_formats is not None:
        dc = mit_outlook_metric_formats(dc, outlook_metric_formats)

    t = Trip(id=trip_id, name="Karnischer Höhenweg", stages=stages,
             display_config=dc, official_warnings=None)
    t.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, send_sms=False,
        send_premium_sms=False, show_outlook=True,
        multi_day_trend_reports=["evening"], email_format=email_format,
    )
    t.official_alerts_enabled = False
    t.official_alert_triggers_enabled = False
    t.alert_cooldown_minutes = 0
    return t


def versendete_teile(t, *, report_type: str = "evening") -> tuple[str, list[str]]:
    """Treibt den echten Versandlauf und liefert (Kompakt-Mailkoerper,
    Telegram-Bubble-Texte) genau so, wie die Transporte sie bekommen."""
    import services.notification_service as ns_mod

    user_id = f"tdd-1720s2-{uuid.uuid4().hex[:8]}"
    mails: list[dict] = []
    bubbles: list[str] = []
    orig_mail, orig_tg = ns_mod.EmailOutput, ns_mod.TelegramOutput

    class _RecordingEmailOutput(orig_mail):     # echte Subklasse, kein Mock
        def send(self, subject, body, **kwargs):
            mails.append({"subject": subject, "body": body, **kwargs})
            return None

    class _RecordingTelegramOutput(orig_tg):    # echte Subklasse, kein Mock
        def send(self, subject, body, **kwargs):
            bubbles.append(body)
            return None

    ns_mod.EmailOutput = _RecordingEmailOutput
    ns_mod.TelegramOutput = _RecordingTelegramOutput
    try:
        with utc_process_tz():
            scheduler = _fixture_scheduler_klasse()(
                settings=_settings(user_id), user_id=user_id)
            ergebnis = scheduler._send_trip_report_outcome(
                t, report_type, on_demand=True)
    finally:
        ns_mod.EmailOutput = orig_mail
        ns_mod.TelegramOutput = orig_tg

    assert ergebnis == "sent", (
        f"Der Versandlauf endete mit {ergebnis!r} statt 'sent' -- ohne "
        "erfolgten Versand prueft dieser Test nichts."
    )
    assert mails, "Es wurde keine E-Mail versendet."
    assert bubbles, "Es wurde keine Telegram-Bubble versendet."
    return mails[0]["body"], bubbles


def compact_outlook_block(body: str) -> Optional[str]:
    """Ausblick-Block der Kompakt-Mail (Ueberschrift + Zeilen) oder ``None``."""
    zeilen = body.splitlines()
    try:
        start = zeilen.index(COMPACT_OUTLOOK_HEADING)
    except ValueError:
        return None
    block = [zeilen[start]]
    for zeile in zeilen[start + 1:]:
        if zeile.strip() == "":
            break
        block.append(zeile)
    return "\n".join(block)


def telegram_outlook_bubble(bubbles: list[str]) -> Optional[str]:
    """Die Ausblick-Bubble (erste Zeile ``Ausblick``) oder ``None``."""
    for text in bubbles:
        if text.splitlines()[:1] == [TELEGRAM_OUTLOOK_HEADING]:
            return text
    return None


def record_reference(force: bool = False) -> list[Path]:
    """Zeichnet die AC-1-Referenz aus dem AKTUELLEN Code auf. Ohne ``force``
    wird eine vorhandene Aufzeichnung NICHT ueberschrieben: eine Referenz, die
    man bei rotem Test neu erzeugen kann, bewacht nichts."""
    body, bubbles = versendete_teile(trip(outlook_metrics=None))
    inhalte = {
        REFERENCE_COMPACT: compact_outlook_block(body),
        REFERENCE_TELEGRAM: telegram_outlook_bubble(bubbles),
    }
    fehlend = [p.name for p, t in inhalte.items() if not t]
    if fehlend:
        raise RuntimeError(f"Kein Ausblick gerendert fuer: {fehlend} -- "
                           "die Aufzeichnung waere leer und wertlos.")
    geschrieben = []
    for pfad, text in inhalte.items():
        if pfad.exists() and not force:
            continue
        pfad.write_text(maskiere_wochentage(text), encoding="utf-8")
        geschrieben.append(pfad)
    return geschrieben


if __name__ == "__main__":  # pragma: no cover - Aufzeichnungs-Werkzeug
    for pfad in record_reference(force="--force" in sys.argv):
        print(f"aufgezeichnet: {pfad}")
