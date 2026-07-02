---
entity_id: issue_956_email_format
type: bugfix
created: 2026-07-01
updated: 2026-07-01
status: draft
version: "1.0"
tags: [email, renderer, html, trip-briefing, visual-tdd]
workflow: fix-956-email-format
---

<!-- Issue #956 — E-Mail Format-Korrekturen Trip-Briefing (HTML-Renderer) -->

# Issue 956 — E-Mail-Format-Korrekturen Trip-Briefing

## Approval

- [ ] Approved

## Purpose

Die Trip-Briefing-HTML-Mail (`render_html()`) weicht in fünf Teilpunkten von der
freigegebenen Claude-Design-Vorlage ("Gregor 20 - Mail Vorschau", Projekt
`019dfcf4-1e69-73f2-b094-c19e157014a2`) ab: überflüssige Trennlinien und redundanter
Etappen-Text im Header, ein veralteter Segment-Header-Text statt Kilometer-/Höhen-Spanne,
ein Datumslogik-Bug in der Nacht-Tabelle, ein Spacing-Fehler bei getönten Tabellenzellen
und eine noch unbestätigte Font-Abweichung. Diese Spec bringt den Renderer 1:1 auf die
Vorlage und beseitigt den Datumsfehler.

## Source

- **File:** `src/output/renderers/email/html.py` — `render_html()`, `_render_email_stat()`,
  `_render_html_table()` (Python-Backend, `src/output/renderers/email/`)
- **File:** `src/formatters/trip_report.py` — `_extract_night_rows()`,
  `_aggregate_night_block()` (Python-Backend, `src/formatters/`)
- **File:** `src/output/renderers/email/design_tokens.py` — `FONT_UI`, `FONT_DATA`,
  `WEB_FONT_LINK` (Diagnose-Referenz für Teil C)
- **Identifier:** `def render_html`, `def _render_email_stat`, `def _render_html_table`,
  `def _extract_night_rows`, `def _aggregate_night_block`

> Schicht-Hinweis: Alle betroffenen Symbole liegen im Python-Backend
> (`src/output/renderers/`, `src/formatters/`), nicht im Frontend/SvelteKit und nicht in der
> Go-API. Kein UI-Code betroffen — Gregor Zwanzig sendet die HTML-Mail serverseitig gerendert.

## Estimated Scope

- **LoC:** +50/-15 (grobe Schätzung aus Analyse: D 1 Zeile, A ~15-25, B ~20-30, E ~2-5, C 0-5 je nach Diagnose-Ausgang)
- **Files:** 2 Code-Dateien (MODIFY) + 2 neue Testdateien (CREATE)
- **Effort:** medium (fünf unabhängige Teilfixe, plus Neuentwicklung einer visuellen Pixel-Diff-Testinfrastruktur als Voraussetzung)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/design-requests/issue-956-mail-vorschau/screenshots/*.png` | Referenz-Artefakte | SOLL-Zustand für Header (A), Segment-Header (B), Cell-Tint (E), Night-Rows-Bug (D) — Basis für Pixel-Diff |
| `docs/design-requests/issue-956-mail-vorschau/screen-output-preview.jsx` | Design-Vorlage | Funktion `EmailSegmentBlock` — 1:1-Vorbild für Teil B (Segment-Header-Format) |
| `.claude/hooks/design_fidelity_diff.py` | Referenz-Tool (read-only) | Pixel-Diff-Muster (Playwright-Screenshot + Bild-Diff), Vorbild für das neu zu bauende Mail-HTML-Diff-Tool |
| `tests/tdd/test_issue_811_mode_matrix.py` | Renderer-Commit-Gate | Modus-Matrix-Vertragstest, MUSS nach jeder Änderung an `html.py` grün laufen (`renderer_mail_gate.py`) |
| `.claude/hooks/briefing_mail_validator.py` | Renderer-Commit-Gate | Validator für den `trip-briefing`-Mail-Pfad, MUSS frisch gegen echte Staging-Mail laufen |
| `NormalizedTimeseries` (`night_weather`) | Datenmodell | Upstream-Zeitreihe für Teil D (Nacht-Zeilen-Aggregation) |
| `seg.distance_km` (Segment-Attribut) | Datenmodell | Basis für die kumulierte km-Laufsumme in Teil B (muss im Renderer aufsummiert werden) |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/email/html.py` | MODIFY | Zeile 778 (`stats_grid_html` `border-top:1px solid #e6e1d3`) entfernen; Zeile 840 (Header-Div `border-bottom:1px solid #e6e1d3`) entfernen; vertikale Stat-Trenner (`_render_email_stat`, Zeile 150 `border-right:1px solid #e6e1d3`) in den Body-Bereich verlängern statt am Header-Rand zu enden; senkrechte Spalten-Trennlinie zwischen `left_col`/`right_col` (Zeile 808–838, `<table>`-Aufbau) lokalisieren und entfernen; `_eyebrow(f"{_rt_upper}-BRIEFING · {_stage_label}")` Zeile 810 auf `_eyebrow(f"{_rt_upper}-BRIEFING")` kürzen; Segment-Header Zeile 930–946 umbauen: `sub_header or seg_header_text(seg)`-Titel-Text (Zeile 940–941) entfernen, `km_str`/`elev_arrow`-Format (Zeile 931–932, 944) durch kumulierte `fromKm - toKm km · fromElev - toElev m`-Darstellung ersetzen (neue Hilfsberechnung: laufende Summe über `seg.distance_km` aller vorherigen Segmente der Etappe); Cell-Tint negative-margin (Zeile 553–556, aktuell `margin:-6px -4px;padding:6px 4px;`) auf die tatsächliche `<td>`-Padding-Regel (Zeile 562: `padding:8px 4px` bei der Risk-Dot-Spalte — als Referenzwert für die Datenzellen-Padding-Regel im CSS-Block zu verifizieren) anpassen |
| `src/formatters/trip_report.py` | MODIFY | Zeile 298: `is_next_day = local_dt.date() > first_date` → `is_next_day = local_dt.date() == first_date + timedelta(days=1)` (setzt `datetime.timedelta`-Import voraus, falls noch nicht vorhanden) |
| `tests/tdd/test_issue_956_night_rows_date_bug.py` | CREATE | Klassischer pytest-Test für Teil D (Datumslogik, kein visuelles Element) |
| `tests/visual/test_issue_956_email_pixel_diff.py` (oder `.claude/hooks/`-Pendant, Pfad in TDD-RED-Phase final) | CREATE | Playwright-basiertes Pixel-Diff-Tool + Test für Teile A, B, E gegen die Referenz-PNGs unter `docs/design-requests/issue-956-mail-vorschau/screenshots/` |
| `src/output/renderers/email/compact.py` | KEINE ÄNDERUNG | Bestätigt (Analyse-Phase): kein SEG-Header-, Font- oder Cell-Tint-Codepfad betroffen. Teil D (Nacht-Zeit-Bug) wirkt gemeinsam, weil `compact.py` dieselbe `trip_report.py::_extract_night_rows()`-Datenquelle nutzt — mit dem Fix in `trip_report.py` ist auch der `compact`-Pfad automatisch korrigiert, ohne dass `compact.py` selbst geändert werden muss |

### Estimated Changes
- Files: 2 Code-Dateien (MODIFY) + 2 neue Testdateien (CREATE)
- LoC: +50/-15 (grobe Schätzung aus Analyse: D 1 Zeile, A ~15-25, B ~20-30, E ~2-5, C 0-5 je nach Diagnose-Ausgang)

## Implementation Details

**Reihenfolge (aus Analyse-Phase-Bewertung):**

1. **Teil D zuerst** (`trip_report.py` Zeile 298) — isolierter Ein-Zeilen-Fix, reine
   Datumslogik ohne visuelles Element. Root Cause: `is_next_day` matched aktuell JEDES
   spätere Datum (`>`), nicht nur exakt den Folgetag. Liefert `night_weather` mehr als
   einen Tag Stundendaten, rutschen Übermorgen-Datenpunkte mit Stunde ≤ 6 fälschlich als
   zusätzliche "00"-Zeile in die Nacht-Tabelle (siehe `_aggregate_night_block()` Zeile
   323–332, die Blöcke nur nach `hour - hour % interval` ohne Datum im finalen `time`-String
   labelt).

2. **Pixel-Diff-Infrastruktur bauen** — Voraussetzung für die visuellen TDD-RED-Tests von
   A/B/E. Analog zu `.claude/hooks/design_fidelity_diff.py` (Issue #603), aber neuer
   Screen-Typ "E-Mail-HTML" statt Frontend-Route: `render_html()` mit Testdaten aufrufen →
   resultierendes HTML per Playwright `page.set_content()` laden → Screenshot → Bild-Diff
   gegen die passende Referenz-PNG unter
   `docs/design-requests/issue-956-mail-vorschau/screenshots/` mit demselben
   Schwellwert-Mechanismus wie das bestehende Tool. **Wichtig:** Test-Schwellen dürfen bei
   Diff-Fehlschlägen NIEMALS angehoben werden — bei Überschreitung erst das Diff-Bild
   ansehen.

3. **Teil E vor A/B** (`html.py` Zeile 553–556 vs. Zeile 562) — Cell-Tint-Fix und
   Header-Trennlinien-Fix betreffen denselben CSS-Bereich; die reale `<td>`-Padding-Regel
   muss zuerst verifiziert werden (Referenzwert `8px 4px`, siehe Risk-Dot-Spalte Zeile 562,
   vs. aktuell hart codiertes `-6px -4px`/`6px 4px` bei Zeile 555–556).

4. **Teil B vor A** — Teil B führt eine neue Datenberechnung ein (kumulierte km-Laufsumme
   über `seg.distance_km` aller vorangegangenen Segmente derselben Etappe), Teil A ist
   reines CSS/String-Handling.

5. **Teil C zuletzt** — reiner Diagnose-Task: echte Staging-Mail (Marker-Header
   `X-GZ-Mail-Type: trip-briefing`) rendern lassen, Screenshot in einem Mail-Client mit
   Web-Font-Unterstützung ziehen und mit der Vorlage abgleichen. Nur falls dabei ein
   fehlendes `font-family:{FONT_UI}` auf einzelnen Elementen (nicht auf `body`) gefunden
   wird, ist ein Code-Fix nötig — sonst bleibt es bei der Diagnose-Dokumentation in dieser
   Spec (kein Blind-Fix).

**Segment-Header-Zielformat (Teil B, aus `EmailSegmentBlock`-Vorlage 1:1 übersetzt):**
`SEG {N}` (bleibt) gefolgt von `{seg_time} · {fromKm:.1f} km - {toKm:.1f} km ·
{fromElev} - {toElev} m` — der bisherige Titel-Text (`sub_header or
seg_header_text(seg)`) entfällt vollständig.

## Test Plan

### Sonderfall TDD-RED: Visuell statt Code-basiert (PO-Vorgabe, Issue-Text)

Die PO-Vorgabe "Du musst die TDD RED Tests visuell erstellen. Code-Tests sind hier nicht
erlaubt." gilt für die **sichtbaren Layout-Bugs A, B, E** (und die Diagnose-Prüfung C) —
für diese ist ein `assert 'x' in html`-Test verboten, weil er das tatsächliche visuelle
Ergebnis nicht beweist. Stattdessen: Pixel-Diff via Playwright-Screenshot gegen die
Referenz-PNGs unter `docs/design-requests/issue-956-mail-vorschau/screenshots/`.

**Teil D (Nacht-Zeit-Bug) ist die begründete Ausnahme:** Der Bug ist reine
Datumslogik in `_extract_night_rows()` ohne jedes visuelle Element — er lässt sich
vollständig und eindeutig über Eingabe-/Ausgabedaten (welche Zeilen landen im
Rückgabewert) beweisen, ohne dass ein Rendering involviert ist. Ein klassischer
pytest-Test ist hier angemessen, ausreichend und deckt den PO-Wunsch nach einem
belastbaren RED→GREEN-Nachweis besser ab als ein erzwungener Screenshot-Umweg über ein
Datum, das im Rendering gar nicht sichtbar unterscheidbar ist.

### Automated Tests (TDD RED)

- [ ] Test 1 (visuell, Teil A): GIVEN eine gerenderte Trip-Briefing-Mail mit
      Stage-Stats und Header WHEN sie via Playwright gescreenshottet und gegen
      `referenz-header-morgenbriefing.png` verglichen wird THEN zeigt der Diff KEINE
      horizontale Linie zwischen Datumszeile und Stats-Grid, KEINE horizontale Linie
      unter dem Stats-Grid, KEINE senkrechte Trennlinie zwischen linker und rechter
      Header-Spalte, und KEINEN "· Etappe N"-Text in der Eyebrow-Zeile (Diff unter
      Schwellwert)

- [ ] Test 2 (visuell, Teil B): GIVEN ein gerendertes Segment mit `distance_km`-Werten
      über mehrere Segmente einer Etappe WHEN der Segment-Header gescreenshottet und
      gegen `soll-segment-header.png` verglichen wird THEN zeigt der Header "SEG N" plus
      kumulierte Kilometer-Spanne ("X.X km - Y.Y km") und Höhen-Spanne ("A - B m") OHNE
      den alten Etappen-Titel-Text

- [ ] Test 3 (visuell, Teil E): GIVEN eine Tabellenzelle mit farbigem Tint-Hintergrund
      (z.B. `precip`-Wert über Schwellwert) WHEN sie gescreenshottet und gegen
      `soll-cell-tint-spacing.png` verglichen wird THEN füllt der getönte Hintergrund die
      Zelle randlos bis an die Gitterlinien (kein sichtbarer weißer Rand wie in
      `ist-cell-tint-spacing.png`)

- [ ] Test 4 (klassisch, Teil D): GIVEN eine `NormalizedTimeseries` mit Stundendaten für
      Ankunftstag, direkten Folgetag UND einen weiteren Tag danach (Übermorgen) mit
      Stunden ≤ 6 WHEN `_extract_night_rows()` aufgerufen wird THEN enthält das
      Rückgabe-Array KEINE Zeile, deren Datenpunkte vom Übermorgen-Datum stammen — nur
      Ankunftstag (ab `arrival_hour`) und direkter Folgetag (bis 06:00) sind vertreten

- [ ] Test 5 (klassisch, Teil D, Regressionsschutz): GIVEN eine `NormalizedTimeseries`
      mit Stundendaten für Ankunftstag und GENAU einen Folgetag (keine weiteren Tage)
      WHEN `_extract_night_rows()` aufgerufen wird THEN bleibt das bisherige korrekte
      Verhalten erhalten (alle Folgetag-Stunden ≤ 6 werden weiterhin aufgenommen) — der
      Fix darf den Normalfall nicht brechen

- [ ] Test 6 (Diagnose, Teil C): GIVEN eine echte Staging-Mail mit Marker-Header
      `X-GZ-Mail-Type: trip-briefing` WHEN sie in einem Web-Font-fähigen Client
      gerendert und per Screenshot geprüft wird THEN wird "Inter Tight" tatsächlich
      angewendet (Soll-Bestätigung) ODER es wird dokumentiert, welches konkrete Element im
      HTML kein explizites `font-family:{FONT_UI}` trägt (Fix-Bedarf), bevor ein Code-Fix
      vorgenommen wird

### Voraussetzung vor Test 1–3: Pixel-Diff-Tool für E-Mail-HTML

Existiert noch nicht. Muss vor den visuellen RED-Tests gebaut werden (siehe
Implementation Details, Schritt 2): Playwright `page.set_content()` mit dem Output von
`render_html()` + Bild-Diff gegen die Referenz-PNGs, Vorbild `.claude/hooks/design_fidelity_diff.py`
(Screenshot-Mechanik), aber als eigenständiges Werkzeug für den neuen Screen-Typ
"E-Mail-HTML" (kein Frontend-Route-Diff).

## Acceptance Criteria

- **AC-1:** Given eine gerenderte Trip-Briefing-Mail mit Stage-Stats-Grid im Header /
  When sie gegen die Referenz `referenz-header-morgenbriefing.png` per Pixel-Diff
  verglichen wird / Then fehlt die horizontale Linie zwischen Datumszeile und Stats-Grid
  sowie die senkrechte Trennlinie zwischen linker und rechter Header-Spalte und der Text
  "· Etappe N" in der Eyebrow-Zeile. Die horizontale Linie UNTER dem Stats-Grid bleibt
  erhalten (PO-Korrektur 2026-07-02, siehe #956/#966), muss aber in der Vorlagenfarbe
  `#e6e1d3` (statt der geerbten dunkleren Standard-Tabellenfarbe) und über die volle
  Breite durchgehend (gleich breite Stat-Spalten statt Auto-Breite) gerendert werden.
  - Test: Pixel-Diff-Vergleich, kein String-Match auf HTML-Quelltext

- **AC-2:** Given ein Segment mit mehreren vorangehenden Segmenten derselben Etappe (mit
  jeweils eigenem `distance_km`) / When die Mail gerendert wird / Then zeigt der
  Segment-Header "SEG N" gefolgt von der kumulierten Kilometer-Spanne
  ("{fromKm:.1f} km - {toKm:.1f} km") und der Höhen-Spanne ("{fromElev} - {toElev} m"),
  OHNE den bisherigen Etappen-Titel-Text
  - Test: Pixel-Diff gegen `soll-segment-header.png` UND Wertekontrolle der berechneten
    Kilometer-Laufsumme gegen bekannte `distance_km`-Testdaten

- **AC-3:** Given eine `NormalizedTimeseries` mit Stundendaten über mehr als einen
  Folgetag (Ankunftstag + Folgetag + Übermorgen mit Stunden ≤ 6) / When
  `_extract_night_rows()` aufgerufen wird / Then enthält das Ergebnis-Array keine Zeile,
  deren zugrundeliegende Datenpunkte vom Übermorgen-Datum stammen — die fälschliche
  zusätzliche "00"-Zeile aus dem Bug-Screenshot (`ist-nightrows-00-bug.png`) tritt nicht
  mehr auf
  - Test: klassischer pytest-Test, Eingabe/Ausgabe-Vergleich auf Datenpunkt-Ebene

- **AC-4:** Given eine getönte Tabellenzelle (z.B. `precip` über Schwellwert) / When die
  Mail gerendert wird / Then füllt der farbige Hintergrund die Zelle randlos bis an die
  Gitterlinien, ohne den in `ist-cell-tint-spacing.png` sichtbaren weißen Rand
  - Test: Pixel-Diff gegen `soll-cell-tint-spacing.png`

- **AC-5:** Given die Renderer-Commit-Gate-Anforderungen (`renderer_mail_gate.py`) / When
  ein Commit auf `html.py` oder `trip_report.py` erfolgt / Then läuft
  `tests/tdd/test_issue_811_mode_matrix.py` grün und `briefing_mail_validator.py` liefert
  einen frischen erfolgreichen Lauf gegen die echte Staging-Mail — die strukturellen
  Änderungen aus AC-1/AC-2/AC-4 haben den Modus-Matrix-Vertrag nicht gebrochen
  - Test: Gate-Lauf vor jedem Commit (kein manueller Bypass)

- **AC-6:** Given `src/output/renderers/email/compact.py` / When die Fixes aus AC-1,
  AC-2, AC-4 implementiert werden / Then bleibt `compact.py` unverändert — der mobile
  Renderer nutzt keinen der betroffenen Codepfade (Header-Border, Segment-Titel-Text,
  Cell-Tint-Margin); nur der Nacht-Zeit-Fix (AC-3) wirkt gemeinsam, weil `compact.py`
  dieselbe `trip_report.py::_extract_night_rows()`-Datenquelle konsumiert
  - Test: Diff-Prüfung, dass `compact.py` im Commit nicht verändert wurde; zusätzlich
    ein bestehender `compact`-Modus-Test aus der Modus-Matrix bleibt grün

- **AC-7:** Given die Font-Family-Diagnose (Teil C) / When eine echte Staging-Mail mit
  Marker-Header `X-GZ-Mail-Type: trip-briefing` in einem Web-Font-fähigen Client
  betrachtet wird / Then ist entweder bestätigt, dass "Inter Tight" korrekt angewendet
  wird (kein Code-Fix nötig, Diagnose-Ergebnis wird in dieser Spec dokumentiert) oder das
  konkrete Element ohne `font-family:{FONT_UI}`-Deklaration ist benannt und gefixt
  - Test: manuelle Diagnose-Session mit Screenshot-Beleg, kein Blind-Fix ohne
    Reproduktion

## Known Limitations

- Die genaue CSS-Regel für die `<td>`-Padding im globalen `<style>`-Block (Zeilen
  ~1157–1478) war zum Zeitpunkt der Analyse noch nicht vollständig lokalisiert — muss in
  der Implementierungsphase vor dem Cell-Tint-Fix (AC-4) verifiziert werden.
- Die exakte Fundstelle der senkrechten Header-Spalten-Trennlinie (AC-1, Punkt 3) war zum
  Zeitpunkt der Analyse noch nicht im CSS-Block bestätigt.
- AC-7 (Font-Diagnose) kann ggf. ohne Code-Änderung enden, falls sich die Abweichung als
  reines Client-Rendering-Artefakt herausstellt — das AC gilt dennoch als erfüllt, sofern
  die Diagnose dokumentiert und mit einem echten Staging-Mail-Screenshot belegt ist.
- Das Pixel-Diff-Tool für E-Mail-HTML ist eine Neuentwicklung ohne bestehende
  Testabdeckung; Schwellwert-Kalibrierung (welcher Diff-Prozentsatz als "bestanden" gilt)
  muss in der TDD-RED-Phase anhand der ersten echten Diffs festgelegt werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix/Format-Korrektur an einem bestehenden Renderer ohne
  architektonische Richtungsentscheidung — keine neue Komponente, kein neuer
  Datenfluss, keine Technologie-Wahl. Die neue Pixel-Diff-Test-Infrastruktur folgt einem
  bereits etablierten Muster (`design_fidelity_diff.py`, Issue #603) und stellt daher
  ebenfalls keine neue architektonische Entscheidung dar. [no-adr]

## Changelog

- 2026-07-01: Initial spec erstellt — Issue #956, Workflow `fix-956-email-format`
