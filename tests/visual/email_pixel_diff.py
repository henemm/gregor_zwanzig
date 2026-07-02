"""Wiederverwendbares Pixel-Diff-Werkzeug für gerendertes E-Mail-HTML (Issue #956).

Anders als `.claude/hooks/design_fidelity_diff.py` navigiert dieses Modul NICHT
zu einer Frontend-Route im laufenden Server, sondern rendert einen HTML-String
(Output von `render_html()`) direkt via Playwright `page.set_content()` und
vergleicht ihn per Pixel-Diff gegen ein Referenz-PNG.

Zweck: PO-Vorgabe für Issue #956 — "Du musst die TDD RED Tests visuell
erstellen. Code-Tests sind hier nicht erlaubt." Die sichtbaren Layout-Bugs
(Teil A/B/E) werden über Screenshot + Pixel-Diff bewiesen, nicht über
`assert 'x' in html`.

Der Diff-Algorithmus (`compute_diff`) ist 1:1 aus
`.claude/hooks/design_fidelity_diff.py::compute_diff()` übernommen
(Pixel-Schwelle 30, PIL + numpy, Diff-Visualisierung).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def screenshot_html(
    html: str,
    out_path: Path,
    viewport: tuple[int, int] = (700, 1000),
    clip: Optional[dict] = None,
) -> None:
    """Rendere einen HTML-String headless und screenshotte ihn.

    Args:
        html: vollständiges HTML-Dokument (Output von render_html()).
        out_path: Zielpfad für den Screenshot-PNG.
        viewport: (Breite, Höhe) des Browser-Viewports.
        clip: optionaler Bildausschnitt {"x","y","width","height"}.
    """
    from playwright.sync_api import sync_playwright

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            device_scale_factor=1,
        )
        page = context.new_page()
        page.set_content(html, wait_until="networkidle")
        # Kurz warten, damit Web-Fonts (falls verfügbar) und Layout stabil sind.
        page.wait_for_timeout(400)
        page.screenshot(path=str(out_path), clip=clip)
        browser.close()


def compute_diff(ist_path: Path, soll_path: Path, diff_path: Path) -> float:
    """Pixel-Diff-Prozentsatz berechnen + Diff-PNG schreiben. Gibt diff_pct zurück.

    1:1 adaptiert aus `.claude/hooks/design_fidelity_diff.py::compute_diff()`:
    - SOLL wird auf IST-Größe skaliert (LANCZOS) → cross-resolution-tolerant.
    - Pixel-Schwelle 30 filtert Anti-Aliasing-Rauschen.
    - Diff-Visualisierung: rot wo geändert, gedimmtes Original sonst.
    """
    from PIL import Image
    import numpy as np

    ist_img = Image.open(ist_path).convert("RGB")
    soll_img = Image.open(soll_path).convert("RGB").resize(ist_img.size, Image.LANCZOS)

    ist_arr = np.array(ist_img, dtype=int)
    soll_arr = np.array(soll_img, dtype=int)

    diff_arr = np.abs(ist_arr - soll_arr)
    changed = np.any(diff_arr > 30, axis=2)
    diff_pct = float(changed.sum()) / changed.size * 100

    diff_vis = np.zeros((*ist_arr.shape[:2], 3), dtype=np.uint8)
    diff_vis[changed] = [255, 0, 0]
    diff_vis[~changed] = (ist_arr[~changed] // 2).astype(np.uint8)
    Image.fromarray(diff_vis).save(diff_path)

    return diff_pct
