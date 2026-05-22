---
entity_id: bug_305_mobile_email_v2
type: bugfix
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [bugfix, email, mobile, dual-mode, responsive, ios-mail, issue-305]
---

<!-- Issue #305 — HTML-E-Mail-Template auf mobilen Geräten (iOS Mail) nicht nutzbar: Mobile zeigt 15+ gestapelte Label-Zeilen pro Stunden-Slot statt kompakter Ansicht -->

# Issue #305 — Echter Fix: HTML-E-Mail Mobile-Kompakt-Layout (v2)

## Approval

- [ ] Approved

## Zweck

Der erste Fix-Versuch (Commit `e3978df`) hat `<thead>`/`<tbody>` und den @media-Breakpoint korrigiert, aber das grundlegende Layout-Problem nicht behoben: das CSS `display:block` auf `table.resp td` wandelt jede Tabellenzelle in eine eigene gelabelte Zeile um — bei 15 Metriken × 6 Stunden-Slots entstehen 90+ gestapelte Label-Wert-Paare pro Segment. Das ist nicht die gewünschte Mobile-Ansicht.

**Echter Root Cause:** Kein separater Mobile-Inhalt. Desktop-Tabelle wird via CSS in ein Card-per-Row-Layout umgewandelt — das Layout-Konzept ist für multi-column Wetter-Tabellen grundsätzlich falsch.

**Lösung:** Dual-Mode-Rendering analog zu `compare_html.py`: Desktop-Tabellen und Mobile-Kompakt-Ansicht beide im HTML, CSS `@media (max-width:600px)` schaltet zwischen beiden um.

## Quelle / Source

**Geänderte Datei:**
- `src/output/renderers/email/html.py` — einzige Datei, die geändert wird

**Betroffene Funktionen:**
- `render_html()` — Wrapper-Divs + neue Compact-Funktion aufrufen
- CSS-Block in `render_html()` — neues Dual-Mode-Switching
- Neue private Funktion `_render_mobile_compact_rows()` — compact Zeilen generieren

**Bestehende Test-Datei:**
- `tests/tdd/test_bug305_mobile_email.py` — neue Testklasse `TestMobileCompactLayout` ergänzen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/html.py` | Python-Modul | Gesamte Änderung liegt hier |
| `src/output/renderers/email/helpers.py` | Python-Modul | `visible_cols()` + `fmt_val()` unverändert wiederverwendet |
| `src/output/renderers/email/design_tokens.py` | Python-Modul | Farb-/Font-Tokens für Compact-Rows |
| `tests/tdd/test_bug305_mobile_email.py` | Test-Datei | Neue Testklasse ergänzen (AC-7..AC-13) |

## Implementation Details

### 1. Neue private Funktion `_render_mobile_compact_rows()`

```python
def _render_mobile_compact_rows(rows: list[dict], *, friendly_keys: set[str]) -> str:
    """Compact single-line-per-hour rows for mobile email."""
    cols = visible_cols(rows) if rows else []
    html_parts = []
    for r in rows:
        time_str = r.get("time", "")
        parts = []
        for key, _ in cols:
            try:
                cell = fmt_val(key, r.get(key), friendly_keys=friendly_keys, html=True, row=r)
            except (TypeError, ValueError):
                cell = str(r.get(key)) if r.get(key) is not None else ""
            if cell and cell != "–":
                parts.append(cell)
        if not parts:
            continue
        html_parts.append(
            f'<div style="display:flex;gap:8px;padding:5px 0;'
            f'border-bottom:1px solid {G_INK_FAINT};font-size:12px;">'
            f'<span style="font-family:{FONT_DATA};color:{G_INK_MUTED};'
            f'min-width:34px;flex-shrink:0">{time_str}</span>'
            f'<span style="color:{G_INK};line-height:1.5">{" · ".join(parts)}</span>'
            f'</div>'
        )
    return "".join(html_parts)
```

### 2. Dual-Mode-Wrapper in `render_html()` — Segment-Schleife

Statt:
```python
seg_html_parts.append(f"""
    <div class="section">
        <h3>Segment {seg.segment_id}: ...</h3>
        {_render_html_table(rows, ...)}
    </div>""")
```

Neu:
```python
seg_header = f"Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | ..."

# Desktop (unverändert, nur Wrapper-Div-Klasse ergänzt)
desktop_html = f"""
    <div class="section desktop-only">
        <h3>{seg_header}</h3>
        {_render_html_table(rows, friendly_keys=friendly_keys)}
    </div>"""

# Mobile compact
compact_rows = _render_mobile_compact_rows(rows, friendly_keys=friendly_keys)
mobile_html = f"""
    <div class="mobile-compact" style="display:none;padding:0 16px">
        <div style="font-size:12px;font-weight:600;color:{G_INK};
             border-bottom:2px solid {G_ACCENT};padding:10px 0 6px 0;margin-top:12px">
             {seg_header}
        </div>
        {compact_rows}
    </div>"""

seg_html_parts.append(desktop_html + mobile_html)
```

Gleiches Muster für `night_html`.

### 3. CSS-Änderungen im `<style>`-Block

Ergänzen (nach den bestehenden Regeln):
```css
.desktop-only { display: block; }
.mobile-compact { display: none; }
```

Im `@media (max-width:600px)`-Block ergänzen:
```css
.desktop-only { display: none !important; }
.mobile-compact { display: block !important; }
```

Die bestehenden `table.resp`-Mobile-CSS-Regeln (Card-per-Row) werden entfernt, da sie durch das neue Dual-Mode-Layout ersetzt werden und nicht mehr benötigt werden.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/output/renderers/email/html.py` | ~+35 / -8 (neue Funktion + Wrapper-Divs + CSS) | ja |
| `tests/tdd/test_bug305_mobile_email.py` | ~+60 (neue Testklasse) | nein (Tests) |
| **Gesamt (zählend)** | **~+27** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Desktop (>600px):** Identisch zu heute — `div.desktop-only` sichtbar, `div.mobile-compact` verborgen
- **Mobile (≤600px):** `div.desktop-only` ausgeblendet, `div.mobile-compact` sichtbar
- **Compact-Rows:** Pro Stunden-Slot eine Zeile: `08:00  15.0 · 12 SW · 0.2 · ⚡ mögl.`
- **Konfigurierbarkeit:** Beide Ansichten zeigen dieselben aktivierten Metriken (via `visible_cols()`)

## Acceptance Criteria

- **AC-7:** Given `render_html()` mit einem Segment / When das HTML auf Wrapper-Klassen geprüft wird / Then enthält es mindestens einen `class="desktop-only"`-Wrapper der eine `table.resp` enthält
  - Test: `TestMobileCompactLayout::test_desktop_only_wrapper_exists`

- **AC-8:** Given `render_html()` mit einem Segment / When das HTML auf Mobile-Wrapper geprüft wird / Then enthält es mindestens einen `class="mobile-compact"`-Wrapper
  - Test: `TestMobileCompactLayout::test_mobile_compact_wrapper_exists`

- **AC-9:** Given `render_html()` / When der CSS-Block auf Dual-Mode-Switch geprüft wird / Then enthält der `@media (max-width:600px)`-Block `.desktop-only { display: none !important; }`
  - Test: `TestMobileCompactLayout::test_css_hides_desktop_on_mobile`

- **AC-10:** Given `render_html()` / When der CSS-Block auf Dual-Mode-Switch geprüft wird / Then enthält der `@media (max-width:600px)`-Block `.mobile-compact { display: block !important; }`
  - Test: `TestMobileCompactLayout::test_css_shows_compact_on_mobile`

- **AC-11:** Given das gerenderte HTML bei 375px Viewport in Playwright / When die Sichtbarkeit von `.desktop-only` geprüft wird / Then hat kein `.desktop-only`-Element eine sichtbare Höhe > 0
  - Test: `TestMobileCompactLayoutPlaywright::test_desktop_only_hidden_at_375px`

- **AC-12:** Given das gerenderte HTML bei 375px Viewport in Playwright / When die Sichtbarkeit von `.mobile-compact` geprüft wird / Then hat mindestens ein `.mobile-compact`-Element eine Höhe > 0
  - Test: `TestMobileCompactLayoutPlaywright::test_mobile_compact_visible_at_375px`

- **AC-13:** Given das gerenderte HTML bei 375px Viewport in Playwright / When kein interner horizontaler Overflow geprüft wird / Then ist für alle `.mobile-compact`-Elemente `scrollWidth <= clientWidth`
  - Test: `TestMobileCompactLayoutPlaywright::test_mobile_compact_no_overflow_at_375px`

## Known Limitations

- Keine Elevation-Sparkline in der Mobile-Ansicht (SVG wäre separates Feature)
- Kein Freitext-Zusammenfassung pro Segment in der Mobile-Ansicht (`compact_summary` erscheint aber weiterhin im Header-Bereich)
- Night-Rows: gleiches Dual-Mode-Muster, aber Nacht-Abschnitt hat anderen Titel

## Out of Scope

- Änderungen an anderen Sektionen (summary, changes, highlights, trend) — bleiben unverändert
- Elevation-Sparkline (SVG) in der Mobile-Ansicht
- Änderungen an Desktop-Darstellung
- Andere Renderer oder Templates

## Changelog

- 2026-05-21: Spec erstellt. Echter Fix nach erstem fehlgeschlagenem Versuch. Dual-Mode-Rendering: `div.desktop-only` / `div.mobile-compact` mit CSS-Switch bei 600px.
