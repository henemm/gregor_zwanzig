---
entity_id: fix_26_email_render_drift
type: module
created: 2026-06-26
updated: 2026-06-26
status: draft
version: "1.0"
tags: [email, renderer, design-compliance]
---

# Briefing-Email · Render-Drift beheben (Issue #26)

## Approval

- [ ] Approved

## Purpose

Drei sichtbare Abweichungen der ausgelieferten Briefing-Email vom Design
(`screen-output-preview.jsx`) beheben: unvollständiger Header (A1),
fehlende RiskDot-Spalte in der Stunden-Tabelle (A3), und zwei getrennte
farbige Kästen (Tageslage + Vortag) zu einem einzigen Akzent-Bar-Lead
zusammenführen (B1–B3).

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `render_html`, `_render_html_table`
- **Canonical Design:** `screen-output-preview.jsx` → `EmailPreview`, `EmailDataTable`, `EmailVortag`

## Estimated Scope

- **LoC:** ~90
- **Files:** 4 (`html.py`, `__init__.py`, `trip_report.py`, `trip_report_scheduler.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `render_html` | function | Haupt-HTML-Renderer — alle Änderungen landen hier |
| `_render_html_table` | function | Tabellen-Renderer — RiskDot-Spalte ergänzen |
| `render_email` | function | Orchestrierer — neuen `stage_total` param durchreichen |
| `TripReportFormatter.format_email` | method | stage_total aus trip berechnen und übergeben |
| `TripReportScheduler` | class | stage_total = len(trip.stages) an format_email übergeben |

## Implementation Details

### A1 — Header vervollständigen

`stage_name` hat das Format `"Etappe N: Route"` (z.B. `"Etappe 1: Calenzana → Carrozzu"`).
Daraus ableiten:
- `_stage_num`: regex `r"Etappe\s+(\d+)"` → `"1"`
- `_route_title`: alles nach `": "` → `"Calenzana → Carrozzu"` (Fallback: `stage_name`)

**Linke Spalte** (wie JSX):
```
MORGEN-BRIEFING · Etappe 1          ← eyebrow (accent, mono 10px)
Calenzana → Carrozzu                 ← Haupttitel 22px (war: trip_name)
Mi · 27.06.2026 · 06:01 MESZ        ← Datum+Zeit+Wochentag (war: nur Datum)
```

**Rechte Spalte** (wie JSX):
```
GREGOR ZWANZIG                       ← eyebrow (muted, mono 10px) ✓ bereits vorhanden
KHW 403                              ← trip_name 14px (war: stage_name)
Etappe 1 / 12                        ← neu: stage_num / stage_total (mono 12px)
```

**Datum+Zeit:** `sent_at` ist optional → wenn vorhanden: Wochentag + Datum + Uhrzeit + Zeitzone.
Wochentag-Map: `["Mo","Di","Mi","Do","Fr","Sa","So"]`.
Wenn `sent_at is None` → nur `report_date` (Rückwärtskompatibilität).

**stage_total:** Neuer optionaler Parameter `stage_total: Optional[int] = None` in:
1. `render_html()` 
2. `render_email()`
3. `TripReportFormatter.format_email()`
4. `TripReportScheduler._send_report()` → `stage_total=len(trip.stages)`

Wenn `stage_total is None` → nur `"Etappe N"` (ohne `/12`).

### A3 — RiskDot-Spalte in `_render_html_table`

Am Ende jeder Datenzeile eine zusätzliche Spalte mit einem farbigen Punkt.

**Header:** `<th style="...">·</th>` (kein Label, zentriert, 4px padding)

**Risk-Level pro Zeile** — abgeleitet aus Schwellwerten (gleiche Logik wie Highlighting):
```python
def _row_risk(r: dict) -> str:
    thunder = float(r.get("thunder") or 0)
    if thunder > 20:
        return "risk"
    gust = float(r.get("gust") or 0)
    wind = float(r.get("wind") or 0)
    precip = float(r.get("precip") or 0)
    pop = float(r.get("pop") or 0)
    vis_raw = r.get("vis")
    vis = float(vis_raw) / 1000 if vis_raw and float(vis_raw) > 100 else float(vis_raw or 99)
    if thunder > 0 or gust > 30 or wind > 20 or precip > 1 or pop > 50 or vis < 2:
        return "watch"
    return "ok"
```

**RiskDot HTML:**
```python
_RISK_DOT_COLORS = {
    "ok":    ("#15803d", "rgba(21,128,61,0.18)"),
    "watch": ("#c2410c", "rgba(194,65,12,0.20)"),
    "risk":  ("#b91c1c", "rgba(185,28,28,0.22)"),
}
```
Dot = `<span>` mit `width:10px; height:10px; border-radius:50%; background; box-shadow` (identisch `_risk_dot()`).
Zell-Style: `padding:8px 4px; text-align:center;`

### B1–B3 — Tageslage-Lead (einen Block statt zwei)

**Aktuell:** `summary_html` (blauer `G_BOX_INFO_BG`-Kasten) + `day_comparison_html` (zweiter oranger Kasten) — zwei separate Blöcke.

**SOLL:** Ein einziger `<div>` mit `border-left:2px solid #c45a2a; padding-left:14px`:

```html
<div style="padding:18px 28px 16px;">
  <div style="border-left:2px solid #c45a2a; padding-left:14px;">
    <!-- Eyebrow TAGESLAGE -->
    <span mono 10px accent>TAGESLAGE</span>
    <!-- Summary-Satz -->
    <div 16px font-weight:500 color:#1d1c1a margin-top:6px>
      {compact_summary}
    </div>
    <!-- Vortag-Mono-Zeile (nur wenn day_comparison_line vorhanden) -->
    <div flex gap:8px margin-top:10px padding-top:10px border-top:1px solid #f0ece1>
      <span mono 9px muted uppercase>VS. GESTERN</span>
      <span color:{trend_color}>{trend_glyph}</span>
      <span 12.5px color:#3a3835>{day_comparison_line}</span>
    </div>
  </div>
</div>
```

**Trend-Glyph** aus `_day_comparison_line`:
- `summarize_day_comparison()` liefert einen fertigen Satz (z.B. "heute bessere Sicht als gestern")
- Glyph-Heuristik: Satz enthält "besser" → `▲` grün `#15803d`; "schlechter" → `▼` orange `#c2410c`; sonst → `▬` neutral `#6b6962`

**Sonderfälle:**
- `compact_summary` vorhanden, `day_comparison_line` leer → nur Lead ohne Vortag-Zeile
- `compact_summary` leer, `day_comparison_line` vorhanden → Lead zeigt nur Vortag-Zeile
- Beide leer → Block wird nicht gerendert (kein leerer Platzhalter)

Die bisherigen Variablen `summary_html` und `day_comparison_html` werden entfernt;
der neue `tageslage_html`-Block ersetzt beide in der `html`-String-Zusammensetzung.

## Expected Behavior

- **Input:** `render_html(..., compact_summary="Mäßiger Regen ab 11:00 ...", day_comparison=DayComparison(...))`
- **Output:** HTML-Email mit vollständigem Header, RiskDot-Spalte, einem Tageslage-Lead-Block
- **Side effects:** keine; reine Renderer-Änderung

## Acceptance Criteria

**AC-1:** Given eine Briefing-Email mit stage_name="Etappe 1: Calenzana → Carrozzu" und trip_name="GR20" / When die Email zugestellt wird / Then enthält der Header links den Strecken-Titel "Calenzana → Carrozzu" (22px) und rechts "GR20" — nicht umgekehrt.
- Test: Staging-Mail via IMAP empfangen; Header-HTML auf Titelposition prüfen.

**AC-2:** Given eine Briefing-Email mit sent_at gesetzt / When die Email zugestellt wird / Then zeigt die Datum-Zeile Wochentag + Datum + Uhrzeit (Format "Mi · 27.06.2026 · 06:01 MESZ").
- Test: Staging-Mail; Datum-Zeile gegen Regex `\w{2} · \d{2}\.\d{2}\.\d{4} · \d{2}:\d{2}` prüfen.

**AC-3:** Given eine Briefing-Email mit stage_total=12 / When die Email zugestellt wird / Then zeigt die rechte Header-Spalte "Etappe 1 / 12".
- Test: Staging-Mail; "Etappe 1 / 12" in Header-HTML.

**AC-4:** Given eine Stunden-Tabelle mit einer Zeile wo gust=35 km/h / When die Email zugestellt wird / Then hat diese Zeile ganz rechts einen orangen RiskDot (Farbe #c2410c).
- Test: Staging-Mail; letzte `<td>` jeder Zeile enthält `<span>` mit `background:#c2410c`.

**AC-5:** Given compact_summary und day_comparison_line beide vorhanden / When die Email zugestellt wird / Then gibt es genau einen Tageslage-Block mit border-left:#c45a2a, der Eyebrow "TAGESLAGE", den Summary-Satz und die Vortag-Mono-Zeile enthält — keinen zweiten farbigen Kasten.
- Test: Staging-Mail; nur ein Element mit `border-left:2px solid #c45a2a`; kein `background:#dde8f3` (alter blauer Box-Hintergrund).

**AC-6:** Given compact_summary leer, day_comparison_line vorhanden / When die Email zugestellt wird / Then zeigt der Tageslage-Block nur die Vortag-Zeile (kein leerer Summary-Satz).
- Test: Test-Trip ohne compact_summary; Mail empfangen; kein leeres `<div>` im Lead-Block.

## Known Limitations

- Trend-Glyph (▲/▼/▬) wird aus dem Freitext von `summarize_day_comparison()` heuristisch abgeleitet ("besser"/"schlechter"). Wenn der Satz andere Formulierungen enthält, erscheint `▬` neutral — korrekt für den ersten Schritt.
- `stage_total` fehlt in Preview-Endpunkten (Go-API `preview_service`) — dort bleibt "Etappe N" ohne `/total` bis ein Folge-Issue den Preview-Pfad nachzieht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Präsentations-Änderung im HTML-Renderer; keine Datenmodell-Änderung; neuer optionaler Parameter `stage_total` bricht keine bestehenden Aufrufe.

## Changelog

- 2026-06-26: Initial spec created
