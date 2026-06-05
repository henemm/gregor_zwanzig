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
}


def load_validator_env() -> None:
    validator_env = Path(".claude/validator.env")
    if not validator_env.exists():
        return
    for line in validator_env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def take_screenshot(base: str, screen_url: str, ist_path: Path, viewport: tuple[int, int] = (1400, 900)) -> bool:
    """Login + navigate + screenshot via Playwright. Returns True on success."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not available — skipping live screenshot", file=sys.stderr)
        return False

    user = os.environ.get("GZ_VALIDATOR_USER", "")
    password = os.environ.get("GZ_VALIDATOR_PASS", "")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
            page = context.new_page()

            if user and password:
                try:
                    page.goto(base + "/login", timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.fill("input[name='username']", user)
                    page.fill("input[name='password']", password)
                    page.click("button[type='submit']")
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception as e:
                    print(f"Login warning (continuing): {e}", file=sys.stderr)

            try:
                page.goto(base + screen_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                print(f"Navigate warning (continuing): {e}", file=sys.stderr)

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
        default=os.environ.get("GZ_ACTIVE_WORKFLOW", "issue-603-design-fidelity-gate"),
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
    screenshot_ok = take_screenshot(base, screen_url, ist_path, viewport=viewport_size)
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
