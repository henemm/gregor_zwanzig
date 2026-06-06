---
entity_id: email_redesign_613
type: module
created: 2026-06-05
updated: 2026-06-05
status: draft
version: "1.0"
tags: [output, email, design-fidelity, issue-613]
---

# E-Mail-Briefing — Visuelles Redesign (Issue #613)

## Approval

- [ ] Approved

## Purpose

Das HTML-E-Mail-Briefing (Morgen/Abend) bekommt das Aussehen aus dem Claude-Design-Handoff „Gregor 20 — Mail Vorschau" (`EmailPreview`). Reines Anzeige-Redesign: drei neue Sektionen + Umstyling, alle Sektionen fest an mit Standardwerten. Konfigurierbarkeit (Schalter) ist NICHT Teil von #613 → #621/#619.

## Source

- **File:** `src/output/renderers/email/html.py` (HTML-Renderer, `render_html`)
- **File:** `src/output/renderers/email/plain.py` (Text-Parität)
- **File:** `src/output/renderers/email/helpers.py` (`pill_html` für Outlook-Chips, Aggregat-Helfer)
- **File:** `src/output/renderers/email/design_tokens.py` (Farb-/Font-Tokens)
- **Identifier:** `render_html()`, `render_plain()`
- **Schicht:** Python-Backend (kein Frontend, kein Go). Verifiziert: Renderer leben ausschließlich in `src/output/renderers/email/`.
- **Design-Soll:** `docs/design-requests/mail-vorschau-2026-06-05/screen-output-preview.jsx` → `EmailPreview` (Z.21)

## Estimated Scope

- **LoC:** ~200–250 (3 neue Sektionen + Umstyling + Plain-Text)
- **Files:** 3–4 (html.py, plain.py, helpers.py, ggf. design_tokens.py)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `render_html` | bestehende Pure-Func | wird umgebaut |
| `pill_html` (helpers) | bestehender Baustein | Quick-Take-Chips (Outlook-kompatibel) |
| `ForecastDataPoint`/`seg_tables` | Datenquelle | Tages-Summe-Aggregate, Quick-Take-Ableitung |

## Implementation Details

Neue/geänderte Sektionen im `render_html`-Body (Reihenfolge nach Entwurf):

1. **Etappen-Kennzahlen-Raster** — ersetzt die einzeilige `stats_line` durch ein `<table>`-Raster (Outlook-sicher, kein CSS-grid): Distanz · ↑Aufstieg · ↓Abstieg · Max Höhe · Segmente. Mono-Font, tabular-nums.
2. **Quick-Take-Chips** — unter dem Fließtext (`compact_summary`) eine Reihe farbiger Chips via `pill_html`, Tonalität warn/ok/info, abgeleitet aus den Segment-Reihen (z. B. „Regen ab HH:00", „Böen bis N km/h", „Kein Gewitter", „0°-Linie N m").
3. **Tageslicht-Leiste** — der bestehende Stirnlampen-Block (`_format_daylight_html`) bekommt zusätzlich eine **visuelle Leiste** (proportionaler Balken Tag/Nutzbar), per `<table>`/Inline-Width (Outlook-sicher).
4. **Tages-Summe** — neuer Block nach dem Ausblick: Raster mit den 4 Standard-Kennzahlen, aggregiert aus allen Segment-Stunden:
   - **Regen gesamt** = Σ `precip_1h_mm` (mm)
   - **Max Wind** = max `gust_kmh` (km/h)
   - **Min Sicht** = min `visibility_m` → km
   - **Gewitter** = max `thunder_level` als Stufe „kein/MED/HIGH" (Datenmodell hat KEINE Gewitter-%-Größe; `pop_pct` ist Regen-, nicht Gewitter-Wahrscheinlichkeit — daher Stufe statt %)
   - **Label-Hinweis:** „Max Wind" trägt den **Böen-Maximalwert** (`gust_kmh`); Label wird als „Max Böe" ausgegeben — fachlich präziser und kollisionsfrei mit `test_plain_text_respects_config` (das „Wind" bei deaktivierter Wind-Metrik verbietet). Bewusste, dokumentierte Abweichung vom JSX-Label „Max Wind".
5. **Umstyling** — weiße Karte auf Off-White, Inter Tight + JetBrains Mono, Eyebrow/Risk-Punkt-Sprache, dunkler Footer (bereits dunkel). Hoher Kontrast (WCAG-AA, CLAUDE.md-Leitprinzip).

**Erhalt-Garantien (Regression):**
- Segment-Kopf zeigt weiter den **km-Bereich** `km {start:.1f}–{end:.1f}` (html.py:318) — NICHT einzelne km.
- Alle bisherigen Sektionen bleiben erhalten (stability, summary, confidence, daylight, changes, segments, night, thunder, trend, highlights, footer).
- Mobile-Pfad (`mobile-compact` / `EmailHourList`-Äquivalent) bleibt funktionsfähig.

## Expected Behavior

- **Input:** unveränderte `render_html(...)`-Signatur (Daten aus dem Formatter).
- **Output:** HTML-String mit neuem Layout + den 3 neuen Sektionen; Plain-Text-String mit Tages-Summe-Parität.
- **Side effects:** keine; reine Darstellung, kein Schema-Eingriff, kein neues Wetter-Feld.

## Acceptance Criteria

- **AC-1:** Given ein Briefing mit Etappen-Stats / When die HTML-Mail gerendert wird / Then erscheinen Distanz, Aufstieg, Abstieg, Max-Höhe und Segment-Anzahl als visuelles Kennzahlen-Raster (nicht als eine durch „|" getrennte Textzeile).
  - Test: `render_html()` mit echten Segmentdaten aufrufen, im Ergebnis die fünf Kennzahl-Werte als getrennte Rasterzellen nachweisen.

- **AC-2:** Given eine Quick-Take-Zusammenfassung / When die HTML-Mail gerendert wird / Then erscheinen unter dem Fließtext farbige Schlagwort-Chips (warn/ok/info-Tonalität) mit aus den Wetterdaten abgeleiteten Aussagen.
  - Test: `render_html()` mit Regen/Böen/Gewitter-Daten aufrufen; nachweisen, dass passende Chips mit korrekter Tonalität (Farbe) ausgegeben werden.

- **AC-3:** Given ein gültiges Tageslicht-Fenster / When die HTML-Mail gerendert wird / Then erscheint neben Start/Ende-Zeiten eine proportionale visuelle Leiste, deren nutzbarer Anteil zur Tageslänge passt.
  - Test: `render_html()` mit zwei verschieden langen Tageslicht-Fenstern aufrufen; nachweisen, dass die Balken-Breite des nutzbaren Abschnitts unterschiedlich ausfällt.

- **AC-4:** Given Segment-Stundenreihen / When die HTML-Mail gerendert wird / Then erscheint ein Tages-Summe-Block mit Regen-Summe (Σ mm), Max Böe (max Böe km/h), Min Sicht (min km) und Gewitter (max. Stufe kein/MED/HIGH), korrekt aus den Stundenwerten berechnet.
  - Test: `render_html()` mit bekannten Stundenwerten aufrufen; die vier Aggregate gegen von Hand berechnete Sollwerte prüfen.

- **AC-5:** Given ein Segment mit Start- und End-Kilometer / When die HTML- und Plain-Mail gerendert werden / Then zeigt der Segment-Kopf weiterhin den Kilometer-Bereich „km X,X–Y,Y" (Regressionsschutz, nicht eine einzelne Kilometerzahl).
  - Test: `render_html()`/`render_plain()` mit Segment km 1,9–4,2 aufrufen; „km 1,9–4,2" im Kopf nachweisen.

- **AC-6:** Given eine vollständige Briefing-Mail / When sie gerendert wird / Then bleiben alle bisherigen Sektionen erhalten (Großwetterlage, Zusammenfassung, Unsicherheits-Hinweis, Tageslicht, Wetteränderungen, Segmente, Nacht, Gewitter-Vorschau, Ausblick, Highlights, Footer) — keine geht durch das Redesign verloren.
  - Test: `render_html()` mit vollständigem Datensatz (alle optionalen Blöcke aktiv) aufrufen; jede Sektion im Ergebnis nachweisen.

- **AC-7:** Given der neue Tages-Summe-Block / When die Plain-Text-Variante gerendert wird / Then enthält sie dieselben vier Kennzahlen wie die HTML-Variante (Text-Parität).
  - Test: `render_plain()` aufrufen; die vier Tages-Summe-Werte im Text-Output nachweisen.

- **AC-8:** Given das fertige Redesign auf Staging / When eine echte Test-Mail an `gregor-test@henemm.com` gesendet und per IMAP geprüft wird / Then meldet `email_spec_validator.py` Exit 0 (Struktur, Location-Anzahl, Plausibilität, Vollständigkeit ok).
  - Test: Test-Trip auf Staging triggern, IMAP-Abruf, `email_spec_validator.py` Exit 0.

## Known Limitations

- Konfigurierbarkeit der Sektionen ist NICHT Teil von #613 — alle Sektionen sind fest an (Tages-Summe-Default: Regen/Wind/Sicht/Gewitter). Schalter → #621, UI → #619.
- Mail-Client-Rendering variiert; Layout muss Outlook-tauglich bleiben (Tabellen/Inline-Styles statt flex/grid).

## Changelog

- 2026-06-05: Initial spec created (Issue #613, abgespalten von Konfigurierbarkeit #621/#619)
- 2026-06-06: Adversary-Fix-Loop — Gewitter-Aggregat als Stufe statt %-Wert (Datenmodell-Grenze, F002); „Max Böe"-Label als dokumentierte Abweichung von JSX „Max Wind" (F003); Chip-Tonalität „ok"→grün + HTML-Escape in pill_html (F001/F004)
