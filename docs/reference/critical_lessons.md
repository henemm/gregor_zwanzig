# Critical Lessons — dauerhafte Regeln ohne anderen Wächter

> Angelegt 2026-07-22 (Issue #1344, Marker-Sweep über das Spec-Archiv).
> Zweck: Regeln, die weder ein Test noch ein Hook noch CLAUDE.md/ADR absichert,
> aber dauerhaft gelten. Jeder Eintrag nennt die Quelle. Wenn eine Regel später
> mechanisch abgesichert wird (Test/Hook), den Eintrag hierher entfernen und am
> Wächter referenzieren — diese Datei soll klein bleiben.

## Visuelle Pixel-Diff-Tests: Schwellen nie anheben

Bei einem roten Pixel-Diff-Test (Design-Fidelity, `design_fidelity_diff.py`,
`SCREEN_THRESHOLD_MAP`) darf die Schwelle NIEMALS angehoben werden, um den Test
grün zu bekommen. Reihenfolge: erst das Diff-Bild ansehen, Ursache verstehen,
dann Design fixen (oder — nur bei bewusster Design-Änderung mit PO-go — die
Referenz aktualisieren). Threshold-Overrides sind temporär und werden wieder
gesenkt.
Quelle: `docs/specs/_archive/modules/issue_956_email_format.md` (§Known
Limitations); verwandt: CLAUDE.md Test-Politik (Schwellen-Manipulation-Verbot).

## Import-Richtung: `comparison_engine.py` importiert nie aus `user.py`-Konsumenten

`src/app/user.py` (bzw. dessen Lookup-Helfer) darf aus
`src/services/comparison_engine.py` heraus NICHT importiert werden — die
Import-Richtung bleibt Engine ← Aufrufer, sonst entsteht ein Zyklus über die
Official-Alerts-Kette. Kein `architecture_guard`-Wächter vorhanden; Regel gilt
per Konvention.
Quelle: `docs/specs/_archive/modules/issue_1034_official_alerts_foundation.md` (§189).
