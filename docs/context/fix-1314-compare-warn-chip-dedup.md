# Context: fix-1314-compare-warn-chip-dedup

## Request Summary
Die Ortsvergleich-Mail zeigt in der Matrix-Zeile „Amtliche Warnungen" pro Ort
**zwei identische „Hitze"-Chips** untereinander (Issue #1314, Epic #1301 Scheibe B).
Anders als Brand (mit Stufe) und Zugang tragen die Hitze-Chips kein
unterscheidendes Detail — echte visuelle Dubletten.

## Root Cause (Analyse)
Der Matrix-Zellen-Renderer `_render_warn_cell` (HTML) rendert pro Alert einen
Kürzel-Chip über `_warn_short(alert)`. Für `extreme_heat` liefert `_warn_short`
**immer** `("Hitze", "warn")` — ohne Stufe, Quelle oder Zeitfenster.

Die Datenebene ist bereits dedupliziert (`_dedup_alerts` → kanonische
`dedupe_official_alerts`), **aber** deren Schlüssel enthält seit **Issue #1245**
bewusst `(valid_from, valid_to)`: zwei Hitze-Warnungen mit unterschiedlichem
Zeitfenster (oder unterschiedlicher `region_label`/`dedup_id`/Quelle) überleben
die Dedup als **zwei** Einträge. In der Detail-Ansicht (Pro-Ort-Streifen) ist
das korrekt — dort werden Label/Quelle/Zeitraum ausgeschrieben, die Alerts sind
unterscheidbar. Im **komprimierten Matrix-Chip** fällt genau dieses
unterscheidende Detail weg → zwei sichtbar identische „Hitze"-Chips.

**Fix-Richtung:** Visuelle Dedup **nur im Matrix-Chip** (`_render_warn_cell`):
identisch gerenderte Chips (gleicher Kürzel-Text **und** gleiche Stufe/Farbe)
werden zu einem kollabiert. Die geteilte `dedupe_official_alerts` bleibt
unangetastet (Semantik #1245/#1134), der Pro-Ort-Streifen zeigt weiterhin beide
Warnungen mit Detail.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py` | `_render_warn_cell` (Z.343) — hier der Fix; `_warn_short` (Z.322), `_dedup_alerts` (Z.334), Matrix-Aufruf (Z.442), Pro-Ort-Streifen (Z.675) |
| `src/output/renderers/alert/official_alerts.py` | Kanonische `dedupe_official_alerts` (Z.274) — **NICHT** anfassen; #1245 fügte `(valid_from, valid_to)` in Schlüssel |
| `src/services/official_alerts/models.py` | `OfficialAlert`: `hazard, level, label, valid_from, valid_to, region_label, dedup_id` — Test-Konstruktion |
| `src/output/renderers/comparison.py` | Klartext-Compare — kein komprimierter Matrix-Chip, zeigt Detail pro Zeile (Z.162) → nicht betroffen, aber als Konsistenz-Check prüfen |

## Existing Patterns
- Chip-Farbe: `_ALERT_LEVEL_CELL.get(alert.level, ...)` (Z.74) → Stufe = sichtbares Unterscheidungsmerkmal.
- Kürzel-Map `_warn_short`: extreme_heat → „Hitze" (kein Detail), wildfire_risk → „Brand · {level}", access_ban → „Zugang".
- Dedup-Wrapper-Muster: `_dedup_alerts` kapselt die kanonische Quelle (ADR-0011, kein Copy-Paste).

## Dependencies
- Upstream: `dedupe_official_alerts` (liefert bereits nach Identität+Zeitraum gruppierte Liste).
- Downstream: HTML-Compare-Mail (email_spec_validator, `X-GZ-Mail-Type: compare`).

## Risks & Considerations
- **Regression-Risiko #1245/#1134:** Fix darf `dedupe_official_alerts` nicht berühren — nur die Chip-Render-Ebene. Zwei echte Warnungen unterschiedlicher **Stufe** (verschiedene Farbe) dürfen NICHT kollabieren.
- **Pro-Ort-Streifen (Z.675)** muss weiterhin beide Warnungen mit Detail zeigen — nicht mit ändern.
- **Klartext-Compare** prüfen: falls dort ebenfalls komprimierte Dubletten → mit abdecken; sonst dokumentiert außen vor.
- Repro-Test braucht zwei `extreme_heat`-Alerts gleicher Stufe mit unterschiedlichem `valid_from/valid_to` (oder `region_label`), die `_dedup_alerts` überleben.
