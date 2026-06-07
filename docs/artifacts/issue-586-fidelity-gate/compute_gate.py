#!/usr/bin/env python3
"""Pixel-Diff Live vs. JSX-Referenz (#586) + Diff-Visualisierung.

Wegwerf-Skript. Berechnet den Diff (gleiche Logik wie design_fidelity_diff.py,
Pixel-Threshold 30) und schreibt eine Diff-PNG zur visuellen Inspektion. Die
finale `passed`/`threshold`-Entscheidung trifft der Mensch nach Inspektion des
Diff-Bildes (Memory: erst Diff-Bild ansehen, dann Schwelle).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
LIVE = HERE / "live-alert-config.png"
REF = HERE / "reference-alert-config.png"
DIFFVIS = HERE / "diff-vis.png"


def main() -> int:
    if not (LIVE.exists() and REF.exists()):
        print(f"Bilder fehlen: live={LIVE.exists()} ref={REF.exists()}", file=sys.stderr)
        return 2
    ist = Image.open(LIVE).convert("RGB")
    soll = Image.open(REF).convert("RGB").resize(ist.size, Image.LANCZOS)
    a = np.array(ist, dtype=int)
    s = np.array(soll, dtype=int)
    changed = np.any(np.abs(a - s) > 30, axis=2)
    diff_pct = float(changed.sum()) / changed.size * 100

    vis = np.zeros((*a.shape[:2], 3), dtype=np.uint8)
    vis[changed] = [255, 0, 0]
    vis[~changed] = (a[~changed] // 2).astype(np.uint8)
    Image.fromarray(vis).save(DIFFVIS)

    print(f"diff_pct={diff_pct:.2f}%  (live={ist.size}, ref→resized)")
    print(f"Diff-Visualisierung: {DIFFVIS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
