---
issue: "#911"
workflow: fix-911-visual-table
status: draft
created: 2026-06-30
adr: docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx (maßgeblich)
---

# Spec: fix-911-visual-table — Desktop-Stundentabelle nach Design-Vorlage

## Kontext

Die Desktop-Stundentabelle der Briefing-Mail (`_render_html_table` in
`src/output/renderers/email/html.py`) entspricht NICHT der maßgeblichen
Design-Vorlage `docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx`
(`EmailDataTable` + `sevCellStyle`). Vier Defekte, alle aus #911-Ticket-Kommentar.

**Tests sind VISUELL** (Playwright, berechnete Stile echter Zellen bei Desktop-Breite
≥601px), KEINE String-Presence-Checks. Begründung: die vorherige Runde war grün mit
String-Tests, während alle vier Bugs live bestanden blieben.

## Architektur-Entscheidung (ADR)

keine — reiner Bugfix gegen die bestehende Design-Vorlage
(`docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx`),
keine neue Richtungsentscheidung.

## Acceptance Criteria

**AC-1 (Linienfarbe — visuell):** Given die Desktop-Stundentabelle bei Viewport-Breite ≥601px gerendert, When die berechnete `border-right-color` UND `border-bottom-color` JEDER Datenzelle (`td`) ausgelesen wird, Then ist sie für ALLE Zellen durchgängig `rgb(240, 236, 225)` (#f0ece1) — keine Zelle trägt das dunkle `rgb(156, 154, 144)` (#9c9a90) der globalen `<style>`-Regel.

**AC-2 (Risk-Hintergrund — visuell):** Given eine Datenzeile, deren Regen-Wert die Achtung-Schwelle überschreitet (precip > 1 mm → caution; precip > 4 → warn; precip > 8 → danger), When die berechnete `background-color` der Regen-Zelle ausgelesen wird, Then ist sie der getönte Wert der Stufe (`rgb(251, 238, 184)` #fbeeb8 caution / `rgb(250, 214, 184)` #fad6b8 warn / `rgb(246, 197, 191)` #f6c5bf danger) und NICHT transparent/weiß. Gleiches gilt analog für Wind (>20/>30/>40), Böen (>30/>45/>60), Rain% (>50/>70/>85), Thndr% (≥15→warn ab; ≥30 danger; >0 caution), Visib (<2/<1/<0.5). Der Zelltext bleibt dunkel-lesbar (kein heller Ampel-Text, kein Emoji).

**AC-3 (Monospace — visuell):** Given die Desktop-Stundentabelle gerendert, When die berechnete `font-family` einer Datenzelle (z. B. Temp) ausgelesen wird, Then enthält der Stack `JetBrains Mono` bzw. endet auf `monospace` — die Tabelle erbt NICHT den serifenlosen Body-Font (`Inter`). Zusätzliche Glyph-Breiten-Prüfung: ein `W` und ein `i` in einer Zelle haben (bei echtem Monospace) gleiche Breite.

**AC-4 (ACC-Pipeline — funktional):** Given ein Trip mit Folge-Etappen innerhalb des Vorhersage-Horizonts, When `_build_stage_trend` die Trend-Etappen baut, Then wird die Ensemble-Confidence für die Trend-Etappen berechnet (analog Hauptpfad `_enrich_ensemble_for_trip`), sodass `confidence_pct` je Etappe einen Wert (nicht None) trägt und die Ausblick-Tabelle einen ACC-Indikator auf der 4-Stufen-Skala (unkritisch/Achtung/Warnung/Gefahr) statt „–" zeigt.

## Technische Hinweise

- Design-Quelle: `EmailDataTable` (Z. 325), `sevCellStyle`/`RISK_CELL`/`sev*`-Schwellen (Z. 420–447) in der #911-Vorlage.
- AC-1: globale `td`-Border-Regel (#9c9a90) im `<style>`-Block greift auf Zellen ohne Inline-Border. Fix: alle `td`/`th` der Tabelle tragen Inline-Border `#f0ece1` (Outlook-fest) ODER die Tabelle bekommt eigene scoped Borders.
- AC-2: `sevCellStyle`-Logik (Schwellen + RISK_CELL-Tönung) auf die numerischen Datenzellen anwenden — unabhängig von Einfach/Roh-Modus, dunkler Text, kein Emoji/Ampel-Span.
- AC-3: `<table>`-Element bekommt `font-family:{FONT_DATA}` inline.
- AC-4: `_build_stage_trend` (Z. 996ff) nach `_fetch_weather` `self._enrich_ensemble_for_trip(trip, seg_weather)` aufrufen, dann `aggregate_stage`.
- LoC-Limit: Standard 250.

## Nebenbefund (separates Issue)
- Ausblick-/Thndr%-Spalte zeigt Werte > 100 % (190, 620, 1190 im IST-Screenshot) — physikalisch unmöglich. Datenpipeline-Bug, NICHT Teil dieses Workflows.
