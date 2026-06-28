# Context: fix-898-899-900-mail-layout

## Request Summary
Vier Layout-Bugs in der HTML-Briefing-E-Mail (gebündelt): Tabellen-Linien fehlen (#900),
Head-Sektion hat Platzverschwendung und falsches Styling (#898), 3-Tage-Trend-Abschnitt
soll komplett umstrukturiert werden (#899), Footer-Links und Stats-Grid bereinigen (#901).

## Betroffene Dateien
| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/email/html.py` | Haupt-Renderer — alle vier Issues zentral hier |
| `src/output/renderers/email/helpers.py` | `build_confidence_hint`, `pill_html`, `build_metrics_summary_pills` (nur Lesen) |
| `src/output/renderers/email/design_tokens.py` | G_INK_FAINT etc. (Lesezugriff, keine Änderung) |
| `src/formatters/compact_summary.py` | Erzeugt `compact_summary` mit Etappenname-Prefix (`"{short_name}: {weather}"`) — NICHT geändert |
| `src/output/renderers/email/__init__.py` | `trip_url` weiterreichen (#901) |
| `src/formatters/trip_report.py` | `trip_url` zu `format_email()` hinzufügen (#901) |
| `src/services/trip_report_scheduler.py` | `trip_url` konstruieren und übergeben (#901) |

## Bestehende Muster
- **pill_html**: Inline `<span>` mit Border/Background je Ampelstufe (Datei helpers.py Z. 902)
- **_eyebrow**: Kleines Uppercase-Label-Element (html.py Z. 89)
- **_risk_dot**: Gefüllter SVG/Span-Kreis-Indikator (html.py Z. 98)
- **thunder_badge**: Roter Badge mit ⚡ für Gewitter-Warnung (html.py Z. 981-986)
- **build_confidence_hint**: Gibt Plaintext zurück wenn confidence_pct < 60 (helpers.py Z. 300)
- **CSS-Tabellen-Stile**: `th { border-bottom }`, `td { border-bottom }` — nur horizontale Linien

## Issue-Details

### #900 — Tabellen-Linien fehlen
- `_render_html_table` erzeugt `<table class="resp">` mit CSS-only-Styling
- CSS-`td` hat `border-bottom` aber KEIN `border-right` → keine Spaltenlinien sichtbar
- CSS-`th` hat nur `border-bottom` → kein vollständiges Gitter
- **Fix:** Inline `border-right` auf `<td>` in `_render_html_table` und globales `td { border-right }` im `<style>`-Block ergänzen

### #898 — Head-Sektion (4 Punkte)
1. **Platzverschwendung links**: Tageslage-Sektion hat `padding:18px 28px 16px` + innere Div mit `border-left:2px solid + padding-left:14px` → Doppel-Einzug. Padding on outer div angleichen.
2. **Schriftgröße Vortagesvergleich**: `_vortag_div` hat `font-size:12.5px`, `_summary_div` hat `font-size:16px`. Beide auf gleiche Größe bringen.
3. **Etappenname in compact_summary**: `compact_summary.py` erzeugt `f"{short_name}: {weather}"`. Im HTML-Renderer diesen Prefix vor dem Anzeigen entfernen. Einfachste Lösung: im Renderer `compact_summary.split(': ', 1)[1]` wenn der String mit dem stage_name beginnt.
4. **Dreieck als Headline-Teil**: Aktuell ist der Trend-Glyph (`▲`/`▼`/`▬`) inline im Fließtext `_vortag_div`. Der User will denselben `_eyebrow`-+Glyph-in-Headline-Pattern wie bei TAGESLAGE.

### #899 — 3-Tage-Trend (6 Punkte)
1. **"3-Tage-Trend" entfernen**: Label in `context_label_html` (html.py Z. 1054) — entfernen
2. **"NÄCHSTE 4 TAGE" entfernen**: `_eyebrow("Ausblick · nächste 4 Tage")` (Z. 1065) — entfernen
3. **SMS-Chip-Format**: Statt Tabelle mit Zeilen → pro Tag ein Chip-Block ähnlich Metriken-Überblick (pill_html/tone-basiert). Inhalt: Wochentag + Temp + Gewitter-Badge wenn vorhanden.
4. **Volle Spaltenbreite**: Chips sollen volle Breite nutzen (`width:100%`)
5. **Kein Etappenname**: Aktuell enthält die Trend-Tabelle eine Name-Spalte (`name`). Diese entfernen.
6. **Genauigkeitstrend-Indikator**: `build_confidence_hint` gibt Plaintext zurück, aktuell als Warning-Box (confidence_hint_html). Stattdessen: kompakter Kreis-Indikator im Trend-Abschnitt, ähnlich dem thunder_badge-Pattern (kleiner farbiger Span, kein separater Block).

## Abhängigkeiten
- **Upstream**: `services/trip_report_scheduler.py` übergibt `compact_summary`, `multi_day_trend`, `day_comparison` an den Renderer
- **Downstream**: Mail-Renderer-Commit-Gate (`renderer_mail_gate.py`) prüft nach Mail-Änderungen
- **Tests**: `tests/tdd/test_issue_811_mode_matrix.py` muss nach Renderer-Änderungen grün bleiben

## Analysis

### Type
Bug (3 gebündelte Layout-Bugs in derselben Mail-Renderer-Datei)

### Betroffene Dateien

| Datei | Change-Type | Beschreibung |
|-------|-------------|-------------|
| `src/output/renderers/email/html.py` | MODIFY | Alle vier Issues: Tabellen-Borders, Head-Sektion, Trend-Umbau, Footer/Stats |
| `src/output/renderers/email/__init__.py` | MODIFY | `trip_url` als optionaler Parameter weiterreichen |
| `src/formatters/trip_report.py` | MODIFY | `trip_url` zu `format_email()` hinzufügen |
| `src/services/trip_report_scheduler.py` | MODIFY | `trip_url` konstruieren und übergeben |

`helpers.py` und `compact_summary.py` bleiben unverändert.

### Scope-Schätzung
- **Dateien:** 4
- **LoC:** ~+80 / -25 (Netto ca. +55)
- **Risiko:** MITTEL — Mail-Renderer-Commit-Gate blockiert Commit bis Matrix-Test + Staging-Validator grün

### Technischer Ansatz je Issue

#### #900 — Tabellen-Linien
In `_render_html_table()` (Z. 470-521): `border-right:1px solid #e6e1d3` als Inline-Style auf jede `<td>`, außer der letzten Risk-Dot-Spalte. Im `<style>`-Block (Z. 1222) zusätzlich `td { border-right: 1px solid {G_INK_FAINT}; }` ergänzen.

#### #898 — Head-Sektion

**Punkt 1 (linker Einzug):** `tageslage_html`-Outer-Div hat `padding:18px 28px 16px`. Dazu kommen `border-left:2px + padding-left:14px` im Inner-Div → Text startet bei 42px, Header bei 28px. Fix: Outer-Padding auf `padding:18px 28px 16px 12px` reduzieren, so dass 12+2+14=28px match.

**Punkt 2 (Schriftgröße):** `_vortag_div` `font-size:12.5px` → `font-size:16px` (gleich wie `_summary_div`).

**Punkt 3 (Etappenname entfernen):** `shorten_stage_name` ist bereits in html.py importiert. Nutze es mit `max_len=40` (identische Logik wie compact_summary.py):
```python
_sn_prefix = shorten_stage_name(stage_name or "", max_len=40) + ": "
_display_summary = compact_summary or ""
if _display_summary and stage_name and _display_summary.startswith(_sn_prefix):
    _display_summary = _display_summary[len(_sn_prefix):]
elif _display_summary and stage_name and ": " not in _display_summary:
    _display_summary = ""  # nur Stage-Name, kein Wetter
```

**Punkt 4 (Dreieck in Headline):** `_vortag_div` neu strukturieren: Statt `VS. GESTERN ▲ text` → `_eyebrow`-ähnliche Headline `▲ VORTAGESVERGLEICH` + darunter nur der Vergleichstext. Baut denselben Muster wie TAGESLAGE auf.

#### #899 — 3-Tage-Trend

1. `context_label_html` (Z. 1044-1057): `"3-Tage-Trend<br>"` entfernen
2. `_eyebrow("Ausblick · nächste 4 Tage")` (Z. 1065): entfernen
3+4. Trend-Loop (Z. 948-1073): `trend_rows`-Tabelle durch Chip-Reihen ersetzen. Pro Tag eine Zeile mit `pill_html`-basierten Chips: Wochentag-Label + Temp + Gewitter-Badge (wenn vorhanden) + Konfidenz-Indikator
5. `name`-Spalte aus Trend-Loop entfernen (`stage.get("name", "")` und `code_html` nicht mehr rendern)
6. Genauigkeitstrend: `stage.get("confidence_pct")` ist bereits in jedem Trend-Dict (Z. 1070 Scheduler). Bei `< 60` → kleiner Badge analog thunder_badge: `⊙ unsicher`. Keine Änderung an helpers.py nötig.

#### #901 — Footer & Stats-Grid

1. `link_row` (Z. 408): `Abmelden`-Span entfernen
2. Deep-Links: `trip_url: Optional[str] = None` neu an `render_html()` + `_render_footer()` hängen. Aufrufer `render_email()` in `__init__.py` weiterreichen; `TripReportFormatter.format_email()` in `trip_report.py` erhält `trip_url=...`; Scheduler baut die URL aus `trip.id`. `_render_footer` rendert `<a href="{trip_url}">Trip-Übersicht öffnen →</a>` und `<a href="{trip_url}/edit">Briefing-Zeitplan</a>`. Ohne `trip_url` bleiben Spans wie bisher (Tests bleiben deterministisch).
3. Stats-Grid: `stat_cells.append(("Segmente", ...))` (Z. 709) entfernen.

**Betroffene Dateien für #901 (zusätzlich zu html.py):**
- `src/formatters/trip_report.py` — `trip_url` zu `format_email()` hinzufügen, URL bauen
- `src/output/renderers/email/__init__.py` — `trip_url` weiterreichen
- `src/services/trip_report_scheduler.py` — `trip_url=f"https://gregor20.henemm.com/trips/{trip.id}"` übergeben

### Abhängigkeiten

- **Upstream:** `trip_report_scheduler.py` erzeugt `multi_day_trend` (inkl. `confidence_pct`), `compact_summary`; für #901 zusätzlich `trip_url` konstruieren und übergeben
- **Gate:** `renderer_mail_gate.py` blockiert Commit bis `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py` gegen Staging-Mail bestanden
- **Tests grün halten:** `test_issue_811_mode_matrix.py` (Matrix-Nachweis), weitere Render-Tests (kein Golden-Test der hart auf Trend-HTML prüft wurde gefunden)

### Offene Fragen
- keine — alle Punkte klar spezifiziert in den Issues

## Risiken & Hinweise
- Mail-Renderer-Commit-Gate aktiv — nach Änderungen MUSS `test_issue_811_mode_matrix.py` laufen und `briefing_mail_validator.py` gegen echte Staging-Mail bestanden werden
- Compact-Summary-Prefix-Stripping: `shorten_stage_name(name, max_len=40)` deckt identische Logik ab wie `compact_summary.py` — sicher, kein Code-Duplikat
- `confidence_hint_html`-Box (Z. 1159-1164, bestehende Warning-Box im Body) bleibt bestehen — der neue Trend-Indikator ist ZUSÄTZLICH im Trend-Abschnitt, keine Doppelung (unterschiedliche Kontexte)
