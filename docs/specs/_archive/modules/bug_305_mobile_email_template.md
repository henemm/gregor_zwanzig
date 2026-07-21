---
entity_id: bug_305_mobile_email_template
type: bugfix
created: 2026-05-21
updated: 2026-05-21
status: implemented
version: "1.0"
tags: [bugfix, email, mobile, html-table, responsive, ios-mail, issue-305]
---

<!-- Issue #305 — HTML-E-Mail-Template auf mobilen Geräten (iOS Mail) nicht nutzbar: 15 Spalten laufen über den Bildschirmrand -->

# Issue #305 — Bug-Fix: HTML-E-Mail auf iOS Mail responsive machen

## Approval

- [x] Approved

## Zweck

Das HTML-E-Mail-Template rendert auf mobilen Geräten (iOS Mail, ~375px Viewport) alle 15 Tabellenspalten horizontal nebeneinander, wobei rechte Spalten über den Bildschirmrand laufen und nicht lesbar sind. Der Bug hat zwei nachgewiesene Root-Causes in `src/output/renderers/email/html.py`: die fehlende `<thead>`/`<tbody>`-Struktur verhindert, dass der vorhandene @media-CSS-Header-Hide greift, und der @media-Breakpoint von 480px feuert im iOS-Mail-Client nie, weil dieser intern mit ~600px virtueller Breite rendert. Beide Root-Causes werden chirurgisch in einer einzigen Datei gefixt — ohne strukturelle Umbauten an der restlichen Rendering-Pipeline.

## Quelle / Source

**Geänderte Datei:**
- `src/output/renderers/email/html.py` — einzige Datei, die geändert wird

**Betroffene Funktionen:**
- `_render_html_table()` (Zeile 87–104) — erzeugt `<table>`-HTML ohne `<thead>`/`<tbody>`
- `render_html()` CSS-Block (Zeile 293) — enthält `@media (max-width:480px)`

**Bestehende Test-Datei (TDD-RED, bereits vorhanden):**
- `tests/tdd/test_bug305_mobile_email.py`

> **Schicht-Hinweis:** Beide Änderungen liegen ausschliesslich im Python-Backend-Layer (`src/output/renderers/email/`). Keine Frontend-Komponenten, kein Go-API-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/html.py` | Python-Modul | Enthält `_render_html_table()` und `render_html()` — beide Änderungen landen hier |
| `tests/tdd/test_bug305_mobile_email.py` | Test-Datei | 5 TDD-RED-Tests, die nach dem Fix grün werden müssen |

## Implementation Details

### RC-1 Fix: `_render_html_table()` — `<thead>`/`<tbody>` ergänzen

**Problem:** Die Funktion gibt aktuell `<table class="resp"><tr><th>...</th></tr>...</table>` zurück. Die CSS-Regel `table.resp thead { display:none }` im @media-Block kann nicht greifen, weil kein `<thead>`-Element existiert.

**Lösung:** Den Header-`<tr>` in `<thead>...</thead>` einwickeln, alle Daten-`<tr>` in `<tbody>...</tbody>`.

Vorher (schematisch):
```html
<table class="resp">
  <tr><th>Time</th><th>Temp</th>...</tr>
  <tr><td>...</td>...</tr>
  ...
</table>
```

Nachher:
```html
<table class="resp">
  <thead><tr><th>Time</th><th>Temp</th>...</tr></thead>
  <tbody>
    <tr><td>...</td>...</tr>
    ...
  </tbody>
</table>
```

Konkrete Code-Änderung in `_render_html_table()`:
- Die Zeile, die den Header-`<tr>` aufbaut, mit `<thead>` und `</thead>` umschliessen
- Den Start der Datenzeilen-Schleife mit `<tbody>` einleiten
- Am Ende der Datenzeilen-Schleife `</tbody>` schliessen (vor `</table>`)

### RC-2 Fix: `@media (max-width:480px)` → `@media (max-width:600px)`

**Problem:** iOS Mail rendert E-Mails intern mit ~600px virtueller Breite. Ein Breakpoint von 480px feuert daher nie im nativen iOS-Mail-Client.

**Lösung:** Einen einzigen String in `render_html()` ändern:

Vorher:
```css
@media (max-width:480px) {
```

Nachher:
```css
@media (max-width:600px) {
```

Dies ist eine einzelne String-Ersetzung in `html.py`. Alle CSS-Regeln innerhalb des @media-Blocks bleiben unverändert.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/output/renderers/email/html.py` | +4 / -2 (thead/tbody-Tags + Breakpoint) | ja |
| **Gesamt (zählend)** | **~6** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Keine Laufzeit-Eingabe — `_render_html_table()` erhält dieselben Daten wie bisher; `render_html()` funktioniert unverändert über dieselbe Aufruf-Schnittstelle
- **Output:** `_render_html_table()` gibt HTML mit `<thead>...</thead><tbody>...</tbody>` zurück; `render_html()` gibt HTML mit `@media (max-width:600px)` im `<style>`-Block zurück
- **Side effects:** Bei 375px Viewport (Playwright-Messung) ist `table.scrollWidth <= table.clientWidth` (kein interner Overflow), alle `<th>`-Elemente haben `offsetHeight == 0` (Header versteckt durch `table.resp thead { display:none }`)

## Acceptance Criteria

- **AC-1:** Given `_render_html_table()` mit Datenzeilen / When das HTML auf Tabellenstruktur geprüft wird / Then enthält es `<thead><tr><th>...</th></tr></thead>` als erste Sektion innerhalb des `<table>`-Elements
  - Test: `TestTableStructure::test_table_has_thead`

- **AC-2:** Given `_render_html_table()` mit Datenzeilen / When das HTML auf Tabellenstruktur geprüft wird / Then enthält es `<tbody>...</tbody>` mit allen Datenzeilen als zweite Sektion innerhalb des `<table>`-Elements
  - Test: `TestTableStructure::test_table_has_tbody`

- **AC-3:** Given `render_html()` mit 15-Spalten-Tabelle / When der CSS-`<style>`-Block auf `@media` geprüft wird / Then ist der `max-width`-Breakpoint >= 600px und nicht mehr 480px
  - Test: `TestTableStructure::test_th_elements_are_inside_thead` (prüft strukturell; Breakpoint-Test ist implizit via Playwright-AC-4)

- **AC-4:** Given das gerenderte HTML bei 375px Viewport in Playwright / When `table.scrollWidth` und `table.clientWidth` gemessen werden / Then ist `scrollWidth <= clientWidth` (kein interner horizontaler Overflow)
  - Test: `TestMobileLayoutPlaywright::test_table_has_no_internal_overflow_at_375px`

- **AC-5:** Given das gerenderte HTML bei 375px Viewport in Playwright / When die Sichtbarkeit aller `<th>`-Elemente geprüft wird / Then hat kein `<th>`-Element `offsetHeight > 0` (Header-Zeile vollständig versteckt)
  - Test: `TestMobileLayoutPlaywright::test_header_row_hidden_at_375px`

## Known Limitations

- **Kein Inline-Style-Fallback für ältere E-Mail-Clients:** Der Fix nutzt `@media`-CSS, das in sehr alten E-Mail-Clients (Outlook 2007–2013) ignoriert wird. Diese Clients sind nicht im Support-Scope des Projekts.
- **iOS Mail Breakpoint empirisch:** 600px ist die etablierte Praxis-Grenze für iOS Mail; offizielle Apple-Dokumentation fehlt. Der Playwright-Test bei 375px ist der verbindliche Nachweis.

## Out of Scope

- Änderungen an anderen E-Mail-Templates oder Renderern
- Visuelle Umgestaltung der mobilen Tabellenansicht (z.B. Card-Layout statt Tabelle)
- Änderungen am Go-API-Layer oder Frontend-Code

## Changelog

- 2026-05-21: Initial spec erstellt. Zwei chirurgische Fixes in `html.py`: `<thead>`/`<tbody>`-Struktur in `_render_html_table()` + @media-Breakpoint von 480px auf 600px angehoben. Behebt horizontalen Overflow (339px) auf iOS Mail bei 375px Viewport.
