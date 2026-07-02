# Context: fix-956-email-format

## Request Summary
Issue #956 bündelt mehrere Abweichungen der Trip-Briefing-E-Mail (HTML-Renderer) von der
Claude-Design-Vorlage: überflüssige Trennlinien im Header, doppelter Etappen-Titel im
Segment-Header statt Kilometer-/Höhen-Spanne, Schriftart weicht von "Inter Tight" ab, ein
Zeit-Bug in der Nacht-Tabelle ("00" statt "08"), und ein Spacing-Fehler bei getönten
Tabellenzellen (Nachtrag-Kommentar). Der Vorlagen-Bezug ist das Claude-Design-Projekt
"Gregor Zwanzig" (`019dfcf4-1e69-73f2-b094-c19e157014a2`), Datei
`Gregor 20 - Mail Vorschau.html` + `screen-output-preview.jsx`.

**PO-Vorgabe (Issue-Text):** "Du musst die TDD RED Tests visuell erstellen. Code-Tests sind
hier nicht erlaubt." → RED-Phase muss auf Screenshot-/Pixel-Vergleich basieren, nicht auf
`assert 'x' in html`.

## Vier Teil-Probleme (Detail)

### A) Header-Trennlinien + Etappen-Code-Text (Screenshot 1, 4 Annotationen)
Vorlage (`docs/design-requests/issue-956-mail-vorschau/screenshots/referenz-header-morgenbriefing.png`)
vs. IST (`.../ist-header-linien-annotiert.png`):
1. Horizontale Linie zwischen Datumszeile und Stats-Grid → entfernen
2. Horizontale Linie unter dem Stats-Grid → entfernen; die senkrechten Trennlinien
   zwischen den 5 Stat-Zellen (Distanz|Aufstieg|Abstieg|Max Höhe|Segmente) sollen stattdessen
   weiter nach unten in den weißen Content-Bereich hineingezogen werden (kein harter
   horizontaler Schnitt zwischen Header-Grau und weißem Body).
3. Senkrechte Trennlinie zwischen linker Header-Spalte (Titel/Datum) und rechter Spalte
   (GREGOR ZWANZIG / Trip-Name / Etappe N/M) → entfernen
4. Text "· Etappe 3" in der Eyebrow-Zeile ("ABEND-BRIEFING · Etappe 3") → entfernen
   (die Etappen-Nummer steht bereits rechts als "Etappe 3 / 13")

Code: `src/output/renderers/email/html.py` `render_html()`, Header-Aufbau ca. Zeile 803–847
(`left_col`, `right_col`, `header_html`; `_eyebrow(f"{_rt_upper}-BRIEFING · {_stage_label}")`
für Punkt 4). Border-Definitionen der Stats-Grid-Zellen: `_render_email_stat()` Zeile 145–162
(`border-right:1px solid #e6e1d3` je Zelle) + `stats_grid_html`-Tabelle Zeile 776–780
(`border-top:1px solid #e6e1d3`). Die konkreten Linien für Punkt 1/2/3 sind im CSS-`<style>`-
Block oder in `header_html`'s äußerem `<div>` zu suchen (border-bottom auf dem Header-Div,
Zeile 840: `border-bottom:1px solid #e6e1d3` — evtl. das ist Linie 1 oder eine andere).
**Für Analyse-Phase:** exakte Border-Deklarationen im CSS-Block (Zeilen ~1157–1478, noch
nicht vollständig gelesen) verifizieren.

### B) Segment-Header: Text statt Kilometer-/Höhen-Spanne (Screenshots 4+5, Folge-Kommentar bestätigt)
**Bereits in der frischen Design-Vorlage exakt vorgegeben** (per DesignSync neu geladen,
`screen-output-preview.jsx`, Funktion `EmailSegmentBlock`):
```jsx
<span style={{...}}>SEG {idx}</span>
{/* KEIN Titel-Text mehr */}
...
{seg.when} · {seg.fromKm.toFixed(1)} km - {seg.toKm.toFixed(1)} km · {fmt(seg.fromAlt)} - {fmt(seg.toAlt)} m
```
Die lokale Kopie unter `docs/design-requests/mail-vorschau-2026-06-05/screen-output-preview.jsx`
ist STALE (andere MD5) — sie hatte noch `seg.title.split(" · ")[1]` und
`↑{fmt(seg.asc)} · {fmt(seg.fromAlt)}→{fmt(seg.toAlt)} m`. Die frische Version liegt jetzt in
`docs/design-requests/issue-956-mail-vorschau/` (siehe unten).

IST (`src/output/renderers/email/html.py` Zeile 930–946, `seg_header_desktop`):
```python
f'<span style="font-size:14px;font-weight:600;">'
f'{sub_header or seg_header_text(seg)}</span>'   # ← zeigt vollen Etappen-Namen, MUSS WEG
...
f'{seg_time}{km_str} · {elev_arrow}{s_elev}</div>'  # ← einzelner km-Wert + Pfeil+Starthöhe,
                                                      #    MUSS: from_km-to_km · from_elev-to_elev
```
`km_str` kommt aus `seg_km = getattr(seg, "distance_km", None)` (Segment-eigene Distanz, nicht
kumuliert). Für `fromKm`/`toKm` (laufende Kilometer auf der Gesamtstrecke) fehlt aktuell eine
kumulierte Distanz-Berechnung über die Segmente einer Etappe — muss in der Analyse-Phase
lokalisiert werden (`seg.distance_km` pro Segment aufsummieren in Aufrufreihenfolge).
`e_elev`/`s_elev` (Segment-End-/Start-Höhe) sind bereits vorhanden (Zeile 872–873), nur nicht
im Format "{s_elev} - {e_elev} m" verwendet.

### C) Font-Family (Screenshot: SOLL "Inter Tight, -apple-system, ...", IST "Arial, Helvetica, sans-serif")
`design_tokens.py` definiert bereits `FONT_UI = "'Inter Tight', -apple-system, ..."` (Zeile 39)
und `WEB_FONT_LINK` (Google-Fonts-`<link>`, Zeile 43–47), eingebunden in `render_html()`
Zeile ~1415 (`{WEB_FONT_LINK}`) und im body-CSS `body {{ font-family: {FONT_UI}; ...}}` Zeile
~1417. **Hypothese für Analyse-Phase:** Der Font-Code ist vermutlich korrekt; die IST-
Diskrepanz könnte daher stammen, dass (a) der Screenshot in einem Client ohne Web-Font-Support
entstand (Fallback-Kette bis Arial ist client-seitig, kein Bug), oder (b) einzelne Elemente
(insbesondere `FONT_DATA`/Mono-Elemente vs. Fließtext-Elemente ohne explizites
`font-family:{FONT_UI}`) tatsächlich ohne Font-Deklaration rendern und daher auf
Client-Default (oft Arial) zurückfallen. Muss in Analyse-Phase mit echter Staging-Mail
(Marker-Header `X-GZ-Mail-Type: trip-briefing`) + Screenshot verifiziert werden — nicht
blind "fixen" ohne Reproduktion.

### D) Nacht-Tabelle: letzte Zeile zeigt "00" statt korrekt keine/andere Zeile (Screenshot 6)
**Root Cause bereits lokalisiert** (Explore-Agent, worktree
`.claude/worktrees/lazy-crunching-thacker`):
`src/formatters/trip_report.py::_extract_night_rows()` (Methode ca. Zeile 279–321).
Zeile 298: `is_next_day = local_dt.date() > first_date` — das ist "größer als", nicht "genau
ein Tag später". Enthält das `night_weather`-Zeitreihen-Objekt mehr als einen Folgetag an
Stundendaten (z. B. weil der Provider mehrere Tage liefert), werden Datenpunkte von
**übermorgen** mit Stunde ≤ 6 fälschlich ebenfalls als "Nacht"-Daten akzeptiert. Die
Block-Aggregation (`_aggregate_night_block()`, Zeile 323–332) labelt Blöcke nur nach
`hour - hour % interval` OHNE Datum im finalen `time`-String — ein Block von "übermorgen
00:00" sortiert (Zeile 316: `sorted(blocks.keys())`, Key = `(date, block_start)`) hinter dem
echten "morgen 06:00"-Block ein und erscheint als zusätzliche, fälschlich "00" gelabelte Zeile.
**Fix-Richtung (nicht in Context-Phase umsetzen):** `is_next_day` muss auf
`local_dt.date() == first_date + timedelta(days=1)` präzisiert werden, damit nur echte
Folgetag-Daten (nicht spätere Tage) ins Nacht-Fenster fallen.

## Nachtrag-Kommentar (issuecomment-4859680791): Cell-Tint-Spacing
SOLL: getönter Zell-Hintergrund füllt die Zelle randlos/nahtlos bis an die Gitterlinien.
IST: sichtbarer weißer Rand um den getönten Bereich (wirkt wie eingerückte Pille).
Code: `src/output/renderers/email/html.py` Zeile 553–557 (`_render_html_table`):
```python
if cell_bg:
    cell = (
        f'<span style="display:block;background:{cell_bg};'
        f'margin:-6px -4px;padding:6px 4px;">{cell}</span>'
    )
```
Negative-Margin-Hack, der die tatsächliche `<td>`-Padding-Deklaration im globalen CSS-Block
(nicht inline, muss noch lokalisiert werden — vermutlich `padding: 8px 4px` je `<td>` laut
Vorlage `dCellStyle()`/`sevCellStyle()` in `screen-output-preview.jsx`, die `8px 4px`
verwenden, nicht `6px 4px`) exakt kompensieren muss. Mismatch zwischen den hart codierten
`-6px -4px` und der echten CSS-Padding erzeugt die sichtbare Lücke.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/html.py` | Haupt-Renderer für Trip-Briefing-HTML-Mails (Header A, Segment-Header B, Cell-Tint Nachtrag) |
| `src/output/renderers/email/design_tokens.py` | FONT_UI/FONT_DATA/WEB_FONT_LINK (Teil C) |
| `src/output/renderers/email/helpers.py` | fmt_val, visible_cols u.a. Formatierungs-Helper |
| `src/output/renderers/email/compact.py` | Mobile/kompakte Renderer-Variante (ggf. gleiche Bugs) |
| `src/formatters/trip_report.py` | `_extract_night_rows`/`_aggregate_night_block` — Root Cause Teil D |
| `src/services/trip_report_scheduler.py` | Bindet WEB_FONT_LINK ein, ruft render_html auf |
| `docs/design-requests/issue-956-mail-vorschau/` | Frisch geladene Vorlagen-Dateien (screen-output-preview.jsx, tokens.css, mock-data.jsx, atoms/molecules/organisms/brand-kit/mobile-shell.jsx, Screenshots) |
| `docs/design-requests/mail-vorschau-2026-06-05/` | STALE — nicht mehr als Referenz verwenden |
| `docs/reference/mail_validators.md` | Validator-Dispatch (`briefing_mail_validator.py` für trip-briefing-Pfad) |

## Existing Patterns
- JSX-Vorlage ist 1:1 in Python-f-String-HTML übersetzt (Kommentare "Issue #884 helpers —
  JSX design-vorlage 1:1 translation" in html.py) — bestehendes Muster für Segment B: Direkte
  Übersetzung der neuen JSX-Zeile in den entsprechenden Python-String.
- Farbtöne/Schwellwerte (RISK_CELL, sevWind etc.) sind in JSX UND Python dupliziert gepflegt —
  kein gemeinsames Token-File für Zahlenschwellen (nur Farben in design_tokens.py zentral).

## Dependencies
- Upstream: `night_weather` NormalizedTimeseries (Provider-Daten), `seg.distance_km` pro
  Segment (Normalizer/Risk-Engine-Ausgabe)
- Downstream: `briefing_mail_validator.py` (Gate für "E2E bestanden" bei Mail-Änderungen),
  Renderer-Commit-Gate (`renderer_mail_gate.py`) blockt Commits auf `email.py`-Dateien ohne
  frischen Modus-Matrix-Test + Validator-Lauf

## Existing Specs
- `docs/specs/modules/output_channel_renderers.md` §A1+§A5+§A6 (referenziert in html.py Docstring)
- `docs/specs/modules/issue_240_email_design_tokens.md` (Design-Tokens-Quelle)

## Analysis

### Type
Bug (5 Teil-Bugs, ein gemeinsamer Kontext: HTML-Trip-Briefing-Renderer)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/formatters/trip_report.py` | MODIFY | Zeile 298: `is_next_day = local_dt.date() > first_date` → `== first_date + timedelta(days=1)` (Teil D) |
| `src/output/renderers/email/html.py` | MODIFY | Header-Border-Deklarationen Zeile 778 (`stats_grid_html` border-top) + Zeile 840 (Header-Div border-bottom) entfernen; vertikale Stat-Trenner-Linien (`_render_email_stat`, Zeile 150) in den Body verlängern (Teil A, Punkt 1+2); senkrechte Spalten-Trennlinie zwischen Header links/rechts lokalisieren + entfernen (Teil A, Punkt 3 — vermutlich im CSS-Block ~1157-1478); `_eyebrow(...)`-String kürzen, `· {_stage_label}` raus (Teil A, Punkt 4); Segment-Header Zeile 930-946 umbauen: Titel-Text raus, kumulierte km-Laufsumme + Höhen-Spanne einführen (Teil B); Cell-Tint negative-margin Zeile 553-557 an echte `<td>`-Padding-Regel anpassen (Teil E) |
| `.claude/hooks/design_fidelity_diff.py` (Referenz) | READ-ONLY Vorbild | Pixel-Diff-Muster für neues Mail-HTML-Diff-Tool (kein Frontend-Screen, muss adaptiert werden) |
| Neues Test-/Tooling-Stück (Pfad TBD in Spec-Phase) | CREATE | Playwright-basiertes Pixel-Diff-Tool für gerendertes E-Mail-HTML gegen `docs/design-requests/issue-956-mail-vorschau/screenshots/` — existiert noch nicht, ist Voraussetzung für "visuelle TDD RED" bei A/B/E |
| `src/output/renderers/email/compact.py` | KEINE ÄNDERUNG | Bestätigt: kein SEG-Header-, Font- oder Cell-Tint-Codepfad betroffen (nur D wirkt pfadübergreifend in `trip_report.py`, dort gemeinsam gefixt) |

### Scope Assessment
- Files: 2 Code-Dateien (html.py, trip_report.py) + 1 neues Test-/Tooling-Stück
- Estimated LoC: ~50–65 (D: 1 Zeile · A: ~15–25 · B: ~20–30 · E: ~2–5 · C: 0–5, evtl. reiner Diagnose-Task ohne Code-Änderung)
- Risk Level: LOW–MEDIUM (kleine, isolierte Änderungen; Hauptrisiko ist Teil E ohne vorherige Lokalisierung der echten `<td>`-Padding-Regel, sowie Kollateralschäden am Modus-Matrix-Test durch strukturelle HTML-Änderungen in A/B/E)

### Technical Approach
**Reihenfolge (aus Plan/Sonnet-Bewertung):**
1. **D zuerst** — isolierter Ein-Zeilen-Fix in `trip_report.py`, reine Datumslogik, kein visuelles Element betroffen → klassischer Code-Test reicht hier (PO-Vorgabe "visuell" bezieht sich sinnvollerweise nur auf sichtbare Layout-Bugs A/B/C/E, nicht auf reine Backend-Datumslogik).
2. **Pixel-Diff-Infrastruktur bauen** — vorgelagerter Task: `render_html()` real rendern → Playwright `page.set_content()` + Screenshot → Vergleich gegen Referenz-PNGs unter `docs/design-requests/issue-956-mail-vorschau/screenshots/`, gleicher Schwellwert-Mechanismus wie `design_fidelity_diff.py` (Issue #603), aber neuer Screen-Typ "E-Mail-HTML" statt Frontend-Route. **Wichtig:** `test_952_alert_mail_design_fidelity.py` ist trotz Namens KEIN Pixel-Diff (nur String-Assertions) — kein Vorbild, widerspricht der PO-Vorgabe.
3. **E vor A/B** — beide brauchen dieselbe Recherche im CSS-Block (echte `<td>`-Padding-Regel lokalisieren, Verdacht: generischer `td { padding: 6px; ...}`-Selektor statt der von der Vorlage verwendeten `8px 4px`).
4. **B vor A** — B führt eine neue Datenberechnung (kumulierte km-Laufsumme) ein, A ist reines CSS/String.
5. **C zuletzt / parallel** — reiner Diagnose-Task mit echter Staging-Mail + Screenshot-Verifikation; ggf. kein Code-Fix nötig, wenn sich der IST-Font als Client-Rendering-Artefakt herausstellt.

### Dependencies
- **Renderer-Commit-Gate** (`renderer_mail_gate.py`) — unumgehbar, verlangt vor jedem Commit auf `html.py`/`trip_report.py`: grünen `tests/tdd/test_issue_811_mode_matrix.py` + frischen `briefing_mail_validator.py`-Lauf gegen echte Staging-Mail.
- Modus-Matrix-Test testet nicht direkt die betroffenen Header-/Segment-Strings, kann aber durch strukturelle HTML-Änderungen (A/B/E) kollateral brechen → nach jeder Änderung laufen lassen.
- `compact.py` ist unabhängig bestätigt — keine Doppel-Prüfung für A/B/C/E nötig, nur D wirkt gemeinsam.

### Open Questions
- [x] compact.py betroffen? → NEIN, bestätigt.
- [ ] Exakte CSS-Regel für `<td>`-Padding (Teil E) — in Spec-/Implementierungs-Phase im CSS-Block ~1157-1478 lokalisieren.
- [ ] Exakte Fundstelle der senkrechten Spalten-Trennlinie im Header (Teil A, Punkt 3) — noch nicht im CSS-Block verifiziert.
- [ ] Teil C: Diagnose-Ergebnis von der echten Staging-Mail abwarten, bevor Code geändert wird.

## Risks & Considerations
- **Renderer-Commit-Gate**: jede Änderung an `html.py` erfordert vor Commit (1) grünen
  `tests/tdd/test_issue_811_mode_matrix.py` und (2) frischen `briefing_mail_validator.py`-Lauf
  gegen die echte Staging-Mail.
- **Visuelle statt Code-TDD-RED**: PO-Vorgabe explizit — RED-Artefakt muss ein
  Screenshot-/Pixel-Vergleich sein, kein `assert 'x' in html`. Abweichung vom Standard-TDD-RED-
  Skill-Flow; im Spec-/TDD-Phasen-Prompt explizit vermerken.
- **compact.py** (mobile Renderer) wurde noch nicht auf dieselben vier Bugs geprüft — evtl.
  identische Fixes dort nötig (separater AC oder bewusst außerhalb des Scopes benennen).
- **Kumulierte Kilometer (fromKm/toKm)**: aktuell nicht als Datenfeld vorhanden — Analyse-Phase
  muss klären, ob das im Renderer (durch Aufsummieren vorheriger `seg.distance_km`) oder weiter
  oben in der Pipeline berechnet werden soll.
- **Font-Bug (Teil C)**: ggf. kein Code-Bug, sondern Client-Rendering-Limitierung — vor Fix
  zwingend mit echter Staging-Mail reproduzieren (KEINE Blind-Änderung).
- Datei liegt im isolierten Worktree `worktree-lazy-crunching-thacker` (Session-Singleton-Regel).
