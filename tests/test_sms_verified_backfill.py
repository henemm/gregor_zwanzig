"""TDD RED — Issue #2406: Nachtrag-Skript, das Bestandskonten mit gesetzter
`sms_to` als bestaetigt nachtraegt.

Spec: docs/specs/modules/sms_nummer_verifikation.md §10 — AC-10 (Dry-Run
aendert nichts, `--execute` traegt nur fuer Konten mit nicht-leerer `sms_to`
nach, zweiter Lauf ist wertgleich idempotent).

Geprueft wird das ECHTE Skript `scripts/backfill_2406_sms_verified.py` als
eigener Prozess gegen einen echten Dateibaum unter `tmp_path` — keine Mocks.
Das Skript wird relativ zu DIESER Testdatei aufgeloest (nie ueber einen festen
Hauptrepo-Pfad), sonst gruente der Test aus dem falschen Checkout.

RED heute: das Skript existiert nicht → `returncode != 0`. Deshalb prueft jeder
Test ZUERST den Rueckgabewert: ohne diese Reihenfolge waere „nichts veraendert"
trivial gruen, solange gar nichts passiert.

Ausfuehren:
  uv run pytest tests/test_sms_verified_backfill.py -v -rA --disable-socket
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKRIPT = REPO_ROOT / "scripts" / "backfill_2406_sms_verified.py"

MIT_NUMMER = "+491511234567"
UNGETRIMMT = "  +491517654321  "


def _profil(uid: str, **overrides) -> dict:
    profil = {
        "id": uid,
        "display_name": f"Konto {uid}",
        "email": f"{uid}@beispiel.de",
        "mail_to": f"{uid}-empfang@beispiel.de",
        "password_hash": "$2a$10$abcdefghijklmnopqrstuv.WXYZ0123456789abcdefghijklmn",
        "tier": "standard",
        "telegram_chat_id": "123456789",
        "created_at": "2025-11-03T08:15:00Z",
        "dem_skript_unbekanntes_feld": {"tief": ["verschachtelt", 42]},
    }
    profil.update(overrides)
    return profil


def _konto(root: Path, uid: str, **overrides) -> Path:
    pfad = root / uid / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(_profil(uid, **overrides), indent=2, ensure_ascii=False), encoding="utf-8")
    return pfad


def _lauf(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SKRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
    )


def _erfolg(ergebnis: subprocess.CompletedProcess, ac: str) -> None:
    assert ergebnis.returncode == 0, (
        f"{ac}: das Nachtrag-Skript {SKRIPT} muss mit 0 enden, Rueckgabewert "
        f"{ergebnis.returncode}.\nstdout:\n{ergebnis.stdout}\nstderr:\n{ergebnis.stderr}"
    )


def _laden(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_ac10_dry_run_aendert_keine_datei(tmp_path):
    root = tmp_path / "users"
    pfad = _konto(root, "henning", sms_to=MIT_NUMMER)
    vorher = pfad.read_bytes()

    ergebnis = _lauf(root)  # ohne --execute: Dry-Run ist Default
    _erfolg(ergebnis, "AC-10 (Dry-Run)")
    assert pfad.read_bytes() == vorher, (
        "AC-10: der Probelauf darf keine Datei veraendern.\n"
        f"vorher:  {vorher!r}\nnachher: {pfad.read_bytes()!r}"
    )


def test_ac10_execute_traegt_nur_konten_mit_nummer_nach(tmp_path):
    root = tmp_path / "users"
    mit = _konto(root, "mitnummer", sms_to=MIT_NUMMER)
    ohne = _konto(root, "ohnenummer")
    leer = _konto(root, "leerenummer", sms_to="")
    ohne_vorher, leer_vorher = ohne.read_bytes(), leer.read_bytes()
    mit_vorher = _laden(mit)

    _erfolg(_lauf(root, "--execute"), "AC-10 (erster Lauf)")

    nachher = _laden(mit)
    assert nachher.get("sms_verified_number") == MIT_NUMMER, (
        "AC-10: sms_verified_number muss die unveraenderte Kopie von sms_to sein, "
        f"Profil: {nachher}"
    )
    assert nachher.get("sms_verified_at"), f"AC-10: sms_verified_at fehlt, Profil: {nachher}"
    rest = {k: v for k, v in nachher.items() if k not in ("sms_verified_number", "sms_verified_at")}
    assert rest == mit_vorher, (
        "AC-10: alle uebrigen Felder muessen unveraendert bleiben (Read-Modify-Write-Merge).\n"
        f"vorher:  {mit_vorher}\nnachher: {rest}"
    )
    assert ohne.read_bytes() == ohne_vorher, "AC-10: Konten ohne sms_to bleiben unberuehrt"
    assert leer.read_bytes() == leer_vorher, "AC-10: Konten mit leerem sms_to bleiben unberuehrt"


def test_ac10_uebernimmt_den_rohwert_byteidentisch(tmp_path):
    """§10/AC-12: der Backfill trimmt NICHT — die Normalisierungs-Symmetrie
    entsteht an der Wirkstelle (config.py), nicht hier."""
    root = tmp_path / "users"
    pfad = _konto(root, "ungetrimmt", sms_to=UNGETRIMMT)

    _erfolg(_lauf(root, "--execute"), "AC-10 (Rohwert)")
    assert _laden(pfad).get("sms_verified_number") == UNGETRIMMT, (
        "AC-10: sms_verified_number muss die byteidentische Kopie des gelesenen sms_to sein, "
        f"bekommen {_laden(pfad).get('sms_verified_number')!r}"
    )


def test_ac10_zweiter_lauf_ist_wertgleich_idempotent(tmp_path):
    """Geprueft wird der WERT, nicht bloss 'ist gesetzt'. Die Beweislast traegt
    Konto B mit einem weit zurueckliegenden Zeitstempel — ein stilles
    Ueberschreiben faellt dort unabhaengig von der Uhrzeit des Laufs auf."""
    root = tmp_path / "users"
    a = _konto(root, "kontoa", sms_to=MIT_NUMMER)
    alt = "2020-01-01T00:00:00Z"
    b = _konto(root, "kontob", sms_to="+491519999999",
               sms_verified_number="+491519999999", sms_verified_at=alt)

    _erfolg(_lauf(root, "--execute"), "AC-10 (erster Lauf)")
    nach_erstem = _laden(a)
    assert nach_erstem.get("sms_verified_number") == MIT_NUMMER

    _erfolg(_lauf(root, "--execute"), "AC-10 (zweiter Lauf)")
    nach_zweitem = _laden(a)
    assert nach_zweitem == nach_erstem, (
        "AC-10: ein zweiter --execute-Lauf darf ein bereits nachgetragenes Konto nicht "
        f"veraendern.\nnach Lauf 1: {nach_erstem}\nnach Lauf 2: {nach_zweitem}"
    )
    assert _laden(b).get("sms_verified_at") == alt, (
        "AC-10: ein vorbestehender sms_verified_at-Wert muss wertgleich erhalten bleiben, "
        f"erwartet {alt!r}, gefunden {_laden(b).get('sms_verified_at')!r}"
    )


def test_ac10_execute_legt_eine_sicherung_an(tmp_path):
    """Bauart-Vorgabe §10 (Vorbild backfill_2271_email_verified.py): vor jeder
    Aenderung entsteht ein tar.gz unter `<root>.parent/.backups`."""
    root = tmp_path / "users"
    _konto(root, "sicherung", sms_to=MIT_NUMMER)

    _erfolg(_lauf(root, "--execute"), "AC-10 (Sicherung)")
    sicherungen = list((tmp_path / ".backups").glob("*.tar.gz"))
    assert sicherungen, (
        "AC-10: der --execute-Lauf muss vor der Aenderung eine tar.gz-Sicherung unter "
        f"{tmp_path / '.backups'} anlegen, gefunden: "
        f"{[p.name for p in (tmp_path / '.backups').glob('*')] if (tmp_path / '.backups').exists() else 'kein Verzeichnis'}"
    )
