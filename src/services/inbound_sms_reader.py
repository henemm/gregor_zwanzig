"""
Inbound SMS Reader — seven.io Journal-Polling fuer den Premium-SMS-Rueckkanal.

Issue #1676 Scheibe S1: holt eingehende SMS aus dem seven.io-Journal ab,
erkennt darunter Garmin-inReach-Nachrichten am Kennzeichen `inreachlink.com`
und meldet die Absendernummer an den internen Go-Endpunkt
`POST /api/internal/premium-sms-learn`, der die eigentliche Nutzer-Aufloesung
(R3) und Persistenz uebernimmt (Go bleibt einziger Schreiber von `user.json`).

Vorbild: `InboundEmailReader`/`InboundTelegramReader` (`poll_and_process`).

Fix F001 (Adversary-Fund, #1676 S1): der Dedup-Zeiger darf NICHT ueber eine
erkannte Garmin-Nachricht hinwegwandern, deren Lernaufruf nur VORUEBERGEHEND
scheiterte (Netzwerkfehler/Timeout/5xx, z.B. weil die Go-API gerade neu
startet). Sonst geht die Rueckadresse dauerhaft verloren, ohne dass irgendwo
ein Fehler sichtbar wird -- das Garmin-Geraet meldet sich im Wesentlichen
einmal pro Tour. Eine BEWUSSTE Ablehnung (HTTP 4xx, insbesondere die
409-Mehrdeutigkeit aus AC-5) ist dagegen eine abschliessende Entscheidung:
dort wandert der Zeiger weiter, sonst warnt das System alle 5 Minuten ueber
etwas, das sich von selbst nicht aendert. `_poll_journal()` traegt dafuer die
Hausnorm aus `dispatch_orchestrator.run_briefing_dispatch()`: ein
`(gelernt, fehlgeschlagen)`-Tupel aus einer fehler-isolierten Schleife, deren
Fehlschlag-Zaehler im ``except`` waechst und in den Rueckgabewert fliesst.
`poll_and_process()` selbst bleibt bei `-> int` (Anzahl echt gelernter
Rueckadressen, AC-7-Vertrag unveraendert); die Fehlschlagzahl liegt danach im
Instanzfeld `last_failed_count` fuer den Trigger-Endpunkt (Team-Lead-Entscheid
#1676 S1 Fix-Loop, s. `api/routers/scheduler.py::trigger_inbound_sms`).

Fix F004 (Produktionsfehler, gemessen 2026-08-10): die echte seven.io-API
liefert `id` im Journal-Eintrag als ZEICHENKETTE (`"5283665"`), nicht als
Zahl -- der Vergleich `id > last_seen_id` brach deshalb mit `TypeError` ab
und legte den Cron-Job alle 5 Minuten lahm. `_coerce_message_id()` wandelt
jede `id` robust in eine ganze Zahl um; eine einzelne nicht umwandelbare `id`
ueberspringt NUR diese Nachricht (mit Warnung), bricht aber nicht den ganzen
Lauf ab -- Fail-soft je Eintrag, nicht Fail-hard fuer das ganze Journal.

SPEC: docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md v1.5
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import httpx

from app.config import Settings
from app.loader import get_data_root
from app.origin_guard import classify_origin

logger = logging.getLogger(__name__)

JOURNAL_URL = "https://gateway.seven.io/api/journal/inbound"
LEARN_ENDPOINT = "http://localhost:8090/api/internal/premium-sms-learn"
GARMIN_MARKER = "inreachlink.com"
DRYRUN_ENV_VAR = "GZ_PREMIUM_SMS_POLL_DRYRUN"

_DEDUP_POINTER_NAME = "premium_sms_inbound.json"


def _origin() -> str:
    """Herkunftssperre, lokale Tiefe-2-Variante (Spec "Herkunftssperre").

    `origin_guard.running_origin()` geht von der Tiefe eines Kanal-Moduls unter
    `src/output/channels/<datei>.py` aus (parents[3]). Dieser Reader liegt eine
    Ebene hoeher (`src/services/<datei>.py`, parents[2]) -- deshalb wird hier
    nur die tiefen-unabhaengige `classify_origin(root)` importiert und die
    Wurzel lokal gebildet, statt `origin_guard.py` selbst zu aendern.
    """
    root = Path(__file__).resolve().parents[2]
    return classify_origin(root)


class InboundSmsReader:
    """Pollt das seven.io-Journal und lernt Garmin-Rueckadressen."""

    def __init__(self) -> None:
        # Fix F001: vom letzten poll_and_process()-Lauf sichtbar gemachte
        # Fehlschlagzahl -- der Trigger-Endpunkt leitet seinen Status daraus
        # ab (Hausnorm run_briefing_dispatch), statt bedingungslos "ok" zu
        # melden.
        self.last_failed_count = 0

    def poll_and_process(self, settings: Settings) -> int:
        """Holt neue Journal-Eintraege, meldet erkannte Garmin-Nachrichten.

        Returns: Anzahl in diesem Lauf ECHT gelernter Rueckadressen (im
        Dry-Run strukturell immer 0, s. Spec Schritt 9/11). Die Anzahl
        vorruebergehend fehlgeschlagener Lernaufrufe steht danach in
        `self.last_failed_count` (Fix F001).
        """
        self.last_failed_count = 0

        origin = _origin()
        dry_run = False
        if origin != "production":
            if os.environ.get(DRYRUN_ENV_VAR) != "1":
                logger.warning(
                    "Premium-SMS-Poll: Herkunft %r ist nicht 'production' und "
                    "%s ist nicht gesetzt -- Poll uebersprungen (AC-7).",
                    origin, DRYRUN_ENV_VAR,
                )
                return 0
            print(
                f"[inbound_sms_reader] WARN: {DRYRUN_ENV_VAR}=1 -- Herkunft "
                f"{origin!r} ist nicht 'production', der Journal-Abruf laeuft "
                "trotzdem (Trockenlauf, AC-10). KEIN user.json wird veraendert.",
                file=sys.stderr,
            )
            dry_run = True

        if not settings.seven_api_key:
            return 0

        learned, failed = self._poll_journal(settings, dry_run)
        self.last_failed_count = failed
        return learned

    def _poll_journal(self, settings: Settings, dry_run: bool) -> tuple[int, int]:
        """Kern des Polls: iteriert das Journal, meldet erkannte
        Garmin-Nachrichten. Gibt `(gelernt, fehlgeschlagen)` zurueck --
        Hausnorm `dispatch_orchestrator.run_briefing_dispatch()` (Fix F001).

        Der Dedup-Zeiger wandert fuer Nachrichten OHNE Kennzeichen und fuer
        Garmin-Nachrichten mit Erfolg ODER bewusster Ablehnung (HTTP 4xx).
        Bei einem VORUEBERGEHENDEN Fehlschlag (Netzwerk/Timeout/5xx) bricht
        die Schleife ab, BEVOR der Zeiger ueber diese (und alle in diesem
        Journal-Fenster nachfolgenden) Nachrichten hinwegwandert -- der
        naechste Lauf versucht sie erneut, in derselben Reihenfolge (R2).
        """
        data_root = get_data_root()
        last_seen_id = self._load_last_seen_id(data_root)

        messages = self._fetch_journal(settings.seven_api_key)
        if messages is None:
            return 0, 0  # Netz-/HTTP-Fehler -- last_seen_id bleibt unveraendert

        parsed: list[tuple[int, dict]] = []
        for m in messages:
            raw_id = m.get("id", 0)
            msg_id = _coerce_message_id(raw_id)
            if msg_id is None:
                logger.warning(
                    "journal/inbound Eintrag mit nicht umwandelbarer id %r "
                    "wird uebersprungen (Fix F004), Rest des Journal-Fensters "
                    "wird weiterverarbeitet.", raw_id,
                )
                continue
            if msg_id > last_seen_id:
                parsed.append((msg_id, m))

        new_messages = sorted(parsed, key=lambda pair: pair[0])

        learned = 0
        failed = 0
        max_seen = last_seen_id
        for msg_id, message in new_messages:
            text = message.get("text", "") or ""
            if GARMIN_MARKER not in text:
                max_seen = max(max_seen, msg_id)
                continue

            sender = message.get("from", "")
            payload: dict = {"from": sender}
            if dry_run:
                payload["dry_run"] = True
            try:
                response = httpx.post(LEARN_ENDPOINT, json=payload, timeout=5)
            except Exception as e:
                failed += 1
                logger.warning(
                    "premium-sms-learn fehlgeschlagen (Netzwerk) fuer maskierte "
                    "Nummer %s: %s -- Zeiger bleibt stehen (Fix F001).",
                    _mask(sender), e,
                )
                break  # vorruebergehend: naechster Lauf versucht diese Nachricht erneut

            if response.status_code == 200:
                max_seen = max(max_seen, msg_id)
                if dry_run:
                    masked = response.json().get("masked_from") or _mask(sender)
                    logger.info(
                        "Premium-SMS-Poll (Trockenlauf): Garmin-Nachricht "
                        "erkannt, Rueckadresse %s wuerde gelernt (kein "
                        "Schreibvorgang).", masked,
                    )
                else:
                    learned += 1
            elif 400 <= response.status_code < 500:
                # Bewusste Ablehnung (z.B. 409 Mehrdeutigkeit, AC-5) --
                # abschliessende Entscheidung, kein Wiederholungsgrund.
                max_seen = max(max_seen, msg_id)
                logger.warning(
                    "premium-sms-learn abgelehnt (HTTP %d) fuer maskierte "
                    "Nummer %s: %s", response.status_code, _mask(sender),
                    response.text[:200],
                )
            else:
                failed += 1
                logger.warning(
                    "premium-sms-learn HTTP %d (vorruebergehend) fuer "
                    "maskierte Nummer %s: %s -- Zeiger bleibt stehen "
                    "(Fix F001).", response.status_code, _mask(sender),
                    response.text[:200],
                )
                break  # vorruebergehend: naechster Lauf versucht diese Nachricht erneut

        self._save_last_seen_id(data_root, max_seen)
        return learned, failed

    def _fetch_journal(self, api_key: str) -> list[dict] | None:
        """GET journal/inbound. None bei Fehler (fail-soft, Schritt 5)."""
        try:
            response = httpx.get(
                JOURNAL_URL,
                headers={"X-Api-Key": api_key},
                params={"limit": 100},
                timeout=10,
            )
            if response.status_code != 200:
                logger.error(
                    "journal/inbound returned status %d: %s",
                    response.status_code, response.text[:200],
                )
                return None
            return response.json()
        except Exception as e:
            logger.error("journal/inbound Abruf fehlgeschlagen: %s", e)
            return None

    def _load_last_seen_id(self, data_root: Path) -> int:
        """Fail-open: kaputte/fehlende Zeigerdatei ODER nicht umwandelbarer
        `last_seen_id`-Wert -> 0 (Fix F004)."""
        path = data_root / "diagnostics" / _DEDUP_POINTER_NAME
        try:
            data = json.loads(path.read_text())
        except Exception:
            return 0
        return _coerce_message_id(data.get("last_seen_id", 0)) or 0

    def _save_last_seen_id(self, data_root: Path, last_seen_id: int) -> None:
        """Atomarer Write (tempfile + os.rename), auch im Dry-Run (Spec:
        globaler Diagnose-State, kein Nutzerdatensatz)."""
        directory = data_root / "diagnostics"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / _DEDUP_POINTER_NAME
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".premium_sms_inbound_")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"last_seen_id": last_seen_id}, f)
            os.rename(tmp_path, path)
        except Exception:
            logger.exception("Dedup-Zeiger konnte nicht geschrieben werden")
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _coerce_message_id(raw) -> int | None:
    """Wandelt eine Journal-`id` robust in eine ganze Zahl um (Fix F004): die
    echte seven.io-API liefert `id` als Zeichenkette (`"5283665"`), unsere
    aeltesten Fixtures nahmen faelschlich eine Zahl an. `None` bei jedem Wert,
    der sich nicht umwandeln laesst -- der Aufrufer ueberspringt dann NUR
    diesen einen Eintrag, statt den ganzen Journal-Lauf abzubrechen."""
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _mask(number: str) -> str:
    """Rufnummern nur maskiert loggen (Spec)."""
    if len(number) <= 3:
        return "*" * len(number)
    return "*" * (len(number) - 3) + number[-3:]
