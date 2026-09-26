"""
Inbound SMS Reader — seven.io Journal-Polling fuer den Premium-SMS-Rueckkanal.

Issue #1676 Scheibe S1: holt eingehende SMS aus dem seven.io-Journal ab,
erkennt die an die Dienstnummer gerichteten Nachrichten am `to`-Feld (Issue
#2323) und meldet die Absendernummer an den internen Go-Endpunkt
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
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import Settings
from app.loader import (
    compare_preset_to_dict,
    get_data_root,
    load_all_trips,
    load_compare_presets,
)
from app.origin_guard import classify_origin
from services.notification_service import NotificationService
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
    match_leading_name,
)
# Eigener, NICHT durch Tests ersetzbarer Name fuer die zustandslose
# Klassifizierung (Issue #2417): `TripCommandProcessor` selbst wird in
# Tests durch einen Recorder ersetzt, der laut eigenem Vertrag nur
# `.process()` abfaengt und keine Parse-Logik nachbildet
# (tests/unit/test_inbound_sms_reply_learning.py::_CommandProcessorRecorder).
from services.trip_command_processor import TripCommandProcessor as _ParseNurProcessor
from services.trip_selection import ZIELLOS_SCHLUESSEL, resolve_command_target

logger = logging.getLogger(__name__)

JOURNAL_URL = "https://gateway.seven.io/api/journal/inbound"
LEARN_ENDPOINT = "http://localhost:8090/api/internal/premium-sms-learn"
GARMIN_MARKER = "inreachlink.com"
# Issue #2323: bewusst EIGENE Konstante, nicht aus premium_sms.py importiert --
# sonst folgte dieses Gate einer Aenderung der Absendernummer stillschweigend.
SERVICE_NUMBER = "4916092172595"
DRYRUN_ENV_VAR = "GZ_PREMIUM_SMS_POLL_DRYRUN"

_DEDUP_POINTER_NAME = "premium_sms_inbound.json"

# Issue #2323: Gestalt des Verknuepfungs-Codes -- fester Praefix "XX" + 3
# Buchstaben (ohne I/L/O) + 3 Ziffern (ohne 0/1), Gross-/Kleinschreibung egal.
# Go-Pendant: internal/handler/premium_sms_link_code.go::generatePremiumSmsLinkCode.
_LINK_CODE_PATTERN = re.compile(r"^XX[A-HJKMNP-Z]{3}[2-9]{3}$", re.IGNORECASE)


def split_link_code(text: str) -> tuple[str, str]:
    """Zerlegt den Nutzertext einer Garmin-Nachricht in (Code, Befehl).

    Issue #2154 Scheibe A, D9 -- die EINZIGE Stelle, an der zerlegt wird:
    sowohl der Payload-Aufbau des Lernaufrufs als auch `_verarbeite_befehl`
    rufen diese Funktion. Zwei getrennte Zerlegungen drifteten
    auseinander, und der Code landete dann als erstes Wort im ausgefuehrten
    Befehl (groesstes Bruchrisiko dieses Umbaus).

    Der Nutzertext steht VOR dem Kennzeichen, danach folgen der von Garmin
    erzeugte Link und die Koordinaten (Beleg #1676 S1). Steht davor ein Wort in
    der Code-Gestalt, ist es der Verknuepfungs-Code; sonst gibt es keinen.

    Der feste Praefix "XX" (Issue #2323) macht die Gestalt eindeutig -- kein
    Steuerbefehl beginnt so. Die frueher noetige Ausnahme fuer RUHETAG/STRECKE
    (sieben Zeichen aus dem alten Code-Alphabet) entfaellt damit.

    Der Code wird beim Zurueckgeben grossgeschrieben, damit er zum
    ausschliesslich gross erzeugten und case-sensitiv per bcrypt verglichenen
    Go-Hash passt (Issue #2323 F001): case-insensitive Eingabe -- ein per
    Satellit kleingeschrieben abgetippter Code wuerde sonst erkannt, aber vom
    Lern-Endpunkt immer abgelehnt -- und normalisierter Versand. Der
    Befehlstext bleibt unveraendert.
    """
    befehl = text.split(GARMIN_MARKER, 1)[0].strip()
    teile = befehl.split(maxsplit=1)
    if teile and _LINK_CODE_PATTERN.match(teile[0]):
        return teile[0].upper(), (teile[1].strip() if len(teile) > 1 else "")
    return "", befehl


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
        # Issue #2154 AC-11: bewusste Ablehnungen (4xx) sind KEINE
        # voruebergehenden Fehlschlaege, duerfen aber auch nicht als "ok"
        # durchgehen -- ein dauerhaft ausgesperrter Nutzer bliebe sonst
        # unsichtbar. Eigener Zaehler, getrennt von last_failed_count.
        self.last_rejected_count = 0

    def poll_and_process(self, settings: Settings) -> int:
        """Holt neue Journal-Eintraege, meldet erkannte Garmin-Nachrichten.

        Returns: Anzahl in diesem Lauf ECHT gelernter Rueckadressen (im
        Dry-Run strukturell immer 0, s. Spec Schritt 9/11). Die Anzahl
        vorruebergehend fehlgeschlagener Lernaufrufe steht danach in
        `self.last_failed_count` (Fix F001), die Zahl bewusst abgelehnter
        Lernaufrufe in `self.last_rejected_count` (Issue #2154 AC-11).
        """
        self.last_failed_count = 0
        self.last_rejected_count = 0

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

        learned, failed, rejected = self._poll_journal(settings, dry_run)
        self.last_failed_count = failed
        self.last_rejected_count = rejected
        return learned

    def _poll_journal(self, settings: Settings, dry_run: bool) -> tuple[int, int, int]:
        """Kern des Polls: iteriert das Journal, meldet erkannte
        Garmin-Nachrichten. Gibt `(gelernt, fehlgeschlagen, abgelehnt)` zurueck
        -- Hausnorm `dispatch_orchestrator.run_briefing_dispatch()` (Fix F001),
        um den Ablehnungszaehler erweitert (Issue #2154 AC-11).

        Der Dedup-Zeiger wandert fuer Nachrichten an eine ANDERE Nummer als die
        Dienstnummer und fuer gemeldete Nachrichten mit Erfolg ODER bewusster
        Ablehnung (HTTP 4xx).
        Bei einem VORUEBERGEHENDEN Fehlschlag (Netzwerk/Timeout/5xx) bricht
        die Schleife ab, BEVOR der Zeiger ueber diese (und alle in diesem
        Journal-Fenster nachfolgenden) Nachrichten hinwegwandert -- der
        naechste Lauf versucht sie erneut, in derselben Reihenfolge (R2).
        """
        data_root = get_data_root()
        last_seen_id = self._load_last_seen_id(data_root)

        messages = self._fetch_journal(settings.seven_api_key)
        if messages is None:
            return 0, 0, 0  # Netz-/HTTP-Fehler -- last_seen_id bleibt unveraendert

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
        rejected = 0
        max_seen = last_seen_id
        for msg_id, message in new_messages:
            text = message.get("text", "") or ""
            # Issue #2323: das Gate haengt am strukturell immer vorhandenen
            # Ziel-Feld, nicht mehr am abschaltbaren Garmin-Kartenlink im Text.
            # Ueber Annahme/Ablehnung entscheidet allein der Go-Lern-Endpunkt.
            if message.get("to") != SERVICE_NUMBER:
                max_seen = max(max_seen, msg_id)
                continue

            sender = message.get("from", "")
            # Issue #2154: der Code wird NUR mitgeschickt, wenn im Text auch
            # einer steht -- ein leerer Wert waere kein "fehlender Code" und
            # kippte den Entscheidungsbaum im Go-Endpunkt.
            link_code, _ = split_link_code(text)
            payload: dict = {"from": sender}
            if link_code:
                payload["code"] = link_code
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
                    # Issue #2184: der Text VOR dem Kennzeichen ist ein Befehl.
                    # Eigenes, NACHGELAGERTES try/except: der Dedup-Zeiger steht
                    # oben bereits fest, und ein Verarbeitungsfehler ist kein
                    # voruebergehender Lernfehler (F001) -- er darf `failed`
                    # nicht erhoehen, sonst kippt der Go-Scheduler-Status von
                    # "ok" auf "partial" (AC-6).
                    try:
                        self._verarbeite_befehl(settings, text, sender, response)
                    except Exception as e:
                        logger.warning(
                            "Premium-SMS-Kommandoverarbeitung fehlgeschlagen "
                            "fuer maskierte Nummer %s: %s -- Lernvorgang bleibt "
                            "erfolgreich (AC-6).", _mask(sender), e,
                        )
            elif 400 <= response.status_code < 500:
                # Bewusste Ablehnung (409 fehlender/ungueltiger Code, 429
                # Ratebremse) -- abschliessende Entscheidung, kein
                # Wiederholungsgrund, aber sichtbar (Issue #2154 AC-11).
                max_seen = max(max_seen, msg_id)
                rejected += 1
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
        return learned, failed, rejected

    def _verarbeite_befehl(
        self, settings: Settings, text: str, sender: str, response,
    ) -> None:
        """Issue #2184 (Epic #2133 S4): den Befehlstext einer Garmin-Nachricht
        verarbeiten und die Antwort per Premium-SMS zurueckschicken.

        Der Nutzer kommt aus der Erfolgsantwort des Lern-Endpunkts. Fehlt der
        Schluessel oder ist er leer, wird NICHT verarbeitet und schon gar nicht
        auf den Mandanten "default" zurueckgefallen (AC-9,
        Cross-User-Datenleck-Verbot) -- der 200er-Vertrag des Go-Endpunkts wird
        nicht stillschweigend vorausgesetzt.
        """
        user_id = (response.json() or {}).get("user_id") or ""
        if not user_id:
            logger.warning(
                "premium-sms-learn antwortete mit HTTP 200 ohne verwertbare "
                "user_id fuer maskierte Nummer %s -- keine "
                "Kommandoverarbeitung (AC-9).", _mask(sender),
            )
            return

        # Dieselbe Zerlegung wie beim Payload-Aufbau (Issue #2154 D9) -- ohne
        # sie landete der Verknuepfungs-Code als erstes Wort im ausgefuehrten
        # Befehl (AC-12).
        _, befehl = split_link_code(text)
        now_utc = datetime.now(timezone.utc)
        user_settings = settings.with_user_profile(user_id)

        # Issue #2282 Abschnitt 2/4: Satelliten-Text traegt normalerweise
        # keinen Namen (jedes Zeichen kostet), kann aber einem Trip/Vergleich
        # explizit vorangestellt sein -- dieselbe geteilte Auswahlregel wie
        # im Telegram-Reader.
        trips = load_all_trips(user_id)
        presets = [compare_preset_to_dict(p) for p in load_compare_presets(user_id)]

        named = match_leading_name(befehl, trips, presets)
        if named is not None:
            name_prefix, rest, name_kind, name_ziel = named
            # Kind/Objekt kommen aus demselben Namens-Treffer wie
            # prefix/rest -- keine zweite Suche (Adversary F001-Nachtrag).
            resolved_kind = "vergleich" if name_kind == "vergleich" else None
            resolved_preset_id = name_ziel.get("id") if name_kind == "vergleich" else None
            result = TripCommandProcessor().process(InboundMessage(
                trip_name=name_prefix, body=rest, sender=sender,
                channel="premium_sms", received_at=now_utc, user_id=user_id,
                resolved_kind=resolved_kind, resolved_preset_id=resolved_preset_id,
            ))
        else:
            # Issue #2417 (AC-18): dieselbe klassifizierte Zielaufloesung wie
            # der Telegram-Reader -- die Befehlsklasse entscheidet VOR jeder
            # Trip-/Vergleichsauswahl, ob ueberhaupt eine noetig ist. Vorher
            # rief dieser Zweig `resolve_active_target` unklassifiziert fuer
            # JEDEN Befehl auf und blockierte z.B. "hilfe" bei Trip+Vergleich
            # mit einer Rueckfrage (B1).
            key, _value = _ParseNurProcessor()._parse_command(befehl)
            if key == "hilfe":
                # AC-23: Premium-SMS bekommt die dedizierte GSM-7-Kurzhilfe
                # statt der Langhilfe -- braucht keine Trip-/Vergleichsladung
                # (AC-15). `premium_sms_kurzhilfe` wird PARALLEL in
                # `trip_command_processor.py` gebaut (#2417); der Import
                # bleibt bewusst lokal, damit dieses Modul weiter importierbar
                # ist, solange sie dort noch fehlt.
                from services.trip_command_processor import premium_sms_kurzhilfe

                result = CommandResult(
                    success=True, command="hilfe",
                    confirmation_subject="Hilfe",
                    confirmation_body=premium_sms_kurzhilfe(),
                )
            elif key in ZIELLOS_SCHLUESSEL:
                # "columns" -- kein Bare-Text-Pendant, aber Symmetrie mit dem
                # Telegram-Reader (AC-15): keine Zielaufloesung noetig.
                result = TripCommandProcessor().process(InboundMessage(
                    trip_name="", body=befehl, sender=sender,
                    channel="premium_sms", received_at=now_utc, user_id=user_id,
                ))
            else:
                ziel = resolve_command_target(
                    key, trips, presets, now_utc, channel="premium_sms",
                )
                if ziel.kind is None:
                    # AC-5/AC-17: identischer Text wie Telegram, kein
                    # `process()`-Aufruf.
                    hinweis = CommandResult(
                        success=False, command="mehrdeutig",
                        confirmation_subject="Hinweis", confirmation_body=ziel.text,
                    )
                    NotificationService(
                        user_settings, user_id=user_id,
                    ).send_command_reply_premium_sms(hinweis, user_settings)
                    return
                if ziel.kind == "route":
                    inbound = InboundMessage(
                        trip_name=ziel.target.name, body=befehl, sender=sender,
                        channel="premium_sms", received_at=now_utc, user_id=user_id,
                    )
                else:
                    preset = ziel.target
                    inbound = InboundMessage(
                        trip_name=preset.get("name", ""), body=befehl, sender=sender,
                        channel="premium_sms", received_at=now_utc, user_id=user_id,
                        resolved_kind="vergleich", resolved_preset_id=preset.get("id"),
                    )
                result = TripCommandProcessor().process(inbound)

        # `heute`/`morgen` haben das Briefing selbst schon per Premium-SMS
        # verschickt -- eine zweite, kostenpflichtige Satelliten-SMS daneben
        # waere die Bestaetigung des Briefings (AC-10).
        if not result.suppress_email_reply:
            NotificationService(
                user_settings, user_id=user_id,
            ).send_command_reply_premium_sms(result, user_settings)

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
