"""Postausgang (SMTP/STARTTLS) und Posteingang (IMAPS) pruefen das Zertifikat (#2961, AC-2).

Gegenstelle ist ein echter TLS-Server auf Loopback (eigener Port, im Test
gebunden) mit einem frisch erzeugten, selbstsignierten Zertifikat. Ohne
Vertrauen in dieses Zertifikat darf der Core keine Zugangsdaten senden; ist das
Zertifikat als vertrauenswuerdig hinterlegt (``SSL_CERT_FILE``), klappt die
Anmeldung wie bisher.
"""
from __future__ import annotations

import shutil
import socket
import ssl
import subprocess
import threading
import time

import pytest

from app.config import Settings
from output.channels.email import EmailOutput
from services.inbound_email_reader import InboundEmailReader

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl fehlt")


@pytest.fixture(scope="module")
def zertifikat(tmp_path_factory):
    d = tmp_path_factory.mktemp("tls")
    cert, key = d / "cert.pem", d / "key.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
         "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
         "-keyout", str(key), "-out", str(cert)],
        check=True, capture_output=True,
    )
    return cert, key


def _schreibe(f, daten: bytes) -> None:
    f.write(daten)
    f.flush()


class _TlsGegenstelle:
    """Minimaler SMTP-(STARTTLS) bzw. IMAPS-Server; protokolliert, ob Zugangsdaten ankamen."""

    def __init__(self, art: str, cert, key) -> None:
        self.art = art
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(str(cert), str(key))
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.sock.settimeout(10)
        self.port = self.sock.getsockname()[1]
        self.zeilen: list[str] = []
        self.thread = threading.Thread(target=self._lauf, daemon=True)
        self.thread.start()

    def _lauf(self) -> None:
        try:
            conn, _ = self.sock.accept()
            conn.settimeout(10)
            if self.art == "smtp":
                self._smtp(conn)
            else:
                self._imap(conn)
        except (OSError, ssl.SSLError):
            pass

    def _zeilen_lesen(self, f, antwort) -> None:
        for raw in f:
            zeile = raw.decode(errors="replace").strip()
            self.zeilen.append(zeile)
            out = antwort(zeile)
            if out is None:
                return
            f.write(out.encode())
            f.flush()

    def _smtp(self, conn) -> None:
        f = conn.makefile("rwb")
        _schreibe(f, b"220 test ESMTP\r\n")
        for raw in f:
            zeile = raw.decode().strip().upper()
            if zeile.startswith("EHLO"):
                _schreibe(f, b"250-test\r\n250 STARTTLS\r\n")
            elif zeile == "STARTTLS":
                _schreibe(f, b"220 go\r\n")
                break
        tls = self.ctx.wrap_socket(conn, server_side=True)
        tf = tls.makefile("rwb")
        im_rumpf = False
        for raw in tf:
            zeile = raw.decode(errors="replace").rstrip("\r\n")
            self.zeilen.append(zeile)
            u = zeile.upper()
            if im_rumpf:
                if zeile == ".":
                    im_rumpf = False
                    _schreibe(tf, b"250 queued\r\n")
            elif u.startswith("EHLO"):
                _schreibe(tf, b"250-test\r\n250 AUTH PLAIN LOGIN\r\n")
            elif u.startswith("AUTH"):
                _schreibe(tf, b"235 ok\r\n")
            elif u == "DATA":
                im_rumpf = True
                _schreibe(tf, b"354 go\r\n")
            elif u == "QUIT":
                _schreibe(tf, b"221 bye\r\n")
                return
            else:
                _schreibe(tf, b"250 ok\r\n")

    def _imap(self, conn) -> None:
        tls = self.ctx.wrap_socket(conn, server_side=True)
        f = tls.makefile("rwb")
        _schreibe(f, b"* OK test IMAP4rev1\r\n")

        def antwort(z: str):
            tag, _, rest = z.partition(" ")
            cmd = rest.split(" ")[0].upper()
            if cmd == "CAPABILITY":
                return f"* CAPABILITY IMAP4rev1 AUTH=PLAIN\r\n{tag} OK done\r\n"
            if cmd == "LOGIN":
                return f"{tag} OK logged in\r\n"
            if cmd == "SELECT":
                return f"* 0 EXISTS\r\n{tag} OK [READ-WRITE] done\r\n"
            if cmd in ("SEARCH", "UID"):
                return f"* SEARCH\r\n{tag} OK done\r\n"
            if cmd == "LOGOUT":
                return f"* BYE\r\n{tag} OK bye\r\n"
            return f"{tag} OK\r\n"

        self._zeilen_lesen(f, antwort)

    def login_gesehen(self) -> bool:
        return any(
            z.upper().startswith("AUTH") or " LOGIN " in f" {z.upper()} " for z in self.zeilen
        )

    def stoppen(self) -> None:
        self.thread.join(timeout=10)
        self.sock.close()


def _smtp_settings(port: int) -> Settings:
    return Settings(
        smtp_host="127.0.0.1", smtp_port=port, smtp_user="u@example.org",
        smtp_pass="geheim-pass", mail_from="u@example.org", mail_to="ziel@example.org",
    )


def _smtp_senden(port: int) -> Exception | None:
    out = EmailOutput(_smtp_settings(port))
    try:
        out._dial_and_send(
            "127.0.0.1", port, "u@example.org", "geheim-pass", ["ziel@example.org"],
            _einfache_mail(), "u@example.org", time.monotonic() + 20,
        )
    except Exception as exc:  # noqa: BLE001
        return exc
    return None


def _einfache_mail():
    from email.mime.text import MIMEText

    m = MIMEText("hallo")
    m["Subject"] = "t"
    m["From"] = "u@example.org"
    m["To"] = "ziel@example.org"
    return m


def test_smtp_starttls_lehnt_unbekanntes_zertifikat_ab(zertifikat, monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    srv = _TlsGegenstelle("smtp", *zertifikat)
    fehler = _smtp_senden(srv.port)
    srv.stoppen()
    assert isinstance(fehler, ssl.SSLCertVerificationError), repr(fehler)
    assert not srv.login_gesehen(), "Zugangsdaten an nicht gepruefte Gegenstelle gesendet"


def test_smtp_starttls_mit_vertrautem_zertifikat_sendet(zertifikat, monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", str(zertifikat[0]))
    srv = _TlsGegenstelle("smtp", *zertifikat)
    fehler = _smtp_senden(srv.port)
    srv.stoppen()
    assert fehler is None, repr(fehler)
    assert srv.login_gesehen()


def _imap_poll(port: int) -> tuple[int, int]:
    s = Settings(
        imap_host="127.0.0.1", imap_port=port, imap_user="u@example.org",
        imap_pass="geheim-pass", smtp_host="127.0.0.1", smtp_user="u@example.org",
        smtp_pass="geheim-pass",
    )
    return InboundEmailReader()._poll_inbox(s, "u@example.org", "geheim-pass")


def test_imap_lehnt_unbekanntes_zertifikat_ab(zertifikat, monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    srv = _TlsGegenstelle("imap", *zertifikat)
    processed, failed = _imap_poll(srv.port)
    srv.stoppen()
    assert (processed, failed) == (0, 1)
    assert not srv.login_gesehen(), "IMAP-Zugangsdaten an nicht gepruefte Gegenstelle gesendet"


def test_imap_mit_vertrautem_zertifikat_meldet_an(zertifikat, monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", str(zertifikat[0]))
    srv = _TlsGegenstelle("imap", *zertifikat)
    processed, failed = _imap_poll(srv.port)
    srv.stoppen()
    assert (processed, failed) == (0, 0)
    assert srv.login_gesehen()
