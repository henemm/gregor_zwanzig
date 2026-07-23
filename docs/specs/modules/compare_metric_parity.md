---
entity_id: compare_metric_parity
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.1"
tags: [compare, email, renderer, frontend, bugfix, rework]
workflow: fix-1335-compare-metric-parity
---

<!-- Issue #1335 (Scheibe 1 von N). Epic #1230 (Trip/Compare-Konvergenz). -->

# Ortsvergleich-Mail: Metrik-Reihenfolge + Windrichtung-Stundenspalte (Scheibe 1 von #1335)

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich-Mail-Renderer soll sich bei zwei konkreten Punkten dem
Trip-Renderer angleichen: (1) beide Compare-Tabellen (Übersichtsmatrix,
Stundentabelle je Ort) folgen der **Reihenfolge**, die der Nutzer im
Compare-Editor für seine Metrik-Auswahl konfiguriert hat, statt einer festen
Code-Listen-Reihenfolge; (2) **Windrichtung** wird — wie beim Trip — in der
Stundentabelle als Kompass-Pfeil in der Wind-Spalte darstellbar, statt
strukturell unmöglich zu sein, UND im Compare-Editor tatsächlich als Toggle
**auswählbar** (nicht nur backend-seitig möglich). Ohne den Frontend-Katalog-
Eintrag bliebe der gemeldete Bug für den Nutzer sichtbar ungelöst — er könnte
Windrichtung serverseitig zwar rendern lassen, aber nirgends anhaken. Alle
zugrunde liegenden Daten (`LocationResult`, Stunden-Rohwerte) liegen bereits
vor; der Compare-Editor hat bereits eine generische, katalog-getriebene
Toggle-Komponente für Stundentabellen-Metriken.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
  - **Identifier:** `CV2_METRICS` (Übersichtsmatrix-Zeilen, Zeile ~215–254),
    `_visible_metrics` (~473–480), `HOUR_METRICS` (Stundentabellen-Spalten,
    ~260–270), `_visible_hour_metrics` (~598–605), `_render_hour_row`
    (~608–621), `_render_hour_table` (~624–647)
- **File:** `src/output/renderers/compare_metric_ids.py`
  - **Identifier:** `resolve_enabled_metrics` (~100–126),
    `FRONTEND_TO_RENDERER_METRIC_ID` (enthält bereits
    `"wind_direction_deg": "wind_direction_avg"`, unverändert)
- **File:** `src/output/renderers/compare_hourly_metric_ids.py`
  - **Identifier:** `FRONTEND_TO_HOURLY_METRIC_ID` (~12–22),
    `resolve_hourly_metrics` (~25–44)
- **File:** `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts`
  - **Identifier:** `ALL_HOURLY_METRICS` (~18–28) — Katalog-Liste, die von
    `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte`
    per `{#each ALL_HOURLY_METRICS as metric}` generisch iteriert wird (Zeile
    66–73 dort) und je Eintrag einen `ChannelToggle` mit
    `testid={`compare-layout-hourly-metric-${metric.key}`}` rendert. **Kein
    Umbau der Svelte-Komponente nötig** — ein neuer Katalog-Eintrag erzeugt
    den Toggle automatisch.
- **Trip-Gegenstück (Referenzmuster, NICHT geändert):**
  `src/output/renderers/email/helpers.py::should_merge_wind_dir` (~64–83),
  `dp_to_row` (~89–117, Merge-Logik ~93/97/109–110), sowie die
  Kompass-Text-Zusammenführung in `helpers.py:648–651`
  (`degrees_to_compass(row["_wind_dir_deg"])` an die Wind-Zelle angehängt).

> Schicht: Python-Core-Renderer (`src/output/renderers/...`) PLUS ein
> Frontend-Katalog-Eintrag (`frontend/src/lib/.../compareHourlyMetricDefs.ts`,
> reines Datenobjekt, keine Komponentenlogik). Kein Go-API-Code betroffen.
> Grep-Check gegen die Symbolnamen oben bestätigt die Zuordnung.

## Estimated Scope

- **LoC:** ~125–170 (Produktivcode, ohne Tests/Doku) — s. „LoC-Einschätzung"
  unten
- **Files:** 4 Produktivdateien (3 Python + 1 Frontend-Katalog) + 2–3
  Testdateien (1–2 neu, 1 bestehend erweitert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID` | internal dict | Bestehende Vokabular-Übersetzung Frontend→Renderer (Übersicht), unverändert |
| `src/output/renderers/compare_hourly_metric_ids.py::FRONTEND_TO_HOURLY_METRIC_ID` | internal dict | Bestehendes Vokabular Frontend→Renderer (Stunde); bekommt einen neuen Eintrag für Windrichtung |
| `frontend/.../compareHourlyMetricDefs.ts::ALL_HOURLY_METRICS` | internal frontend catalog | Muss **1:1** mit den Keys aus `FRONTEND_TO_HOURLY_METRIC_ID` übereinstimmen (Datei-Kommentar dort, Zeile 4–6) — sonst verwirft `resolve_hourly_metrics` die Auswahl (unbekannte ID → None → Default „alle"). Bekommt den neuen Windrichtungs-Key als Eintrag. |
| `frontend/.../CompareHourlyLayoutControls.svelte` | internal frontend component | Generische, bereits geteilte Toggle-Iteration (`{#each ALL_HOURLY_METRICS}`) — reiner Katalog-Konsument, **keine Änderung** an dieser Komponente nötig |
| `src/services/report_config_resolver.py` | internal module | Ruft `resolve_enabled_metrics`/`resolve_hourly_metrics` auf und reicht das Ergebnis in `CompareRenderOptions` durch — Konsument, keine Änderung nötig (Duck-Typing: Liste statt Set funktioniert transparent an allen Aufrufstellen) |
| `src/output/renderers/comparison.py` (SMS/Telegram-Compare) | internal module | Nutzt `enabled_metrics` nur für `in`-Mitgliedschaftsprüfung, keine Reihenfolge-Semantik nötig — bleibt unverändert, Verhalten unangetastet |
| `src/output/renderers/email/helpers.py::should_merge_wind_dir`/`degrees_to_compass` | internal (Trip-Muster) | Referenzmuster für die Windrichtungs-Merge-Logik im Compare-Pfad (kein Code-Reuse, da Trip auf `UnifiedWeatherDisplayConfig.metrics` arbeitet, Compare auf der Renderer-eigenen `HOUR_METRICS`-Liste) |
| `src/utils/geo.py::degrees_to_compass` | internal function | Kompass-Text aus Grad — wird auch im Compare-Pfad wiederverwendet (echtes Code-Reuse, kein Nachbau) |
| `ForecastDataPoint.wind_direction_deg` (`src/app/models.py`) | internal model field | Datenquelle für den Stunden-Kompass-Pfeil; liegt in `loc.hourly_data`-Punkten bereits vor |

**Konsistenz-Hinweis (bewusste Design-Entscheidung dieser Scheibe):**
`ALL_HOURLY_METRICS` (Frontend, `compareHourlyMetricDefs.ts`) und
`FRONTEND_TO_HOURLY_METRIC_ID` (Backend, `compare_hourly_metric_ids.py`) sind
aktuell **zwei handgepflegte, unabhängige Vokabular-Deklarationen ohne
automatisierten Cross-Check** — der Datei-Kommentar in
`compareHourlyMetricDefs.ts` fordert die 1:1-Übereinstimmung nur als
Konvention, nicht als erzwungenen Build-Schritt. Diese Scheibe pflegt den
einen neuen Windrichtungs-Eintrag in **beiden** Katalogen im Bestandsmuster
nach (gleicher Key-String auf beiden Seiten). Eine generische
Vereinheitlichung (z.B. Auswahl aus einem gemeinsamen `/api/metrics`-Katalog
statt zweier Duplikate) bleibt bewusst #1350 (Katalog-Single-Source) bzw.
#1351 (Katalog-Lücken) vorbehalten — nicht Teil dieser Spec.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/compare_metric_ids.py` | MODIFY | `resolve_enabled_metrics` gibt eine **reihenfolge-erhaltende, deduplizierte Liste** (statt `set`) zurück — erste Vorkommensreihenfolge von `active_metrics`, unmappbare IDs weiterhin verworfen + geloggt (Verhalten AC-2/AC-4/AC-6 aus #1296 bleibt erhalten). |
| `src/output/renderers/compare_hourly_metric_ids.py` | MODIFY | Neuer Eintrag `"wind_dir_deg": "wind_direction_deg"` in `FRONTEND_TO_HOURLY_METRIC_ID`; `resolve_hourly_metrics` analog reihenfolge-erhaltend statt `set`. |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_visible_metrics`: Zeilen-Reihenfolge nach `enabled_metrics`-Reihenfolge, „warn"-Zeile bleibt fest an erster Position. `_visible_hour_metrics`: Spalten-Reihenfolge nach `hourly_metrics`-Reihenfolge; `wind_direction_deg` wird aus der Spaltenliste ausgefiltert (kein eigenes `<th>`), aber als Merge-Signal an `_render_hour_row` durchgereicht. `_render_hour_row`/`_render_hour_table`: hängt bei aktivem Merge den Kompass-Pfeil (`degrees_to_compass`) an die Wind-Zelle an — analog `helpers.py:648–651`. |
| `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` | MODIFY | `ALL_HOURLY_METRICS` bekommt einen neuen Eintrag `{ key: 'wind_dir_deg', label: 'Windrichtung' }` (Key 1:1 identisch zum neuen Backend-`FRONTEND_TO_HOURLY_METRIC_ID`-Eintrag). Der veraltete Datei-Kommentar Zeile 15–17 („NICHT die Spaltenreihenfolge in der Mail ... kanonisch fest verdrahtet") wird bei dieser Gelegenheit korrigiert, da er durch diese Scheibe fachlich falsch wird. Kein Änderungsbedarf an `CompareHourlyLayoutControls.svelte` — die generische `{#each ALL_HOURLY_METRICS}`-Iteration erzeugt den Toggle automatisch. |
| `frontend/src/lib/components/compare/compareEditorHourlyMetrics.test.ts` | MODIFY | Bestehende Katalog-Assertion `ALL_HOURLY_METRICS.length === 9` wird auf `10` angepasst; neuer Test prüft explizit den Windrichtungs-Eintrag (Key + Label). |
| `tests/tdd/test_compare_metric_order.py` | CREATE | Backend-Kern-Tests: Übersichts-Zeilenreihenfolge folgt `active_metrics`; Stundentabellen-Spaltenreihenfolge folgt `hourly_metrics`; Windrichtung erscheint/fehlt korrekt in der Stundentabelle; Übersichtsmatrix-Windrichtung bleibt korrekt (Regress-Test). |
| `tests/tdd/test_trip_renderer_characterization.py` (oder Ergänzung einer bestehenden Trip-Charakterisierungs-Suite, falls vorhanden — vor Implementierung prüfen) | CREATE/MODIFY | Byte-identischer Trip-SMS/Telegram/Mail-Output vor/nach dem Umbau (Fixtures, kein Live-Wetter). |

### Estimated Changes

- Files: 4 Produktiv (3 Python + 1 Frontend-Katalog) + 2–3 Tests
- LoC: +130/-30 (Produktivcode, Schätzung); Tests zusätzlich ~160–210 LoC

## Implementation Details

**1. Reihenfolge-Auflösung (`resolve_enabled_metrics`/`resolve_hourly_metrics`):**
Die JSON-Felder `display_config.active_metrics`/`display_config.hourly_metrics`
sind bereits geordnete Listen. Die aktuelle Implementierung baut daraus ein
`set` (Comprehension `{... for m in active_metrics ...}`) — Python-Sets haben
keine garantierte Iterationsreihenfolge, dadurch geht die Nutzer-Reihenfolge
verloren, bevor sie den Renderer erreicht. Fix: `dict.fromkeys(...)`-Muster
oder explizite Schleife, die die erste-Vorkommen-Reihenfolge beibehält und
Duplikate entfernt; Rückgabetyp wird `list[str] | None` (Typ-Hint-Update).
Der `unmapped`-Warn-Pfad (Issue #1296 Guard) bleibt unverändert erhalten.

**2. Windrichtung ins Stunden-Vokabular (Backend):** Neuer Eintrag
`"wind_dir_deg": "wind_direction_deg"` in `FRONTEND_TO_HOURLY_METRIC_ID`
(rechte Seite = Name des `ForecastDataPoint`-Feldes). Dieser Key hat
**keinen** Eintrag in `HOUR_METRICS` (keine eigene Spalte) — er ist reines
Merge-Signal.

**3. Windrichtung im Frontend-Katalog (End-to-End-Auswahl):** Neuer Eintrag
`{ key: 'wind_dir_deg', label: 'Windrichtung' }` in `ALL_HOURLY_METRICS`
(`compareHourlyMetricDefs.ts`) — Key identisch zum Backend-Eintrag aus Punkt
2. `CompareHourlyLayoutControls.svelte` iteriert diese Liste bereits
generisch (`{#each ALL_HOURLY_METRICS as metric}`, Zeile 66) und erzeugt pro
Eintrag einen `ChannelToggle` mit `testid={`compare-layout-hourly-metric-${metric.key}`}`
— **kein Komponenten-Umbau nötig**, der Toggle „Windrichtung" erscheint
automatisch im Compare-Editor-Layout-Tab. Aktiviert der Nutzer ihn, landet
`'wind_dir_deg'` in `wiz.hourlyMetricKeys` → `display_config.hourly_metrics`
(bestehender Speicherpfad, unverändert) → `resolve_hourly_metrics` (Punkt 1)
→ Merge-Logik (Punkt 5).

**4. Reihenfolge-Filterung in `compare_html.py`:** `_visible_metrics`/
`_visible_hour_metrics` bauen aus der jetzt geordneten `enabled_metrics`/
`hourly_metrics`-Liste die sichtbare Zeilen-/Spaltenliste **in dieser
Reihenfolge** (Lookup-Dict aus `CV2_METRICS`/`HOUR_METRICS` nach `key`, dann
in Auswahlreihenfolge zusammensetzen). Die „warn"-Zeile wird dabei **immer**
vorangestellt, unabhängig von ihrer Position (oder Abwesenheit) in
`active_metrics` — sie ist nicht Teil des wählbaren Reihenfolge-Vokabulars
(konsistent zu #1332).

**5. Windrichtungs-Merge in der Stundentabelle:** Analog
`should_merge_wind_dir()` (Trip-Muster) wird ermittelt, ob sowohl die
Wind-Spalte (`wind10m_kmh`) als auch `wind_direction_deg` in der aufgelösten
`hourly_metrics`-Auswahl enthalten sind. Ist das der Fall, wird beim Rendern
der Wind-Zelle `degrees_to_compass(dp.wind_direction_deg)` an den
formatierten Text angehängt (Leerzeichen-getrennt, wie im Trip-Pfad). Ist
`hourly_metrics` `None` (kein Filter gesetzt = Altbestand/Default) oder fehlt
`wind_dir_deg` in der Auswahl, bleibt die Wind-Zelle unverändert — Windrichtung
erscheint **nur bei expliziter Auswahl**, nie automatisch für Bestandsnutzer
ohne Konfiguration (kein stiller Verhaltenswechsel für alle Compare-Mails).

**6. Übersichtsmatrix-Windrichtung (Regress-Schutz):** Die bestehende Zeile
`{"key": "wind_direction_avg", "label": "Windrichtung", "unit": "°"}` in
`CV2_METRICS` bleibt unverändert in Inhalt und Formatierung — nur ihre
*Position* in der gerenderten Tabelle folgt jetzt ggf. einer anderen
Config-Reihenfolge, der Zellenwert selbst ändert sich nicht.

**Nicht Teil dieser Scheibe:** die generische Vereinheitlichung der beiden
parallel gepflegten Frontend-Kataloge (`compareMetricDefs.ts` für die
Übersicht, `compareHourlyMetricDefs.ts` für die Stunde) bzw. deren Ablösung
durch einen gemeinsamen `/api/metrics`-getriebenen Katalog — das ist #1350
(Katalog-Single-Source). Ebenso nicht Teil dieser Scheibe: darüber
hinausgehende Katalog-Lücken anderer fehlender Metriken (#1351).

## Expected Behavior

- **Input:** `display_config.active_metrics` (geordnete Liste von
  Frontend-Metrik-IDs) und `display_config.hourly_metrics` (geordnete Liste
  von Frontend-Stunden-Metrik-IDs, inkl. optional `"wind_dir_deg"` — jetzt
  auch über den Compare-Editor-Toggle setzbar), sowie `LocationResult`-Objekte
  mit `hourly_data` (Stunden-Rohwerte inkl. `wind_direction_deg`).
- **Output:** Übersichtsmatrix-HTML mit Zeilen in `active_metrics`-Reihenfolge
  (Warn-Zeile fest zuerst); Stundentabellen-HTML mit Spalten in
  `hourly_metrics`-Reihenfolge; Wind-Zelle mit angehängtem Kompass-Pfeil, wenn
  `wind_dir_deg` mitgewählt wurde; im Compare-Editor erscheint ein neuer
  Toggle „Windrichtung" unter der Stundenverlauf-Metrik-Auswahl.
- **Side effects:** keine (reine Rendering-Funktionen + ein statischer
  Katalog-Eintrag, keine Persistenz-/Netzwerk-Seiteneffekte). Trip-Renderer-
  Output bleibt byte-identisch.

## Test Plan

Kern-Schicht (deterministisch, keine Live-Wetterdaten, keine Mocks von
Rendering-Logik — echte Fixture-Objekte):

### Automated Tests (TDD RED)

- [ ] **Test A — Übersichtsmatrix-Reihenfolge:** `LocationResult`-Fixtures
  (≥2 Orte) mit gesetzten Werten für `wind_max`/`temp_max`/`precip_sum`;
  `enabled_metrics`/`active_metrics`-Reihenfolge bewusst umgekehrt zur
  `CV2_METRICS`-Deklarationsreihenfolge (z.B. `["precip_sum", "wind_max",
  "temp_max"]`). GIVEN diese Reihenfolge WHEN `render_compare_html(...)`
  gerufen wird THEN erscheinen die Zeilen-Label im gerenderten HTML in
  genau dieser Reihenfolge (Positionsvergleich der Label-Strings), Warn-Zeile
  weiterhin zuerst.
- [ ] **Test B — Stundentabellen-Reihenfolge:** `hourly_data`-Fixture mit
  mehreren Stunden-Datenpunkten; `hourly_metrics` bewusst umsortiert (z.B.
  `["precip_mm", "temp_c", "wind_kmh"]`). GIVEN diese Auswahl WHEN die
  Stundentabelle gerendert wird THEN erscheinen die `<th>`-Spaltenköpfe in
  genau dieser Reihenfolge.
- [ ] **Test C — Windrichtung erscheint (Merge):** Stunden-Datenpunkt mit
  `wind_direction_deg=225` und gesetztem `wind10m_kmh`; `hourly_metrics`
  enthält `"wind_kmh"` UND `"wind_dir_deg"`. GIVEN diese Auswahl WHEN die
  Stundentabelle gerendert wird THEN enthält die Wind-Zelle sowohl den
  Wind-Zahlwert als auch den Kompass-Text (z.B. "SW"), UND es gibt keine
  eigene Windrichtungs-Spalte (Spaltenzahl unverändert ggü. Auswahl ohne
  `wind_dir_deg`).
- [ ] **Test D — Windrichtung fehlt in Auswahl (kein Regress):** gleiche
  Fixture wie Test C, aber `hourly_metrics` ohne `"wind_dir_deg"`. GIVEN diese
  Auswahl WHEN gerendert wird THEN zeigt die Wind-Zelle nur den Zahlwert,
  kein Kompass-Text — identisch zum Verhalten vor dieser Änderung.
- [ ] **Test E — Übersichtsmatrix-Windrichtung weiterhin korrekt:**
  `LocationResult` mit `wind_direction_avg` gesetzt, `active_metrics` enthält
  `"wind_direction_deg"` an beliebiger Position. GIVEN dies WHEN gerendert
  wird THEN zeigt die Windrichtungs-Zeile weiterhin den korrekten
  Grad-Wert (kein Formatierungs-Regress durch die Reihenfolge-Änderung).
- [ ] **Test F — Trip-Charakterisierung:** bestehende Trip-Fixture (SMS,
  Telegram, Mail) vor und nach dem Umbau rendern (Snapshot-Vergleich oder
  Byte-Vergleich des Outputs). GIVEN unveränderte Trip-Konfiguration WHEN
  Trip-Renderer aufgerufen wird THEN ist der Output byte-identisch zum
  Stand vor dieser Änderung.
- [ ] **Test G — Frontend-Katalog-Eintrag + Toggle-Iteration (AST/Struktur,
  analog `compare_hourly_layout_controls_structure.test.ts`):** Erweiterung
  von `compareEditorHourlyMetrics.test.ts` (oder neuer Test im selben
  Verzeichnis). GIVEN der Katalog `ALL_HOURLY_METRICS` WHEN er importiert und
  inspiziert wird THEN enthält er genau einen Eintrag mit
  `key === 'wind_dir_deg'` und `label === 'Windrichtung'` (Ersetzt die
  bisherige `length === 9`-Assertion durch `length === 10`); zusätzlich
  bestätigt der bestehende AST-Test `compare_hourly_layout_controls_structure.test.ts`
  (unverändert, da strukturell/generisch) weiterhin, dass JEDER
  `ALL_HOURLY_METRICS`-Eintrag — inkl. des neuen — einen
  `compare-layout-hourly-metric-${metric.key}`-Toggle erzeugt.

Live-E2E (nicht Teil des RED/GREEN-Kernzyklus dieser Scheibe): Staging —
Compare-Editor öffnen, Toggle „Windrichtung" unter Stundenverlauf aktivieren,
Preset speichern, Mail auslösen und per `email_spec_validator.py`
(Ortsvergleich-Pfad) verifizieren, dass die Wind-Zelle den Kompass-Pfeil
zeigt, im Rahmen des Post-Push-Workflows.

## Acceptance Criteria

- **AC-1:** Given eine Compare-Konfiguration mit `active_metrics = ["precip_sum_mm", "wind_max_kmh", "temp_max_c"]` (bewusst nicht in `CV2_METRICS`-Deklarationsreihenfolge) / When die Übersichtsmatrix gerendert wird / Then erscheinen die Zeilen "Regen", "Wind", "Temp max" in genau dieser Reihenfolge unterhalb der stets ersten "Amtliche Warnungen"-Zeile.
  - Test: Test A (Positionsvergleich der Zeilen-Label im gerenderten HTML)

- **AC-2:** Given eine Compare-Konfiguration mit `hourly_metrics = ["precip_mm", "temp_c", "wind_kmh"]` (umsortiert ggü. `HOUR_METRICS`-Reihenfolge) / When die Stundentabelle eines Ortes gerendert wird / Then erscheinen die Spaltenköpfe "Regen", "Temp", "Wind" in genau dieser Reihenfolge; ist `hourly_metrics` nicht gesetzt (None), bleibt die bisherige Default-Reihenfolge unverändert.
  - Test: Test B (Positionsvergleich der `<th>`-Spaltenköpfe)

- **AC-3:** Given eine Compare-Konfiguration mit `hourly_metrics` enthält sowohl `"wind_kmh"` als auch `"wind_dir_deg"`, und ein Stunden-Datenpunkt mit gesetztem `wind_direction_deg` / When die Stundentabelle gerendert wird / Then enthält die Wind-Zelle zusätzlich zum Zahlwert einen Kompass-Richtungstext (analog Trip-Muster `should_merge_wind_dir`), ohne eine zusätzliche eigenständige Spalte zu erzeugen.
  - Test: Test C (Zelleninhalt + Spaltenzahl-Vergleich)

- **AC-4:** Given eine Compare-Konfiguration ohne `"wind_dir_deg"` in `hourly_metrics` (oder `hourly_metrics = None`) / When die Stundentabelle gerendert wird / Then zeigt die Wind-Zelle unverändert nur den Zahlwert, kein Kompass-Text erscheint — identisches Verhalten zum Stand vor dieser Scheibe.
  - Test: Test D (Zelleninhalt-Vergleich, negativer Fall)

- **AC-5:** Given eine `LocationResult` mit gesetztem `wind_direction_avg` und `active_metrics` enthält `"wind_direction_deg"` an beliebiger Position / When die Übersichtsmatrix gerendert wird / Then zeigt die Windrichtungs-Zeile weiterhin den korrekten Gradwert — die Reihenfolge-Änderung dieser Scheibe verändert den Zellenwert nicht.
  - Test: Test E (Regress-Test Übersichtsmatrix)

- **AC-6:** Given eine unveränderte Trip-Konfiguration (SMS/Telegram/Mail) / When der Trip-Renderer nach dieser Änderung erneut aufgerufen wird / Then ist der gerenderte Output byte-identisch zum Stand vor der Änderung (Charakterisierungs-Anker, kein Trip-Regress).
  - Test: Test F (Byte-/Snapshot-Vergleich)

- **AC-7:** Given eine beliebige `active_metrics`-Konfiguration, die `"warn"` nicht enthält (die Warn-Zeile ist kein wählbares Auswahl-Item) / When die Übersichtsmatrix gerendert wird / Then erscheint die "Amtliche Warnungen"-Zeile trotzdem immer als erste Zeile — konsistent zum in #1332 ausgelieferten Verhalten.
  - Test: Test A deckt dies implizit ab (Warn-Zeile-Positionsprüfung); zusätzlicher expliziter Assert im selben Testfall.

- **AC-8:** Given der Compare-Editor (Stundentabellen-Metrik-Auswahl im Layout-Tab) / When der Nutzer die Stundentabellen-Metriken konfiguriert / Then ist Windrichtung als auswählbare Stundentabellen-Metrik vorhanden (Toggle `compare-layout-hourly-metric-wind_dir_deg`, generiert aus dem neuen `ALL_HOURLY_METRICS`-Katalog-Eintrag), und ihr Aktivieren führt END-TO-END dazu, dass die Windrichtung als Kompass-Pfeil in der Wind-Spalte der Stundentabelle der versendeten Mail erscheint (Auswahl → `display_config.hourly_metrics` → Renderer-Merge, AC-3).
  - Test: Test G (Frontend-Katalog-Eintrag + generische Toggle-Iteration) in Kombination mit Test C (Backend-Merge) als End-to-End-Beleg des vollständigen Pfads.

## Known Limitations

- Die 1:1-Übereinstimmung zwischen `ALL_HOURLY_METRICS` (Frontend) und
  `FRONTEND_TO_HOURLY_METRIC_ID` (Backend) bleibt in dieser Scheibe **manuell
  gepflegte Konvention** (per Datei-Kommentar dokumentiert), nicht
  automatisiert erzwungen — eine Drift zwischen beiden Katalogen würde
  weiterhin still zu einer verworfenen Auswahl führen (Resolver-Fallback auf
  „alle"), nicht zu einem Build-/Test-Fehler. Ein automatisierter Cross-Check
  ist Teil der Katalog-Single-Source-Vereinheitlichung (#1350).
- Katalog-Single-Source (#1350) und weitergehende Katalog-Lücken/
  channel_layouts (#1351) bleiben ausdrücklich Folge-Scheiben, nicht Teil
  dieser Spec.

## LoC-Einschätzung (Reihenfolge + Windrichtung zusammen vs. getrennt)

**Empfehlung: zusammen ausliefern (eine Scheibe, kein S1a/S1b-Split).**

Begründung: Alle drei Teile (Reihenfolge, Backend-Windrichtungs-Vokabular,
Frontend-Katalog-Eintrag) berühren dieselben vier Renderer-Funktionen in
derselben Datei (`_visible_metrics`, `_visible_hour_metrics`,
`_render_hour_row`, `_render_hour_table`) bzw. dieselbe
Reihenfolge-Auflösungs-Logik in `compare_metric_ids.py`/
`compare_hourly_metric_ids.py`, und der Frontend-Katalog-Eintrag ist ohne
Backend-Vokabular-Eintrag wertlos (führt sonst nur zu einer vom Resolver
verworfenen Auswahl). Ein Split würde Teil-Scheiben zwingen, dieselben
Funktionen mehrfach anzufassen (Review-Overhead ohne fachlichen Nutzen) und
würde den End-to-End-Nutzen (AC-8) künstlich auf zwei Scheiben verteilen.

Geschätzter Umfang (Produktivcode, ohne Tests/Doku):
- `compare_metric_ids.py`: ~15–20 LoC (Funktions-Umbau + Docstring)
- `compare_hourly_metric_ids.py`: ~15–20 LoC (neuer Dict-Eintrag +
  Funktions-Umbau + Docstring)
- `compare_html.py`: ~70–100 LoC (zwei `_visible_*`-Umbauten,
  Merge-Flag-Ermittlung, Wind-Zellen-Text-Erweiterung, Signatur-Anpassungen)
- `compareHourlyMetricDefs.ts`: ~3–5 LoC (ein neuer Katalog-Eintrag +
  Kommentar-Korrektur)
- **Summe: ~125–170 LoC**, deutlich unter der 250-LoC-Marke aus dem
  Regel-Budget — kein Anlass zur Teilung.

Tests kommen mit ~160–210 LoC hinzu (inkl. der Frontend-Katalog-Erweiterung
in `compareEditorHourlyMetrics.test.ts`), zählen aber laut Aufgabenstellung
nicht in die Split-Entscheidung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Renderer-Bugfix/Rework plus ein additiver
  Frontend-Katalog-Eintrag innerhalb einer bestehenden, bereits durch ADRs
  abgedeckten Fläche (Compare-Mail-Rendering, Trip/Compare-Code-Teilungs-
  Prinzip aus CLAUDE.md, geteilte `CompareHourlyLayoutControls.svelte`
  bleibt unverändert). Keine neue Architektur-Entscheidungsfläche (kein
  neuer Kanal, kein neuer Provider, kein Datenmodell-Wechsel, keine
  Auth-/Persistenz-Änderung).

## Changelog

- 2026-07-23: Initial spec created (Scheibe 1 von #1335, Analyse in
  `docs/context/fix-1335-compare-metric-parity.md`)
- 2026-07-23: Scope-Korrektur (Koordinator-Review) — Frontend-Katalog-Eintrag
  `compareHourlyMetricDefs.ts` in Affected Files aufgenommen (End-to-End-
  Auswahlpfad statt nur Backend-Möglichkeit); AC-8 ergänzt; Konsistenz-Hinweis
  zur handgepflegten 1:1-Kopplung `ALL_HOURLY_METRICS` ↔
  `FRONTEND_TO_HOURLY_METRIC_ID` ergänzt; Test G (Frontend-Struktur-Test)
  ergänzt.
