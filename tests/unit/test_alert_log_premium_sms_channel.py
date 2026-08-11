"""RED — Issue #1701 (#1676 Scheibe S2b): Premium-SMS im Alarm-Protokoll.

Spec: docs/specs/modules/feat_1701_alarm_premium_sms.md
Abgedeckt: AC-9, plus die ``_ALL_CHANNELS``-Erweiterung (Test Coverage:
"kein stilles Loch").

TESTPOLITIK (CLAUDE.md "Test-Politik: Zwei Schichten", Kern-Schicht): kein
Mock-Theater, kein Mock des Protokolls selbst -- ``append_entry()`` wird
direkt aufgerufen (echter Baustein, geteilt von allen sechs Aufrufstellen)
und ``alert_log.json`` danach als echte Datei gelesen (Vorbild
``tests/helpers/alert_log_fixtures.py::read_log``).

Pfadregel #1409: ``get_data_dir()`` respektiert die pytest-isolierte
Datenwurzel (#1133) -- kein fester Hauptrepo-Pfad.
"""
from __future__ import annotations

import json
import uuid

from services import alert_log


def _uid(prefix: str) -> str:
    return f"tdd-1701-log-{prefix}-{uuid.uuid4().hex[:6]}"


def _read_log(user_id: str) -> dict:
    from app.loader import get_data_dir

    path = get_data_dir(user_id) / "alert_log.json"
    if not path.exists():
        return {"entries": [], "not_delivered": []}
    data = json.loads(path.read_text())
    data.setdefault("entries", [])
    data.setdefault("not_delivered", [])
    return data


def _not_sent(entry: dict, channel: str) -> dict | None:
    for item in entry.get("channels_not_sent") or []:
        if isinstance(item, dict) and item.get("channel") == channel:
            return item
    return None


# ═══════════════════════════════ AC-9 ═════════════════════════════════════

def test_blocked_premium_sms_reason_is_specific_not_generic():
    """AC-9: Given eine Alarm-Meldung sollte per Premium-SMS gehen, aber die
    gelernte Rueckadresse ist leer oder veraltet / When der Alarm-Lauf
    abgeschlossen ist / Then zeigt ``alert_log.json`` den Kanal
    ``premium_sms`` unter ``channels_not_sent`` mit dem SPEZIFISCHEN Grund
    (``premium_sms_no_reply_address``) -- nicht mit dem generischen
    ``delivery_failed`` und nicht als spurloses Fehlen.

    ROT-Grund (gemessen): ``append_entry()`` kennt den Parameter
    ``blocked_reason_codes`` heute nicht (``alert_log.py:135-149``) -- der
    Aufruf unten scheitert mit ``TypeError: unexpected keyword argument``.
    Selbst wenn der Parameter existierte: ``_channels_not_sent()`` iteriert
    nur ``_ALL_CHANNELS = ("email", "telegram", "sms")`` -- "premium_sms"
    kann in ``channels_not_sent`` heute UEBERHAUPT NICHT erscheinen (stilles
    Loch, D5).
    """
    uid = _uid("ac9")
    alert_log.append_entry(
        uid, entity_id="trip-ac9", entity_type="trip",
        changes_count=1, severity="MODERATE",
        reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels={"email", "premium_sms"},
        sent_channels=["email"],
        reachable_channels=["email"],
        blocked_reason_codes={"premium_sms": "premium_sms_no_reply_address"},
    )

    log = _read_log(uid)
    assert len(log["entries"]) == 1, (
        f"Voraussetzung: genau EIN Protokolleintrag erwartet, gefunden: {log!r}"
    )
    entry = log["entries"][0]
    item = _not_sent(entry, "premium_sms")
    assert item is not None, (
        "AC-9: 'premium_sms' fehlt komplett unter 'channels_not_sent' -- "
        f"stilles Loch statt eines auswertbaren Grundes: {entry!r}"
    )
    assert item.get("reason") == "premium_sms_no_reply_address", (
        "AC-9: der Grund muss die SPEZIFISCHE Kennung tragen, nicht den "
        f"generischen Sammelbegriff. Gefunden: {item.get('reason')!r}"
    )
    assert item.get("reason") != alert_log.REASON_DELIVERY_FAILED, (
        f"AC-9: der generische Grund {alert_log.REASON_DELIVERY_FAILED!r} "
        "verdeckt die eigentliche Ursache (fehlende Rueckadresse) -- genau "
        "die Ununterscheidbarkeit, die D5 beseitigen soll."
    )


def test_email_reason_stays_generic_when_no_blocked_reason_code_given():
    """AC-9 Gegenprobe: Given ein E-Mail-Versand scheitert OHNE
    ``blocked_reason_codes``-Eintrag (Bestandsverhalten, Invariante der
    Spec) / When der Alarm-Lauf abgeschlossen ist / Then bleibt der Grund
    fuer E-Mail unveraendert der generische ``delivery_failed`` -- die neue
    Vorrangregel (D5) darf nur GEFUELLTE Eintraege ersetzen, nie Kanaele
    ohne eigene Kennung."""
    uid = _uid("ac9-invariant")
    alert_log.append_entry(
        uid, entity_id="trip-ac9-inv", entity_type="trip",
        changes_count=1, severity="MODERATE",
        reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels={"email", "premium_sms"},
        sent_channels=[],
        reachable_channels=[],
        blocked_reason_codes={"premium_sms": "premium_sms_no_reply_address"},
    )

    log = _read_log(uid)
    entry = log["entries"][0] if log["entries"] else log["not_delivered"][0]
    email_item = _not_sent(entry, "email")
    assert email_item is not None, f"'email' fehlt unter 'channels_not_sent': {entry!r}"
    assert email_item.get("reason") == alert_log.REASON_DELIVERY_FAILED, (
        "Invariante verletzt: ein Kanal OHNE eigenen blocked_reason_codes-"
        f"Eintrag muss beim generischen Grund bleiben, gefunden: "
        f"{email_item.get('reason')!r}"
    )


# ══════════════ _ALL_CHANNELS-Erweiterung (Test Coverage, kein Mock) ═══════

def test_premium_sms_missing_delivery_appears_in_protocol_no_silent_hole():
    """Given Premium-SMS ist im effektiven Kanal-Set enthalten UND wurde
    NICHT zugestellt (kein ``blocked_reason_codes``-Eintrag, z.B. ein
    technischer Transportfehler) / When der Protokoll-Eintrag geschrieben
    wird / Then erscheint 'premium_sms' TROTZDEM unter 'channels_not_sent'
    (generischer Grund) -- statt spurlos zu fehlen.

    ROT-Grund (gemessen): ``_ALL_CHANNELS = ("email", "telegram", "sms")``
    (``alert_log.py:59``) -- ``_channels_not_sent()`` iteriert nur diese drei
    Namen, ein vierter Kanal kann im Ergebnis strukturell nicht auftauchen,
    unabhaengig davon was uebergeben wird.
    """
    uid = _uid("all-channels")
    alert_log.append_entry(
        uid, entity_id="trip-all-channels", entity_type="trip",
        changes_count=1, severity="MODERATE",
        reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels={"premium_sms"},
        sent_channels=[],
        reachable_channels=[],
    )

    log = _read_log(uid)
    assert log["entries"] == [], (
        "Voraussetzung: kein erreichbarer Kanal -> Eintrag landet unter "
        f"'not_delivered', gefunden unter 'entries': {log['entries']!r}"
    )
    assert len(log["not_delivered"]) == 1, (
        f"Voraussetzung: genau EIN Eintrag unter 'not_delivered', gefunden: {log!r}"
    )
    entry = log["not_delivered"][0]
    item = _not_sent(entry, "premium_sms")
    assert item is not None, (
        "'premium_sms' fehlt komplett unter 'channels_not_sent' -- stilles "
        f"Loch statt eines Protokoll-Eintrags: {entry!r}"
    )
    assert item.get("reason") == alert_log.REASON_DELIVERY_FAILED, (
        f"Ohne eigene Kennung muss der generische Grund stehen, gefunden: "
        f"{item.get('reason')!r}"
    )
