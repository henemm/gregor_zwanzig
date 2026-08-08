#!/usr/bin/env python3
"""
e2e_frontend_browser_gate.py — Frontend-Aenderungen erzwingen einen echten
Browserlauf (Issue #1558, Spec docs/specs/modules/feat_1558_frontend_browser_gate.md).

Beruehrt der auszuliefernde Aenderungssatz das Frontend, laedt dieses Gate die
Kernseiten selbst in einem echten Browser und verweigert das Staging-Verdict,
wenn dabei Konsolenfehler auftreten oder der Lauf nicht zustande kommt.

Die Fail-Grenze verlaeuft NICHT entlang "Exception ja/nein", sondern entlang
"liegt der Defekt im Gate oder im Nachweis":
  - Nachweis nicht erbringbar (Playwright fehlt, Staging tot, Anmeldung
    scheitert, Zugangsdaten fehlen, Konsolenfehler) → blockieren (!= 0).
  - Das Gate-Modul selbst ist kaputt → das faengt der Aufrufer
    (staging_gate._frontend_browser_gate) mit einer Warnung ab, nicht dieses
    Modul. Ein pauschales try/except hier waere genau das Sicherheits-Theater,
    das #1558 abschafft.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Fester Satz Kernseiten (Spec: nicht aus dem Diff abgeleitet — eine Zuordnung
# "geaenderte Komponente → betroffene Route" waere ohne Dependency-Graph eine
# Rate-Funktion, genau die Fehlerklasse, gegen die das Gate antritt).
CORE_PAGES: tuple[str, ...] = (
    "/", "/trips", "/trips/new", "/compare", "/compare/new", "/locations",
)
DEFAULT_BASE = "https://staging.gregor20.henemm.com"
# Zwei Schranken, zwei Zugangsdaten-Paare (#1307 Scheibe B): GZ_VALIDATOR_* ist
# der vorgeschaltete Basic-Auth-Schutz, GZ_AUTH_* die Anmeldung der Anwendung.
REQUIRED_CREDENTIALS = (
    "GZ_VALIDATOR_USER", "GZ_VALIDATOR_PASS", "GZ_AUTH_USER", "GZ_AUTH_PASS",
)
# Die Staging-Instanz hat EIGENE Anmeldedaten der Anwendung: gleicher
# Benutzername, anderes Passwort. Gemessen 2026-08-08 gegen POST /api/auth/login:
# die .env des Arbeitsordners -> 401 "invalid credentials", die Staging-.env ->
# 200 mit gz_session-Cookie. Ohne diese Unterscheidung meldet sich das Gate
# falsch an und blockiert JEDE Frontend-Auslieferung. Dieselbe Quelle nennen die
# Playwright-Staging-Specs (frontend/e2e/issue-1093-compare-layout-crash.spec.ts:21-22).
# Modul-Attribut UND Umgebungsvariable, damit die Wahl ueberschreibbar bleibt.
STAGING_ENV_PATH = Path("/home/hem/gregor_zwanzig_staging/.env")
APP_CREDENTIALS = ("GZ_AUTH_USER", "GZ_AUTH_PASS")


def _design_fidelity():
    """Wiederverwendung statt Neubau: load_validator_env() und
    unauthenticated_reason() leben in design_fidelity_diff.py (dort gemessen und
    gehaertet, #1307 Scheibe B). Import per Pfad, weil .claude/hooks kein Package
    ist (Muster staging_gate.py:45-53)."""
    path = Path(__file__).resolve().parent / "design_fidelity_diff.py"
    spec = importlib.util.spec_from_file_location("_dfd_for_frontend_gate", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_env_file(path: Path) -> dict:
    """Genuegsamer KEY=VALUE-Leser, gleiche Regeln wie load_validator_env()."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def load_validator_env() -> None:
    """Zugangsdaten beider Ebenen nachladen. Bewusst NICHT aus gate() heraus
    aufgerufen: os.environ.setdefault wuerde die Bedingung "Zugangsdaten fehlen"
    wieder aufheben und damit unpruefbar machen.

    Zielabhaengig: zeigt der Lauf auf Staging, stammen die ANWENDUNGS-Daten
    (GZ_AUTH_*) aus der Staging-.env — der Arbeitsordner hat ein anderes
    Passwort und liefert dort 401. Die vorgeschaltete nginx-Schranke
    (GZ_VALIDATOR_*) bleibt unveraendert aus .claude/validator.env.

    Rangfolge: bereits gesetzte Umgebungsvariablen > Staging-.env (nur bei
    Staging-Ziel) > .claude/validator.env und lokale .env. Umgesetzt ueber die
    Reihenfolge: setdefault macht den ersten Schreiber massgeblich.
    """
    base = (os.environ.get("GZ_VALIDATION_URL")
            or _read_env_file(Path(".claude/validator.env")).get("GZ_VALIDATION_URL", "")
            or DEFAULT_BASE)
    if "staging" in base:
        staging_env = Path(os.environ.get("GZ_STAGING_ENV_PATH") or STAGING_ENV_PATH)
        app = _read_env_file(staging_env)
        for key in APP_CREDENTIALS:
            if app.get(key):
                os.environ.setdefault(key, app[key])
    _design_fidelity().load_validator_env()


def _login(page, base: str, env: dict, messages: list[str]) -> None:
    """Formular-Anmeldung der Anwendung.

    Die Ausgaenge muessen UNTERSCHEIDBAR bleiben, sonst gilt ein generell
    kaputter Anmeldeweg als Beleg dafuer, dass ein falsches Passwort erkannt
    wurde (dieser Fehlschluss ist am 2026-08-08 passiert):
      - "Zugangsdaten fehlen"           → meldet bereits gate()
      - "Anmeldung nicht durchfuehrbar" → technisch (Zeitueberschreitung, Feld weg)
      - "Anmeldung abgelehnt"           → die Anwendung weist die Daten zurueck
      - "noch auf der Anmeldemaske"     → meldet _visit() ueber unauthenticated_reason
    """
    user, pw = env.get("GZ_AUTH_USER", ""), env.get("GZ_AUTH_PASS", "")
    if not (user and pw):
        return
    # Gemessen 2026-08-08 gegen Staging: die Ablehnung kommt als POST 401 auf
    # die Route "/login" (SvelteKit-Form-Action) — NICHT auf "/api/auth/login".
    # Ein fest verdrahteter Pfad haette hier still nichts gefunden. Deshalb die
    # allgemeine Bedingung: waehrend der Anmeldung ist JEDE fehlgeschlagene
    # POST-Antwort die abgelehnte Anmeldung.
    rejected: list[tuple[int, str]] = []
    page.on("response", lambda r: rejected.append((r.status, urlparse(r.url).path))
            if r.request.method == "POST" and r.status >= 400 else None)
    try:
        page.goto(base + "/login", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.fill("input[name='username']", user)
        page.fill("input[name='password']", pw)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception as exc:  # noqa: BLE001
        messages.append(f"/login: Anmeldung nicht durchfuehrbar — {exc}")
        return
    if rejected:
        status, route = rejected[-1]
        messages.append(
            f"/login: Anmeldung abgelehnt — die Anwendung hat die Zugangsdaten "
            f"zurueckgewiesen (HTTP {status} auf {route}). Geprueft werden "
            f"GZ_AUTH_USER/GZ_AUTH_PASS; fuer Staging stammen sie aus "
            f"{STAGING_ENV_PATH} (per GZ_STAGING_ENV_PATH ueberschreibbar)."
        )


def _visit(page, base: str, path: str, errors: list[str], messages: list[str],
           unauthenticated_reason) -> None:
    """Eine Kernseite laden und bewerten. Meldungen nennen immer Seite UND Grund."""
    del errors[:]
    try:
        page.goto(base + path, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception as exc:  # noqa: BLE001
        messages.append(f"{path}: Seite nicht ladbar — {exc}")
        return
    # #1307: eine fehlerfreie Anmeldemaske ist KEINE bestandene Kernseite.
    reason = unauthenticated_reason(
        page.url, page.query_selector("input[type='password']") is not None
    )
    if reason is not None:
        messages.append(f"{path}: keine angemeldete Kernseite — {reason}")
    for err in errors:
        messages.append(f"{path}: Konsolenfehler beim Laden — {err}")


def check_pages(base: str, paths, env: dict) -> tuple[int, list[str]]:
    """Kernseiten laden, Konsolenfehler sammeln. Getrennt von gate(), damit AC-2
    ohne Staging pruefbar bleibt.

    Erfasst werden ausschliesslich console(type == 'error') und pageerror —
    Warnungen zaehlen nicht (sonst erstickt das Gate im Rauschen von
    Drittbibliotheken; #1552 war ein 'error').

    Returns: (0 = alle Seiten sauber, 1 = Nachweis nicht erbracht, Meldungen).
    """
    messages: list[str] = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return 1, [f"Playwright nicht verfuegbar ({exc}) — Browserlauf nicht "
                   "durchfuehrbar, Nachweis nicht erbringbar."]

    unauthenticated_reason = _design_fidelity().unauthenticated_reason
    errors: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            kwargs = {"viewport": {"width": 1400, "height": 900}}
            basic_user = env.get("GZ_VALIDATOR_USER", "")
            basic_pass = env.get("GZ_VALIDATOR_PASS", "")
            if basic_user and basic_pass:
                kwargs["http_credentials"] = {"username": basic_user, "password": basic_pass}
            page = browser.new_context(**kwargs).new_page()
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            try:
                _login(page, base, env, messages)
                for path in paths:
                    _visit(page, base, path, errors, messages, unauthenticated_reason)
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 — Nachweis nicht erbringbar, nicht "Gate kaputt"
        messages.append(f"Browserlauf nicht zustande gekommen — {exc}")
        return 1, messages
    return (1 if messages else 0), messages


def gate(scope: str, env: dict) -> int:
    """0 = durchlassen, != 0 = blockieren.

    Bewertet AUSSCHLIESSLICH das uebergebene ``env`` und laedt selbst keine
    Zugangsdaten aus Dateien nach — das macht der Aufrufer
    (staging_gate._frontend_browser_gate).
    """
    if scope not in ("frontend-only", "full-stack"):
        return 0
    base = env.get("GZ_VALIDATION_URL") or DEFAULT_BASE
    missing = [k for k in REQUIRED_CREDENTIALS if not (env.get(k) or "").strip()]
    if missing:
        print(
            f"FEHLER: Zugangsdaten fuer den Browserlauf fehlen ({', '.join(missing)}) — "
            "der Nachweis ist nicht erbringbar. Kein Freifahrtschein: Gate blockt.",
            file=sys.stderr,
        )
        return 1
    rc, messages = check_pages(base, CORE_PAGES, env)
    for msg in messages:
        print(f"FEHLER: {msg}", file=sys.stderr)
    if rc == 0:
        print(f"OK: {len(CORE_PAGES)} Kernseiten ohne Konsolenfehler geladen ({base}).")
    return rc


if __name__ == "__main__":
    load_validator_env()
    sys.exit(gate(sys.argv[1] if len(sys.argv) > 1 else "frontend-only", dict(os.environ)))
