---
entity_id: issue_884_mail_fidelity
type: feature
created: 2026-06-25
updated: 2026-06-25
status: draft
version: "3.0"
tags: [email, renderer, html, design-fidelity, briefing]
workflow: fix-884-mail-fidelity
---

<!-- Issue #884 — E-Mail-Renderer Fidelity: gesamte HTML-Mail an Claude-Design-Vorlage angleichen (alle 7 Sektionen) -->

# Issue 884 — E-Mail-Renderer Fidelity: vollständige 1:1-Umsetzung (v3.0)

## Approval

- [ ] Approved

## Purpose

Den Python-HTML-Mail-Renderer in allen Sektionen vollständig an die Claude-Design-Vorlage
(`screen-output-preview.jsx`, EmailPreview-Komponente) angleichen — Desktop und Mobile gleichzeitig.

**Implementierungsansatz:** Der Developer Agent liest das JSX als 1:1-Implementierungsvorlage.
JSX-Inline-Styles werden direkt in Python-f-String-HTML übersetzt. Wo JSX CSS-Grid/Flex verwendet,
entsteht ein Outlook-kompatibler `<table>`-Ersatz mit optisch identischem Ergebnis.

**v3.0-Änderungen gegenüber v2.0:**
- Tages-Summe-Sektion ENTFERNT (wurde im neuen Cloud-Design aus JSX entfernt)
- Antwort-Kommandos als EIGENE Sektion hinzugefügt (neues dediziertes Layout in JSX)
- EmailHourList als NEUE mobile Tabellen-Komponente (ersetzt `_render_mobile_compact_rows`)
- Stirnlampe-Sektion: ENTFÄLLT (PO-Entscheidung, unverändert)

## Source

- **File:** `src/output/renderers/email/html.py` — Hauptrenderer (~734 LoC)
- **File:** `src/output/renderers/email/design_tokens.py` — neues Token `G_HEADER_BG`

## Estimated Scope

- **LoC:** ~450 (Modifikationen + neue Hilfsfunktionen)
- **Files:** 2
- **LoC-Limit-Override:** 500 (PO bestätigt)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/design_tokens.py` | module | Neues Token `G_HEADER_BG = '#fbfaf6'` |
| `src/output/renderers/email/helpers.py` → `format_trend_tokens()` | function | Liefert `thunder_sq_color` für Risk-Dot |
| `tests/tdd/test_issue_811_mode_matrix.py` | test | Nicht-Regressions-Gate — muss grün bleiben |
| `.claude/hooks/briefing_mail_validator.py` | gate | Pflicht-Gate: Exit 0 vor Commit-Merge |
| `.claude/hooks/renderer_mail_gate.py` | gate | Blockiert Commits bis Matrix-Test + Validator grün |

## Sektionen (7 implementiert, 1 weggelassen)

Die neue JSX-Vorlage definiert 8 Abschnitte. Implementiert werden 7:

| Nr. | Sektion | JSX-Komponente | Status |
|-----|---------|----------------|--------|
| 1 | Header (zweispaltig + Stats-Grid) | `EmailPreview` L63–122 | IMPLEMENTIEREN |
| 2 | Quick-Take + Tags | `EmailPreview` L124–137 | IMPLEMENTIEREN |
| 3 | Stirnlampe | `EmailPreview` L139–153 | ENTFÄLLT (PO-Entscheidung) |
| 4 | Segmente (EmailSegmentBlock + EmailDataTable/EmailHourList) | L155–161, L276–350 | IMPLEMENTIEREN |
| 5 | Wetter am Ziel (abgesetzt, accent-Eyebrow) | `EmailPreview` L162–172 | IMPLEMENTIEREN |
| 6 | Folge-Etappen (UpcomingRow mit Risk-Dot + Gewitter-Badge) | L174–183, L388–422 | IMPLEMENTIEREN |
| 7 | Antwort-Kommandos (3×2-Grid, eigene Sektion) | `EmailPreview` L185–200 | IMPLEMENTIEREN (NEU) |
| 8 | Footer (zweigeteilt: Brand + Link-Zeile) | `EmailPreview` L201–212 | IMPLEMENTIEREN |

**Tages-Summe entfällt** — `SumStat`-Komponente existiert in JSX, wird aber **nicht mehr in EmailPreview verwendet**.
Diese Sektion ist im neuen Cloud-Design entfernt worden.

## Technische Konventionen

### Outlook-Kompatibilität (PFLICHT)
- Kein `display:grid` in Mail-HTML — alle Grid-Layouts als `<table>`
- Kein `display:flex` ohne `<table>`-Fallback
- Mobile via `@media (max-width:600px)` + CSS-Klassen `desktop-only` / `mobile-compact` im `<style>`-Block

### JSX → Python-Übersetzungsregeln
| JSX | Python f-string |
|-----|----------------|
| `{ fontSize: 12, color: "#abc" }` | `style="font-size:12px;color:#abc;"` |
| `fontFamily: EMAIL_MONO_STACK` | `style="font-family:'{JB_MONO}',monospace;"` |
| `fontVariantNumeric: "tabular-nums"` | `style="font-variant-numeric:tabular-nums;"` |
| `display:"flex", justifyContent:"space-between"` | `<table width="100%"><tr><td>…</td><td align="right">…</td></tr></table>` |
| `display:"grid", gridTemplateColumns:"repeat(5,1fr)"` | `<table><tr><td>…</td>×5</tr></table>` |

### Neue Hilfsfunktionen

| JSX-Komponente | Python-Funktion (neu) |
|---|---|
| `EmailStat` | `_render_email_stat(label, value, unit, last, is_mobile)` |
| `EmailEyebrow` | `_eyebrow(text, accent=False)` → f-string |
| `EmailHourList` | `_render_mobile_hour_list(rows)` (ersetzt `_render_mobile_compact_rows`) |
| `RiskDot` | `_risk_dot(color)` → f-string |
| Antwort-Kommandos | `_render_kommandos_section()` (neu) |
| Footer zweigeteilt | `_render_footer()` (überarbeitet) |

### Neues Design-Token
```python
G_HEADER_BG = '#fbfaf6'   # Header + Section-Hintergrund (heller als G_PAPER #f6f4ee)
```

## Sektion 1: Header (zweispaltig + Stats-Grid)

**IST:** Einspaltiger Block — Profil-Eyebrow, `<h1>`, Datum.

**SOLL** (JSX L63–122):

Outer-Div via HTML-`<table>` mit zwei `<td>`:
- Hintergrund: `G_HEADER_BG (#fbfaf6)`, `border-bottom:1px solid #e6e1d3`

**Linke `<td>` (Desktop: padding-right; Mobile: volle Breite):**
- Eyebrow: "MORGEN-BRIEFING · {stage_code}" — mono 10px, color `#c45a2a`, fontWeight 600, letterSpacing 0.12em
- Titel: 22px desktop / 18px mobile, fontWeight 600, letterSpacing -0.015em, color `#1d1c1a`
- Datum: "Mi · DD.MM.YYYY · HH:MM MESZ" — mono 13px desktop / 12px mobile, color `#6b6962`

**Rechte `<td>` (text-align right; Mobile: in eyebrow-Zeile integriert):**
- "GREGOR ZWANZIG" — mono 10px, color `#9a978d`, letterSpacing 0.12em, fontWeight 600
- Trip-Kurzname — 14px, fontWeight 600, color `#1d1c1a`
- "Etappe N/M" — mono 12px, color `#6b6962`

**Stats-Grid** (JSX L108–121): `<table>` mit 5 gleichbreiten `<td>` (desktop) / 3 Spalten in 2 Zeilen via `@media` (mobile).
`border-top:1px solid #e6e1d3`, `border-right:1px solid #e6e1d3` als Trennlinie zwischen Stats.

Jede Stat-Zelle (via `_render_email_stat`):
- Label: 9px mono, color `#9a978d`, uppercase, letterSpacing 0.1em
- Wert: 18px desktop / 15px mobile, fontWeight 600, mono, tabular-nums, color `#1d1c1a`
- Einheit (optional): 11px, color `#9a978d`, fontWeight 400, marginLeft 3px

Inhalte: Distanz (km) · Aufstieg (↑ m) · Abstieg (↓ m) · Max-Höhe (m) · Segmente (Anzahl)

## Sektion 2: Quick-Take + Tags

**IST:** `metrics_summary_html` oder `compact_summary` ohne eigene Sektion.

**SOLL** (JSX L124–137):
- Padding: 20px 28px 16px desktop / 18px 16px 14px mobile, bg `#fff`
- `_eyebrow("Quick-Take")` — 10px mono, color `#9a978d`, uppercase, letterSpacing 0.12em
- `compact_summary`-Text: 15px desktop / 13px mobile, lineHeight 1.55, color `#3a3835`, marginTop 8px
- Tag-Zeile (flexWrap, gap 6px, marginTop 12px) via `<span>` Inline-Tags:
  - `tone="warn"` (bg `#fde6cc`, fg `#7c2d12`, border `#f0a060`) — für Warn-Einträge
  - `tone="ok"` (bg `#dcf2e1`, fg `#14532d`, border `#86c89a`) — für ok-Status
  - `tone="info"` (bg `#dde8f3`, fg `#1e3a5f`, border `#8aacd0`) — für Infos
  - `tone="risk"` (bg `#fadcd6`, fg `#7f1d1d`, border `#e88472`) — für Risiko
  - Stil immer: display inline-flex, padding 4px 10px, font-size 11px, fontWeight 600, mono, letterSpacing 0.02em, KEIN border-radius

## Sektion 4: Segmente (EmailSegmentBlock + Tabellen)

**IST:** Einfacher 1-Ebenen-Tabellen-Header, padding 6px, border `G_INK_FAINT`.

**SOLL** (JSX L155–161, L276–350):

### Segment-Header-Karte (JSX L276–296, pro Segment)
`<table>` mit einer Zeile, `border-bottom:2px solid #1d1c1a`, paddingBottom 8px:
- Links: "SEG {N}" (mono 11px, color `#c45a2a`, letterSpacing 0.1em, fontWeight 600) + Segment-Titel (14px desktop / 13px mobile, fontWeight 600)
- Rechts: Zeitraum · km · ↑Aufstieg · von→bis m (mono 11px, color `#6b6962`)

### EmailDataTable — Desktop (JSX L299–351)

**Header-Ebene 1 (Gruppen-Row):** Hintergrund `#fbfaf6`, font-size 9px mono uppercase, fontWeight 600, padding 5px 4px 4px, borderBottom 1px `#e6e1d3`, borderRight 1px `#f0ece1`:
- colspan 1: leer (Zeit)
- colspan 2: "TEMP" (color `#c45a2a`)
- colspan 3: "WIND" (color `#9a978d`)
- colspan 3: "NIEDERSCHLAG" (color `#2a6a8c`)
- colspan 2: "SICHT / UV" (color `#9a978d`)
- colspan 1: "HÖHE" (color `#9a978d`)
- colspan 1: leer (Risk-Spalte)

**Header-Ebene 2 (Einheiten-Row):** bg `#fff`, borderBottom 1px `#e6e1d3`, fontSize 11px, color `#3a3835`, fontWeight 600, padding 6px 4px, borderRight 1px `#f0ece1`:
`h | °C | gef. | km/h | böe | dir | mm | R% | Gw% | km | UV | 0°m | ·`

**Datenzellen:** padding 8px 4px, fontSize 13px, mono, tabular-nums, borderRight 1px `#f0ece1`, Zeilentrennlinie 1px `#f0ece1`.

**Highlighting** (fontWeight 700 + Farbe bei Überschreitung):
| Metrik | Schwelle | Farbe |
|--------|----------|-------|
| Wind | > 20 km/h | `#c2410c` |
| Böen | > 30 km/h | `#c2410c` |
| Niederschlag | > 1 mm | `#0e6fb8` |
| Regenwahrsch. | > 50 % | `#0e6fb8` |
| Gewitterindex | > 0 | `#b91c1c` |
| Sichtweite | < 2 km | `#c2410c` |

**Colspan-Kompatibilität:** Spaltenanzahl und Colspan-Werte folgen der aktiven `display_config` — kein Mismatch wenn einzelne Metriken deaktiviert.

### EmailHourList — Mobile NEU (JSX L452–510)

Neue Funktion `_render_mobile_hour_list(rows)`, ersetzt `_render_mobile_compact_rows()`.
Pro Stunde: zwei Zeilen, kein Horizontal-Scroll:

**Hauptzeile:** Zeit (13px mono bold, 26px breit) · Wetter-Glyph (☼/⛅/☁/☂, 14px) · Temp (14px mono bold) · gefühlte Temp (11px mono `#9a978d`) · Risk-Dot rechts

**Detailzeile** (paddingLeft 36px, mono 11px, color `#6b6962`):
`Wind {km/h}/{böen} {dir}` · `Regen {mm} ({%})` · ggf. `Gw {%}` · `Sicht {km}` · `UV {n}` · `0° {m}`
Kritische Werte: fett + Farbe (gleiche Schwellen wie Desktop)

Hintergrund: transparent (ok), leicht warn-getönt wenn risk=watch (`rgba(194,65,12,0.04)`), risk (`rgba(185,28,28,0.05)`)

## Sektion 5: Wetter am Ziel (abgesetzt)

**IST:** In Segment-Block integriert oder nicht vorhanden.

**SOLL** (JSX L162–172):
- Eigene Sektion: bg `#fbfaf6`, `border-top:1px solid #e6e1d3`, marginTop 16px
- Padding: 20px 28px 0 desktop / 18px 16px 16px mobile
- Kopfzeile: Zweispaltig space-between, align baseline:
  - Links: `_eyebrow("Ankunft · Wetter am Ziel", accent=True)` (color `#c45a2a`) + Zielname (16px desktop / 14px mobile, fontWeight 600, marginTop 4px)
  - Rechts: Zeitraum-String (mono 12px desktop / 11px mobile, color `#6b6962`)
- Desktop: `EmailDataTable` (gleicher Stil wie Sektion 4)
- Mobile: `EmailHourList`

## Sektion 6: Folge-Etappen/Ausblick (UpcomingRow + Risk-Dot + Gewitter-Badge)

**IST:** HTML-`<table>` mit 4 Spalten (TEMP/REGEN/WIND/GEWITTER), 2 Zeilen pro Etappe.

**SOLL** (JSX L174–183, L388–422):
- Bg `#fbfaf6`, padding 24px 28px 16px desktop / 20px 16px 12px mobile
- `_eyebrow("Ausblick · nächste 4 Tage")`
- `<table>` mit einer `<tr>` pro Folge-Etappe, `border-bottom:1px solid #e6e1d3`

**Desktop** (5 `<td>` per `<tr>`):
| Spalte | Breite | Inhalt | Stil |
|--------|--------|--------|------|
| Wochentag | 32px | "Mo"/"Di" etc. | mono 11px, fontWeight 700, color `#1d1c1a`, letterSpacing 0.04em |
| Code | 70px | Etappen-Code | mono 11px, color `#9a978d` |
| Name + Note + ggf. Badge | flex | Titel (12px bold) + Note (11px `#6b6962`) + Gewitter-Badge | — |
| Temp-Range | 80px | "−1 / 13°C" | mono 11px, color `#3a3835`, textAlign right |
| Risk-Dot | 14px | `_risk_dot(color)` | `border-radius:50%` |

**Gewitter-Badge** (JSX L393–396, wenn `thunder` vorhanden):
`<span style="font-family:mono;font-size:10px;font-weight:700;color:#b91c1c;background:rgba(185,28,28,0.09);padding:2px 7px;border:1px solid rgba(185,28,28,0.22);">⚡ Gewitter {zeitangabe}</span>`

**Mobile** (3 `<td>` per `<tr>`, JSX L388–408):
- Spalte 1: Wochentag (28px, 11px mono bold)
- Spalte 2: Titel + Code + Note + ggf. Gewitter-Badge gestapelt
- Spalte 3: Temp-Range + Risk-Dot übereinander (align-end)

**Risk-Dot `_risk_dot(color)`** — `thunder_sq_color` aus `format_trend_tokens()`:
| Risk-Level | bg | ring |
|---|---|---|
| ok | `#15803d` | `rgba(21,128,61,0.18)` |
| watch | `#c2410c` | `rgba(194,65,12,0.20)` |
| risk | `#b91c1c` | `rgba(185,28,28,0.22)` |
| Fallback | `#c8c4b8` | transparent |

## Sektion 7: Antwort-Kommandos (NEU — eigene Sektion)

**IST:** Nicht als eigene Sektion vorhanden; PAUSE/SKIP/STOP irgendwo im Footer-Bereich.

**SOLL** (JSX L185–200 — dedizierter Block in EmailPreview):
- Bg `#fbfaf6`, `border-bottom:1px solid #e6e1d3`
- Padding: 16px 28px 18px desktop / 14px 16px 16px mobile
- `_eyebrow("Antwort-Kommandos")`
- 3×2-Grid via `<table>` (3 Spalten, 2 Zeilen) desktop / 2×3-Grid mobile, marginTop 10px
- 6 Einträge: `PAUSE 2d · Briefings pausieren` / `SKIP · Nächstes überspringen` / `STOP · Dauerhaft deaktivieren` / `STATUS · Trip-Status abrufen` / `CONFIG · Spalten ändern` / `HELP · Alle Kommandos`
- Jeder Eintrag: CMD mono 11px fontWeight 700 `#1d1c1a` (minWidth 70px) + Beschreibung mono 10px `#9a978d`
- Hinweistext darunter: mono 10px, color `#b8b4a8`: "Antworte auf diese E-Mail mit einem Schlüsselwort."

## Sektion 8: Footer (zweigeteilt)

**IST:** Einzeilig, dunkles Bg, Text + Legende + Kommando-Block.

**SOLL** (JSX L201–212):
- Gesamter Footer: bg `#1d1c1a`, color `#9a978d`, fontSize 11px, mono
- Padding: 16px 28px 20px desktop / 14px 16px 18px mobile

**Obere Zeile** (JSX L203–207, via `<table>` space-between):
- Links: "GREGOR ZWANZIG" (color `#fff`, fontWeight 600, letterSpacing 0.06em) + " · " (color `#5a5750`) + Briefing-Typ
- Rechts (desktop only, `@media` auf mobile versteckt): "2026-05-06 05:01 UTC · openmeteo · icon_d2"

**Untere Zeile** (JSX L208–211, nach `border-top:1px solid #3a3835`, marginTop/paddingTop 8px):
- `<table>` mit Link-Zellen, gap 16px desktop / 10px mobile, fontSize 10px
- "Trip-Übersicht öffnen →" (color `#c45a2a`) | "Briefing-Zeitplan" (color `#9a978d`) | "Abmelden" (color `#9a978d`, textAlign right / marginLeft auto)
- Mobile: "Spalten ändern" entfällt
- Alle als Plain Text ohne `href` (PO-Entscheidung — keine Deep-Link-URLs vorhanden)

## Acceptance Criteria

**AC-1:** Given eine gerenderte Briefing-HTML-Mail, When der Header betrachtet wird, Then enthält er eine `<table>`-Zweispaltenstruktur (links: Eyebrow `MORGEN-BRIEFING · {CODE}` in mono `#c45a2a` + Titel + Datum; rechts: `GREGOR ZWANZIG` + Tripname + Etappennummer) mit Hintergrund `#fbfaf6`, und darunter ein Stats-Grid mit 5 Kennzahlen (Distanz, Aufstieg, Abstieg, Max-Höhe, Segmente) mit `border-right:1px solid #e6e1d3` als Trennlinie.

**AC-2:** Given eine gerenderte Briefing-Mail auf Mobile-Viewport (≤600px), When der Header betrachtet wird, Then zeigt das Stats-Grid 3 Spalten in Zeile 1 (Distanz · Aufstieg · Abstieg) und 2 Spalten in Zeile 2 (Max-Höhe · Segmente) ohne horizontalen Scroll.

**AC-3:** Given eine gerenderte Briefing-Mail (Desktop), When die Stundentabelle betrachtet wird, Then enthält der `<thead>` zwei Zeilen: (1) Gruppen-Row (9px mono uppercase, Temp/Wind/Niederschlag/Sicht·UV/Höhe mit colspan) und (2) Einheiten-Row (11px, fontWeight 600). Datenzellen haben padding 8px 4px, mono, tabular-nums. Trennlinien sind `1px solid #f0ece1`.

**AC-4:** Given eine gerenderte Briefing-Mail mit Stundenwert Wind=25 km/h (>20-Schwelle), When die Wind-Datenzelle betrachtet wird, Then ist sie `font-weight:700;color:#c2410c;`. Alle anderen nicht-kritischen Zellen sind `color:#1d1c1a;font-weight:500;`.

**AC-5:** Given eine gerenderte Briefing-Mail auf Mobile-Viewport, When die Stundentabelle betrachtet wird, Then erscheint eine zweizeilige Stunden-Liste (`_render_mobile_hour_list`): Hauptzeile (Zeit · Glyph · Temp · gefühlte Temp · Risk-Dot) und Detailzeile (Wind · Regen · ggf. Gewitter · Sicht · UV · 0°-Linie). Kritische Werte sind fett + farbig. Kein horizontaler Scroll.

**AC-6:** Given eine gerenderte Briefing-Mail mit Wetter-am-Ziel-Daten, When die Ziel-Sektion betrachtet wird, Then ist sie eine eigene abgesetzte Sektion mit bg `#fbfaf6`, `border-top:1px solid #e6e1d3`, accent-Eyebrow "ANKUNFT · WETTER AM ZIEL" (color `#c45a2a`), Zielname als Titel, und Datentabelle im gleichen Stil wie die Segment-Tabellen.

**AC-7:** Given eine gerenderte Briefing-Mail mit Folge-Etappen, When der Ausblick-Abschnitt betrachtet wird, Then zeigt jede Folge-Etappe eine `<tr>` mit Wochentag · Code · Name+Note · Temp · Risk-Dot. Der Risk-Dot ist ein `<span>` mit `border-radius:50%;width:10px;height:10px` und einer Farbe aus der Risk-Mapping-Tabelle. Etappen mit Gewitter-Warnung haben einen `⚡ Gewitter`-Badge in `#b91c1c`.

**AC-8:** Given eine gerenderte Briefing-Mail, When der Antwort-Kommandos-Abschnitt betrachtet wird, Then erscheint ein eigenständiger Block (Eyebrow "Antwort-Kommandos") mit einem 3×2-Grid der Kommandos PAUSE 2d · SKIP · STOP · STATUS · CONFIG · HELP (je CMD in mono bold + Beschreibung in `#9a978d`) und dem Hinweistext "Antworte auf diese E-Mail mit einem Schlüsselwort." Hintergrund `#fbfaf6`.

**AC-9:** Given eine gerenderte Briefing-Mail, When der Footer betrachtet wird, Then ist er zweigeteilt: Obere Zeile (links: "GREGOR ZWANZIG" in `#fff` + Briefing-Typ; rechts desktop-only: Datum+Provider) getrennt durch `border-top:1px solid #3a3835` von einer Link-Zeile ("Trip-Übersicht öffnen →" in `#c45a2a` · "Briefing-Zeitplan" · "Abmelden"). Hintergrund `#1d1c1a`.

**AC-10:** Given die Mode-Matrix-Tests nach allen Renderer-Änderungen, When `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` läuft, Then sind alle Kombinationen ({full,compact} × {Einfach,Roh} × {briefing,alert}) grün (Exit 0). Kein Colspan-Mismatch, kein Rendering-Crash, keine fehlenden Pflichtfelder.

## Was sich NICHT ändert

- Kein neues Datenmodell-Feld (`thunder_sq_color` aus `format_trend_tokens()` reicht für Risk-Dot)
- Keine Änderung an API-Schnittstellen (`/api/briefing`, `src/outputs/email.py`)
- Stirnlampe bleibt entfernt (PO-Entscheidung aus #790)
- Tages-Summe wird nicht eingebaut (wurde aus aktuellem Cloud-Design entfernt)
- `EmailMetricsSummary` wird nicht implementiert (JSX-only Opt-In, Briefing zeigt immer Quick-Take-Text)
- Signal als Kanal bleibt entfernt (Issue #610)
- Footer-Links bleiben Plain Text ohne `href` (keine Deep-Link-URLs vorhanden)

## Known Limitations

- Outlook ignoriert `@media (max-width:600px)` → Stats-Grid zeigt in Outlook immer 5 Spalten; akzeptiertes Verhalten
- Colspan-Berechnung in Sektion 4 ist dynamisch; bei komplett deaktivierter `display_config` leerer Header — bestehende Einschränkung, kein neues Risiko
- Risk-Dot basiert auf `thunder_sq_color`; bei Etappen ohne Gewitterdaten erscheint neutraler Kreis `#c8c4b8`

## Test Coverage

Tests in `tests/tdd/test_issue_884_mail_fidelity.py` (alle gegen echten Staging-Endpoint, kein Mock):

- `test_header_two_column_table_structure` — HTTP GET `/api/preview/{trip_id}` Staging; prüft 2-spaltige `<table>` im Header, `#fbfaf6`, 5 Stat-Zellen
- `test_header_mobile_3col_stats_grid` — gleicher Endpoint mit User-Agent Mobile; prüft 3-Spalten-Stats in `@media`-Block
- `test_table_two_level_header_present` — Preview-Endpoint; prüft Gruppen-Row (colspan, Temp/Wind/Niederschlag) + Einheiten-Row
- `test_wind_highlighting_above_threshold` — Preview-Endpoint mit synthetischem Trip (Wind=25); Response-HTML enthält `font-weight:700;color:#c2410c`
- `test_mobile_hour_list_two_rows_per_hour` — Preview-Endpoint Mobile; prüft zwei-Zeilen-Format, kein `<table>` für Stundendaten
- `test_destination_weather_own_section` — Preview-Endpoint; prüft "ANKUNFT · WETTER AM ZIEL" Eyebrow, `#fbfaf6` bg, eigene Sektion
- `test_upcoming_rows_riskdot_and_thunder_badge` — Preview-Endpoint; prüft `border-radius:50%` im Risk-Dot, `⚡ Gewitter` Badge bei Thunder-Etappen
- `test_kommandos_section_present` — Preview-Endpoint; prüft Eyebrow "Antwort-Kommandos", alle 6 CMD-Labels, Hinweistext
- `test_footer_two_sections_brand_and_links` — Preview-Endpoint; prüft "GREGOR ZWANZIG", `border-top:1px solid #3a3835`, Link-Labels
- `test_mode_matrix_no_regression` — `uv run pytest tests/tdd/test_issue_811_mode_matrix.py`; Exit 0
- `test_briefing_mail_validator_exits_zero` — `briefing_mail_validator.py` gegen echte Staging-Mail; Exit 0

## Changelog

- 2026-06-25: v1.0 initial — 3 Sektionen (unvollständig)
- 2026-06-25: v2.0 — alle 7 Sektionen (inkl. Tages-Summe aus altem Design)
- 2026-06-25: v3.0 — Tages-Summe entfernt (nicht im aktuellen Cloud-Design), Antwort-Kommandos als eigene Sektion, EmailHourList für Mobile, JSX-as-source Implementierungsansatz
