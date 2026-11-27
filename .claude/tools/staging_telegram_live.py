#!/usr/bin/env python3
"""Telegram-Live-Messskript fuer /e2e-verify Schritt 3c (#2541).

Spec: docs/specs/modules/fix_2541_telegram_live_messskript.md

Fuehrt die Telegram-Live-Tests beider Dateien mit ``-m live`` und
``GZ_TELEGRAM_LIVE=1`` im Staging-Checkout aus. Die Zugangsdaten liest die
Test-Fixture selbst aus der Staging-``.env``; der Aufrufer braucht keine und
seine ``GZ_TELEGRAM_*``-Werte erreichen pytest nicht.

Aufruf:  python3 .claude/tools/staging_telegram_live.py
Exit:    0 = alle Soll-Live-Tests passed, nichts uebersprungen/fehlgeschlagen,
             zweiter Test-Nutzer unveraendert; Nachweis geschrieben
         1 = Befund (0 Tests, SKIPPED, Failure, Teardown-Error, fehlender
             Soll-Test, Fingerabdruck des zweiten Nutzers veraendert)
         2 = Umgebungsfehler (Checkout/uv/.env fehlt, pytest startet nicht,
             junit-Datei fehlt oder unlesbar)
stdout:  je Soll-Test eine PASS/FAIL-Zeile, Zaehler, ggf. Fehlerklasse.
         Keine pytest-Rohausgabe, keine Secrets (Maskierung in zwei Schichten).
Nachweis: nur bei Exit 0 ``<Repo dieses Werkzeugs>/.claude/e2e_telegram_live/<sha>.json``
         (sha = HEAD des Staging-Checkouts); liest staging_gate.py --write-verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = Path("/home/hem/gregor_zwanzig_staging")
NACHWEIS_DIR = REPO_ROOT / ".claude" / "e2e_telegram_live"
LIVE_DATEIEN = (
    "tests/tdd/test_issue_686_telegram_functional_live.py",
    "tests/tdd/test_telegram_live_zweisprachig.py",
)
GATE_HOOK = REPO_ROOT / ".claude" / "hooks" / "e2e_telegram_live.py"


def _lade_soll_tests() -> tuple:
    """Soll-Live-Tests aus dem Gate-Hook (eine Quelle). Fail-closed: ist der
    Hook nicht ladbar, endet das Werkzeug mit Exit 2 (Umgebungsfehler)."""
    import importlib.util

    try:
        spec = importlib.util.spec_from_file_location("_e2e_telegram_live_soll", str(GATE_HOOK))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        soll = tuple(mod.SOLL_TESTS)
    except Exception as exc:  # noqa: BLE001 — jeder Ladefehler ist Umgebungsfehler
        print(f"FEHLER: Soll-Liste aus {GATE_HOOK} nicht ladbar ({type(exc).__name__}).",
              file=sys.stderr)
        raise SystemExit(2) from None
    if not soll:
        print(f"FEHLER: Soll-Liste in {GATE_HOOK} ist leer.", file=sys.stderr)
        raise SystemExit(2)
    return soll


#: Soll-Live-Tests: alle live_telegram_enabled-gegateten Tests beider Dateien.
#: Einzige Quelle ist SOLL_TESTS in .claude/hooks/e2e_telegram_live.py (Gate);
#: ein Kern-Test haelt sie synchron (neuer Live-Test ohne Eintrag => rot).
SOLL_TESTS = _lade_soll_tests()
LIVE_NUTZER = "tg-live-e2e"
ZWEITER_NUTZER = "tg-live-e2e-zweiter"
PYTEST_TIMEOUT_S = 1800
TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{30,}")
MASKE = "***"
#: Schluessel der .env, deren Werte maskiert werden (Telegram, Tokens, Passwoerter).
_GEHEIM_SCHLUESSEL = re.compile(r"TELEGRAM|TOKEN|SECRET|PASS|KEY|CHAT_ID", re.I)
_MIN_GEHEIM_LAENGE = 4
_FEHLERKLASSE_RE = re.compile(r"\b([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Failed))\b")


# ---------------------------------------------------------------------------
# Umgebung und Befehl (AC-1)
# ---------------------------------------------------------------------------

def baue_env(umgebung) -> dict:
    """Kopie der Aufrufer-Umgebung ohne jedes ``GZ_TELEGRAM_*``, plus Opt-in."""
    env = {k: v for k, v in dict(umgebung).items() if not k.startswith("GZ_TELEGRAM_")}
    env["GZ_TELEGRAM_LIVE"] = "1"
    return env


def baue_befehl(junit: Path, uv: str = "uv") -> list:
    return [uv, "run", "pytest", "-m", "live", *LIVE_DATEIEN,
            "-p", "no:cacheprovider", f"--junitxml={junit}", "-q"]


# ---------------------------------------------------------------------------
# junit-Auswertung (AC-2)
# ---------------------------------------------------------------------------

def _leeres_ergebnis(fehler: str = "") -> dict:
    return {"passed": 0, "skipped": 0, "failures": 0, "errors": 0,
            "tests": [], "fehlend": list(SOLL_TESTS), "befunde": [], "fehler": fehler}


def _fehlerklasse(knoten) -> str:
    text = (knoten.get("message") or "") + " " + (knoten.get("type") or "")
    treffer = _FEHLERKLASSE_RE.search(text)
    return treffer.group(1) if treffer else knoten.tag


def _suite_summe(wurzel, feld: str) -> int:
    summe = 0
    for suite in wurzel.iter("testsuite"):
        try:
            summe += int(suite.get(feld) or 0)
        except ValueError:
            pass
    return summe


def werte_junit_aus(xml_text: str) -> tuple[int, dict]:
    """(Exit-Code, Ergebnis) aus junit-XML. 0 nur bei allen Soll-Tests passed
    und skipped = failures = errors = 0; unlesbares XML => 2."""
    try:
        wurzel = ET.fromstring(xml_text)
    except ET.ParseError:
        return 2, _leeres_ergebnis("junit-XML unlesbar")
    zaehler = {"skipped": 0, "failures": 0, "errors": 0}
    art_feld = {"skipped": "skipped", "failure": "failures", "error": "errors"}
    passed, befunde = [], []
    for case in wurzel.iter("testcase"):
        name = case.get("name") or "?"
        probleme = [k for k in case if k.tag in art_feld]
        for k in probleme:
            zaehler[art_feld[k.tag]] += 1
            befunde.append({"test": name, "art": k.tag, "klasse": _fehlerklasse(k)})
        if not probleme:
            passed.append(name)
    for feld in zaehler:
        zaehler[feld] = max(zaehler[feld], _suite_summe(wurzel, feld))
    basis = {n.split("[")[0] for n in passed}
    fehlend = [t for t in SOLL_TESTS if t not in basis]
    erg = {"passed": len(passed), **zaehler, "tests": passed,
           "fehlend": fehlend, "befunde": befunde, "fehler": ""}
    gruen = passed and not fehlend and not any(zaehler.values())
    return (0 if gruen else 1), erg


# ---------------------------------------------------------------------------
# Maskierung und Bericht (AC-4)
# ---------------------------------------------------------------------------

def maskiere(text: str, geheimnisse) -> str:
    """Erste Schicht: bekannte Werte; zweite Schicht: Telegram-Token-Muster."""
    werte = sorted({g for g in geheimnisse if g}, key=len, reverse=True)
    for wert in werte:
        text = text.replace(wert, MASKE)
    return TOKEN_RE.sub(MASKE, text)


def formatiere_bericht(erg: dict, geheimnisse) -> str:
    basis = {n.split("[")[0] for n in erg.get("tests", [])}
    zeilen = [f"{'PASS' if t in basis else 'FAIL'} {t}" for t in SOLL_TESTS]
    for b in erg.get("befunde", []):
        zeilen.append(f"FAIL {b['test']} ({b['art']}: {b['klasse']})")
    if erg.get("zweiter_nutzer_veraendert"):
        zeilen.append(f"FAIL zweiter Nutzer veraendert ({ZWEITER_NUTZER}: "
                      "Fingerabdruck-Abweichung)")
    zeilen.append(
        f"passed={erg.get('passed', 0)} skipped={erg.get('skipped', 0)} "
        f"failures={erg.get('failures', 0)} errors={erg.get('errors', 0)}")
    if erg.get("fehlend"):
        zeilen.append("fehlende Soll-Tests: " + ", ".join(erg["fehlend"]))
    if erg.get("fehler"):
        zeilen.append(f"Befund: {erg['fehler']}")
    return maskiere("\n".join(zeilen), geheimnisse)


# ---------------------------------------------------------------------------
# Nachweis (AC-5)
# ---------------------------------------------------------------------------

def schreibe_nachweis(ordner, sha: str, erg: dict, geheimnisse) -> Path:
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    daten = {
        "commit": sha,
        "passed": erg["passed"],
        "skipped": erg["skipped"],
        "failures": erg["failures"],
        "errors": erg["errors"],
        "tests": [maskiere(t, geheimnisse) for t in erg["tests"]],
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    text = maskiere(json.dumps(daten, ensure_ascii=False, indent=2), geheimnisse)
    pfad = ordner / f"{sha}.json"
    tmp = pfad.with_suffix(".json.tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, pfad)
    return pfad


def abschluss(exit_code: int, ordner, sha: str, erg: dict, geheimnisse) -> Path | None:
    """Nachweis nur bei Exit 0; sonst None (ein frueherer Nachweis bleibt unberuehrt)."""
    if exit_code != 0:
        return None
    return schreibe_nachweis(ordner, sha, erg, geheimnisse)


# ---------------------------------------------------------------------------
# Zweiter Nutzer (AC-8)
# ---------------------------------------------------------------------------

def fingerabdruck(verzeichnis) -> dict:
    """{relativer Pfad: (Groesse, sha256)} aller Dateien; Ordner mit None. Ohne mtime."""
    basis = Path(verzeichnis)
    ergebnis = {}
    if not basis.is_dir():
        return ergebnis
    for pfad in sorted(basis.rglob("*")):
        rel = pfad.relative_to(basis).as_posix()
        if pfad.is_dir():
            ergebnis[rel] = None
        else:
            inhalt = pfad.read_bytes()
            ergebnis[rel] = (len(inhalt), hashlib.sha256(inhalt).hexdigest())
    return ergebnis


def _zweiter_nutzer_bereit(data_dir: Path) -> Path:
    """Legt den zweiten Test-Nutzer bei Bedarf an (nie ueberschreiben)."""
    nutzer = data_dir / "users" / ZWEITER_NUTZER
    profil = nutzer / "user.json"
    if not profil.exists():
        nutzer.mkdir(parents=True, exist_ok=True)
        profil.write_text(json.dumps({
            "id": ZWEITER_NUTZER,
            "password_hash": "$2a$10$placeholder000000000000000000000000000000000",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mail_to": "",
            "language": "de",
            "is_test_user": True,
        }, indent=2), encoding="utf-8")
    return nutzer


# ---------------------------------------------------------------------------
# Ablauf (AC-3, main)
# ---------------------------------------------------------------------------

def _melde(text: str) -> None:
    print(text, file=sys.stderr)


def _lade_geheimnisse(env_datei: Path) -> list:
    geheim = []
    for zeile in env_datei.read_text(encoding="utf-8").splitlines():
        if "=" not in zeile or zeile.lstrip().startswith("#"):
            continue
        k, v = zeile.split("=", 1)
        wert = v.strip().strip("'\"")
        if _GEHEIM_SCHLUESSEL.search(k) and len(wert) >= _MIN_GEHEIM_LAENGE:
            geheim.append(wert)
    return geheim


def _vorpruefung(staging: Path, uv_arg: str) -> tuple[str | None, list, str]:
    """(uv-Pfad, Geheimnisse, Fehlermeldung); Meldung leer = alles da."""
    if not staging.is_dir():
        return None, [], f"Staging-Checkout fehlt: {staging}"
    uv = shutil.which(uv_arg)
    if uv is None:
        return None, [], f"uv nicht auffindbar: {uv_arg}"
    try:
        geheim = _lade_geheimnisse(staging / ".env")
    except (OSError, UnicodeDecodeError):
        return None, [], f"Staging-.env nicht lesbar: {staging / '.env'}"
    return uv, geheim, ""


def _staging_head(staging: Path) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(staging),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    sha = r.stdout.strip()
    return sha if r.returncode == 0 and sha else None


def _pytest_lauf(staging: Path, uv: str) -> tuple[int, dict]:
    """Startet pytest im Staging-Checkout; Ausgabe wird verworfen."""
    with tempfile.TemporaryDirectory(prefix="gz-tg-live-") as tmp:
        junit = Path(tmp) / "ergebnis.xml"
        try:
            subprocess.run(baue_befehl(junit, uv), cwd=str(staging),
                           env=baue_env(os.environ), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=PYTEST_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 2, _leeres_ergebnis(f"pytest startet nicht ({type(exc).__name__})")
        if not junit.exists():
            return 2, _leeres_ergebnis("junit-Datei fehlt (pytest lief nicht durch)")
        return werte_junit_aus(junit.read_text(encoding="utf-8", errors="replace"))


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Telegram-Live-Test auf Staging (#2541)")
    p.add_argument("--staging-dir", default=str(STAGING_DIR))
    p.add_argument("--nachweis-dir", default=str(NACHWEIS_DIR))
    p.add_argument("--uv", default="uv")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    staging = Path(args.staging_dir)
    uv, geheim, meldung = _vorpruefung(staging, args.uv)
    if meldung:
        _melde(f"UMGEBUNGSFEHLER: {meldung}")
        return 2
    sha = _staging_head(staging)
    if sha is None:
        _melde(f"UMGEBUNGSFEHLER: HEAD des Staging-Checkouts nicht lesbar: {staging}")
        return 2
    try:
        zweiter = _zweiter_nutzer_bereit(staging / "data")
        fp_vorher = fingerabdruck(zweiter)
    except OSError as exc:
        _melde(f"UMGEBUNGSFEHLER: zweiter Test-Nutzer nicht pruefbar ({type(exc).__name__})")
        return 2
    _melde(f"Telegram-Live-Lauf auf Staging {sha[:12]} ...")
    code, erg = _pytest_lauf(staging, uv)
    if code != 2 and fingerabdruck(zweiter) != fp_vorher:
        code, erg["fehler"] = 1, f"Daten des zweiten Test-Nutzers {ZWEITER_NUTZER} veraendert"
        erg["zweiter_nutzer_veraendert"] = True
    print(formatiere_bericht(erg, geheim))
    pfad = abschluss(code, Path(args.nachweis_dir), sha, erg, geheim)
    if pfad is not None:
        print(f"Nachweis: {pfad}")
    print({0: "BESTANDEN", 1: "BEFUND"}.get(code, "UMGEBUNGSFEHLER"))
    return code


if __name__ == "__main__":
    sys.exit(main())
