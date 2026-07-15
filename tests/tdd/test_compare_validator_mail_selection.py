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
import importlib.util
from pathlib import Path

import pytest


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


def _header_bytes(mail_type: "str | None", subject: str = "Test") -> bytes:
    """Baut einen echten RFC822-Header-Block, wie IMAP ihn bei
    `BODY.PEEK[HEADER]` liefert: Header-Zeilen, CRLF-getrennt, mit leerer
    Trennzeile am Ende. `mail_type=None` -> gar kein X-GZ-Mail-Type-Header."""
    lines = [f"Subject: {subject}"]
    if mail_type is not None:
        lines.append(f"X-GZ-Mail-Type: {mail_type}")
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


class _RecordingIMAPFake:
    """Duck-typed IMAP-Verbindung (KEIN Mock-Framework). Implementiert die vom
    Validator genutzten Kommandos und schreibt jedes `fetch`-Kommando in
    `self.fetched` mit.

    `mails` ist eine geordnete Liste von ``(uid: bytes, mail_type: str | None)``
    in IMAP-Reihenfolge (aeltest -> neuest), wie ``imap.search`` sie liefert.
    Default: uid b'1' Nicht-compare, uid b'2' compare (neueste)."""

    def __init__(self, mails=None):
        if mails is None:
            mails = [(b"1", None), (b"2", "compare")]
        self.mails = mails
        self.fetched: list = []
        self.selected: "str | None" = None
        self._headers = {
            uid: _header_bytes(mt, subject=f"Mail {uid.decode()}")
            for uid, mt in mails
        }
        self._full = {}
        for uid, mt in mails:
            lines = [f"Subject: Mail {uid.decode()}"]
            if mt is not None:
                lines.append(f"X-GZ-Mail-Type: {mt}")
            body = "\r\n".join(lines) + "\r\n\r\n<html><body><table></table></body></html>"
            self._full[uid] = body.encode("utf-8")

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
        else:
            payload = self._full.get(uid, b"\r\n\r\n")
        return ("OK", [(uid + b" (X)", payload)])

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
