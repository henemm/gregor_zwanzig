---
entity_id: issue_898_901_mail_layout
type: bugfix
created: 2026-06-28
updated: 2026-06-28
status: draft
workflow: fix-898-899-900-mail-layout
---

# HTML-Briefing-Mail: Layout-Bugs #898/#899/#900/#901

## Approval

- [x] Approved (PO, 2026-06-28)

## Purpose

Behebt vier gebündelte Layout-Defekte in der HTML-Briefing-E-Mail: fehlende Tabellen-Spaltenlinien (#900), Platzverschwendung und Styling-Inkonsistenzen in der Head-Sektion (#898), strukturelle Überarbeitung des 3-Tage-Trend-Abschnitts (#899) und Bereinigung von Footer-Links sowie Stats-Grid (#901). Alle vier Issues betreffen primär denselben Renderer `html.py` und werden im selben Workflow gebündelt.

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `render_html`, `_render_html_table`, `_render_footer`

## Estimated Scope

- **LoC:** ~+80 / -25 (Netto ca. +55)
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/helpers.py` | module | `pill_html`, `build_metrics_summary_pills`, `build_confidence_hint` — nur Lesezugriff, keine Änderung |
| `src/output/renderers/email/design_tokens.py` | module | Farb-Token `G_INK_FAINT` etc. — nur Lesezugriff |
| `src/output/renderers/email/__init__.py` | module | `render_email()` — erhält neuen optionalen Parameter `trip_url` (#901) |
| `src/formatters/trip_report.py` | module | `format_email()` — erhält neuen optionalen Parameter `trip_url` (#901) |
| `src/services/trip_report_scheduler.py` | service | Konstruiert `trip_url` aus `trip.id` und übergibt ihn (#901) |
| `src/formatters/compact_summary.py` | module | Erzeugt `compact_summary` mit Etappenname-Prefix — bleibt unverändert |
| `tests/tdd/test_issue_811_mode_matrix.py` | test | Muss nach Renderer-Änderungen grün bleiben (Mail-Renderer-Commit-Gate) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/html.py` | MODIFY | Alle vier Issues: vollständiges Tabellen-Gitter (Zeilen+Spalten+Header), Head-Sektion (Einzug, Schriftgröße, Prefix-Strip, Dreieck-Headline), Trend-Umbau (Labels weg, Chip-Format, Genauigkeits-Indikator pro Tag), Footer (Abmelden weg, Deep-Links, Segmente-Zelle ausrichten) |
| `src/output/renderers/email/__init__.py` | MODIFY | `trip_url: Optional[str] = None` als optionalen Parameter zu `render_email()` hinzufügen und an `render_html()` weiterreichen |
| `src/formatters/trip_report.py` | MODIFY | `trip_url: Optional[str] = None` zu `format_email()` hinzufügen |
| `src/services/trip_report_scheduler.py` | MODIFY | `trip_url=f"https://gregor20.henemm.com/trips/{trip.id}"` konstruieren und übergeben |

### Estimated Changes

- Files: 4
- LoC: +80 / -25

## Implementation Details

### #900 — Tabellen-Gitterlinien (Zeilen UND Spalten)

Der User bemängelt, dass die Stundentabelle **weder klare Zeilen- noch Spalten-Linien** hat („Es fehlen Zeilen- und Spalten-Linien/Kennzeichnung") — im Screenshot ist nur die Zeit-Spalte unterstrichen, sonst kein sichtbares Gitter. Ziel: ein **vollständiges, sichtbares Gitter** wie in der Vorlage.

In `_render_html_table()` (Z. 435–529):
- **Vertikale Linien (Spalten):** Jedes `<td>` und jedes `<th>` erhält `border-right:1px solid #e6e1d3`. Die letzte Spalte (Risk-Dot) bekommt kein `border-right`.
- **Horizontale Linien (Zeilen):** Jede Datenzeile erhält eine sichtbare `border-bottom:1px solid #e6e1d3` auf den `<td>` (aktuell nur via CSS `td { border-bottom }`, das in manchen Clients/Inline-Kontexten nicht greift → inline absichern).
- **Header-Kennzeichnung:** Die `<th>`-Kopfzeile bekommt einen sichtbaren Hintergrund (`background:{G_SURFACE_1}`) inline, damit die Spaltenüberschriften klar abgesetzt sind (Outlook/Clients ignorieren das CSS `th { background }` teils).

Im globalen `<style>`-Block (Z. 1220–1222) wird zusätzlich `td, th { border-right: 1px solid {G_INK_FAINT}; }` ergänzt (mit `:last-child { border-right: none }` für die Risk-Dot-Spalte), als Fallback für Clients die Inline-Styles bevorzugen. Ergebnis: durchgehendes Gitter aus horizontalen + vertikalen Linien plus gekennzeichneter Header.

### #898 — Head-Sektion (4 Punkte)

**Punkt 1 — Linker Einzug:** Der outer Div der Tageslage-Sektion hat `padding:18px 28px 16px`. Darin liegt ein inner Div mit `border-left:2px solid + padding-left:14px`, was einen Doppel-Einzug (28px + 16px = 44px) ergibt. Fix: Outer-Padding auf `padding:18px 28px 16px 12px` reduzieren, sodass `12 + 2 + 14 = 28px` bündig mit dem restlichen Header ausgerichtet ist.

**Punkt 2 — Schriftgröße:** `_vortag_div` hat `font-size:12.5px`. `_summary_div` hat `font-size:16px`. Beide vereinheitlichen auf `font-size:16px`.

**Punkt 3 — Etappenname-Prefix entfernen:** `compact_summary.py` erzeugt `f"{short_name}: {weather}"`. Im Renderer, direkt vor der Anzeige, den Prefix entfernen:
```python
_sn_prefix = shorten_stage_name(stage_name or "", max_len=40) + ": "
_display_summary = compact_summary or ""
if _display_summary and stage_name and _display_summary.startswith(_sn_prefix):
    _display_summary = _display_summary[len(_sn_prefix):]
```
`shorten_stage_name` ist bereits in `html.py` importiert. `compact_summary.py` bleibt unverändert.

**Punkt 4 — Dreieck als Headline-Teil:** `_vortag_div` aktuell rendert Trend-Glyph (`▲`/`▼`/`▬`) inline im Fließtext. Neues Muster: `_eyebrow`-Headline `▲ VORTAGESVERGLEICH` (mit Glyph als Teil des Labels), darunter nur der Vergleichstext — identisch zum TAGESLAGE-Pattern.

### #899 — 3-Tage-Trend (6 Punkte)

1. `"3-Tage-Trend<br>"` in `context_label_html` (Z. 1044–1057) entfernen.
2. `_eyebrow("Ausblick · nächste 4 Tage")` (Z. 1065) entfernen.
3. + 4. Trend-Loop (Z. 948–1073): `trend_rows`-Tabelle durch Chip-Reihen ersetzen. Pro Tag eine Zeile mit `pill_html`-basierten Chips: Wochentag-Label + Temp + Gewitter-Badge wenn vorhanden. `width:100%` für volle Spaltenbreite.
5. `name`-Spalte aus dem Trend-Loop entfernen (`stage.get("name", "")` und `code_html` nicht mehr rendern).
6. **Genauigkeits-Indikator (Vorhersage-Verlässlichkeit) — PRO TAG durchgängig:** Der User fragt „wo ist der Genauigkeitstrend hin?" und stellt klar: der Indikator gehört zur **3-Tages-Prognose** und zeigt für **jeden Tag** der Vorschau an, **wie stark die Vorhersage-Modelle auseinanderlaufen** (Ensemble-Divergenz = `confidence_pct`), damit der Nutzer einschätzen kann, wie sicher die Prognose ist. „ähnlich wie der Hinweis für Gewitter (Kreis)" → ein **kompaktes Kreis-Symbol pro Trend-Zeile**, das die Verlässlichkeit visualisiert (nicht nur ein Warnsymbol bei niedriger Sicherheit).

   - Datenquelle: `stage.get("confidence_pct")` (bereits pro Trend-Dict vorhanden, Z. 1070 Scheduler).
   - **Darstellung: bestehenden `_risk_dot()`-Indikator wiederverwenden** (PO-Vorgabe „Verwende die bereits verwendeten Indikatoren!!!") — derselbe gefüllte Kreis mit Ring, den der Trend-Abschnitt bereits rechts nutzt (das ist der vom User gemeinte „Hinweis-Kreis"). Keine neuen Symbole (kein ●/◐/○). Dreistufig über die **bereits definierten Farben** aus `_RISK_DOT_COLORS`:
     - **hoch** (`>= 80`): `#15803d` (grün, = „ok"-Farbe)
     - **mittel** (`60–79`): `#c2410c` (orange, = „watch"-Farbe)
     - **niedrig** (`< 60`): `#b91c1c` (rot, = „risk"-Farbe)
   - Aufruf: `_risk_dot(color)` mit der je Stufe abgeleiteten Farbe. Die Farben sind exakt die drei, die `_risk_dot` bereits in seiner `ring_map` kennt — keine Erweiterung nötig.
   - Position: in der Trend-Chip-Zeile, klar unterscheidbar vom bestehenden Wetter-Risk-Dot (eigene Position/eigenes Mikrolabel „Prognose", damit nicht mit dem Wetter-Risiko-Punkt verwechselt). Beide nutzen denselben visuellen Baustein, tragen aber unterschiedliche Bedeutung — das ist beabsichtigte Konsistenz.
   - Fehlt `confidence_pct` (None) → kein Indikator (fail-soft).
   - Stufen-/Farb-Ableitung als kleiner lokaler Helper in `html.py` (z.B. `_confidence_dot_color(pct)`), der eine der drei `_RISK_DOT_COLORS`-Farben zurückgibt.
   - **#710-konform:** reiner Verlässlichkeits-Hinweis im E-Mail-Trend, keine wählbare Metrik, keine Wetterwert-Spalte. Siehe Known Limitations.

### #901 — Footer & Stats-Grid (3 Punkte)

1. `Abmelden`-Span aus `link_row` (Z. 408) entfernen.
2. Deep-Links: `render_html()` erhält neuen optionalen Parameter `trip_url: Optional[str] = None`. `_render_footer()` erhält ihn weiter. Bei gesetztem `trip_url`:
   - `Trip-Übersicht öffnen →` → `<a href="{trip_url}">Trip-Übersicht öffnen →</a>`
   - `Briefing-Zeitplan` → `<a href="{trip_url}/edit">Briefing-Zeitplan</a>`
   Ohne `trip_url` (None): Spans wie bisher — keine Änderung an bestehendem Render-Output, bestehende Tests bleiben deterministisch.
3. **„Segmente" in horizontale Flucht bringen (Alignment-Fix, NICHT entfernen):** Im Screenshot ist die letzte Stat-Zelle „SEGMENTE / 6" gegenüber den anderen Stat-Zellen (DISTANZ, AUFSTIEG, ABSTIEG, MAX HÖHE) vertikal nach unten verrutscht — Label und Wert sitzen nicht auf derselben Baseline. Ursache liegt in `_render_email_stat()` (Z. 145–158) bzw. der Stats-Grid-Tabelle (Z. 715–719): die SEGMENTE-Zelle hat `unit=""` (keine Einheit), wodurch die vertikale Ausrichtung gegenüber den Zellen mit Einheit kippt. Fix: einheitliche vertikale Ausrichtung aller Stat-Zellen sicherstellen (z.B. konsistentes `vertical-align:top` greift bereits — echte Ursache per Render diagnostizieren; mögliche Fixes: leeren `unit`-Span trotzdem rendern, feste Zeilenhöhe, oder Baseline-Alignment). **Die Zelle bleibt erhalten** — der Wert „Segmente" wird nur korrekt ausgerichtet.

Die URL-Kette für die Deep-Links: `trip_report_scheduler.py` → `trip_report.py format_email()` → `__init__.py render_email()` → `html.py render_html()` → `_render_footer()`.

## Test Plan

### Automated Tests (TDD RED)

Tests rufen `render_html()` direkt mit Fixture-Segment-Daten auf und prüfen das gerenderte HTML-Output strukturell (BeautifulSoup oder Regex auf HTML-String) — kein Dateiinhalt-Check, keine Mocks.

- [ ] **Test AC-1 (#900 Gitterlinien):** `render_html()` mit Stundentabellen-Daten aufrufen → gerendertes HTML hat sowohl vertikale (`border-right` auf `<td>`/`<th>`, außer letzter Spalte) als auch horizontale Linien (`border-bottom` auf Datenzeilen) UND einen gekennzeichneten Header (`<th>` mit Hintergrundfarbe)
- [ ] **Test AC-2 (#898 Einzug):** `render_html()` mit Tageslage-Daten → Outer-Div der Tageslage-Sektion hat `padding-left` kleiner als 28px (kein Doppel-Einzug)
- [ ] **Test AC-3 (#898 Schriftgröße):** `render_html()` → Summary-Div und Vortagesvergleich-Div haben identische `font-size`
- [ ] **Test AC-4 (#898 Prefix-Strip):** `render_html()` mit `compact_summary="Etappe 10: KHW_08: Sonnig"` und passendem `stage_name` → gerendertes HTML enthält NICHT den Stage-Name-Prefix vor dem Wettertext
- [ ] **Test AC-5 (#898 Dreieck):** `render_html()` mit Vortagesvergleich-Daten → Trend-Glyph (`▲`/`▼`) erscheint im Eyebrow-Headline-Element, nicht im Fließtext-Absatz
- [ ] **Test AC-6 (#899 Labels entfernt):** `render_html()` → gerendertes HTML enthält nicht den String `3-Tage-Trend` und nicht `Ausblick · nächste 4 Tage`
- [ ] **Test AC-7 (#899 Chip-Format):** `render_html()` mit Trend-Daten → Trend-Abschnitt enthält `pill_html`-Spans (erkennbar an der CSS-Klasse oder Inline-Style), keine `<table>`-Zeilen
- [ ] **Test AC-8 (#899 Kein Etappenname in Trend):** `render_html()` mit Trend-Daten die `name`-Felder enthalten → Trend-Abschnitt enthält keine Stage-Namen in den Chip-Zeilen
- [ ] **Test AC-9 (#899 Genauigkeits-Indikator pro Tag):** `render_html()` mit drei Trend-Einträgen `confidence_pct=85/70/45` → jede der drei Trend-Zeilen enthält einen `_risk_dot`-Kreis (border-radius:50%) in der erwarteten Farbe (`#15803d` / `#c2410c` / `#b91c1c`); ein Eintrag ohne `confidence_pct` (None) → kein Genauigkeits-Indikator in dieser Zeile
- [ ] **Test AC-10 (#901 Abmelden):** `render_html()` → gerendertes HTML enthält nicht das Wort `Abmelden`
- [ ] **Test AC-11 (#901 Deep-Links gesetzt):** `render_html(..., trip_url="https://gregor20.henemm.com/trips/test-123")` → Footer enthält `<a href="https://gregor20.henemm.com/trips/test-123">` und `<a href="https://gregor20.henemm.com/trips/test-123/edit">`
- [ ] **Test AC-12 (#901 Deep-Links nicht gesetzt):** `render_html(..., trip_url=None)` → Footer enthält keinen `<a href>`-Tag für Trip-Übersicht (Backward-Compatibility)
- [ ] **Test AC-13 (#901 Segmente-Ausrichtung):** `render_html()` mit Stage-Stats → die `Segmente`-Zelle ist weiterhin vorhanden UND vertikal in derselben Flucht wie die anderen Stat-Zellen (gleiche Struktur/Baseline: Label-Div + Value-Div, identisches `vertical-align` und konsistenter Aufbau wie die Zellen mit Einheit)

## Acceptance Criteria

**AC-1:** Given eine HTML-Briefing-Mail wird gerendert / When die Stundentabelle im Output betrachtet wird / Then hat die Tabelle ein vollständiges, sichtbares Gitter — vertikale Spaltenlinien (`border-right` auf Zellen außer der letzten) UND horizontale Zeilenlinien (`border-bottom` auf Datenzeilen) — sowie einen optisch gekennzeichneten Header (Kopfzeile mit Hintergrundfarbe), so wie in der Vorlage

**AC-2:** Given eine HTML-Briefing-Mail wird gerendert / When der Tageslage-Block im Output betrachtet wird / Then ist der linke Einzug des Tageslage-Textes bündig mit dem restlichen Mail-Header (kein Doppel-Einzug durch gestapeltes padding + border-left)

**AC-3:** Given eine HTML-Briefing-Mail mit Wetterzusammenfassung und Vortagesvergleich / When das gerenderte HTML analysiert wird / Then haben Wetterzusammenfassungs-Text und Vortagesvergleich-Text identische Schriftgröße

**AC-4:** Given `compact_summary` enthält den Etappenname als Prefix (z.B. `"KHW_08: Sonnig, 24°C"`) / When die HTML-Mail gerendert wird / Then erscheint der Stage-Name-Prefix NICHT im angezeigten Wettertext der Mail (nur der Wetterteil wird dargestellt)

**AC-5:** Given eine HTML-Briefing-Mail mit Vortagesvergleich-Daten (positiver/negativer Trend) / When der Head-Bereich der Mail betrachtet wird / Then ist das Trend-Dreieck (▲/▼) Teil der Abschnitts-Headline im Eyebrow-Stil, nicht als Inline-Zeichen im Fließtext

**AC-6:** Given eine HTML-Briefing-Mail wird gerendert / When der Trend-Abschnitt betrachtet wird / Then enthält die Mail weder den Text `3-Tage-Trend` noch `Ausblick · nächste 4 Tage` als Label

**AC-7:** Given eine HTML-Briefing-Mail mit mehrtägigen Trend-Daten / When der Trend-Abschnitt im gerenderten HTML betrachtet wird / Then sind die Trend-Tage als Chip-Zeilen (pill_html-basierte Spans) dargestellt, nicht als HTML-Tabelle mit Zeilen

**AC-8:** Given eine HTML-Briefing-Mail mit Trend-Daten die Stage-Namen enthalten / When der Trend-Abschnitt betrachtet wird / Then erscheinen keine Stage-Namen in den Trend-Chip-Zeilen

**AC-9:** Given eine HTML-Briefing-Mail mit mehrtägiger Trend-Prognose, bei der jeder Tag ein `confidence_pct` trägt / When der Trend-Abschnitt betrachtet wird / Then erscheint pro Tag ein durchgängiger Genauigkeits-Indikator, der den **bestehenden `_risk_dot()`-Kreis** wiederverwendet (keine neuen Symbole), dreistufig über die vorhandenen Farben (hoch ≥80 → grün, mittel 60–79 → orange, niedrig <60 → rot) — sichtbar für ALLE Tage, nicht nur bei niedriger Sicherheit; fehlt `confidence_pct` für einen Tag, bleibt dieser Indikator weg (fail-soft)

**AC-10:** Given eine HTML-Briefing-Mail wird gerendert / When der Footer betrachtet wird / Then enthält der Footer keinen `Abmelden`-Link oder -Text

**AC-11:** Given `render_html()` wird mit `trip_url="https://gregor20.henemm.com/trips/abc-123"` aufgerufen / When der Footer gerendert wird / Then enthalten `Trip-Übersicht öffnen →` und `Briefing-Zeitplan` echte `<a href>`-Links auf die Trip-URL bzw. Trip-URL + `/edit`

**AC-12:** Given `render_html()` wird ohne `trip_url` (None) aufgerufen / When der Footer gerendert wird / Then werden `Trip-Übersicht` und `Briefing-Zeitplan` als einfacher Text gerendert (keine `<a href>`-Tags) — bestehende Tests bleiben deterministisch

**AC-13:** Given eine HTML-Briefing-Mail mit Stage-Stats wird gerendert / When das Stats-Grid im Header betrachtet wird / Then ist die `Segmente`-Zelle weiterhin vorhanden und vertikal in derselben horizontalen Flucht (gleiche Baseline für Label und Wert) wie die übrigen Stat-Zellen — sie ist nicht mehr nach unten verrutscht

## Known Limitations

- **Mail-Renderer-Commit-Gate (un-überspringbar):** Jeder Commit der `src/output/renderers/email/*.py` oder `src/formatters/*.py` staged, wird vom `renderer_mail_gate.py`-Hook blockiert bis (1) `tests/tdd/test_issue_811_mode_matrix.py` grün ist und (2) `briefing_mail_validator.py` gegen eine echte Staging-Mail bestanden hat. Beide Nachweise sind an sha256/`validated_at` gebunden — nach jeder Renderer-Änderung müssen sie neu erbracht werden.
- **Backward-Compatibility `trip_url`:** Der Parameter ist optional (Default `None`). Ohne ihn bleibt der Footer-Output identisch zum bisherigen Stand, sodass bestehende Render-Tests ohne Anpassung weiter laufen.
- **`confidence_hint_html`-Box bleibt:** Die bestehende Warning-Box im Mail-Body (Z. 1159–1164) bleibt unangetastet. Der neue Konfidenz-Badge im Trend-Abschnitt ist ein zusätzlicher, kompakter Indikator in anderem Kontext — keine Dopplung, sondern Komplementierung.
- **`compact_summary.py` bleibt unverändert:** Der Prefix-Strip findet nur im Renderer statt — keine Änderung am Erzeuger. Das stellt sicher, dass SMS- und andere Kanäle weiterhin den vollständigen String erhalten.
- **#710-Compliance (Confidence):** Der Konfidenz-Badge (#899 Punkt 6) ist ein **Vorhersage-Verlässlichkeits-Hinweis** im E-Mail-Trend-Abschnitt — exakt der laut Issue #710 erlaubte Anzeige-Pfad (Kategorie 1: Verlässlichkeits-Hinweis). Er ist KEINE wählbare Metrik, keine per-Etappe-Wetterspalte und erscheint NICHT im Trip-Editor/Wizard/Metrik-Auswahl. `confidence` bleibt `selectable=false`. Damit ist der Badge regelkonform und stellt keinen Regress zu #710/#473 dar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Layout-Korrekturen und optionale Parameterergänzung ohne Richtungsentscheidung für die Systemarchitektur. Kein neues Muster eingeführt, alle Änderungen folgen etablierten Konventionen des Renderers (`pill_html`, `_eyebrow`, `thunder_badge`-Pattern).

## Changelog

- 2026-06-28: Initial spec created (Issues #898, #899, #900, #901 gebündelt)
- 2026-06-28: Korrektur nach Screenshot-Review (PO-Feedback): #900 = vollständiges Gitter (Zeilen+Spalten+Header-Kennzeichnung) statt nur Spaltenlinien; #899.6 = Genauigkeits-Indikator pro Tag der 3-Tages-Prognose (durchgängig) statt nur Warnbadge bei <60; #901.3 = Segmente-Zelle AUSRICHTEN statt entfernen
