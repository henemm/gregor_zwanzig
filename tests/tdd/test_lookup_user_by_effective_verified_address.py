"""TDD RED — Issue #2147 Scheibe B2: Python-Kommandoweg ordnet einen Absender
nur ueber die BESTAETIGTE WIRKSAME Kontaktadresse zu.

Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §7, AC-13, AC-5.

Heute vergleicht ``lookup_user_by_email`` (src/app/loader.py) nur
``profile["mail_to"]`` — unabhaengig von ``email_verified_at`` und ohne den
Ersatz ``email``, wenn ``mail_to`` fehlt. Ab B2: Treffer nur, wenn die Adresse
der wirksamen Kontaktadresse (``mail_to``, ersatzweise ``email``) entspricht
UND ``email_verified_at`` gesetzt ist — Pendant zu Go ``ResolveAddressOwner``.

Datenisolation: jeder Test schreibt echte ``user.json``-Dateien in
``tmp_path`` und uebergibt ``data_dir`` explizit — der echte ``data/``-Baum
wird nie beruehrt. Zwei-Nutzer-Pflicht: jeder Fall legt ein zweites echtes
Konto mit eigener Adresse an.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import lookup_user_by_email  # noqa: E402

VERIFIED = "2026-01-01T00:00:00Z"


def _write_profile(data_root: Path, user_id: str, **fields) -> None:
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    profile = {"id": user_id, **fields}
    (user_dir / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _second_account(data_root: Path) -> None:
    _write_profile(
        data_root, "wanderer-zweit",
        mail_to="wanderer-zweit@gmail.com", email_verified_at=VERIFIED,
    )


# ---------------------------------------------------------------------------
# AC-13
# ---------------------------------------------------------------------------

def test_ac13a_address_only_in_email_field_with_different_mail_to_is_not_resolved(tmp_path):
    """AC-13 (a): Adresse steht nur im Nebenfeld ``email``, ``mail_to`` weicht
    ab, Konto bestaetigt -> keine Zuordnung (None).

    Heute bereits gruen (Lookup liest nur mail_to) — Regressionswaechter gegen
    eine Umsetzung, die beide Felder vergleicht."""
    _write_profile(
        tmp_path, "wanderer-a",
        email="wanderer-a-login@gmail.com", mail_to="wanderer-a-kontakt@gmail.com",
        email_verified_at=VERIFIED,
    )
    _second_account(tmp_path)

    result = lookup_user_by_email("wanderer-a-login@gmail.com", data_dir=str(tmp_path))

    assert result is None, (
        f"AC-13a: Adresse nur im email-Feld (mail_to abweichend) wurde {result!r} "
        "zugeordnet — nur die wirksame Kontaktadresse darf zuordnen"
    )


def test_ac13b_unverified_account_is_not_resolved(tmp_path):
    """AC-13 (b): Adresse == ``mail_to``, aber ``email_verified_at`` fehlt ->
    keine Zuordnung (None).

    Heute ROT: der Lookup prueft den Bestaetigungsstatus gar nicht."""
    _write_profile(tmp_path, "wanderer-b", mail_to="wanderer-b-kontakt@gmail.com")
    _second_account(tmp_path)

    result = lookup_user_by_email("wanderer-b-kontakt@gmail.com", data_dir=str(tmp_path))

    assert result is None, (
        f"AC-13b: unbestaetigtes Konto wurde der Adresse zugeordnet ({result!r}) — "
        "ohne email_verified_at darf keine Zuordnung erfolgen"
    )


def test_ac13c_verified_effective_mail_to_is_resolved(tmp_path):
    """AC-13 (c): Adresse == ``mail_to`` (wirksam), Konto bestaetigt -> Konto.
    Gegenprobe gegen Ueberkorrektur; heute gruen."""
    _write_profile(
        tmp_path, "wanderer-c",
        email="wanderer-c-login@gmail.com", mail_to="wanderer-c-kontakt@gmail.com",
        email_verified_at=VERIFIED,
    )
    _second_account(tmp_path)

    result = lookup_user_by_email("Wanderer-C-Kontakt@gmail.com", data_dir=str(tmp_path))

    assert result == "wanderer-c", (
        f"AC-13c: bestaetigte wirksame mail_to-Adresse muss wanderer-c liefern, bekam {result!r}"
    )


def test_ac13d_verified_email_without_mail_to_is_resolved_as_effective_address(tmp_path):
    """AC-13 (d): nur ``email`` gesetzt, kein ``mail_to``, Konto bestaetigt ->
    Konto (``email`` ist ersatzweise die wirksame Kontaktadresse).

    Heute ROT: der Lookup vergleicht nur mail_to und kennt den Ersatz nicht."""
    _write_profile(
        tmp_path, "wanderer-d",
        email="wanderer-d-login@gmail.com", email_verified_at=VERIFIED,
    )
    _second_account(tmp_path)

    result = lookup_user_by_email("wanderer-d-login@gmail.com", data_dir=str(tmp_path))

    assert result == "wanderer-d", (
        f"AC-13d: email ohne mail_to ist die wirksame Adresse, erwartet wanderer-d, bekam {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (Python-Lookup-Haelfte) — Regressionswaechter
# ---------------------------------------------------------------------------

def test_ac5_pending_address_is_not_resolved_to_account_old_address_still_is(tmp_path):
    """AC-5: bestaetigtes Konto mit ``mail_to``=ALT und roh gesetzter
    ausstehender Aenderung (``pending_contact_address``=NEU,
    ``pending_contact_field``=``mail_to``) -> Lookup(NEU) liefert NICHT dieses
    Konto, Lookup(ALT) weiterhin.

    Heute gruen (Pending-Felder werden ignoriert) — Waechter gegen eine
    Umsetzung, die die ausstehende Adresse zuordnet."""
    _write_profile(
        tmp_path, "wanderer-alt",
        email="wanderer-alt@gmail.com", mail_to="wanderer-alt@gmail.com",
        email_verified_at=VERIFIED,
        pending_contact_address="wanderer-neu@gmail.com",
        pending_contact_field="mail_to",
    )
    _second_account(tmp_path)

    assert lookup_user_by_email("wanderer-neu@gmail.com", data_dir=str(tmp_path)) != "wanderer-alt", (
        "AC-5: ausstehende, unbestaetigte Adresse wurde dem Konto zugeordnet"
    )
    assert lookup_user_by_email("wanderer-alt@gmail.com", data_dir=str(tmp_path)) == "wanderer-alt", (
        "AC-5: alte bestaetigte Adresse muss waehrend der ausstehenden Aenderung zuordnen"
    )
