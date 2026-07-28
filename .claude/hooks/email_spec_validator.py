#!/usr/bin/env python3
"""
E-Mail Spec v4.0 Compliance Validator

DIESER VALIDATOR IST ZWINGEND VOR JEDEM "E2E TEST BESTANDEN" AUSZUFÜHREN!

Prüft:
1. Struktur (2 Tabellen, 9 Zeilen)
2. Location-Anzahl (mind. 3 oder alle verfügbaren)
3. Daten-Plausibilität (Sonnenstunden vs Wolkenlage)
4. Format-Korrektheit (Wind/Böen, Sonnenstunden)
5. Vollständigkeit (Stunden-Tabelle)

Exit codes:
    0 = Alle Checks bestanden
    1 = Spec-Verletzung gefunden
    2 = Technischer Fehler
"""

import argparse
import math
import os
import sys
import imaplib
import email
import re
import time
from datetime import date
from email.header import decode_header
from pathlib import Path
from typing import List, Tuple

# Issue #1282 AC-4: shared-repo _log-Aufloesung (git-common-dir) -- gleiches
# Muster wie renderer_mail_gate.py fuer hook_utils (sys.path-Erweiterung fuer
# standalone-Aufruf, kein relativer Import noetig).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _e2e_paths  # noqa: E402
import _validator_log  # noqa: E402  (#1408 F005: kollisionsfreie Log-Ablage)


def _write_validation_log(
    success: bool,
    errors: list,
    min_locations: int,
    log_dir: "Path | None" = None,
    workflow_id: "str | None" = None,
    max_age_minutes: "int | None" = None,
    ignore_mail_age_reason: "str | None" = None,
) -> None:
    """Issue #465 (B2): Strukturiertes Validator-Log YAML.

    Schreibt in ``.claude/workflows/_log/<ts>_<wf>_email_validation.yaml``.
    Fail-soft: jeder Fehler wird unterdrueckt, damit der Validator-Exit-Code
    erhalten bleibt.

    Issue #1408 (AC-5): ``max_age_minutes`` und ``ignore_mail_age_reason``
    werden IMMER geschrieben -- auch bei ``passed: true``. Eine bewusst
    abgeschaltete Altersschranke bleibt so weder unbemerkt noch unbegruendet:
    im Log steht der Grund im Klartext, nicht nur ein ``true``.

    Issue #1282 AC-4: ist ``log_dir`` NICHT explizit uebergeben, wird das
    shared-repo `_log` (git-common-dir via ``_e2e_paths.shared_repo_dir``)
    verwendet, Fail-soft-Fallback auf die alte __file__-relative Berechnung
    (z.B. ausserhalb eines Git-Repos). Ein explizit uebergebenes ``log_dir``
    behaelt weiterhin Vorrang (Tests/AC-10 in test_issue_465).
    """
    try:
        from datetime import datetime
        import yaml as _yaml

        if log_dir is None:
            hooks_dir = Path(__file__).resolve().parent
            fallback_log_dir = hooks_dir.parent.parent / ".claude" / "workflows" / "_log"
            try:
                shared = _e2e_paths.shared_repo_dir(cwd=hooks_dir)
            except Exception:
                shared = None
            log_dir = (shared / ".claude" / "workflows" / "_log") if shared else fallback_log_dir

        if workflow_id is None:
            workflow_id = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "unknown")

        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)


        # None heisst hier wie im Fetch-Pfad "Standardgrenze war aktiv".
        effective_max_age = (
            int(max_age_minutes) if max_age_minutes is not None
            else _DEFAULT_MAX_AGE_MINUTES
        )

        data = {
            "validator": "email_spec_validator",
            "validated_at": datetime.utcnow().isoformat(),
            "workflow_id": workflow_id,
            "passed": bool(success),
            "error_count": len(errors),
            "errors": list(errors),
            "min_locations_checked": int(min_locations),
            # Issue #1408 AC-5: Zustand der Altersschranke ist Teil jedes Laufs.
            # Adversary F001: NICHT nur das Abschalten wird sichtbar, sondern
            # jede Abweichung vom Standardwert -- sonst verschoebe sich die
            # stille Umgehung bloss von "unendlich" auf "knapp unter der
            # Obergrenze".
            "max_age_minutes": effective_max_age,
            "max_age_minutes_default": _DEFAULT_MAX_AGE_MINUTES,
            "max_age_minutes_overridden": effective_max_age != _DEFAULT_MAX_AGE_MINUTES,
            "ignore_mail_age_reason": ignore_mail_age_reason,
        }

        import tempfile
        fd, tmp = tempfile.mkstemp(dir=str(log_dir), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            _yaml.safe_dump(data, f, allow_unicode=True)
        # F005: nie ueberschreiben -- auch nicht bei parallelen Sitzungen.
        # Der Zaehler waechst im Praefix, die Endung '_email_validation.yaml'
        # bleibt unangetastet (danach sucht renderer_mail_gate.py).
        _validator_log.place_exclusively(tmp, log_dir, workflow_id, "email_validation")
    except Exception as exc:
        # fail-soft — darf den Validator-Exit-Code nie kippen, aber NICHT
        # lautlos: das Log ist der Nachweis, den das Renderer-Commit-Gate
        # (#811) liest. Ein fehlendes Log ohne Hinweis sieht aus wie ein
        # vergessener Lauf.
        print(
            f"WARNUNG: Validator-Log konnte nicht geschrieben werden ({exc}) -- "
            f"der Lauf zaehlt damit nicht als Nachweis.",
            file=sys.stderr,
        )


# Issue #1124 (Teil B): Marker-Header, der eine Compare-Mail auszeichnet. Teil A
# (live) sorgt dafuer, dass echte Ortsvergleichs-Mails diesen Header tragen.
_COMPARE_MAIL_TYPE = "compare"

# Issue #1408: Altersschranke fuer die gepruefte Mail, standardmaessig AKTIV.
# Das geteilte Test-Postfach nimmt auch Mails paralleler Sitzungen auf -- ohne
# Zeitgrenze kann eine beliebig alte Mail (z.B. aus einem abgebrochenen
# Vorlauf) als frischer Nachweis in das Renderer-Commit-Gate #811 und in die
# Staging-Attestation eingehen.
#
# PRUEFDATUM (Regel-Budget, CLAUDE.md): 2026-10-26. Bis dahin muss die
# Schranke einen echten Fang vorweisen (verhinderter Falsch-Nachweis) oder sie
# wird zurueckgebaut. Zu eng (legitime langsame Staging-Laeufe scheitern) oder
# zu weit (faengt die #1408-Ursache nicht mehr) => Wert anpassen.
_DEFAULT_MAX_AGE_MINUTES = 60

# Bewusstes Abschalten verlangt einen Grund im Klartext (Vorbild
# `qa_gate.py --no-visual "<Grund>"`). KEIN Sentinel-Zahlenwert: eine `0`, die
# "unbegrenzt" statt "nichts erlaubt" bedeutet, wird im entscheidenden Moment
# falsch gelesen.
_IGNORE_AGE_HINT = (
    'bewusstes Abschalten nur ueber --ignore-mail-age "<Grund>" '
    "(der Grund landet im Validator-Log)"
)



# Adversary F001: Obergrenze fuer --max-age-minutes. Ohne sie liesse sich die
# Schranke ueber einen absurd hohen Wert (999999999) faktisch abschalten --
# dieselbe stille Umkehr ueber einen Zahlenwert, die der begruendungspflichtige
# Schalter gerade verhindern soll, nur mit einer anderen Zahl. 24 Stunden ist
# die Grenze dessen, was noch als "aus diesem Lauf" durchgehen kann; wer weiter
# zurueckgreifen will, muss es begruenden.
_MAX_AGE_CEILING_MINUTES = 1440


def _check_selection_arguments(
    max_age_minutes: "int | None" = None,
    ignore_mail_age_reason: "str | None" = None,
    subject_contains: "str | None" = None,
) -> None:
    """Adversary F001/F002/F003: EINE Stelle fuer alle Werte, die still "aus"
    bedeuten koennten -- auf Funktionsebene, nicht nur in ``main()``.

    - Eine Altersgrenze oberhalb von 24 Stunden wird abgelehnt und auf den
      begruendungspflichtigen Schalter verwiesen.
    - Ein gesetzter, aber leerer/whitespace-only Grund zaehlt NICHT als
      Begruendung: sonst waere ``ignore_mail_age_reason=""`` ein
      begruendungsfreier Ausschalter, waehrend das Log ein leeres Feld zeigt.
    - Ein gesetztes, aber leeres Betreffs-Fragment steckt in JEDEM Betreff und
      schaltet den Filter damit still ab -- der Aufrufer glaubt, seine eigene
      Mail benannt zu haben, und prueft die fremde. Nicht filtern wollen heisst
      Argument weglassen, nicht Argument leer setzen.

    Gemeinsames Muster aller drei: ein Wert, der unauffaellig "keine Pruefung"
    bedeutet, ist gefaehrlicher als ein fehlender Wert -- weil er wie eine
    Pruefung aussieht.
    """
    if subject_contains is not None and not subject_contains.strip():
        raise ValueError(
            "Ein leeres Betreffs-Fragment (subject_contains / "
            "--subject-contains) passt auf JEDE Mail und schaltet den Filter "
            "damit still ab. Wer filtern will, muss ein Fragment nennen; wer "
            "nicht filtern will, laesst das Argument weg."
        )
    if ignore_mail_age_reason is not None and not ignore_mail_age_reason.strip():
        raise ValueError(
            "Die Altersschranke laesst sich nur mit einem nicht-leeren Grund "
            "abschalten (ignore_mail_age_reason / --ignore-mail-age \"<Grund>\"). "
            "Ein leerer Grund waere eine begruendungsfreie Abschaltung mit "
            "leerer Log-Spur -- die Schranke bleibt aktiv."
        )
    if max_age_minutes is not None and not math.isfinite(max_age_minutes):
        # Adversary F004: `nan` ist der schlechteste aller Werte -- jeder
        # Vergleich mit ihm ist falsch (`nan > 1440` UND `age > nan`), es
        # umgeht also Obergrenze und Altersvergleich in einem Zug, und
        # anschliessend laesst `int(nan)` auch noch das Validator-Log
        # entfallen: Schranke weg UND Nachweis weg. `inf` faellt hier
        # gleich mit ab (frueher ein Sonderfall beim Formatieren).
        raise ValueError(
            f"Die Altersgrenze muss eine endliche Zahl in Minuten sein "
            f"(bekommen: {max_age_minutes}). Nicht-endliche Werte vergleichen "
            f"sich mit nichts -- die Schranke waere lautlos ausgeschaltet und "
            f"das Validator-Log bliebe leer. {_IGNORE_AGE_HINT}."
        )
    if max_age_minutes is not None and max_age_minutes > _MAX_AGE_CEILING_MINUTES:
        raise ValueError(
            f"Altersgrenze {max_age_minutes} Minuten ueberschreitet das "
            f"Maximum von {_MAX_AGE_CEILING_MINUTES} Minuten (24 Stunden). Eine "
            f"beliebig grosse Grenze waere eine stille Abschaltung der Schranke "
            f"ohne Begruendung -- {_IGNORE_AGE_HINT}."
        )


def _decode_subject(raw: "str | None") -> str:
    """Dekodiert ein (ggf. RFC-2047-kodiertes) Subject zu lesbarem str.

    1:1 das Vorbild aus `briefing_mail_validator.py` (#780): Umlaut-/Em-Dash-
    Subjects kommen per IMAP als ``=?utf-8?b?...?=`` zurueck."""
    if not raw:
        return ""
    parts = []
    for chunk, enc in decode_header(raw):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _message_matches(headers, subject_contains: "str | None" = None) -> bool:
    """Issue #1408: EINE gemeinsame Trefferbedingung fuer die Mail-Auswahl.

    Vorher stand dieselbe Marker-Pruefung zweimal im Modul (in
    ``_select_compare_uid`` und inline in ``_fetch_latest_message``) und war
    bereits einmal auseinandergelaufen -- die getestete Auswahlfunktion wurde
    im echten Fetch-Pfad nie aufgerufen. Beide Stellen rufen jetzt dieses
    Praedikat auf; zwei Kopien sind strukturell nicht mehr moeglich.

    - Marker: ``X-GZ-Mail-Type`` muss ``compare`` sein (immer geprueft).
    - ``subject_contains`` gesetzt: das dekodierte Subject muss das Fragment
      enthalten. ``None`` => Verhalten exakt wie vor #1408 (nur Marker).
    """
    if headers.get("X-GZ-Mail-Type") != _COMPARE_MAIL_TYPE:
        return False
    if subject_contains is not None:
        if subject_contains not in _decode_subject(headers.get("Subject")):
            return False
    return True


def _no_compare_mail_error(
    subject_contains: "str | None" = None,
    max_age_minutes: "int | None" = None,
) -> ValueError:
    """Einheitliche AC-3-Fehlermeldung, damit die reine Auswahl-Funktion und der
    IMAP-Fetch dieselbe Meldung erheben.

    Issue #1408: Die Meldung nennt jetzt auch, WONACH gesucht wurde (Betreffs-
    Fragment) und welche Altersgrenze aktiv war -- sonst tauscht man ein stilles
    Falsch-Gruen gegen ein raetselhaftes Rot."""
    msg = (
        f"Keine Compare-Mail (X-GZ-Mail-Type: {_COMPARE_MAIL_TYPE}) im Postfach "
        f"gefunden -- der Validator prueft nur echte Ortsvergleichs-Mails."
    )
    if subject_contains is not None:
        msg += (
            f" Gesucht wurde zusaetzlich nach dem Betreffs-Fragment "
            f"{subject_contains!r} (--subject-contains); keine Mail erfuellt "
            f"Marker UND Betreff gleichzeitig."
        )
    if max_age_minutes is not None:
        msg += f" Aktive Altersgrenze: {int(max_age_minutes)} Minuten."
    return ValueError(msg)


def _internaldate_line(fetch_data) -> bytes:
    """Issue #1408: Fuegt die NICHT-Nutzlast-Teile einer Fetch-Antwort zusammen.

    ``imaplib`` liefert einen kombinierten Fetch als Mischung aus Tupeln
    ``(praefix, nutzlast)`` und losen bytes. Wo der Server ``INTERNALDATE``
    ablegt, haengt davon ab, ob er es VOR oder NACH dem Literal ausgibt --
    beides ist protokollkonform. Deshalb werden alle Nicht-Nutzlast-Teile
    betrachtet; die Nutzlast (``item[1]``, der Header-Text selbst) bleibt
    ausdruecklich aussen vor, damit kein Mail-Inhalt als Zeitstempel
    fehlgedeutet werden kann."""
    parts = []
    for item in fetch_data or []:
        if isinstance(item, tuple) and item:
            parts.append(bytes(item[0]))
        elif isinstance(item, (bytes, bytearray)):
            parts.append(bytes(item))
    return b" ".join(parts)


def _age_minutes(fetch_response_line, subject: str = "") -> float:
    """Issue #1408 (AC-3/AC-6): Alter der Mail in Minuten aus der serverseitig
    vergebenen ``INTERNALDATE``.

    ``fetch_response_line`` ist die PRAEFIX-Zeile der Fetch-Antwort
    (``data[0][0]``, z.B. ``b'12 (INTERNALDATE "28-Jul-2026 09:00:00 +0000"
    BODY[HEADER] {842}'``) -- NICHT die Nutzlast. Geparst wird mit dem dafuer
    vorgesehenen Stdlib-Helfer ``imaplib.Internaldate2tuple()``.

    AC-6: Liefert die Antwort keinen auswertbaren Zeitstempel, gibt
    ``Internaldate2tuple`` schlicht ``None`` zurueck (keine Exception). Dieses
    ``None`` wird hier in einen ValueError uebersetzt -- es gibt bewusst KEINEN
    Rueckfall auf den ``Date``-Header der Mail: der ist absenderseitig gesetzt
    und damit manipulierbar, waehrend ``INTERNALDATE`` vom Server stammt. Ein
    stiller Rueckfall waere genau die Art Luecke, die #1408 schliesst.

    ``Internaldate2tuple`` liefert LOKALZEIT als struct_time -> ``time.mktime``
    (nicht ``calendar.timegm``, das verschoebe das Alter um den UTC-Versatz).
    """
    parsed = imaplib.Internaldate2tuple(fetch_response_line)
    if parsed is None:
        raise ValueError(
            f"Der IMAP-Server hat fuer die gewaehlte Mail{f' ({subject!r})' if subject else ''} "
            f"keinen auswertbaren Server-Zeitstempel (INTERNALDATE) geliefert. "
            f"Der Validator weicht bewusst NICHT auf den Date-Header der Mail aus "
            f"(absenderseitig gesetzt, manipulierbar) und verweigert stattdessen "
            f"die Arbeit -- {_IGNORE_AGE_HINT}."
        )
    return (time.time() - time.mktime(parsed)) / 60.0


def _too_old_error(subject: str, age: float, max_age_minutes: int) -> ValueError:
    """Issue #1408 (AC-3): Treffer gefunden, aber zu alt. Die Meldung nennt die
    Mail, ihr Alter, die Grenze und den bewussten Ausweg."""
    return ValueError(
        f"Die gefundene Compare-Mail ({subject!r}) ist {age:.0f} Minuten alt und "
        f"damit aelter als die zulaessigen {int(max_age_minutes)} Minuten "
        f"(--max-age-minutes). Sie stammt nicht aus diesem Lauf und taugt nicht "
        f"als Nachweis -- {_IGNORE_AGE_HINT}."
    )


def _select_compare_uid(candidates, subject_contains: "str | None" = None):
    """Issue #1124 (Teil B): Rein deterministische Auswahl der zu pruefenden
    Mail. `candidates` ist eine geordnete Liste von ``(uid: bytes, header_bytes:
    bytes)`` in IMAP-Suchreihenfolge (aeltest -> neuest, wie ``imap.search``
    liefert). Rueckgabe: die UID der NEUESTEN Mail, die ``_message_matches``
    erfuellt.

    Issue #1408: Mit ``subject_contains`` wird die eigene Mail NAMENTLICH
    gewaehlt -- eine juengere fremde compare-Mail aus einer parallelen Sitzung
    verdraengt sie dann nicht mehr.

    Faellt keine Mail unter die Bedingung, wird ``ValueError`` mit einer klaren
    Meldung erhoben (statt still die falsche Mail zu pruefen, AC-3)."""
    # Adversary F003: auch der direkte Einstieg (ohne IMAP) darf sich den
    # Filter nicht per leerem Fragment abschalten lassen.
    _check_selection_arguments(subject_contains=subject_contains)
    for uid, header_bytes in reversed(candidates):
        headers = email.message_from_bytes(header_bytes)
        if _message_matches(headers, subject_contains=subject_contains):
            return uid
    raise _no_compare_mail_error(subject_contains=subject_contains)


def _fetch_latest_message(
    imap=None,
    subject_contains: "str | None" = None,
    max_age_minutes: "int | None" = None,
    ignore_mail_age_reason: "str | None" = None,
):
    """IMAP-Fetch der zu pruefenden Compare-Mail (Issue #1124 Teil B).

    Scannt die Mails newest-first NUR ueber ihren Header (``BODY.PEEK[HEADER]``,
    setzt kein ``\\Seen``) und stoppt beim ERSTEN Treffer mit
    ``X-GZ-Mail-Type: compare`` (lazy Frueh-Abbruch). Es gibt KEIN festes
    Scan-Fenster mehr (F001): auf dem geteilten Test-Postfach kann eine
    Compare-Mail tief unter frischeren Nicht-Compare-Mails liegen -- ein Cap
    haette sie verpasst und faelschlich AC-3 gemeldet. Erst wenn das GESAMTE
    Postfach keine Compare-Mail traegt, wird der AC-3-Fehler erhoben.

    Der Voll-Fetch der gefundenen Mail laeuft ebenfalls ueber ``BODY.PEEK[]`` --
    die gepruefte Mail bleibt im selben Gelesen-Zustand.

    Issue #1408: Der Scan nutzt ``_message_matches`` -- mit ``subject_contains``
    wird die eigene Mail namentlich gesucht. Der Treffer wird zusaetzlich auf
    sein Alter geprueft (serverseitige ``INTERNALDATE``, im selben Fetch
    mitgeholt, kein zusaetzlicher Roundtrip). Ist er aelter als
    ``max_age_minutes`` (``None`` => Standardgrenze
    ``_DEFAULT_MAX_AGE_MINUTES``), wird SOFORT abgebrochen: weiter zurueck
    liegende Mails sind per Definition noch aelter. Abschalten geht nur bewusst
    ueber ``ignore_mail_age_reason`` -- dann entfaellt die Zeitpruefung
    vollstaendig (inklusive der AC-6-Pruefung auf einen ueberhaupt vorhandenen
    Server-Zeitstempel; das ist Teil derselben bewussten Entscheidung).

    Ist ``imap`` (eine fertige, bereits angemeldete Verbindung) uebergeben, wird
    sie direkt genutzt -- ohne Settings/Credentials/IMAP4_SSL-Aufbau (Test-Seam).
    """
    # None heisst "Standardgrenze anwenden", NICHT "keine Grenze": ein Aufruf
    # ohne neue Argumente (AC-4) laeuft weiter, bleibt aber geschuetzt.
    if max_age_minutes is None:
        max_age_minutes = _DEFAULT_MAX_AGE_MINUTES

    # Adversary F001/F002: Beide Schutzpruefungen sitzen HIER, an der Stelle,
    # an der die Entscheidung faellt -- nicht (nur) in main(). Ein Schutz, der
    # allein an der Kommandozeilen-Oberflaeche haengt, faellt weg, sobald ein
    # zweiter Aufrufer die Funktion direkt benutzt.
    _check_selection_arguments(
        max_age_minutes=max_age_minutes,
        ignore_mail_age_reason=ignore_mail_age_reason,
        subject_contains=subject_contains,
    )

    own_connection = imap is None
    if own_connection:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
        from app.config import Settings
        settings = Settings()

        imap_host = settings.imap_host or settings.smtp_host
        # #972: Test-Postfach-Credentials priorisieren (Referenz-Pattern aus
        # radar_alert_mail_validator.py:170-171) — sonst prueft der Validator
        # versehentlich gegen das Produktiv-Postfach.
        imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
        imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
        if not imap_user or not imap_pass:
            raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")

        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
        imap.login(imap_user, imap_pass)

    try:
        imap.select('INBOX')

        _, data = imap.search(None, 'ALL')
        all_ids = data[0].split()
        if not all_ids:
            raise ValueError("Keine E-Mails gefunden")

        # Newest-first, lazy: je UID nur den Header holen (BODY.PEEK[HEADER] =>
        # kein \Seen) und beim ERSTEN compare-Treffer stoppen. Kein Fenster-Cap
        # (F001) -- im Normalfall (Compare = juengste Mail) genau EIN Header-Fetch.
        selected_uid = None
        for uid in reversed(all_ids):
            # #1408: INTERNALDATE reist in DERSELBEN Fetch-Antwort mit (kein
            # zusaetzlicher Roundtrip) und steht in deren Praefix-Zeile.
            _, hdr_data = imap.fetch(uid, '(BODY.PEEK[HEADER] INTERNALDATE)')
            headers = email.message_from_bytes(hdr_data[0][1])
            if _message_matches(headers, subject_contains=subject_contains):
                selected_uid = uid
                selected_subject = _decode_subject(headers.get("Subject"))
                selected_response_line = _internaldate_line(hdr_data)
                break
        if selected_uid is None:
            raise _no_compare_mail_error(
                subject_contains=subject_contains,
                max_age_minutes=None if ignore_mail_age_reason else max_age_minutes,
            )

        # #1408 AC-3/AC-6: Zeitpruefung des Treffers. Bewusst abgeschaltet
        # (mit Begruendung) => komplett uebersprungen, sonst muss eine
        # belastbare Server-Zeit vorliegen UND im Fenster liegen.
        if ignore_mail_age_reason is None:
            age = _age_minutes(selected_response_line, subject=selected_subject)
            if age > max_age_minutes:
                raise _too_old_error(selected_subject, age, max_age_minutes)

        # Voll-Fetch der Treffer-Mail ebenfalls per BODY.PEEK[] (kein \Seen).
        _, msg_data = imap.fetch(selected_uid, '(BODY.PEEK[])')
        msg = email.message_from_bytes(msg_data[0][1])
    finally:
        if own_connection:
            try:
                imap.close()
                imap.logout()
            except Exception:
                pass

    return msg


def _extract_html_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            return part.get_payload(decode=True).decode('utf-8')
    return ''


def fetch_latest_email() -> str:
    """Fetch latest sent email HTML body. Unveraenderter oeffentlicher Vertrag."""
    return _extract_html_body(_fetch_latest_message())


# Issue #1108: v2-Vertrag (render_compare_html, Issue #1110) hat kein
# class="matrix-table" mehr -- die Uebersichtstabelle wird stattdessen ueber
# ihre erste Datenzeile "Amtliche Warnungen" identifiziert (CV2_METRICS[0],
# immer sichtbar, auch bei preset-gefilterten Metriken, #1104).
_OVERVIEW_WARN_LABEL = "Amtliche Warnungen"
_TABLE_RE = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL)

# v2-Stunden-Spaltenvertrag (compare_html.py:HOUR_METRICS), Issue #1106:
# 10-Spalten-Superset-Liste ("Zeit" + 9 konfigurierbare Wert-Spalten).
# Issue #1381: Diese Liste ist eine ALLOWLIST, KEINE Reihenfolge-Vorgabe --
# seit #1359 ist die Spaltenreihenfolge nutzerseitig frei einstellbar.
# Konfigurierbare Teilmengen in beliebiger Anordnung sind zulaessig,
# s. validate_structure().
#
# Issue #1404: UEBERGANGS-UNION, strikt additiv. #1401 Scheibe A2b leitet die
# Spaltenueberschriften aus dem zentralen Namensregister ab; 6 der 9
# Wertspalten heissen danach anders (Gef.->Feels, Böen->Gust, Regen->Rain,
# Gew.->Thdr, Regen-W.->Rain%, Sicht->Visib; Zeit/Temp/Wind/UV bleiben
# gleich). Waere hier nur EINE Fassung gelistet, wuerde der Pruefer die
# jeweils andere -- inhaltlich korrekte -- Mail hart ablehnen (Exit 1) und
# ueber das Renderer-Commit-Gate #811 jeden Commit an compare_html.py
# blockieren: A2b koennte seine eigene Aenderung nicht committen. Solange die
# Umbenennung laeuft, gehen deshalb BEIDE Fassungen durch.
#
# RUECKBAU-AUFTRAG: Sobald #1401 A2b geliefert ist, fallen die 6 alten Labels
# ("Gef.", "Böen", "Regen", "Gew.", "Regen-W.", "Sicht") wieder heraus --
# Zielzustand sind exakt die 10 A2b-Spalten. Bis dahin erinnert
# _HOUR_COLUMNS_V2_REVIEW_DATE an die faellige Entscheidung.
_HOUR_COLUMNS_V2 = [
    # heutige Fassung (10)
    "Zeit", "Temp", "Gef.", "Wind", "Böen", "Regen", "UV", "Gew.", "Regen-W.", "Sicht",
    # Zielfassung #1401 A2b -- nur die 6 tatsaechlich abweichenden Labels
    "Feels", "Gust", "Rain", "Thdr", "Rain%", "Visib",
]

# Pruefdatum der Uebergangs-Union (Regel-Budget: Spec-`created` 2026-07-28 +
# 90 Tage). REINER ERINNERUNGS-MARKER fuer eine menschliche Review -- anders
# als bei `nebenbefund_gate.py:21` schaltet dieses Datum KEIN Verhalten um und
# es gibt keinen Code-Zweig darauf. Eine Selbstverengung am Stichtag waere
# falsch: verzoegert sich #1401 A2b, wuerde die dann korrekte neue Mail wieder
# hart abgelehnt -- genau der Fehler, den diese Union verhindert.
_HOUR_COLUMNS_V2_REVIEW_DATE = date(2026, 10, 26)

# Negativ-Check: Score-/Winner-Sprache ist im v2-Vertrag ein Verstoss (kein
# Ranking mehr, s. compare_html.py-Docstring "Kein Score/Ranking/Winner-Card").
# Adversary F001: Wortgrenzen statt ungebundener Substring-Suche (sonst
# false positives bei Ortsnamen wie "Scoresbysund"/"Gewinnerort"); "score"
# zusaetzlich mit Zahlen-Kontext (Score-Werte sind immer "Score: N"/"Score N"),
# damit ein isoliertes Wort "Score" (z. B. in einem Ortsnamen-Fragment mit
# Wortgrenze) nicht faelschlich als Verstoss zaehlt.
_SCORE_WINNER_RE = re.compile(
    r"\bscore\b\s*[:=]?\s*\d+|\bwinner\b|\bempfehlung\b|\bbester\s+standort\b|🏆",
    re.IGNORECASE,
)

# v2-Uebersichtstabellen-Metrikzeilen (CV2_METRICS-Label -> Format-Regex +
# plausibler Wertebereich).
#
# Issue #1404: von 5 auf 24 Zeilen erweitert -- 19 numerisch pruefbare Zeilen
# liefen bis dahin durch den stillen `continue`-Pfad in
# validate_plausibility()/validate_format(), also voellig ungeprueft.
#
# WAS DIESE PRUEFUNG LEISTET -- und was nicht: Sie faengt Tippfehler,
# Einheitenverwechslungen und offensichtlichen Datenmuell (leere/kaputte
# Zellen, Faktor-1000-Fehler, Vorzeichendreher). Sie bewertet KEINE
# Meteorologie: die Grenzen sind bewusst weit gewaehlt und physikalisch
# geschaetzt, nicht gegen historische Wetterdaten belegt (s. Spec
# `fix_1404_validator_spaltennamen.md`, Known Limitations). Ein echter
# Extremwert darf hier nie anschlagen -- ein Fehlalarm bei genau der
# Wetterlage, fuer die dieses Produkt gebaut ist, waere schlimmer als eine
# durchgelassene Unplausibilitaet.
#
# Format und Einheiten-Abstand sind AM RENDERER gemessen, nicht geraten:
# `_fmt_metric()` (compare_html.py) haengt "°C" und "%" OHNE Leerzeichen an,
# jede andere Einheit ("°", "hPa", "m", "km/h", "J/kg", "cm", "mm", "h") MIT.
# Zeilen mit eigener `fmt`-Funktion (Sicht min) folgen deren Ausgabe.
_OVERVIEW_METRIC_CHECKS = {
    # -- bereits vor #1404 geprueft ------------------------------------------
    "Temp max": (re.compile(r'^-?\d+°C$'), (-40, 55)),
    "Wind": (re.compile(r'^\d+ km/h$'), (0, 250)),
    "Sonne": (re.compile(r'^\d+\.\d h$'), (0, 24)),
    "Wolken": (re.compile(r'^\d+%$'), (0, 100)),
    "UV max": (re.compile(r'^\d+$'), (0, 16)),
    # -- mit #1404 ergaenzt (vorher stillschweigend ungeprueft) --------------
    "Regen": (re.compile(r'^\d+\.\d mm$'), (0, 300)),
    "Regenwahrscheinlichkeit": (re.compile(r'^\d+%$'), (0, 100)),
    # Sicht: Modelle deckeln die Sichtweite meist weit darunter; 100 km ist
    # grosszuegig, aber nicht mehr sinnfrei (#1404 PO-Vorgabe).
    "Sicht min": (re.compile(r'^\d+\.\d km$'), (0, 100)),
    "Schneehöhe": (re.compile(r'^\d+ cm$'), (0, 1000)),
    "Neuschnee": (re.compile(r'^\d+ cm$'), (0, 300)),
    "Temp min": (re.compile(r'^-?\d+°C$'), (-40, 55)),
    "Böen": (re.compile(r'^\d+ km/h$'), (0, 300)),
    # CAPE: Obergrenze bewusst weit (#1404 PO-Vorgabe). Extreme
    # Superzellen-Umgebungen erreichen 6000+ J/kg -- eine engere Grenze wuerde
    # einen ECHTEN Extremwert als unplausibel melden. Diese Schwelle soll
    # Tippfehler und Einheitenfehler fangen, keine Gewitterlage bewerten.
    "CAPE": (re.compile(r'^\d+ J/kg$'), (0, 10000)),
    "Nullgradgrenze": (re.compile(r'^\d+ m$'), (0, 6000)),
    "Windrichtung": (re.compile(r'^\d+ °$'), (0, 360)),
    # Windchill unterschreitet die Lufttemperatur -> untere Grenze weiter als
    # bei "Temp min".
    "Gefühlte Temp. min": (re.compile(r'^-?\d+°C$'), (-50, 50)),
    "Gefühlte Temp. max": (re.compile(r'^-?\d+°C$'), (-50, 55)),
    "Wolken tief": (re.compile(r'^\d+%$'), (0, 100)),
    "Wolken mittel": (re.compile(r'^\d+%$'), (0, 100)),
    "Wolken hoch": (re.compile(r'^\d+%$'), (0, 100)),
    "Luftfeuchtigkeit Ø": (re.compile(r'^\d+%$'), (0, 100)),
    "Taupunkt Ø": (re.compile(r'^-?\d+°C$'), (-40, 35)),
    # Luftdruck: deckt Meereshoehe UND hochalpine Stationsdruecke ab, daher
    # breit -- entsprechend schwacher Waechter (Spec, Known Limitations).
    "Luftdruck Ø": (re.compile(r'^\d+ hPa$'), (500, 1085)),
    "Schneefallgrenze": (re.compile(r'^\d+ m$'), (0, 5000)),
}

# Issue #1404 (AC-4): die AUSGESPROCHENE Ausnahme-Menge. Diese drei Zeilen
# tragen keinen Zahlenwert; "keine Pruefung" ist fuer sie richtig -- aber es
# muss ein Wert sein, keine Folge eines fehlenden Dict-Eintrags. Sonst rutscht
# eine kuenftig hinzugefuegte Zeile lautlos in denselben Zustand (Bug-Typ
# #1296/#1324). Vorbild im selben Modul: _OVERVIEW_WARN_LABEL.
#
#   "Amtliche Warnungen"  Warn-Zeile (CV2_METRICS[0], kind="warn"): die Zelle
#                         enthaelt gestapelte Warn-Chips bzw. "—", nie eine
#                         Zahl -- _render_overview_row umgeht _fmt_metric
#                         komplett.
#   "Gewitter"            ThunderLevel-Enum, ueber _fmt_thunder als Wort
#                         gerendert ("mittel"/"hoch"/...). Kein Zahlenformat
#                         moeglich; f"{value:.0f}" wuerde mit TypeError krachen.
#   "Niederschlagsart"    PrecipType-Enum, ueber _fmt_precip_type als Wort
#                         gerendert ("Regen"/"Schnee"/...). Gleiche Lage.
#
# 24 geprueft + 3 ausgenommen = 27 = volle Zeilenzahl von CV2_METRICS; ein
# Test haelt diese Rechnung fest.
_OVERVIEW_NO_CHECK_LABELS = {
    _OVERVIEW_WARN_LABEL,
    "Gewitter",
    "Niederschlagsart",
}


def _extract_rows_from_table_html(table_inner: str) -> List[List[str]]:
    rows = []
    for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_inner, re.DOTALL):
        row_html = row_match.group(1)
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        clean_cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
        rows.append(clean_cells)
    return rows


def extract_table_rows(body: str) -> List[List[str]]:
    """Findet die v2-Uebersichtstabelle ueber ihre erste Datenzeile
    "Amtliche Warnungen" (Issue #1108) -- ersetzt die alte
    class="matrix-table"-Erkennung, die im v2-Renderer nicht mehr existiert."""
    for match in _TABLE_RE.finditer(body):
        rows = _extract_rows_from_table_html(match.group(1))
        if len(rows) >= 2 and rows[1] and rows[1][0].strip() == _OVERVIEW_WARN_LABEL:
            return rows
    return []


def extract_locations(body: str) -> List[str]:
    """Extract location names from comparison table header."""
    rows = extract_table_rows(body)
    if not rows:
        return []

    header = rows[0]
    # First cell is "Metrik", rest are locations with #N prefix
    locations = []
    for cell in header[1:]:
        # Remove #N prefix
        name = re.sub(r'^#\d+\s*', '', cell).strip()
        if name:
            locations.append(name)

    return locations


def _find_location_hour_table(body: str, location_name: str, occurrence: int = 0):
    """Findet die Stundentabelle eines Ortes ueber den vorausgehenden
    "ORT <Name>"-Kopf (_render_location_section, Issue #1108) -- ersetzt die
    alte CSS-Klassen-Erkennung. `occurrence` waehlt bei gleichnamigen Orten
    (Adversary F002) das N-te Vorkommen des Namens statt immer nur das erste.
    Rueckgabe: (Spaltenkoepfe, Datenzeilen) oder None, wenn kein Ort-Kopf
    dieses Vorkommens bzw. keine folgende Tabelle gefunden wird."""
    marker = re.compile(r'>ORT</span>\s*<span[^>]*>' + re.escape(location_name) + r'</span>')
    matches = list(marker.finditer(body))
    if occurrence >= len(matches):
        return None
    match = matches[occurrence]
    # Issue #1150: Suche auf die aktuelle ORT-Sektion begrenzen. Die
    # Stundentabelle eines Ortes steht VOR dem naechsten "ORT <Name>"-Kopf.
    # Ohne diese Grenze wuerde eine fehlende Tabelle faelschlich die Tabelle
    # des naechsten Ortes einsammeln -- ein fehlendes Vorkommen bliebe unerkannt
    # (Erosion der Stundentabellen-Pflicht).
    next_ort = re.search(r'>ORT</span>\s*<span[^>]*>', body[match.end():], re.DOTALL)
    section_end = match.end() + next_ort.start() if next_ort else len(body)
    # Issue #1150 (Fix-Runde 2, Adversary F001): Die Stundentabelle ueber ihr
    # STABILES Merkmal identifizieren -- erste Zelle der Kopfzeile == "Zeit"
    # (Renderer-Vertrag _render_hour_table, "Zeit" ist fest verdrahtete erste
    # Spalte). "Erste <table> nach dem ORT-Kopf" ist unsicher: beim LETZTEN Ort
    # fehlt der Vorwaerts-Bound (kein Folge-ORT-Kopf), section_end == len(body),
    # und bei FEHLENDER Stundentabelle wuerde faelschlich die naechstbeste
    # Tabelle (Legende/Abo-/App-Footer) eingesammelt -> falsche Fehlermeldung
    # statt "nicht gefunden". Legende/Footer haben nie "Zeit" als erste Spalte.
    section = body[match.end():section_end]
    for table_match in re.finditer(r'<table[^>]*>(.*?)</table>', section, re.DOTALL):
        rows = _extract_rows_from_table_html(table_match.group(1))
        if rows and rows[0] and rows[0][0].strip() == "Zeit":
            return rows[0], rows[1:]
    return None


def validate_structure(body: str, hourly_enabled: bool = True) -> List[str]:
    """Validate email structure against the v2-Vertrag (Issue #1108/#1110,
    Spalten-Konfigurierbarkeit #1106, freie Spaltenreihenfolge #1381):
    Uebersichtstabelle (Warn-Zeile + >=1 numerische Zeile), Stundentabellen fuer
    alle gelisteten Orte mit einer gueltigen Teilmenge von ``_HOUR_COLUMNS_V2``
    (Mindestens "Zeit" + 1 Wert-Spalte, keine Fremdspalten, keine Duplikate --
    Reihenfolge frei, aber mail-weit einheitlich), kein Score-/Winner-Vertrag
    mehr."""
    errors: List[str] = []

    rows = extract_table_rows(body)
    if not rows:
        errors.append(
            f"STRUKTUR: Uebersichtstabelle nicht gefunden (erste Datenzeile "
            f"'{_OVERVIEW_WARN_LABEL}' fehlt)"
        )
    elif len(rows) < 2:
        errors.append(
            f"STRUKTUR: Uebersichtstabelle hat nur {len(rows)} Zeile(n), "
            f"erwartet: Warn-Zeile + mindestens 1 numerische Metrik-Zeile"
        )

    locations = extract_locations(body)
    if rows and not locations:
        errors.append("STRUKTUR: Keine Orte in der Uebersichtstabelle-Kopfzeile gefunden")

    # Issue #1107/#1150: bei abgeschalteter Stundenverlauf-Sektion entfaellt
    # die gesamte Pflicht-Pruefung -- eine bewusst abgeschaltete Sektion darf
    # weder Tabellen enthalten noch ist ihr Fehlen ein Fehler. Bei fehlendem
    # Header (Default True) bleibt die Pruefung exakt so streng wie bisher.
    if hourly_enabled:
        # Adversary F002: gleichnamige Orte einzeln pruefen (N-tes Vorkommen statt
        # immer nur das erste) -- sonst wird eine defekte Stundentabelle des
        # zweiten (oder n-ten) gleichnamigen Ortes nie erkannt.
        occurrence_counts: dict = {}
        # Adversary F001 (Fix-Runde 2, Issue #1106): eine Config gilt mail-weit
        # fuer ALLE Orte (render_compare_html hat genau EIN hourly_metrics-Set
        # fuer den gesamten Aufruf). Eine einzelne Stundentabelle, die fuer sich
        # genommen eine gueltige Teilmenge-mit-Reihenfolge ist, aber von den
        # Spalten der uebrigen Orte abweicht, ist trotzdem ein Fehler --
        # Referenz-Spalten = die erste Stundentabelle ohne eigene Struktur-
        # Verletzung.
        reference_cols: list | None = None
        reference_name: str | None = None
        for name in locations:
            occurrence = occurrence_counts.get(name, 0)
            occurrence_counts[name] = occurrence + 1
            table = _find_location_hour_table(body, name, occurrence)
            if table is None:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) nicht gefunden"
                )
                continue
            header_cols, _rows = table
            # Issue #1106: Teilmengen-Pruefung statt Exakt-Vergleich.
            # Mindestspalten-Regel: "Zeit" muss erste Spalte sein UND es muss
            # mindestens eine Wert-Spalte daneben existieren (sonst sinnlose Config).
            if not header_cols or header_cols[0] != "Zeit" or len(header_cols) < 2:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) "
                    f"verletzt die Mindestspalten-Regel (Zeit + mind. 1 Wert-Spalte), "
                    f"Spalten {header_cols}"
                )
                continue
            # Issue #1381: KEINE Reihenfolge-Pruefung gegen _HOUR_COLUMNS_V2 mehr
            # (die Spaltenreihenfolge ist seit #1359 nutzerseitig frei einstellbar;
            # die alte Projektion auf die Kanon-Reihenfolge lehnte korrekte Mails ab
            # und blockierte damit das Renderer-Commit-Gate #811). An ihre Stelle
            # treten zwei ausdrueckliche Pruefungen, die benennen, WELCHE Spalte
            # stoert -- sie halten das, was die Projektion bisher nur als
            # Nebeneffekt leistete. NICHT wieder eine Reihenfolge einbauen.
            unknown_cols = [c for c in header_cols if c not in _HOUR_COLUMNS_V2]
            if unknown_cols:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) "
                    f"enthaelt unbekannte Spalte(n) {unknown_cols} -- zulaessig sind nur "
                    f"{_HOUR_COLUMNS_V2}"
                )
            duplicate_cols = sorted(
                {c for c in header_cols if header_cols.count(c) > 1},
                key=header_cols.index,
            )
            if duplicate_cols:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) "
                    f"enthaelt doppelte Spalte(n) {duplicate_cols} -- jede Spalte darf nur "
                    f"einmal vorkommen, Spalten {header_cols}"
                )
            if unknown_cols or duplicate_cols:
                continue
            # Cross-Location-Konsistenz: erst hier pruefen, da nur individuell
            # gueltige Spaltenlisten als Referenz bzw. Vergleichswert taugen.
            if reference_cols is None:
                reference_cols = header_cols
                reference_name = name
            elif header_cols != reference_cols:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) hat "
                    f"Spalten {header_cols}, weicht von der mail-weiten Spalten-Konfiguration "
                    f"{reference_cols} (Referenz-Ort '{reference_name}') ab"
                )

    score_match = _SCORE_WINNER_RE.search(body)
    if score_match:
        errors.append(
            f"STRUKTUR: Score-/Winner-Sprache im Mail-Body gefunden "
            f"('{score_match.group(0)}') -- im v2-Vertrag unzulaessig"
        )

    return errors


def validate_location_count(body: str, min_expected: int = 3) -> List[str]:
    """Validate number of locations."""
    errors = []

    locations = extract_locations(body)

    if len(locations) < min_expected:
        errors.append(
            f"LOCATIONS: {len(locations)} Locations gefunden, "
            f"erwartet: mindestens {min_expected}"
        )

    return errors


def validate_plausibility(body: str) -> List[str]:
    """v2 (Issue #1108): Wertebereichs-Pruefung der Uebersichtstabellen-
    Metrikzeilen (_OVERVIEW_METRIC_CHECKS -- seit #1404 alle 24 numerischen
    Zeilen, vorher nur 5) statt String-Presence-Check der alten englischen
    Zeilen-Labels (Cloud Cover/Sunny Hours). "—" bleibt als Fehlwert-Fallback
    zulaessig; die 3 nicht-numerischen Zeilen (_OVERVIEW_NO_CHECK_LABELS)
    bleiben ausdruecklich unbewertet."""
    errors = []
    rows = extract_table_rows(body)

    for row in rows[1:]:
        if not row:
            continue
        label = row[0].strip()
        check = _OVERVIEW_METRIC_CHECKS.get(label)
        if check is None:
            continue
        _, (lo, hi) = check
        for i, val in enumerate(row[1:]):
            val = val.strip()
            if val == "—":
                continue
            num_match = re.search(r'-?\d+(\.\d+)?', val)
            if not num_match:
                continue
            num = float(num_match.group(0))
            if not (lo <= num <= hi):
                errors.append(
                    f"PLAUSIBILITÄT: '{label}' Ort {i+1} Wert '{val}' liegt "
                    f"ausserhalb des plausiblen Wertebereichs [{lo}, {hi}]"
                )

    return errors


def validate_format(body: str) -> List[str]:
    """v2 (Issue #1108): Format-Check der Uebersichtstabellen-Metrikzeilen
    (z. B. 'N°C', 'N km/h') statt der alten englischen Zeilen-Labels
    (Wind/Gusts, Sunny Hours). "—" bleibt als Fehlwert-Fallback zulaessig.
    Issue #1404: deckt alle 24 numerischen Zeilen ab (vorher 5); die 3
    nicht-numerischen bleiben ausdruecklich unbewertet."""
    errors = []
    rows = extract_table_rows(body)

    for row in rows[1:]:
        if not row:
            continue
        label = row[0].strip()
        check = _OVERVIEW_METRIC_CHECKS.get(label)
        if check is None:
            continue
        pattern, _ = check
        for i, val in enumerate(row[1:]):
            val = val.strip()
            if val == "—":
                continue
            if not pattern.match(val):
                errors.append(
                    f"FORMAT: '{label}' Ort {i+1} ist '{val}', erwartet Format "
                    f"gemaess '{label}'-Spalte (Muster: {pattern.pattern})"
                )

    return errors


def validate_hourly_table(body: str, time_start: int = 9, time_end: int = 16) -> List[str]:
    """v2 (Issue #1108): Vollstaendigkeits-Check pro Ort (ueber die zugehoerige
    Stundentabelle, _find_location_hour_table) statt globaler String-Presence
    im gesamten Body -- ein fehlender Ort/eine fehlende Stunde ist damit
    eindeutig benennbar."""
    errors = []
    # Issue #1242: Die Zeit-Zelle der Ortsvergleichs-Stundentabelle traegt seit
    # #1237 (PO-Freigabe) nur noch die STUNDE ("09"), nicht mehr "09:00" -- die
    # Spalte wird dadurch schmaler, die Uhrzeit ist aus dem Kontext eindeutig.
    # Der Pruefer muss dasselbe Format erwarten, das der Renderer erzeugt, sonst
    # weist er eine korrekte Mail zurueck. Die Vollstaendigkeits-Semantik bleibt
    # unveraendert: geprueft wird weiterhin PRO ORT, ob jede erwartete Stunde
    # vorkommt (Issue #1108).
    expected_hours = [f"{h:02d}" for h in range(time_start, time_end + 1)]

    # Adversary F002: Vorkommens-Index statt immer nur das erste Vorkommen.
    occurrence_counts: dict = {}
    for name in extract_locations(body):
        occurrence = occurrence_counts.get(name, 0)
        occurrence_counts[name] = occurrence + 1
        table = _find_location_hour_table(body, name, occurrence)
        if table is None:
            continue  # bereits von validate_structure() gemeldet
        _header, data_rows = table
        present_hours = {row[0].strip() for row in data_rows if row}
        missing = [h for h in expected_hours if h not in present_hours]
        if missing:
            errors.append(
                f"STUNDEN-TABELLE: Ort '{name}' (Vorkommen {occurrence + 1}) fehlende "
                f"Stunden: {', '.join(missing)}"
            )

    return errors


def run_validation(
    min_locations: int = 3,
    subject_contains: "str | None" = None,
    max_age_minutes: "int | None" = None,
    ignore_mail_age_reason: "str | None" = None,
) -> Tuple[bool, List[str]]:
    """Run all validations and return (success, errors).

    Issue #1408: reicht Betreffs-Filter und Altersschranke an die Mail-Auswahl
    durch. Ohne die neuen Argumente unveraendertes Verhalten (AC-4), lediglich
    mit aktiver Standard-Altersgrenze."""
    try:
        msg = _fetch_latest_message(
            subject_contains=subject_contains,
            max_age_minutes=max_age_minutes,
            ignore_mail_age_reason=ignore_mail_age_reason,
        )
    except Exception as e:
        return False, [f"FEHLER: E-Mail konnte nicht geladen werden: {e}"]

    body = _extract_html_body(msg)
    # Fehlender Header (Alt-Mails vor diesem Feature) oder Wert != "false"
    # => True (bisheriges strenges Verhalten bleibt der sichere Default).
    hourly_enabled = msg.get("X-GZ-Compare-Hourly-Enabled") != "false"

    all_errors = []

    # Run all validators
    all_errors.extend(validate_structure(body, hourly_enabled=hourly_enabled))
    all_errors.extend(validate_location_count(body, min_locations))
    all_errors.extend(validate_plausibility(body))
    all_errors.extend(validate_format(body))
    all_errors.extend(validate_hourly_table(body))

    return len(all_errors) == 0, all_errors


def main():
    parser = argparse.ArgumentParser(description="E-Mail Spec v4.0 Validator")
    parser.add_argument(
        "--min-locations",
        type=int,
        default=3,
        help="Mindestanzahl erwarteter Locations (default: 3)"
    )
    # Issue #1242: Die Projekt-Konvention (CLAUDE.md, "Mail-Validatoren &
    # Renderer-Gate") verlangt den Aufruf JEDES Mail-Validators mit
    # --mail-type. Die beiden anderen Validatoren kennen das Flag; dieser
    # brach bislang mit Exit 2 ab. Ein falscher Typ wird laut abgelehnt statt
    # still durchgewunken -- ein Validator, der den falschen Mail-Pfad prueft,
    # ist strukturell nie bestehbar und erodiert das Gate.
    parser.add_argument(
        "--mail-type",
        default="compare",
        help="Erwarteter Mail-Typ (nur 'compare' -- dies ist der "
             "Ortsvergleichs-Validator)",
    )
    # Issue #1408: Betreffs-Filter (Vorbild briefing_mail_validator.py, #780)
    # und Altersschranke. Beide optional -- die dokumentierten Aufrufe ohne
    # Argumente bleiben unveraendert lauffaehig (AC-4).
    parser.add_argument(
        "--subject-contains",
        default=None,
        help="Nur eine Mail pruefen, deren Betreff dieses Fragment enthaelt "
             "(waehlt die EIGENE Mail auch dann, wenn eine juengere fremde "
             "Compare-Mail daneben liegt)",
    )
    parser.add_argument(
        "--max-age-minutes",
        type=int,
        default=_DEFAULT_MAX_AGE_MINUTES,
        help=f"Hoechstalter der geprueften Mail in Minuten "
             f"(default: {_DEFAULT_MAX_AGE_MINUTES})",
    )
    parser.add_argument(
        "--ignore-mail-age",
        metavar="GRUND",
        default=None,
        help="Altersschranke bewusst abschalten -- verlangt eine nicht-leere "
             "Begruendung, die im Validator-Log landet",
    )
    args = parser.parse_args()

    # Fail-fast, analog `qa_gate.py --no-visual "<Grund>"`: der Schutz laesst
    # sich nicht versehentlich (und nicht wortlos) abschalten.
    if args.ignore_mail_age is not None and not args.ignore_mail_age.strip():
        print(
            "FEHLER: --ignore-mail-age verlangt eine nicht-leere Begruendung "
            '(z.B. --ignore-mail-age "Altfall, Mail bewusst manuell geprueft"). '
            "Ohne Grund bleibt die Altersschranke aktiv."
        )
        sys.exit(2)

    # Adversary F001: dieselbe Grenze wie in _check_selection_arguments, hier
    # nur fuer eine freundliche Meldung statt eines Traceback-Umwegs. Die
    # verbindliche Pruefung sitzt in der Funktion.
    if args.max_age_minutes > _MAX_AGE_CEILING_MINUTES:
        print(
            f"FEHLER: --max-age-minutes={args.max_age_minutes} ueberschreitet das "
            f"Maximum von {_MAX_AGE_CEILING_MINUTES} Minuten (24 Stunden). Eine "
            f"beliebig grosse Grenze waere eine stille Abschaltung der "
            f"Altersschranke ohne Begruendung -- {_IGNORE_AGE_HINT}."
        )
        sys.exit(2)

    if args.mail_type != "compare":
        print(
            f"FEHLER: --mail-type={args.mail_type!r} -- dies ist der "
            "Ortsvergleichs-Validator (X-GZ-Mail-Type: compare). Fuer "
            "Trip-Briefings: briefing_mail_validator.py, fuer amtliche "
            "Warnungen: official_alert_mail_validator.py."
        )
        sys.exit(2)

    print("=" * 70)
    print("E-MAIL SPEC v4.0 COMPLIANCE VALIDATOR")
    print("=" * 70)
    print()

    success, errors = run_validation(
        args.min_locations,
        subject_contains=args.subject_contains,
        max_age_minutes=args.max_age_minutes,
        ignore_mail_age_reason=args.ignore_mail_age,
    )

    # Issue #465 (B2): Strukturiertes Log VOR sys.exit() schreiben (fail-soft).
    # Issue #1408 (AC-5): Zustand der Altersschranke immer mitschreiben.
    _write_validation_log(
        success=success,
        errors=errors,
        min_locations=args.min_locations,
        max_age_minutes=args.max_age_minutes,
        ignore_mail_age_reason=args.ignore_mail_age,
    )

    if success:
        print("✅ ALLE SPEC-ANFORDERUNGEN ERFÜLLT!")
        print()
        print("Du darfst jetzt 'E2E Test bestanden' sagen.")
        sys.exit(0)
    else:
        print("❌ SPEC-VERLETZUNGEN GEFUNDEN:")
        print()
        for error in errors:
            print(f"  • {error}")
        print()
        print("=" * 70)
        print("⛔ DU DARFST NICHT 'E2E TEST BESTANDEN' SAGEN!")
        print("   Behebe zuerst alle Fehler und führe den Validator erneut aus.")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
