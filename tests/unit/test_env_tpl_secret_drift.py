# doc-compliance-test
"""Drift-Ratsche .env.tpl (Issue #2163, Scheibe 2, AC-13 bis AC-15).

Liest Go-Config, Python-Settings und os.environ-Zugriffe als Daten und
prueft, dass jedes Secret in .env.tpl als Wert- oder Kommentarzeile steht.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]
GO_CONFIG = ROOT / "internal" / "config" / "config.go"
SRC_DIR = ROOT / "src"
ENV_TPL = ROOT / ".env.tpl"

SECRET_SUFFIXES = ("_SECRET", "_KEY", "_PASS", "_TOKEN", "_APIKEY")
GO_FIELD_RE = re.compile(r"^\s*([A-Z]\w*)\s+[\w\[\]\.\*]+\s*(`.*`)?\s*$")
GO_TAG_RE = re.compile(r'envconfig:"([A-Z0-9_]+)"')
ENVIRON_RE = re.compile(r'os\.environ(?:\.get\(|\[)\s*["\'](GZ_[A-Z0-9_]+)["\']')

# Tabelle "endgueltige Secret-Liste" der Spec auth_haertung_python_2163.md.
SPEC_LISTE = {
    "GZ_SESSION_SECRET", "GZ_CORE_SHARED_SECRET", "GZ_AUTH_PASS", "GZ_SMTP_PASS",
    "GZ_GOOGLE_SMTP_PASS", "GZ_FALLBACK_SMTP_PASS", "GZ_GOOGLE_CLIENT_SECRET",
    "GZ_TELEGRAM_WEBHOOK_SECRET", "GZ_SEVEN_WEBHOOK_PATH_SECRET",
    "GZ_SEVEN_WEBHOOK_SIGNING_KEY", "GZ_STALWART_WEBHOOK_PATH_SECRET",
    "GZ_STALWART_WEBHOOK_SECRET", "GZ_STATUS_TOKEN", "GZ_IMAP_PASS",
    "GZ_TEST_SMTP_PASS", "GZ_TEST_IMAP_PASS", "GZ_SEVEN_API_KEY",
    "GZ_SEVEN_SANDBOX_KEY", "GZ_TELEGRAM_BOT_TOKEN", "GZ_TELEGRAM_TEST_BOT_TOKEN",
    "GZ_METEOFRANCE_APIKEY",
}

# Die 7 urspruenglichen Wertzeilen (Stand vor #2163 Scheibe 2), byte-gleich.
ORIGINAL_WERTZEILEN = [
    'GZ_SMTP_HOST="op://Private/Gregor Zwanzig SMTP/host"',
    'GZ_SMTP_PORT="op://Private/Gregor Zwanzig SMTP/port"',
    'GZ_SMTP_USER="op://Private/Gregor Zwanzig SMTP/username"',
    'GZ_SMTP_PASS="op://Private/Gregor Zwanzig SMTP/password"',
    'GZ_MAIL_FROM="op://Private/Gregor Zwanzig SMTP/mail_from"',
    'GZ_MAIL_TO="op://Private/Gregor Zwanzig SMTP/mail_to"',
    'GZ_PO_EMAIL="op://Private/Gregor Zwanzig SMTP/mail_to"',
]


def _ist_secret(name: str) -> bool:
    return name.endswith(SECRET_SUFFIXES)


def _go_namen(go_config: Path) -> list[str]:
    text = go_config.read_text(encoding="utf-8")
    body = re.search(r"type Config struct \{\n(.*?)\n\}", text, re.S)
    assert body, f"type Config struct nicht gefunden in {go_config}"
    namen = []
    for zeile in body.group(1).splitlines():
        if not zeile.strip() or zeile.strip().startswith("//"):
            continue
        feld = GO_FIELD_RE.match(zeile)
        assert feld, f"Unbekannte Zeile im Config-Struct: {zeile!r}"
        tag = GO_TAG_RE.search(zeile)
        assert tag, f"Go-Feld {feld.group(1)} ohne envconfig-Tag - Name wird nicht geraten"
        namen.append("GZ_" + tag.group(1))
    return namen


def _python_namen() -> list[str]:
    assert Settings.model_config.get("env_prefix") == "GZ_"
    for name, feld in Settings.model_fields.items():
        assert feld.alias is None and feld.validation_alias is None, (
            f"Settings.{name} hat einen Alias - Env-Name nicht mehr GZ_<FELD>"
        )
    return ["GZ_" + name.upper() for name in Settings.model_fields]


def soll_secrets(go_config: Path, src_dir: Path) -> dict[str, str]:
    """Secret-Name -> Quelle(n), abgeleitet aus Go, Python-Settings, os.environ."""
    quellen: dict[str, set[str]] = {}
    for name in _go_namen(go_config):
        quellen.setdefault(name, set()).add("Go")
    for name in _python_namen():
        quellen.setdefault(name, set()).add("Python-Settings")
    for datei in sorted(src_dir.rglob("*.py")):
        for name in ENVIRON_RE.findall(datei.read_text(encoding="utf-8")):
            quellen.setdefault(name, set()).add(f"os.environ {datei.relative_to(src_dir)}")
    return {n: ", ".join(sorted(q)) for n, q in quellen.items() if _ist_secret(n)}


def fehlende_in_tpl(soll: dict[str, str], env_tpl: Path) -> dict[str, str]:
    vorhanden = set()
    for zeile in env_tpl.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(?:#\s*)?(GZ_[A-Z0-9_]+)=", zeile)
        if m:
            vorhanden.add(m.group(1))
    return {n: q for n, q in sorted(soll.items()) if n not in vorhanden}


def test_ac13_abgeleitete_liste_deckt_spec_tabelle():
    soll = soll_secrets(GO_CONFIG, SRC_DIR)
    assert SPEC_LISTE <= set(soll), f"Ableitung findet nicht: {sorted(SPEC_LISTE - set(soll))}"
    assert set(soll) <= SPEC_LISTE, f"Ableitung findet mehr als Spec: {sorted(set(soll) - SPEC_LISTE)}"


def test_ac13_jedes_secret_steht_in_env_tpl():
    fehlend = fehlende_in_tpl(soll_secrets(GO_CONFIG, SRC_DIR), ENV_TPL)
    assert not fehlend, "In .env.tpl fehlen:\n" + "\n".join(f"  {n}  ({q})" for n, q in fehlend.items())


def test_ac14_neues_go_secret_wird_als_fehlend_gemeldet(tmp_path):
    kopie = tmp_path / "config.go"
    text = GO_CONFIG.read_text(encoding="utf-8")
    zusatz = '\tNeuesGeheimnis string `envconfig:"NEUES_GEHEIMNIS_KEY" default:""`\n}'
    kopie.write_text(re.sub(r"(type Config struct \{\n.*?)\n\}", lambda m: m.group(1) + "\n" + zusatz, text, count=1, flags=re.S), encoding="utf-8")
    tpl = tmp_path / ".env.tpl"
    shutil.copy(ENV_TPL, tpl)
    fehlend = fehlende_in_tpl(soll_secrets(kopie, SRC_DIR), tpl)
    assert "GZ_NEUES_GEHEIMNIS_KEY" in fehlend
    assert "Go" in fehlend["GZ_NEUES_GEHEIMNIS_KEY"]


def test_ac15_wertzeilen_byte_gleich_und_kein_neuer_op_pfad():
    zeilen = ENV_TPL.read_text(encoding="utf-8").splitlines()
    wertzeilen = [z for z in zeilen if z.strip() and not z.lstrip().startswith("#")]
    assert wertzeilen == ORIGINAL_WERTZEILEN
    op_zeilen = [z for z in zeilen if "op://" in z]
    assert op_zeilen == ORIGINAL_WERTZEILEN, f"op:// ausserhalb der 7 Originalzeilen: {op_zeilen}"
    for z in zeilen:
        if re.match(r"^#\s*GZ_[A-Z0-9_]+=", z):
            assert "1Password-Eintrag noch anzulegen" in z, f"Vermerk fehlt: {z!r}"
