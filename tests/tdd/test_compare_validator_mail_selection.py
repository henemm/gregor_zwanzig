"""#1124 Teil B — Compare-Validator waehlt Mail per Marker-Header + BODY.PEEK.

RED-Phase: `email_spec_validator._fetch_latest_message()` nimmt aktuell blind
`all_ids[-1]` (die schlicht neueste Mail, ohne den Marker-Header zu pruefen) und
fetcht mit `(RFC822)` — was die gepruefte Mail als gelesen (`\\Seen`) markiert.

Diese Tests belegen das gewuenschte Verhalten aus Nutzersicht:

- AC-1/AC-2/AC-3 gegen die herausgeloeste, rein deterministische Auswahl-Logik
  `_select_compare_uid(...)` (existiert in RED noch nicht -> AttributeError bzw.
  Assertion-Fehler). Eingabe sind AUFGEZEICHNETE Header-Bytes, wie IMAP sie bei
  `BODY.PEEK[HEADER]` liefert (RFC822-Header-Block, CRLF-terminiert). Kein Mock,
  kein Patch — echter email-Parser.
- AC-4 gegen einen duck-typed IMAP-Fake (echte kleine Klasse, KEIN Mock-Framework),
  der jedes `fetch`-Kommando mitschreibt. `_fetch_latest_message(imap=<fake>)`
  (Injektions-Seam existiert in RED noch nicht -> TypeError) muss ALLE Fetches per
  `BODY.PEEK` machen, NIE per `RFC822`.

Seam/Interface, das diese Tests vom kuenftigen Code erzwingen:
  * `_select_compare_uid(candidates)` — `candidates` = geordnete Liste von
    `(uid: bytes, header_bytes: bytes)` in IMAP-Suchreihenfolge (aeltest -> neuest,
    wie `imap.search`-Rueckgabe). Rueckgabe: die UID der NEUESTEN Mail mit
    `X-GZ-Mail-Type: compare`. Keine solche Mail -> ValueError mit klarer Meldung,
    die "X-GZ-Mail-Type: compare" nennt.
  * `_fetch_latest_message(imap=None, ...)` — optionaler Injektions-Seam: wird eine
    fertige (duck-typed) IMAP-Verbindung uebergeben, nutzt der Helfer sie direkt
    (kein Settings/Credential-Bedarf) und fetcht ausschliesslich per BODY.PEEK.
"""

from __future__ import annotations

import email
import imaplib
import importlib.util
import re
import shlex
import subprocess
import sys
import time
from email.utils import formatdate
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"


def _load_validator():
    """Laedt den Validator als isoliertes Modul (vermeidet sys.modules-
    Kontamination), analog test_issue_1150::_load_validator. Der Modul-Top-Level
    importiert nur stdlib -> kein IMAP/kein Settings beim Laden."""
    spec = importlib.util.spec_from_file_location("esv1124", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _header_bytes(
    mail_type: "str | None",
    subject: str = "Test",
    date_header: "str | None" = None,
) -> bytes:
    """Baut einen echten RFC822-Header-Block, wie IMAP ihn bei
    `BODY.PEEK[HEADER]` liefert: Header-Zeilen, CRLF-getrennt, mit leerer
    Trennzeile am Ende. `mail_type=None` -> gar kein X-GZ-Mail-Type-Header.

    `date_header` (#1408 AC-6) setzt den absenderseitigen `Date:`-Header. Er
    dient als Koeder: ist er gesetzt und frisch, waere ein stiller Rueckfall
    auf ihn (statt der serverseitigen INTERNALDATE) unsichtbar erfolgreich —
    genau das muss der Test ausschliessen koennen."""
    lines = [f"Subject: {subject}"]
    if mail_type is not None:
        lines.append(f"X-GZ-Mail-Type: {mail_type}")
    if date_header is not None:
        lines.append(f"Date: {date_header}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")


# ---------------------------------------------------------------------------
# AC-1 — neueste Mail ohne compare-Header, aeltere MIT compare -> waehle die
# aeltere (echte compare-Mail), nicht die neuere Nicht-compare-Mail.
# ---------------------------------------------------------------------------


def test_ac1_picks_older_compare_over_newer_non_compare():
    """Given ein Postfach, in dem die neueste Mail KEINEN
    `X-GZ-Mail-Type: compare` traegt (Warn-Mail obenauf), eine aeltere aber schon
    / When die Auswahl-Logik greift / Then waehlt sie die aeltere compare-Mail,
    NICHT die neuere Nicht-compare-Mail."""
    mod = _load_validator()

    # IMAP-Reihenfolge: aeltest -> neuest (wie imap.search).
    candidates = [
        (b"1", _header_bytes("compare", subject="Ortsvergleich")),
        (b"2", _header_bytes(None, subject="Amtliche Warnung")),  # neueste, kein Marker
    ]

    selected = mod._select_compare_uid(candidates)
    assert selected == b"1", (
        "Die neueste Mail traegt keinen compare-Header; gewaehlt werden muss die "
        f"aeltere compare-Mail (uid b'1'), nicht die neuere Warn-Mail, bekommen: {selected!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — mehrere compare-Mails -> die neueste (juengste UID) davon.
# ---------------------------------------------------------------------------


def test_ac2_picks_newest_of_multiple_compare_mails():
    """Given mehrere Mails mit `X-GZ-Mail-Type: compare` / When die Auswahl
    greift / Then waehlt sie die NEUESTE davon (juengste UID in IMAP-Reihenfolge),
    nicht eine aeltere compare-Mail."""
    mod = _load_validator()

    candidates = [
        (b"1", _header_bytes("compare", subject="alte Compare-Mail")),
        (b"2", _header_bytes(None, subject="Warn-Mail dazwischen")),
        (b"3", _header_bytes("compare", subject="frische Compare-Mail")),
    ]

    selected = mod._select_compare_uid(candidates)
    assert selected == b"3", (
        "Bei mehreren compare-Mails muss die neueste (uid b'3') gewaehlt werden, "
        f"nicht eine aeltere compare-Mail, bekommen: {selected!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — keine compare-Mail -> lauter Fehler statt stiller Fehlprüfung.
# ---------------------------------------------------------------------------


def test_ac3_no_compare_mail_raises_clear_error():
    """Given ein Postfach OHNE jede compare-Mail / When die Auswahl versucht wird
    / Then bricht sie mit klarem Fehler ab, dessen Meldung
    'X-GZ-Mail-Type: compare' nennt — statt still eine Nicht-compare-Mail zu
    waehlen."""
    mod = _load_validator()

    candidates = [
        (b"1", _header_bytes(None, subject="Warn-Mail")),
        (b"2", _header_bytes("trip-briefing", subject="Trip-Briefing")),
        (b"3", _header_bytes("radar-alert", subject="Radar-Alarm")),
    ]

    with pytest.raises(ValueError) as excinfo:
        mod._select_compare_uid(candidates)

    msg = str(excinfo.value)
    assert "X-GZ-Mail-Type: compare" in msg, (
        f"Fehlermeldung muss den erwarteten Marker 'X-GZ-Mail-Type: compare' "
        f"nennen, bekommen: {msg!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Voll-Fetch per BODY.PEEK (kein RFC822 -> kein \\Seen-Flag).
# ---------------------------------------------------------------------------


NO_INTERNALDATE = object()
"""Sentinel (#1408 AC-6): der Server liefert fuer diese Mail KEINEN
auswertbaren `INTERNALDATE`-Bestandteil in der Fetch-Antwort."""


class _RecordingIMAPFake:
    """Duck-typed IMAP-Verbindung (KEIN Mock-Framework). Implementiert die vom
    Validator genutzten Kommandos und schreibt jedes `fetch`-Kommando in
    `self.fetched` mit.

    `mails` ist eine geordnete Liste in IMAP-Reihenfolge (aeltest -> neuest,
    wie ``imap.search`` sie liefert). Jeder Eintrag ist eines von:

      * ``(uid: bytes, mail_type: str | None)`` — Mail ist frisch (Alter 0 min)
      * ``(uid, mail_type, age_minutes: float)`` — Mail ist `age_minutes` alt
      * ``(uid, mail_type, age_minutes, date_header: str | None)``

    ``age_minutes`` darf ``NO_INTERNALDATE`` sein: dann traegt die Fetch-Antwort
    dieser uid GAR KEINEN Server-Zeitstempel (#1408 AC-6).

    Das Antwortformat bildet die echte IMAP-Form nach: der erste Teil des
    Fetch-Tupels ist die Praefix-Zeile, in der der Server ``INTERNALDATE "..."``
    mitliefert (Zeitstring ueber ``imaplib.Time2Internaldate`` erzeugt, nicht
    handgeschrieben). Genau diese Zeile ist es, die ``imaplib.Internaldate2tuple``
    auswertet.

    Default: uid b'1' Nicht-compare, uid b'2' compare (neueste), beide frisch."""

    def __init__(self, mails=None):
        if mails is None:
            mails = [(b"1", None), (b"2", "compare")]

        normalized = []
        for entry in mails:
            uid, mail_type = entry[0], entry[1]
            age = entry[2] if len(entry) > 2 else 0.0
            date_header = entry[3] if len(entry) > 3 else None
            normalized.append((uid, mail_type, age, date_header))

        # Rueckwaertskompatibel: bestehende Tests lesen `self.mails` als
        # (uid, mail_type)-Paare.
        self.mails = [(uid, mt) for uid, mt, _age, _dh in normalized]
        self.fetched: list = []
        self.selected: "str | None" = None

        self._headers = {}
        self._full = {}
        self._internaldate = {}
        now = time.time()
        for uid, mt, age, date_header in normalized:
            self._headers[uid] = _header_bytes(
                mt, subject=f"Mail {uid.decode()}", date_header=date_header
            )
            lines = [f"Subject: Mail {uid.decode()}"]
            if mt is not None:
                lines.append(f"X-GZ-Mail-Type: {mt}")
            if date_header is not None:
                lines.append(f"Date: {date_header}")
            body = "\r\n".join(lines) + "\r\n\r\n<html><body><table></table></body></html>"
            self._full[uid] = body.encode("utf-8")
            if age is NO_INTERNALDATE:
                self._internaldate[uid] = None
            else:
                # imaplib.Time2Internaldate liefert '"28-Jul-2026 09:00:00 +0000"'
                self._internaldate[uid] = imaplib.Time2Internaldate(now - float(age) * 60.0)

    def header_fetch_count(self) -> int:
        """Anzahl der reinen Header-Fetches (BODY.PEEK[HEADER])."""
        n = 0
        for _uid, spec in self.fetched:
            spec_str = spec if isinstance(spec, str) else str(spec)
            if "HEADER" in spec_str.upper():
                n += 1
        return n

    def login(self, user, password):  # pragma: no cover - vom Seam evtl. ungenutzt
        return ("OK", [b"logged in"])

    def select(self, mailbox="INBOX"):
        self.selected = mailbox
        return ("OK", [str(len(self.mails)).encode()])

    def search(self, charset, *criteria):
        ids = b" ".join(uid for uid, _mt in self.mails)
        return ("OK", [ids])

    def fetch(self, uid, message_parts):
        self.fetched.append((uid, message_parts))
        spec = message_parts.upper() if isinstance(message_parts, str) else str(message_parts)
        if "HEADER" in spec:
            payload = self._headers.get(uid, b"\r\n\r\n")
            item = b"BODY[HEADER]"
        else:
            payload = self._full.get(uid, b"\r\n\r\n")
            item = b"BODY[]"

        internaldate = self._internaldate.get(uid)
        prefix = uid + b" ("
        if internaldate is not None:
            prefix += b"INTERNALDATE " + internaldate.encode("ascii") + b" "
        prefix += item + b" {" + str(len(payload)).encode("ascii") + b"}"
        return ("OK", [(prefix, payload)])

    def close(self):
        return ("OK", [b"closed"])

    def logout(self):
        return ("BYE", [b"bye"])


def test_ac4_full_fetch_uses_body_peek_not_rfc822():
    """Given der Validator holt eine Mail zur Pruefung / When er sie per IMAP
    fetcht (via injizierten duck-typed Fake) / Then verwenden ALLE Fetch-Kommandos
    `BODY.PEEK`, KEINES `RFC822` — das \\Seen-Flag der geprueften Mail bleibt
    unberuehrt.

    In RED schlaegt das fehl: `_fetch_latest_message` kennt den `imap`-Seam nicht
    (TypeError) bzw. fetcht die Treffer-Mail mit `(RFC822)`.
    """
    mod = _load_validator()
    fake = _RecordingIMAPFake()

    msg = mod._fetch_latest_message(imap=fake)

    assert fake.fetched, "Es muss mindestens ein IMAP-Fetch stattgefunden haben"

    for uid, spec in fake.fetched:
        spec_str = spec if isinstance(spec, str) else str(spec)
        assert "BODY.PEEK" in spec_str.upper(), (
            f"Fetch von uid {uid!r} nutzt {spec_str!r} — erwartet BODY.PEEK "
            f"(setzt kein \\Seen), alle Fetches: {fake.fetched}"
        )
        assert "RFC822" not in spec_str.upper(), (
            f"Fetch von uid {uid!r} nutzt RFC822 ({spec_str!r}) — das markiert die "
            f"Mail als gelesen und ist verboten, alle Fetches: {fake.fetched}"
        )

    # Der Voll-Fetch muss die compare-Mail (uid b'2') geliefert haben.
    assert msg.get("X-GZ-Mail-Type") == "compare", (
        f"_fetch_latest_message muss die compare-Mail (uid b'2') zurueckgeben, "
        f"bekommen X-GZ-Mail-Type={msg.get('X-GZ-Mail-Type')!r}"
    )

    # Newest-first Frueh-Abbruch: die compare-Mail IST die juengste (uid b'2'),
    # also darf genau EIN Header-Fetch noetig gewesen sein (nicht alle Header
    # vorab laden).
    assert fake.header_fetch_count() == 1, (
        f"Bei compare == juengste Mail darf nur EIN Header-Fetch stattfinden "
        f"(lazy Frueh-Abbruch), bekommen: {fake.header_fetch_count()} "
        f"(Fetches: {fake.fetched})"
    )


def test_f001_deep_compare_mail_found_without_window_cap():
    """F001-Regression: Auf dem GETEILTEN Postfach kann die einzige Compare-Mail
    tief unter vielen frischeren Nicht-Compare-Mails liegen. Given 100 Mails, von
    denen NUR uid b'5' eine compare-Mail ist (95 neuere Nicht-Compare-Mails
    darueber) / When `_fetch_latest_message(imap=fake)` laeuft / Then wird die
    tiefe Compare-Mail trotzdem gefunden (kein festes Scan-Fenster, kein
    faelschlicher AC-3-Fehler). Ein 50er-Cap (all_ids[-50:]) haette sie
    verpasst."""
    mod = _load_validator()

    mails = []
    for i in range(1, 101):  # uid b'1' .. b'100', aeltest -> neuest
        uid = str(i).encode()
        mail_type = "compare" if i == 5 else None
        mails.append((uid, mail_type))
    fake = _RecordingIMAPFake(mails=mails)

    msg = mod._fetch_latest_message(imap=fake)

    assert msg.get("X-GZ-Mail-Type") == "compare", (
        "Die tief liegende Compare-Mail (uid b'5' von 100) muss ohne Fenster-Cap "
        f"gefunden werden, bekommen X-GZ-Mail-Type={msg.get('X-GZ-Mail-Type')!r}"
    )

    # Beweis, dass KEIN 50er-Fenster mehr existiert: um uid b'5' zu erreichen,
    # muss newest-first ueber die 95 frischeren Mails hinaus gescannt worden sein
    # (> 50 Header-Fetches). Ein Cap haette hier bei 50 gestoppt und AC-3 gemeldet.
    assert fake.header_fetch_count() > 50, (
        f"Um die tiefe Compare-Mail zu finden, muss ueber ein 50er-Fenster hinaus "
        f"gescannt worden sein, Header-Fetches: {fake.header_fetch_count()}"
    )

    # Alle Fetches bleiben BODY.PEEK (kein \Seen), auch beim tiefen Scan.
    for uid, spec in fake.fetched:
        spec_str = spec if isinstance(spec, str) else str(spec)
        assert "BODY.PEEK" in spec_str.upper() and "RFC822" not in spec_str.upper(), (
            f"Fetch von uid {uid!r} nutzt {spec_str!r} — erwartet BODY.PEEK, nie RFC822"
        )


def test_ac3_full_mailbox_scan_before_error():
    """AC-3 bleibt bei No-Window: Given ein Postfach OHNE jede compare-Mail /
    When `_fetch_latest_message(imap=fake)` laeuft / Then wird das GESAMTE
    Postfach gescannt und erst dann ValueError erhoben (Meldung nennt
    'X-GZ-Mail-Type: compare')."""
    mod = _load_validator()

    mails = [(str(i).encode(), None) for i in range(1, 61)]  # 60 Nicht-Compare
    fake = _RecordingIMAPFake(mails=mails)

    with pytest.raises(ValueError) as excinfo:
        mod._fetch_latest_message(imap=fake)

    assert "X-GZ-Mail-Type: compare" in str(excinfo.value), (
        f"AC-3-Fehlermeldung muss den Marker nennen, bekommen: {excinfo.value!r}"
    )
    # Es wurde das ganze Postfach gescannt (alle 60 Header), nicht nur ein Fenster.
    assert fake.header_fetch_count() == 60, (
        f"Ohne Treffer muss das GESAMTE Postfach gescannt werden (60 Header), "
        f"bekommen: {fake.header_fetch_count()}"
    )


# ===========================================================================
# Issue #1408 — der Pruefer sucht die eigene Mail NAMENTLICH und lehnt eine
# nicht belastbar datierte oder zu alte Mail hoerbar ab.
# Spec: docs/specs/modules/fix_1408_validator_betrefffilter.md
# ===========================================================================

_SUBJECT_FRAGMENT = "gz-1408-eigene-sitzung"


def _numbers_in(text: str) -> list:
    return [int(n) for n in re.findall(r"\d+", text)]


# ---------------------------------------------------------------------------
# #1408 AC-1 — benannte (aeltere) Mail schlaegt juengere fremde compare-Mail.
# ---------------------------------------------------------------------------


def test_subject_filter_picks_named_mail_over_newer_foreign_compare():
    """Given zwei Mails tragen denselben Compare-Marker, aber nur die AELTERE
    traegt das gesuchte Betreffs-Fragment (die juengere stammt aus einer
    parallelen Sitzung) / When der Pruefer namentlich sucht / Then waehlt er die
    benannte, aeltere Mail — nicht die juengere fremde."""
    mod = _load_validator()

    candidates = [
        (b"1", _header_bytes("compare", subject=f"Ortsvergleich {_SUBJECT_FRAGMENT}")),
        (b"2", _header_bytes("compare", subject="Ortsvergleich fremde Sitzung")),
    ]

    selected = mod._select_compare_uid(candidates, subject_contains=_SUBJECT_FRAGMENT)
    assert selected == b"1", (
        "Gesucht war die namentlich benannte Mail (uid b'1'); die juengere fremde "
        f"compare-Mail (uid b'2') darf sie nicht verdraengen, bekommen: {selected!r}"
    )


# ---------------------------------------------------------------------------
# #1408 AC-2 — benannte Mail fehlt -> hoerbarer Abbruch, Meldung nennt Marker
#              UND Betreffs-Fragment.
# ---------------------------------------------------------------------------


def test_missing_named_mail_error_names_marker_and_subject_fragment():
    """Given keine Mail erfuellt Marker UND Betreffs-Fragment gleichzeitig /
    When der Pruefer danach sucht / Then bricht er mit ValueError ab, dessen
    Meldung BEIDES nennt — statt still die naechstbeste compare-Mail zu
    nehmen."""
    mod = _load_validator()

    candidates = [
        (b"1", _header_bytes("compare", subject="Ortsvergleich fremde Sitzung A")),
        (b"2", _header_bytes("compare", subject="Ortsvergleich fremde Sitzung B")),
        (b"3", _header_bytes(None, subject="Warn-Mail")),
    ]

    with pytest.raises(ValueError) as excinfo:
        mod._select_compare_uid(candidates, subject_contains=_SUBJECT_FRAGMENT)

    msg = str(excinfo.value)
    assert "X-GZ-Mail-Type: compare" in msg, (
        f"Meldung muss den erwarteten Marker nennen, bekommen: {msg!r}"
    )
    assert _SUBJECT_FRAGMENT in msg, (
        "Meldung muss auch das gesuchte Betreffs-Fragment nennen (sonst bleibt "
        f"unklar, WONACH gesucht wurde), bekommen: {msg!r}"
    )


# ---------------------------------------------------------------------------
# #1408 AC-3 — Mail aelter als die Grenze -> abgelehnt, Meldung nennt Alter
#              und Grenze.
# ---------------------------------------------------------------------------


def test_mail_older_than_age_limit_is_rejected_naming_age_and_limit():
    """Given die einzige compare-Mail wurde vom Server vor 180 Minuten
    zugestellt, die Grenze liegt bei 30 Minuten / When der Pruefer sie waehlt /
    Then lehnt er sie ab, obwohl ihr Inhalt fehlerfrei waere — die Meldung nennt
    Alter und Grenze, damit das Rot nicht raetselhaft ist."""
    mod = _load_validator()

    fake = _RecordingIMAPFake(mails=[(b"1", None), (b"2", "compare", 180.0)])

    with pytest.raises(ValueError) as excinfo:
        mod._fetch_latest_message(imap=fake, max_age_minutes=30)

    msg = str(excinfo.value)
    numbers = _numbers_in(msg)
    assert 30 in numbers, (
        f"Meldung muss die konfigurierte Grenze (30) nennen, bekommen: {msg!r}"
    )
    assert any(170 <= n <= 190 for n in numbers), (
        "Meldung muss das tatsaechliche Alter der Mail (~180 Minuten) nennen, "
        f"bekommen: {msg!r}"
    )
    assert "inut" in msg.lower(), (
        f"Meldung muss die Einheit (Minuten) nennen, bekommen: {msg!r}"
    )


# ---------------------------------------------------------------------------
# #1408 AC-4 — Bestandsschutz: Aufruf ohne die neuen Argumente.
# ---------------------------------------------------------------------------


def test_call_without_new_arguments_behaves_as_before():
    """Given eine frische compare-Mail und ein Aufruf OHNE die neuen Argumente /
    When der Pruefer laeuft / Then liefert er dieselbe Mail wie bisher, per
    BODY.PEEK und mit genau EINEM Header-Fetch (identisch zu
    test_ac4_full_fetch_uses_body_peek_not_rfc822)."""
    mod = _load_validator()
    fake = _RecordingIMAPFake()

    msg = mod._fetch_latest_message(imap=fake)

    assert msg.get("X-GZ-Mail-Type") == "compare", (
        "Ohne neue Argumente muss weiterhin die compare-Mail (uid b'2') "
        f"zurueckkommen, bekommen: {msg.get('X-GZ-Mail-Type')!r}"
    )
    assert fake.header_fetch_count() == 1, (
        "Der lazy Frueh-Abbruch darf sich nicht veraendern (genau EIN "
        f"Header-Fetch), bekommen: {fake.header_fetch_count()}"
    )
    for uid, spec in fake.fetched:
        spec_str = spec if isinstance(spec, str) else str(spec)
        assert "BODY.PEEK" in spec_str.upper() and "RFC822" not in spec_str.upper(), (
            f"Fetch von uid {uid!r} nutzt {spec_str!r} — erwartet BODY.PEEK, nie RFC822"
        )


def _documented_invocations() -> list:
    """Liest die drei dokumentierten Aufrufformen aus den Dokumenten, statt sie
    im Test zu erfinden (CLAUDE.md, /e2e-verify, email_formatting.md)."""
    docs = [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / ".claude" / "commands" / "e2e-verify.md",
        REPO_ROOT / ".claude" / "standards" / "email_formatting.md",
    ]
    calls = []
    for doc in docs:
        for line in doc.read_text(encoding="utf-8").splitlines():
            if "email_spec_validator.py" not in line:
                continue
            tail = line.split("email_spec_validator.py", 1)[1]
            tail = re.split(r"[`|&;]", tail, maxsplit=1)[0]
            calls.append((doc.name, shlex.split(tail)))
    return calls


def test_documented_invocations_still_accepted_by_cli():
    """Given die drei dokumentierten Aufrufe des Pruefers (CLAUDE.md,
    /e2e-verify, email_formatting.md) / When der Pruefer mit genau diesen
    Argumenten aufgerufen wird / Then akzeptiert seine Kommandozeile sie
    weiterhin — ein neues Pflicht-Argument waere ein Bruch.

    `--help` wird angehaengt, damit der Aufruf VOR jedem IMAP-Zugriff endet:
    argparse verarbeitet die Argumente der Reihe nach, ein unbekanntes Argument
    wuerde vor `--help` mit Exit 2 abbrechen."""
    calls = _documented_invocations()
    assert len(calls) == 3, (
        f"Erwartet werden die drei dokumentierten Aufrufe, gefunden: {calls}"
    )

    for doc_name, args in calls:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH)] + args + ["--help"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, (
            f"Der in {doc_name} dokumentierte Aufruf {args} wird nicht mehr "
            f"akzeptiert (Exit {result.returncode}).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# #1408 AC-5 — abgeschaltete Altersschranke steht mit Begruendung im Log;
#              ein leerer Grund wird abgelehnt.
# ---------------------------------------------------------------------------


def test_validation_log_records_age_guard_reason_in_plain_text(tmp_path):
    """Given die Altersschranke wurde fuer einen bewusst geprueften Altfall
    ueber `--ignore-mail-age "<Grund>"` ausgeschaltet / When der Lauf
    abgeschlossen ist / Then traegt das geschriebene Validator-Log den Grund im
    Klartext (nicht nur true/false) und die konfigurierte Grenze."""
    mod = _load_validator()
    log_dir = tmp_path / "_log"
    log_dir.mkdir(parents=True)

    reason = "Altfall #1408: Mail stammt aus dem Nachweislauf von gestern, bewusst geprueft"

    mod._write_validation_log(
        success=True,
        errors=[],
        min_locations=3,
        log_dir=log_dir,
        workflow_id="fix-1408-validator-betrefffilter",
        max_age_minutes=60,
        ignore_mail_age_reason=reason,
    )

    yaml_files = list(log_dir.glob("*_email_validation.yaml"))
    assert len(yaml_files) == 1, (
        f"Genau ein Validator-Log erwartet, gefunden: {[p.name for p in yaml_files]}"
    )

    data = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
    assert "ignore_mail_age_reason" in data, (
        f"Das Log muss die abgeschaltete Schranke sichtbar machen, Felder: {sorted(data)}"
    )
    assert data["ignore_mail_age_reason"] == reason, (
        "Der Grund muss im Klartext im Log stehen (nicht nur true/false), "
        f"bekommen: {data['ignore_mail_age_reason']!r}"
    )
    assert data.get("max_age_minutes") == 60, (
        f"Das Log muss die konfigurierte Altersgrenze tragen, bekommen: {data.get('max_age_minutes')!r}"
    )


def test_empty_ignore_mail_age_reason_is_rejected():
    """Given der Schalter zum Abschalten der Altersschranke wird ohne
    Begruendung gesetzt / When der Pruefer startet / Then bricht er sofort mit
    einem klaren Fehler ab, der die fehlende Begruendung benennt — der Schutz
    laesst sich nicht versehentlich abschalten."""
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--ignore-mail-age", ""],
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = (result.stdout + result.stderr).lower()

    assert result.returncode != 0, (
        "Ein leerer Grund darf nicht durchgehen.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert not any(
        marker in combined
        for marker in ("unrecognized argument", "unbekanntes argument", "no such option")
    ), (
        "Der Schalter --ignore-mail-age muss existieren; der Abbruch darf nicht "
        f"daher kommen, dass argparse ihn gar nicht kennt.\nAusgabe: {combined!r}"
    )
    assert any(marker in combined for marker in ("grund", "begründ", "begruend")), (
        "Die Fehlermeldung muss sagen, dass eine Begruendung fehlt.\n"
        f"Ausgabe: {combined!r}"
    )


# ---------------------------------------------------------------------------
# #1408 AC-6 — keine belastbare Server-Zeit -> hoerbarer Abbruch, KEIN
#              Ausweichen auf den absenderseitigen Date-Header.
# ---------------------------------------------------------------------------


def test_missing_internaldate_aborts_and_ignores_fresh_date_header():
    """Given der Server liefert fuer die gewaehlte compare-Mail keinen
    auswertbaren `INTERNALDATE`-Bestandteil, die Mail traegt aber einen
    GUELTIGEN und FRISCHEN `Date`-Header (2 Minuten alt, weit innerhalb der
    60-Minuten-Grenze) / When der Pruefer ihr Alter bestimmen will / Then
    verweigert er die Arbeit hoerbar und nennt den fehlenden Server-Zeitstempel.

    Der frische Date-Header ist der eigentliche Beweis: weicht die Umsetzung
    still auf ihn aus, gilt die Mail als frisch und der Fetch gelingt — dieser
    Test wuerde dann NICHT bestehen. Er besteht nur, wenn die absenderseitige
    Zeitangabe ignoriert wird."""
    mod = _load_validator()

    fresh_date = formatdate(time.time() - 120, localtime=False)
    fake = _RecordingIMAPFake(
        mails=[
            (b"1", None),
            (b"2", "compare", NO_INTERNALDATE, fresh_date),
        ]
    )

    with pytest.raises(ValueError) as excinfo:
        mod._fetch_latest_message(imap=fake, max_age_minutes=60)

    msg = str(excinfo.value)
    assert any(
        marker in msg.lower()
        for marker in ("internaldate", "server-zeit", "serverzeit", "server-zeitstempel", "zeitstempel")
    ), (
        "Die Meldung muss den fehlenden serverseitigen Zeitstempel als Grund "
        f"benennen, bekommen: {msg!r}"
    )


# ---------------------------------------------------------------------------
# #1408 F001 (Adversary, HIGH) — die Altersschranke darf sich nicht ueber einen
# absurd hohen Zahlenwert still abschalten lassen. Genau diese Umkehr ueber
# eine Zahl sollte der begruendungspflichtige Schalter verhindern; sie war
# ueber `--max-age-minutes` weiterhin offen (999999999 => `age > grenze` nie
# erfuellbar, ohne Grund, ohne Log-Spur).
# ---------------------------------------------------------------------------


def test_age_limit_cannot_be_stretched_into_a_silent_shutdown(tmp_path):
    """Given eine 180 Minuten alte Compare-Mail / When jemand die Altersgrenze
    auf einen absurd hohen Wert setzt, statt die Schranke begruendet
    abzuschalten / Then wird der Wert abgelehnt und auf den
    begruendungspflichtigen Weg verwiesen.

    Und: Given eine abweichende, aber zulaessige Grenze / When der Lauf
    protokolliert wird / Then ist die Abweichung im Log erkennbar — sonst
    verschoebe sich die stille Umgehung nur von 'unendlich' auf '1439'."""
    mod = _load_validator()

    # --- Teil 1: oberhalb der Obergrenze -> hoerbare Ablehnung ---------------
    fake = _RecordingIMAPFake(mails=[(b"1", None), (b"2", "compare", 180.0)])

    with pytest.raises(ValueError) as excinfo:
        mod._fetch_latest_message(imap=fake, max_age_minutes=999999999)

    msg = str(excinfo.value)
    assert "1440" in msg, (
        f"Die Meldung muss die Obergrenze (1440 Minuten = 24 Stunden) nennen, "
        f"bekommen: {msg!r}"
    )
    assert "ignore-mail-age" in msg, (
        "Die Meldung muss auf den begruendungspflichtigen Weg "
        f"(--ignore-mail-age \"<Grund>\") verweisen, bekommen: {msg!r}"
    )

    # --- Teil 2: abweichende, zulaessige Grenze steht im Log -----------------
    abweichend = tmp_path / "abweichend"
    abweichend.mkdir(parents=True)
    mod._write_validation_log(
        success=True,
        errors=[],
        min_locations=3,
        log_dir=abweichend,
        workflow_id="fix-1408-validator-betrefffilter",
        max_age_minutes=300,
        ignore_mail_age_reason=None,
    )
    data = yaml.safe_load(
        next(abweichend.glob("*_email_validation.yaml")).read_text(encoding="utf-8")
    )
    assert data.get("max_age_minutes") == 300, (
        f"Der benutzte Wert muss im Log stehen, bekommen: {data.get('max_age_minutes')!r}"
    )
    assert data.get("max_age_minutes_overridden") is True, (
        "Eine vom Standard abweichende Altersgrenze muss im Log als Abweichung "
        f"erkennbar sein, Felder: {sorted(data)}"
    )
    assert data.get("max_age_minutes_default") == 60, (
        "Das Log muss den Standardwert mitfuehren, damit die Abweichung ohne "
        f"Blick in den Code lesbar ist, bekommen: {data.get('max_age_minutes_default')!r}"
    )

    # Gegenprobe: beim Standardwert darf die Abweichungs-Markierung NICHT
    # gesetzt sein (sonst waere sie eine wertlose Konstante).
    standard = tmp_path / "standard"
    standard.mkdir(parents=True)
    mod._write_validation_log(
        success=True,
        errors=[],
        min_locations=3,
        log_dir=standard,
        workflow_id="fix-1408-validator-betrefffilter",
        max_age_minutes=60,
        ignore_mail_age_reason=None,
    )
    data_std = yaml.safe_load(
        next(standard.glob("*_email_validation.yaml")).read_text(encoding="utf-8")
    )
    assert data_std.get("max_age_minutes_overridden") is False, (
        "Beim Standardwert darf keine Abweichung gemeldet werden, bekommen: "
        f"{data_std.get('max_age_minutes_overridden')!r}"
    )


# ---------------------------------------------------------------------------
# #1408 F002 (Adversary, MEDIUM) — die Begruendungspflicht muss dort sitzen, wo
# die Entscheidung faellt (Funktion), nicht nur in der Kommandozeilen-Schicht.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank_reason", ["", "   ", "\t\n"])
def test_blank_reason_does_not_disable_the_age_guard(blank_reason):
    """Given jemand ruft die Auswahl direkt (nicht ueber die Kommandozeile) mit
    einem leeren Grund auf / When eine 180 Minuten alte Mail vorliegt / Then
    bleibt die Altersschranke aktiv und der leere Grund wird abgelehnt — ein
    Schutz, der nur an der Oberflaeche haengt, ist kein Schutz."""
    mod = _load_validator()
    fake = _RecordingIMAPFake(mails=[(b"1", None), (b"2", "compare", 180.0)])

    with pytest.raises(ValueError) as excinfo:
        mod._fetch_latest_message(
            imap=fake, max_age_minutes=60, ignore_mail_age_reason=blank_reason
        )

    msg = str(excinfo.value).lower()
    assert any(marker in msg for marker in ("grund", "begründ", "begruend")), (
        "Die Meldung muss die fehlende Begruendung benennen (und nicht bloss "
        f"ueber das Alter reden), bekommen: {msg!r}"
    )


# ---------------------------------------------------------------------------
# #1408 F003 — ein leeres Betreffs-Fragment darf den Filter nicht still
# abschalten. Ein leerer String steckt in JEDEM Betreff: der Pruefer faellt
# damit auf "nimm die juengste compare-Mail" zurueck, waehrend der Aufrufer
# glaubt, seine eigene Mail benannt zu haben — genau der Schaden aus #1408,
# nur ueber einen Wert statt ueber ein fehlendes Argument.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank_fragment", ["", "   ", "\t"])
def test_blank_subject_fragment_does_not_silently_disable_the_filter(blank_fragment):
    """Given zwei compare-Mails — die eigene, aeltere und eine fremde, juengere
    (dieselbe Anordnung wie bei AC-1) / When jemand als Betreffs-Fragment einen
    leeren Wert setzt / Then bricht die Auswahl hoerbar ab und verlangt ein
    Fragment, statt still die fremde juengste Mail zu waehlen.

    Beide Einstiege werden geprueft: die reine Auswahlfunktion UND der
    Fetch-Pfad — ein Schutz, der nur an einem der beiden haengt, ist keiner."""
    mod = _load_validator()

    candidates = [
        (b"1", _header_bytes("compare", subject=f"Ortsvergleich {_SUBJECT_FRAGMENT}")),
        (b"2", _header_bytes("compare", subject="Ortsvergleich fremde Sitzung")),
    ]

    with pytest.raises(ValueError) as excinfo:
        mod._select_compare_uid(candidates, subject_contains=blank_fragment)

    msg = str(excinfo.value).lower()
    assert "fragment" in msg, (
        "Die Meldung muss sagen, dass ein Betreffs-Fragment fehlt, bekommen: "
        f"{msg!r}"
    )

    fake = _RecordingIMAPFake(mails=[(b"1", "compare", 5.0), (b"2", "compare", 1.0)])
    with pytest.raises(ValueError):
        mod._fetch_latest_message(imap=fake, subject_contains=blank_fragment)


# ---------------------------------------------------------------------------
# #1408 F004 — eine nicht-endliche Altersgrenze ist der schlechteste Ausgang:
# `nan` vergleicht sich mit nichts (`nan > x` ist IMMER falsch), haengelt also
# Obergrenze UND Altersvergleich zugleich aus — und laesst obendrein das
# Validator-Log entfallen, also genau den Nachweis, den das Commit-Gate liest.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nicht_endlich", [float("nan"), float("inf")])
def test_non_finite_age_limit_is_rejected(nicht_endlich):
    """Given eine 180 Minuten alte Compare-Mail / When die Altersgrenze auf
    einen nicht-endlichen Wert gesetzt wird / Then wird das als Klartext-Fehler
    abgelehnt — statt Schranke und Nachweis gleichzeitig verschwinden zu
    lassen."""
    mod = _load_validator()
    fake = _RecordingIMAPFake(mails=[(b"1", None), (b"2", "compare", 180.0)])

    with pytest.raises(ValueError) as excinfo:
        mod._fetch_latest_message(imap=fake, max_age_minutes=nicht_endlich)

    msg = str(excinfo.value).lower()
    assert "endlich" in msg, (
        "Die Meldung muss sagen, dass nur endliche Zahlen zulaessig sind, "
        f"bekommen: {msg!r}"
    )


def test_unwritable_validation_log_is_reported_not_swallowed(tmp_path, capsys):
    """Given das Validator-Log kann nicht geschrieben werden / When der Lauf
    endet / Then sagt der Pruefer das hoerbar auf stderr — ein fehlender
    Nachweis darf nicht unbemerkt bleiben, denn genau ihn liest das
    Commit-Gate.

    Ausloeser ist derselbe Wert wie oben: bei `nan` scheitert die Log-Erzeugung
    still, weil der fail-soft-Zweig jeden Fehler schluckt."""
    mod = _load_validator()
    log_dir = tmp_path / "_log"
    log_dir.mkdir(parents=True)

    mod._write_validation_log(
        success=True,
        errors=[],
        min_locations=3,
        log_dir=log_dir,
        workflow_id="fix-1408-validator-betrefffilter",
        max_age_minutes=float("nan"),
    )

    assert not list(log_dir.glob("*_email_validation.yaml")), (
        "Vorbedingung dieses Tests: in diesem Fall entsteht kein Log"
    )
    stderr = capsys.readouterr().err.lower()
    assert "log" in stderr and ("warn" in stderr or "fehler" in stderr), (
        "Ein ausgefallenes Validator-Log muss hoerbar gemeldet werden "
        f"(stderr), bekommen: {stderr!r}"
    )
