"""Live-Nachweis AC-26 (#2417): echte Apple-Mail-Zustellung ueber Stalwart.

Reproduziert B2 auf dem echten Zustellweg (nicht nur im Kern-Fake): eine
synthetische Apple-Mail-Antwort (NUR ``text/html``, mit Zitat und Signatur)
mit ``Hilfe`` wird ueber die REALE anonyme Port-25-Inbound-Pipeline ins
Stalwart-Test-Postfach ``gregor-test@henemm.com`` zugestellt (echter,
Stalwart-prependeter ``Authentication-Results``-Header -- die authentifizierte
Submission auf Port 587 traegt strukturell KEINEN solchen Header, #2143 F003,
deshalb NICHT ``_deliver_mail`` sondern die anonyme Variante). Danach loest
``poll_and_process`` die Verarbeitung aus, die Antwort wird per IMAP gelesen.

Muster: ``tests/tdd/test_issue_1009_1019_inbound_robustness.py`` (Helfer
``_deliver_mail_anonymous``/``_imap``/``_base_email_settings``, insbesondere
``test_live_authorized_sender_over_real_anonymous_pipeline_is_processed``).

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md (AC-26)

NICHT lokal ausfuehren -- nur ``--collect-only`` als Beleg (Team-Lead-Vorgabe).
Pflichtschritt in ``/e2e-verify``, nicht optional.

Issue #2417 Fix-Loop 2: ``pytestmark`` traegt jetzt ``real_data_root`` (sonst
biegt ``tests/conftest.py:214-231`` ``app.loader._DATA_ROOT`` auf eine
Temp-Wurzel um, waehrend ``_make_user``/``save_trip`` in den ECHTEN
``data/users``-Baum schreiben -- der Absender wurde dadurch nie aufgeloest,
"Unresolved/ambiguous sender", processed=0). AUSSERDEM darf ``poll_and_process``
NICHT die gesamte UNSEEN-Queue des geteilten Postfachs ``gregor-test@henemm.com``
anfassen (haette Fremdmails faelschlich \\Seen markiert und ggf. echte
Antwortmails an fremde Absender ausgeloest). Deshalb bekommt die eigene
Testmail einen eindeutigen Plus-Adress-``To:``-Header
(``gregor-test+gz2417-<suffix>@henemm.com``), UND ``inbound_address`` wird in
``_base_email_settings()`` auf genau diese Adresse gesetzt -- damit greift der
bereits vorhandene TO-Filter in ``poll_and_process``
(``src/services/inbound_email_reader.py:156-160``: ``inbound !=
settings.smtp_user`` -> ``imap.search(None, "UNSEEN", "TO", inbound)``) und
der Poll sieht NUR die eigene Mail. Envelope-RCPT-TO bleibt bewusst das
bare Postfach (``gregor-test@henemm.com``) -- Zustellung haengt so nicht von
Stalwart-Plus-Adressierung ab, nur der ``To:``-HEADER trägt die Plus-Adresse
fuer den IMAP-Header-Suchfilter.
"""
from __future__ import annotations

import email
import imaplib
import os
import quopri
import smtplib
import time as time_mod
import uuid
from email.header import decode_header, make_header
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import get_data_dir, save_trip
from app.trip import Stage, Trip, Waypoint
from services.inbound_email_reader import InboundEmailReader
from services.trip_command_processor import _COMMAND_SPECS

pytestmark = [pytest.mark.live, pytest.mark.email, pytest.mark.real_data_root]

_TEST_MAILBOX = "gregor-test@henemm.com"
_SYSTEM_FROM = "gregor_zwanzig@henemm.com"
_REPO_ROOT = Path(__file__).resolve().parents[2]
LAT, LON = 47.2692, 11.4041

_EMAIL_CREDS_PRESENT = bool(
    os.environ.get("GZ_TEST_IMAP_USER")
    and os.environ.get("GZ_TEST_IMAP_PASS")
    and os.environ.get("GZ_TEST_SMTP_USER")
    and os.environ.get("GZ_TEST_SMTP_PASS")
)
_email_gate = pytest.mark.skipif(
    not _EMAIL_CREDS_PRESENT,
    reason="GZ_TEST_IMAP_*/GZ_TEST_SMTP_PASS nicht gesetzt — echter Mail-Roundtrip nicht möglich",
)


def _make_user(user_id: str, mail_to: str) -> None:
    """Schreibt user.json ueber ``get_data_dir()`` (wie ``save_trip``/
    ``lookup_user_by_email``) statt eines hartkodierten ``_REPO_ROOT``-Pfads --
    beide MUESSEN auf dieselbe Wurzel zeigen, sonst loest
    ``_resolve_settings_for_sender`` den Absender nie auf (#2417 Fix-Loop 2,
    Befund 1)."""
    import json
    import shutil

    udir = get_data_dir(user_id)
    if udir.exists():
        shutil.rmtree(udir)
    udir.mkdir(parents=True)
    (udir / "user.json").write_text(json.dumps({
        "id": user_id,
        "created_at": "2026-09-25T00:00:00Z",
        "mail_to": mail_to,
        "email_verified_at": "2026-09-25T00:00:00Z",
        "is_test_user": True,
    }))


def _cleanup_user(user_id: str) -> None:
    import shutil

    udir = get_data_dir(user_id)
    if udir.exists():
        shutil.rmtree(udir)


def _make_trip(user_id: str, trip_id: str, name: str) -> Trip:
    from datetime import date

    today = date.today()
    wps = [
        Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600),
        Waypoint(id="G2", name="Ziel", lat=47.2950, lon=11.4420, elevation_m=800),
    ]
    stage = Stage(id="T1", name=f"{name}-Etappe", date=today, waypoints=wps)
    trip = Trip(id=trip_id, name=name, stages=[stage])
    save_trip(trip, user_id=user_id)
    return trip


def _base_email_settings(inbound_address: str = _TEST_MAILBOX) -> Settings:
    """Wie ``_base_email_settings`` in
    ``test_issue_1009_1019_inbound_robustness.py``: IMAP auf das Test-
    Postfach, SMTP-Antwort ueber die ``test_smtp_*``-Felder (Stalwart), damit
    die Herkunftssperre (#1476) die Antwort auf ``gregor-test@henemm.com``
    umleitet, statt auf ein produktives Postfach.

    ``inbound_address`` ist per Default ``_TEST_MAILBOX`` (Fallback), wird von
    ``test_apple_mail_hilfe_ueber_echte_stalwart_zustellung_wird_beantwortet``
    aber auf eine eindeutige Plus-Adresse gesetzt (#2417 Fix-Loop 2, Befund
    1): ``poll_and_process`` (src/services/inbound_email_reader.py:156-160)
    filtert dann per IMAP-TO-Header-Suche NUR die eigene Mail, statt die
    gesamte UNSEEN-Queue des GETEILTEN Postfachs zu verarbeiten."""
    return Settings(
        imap_host=os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
        imap_port=int(os.environ.get("GZ_IMAP_PORT", "993")),
        imap_user=os.environ["GZ_TEST_IMAP_USER"],
        imap_pass=os.environ["GZ_TEST_IMAP_PASS"],
        inbound_address=inbound_address,
        smtp_user=_TEST_MAILBOX,
        mail_from=_SYSTEM_FROM,
        test_smtp_host=os.environ.get("GZ_TEST_SMTP_HOST", "mail.henemm.com"),
        test_smtp_port=int(os.environ.get("GZ_TEST_SMTP_PORT", "587")),
        test_smtp_user=os.environ["GZ_TEST_SMTP_USER"],
        test_smtp_pass=os.environ["GZ_TEST_SMTP_PASS"],
        test_mail_from=_SYSTEM_FROM,
        test_imap_user=os.environ["GZ_TEST_IMAP_USER"],
        test_imap_pass=os.environ["GZ_TEST_IMAP_PASS"],
    )


def _imap() -> imaplib.IMAP4_SSL:
    m = imaplib.IMAP4_SSL(os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
                          int(os.environ.get("GZ_IMAP_PORT", "993")), timeout=15)
    m.login(os.environ["GZ_TEST_IMAP_USER"], os.environ["GZ_TEST_IMAP_PASS"])
    m.select("INBOX")
    return m


def _apple_html_only_body(befehl: str) -> tuple[str, bytes]:
    """Apple-Mail-Antwortstruktur (nur ``text/html``, Zitat + Signatur) --
    dasselbe Muster wie ``_mime_apple_html_only`` im Kern-Fundament
    (``tests/tdd/_befehl_e2e_fixtures.py``), hier als fertiger Content-Type/
    Payload-Teil fuer den echten SMTP-Versand."""
    html = (
        f'<body dir="auto">{befehl}<br id="lineBreakAtBeginningOfSignature">'
        "<div dir=\"ltr\"><div><br></div></div>"
        '<div dir="ltr"><br><blockquote type="cite">Am 25.09.2026 um 06:06 '
        "schrieb Absender:<br><br></blockquote></div></body>"
    )
    qp = quopri.encodestring(html.encode("utf-8")).decode("ascii")
    boundary = f"Apple-Mail-Live=_GZ2417-{uuid.uuid4().hex[:8]}"
    return boundary, qp.encode("ascii")


def _deliver_apple_html_mail_anonymous(
    envelope_from: str, header_from: str, subject: str, befehl: str,
    *, to_header: str = _TEST_MAILBOX,
) -> None:
    """Liefert eine synthetische Apple-Mail-Antwort (nur ``text/html``) ueber
    die ECHTE anonyme Inbound-Pipeline (Port 25) ein -- nur auf diesem Weg
    prependt Stalwart einen ECHTEN ``Authentication-Results``-Header (#2143
    F003; die authentifizierte Submission auf Port 587 traegt strukturell
    NIE einen).

    ``to_header`` traegt bewusst die Plus-Adresse fuer den TO-Filter in
    ``poll_and_process`` (#2417 Fix-Loop 2, Befund 1) -- der Envelope-
    Empfaenger (``sendmail``-Zielliste) bleibt IMMER das bare Postfach, damit
    die Zustellung nicht von Stalwart-Plus-Adressierung abhaengt."""
    boundary, qp_payload = _apple_html_only_body(befehl)
    raw = (
        f"From: {header_from}\r\n"
        f"To: {to_header}\r\n"
        f"Subject: {subject}\r\n"
        "MIME-Version: 1.0\r\n"
        f'Content-Type: multipart/alternative; boundary="{boundary}"\r\n'
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/html;\r\n"
        "\tcharset=utf-8\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n"
        "\r\n"
    ).encode("utf-8") + qp_payload + f"\r\n--{boundary}--\r\n".encode("utf-8")

    with smtplib.SMTP("mail.henemm.com", 25, timeout=15) as server:
        server.ehlo()
        server.sendmail(envelope_from, [_TEST_MAILBOX], raw)


def _subject(msg) -> str:
    return str(make_header(decode_header(msg.get("Subject", ""))))


def _find_reply_by_subject(exact_subject: str, *, not_before_uid: bytes | None,
                            timeout_s: int = 120) -> list[bytes]:
    """Sucht die vom System selbst versendete Antwortmail anhand ihres
    (fixen, nicht tripbezogenen) Betreffs. RISIKO (dokumentiert statt
    verschwiegen): ``_show_help()`` traegt IMMER den Betreff "Hilfe" ohne
    Trip-/Token-Bezug -- eine zeitgleiche zweite Session, die ebenfalls
    HILFE per E-Mail ausloest, kann diese Suche verwirren. Fuer den
    Pflichtlauf in ``/e2e-verify`` (ein Lauf zur Zeit) ist das hinnehmbar,
    fuer parallele Live-Laeufe waere ein tripbezogener Hilfe-Betreff eine
    Produktverbesserung."""
    deadline = time_mod.time() + timeout_s
    while True:
        m = _imap()
        try:
            _, data = m.uid("search", None, "SUBJECT", exact_subject)
            hits = [
                uid for uid in (data[0].split() if data and data[0] else [])
                if not_before_uid is None or int(uid) > int(not_before_uid)
            ]
            if hits or time_mod.time() > deadline:
                return hits
        finally:
            m.logout()
        time_mod.sleep(8)


def _peek_msg(uid: bytes):
    m = _imap()
    try:
        _, data = m.uid("fetch", uid, "(BODY.PEEK[])")
        return email.message_from_bytes(data[0][1]) if data and data[0] else None
    finally:
        m.logout()


def _hoechste_uid() -> bytes:
    m = _imap()
    try:
        _, data = m.uid("search", None, "ALL")
        uids = data[0].split() if data and data[0] else []
        return max(uids, key=int) if uids else b"0"
    finally:
        m.logout()


def _delete_uids(uids: list[bytes]) -> None:
    if not uids:
        return
    m = _imap()
    try:
        for uid in uids:
            m.uid("store", uid, "+FLAGS", "(\\Deleted)")
        m.expunge()
    finally:
        m.logout()


@_email_gate
def test_apple_mail_hilfe_ueber_echte_stalwart_zustellung_wird_beantwortet():
    """AC-26: eine echte, ueber Stalwart zugestellte Apple-Mail-Antwort (nur
    ``text/html``) mit ``Hilfe`` wird erkannt und mit allen 12
    Befehlswoertern beantwortet -- Live-Nachweis fuer AC-6/AC-19 auf dem
    echten Zustellweg."""
    suffix = uuid.uuid4().hex[:8]
    user_id = f"gz2417-live-{suffix}"
    sender = f"{user_id}@henemm.com"
    token = f"GZ2417LIVE-{suffix}"
    # Eindeutige Plus-Adresse NUR fuer diesen Testlauf (#2417 Fix-Loop 2,
    # Befund 1) -- damit greift der TO-Filter in poll_and_process
    # (inbound_email_reader.py:156-160) und der Poll fasst NICHT die gesamte
    # UNSEEN-Queue des geteilten Postfachs an.
    own_inbound = f"gregor-test+gz2417-{suffix}@henemm.com"
    _make_user(user_id, mail_to=sender)
    _make_trip(user_id, trip_id=f"t{suffix}", name=token)

    settings = _base_email_settings(inbound_address=own_inbound)
    baseline_uid = _hoechste_uid()

    _deliver_apple_html_mail_anonymous(
        envelope_from=sender, header_from=sender,
        subject=f"Re: [{token}] Etappe", befehl="Hilfe",
        to_header=own_inbound,
    )

    try:
        # Port-25-Zustellung ist asynchron -- ein einzelner Poll direkt nach
        # dem Versand waere ein Race. Bis zu 60s erneut pollen, bis die eigene
        # (per TO-Filter isolierte) Mail verarbeitet wurde.
        processed = 0
        deadline = time_mod.time() + 60
        while time_mod.time() < deadline:
            processed = InboundEmailReader().poll_and_process(settings)
            if processed >= 1:
                break
            time_mod.sleep(5)
        assert processed >= 1, (
            f"Apple-Mail-Antwort wurde nicht verarbeitet (processed={processed})."
        )

        reply_uids = _find_reply_by_subject("Hilfe", not_before_uid=baseline_uid)
        assert reply_uids, "Keine Antwortmail mit Betreff 'Hilfe' gefunden."
        antwort = _peek_msg(reply_uids[-1])
        assert antwort is not None
        body = antwort.get_payload(decode=True).decode(
            antwort.get_content_charset() or "utf-8", errors="replace"
        ) if not antwort.is_multipart() else "\n".join(
            p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace")
            for p in antwort.walk() if p.get_content_maintype() == "text"
        )
        for wort, _arg, _beschreibung, _kinds in _COMMAND_SPECS:
            assert wort.upper() in body, f"Antwort fehlt Befehlswort {wort.upper()!r}: {body!r}"
    finally:
        _cleanup_user(user_id)
