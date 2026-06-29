# Spec: Briefing-Mail Detail-Korrekturen (#911)

- **Created:** 2026-06-29
- **Issue:** #911
- **Workflow:** fix-911-mail-details
- **Scope:** `src/output/renderers/email/html.py` (Renderer, Desktop **und** Mobile-Pfad),
  `helpers.py` (Spalten-Order Issue 3 + Trend-Tokens Issue 12), `design_tokens.py` (4-Stufen-Farben),
  `services/trip_report_scheduler.py` + `services/weather_metrics.py` (Trend-Builder: PR/Gewitter-% pro
  Folgetag für die Ausblick-Tabelle, Issue 12). **Kein** Wholesale-Replace.
- **PO-Entscheidungen 2026-06-29:** (a) Issue 7 = nur Abstände in diesem Workflow; abweichendes Pill-Textformat
  → separate Übersicht/Folge-Issue. (b) Issue 12 = volle Tabelle inkl. PR/Gewitter-%, soweit Vorhersagedaten im
  Horizont vorliegen (sonst „–"). (c) Fixes 4/5/10/11/12 für Desktop **und** Mobile.
- **Referenz-Vorlage:** `docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx` (`EmailPreview`)
- **ADR:** keine Richtungsentscheidung (reine Fidelity-Korrektur) → `[no-adr]`

## Kontext
12 Detail-Abweichungen der Trip-Briefing-Mail gegenüber der Design-Vorlage. Jede AC = ein Punkt aus #911.
Geprüft wird am **gerendert HTML** der echten Staging-Mail (`briefing_mail_validator.py`), nicht an Strings.

## Zwei Entscheidungen (beim Approval bestätigen)
- **AC-1 (Farbe):** Die Vorlage nutzt für den Vortagsvergleich ein *graues* „vs. Gestern". #911 verlangt aber
  ausdrücklich *dieselbe Farbe wie TAGESLAGE*. → Wir setzen die Headline „VORTAGESVERGLEICH" auf **Akzent-Orange**
  (`#c45a2a`, wie TAGESLAGE). Issue-Text ist Autorität.
- **AC-3 (Reihenfolge):** Issue 3 = **Spalten**-Reihenfolge der Stundentabelle soll der im Trip-Editor
  konfigurierten Metrik-Reihenfolge (`dc.metrics`, links→rechts) folgen — *nicht* der festen Demo-Reihenfolge
  der Vorlage. Aktuell ordnet `visible_cols` nach festem Katalog (`get_col_defs()`).

## Acceptance Criteria

**AC-1:** Given eine Briefing-Mail mit Vortagsvergleich, When sie gerendert wird, Then trägt die Headline
„VORTAGESVERGLEICH" dieselbe Akzent-Orange-Farbe (`#c45a2a`) wie die Headline „TAGESLAGE" (nicht mehr Grau `#9a978d`).

**AC-2:** Given der Vortagsvergleich hat einen Trend-Indikator (▲/▼/▬), When die Mail gerendert wird, Then steht
der Indikator-Glyph **hinter** der Headline „VORTAGESVERGLEICH" (Reihenfolge: Headline-Text, dann Glyph), nicht davor.

**AC-3:** Given ein Trip mit einer im Editor konfigurierten Metrik-Reihenfolge, When die Stundentabelle gerendert
wird, Then erscheinen die Wetter-Spalten links→rechts in genau dieser konfigurierten Reihenfolge (nach der festen
Zeit/Temp-Leitspalte), statt in der festen Katalog-Reihenfolge.

**AC-4:** Given eine Segment-/Ziel-Stundentabelle (Desktop **und** Mobile), When sie gerendert wird, Then
entsprechen Linienfarben (Zell-Linien `#f0ece1`, Header-Unterkante `#e6e1d3`), Header (weißer Hintergrund,
Text `#3a3835` 11px/600) und Typografie der Vorlage-`EmailDataTable` (Mono-Datenzellen, tabular-nums).

**AC-5:** Given die Stundentabelle, When sie gerendert wird, Then heißt die letzte Spalte „Risk" (statt „·"); der
Spalteninhalt bleibt der pro-Stunde berechnete Risiko-Dot (Ampel aus Schwellwerten: Gewitter/Böen/Wind/Regen/RegenW/Sicht).

**AC-6:** Given der Etappen-Stats-Block im Header (DISTANZ/AUFSTIEG/…), When er gerendert wird, Then besteht ein
sichtbarer Abstand zwischen der oberen Trennlinie und den Spalten-Labels (Labels stoßen nicht mehr an die Linie).

**AC-7:** Given der METRIKEN-ÜBERBLICK (Desktop), When er gerendert wird, Then entsprechen Außenabstand
(`padding:14px 28px 18px`), Hintergrund (`#fdfcf8`), Unterkante (`#e6e1d3`) und Pill-Abstände (Flex `gap:6`,
`margin-top:10`) der Vorlage-`EmailMetricsSummary` (Pills nicht mehr gedrängt/ohne Gap). **Nur Abstände** —
das abweichende Pill-Textformat ist NICHT Teil dieses Workflows (Übersicht: `docs/context/911-pill-format-delta.md`,
Folge-Issue).

**AC-8:** Given der Ausblick auf die nächsten Tage, When er gerendert wird, Then enthält er eine Spalte „ACC"
(Prognose-Genauigkeit) je Tag, dargestellt als 4-stufiger Risk-Dot aus dem Konfidenz-Wert (`confidence_pct`).

**AC-9:** Given der Ausblick-Abschnitt, When er gerendert wird, Then steht darüber die Eyebrow-Headline
„Ausblick · nächste 3 Tage" (aktuell fehlend).

**AC-10:** Given eine Stundentabellen-Zelle mit erhöhtem Schweregrad (Wind/Böen/Regen/RegenW/Gewitter/Sicht),
When sie gerendert wird (Desktop **und** Mobile), Then trägt die **Zelle einen getönten Hintergrund** entsprechend
dem Warn-Level (caution `#fbeeb8`, warn `#fad6b8`, danger `#f6c5bf`), nicht nur farbigen Text.

**AC-11:** Given die RISK-Legende der Mail (Desktop **und** Mobile), When sie gerendert wird, Then erscheint sie
mit „RISK"-Präfix und **flachen CSS-Dots** (4-stufig, via `_risk_dot`) auf hellem Section-Hintergrund über dem
dunklen Footer — keine glänzenden Emoji-Kreise auf dem dunklen Footer.

**AC-12:** Given der Ausblick auf die nächsten Tage, When er gerendert wird (Desktop **und** Mobile), Then ist er
als **Tabelle** (Vorlage-`OutlookTable`) dargestellt: eine Zeile je Tag, Spalten Tag · N · D · R · PR · Wind ·
Böen · Gew · ACC, Inhalte analog den SMS-Tokens, Zell-Hintergrund je Warn-Level, mit Code-Legende darunter.

**AC-13:** Given die Ausblick-Tabelle benötigt PR (Regenwahrscheinlichkeit %) und Gewitter-Stufe pro Folgetag,
When der Trend-Builder die Folgetage aggregiert, Then werden PR aus `pop_max_pct` und Gewitter-Stufe aus
`thunder_level_max` in den Trend-Datensatz aufgenommen; die Gew-Spalte zeigt die laienverständliche Stufe
(„mittel @HH" / „hoch @HH") — **kein Fake-%-Wert** (ForecastDataPoint hat kein thunder_pct-Feld); NONE → „–".
Liegt kein Wert vor, zeigt die Zelle „–" (kein Fehler). **PO-Entscheidung 2026-06-29.**

## Invarianten (dürfen NICHT brechen)
- Risk-Engine, Alert-Logik, Scheduler, Persistenz unverändert — nur Rendering.
- Bestehende Mail-Sektionen (Header-Inhalte, Tageslage-Text, Antwort-Kommandos, Footer-Deep-Links #901,
  Mobile-Stundenliste) bleiben funktional erhalten.
- `confidence` bleibt nicht-wählbare Metrik (#710); ACC nutzt nur den Konfidenz-Wert für den Ausblick-Dot.
- Mandantentrennung unverändert.
- `test_issue_811_mode_matrix.py` (Modus-Matrix) bleibt grün.

## Test-Strategie (KEINE Mocks)
- Rendern echter Briefing-Mail über den Renderer mit realistischen Segment-Daten; Assertions am erzeugten HTML
  (Plausibilität, nicht bloße String-Presence): Headline-Farben, Glyph-Position, Spalten-Order, Zell-bg-Tönung,
  „Risk"/„ACC"-Header, Ausblick-Tabelle, Legenden-Dots.
- E2E: echte Staging-Mail an `gregor-test@henemm.com`, `briefing_mail_validator.py` Exit 0.
