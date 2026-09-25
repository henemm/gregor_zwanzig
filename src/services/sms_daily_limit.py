"""SMS-/Premium-SMS-Tageslimit je Nutzer (Issue #2412, Scheibe S4a, Epic #2138).

Deckelt den taeglichen Versand ueber die Kanaele SMS und Premium-SMS je
Nutzer, damit ein einzelnes Nutzerkonto keine unbegrenzten Versandkosten
verursacht. Briefing- und Alarm-SMS werden je Kanal in EINEM Zaehler
zusammengezaehlt, mit einer festen Reserve fuer Alarme (die Empfangslage
unterwegs ist unvorhersehbar -- jeder Kanal muss jede Frage beantworten
koennen, CLAUDE.md PO-Korrektur 2026-09-05).

SPEC: docs/specs/modules/sms_daily_limit.md (AC-1..AC-10)

Muster (Sidecar-Lock + atomares tempfile/os.replace-Schreiben, Fail-Open bei
Lock-Timeout): `src/services/throttle_store.py`, `src/services/forecast_budget.py`.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from app.loader import get_data_dir
from output.channels.base import ChannelBlockedError
from services import user_tier
from services.file_lock import LOCK_TIMEOUT_SECONDS, acquire_exclusive
from utils.timezone import to_utc

logger = logging.getLogger("sms_daily_limit")

_FILENAME = "sms_daily_count.json"
_LOCK_SUFFIX = ".lock"
REASON_CODE = "sms_daily_limit_exceeded"


def _path(user_id: str) -> Path:
    return get_data_dir(user_id) / _FILENAME


def _today(now: datetime) -> str:
    """Issue #2412 S4a Nachbesserung: `to_utc()` statt rohem
    `.astimezone(timezone.utc)` -- der Zeitzonen-Waechter
    (`tests/test_output_timezone_guard.py`) flaggt den rohen Aufruf als
    `raw_astimezone` (Fix #1727 S5f). Gleiches Ergebnis, gepruefte Form."""
    return to_utc(now).date().isoformat()


def _load(path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        # Adversary F001: `ValueError` deckt `json.JSONDecodeError` UND
        # z.B. `UnicodeDecodeError` ab (beide Unterklassen von `ValueError`)
        # -- jede Art von kaputtem Dateiinhalt gilt als leerer Tagesstand,
        # nie als Wurfquelle.
        return {}


def _zaehlerwert(data: dict, kind: str) -> int:
    """Adversary F001 (CRITICAL): ein fremder/kaputter Wert im Zaehlerfeld
    (z.B. `{"sms": "abc"}`, von aussen manipuliert oder durch einen frueheren
    Bug entstanden) darf das Gate NIE zum Werfen bringen -- gilt als 0
    (leerer Tagesstand), WARNING geloggt, fail-open."""
    raw = data.get(kind, 0)
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError, OverflowError):
        # Adversary F001c (MEDIUM): `OverflowError` faengt z.B. `1e400`
        # (JSON-Float, der als `inf` geparst wird -- `int(inf)` wirft
        # `OverflowError`, nicht `ValueError`).
        logger.warning(
            "SMS-Tageslimit: unlesbarer Zaehlerwert %r fuer %r -- als 0 "
            "behandelt (fail-open)",
            raw, kind,
        )
        return 0


def _tagesstand(data: dict, today: str) -> dict:
    """Fremdes/fehlendes Datum gilt als frischer Nullstand -- EINE Regel fuer
    Schreib- (`check_and_reserve`) und Lesepfad (`get_daily_usage`)."""
    if data.get("date") != today:
        return {"date": today, "sms": 0, "premium_sms": 0}
    return data


def _write(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".sms_daily_count_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data))
        os.replace(tmp_name, path)
    except OSError:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _cap(user_id: str, kind: str, purpose: str) -> int:
    """Obergrenze fuer `kind`/`purpose` nach Tier (Spec: Obergrenzen-Tabelle)."""
    if kind == "sms":
        limit = user_tier.daily_sms_limit(user_id)
        reserve = user_tier.SMS_ALARM_RESERVE
    else:
        limit = user_tier.daily_premium_sms_limit(user_id)
        reserve = user_tier.PREMIUM_SMS_ALARM_RESERVE
    if purpose == "briefing":
        return max(0, limit - reserve)
    if purpose == "reply":
        # Issue #2412 S4a Nachbesserung: die Reply-Zusatzmenge gilt NUR, wenn
        # das Grundlimit > 0 ist (Spec-Tabelle: free/standard Reply-Cap 0,
        # nicht 0+Overshoot) -- Verteidigung in der Tiefe darf einem Tier
        # ohne Premium-SMS-Zugriff nicht durch den Overshoot doch 3 Reply-SMS
        # gewaehren.
        return limit + user_tier.PREMIUM_SMS_REPLY_OVERSHOOT if limit > 0 else 0
    return limit  # purpose == "alert"


def check_and_reserve(user_id: str, kind: str, purpose: str, now: datetime) -> None:
    """Prueft die Tagesobergrenze und reserviert atomar EINE Einheit.

    Wirft `ChannelBlockedError(kind, ..., reason_code=REASON_CODE)`, wenn das
    Kontingent fuer `kind`/`purpose` bereits ausgeschoepft ist -- OHNE zu
    inkrementieren. Sonst wird der Tageswert fuer `kind` um 1 erhoeht
    (Reservierung) und die Zaehlerdatei atomar geschrieben.

    Fail-open bei Lock-Timeout (analog `throttle_store.py`/`forecast_budget.py`):
    eine WARNING wird geloggt, der Versand bleibt ungezaehlt zugelassen.
    Adversary F001 (CRITICAL): dasselbe Fail-Open gilt fuer JEDE weitere
    I/O-Stoerung (Sperrdatei nicht oeffenbar, Schreibfehler beim Persistieren)
    -- das Gate wirft NIE etwas ausser `ChannelBlockedError` bei einer
    tatsaechlichen Sperre.
    """
    try:
        cap = _cap(user_id, kind, purpose)
    except Exception as e:  # noqa: BLE001 — Adversary F009 fail-CLOSED
        # Ein nicht ermittelbarer Tarif ist PROJEKTWEIT fail-closed
        # (Praezedenz `premium_sms_allowed`-Docstring, Issue #1676) --
        # anders als operative Speicherfehler (F007, bewusst
        # fail-open: Sperrdatei/Schreiben) ist eine kaputte/fremde
        # Tarifangabe kein Infrastruktur-, sondern ein
        # Rechte-Problem. Im Zweifel SPERREN (cap=0) wie bei free.
        logger.warning(
            "SMS-Tageslimit: Tier-/Cap-Ermittlung fuer %s fehlgeschlagen "
            "(%s) -- fail-closed, Kontingent gilt als erschoepft",
            user_id, e,
        )
        cap = 0
    if cap <= 0:
        # Kein Kontingent (free/fail-closed): sperren OHNE mkdir/Sperrdatei.
        raise ChannelBlockedError(kind, "SMS-Tageslimit erreicht", reason_code=REASON_CODE)
    path = _path(user_id)
    lock_path = str(path) + _LOCK_SUFFIX
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    except OSError as e:
        logger.warning(
            "SMS-Tageslimit: Sperrdatei %s nicht erreichbar (%s) -- "
            "Pruefung uebersprungen (fail-open)",
            lock_path, e,
        )
        return
    try:
        if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
            logger.warning(
                "Dateisperre %s nicht innerhalb %.2fs erhalten -- "
                "SMS-Tageslimit-Pruefung uebersprungen (fail-open)",
                lock_path, LOCK_TIMEOUT_SECONDS,
            )
            return
        try:
            today = _today(now)
            data = _tagesstand(_load(path), today)
            current = _zaehlerwert(data, kind)
            if current >= cap:
                raise ChannelBlockedError(
                    kind, "SMS-Tageslimit erreicht", reason_code=REASON_CODE,
                )
            data[kind] = current + 1
            data.setdefault("sms", 0)
            data.setdefault("premium_sms", 0)
            try:
                _write(path, data)
            except OSError as e:
                logger.warning(
                    "SMS-Tageslimit: Schreiben von %s fehlgeschlagen (%s) -- "
                    "Reservierung nicht persistiert, Versand bleibt "
                    "zugelassen (fail-open)",
                    path, e,
                )
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def release_reservation(user_id: str, kind: str, now: datetime) -> None:
    """Gegenstueck zu `check_and_reserve` -- dekrementiert `kind` um 1, nur
    fuer den laufenden Tag. Nur aus dem Fehlerzweig eines tatsaechlich
    fehlgeschlagenen Transports aufrufen, nie bei einer Sperre.

    Randfall Tageswechsel: stimmt das gespeicherte Datum nicht mit `now`
    ueberein, wird NICHT dekrementiert (No-op) -- ein Rueckbuchen in den
    bereits zurueckgesetzten neuen Tag waere falsch. Der Zaehler geht nie
    unter 0 (Floor).

    Adversary F001 (CRITICAL): wie `check_and_reserve` fail-open bei JEDER
    I/O-Stoerung (Sperrdatei, Schreibfehler) -- ein Rollback, der selbst
    scheitert, darf NIE die urspruengliche Transportfehler-Behandlung des
    Aufrufers ueberdecken.
    """
    path = _path(user_id)
    lock_path = str(path) + _LOCK_SUFFIX
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    except OSError as e:
        logger.warning(
            "SMS-Tageslimit: Sperrdatei %s nicht erreichbar (%s) -- "
            "Rollback uebersprungen (fail-open)",
            lock_path, e,
        )
        return
    try:
        if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
            logger.warning(
                "Dateisperre %s nicht innerhalb %.2fs erhalten -- "
                "SMS-Tageslimit-Rollback uebersprungen (fail-open)",
                lock_path, LOCK_TIMEOUT_SECONDS,
            )
            return
        try:
            today = _today(now)
            data = _load(path)
            if not data or data.get("date") != today:
                return  # Tageswechsel zwischen Reservierung und Release -- No-op
            current = _zaehlerwert(data, kind)
            data[kind] = max(0, current - 1)
            try:
                _write(path, data)
            except OSError as e:
                logger.warning(
                    "SMS-Tageslimit: Rollback-Schreiben von %s fehlgeschlagen "
                    "(%s) -- Zaehlerstand bleibt unveraendert (fail-open)",
                    path, e,
                )
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def get_daily_usage(user_id: str, now: datetime) -> dict:
    """Tagesstand fuer die Konto-Anzeige (S4b, Issue #2412). Rein lesend, KEIN
    Lock: `_write` ersetzt atomar, ein Leser sieht nie einen Teilzustand.
    Wirft nie -- kaputte Zaehlerdatei => used=0, kaputter Tarif => limit=0."""
    data = _tagesstand(_load(_path(user_id)), _today(now))

    def _limit(fn, kind: str) -> int:
        try:
            return fn(user_id)
        except Exception as e:  # noqa: BLE001 -- Anzeige sperrt nichts, daher fail-open
            logger.warning(
                "SMS-Tageskontingent-Anzeige: Tier-Ermittlung (%s) fuer %s "
                "fehlgeschlagen (%s) -- Limit als 0 angezeigt", kind, user_id, e,
            )
            return 0

    return {
        "sms": {
            "used": _zaehlerwert(data, "sms"),
            "limit": _limit(user_tier.daily_sms_limit, "sms"),
            "reserve": user_tier.SMS_ALARM_RESERVE,
        },
        "premium_sms": {
            "used": _zaehlerwert(data, "premium_sms"),
            "limit": _limit(user_tier.daily_premium_sms_limit, "premium_sms"),
            "reserve": user_tier.PREMIUM_SMS_ALARM_RESERVE,
            "reply_overshoot": user_tier.PREMIUM_SMS_REPLY_OVERSHOOT,
        },
    }
