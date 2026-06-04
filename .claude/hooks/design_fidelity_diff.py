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
    "G-compare-uebersicht-kacheln": "/compare",
    "D-home-trip": "/",
    "D-home-compare": "/",
    "D-home-planning": "/",
    "E-trips-list-variant": "/trips",
    "F-trip-detail-overview": "/trips",
    "G-compare-wizard-step1": "/compare/new",
    "H-archive": "/archive",
    "I-wizard-step1-route": "/trips/new",
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


def take_screenshot(base: str, screen_url: str, ist_path: Path) -> bool:
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
            context = browser.new_context(viewport={"width": 1400, "height": 900})
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

    diff_arr = np.abs(ist_arr - soll_arr)
    changed = np.any(diff_arr > 10, axis=2)
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
    threshold = args.threshold
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

    # Take screenshot
    screenshot_ok = take_screenshot(base, screen_url, ist_path)
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
