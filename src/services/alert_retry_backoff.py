"""Fehlversuchs-Backoff fuer Alarme (Issue #1405 S1, ADR-0086).

Geteilter Baustein fuer ALLE Alarm-Aufrufer (Trip und Ortsvergleich): ein
Alarm, der auf keinem Kanal zugestellt wurde (`transport_failed`), wird NICHT
als erledigt gebucht, sondern hoechstens einmal je 30 Minuten je Ereignis
erneut versucht. Zustand im bestehenden, nutzerbezogenen ``ThrottleStore``
unter dem Scope ``<scope>:retry``, Schluessel = Ereignis-Fingerabdruck.

Bewusst KEIN Versuchsdeckel (Zaehler, s. #1662): die Wiederholung endet, wenn
das Ereignis entfaellt oder ein Kanal zustellt (Restrisiko in ADR-0086).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from services.throttle_store import ThrottleStore

logger = logging.getLogger("alert_retry_backoff")

RETRY_BACKOFF_MINUTES = 30

DELIVERED = "delivered"
TRANSPORT_FAILED = "transport_failed"
BLOCKED_ONLY = "blocked_only"
NO_CHANNEL = "no_channel"

#: Ausgaenge, nach denen der Alarm als erledigt gebucht wird (terminal).
BOOKING_OUTCOMES = (DELIVERED, BLOCKED_ONLY)


def retry_scope(scope: str) -> str:
    return f"{scope}:retry"


def event_fingerprint(entity_id: str, parts: Iterable[str]) -> str:
    """Entitaet + sortierte, eindeutige Ereignis-Bestandteile."""
    return "|".join([entity_id, *sorted({str(p) for p in parts})])


def official_alert_parts(alerts: Iterable) -> list[str]:
    """Meldungs-Kennungen amtlicher Warnungen fuer den Fingerabdruck:
    Gefahrenart + stabile Identitaet (``dedup_id`` > ``region_label`` >
    ``label``) -- bewusst OHNE Gueltigkeitszeiten, die sich je Abruf
    verschieben koennen."""
    return [
        f"{a.hazard}:{a.dedup_id or a.region_label or a.label}" for a in alerts
    ]


def backoff_active(
    store: ThrottleStore, scope: str, fingerprint: str,
    now: Optional[datetime] = None,
) -> bool:
    """Laeuft fuer dieses Ereignis ein Fehlversuchs-Backoff? Dann kein
    Versand und kein Protokolleintrag (AC-11/AC-18)."""
    now = now or datetime.now(timezone.utc)
    active = store.is_throttled(
        retry_scope(scope), fingerprint, RETRY_BACKOFF_MINUTES, now,
    )
    if active:
        logger.info(
            "Alarm-Wiederholung: Backoff laeuft fuer %s (%s) -- kein Versuch",
            fingerprint, scope,
        )
    return active


def settle(
    store: ThrottleStore, scope: str, fingerprint: str, outcome: str,
    now: Optional[datetime] = None,
) -> bool:
    """Nachbehandlung nach dem Versand; ``True`` = Aufrufer bucht wie bisher.

    ``transport_failed`` setzt den Backoff (keine Buchung); ``delivered`` und
    ``blocked_only`` loeschen einen evtl. vorhandenen Backoff und buchen;
    ``no_channel`` bleibt unveraendert (keine Buchung, kein Backoff)."""
    now = now or datetime.now(timezone.utc)
    if outcome == TRANSPORT_FAILED:
        store.record(retry_scope(scope), fingerprint, now)
        logger.warning(
            "Alarm nicht zugestellt (%s, %s) -- naechster Versuch fruehestens "
            "in %d Minuten", fingerprint, scope, RETRY_BACKOFF_MINUTES,
        )
        return False
    if outcome in BOOKING_OUTCOMES:
        if store.last_sent(retry_scope(scope), fingerprint) is not None:
            store.clear(retry_scope(scope), fingerprint)
        return True
    return False


# ─────────────── Nowcast: toleranzbasierter Ereignis-Abgleich ───────────────
# Ein Nowcast-Ereignis traegt keine stabile Kennung, und seine Startzeit kann
# zwischen zwei Laeufen leicht wandern. Schluessel = Entitaet (bzw. Ort) +
# Klasse + ABSOLUTER Beginn (Epoch-Minute, "laufend" als eigener Wert). Zwei
# Startzeiten derselben Klasse, die hoechstens 30 Min auseinanderliegen,
# gelten als dasselbe Ereignis (Spec Known Limitations).

_LAUFEND = "laufend"


def nowcast_key(entity_id: str, is_convective: bool, onset_at: Optional[datetime]) -> str:
    klasse = "konvektiv" if is_convective else "nass"
    # Absoluter Beginn als Epoch-Minute (zonenunabhaengig).
    beginn = _LAUFEND if onset_at is None else str(int(onset_at.timestamp() // 60))
    return f"{entity_id}|{klasse}|{beginn}"


def _same_nowcast_event(a: str, b: str) -> bool:
    ea, ka, ba = a.rsplit("|", 2)
    eb, kb, bb = b.rsplit("|", 2)
    if (ea, ka) != (eb, kb):
        return False
    if _LAUFEND in (ba, bb):
        return ba == bb
    return abs(int(ba) - int(bb)) <= RETRY_BACKOFF_MINUTES


def _nowcast_entries(store: ThrottleStore, scope: str) -> list[str]:
    return [k for k in store.keys(retry_scope(scope)) if k.count("|") >= 2]


def nowcast_backoff_active(
    store: ThrottleStore, scope: str, keys: list[str], now: Optional[datetime] = None,
) -> bool:
    """Backoff aktiv, wenn JEDES Ereignis des Laufs (je Ort) einen nicht
    abgelaufenen Fehlversuch in der Toleranz hat -- ein neues Ereignis
    (anderer Ort, andere Klasse, Beginn > 30 Min entfernt) wird versendet."""
    now = now or datetime.now(timezone.utc)
    bestand = _nowcast_entries(store, scope)
    active = bool(keys) and all(
        any(
            _same_nowcast_event(k, alt)
            and store.is_throttled(retry_scope(scope), alt, RETRY_BACKOFF_MINUTES, now)
            for alt in bestand
        )
        for k in keys
    )
    if active:
        logger.info("Alarm-Wiederholung: Backoff laeuft fuer %s (%s)", keys, scope)
    return active


def settle_nowcast(
    store: ThrottleStore, scope: str, keys: list[str], outcome: str,
    now: Optional[datetime] = None,
) -> bool:
    """Wie `settle`, je Ereignis-Schluessel. Bei Buchung werden alle passenden
    (Toleranz) und alle abgelaufenen Eintraege derselben Entitaeten geloescht."""
    now = now or datetime.now(timezone.utc)
    if outcome == TRANSPORT_FAILED:
        for k in keys:
            settle(store, scope, k, outcome, now)
        return False
    if outcome not in BOOKING_OUTCOMES:
        return False
    entitaeten = {k.rsplit("|", 2)[0] for k in keys}
    for alt in _nowcast_entries(store, scope):
        passend = any(_same_nowcast_event(k, alt) for k in keys)
        abgelaufen = alt.rsplit("|", 2)[0] in entitaeten and not store.is_throttled(
            retry_scope(scope), alt, RETRY_BACKOFF_MINUTES, now,
        )
        if passend or abgelaufen:
            store.clear(retry_scope(scope), alt)
    return True
