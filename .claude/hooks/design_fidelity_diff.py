#!/usr/bin/env python3
"""
Design-Fidelity Pixel-Diff Tool (Issue #603)

Usage:
    python3 .claude/hooks/design_fidelity_diff.py --screen <screen-id>
    python3 .claude/hooks/design_fidelity_diff.py --screen <screen-id> --threshold 5.0

Exit 0 = diff_pct < threshold (PASS)
Exit 1 = diff_pct >= threshold (FAIL) or missing soll-PNG
"""
import argparse
import datetime
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

SCREEN_URL_MAP = {
    # Home (D) — gleiche Route, verschiedene Cockpit-Varianten
    "D-home-trip": "/",
    "D-home-compare": "/",
    "D-home-planning": "/",

    # Trips-Liste (E)
    "E-trips-list-variant": "/trips",

    # Trip-Detail (F) — Standard auf erstem Trip, Tab-Varianten als Hinweis
    "F-trip-detail-overview": "/trips",
    "F-trip-detail-wetter": "/trips",
    "F-trip-detail-reports-collapsed": "/trips",
    "F-trip-detail-reports-expanded": "/trips",
    "F-trip-detail-editor-top": "/trips",

    # Compare (G)
    "G-compare-uebersicht-kacheln": "/compare",
    "G-compare-detail": "/compare",
    "G-compare-edit": "/compare",
    "G-compare-edit-locations": "/compare",
    "G-compare-edit-step1": "/compare/new",
    "G-compare-new": "/compare/new",
    "G-compare-wizard-step1": "/compare/new",

    # Archiv (H) — KORREKTER Route-Pfad ist /archiv (Deutsch), nicht /archive
    "H-archive": "/archiv",

    # Trip-Wizard (I)
    "I-wizard-step1-route": "/trips/new",
    "I-wizard-step2-etappen": "/trips/new",
    "I-wizard-step3-wetter": "/trips/new",
    "I-wizard-step4-layout": "/trips/new",
    "I-wizard-step5-reports": "/trips/new",

    # Waypoint-Editor (J) — Trip-Edit Etappen-Tab
    "J-waypoint-editor-etappen-tab": "/trips",

    # Alert-Config (K) — als Tab im Trip-Detail
    "K-alert-config-list": "/trips",

    # Metrics-Editor (L) — als Tab im Trip-Detail mit Varianten
    "L-metrics-editor-table-preview": "/trips",
    "L-metrics-editor-sms-preview": "/trips",
    "L-metrics-editor-signal-preview": "/trips",
    "L-metrics-editor-save-preset": "/trips",

    # Location-New (M) — Modal aus /locations
    "M-location-new": "/locations",
}

# Per-Screen Threshold-Overrides (Default 10 %).
# Erhöhte Schwellen sind temporär und bezeichnen Layout/Sidebar-Drift, die
# in eigenen Sub-Issues angegangen werden. Sobald ein Layout-Issue
# abgearbeitet ist, soll der Override hier zurück auf 10 % gesenkt werden.
SCREEN_THRESHOLD_MAP: dict[str, float] = {
    # #583 Archiv: 30 % wegen Sidebar-User-Block + Stats-Strip-Umbruch
    # (gehört nicht zum Archiv-Screen, sondern zu Layout/Sidebar-Komponente).
    "H-archive": 30.0,
    # #579 Home-Screen (alle 3 Modi trip/compare/planning teilen die Route "/"):
    # 30 % dokumentierter Override. Ein exaktes <10 % ist strukturell unmöglich:
    #   (a) SOLL-PNGs sind veraltet — sie zeigen durchgehend den per PO-Entscheidung
    #       #610 app-weit entfernten Signal-Kanal (Kanal-Pills, "signal"-Versandzeilen).
    #   (b) Daten-Divergenz: das Staging-Test-Konto ist dünn (1 Vergleich, keine
    #       Region, kein Archiv, keine Sende-Historie) gegenüber datenreichem SOLL
    #       (KHW-403-Trip, 8 Archiv-Trips, Briefing-Timeline).
    #   (c) 3 Modi / 1 URL: das Konto ist zu einem Zeitpunkt nur in EINEM Modus
    #       (aktuell compare) — trip/planning werden gegen ein Wrong-Mode-SOLL
    #       gemessen und sind nie apple-to-apple.
    # Das LAYOUT ist 1:1 zur JSX bestätigt: staging-validator 2026-06-07 (#579)
    # AC-1/AC-3/AC-4 PASS (Compare-Empty-State "Kein Trip geplant" + primary
    # "Neuer Trip", Eyebrow "Einrichten", Hero/Outbox/Alerts/5 Schnellaktionen).
    # Reine Inhalts-/SOLL-Aktualitäts-Divergenz, kein Layout-Drift.
    # (Ersetzt den temporären #578-Override von 20 %.)
    "D-home-trip": 30.0,
    "D-home-compare": 30.0,
    "D-home-planning": 30.0,
    # #486 E-trips-list-variant: 30 % wegen Daten-Divergenz — das SOLL-Bild zeigt
    # Demo-Trips (KHW 403, GR221 …) mit anderen Namen/Etappen/Stats, das Staging-
    # Test-Konto zeigt seine echten Trips (Dachstein, Gardasee …). Das Layout ist
    # 1:1 (staging-validator 2026-06-05 AC-7 PASS: ⋯-Menü statt Icon-Geschwader,
    # gleiche Spalten/Zeilenstruktur). Reine Inhalts-, keine Layout-Divergenz.
    "E-trips-list-variant": 30.0,
    # #582 G-compare-uebersicht-kacheln: 30 % wegen Daten-Divergenz UND veraltetem
    # SOLL. Das SOLL-Bild zeigt 4 Demo-Vergleiche (2 aktiv, 1 Draft, mit Regionen,
    # Kanal-Pills inkl. SIGNAL und "zuletzt heute/Sa"); das Staging-Test-Konto zeigt
    # 2 pausierte Vergleiche ohne Kanäle. Zusätzlich ist das SOLL veraltet: es zeigt
    # den Signal-Kanal, der per PO-Entscheidung #610 app-weit entfernt wurde — ein
    # exaktes <10 % ist dagegen strukturell unmöglich. Das Layout ist 1:1
    # (staging-validator 2026-06-07: AC-1/2/3/6/7 PASS, AC-4 SKIPPED kein aktives
    # Preset; Kachel-Struktur Dot/Eyebrow+Region/Meta/Pills/gestrichelter Fuß 1:1
    # nach molecules.jsx). Reine Inhalts-/SOLL-Aktualitäts-Divergenz, kein Layout-Drift.
    "G-compare-uebersicht-kacheln": 30.0,
}

# Per-Screen Pre-Screenshot-Actions (für Modale/Tabs/etc.).
# Format: {screen_id: [(action_type, selector), ...]}
# Action-Types: "click", "wait_selector".
SCREEN_PRE_ACTIONS: dict[str, list[tuple[str, str]]] = {
    # Modal-Triggers: Buttons klicken, die Modal öffnen
    "M-location-new": [("click", 'button:has-text("Neuer Ort")'), ("wait_selector", "text=Verortung")],
    # NB (#646): Ein automatischer Pixel-Gate für G-compare-detail ist nicht
    # praktikabel — die Compare-Kacheln reagieren nur auf Svelte-onclick
    # (JS-dispatchEvent), nicht auf Playwright-page.click; zudem nutzt der SOLL
    # Mock-Daten, die nie zum Live-Testkonto passen. Fidelity wird stattdessen
    # per staging-validator (AC-Walk + Screenshots) verifiziert. Kein Pre-Action-
    # Eintrag hier, um Fake-Passes (Liste-vs-Hub-SOLL) zu vermeiden.
    # Fix #622: Trip-Wizard-Tabs ansteuern (sonst Screenshot immer Route-Tab).
    # step2: Etappen-Tab erst nach Name+Datum unlock navigierbar.
    # Hinweis: Desktop-Date-Input hat kein data-testid → input[type="date"] nötig.
    "I-wizard-step2-etappen": [
        ("fill", '[data-testid="trip-new-name-input"]', "Fidelity Test"),
        ("fill", 'input[type="date"]', "2026-09-01"),
        ("wait_ms", "400"),
        ("click", '[role="tab"]:has-text("Etappen & GPX")'),
        ("wait_selector", '[role="tab"][aria-selected="true"]:has-text("Etappen & GPX")'),
    ],
    "I-wizard-step3-wetter": [
        ("click", '[role="tab"]:has-text("Wegpunkte prüfen")'),
        ("wait_selector", '[role="tab"][aria-selected="true"]:has-text("Wegpunkte prüfen")'),
    ],
}


def load_validator_env() -> None:
    """Zugangsdaten nachladen — ZWEI Quellen, zwei verschiedene Schranken:

    - `.claude/validator.env` (GZ_VALIDATOR_*) → der vorgeschaltete
      Basic-Auth-Schutz vor Staging.
    - `.env` (GZ_AUTH_*) → die Anmeldung der Anwendung selbst.

    Beides wurde frueher aus GZ_VALIDATOR_* bedient; die Anwendung lehnt diese
    Daten ab (#1307 Scheibe B), wodurch das Werkzeug still die Anmeldemaske
    fotografierte. Bereits gesetzte Umgebungsvariablen haben Vorrang.
    """
    for env_file in (Path(".claude/validator.env"), Path(".env")):
        if not env_file.exists():
            continue
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def unauthenticated_reason(final_url: str, has_password_field: bool) -> "str | None":
    """Warum die aufgenommene Seite KEINE gueltige, angemeldete Zielseite ist.

    Rueckgabe: Begruendung als Text, oder None wenn die Aufnahme gueltig ist.

    Hintergrund (#1307 Scheibe B): Die Formular-Anmeldung scheitert LAUTLOS —
    `page.fill`/`page.click` werfen keine Ausnahme, wenn die Anwendung die
    Zugangsdaten ablehnt. Das Werkzeug lief weiter, fotografierte die
    Anmeldemaske und schrieb einen Bericht mit `passed: true` (23,35 % bei
    Schwelle 30 %). Ein Design-Waechter, der sich damit zufriedengibt, prueft
    nichts. Diese Funktion prueft deshalb an der Stelle, an der es zaehlt:
    unmittelbar vor der Aufnahme.

    Zwei unabhaengige Merkmale, damit ein einzelner Umbau (umbenanntes Feld,
    andere Rueckleitung) die Pruefung nicht still aushebelt.
    """
    path = urlparse(final_url).path
    if path == "/login" or path.startswith("/login/"):
        return (
            f"die Seite steht nach der Anmeldung auf {final_url} — "
            "zurueckgeleitet auf die Anmeldemaske"
        )
    if has_password_field:
        return (
            "auf der Zielseite ist noch ein Passwortfeld sichtbar — "
            "die Anmeldung hat nicht gegriffen"
        )
    return None


def take_screenshot(
    base: str,
    screen_url: str,
    ist_path: Path,
    viewport: tuple[int, int] = (1400, 900),
    pre_actions: list[tuple[str, str]] | None = None,
) -> bool:
    """Login + navigate + optional pre-actions + screenshot via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not available — skipping live screenshot", file=sys.stderr)
        return False

    # Zwei Schranken, zwei Zugangsdaten-Paare (#1307 Scheibe B):
    #   basic_* → vorgeschalteter Basic-Auth-Schutz (nginx, realm "Staging")
    #   app_*   → Anmeldung der Anwendung selbst
    # Frueher bediente GZ_VALIDATOR_* beides. Die Anwendung lehnt diese Daten
    # ab (gemessen: POST /api/auth/login → 401 "invalid credentials"), ohne
    # dass page.fill/click eine Ausnahme werfen — deshalb blieb es still.
    basic_user = os.environ.get("GZ_VALIDATOR_USER", "")
    basic_pass = os.environ.get("GZ_VALIDATOR_PASS", "")
    app_user = os.environ.get("GZ_AUTH_USER", "")
    app_pass = os.environ.get("GZ_AUTH_PASS", "")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Staging liegt hinter einem vorgeschalteten Basic-Auth-Schutz
            # (nginx, realm "Staging"): /login antwortet ohne Zugangsdaten mit
            # 401 (gemessen 2026-08-05). Ohne http_credentials fotografiert das
            # Werkzeug die Sperrseite statt der angeforderten Seite
            # (#1307 Scheibe B, AC-11). Die Formular-Anmeldung unten bleibt
            # davon unberuehrt — beide Schritte sind noetig.
            context_kwargs = {"viewport": {"width": viewport[0], "height": viewport[1]}}
            if basic_user and basic_pass:
                context_kwargs["http_credentials"] = {
                    "username": basic_user, "password": basic_pass,
                }
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            if app_user and app_pass:
                try:
                    page.goto(base + "/login", timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.fill("input[name='username']", app_user)
                    page.fill("input[name='password']", app_pass)
                    page.click("button[type='submit']")
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception as e:
                    print(f"Login warning (continuing): {e}", file=sys.stderr)

            try:
                page.goto(base + screen_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                print(f"Navigate warning (continuing): {e}", file=sys.stderr)

            if pre_actions:
                for action in pre_actions:
                    action_type = action[0]
                    selector = action[1] if len(action) > 1 else ""
                    value = action[2] if len(action) > 2 else ""
                    try:
                        if action_type == "click":
                            page.click(selector, timeout=8000)
                        elif action_type == "wait_selector":
                            page.wait_for_selector(selector, timeout=8000)
                        elif action_type == "fill":
                            page.fill(selector, value, timeout=8000)
                        elif action_type == "force_fill":
                            # JS-based fill — works even when element is off-screen / hidden
                            page.evaluate(
                                "([sel, val]) => { const el = document.querySelector(sel); "
                                "if (!el) return; el.value = val; "
                                "el.dispatchEvent(new Event('input', {bubbles:true})); "
                                "el.dispatchEvent(new Event('change', {bubbles:true})); }",
                                [selector, value],
                            )
                        elif action_type == "dispatch_change":
                            page.fill(selector, value, timeout=8000)
                            page.evaluate(
                                "(sel) => { const el = document.querySelector(sel); "
                                "if (el) el.dispatchEvent(new Event('change', {bubbles:true})); }",
                                selector,
                            )
                        elif action_type == "wait_ms":
                            page.wait_for_timeout(int(selector))
                    except Exception as e:
                        print(f"Pre-action {action_type}({selector}) warning: {e}", file=sys.stderr)
                # Modal-Render-Zeit
                page.wait_for_timeout(800)

            # Fail-closed VOR der Aufnahme (#1307 Scheibe B): ist die Anmeldung
            # nicht gegriffen, wird NICHT fotografiert — sonst entsteht ein
            # Bericht ueber die Anmeldemaske, der unter der Schwelle liegt und
            # `passed: true` traegt. Genau so ist es passiert.
            reason = unauthenticated_reason(
                page.url,
                page.query_selector("input[type='password']") is not None,
            )
            if reason is not None:
                print(
                    f"ERROR: keine gueltige Aufnahme — {reason}. "
                    "Erwartet wird die angemeldete Zielseite; geprueft werden "
                    "GZ_AUTH_USER/GZ_AUTH_PASS (Anwendung) und "
                    "GZ_VALIDATOR_USER/GZ_VALIDATOR_PASS (vorgeschalteter "
                    "Schutz). Kein Bericht geschrieben.",
                    file=sys.stderr,
                )
                browser.close()
                return False

            page.screenshot(path=str(ist_path), full_page=False)
            browser.close()
        return True
    except Exception as e:
        print(f"Screenshot error: {e}", file=sys.stderr)
        return False


def compute_diff(ist_path: Path, soll_path: Path, diff_path: Path) -> float:
    """Compute pixel diff percentage and write diff-PNG. Returns diff_pct."""
    from PIL import Image
    import numpy as np

    ist_img = Image.open(ist_path).convert("RGB")
    soll_img = Image.open(soll_path).convert("RGB").resize(ist_img.size, Image.LANCZOS)

    ist_arr = np.array(ist_img, dtype=int)
    soll_arr = np.array(soll_img, dtype=int)

    # Pixel-threshold 30 filters anti-aliasing noise from cross-resolution
    # comparison; real visual drift exceeds this comfortably.
    diff_arr = np.abs(ist_arr - soll_arr)
    changed = np.any(diff_arr > 30, axis=2)
    diff_pct = float(changed.sum()) / changed.size * 100

    # Diff visualization: red where changed, dimmed original elsewhere
    diff_vis = np.zeros((*ist_arr.shape[:2], 3), dtype=np.uint8)
    diff_vis[changed] = [255, 0, 0]
    diff_vis[~changed] = (ist_arr[~changed] // 2).astype(np.uint8)
    Image.fromarray(diff_vis).save(diff_path)

    return diff_pct


def main() -> None:
    parser = argparse.ArgumentParser(description="Design-Fidelity Pixel-Diff Tool")
    parser.add_argument("--screen", required=True, help="Screen ID (e.g. G-compare-uebersicht-kacheln)")
    parser.add_argument("--threshold", type=float, default=10.0, help="Max allowed diff %% (default: 10.0)")
    parser.add_argument(
        "--workflow",
        # #1307 Scheibe B (AC-12): beide Schreibweisen der Workflow-Kennung,
        # in DERSELBEN Reihenfolge wie pre_issue_close_design_gate.py — sonst
        # legt das Werkzeug seinen Bericht in einem anderen Ordner ab als der
        # Waechter durchsucht, und der frische Bericht wird nie gefunden.
        default=(
            os.environ.get("OPENSPEC_ACTIVE_WORKFLOW")
            or os.environ.get("GZ_ACTIVE_WORKFLOW")
            or "issue-603-design-fidelity-gate"
        ),
        help="Workflow name for artifact directory",
    )
    args = parser.parse_args()

    load_validator_env()

    screen = args.screen
    # CLI --threshold überschreibt Map (für Ad-hoc-Läufe); sonst Map > Default
    if "--threshold" in sys.argv:
        threshold = args.threshold
    else:
        threshold = SCREEN_THRESHOLD_MAP.get(screen, args.threshold)
    workflow = args.workflow

    base = os.environ.get("GZ_VALIDATION_URL", "https://staging.gregor20.henemm.com")

    # Resolve screen URL
    screen_url = SCREEN_URL_MAP.get(screen, "/")

    # Paths
    repo = Path(".")
    soll_path = repo / "claude-code-handoff/current/soll" / f"{screen}.png"
    artifact_dir = repo / "docs/artifacts" / workflow
    artifact_dir.mkdir(parents=True, exist_ok=True)

    ist_path = artifact_dir / f"design-diff-{screen}-ist.png"
    diff_path = artifact_dir / f"design-diff-{screen}-diff.png"
    report_path = artifact_dir / f"design-diff-{screen}.json"

    # Ein frueherer, bestandener Bericht darf einen jetzt scheiternden Lauf
    # nicht ueberleben (#1307 Scheibe B): der Waechter sucht per Glob nach
    # IRGENDEINEM `passed: true` und wuerde sonst den alten Nachweis fuer den
    # neuen Stand halten. Fail-closed: erst weg, dann neu belegen.
    report_path.unlink(missing_ok=True)

    # Check soll-PNG
    if not soll_path.exists():
        print(f"ERROR: Soll-PNG not found: {soll_path}", file=sys.stderr)
        sys.exit(1)

    # Choose IST viewport: SOLL-PNGs were rendered at desktop layout but
    # downscaled to ~815px. Mobile-rendering at 815px would compare apples
    # to oranges, so pick a desktop viewport that matches the SOLL aspect
    # ratio (height derived) when aspect > 1.4 (desktop), else use SOLL size
    # directly (mobile screenshots).
    from PIL import Image as _Image
    with _Image.open(soll_path) as _s:
        soll_w, soll_h = _s.size
    aspect = soll_w / soll_h if soll_h else 1.5
    if aspect > 1.4:
        # Claude-Design SOLLs werden i.d.R. bei 1024px-Desktop-Viewport
        # gerendert (dann downscaled auf 815). 1024 reproduziert die
        # gleichen Layout-Entscheidungen (Spaltenbreiten, Truncation).
        target_w = 1024
        target_h = int(round(target_w / aspect))
        viewport_size = (target_w, target_h)
    else:
        viewport_size = (soll_w, soll_h)
    pre_actions = SCREEN_PRE_ACTIONS.get(screen)
    screenshot_ok = take_screenshot(
        base, screen_url, ist_path,
        viewport=viewport_size,
        pre_actions=pre_actions,
    )
    if not screenshot_ok or not ist_path.exists():
        print(f"ERROR: Screenshot failed or ist-PNG missing: {ist_path}", file=sys.stderr)
        sys.exit(1)

    # Compute diff
    diff_pct = compute_diff(ist_path, soll_path, diff_path)
    passed = diff_pct < threshold

    # Write report
    report = {
        "screen": screen,
        "diff_pct": round(diff_pct, 4),
        "threshold": threshold,
        "passed": passed,
        "ist_path": str(ist_path),
        "soll_path": str(soll_path),
        "diff_path": str(diff_path),
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "workflow": workflow,
    }
    report_path.write_text(json.dumps(report, indent=2))

    print(f"diff_pct={diff_pct:.2f}% threshold={threshold}% passed={passed}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
