"""TDD RED — Issue #2147 Scheibe B2: Python-Resend-Allowlist enthaelt je Konto
nur noch die BESTAETIGTE WIRKSAME Kontaktadresse (``mail_to``, ersatzweise
``email``).

Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §6, AC-15, AC-5.
Go-Pendant: internal/mail/sender_effective_allowlist_test.go. Die
Guard-Ebene (voller ``send()``-Pfad) deckt der gemeinsame Paritaetsfall
``adresse-nur-in-email-mail_to-abweichend`` in
tests/fixtures/mail_recipient_parity/faelle.json ab
(tests/test_mail_recipient_parity.py).

Datenisolation: ``_load_resend_allowlist(data_dir=...)`` wird direkt mit
``tmp_path`` gerufen — kein Netz, kein echter ``data/``-Baum. Zwei-Nutzer-
Pflicht: jeder Test legt mindestens zwei Konten an.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from output.channels.email import _load_resend_allowlist  # noqa: E402

VERIFIED = "2026-01-01T00:00:00Z"


def _write_profile(data_root: Path, user_id: str, **fields) -> None:
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(json.dumps({"id": user_id, **fields}), encoding="utf-8")


def test_ac15_address_only_in_email_field_with_different_mail_to_is_not_allowlisted(tmp_path):
    """AC-15 (Python): Konto A bestaetigt mit ``email``=Login-Adresse und
    abweichendem ``mail_to``; Konto B bestaetigt mit eigenem ``mail_to``.
    Die Login-Adresse von A darf NICHT in der Allowlist stehen; die wirksamen
    Adressen von A und B schon.

    Heute ROT: die Schleife nimmt ``("mail_to", "email")`` auf."""
    _write_profile(
        tmp_path, "wanderer-a",
        email="wanderer-a-login@gmail.com", mail_to="wanderer-a-kontakt@gmail.com",
        email_verified_at=VERIFIED,
    )
    _write_profile(
        tmp_path, "wanderer-b",
        mail_to="wanderer-b-kontakt@gmail.com", email_verified_at=VERIFIED,
    )

    allow = _load_resend_allowlist(data_dir=str(tmp_path))

    assert "wanderer-a-login@gmail.com" not in allow, (
        f"AC-15: nicht wirksame Login-Adresse (mail_to abweichend) steht in der Allowlist: {sorted(allow)}"
    )
    assert "wanderer-a-kontakt@gmail.com" in allow, "AC-15 Gegenprobe: wirksame Adresse von A fehlt"
    assert "wanderer-b-kontakt@gmail.com" in allow, "AC-15 Gegenprobe: wirksame Adresse von B fehlt"


def test_ac15_email_without_mail_to_stays_allowlisted_as_effective_address(tmp_path):
    """AC-15 Gegenprobe (ersatzweise ``email``): bestaetigtes Konto ohne
    ``mail_to`` bleibt ueber ``email`` erreichbar — faengt "nur noch mail_to".
    Heute gruen (Regressionswaechter)."""
    _write_profile(tmp_path, "wanderer-c", email="wanderer-c-login@gmail.com", email_verified_at=VERIFIED)
    _write_profile(
        tmp_path, "wanderer-d",
        email="wanderer-d-login@gmail.com", mail_to="wanderer-d-kontakt@gmail.com",
        email_verified_at=VERIFIED,
    )

    allow = _load_resend_allowlist(data_dir=str(tmp_path))

    assert "wanderer-c-login@gmail.com" in allow, (
        f"AC-15: email ohne mail_to ist die wirksame Adresse und muss erlaubt sein: {sorted(allow)}"
    )


def test_ac5_pending_address_not_allowlisted_old_address_still_is(tmp_path):
    """AC-5 (Python-Allowlist-Haelfte) — Regressionswaechter, heute gruen:
    bestaetigtes Konto mit ``mail_to``=ALT und roh gesetzter ausstehender
    Aenderung auf NEU -> NEU nicht in der Allowlist, ALT weiterhin."""
    _write_profile(
        tmp_path, "wanderer-alt",
        email="wanderer-alt@gmail.com", mail_to="wanderer-alt@gmail.com",
        email_verified_at=VERIFIED,
        pending_contact_address="wanderer-neu@gmail.com",
        pending_contact_field="mail_to",
    )
    _write_profile(
        tmp_path, "wanderer-zweit",
        mail_to="wanderer-zweit@gmail.com", email_verified_at=VERIFIED,
    )

    allow = _load_resend_allowlist(data_dir=str(tmp_path))

    assert "wanderer-neu@gmail.com" not in allow, (
        f"AC-5: ausstehende Adresse steht in der Allowlist: {sorted(allow)}"
    )
    assert "wanderer-alt@gmail.com" in allow, "AC-5: alte bestaetigte Adresse fehlt in der Allowlist"
