# User Story: Vortag-Vergleich im Trip-Briefing

**Status:** open
**Erstellt:** 2026-06-11
**GitHub Issues:** #747 (F1), #748 (F2), #749 (F3), #750 (F4), #751 (F5), #752 (F6)

## Story

Als Weitwanderer auf dem GR20
moechte ich in meiner Briefing-E-Mail einen kompakten Vergleich zur gestrigen Vorhersage sehen,
damit ich sofort einschaetzen kann ob heute besser oder schlechter wird — ohne die gestrige E-Mail aufzurufen.

## Acceptance Criteria (PO-bestaetigt)

- [ ] Eine Sektion "Vergleich zum Vortag" zeigt ausschliesslich Deltas gegenueber der gestrigen Vorhersage (z.B. "+5°C gefuehlt, -30 km/h Boen, -40% Regen" — oder regelbasierte Prosa)
- [ ] Heute-Werte werden nicht wiederholt
- [ ] Keine AI-Textgenerierung — ausschliesslich regelbasierte Ausgabe
- [ ] Sektion fehlt stillschweigend wenn keine gestrige Vorhersage vorliegt (erster Tag, noch kein Snapshot)
- [ ] Vergleichsbasis: gestrige Vorhersage (nicht gestrige Ist-Werte)

## Architektur-Analyse

### Kern-Herausforderung: Snapshot-Persistenz

Die aktuelle `WeatherSnapshotService.save()` schreibt immer auf `{trip_id}.json` — es gibt nur einen einzigen Snapshot pro Trip, der bei jedem Report ueberschrieben wird. Fuer den Vortag-Vergleich muss der Snapshot des Vortages lesbar sein, waehrend der aktuelle Snapshot des heutigen Tages gespeichert wird.

**Loesungsansatz:** Snapshot-Dateinamen auf `{trip_id}_{YYYY-MM-DD}.json` umstellen. Der Scheduler laedt `{trip_id}_{gestern}.json` vor dem Ueberschreiben. Retention: max. 3 Snapshots pro Trip (mtime-sortiert), um Speicher zu begrenzen.

### Betroffene Architektur-Schichten

```
Scheduler (Step 6: Vortag laden → Delta berechnen)
  ↓
WeatherSnapshotService (save/load mit Datum-Schluessel + Retention)
  ↓
DayComparisonService (neu: Delta-Berechnung aus zwei SegmentWeatherData-Listen)
  ↓
TripReportFormatter.format_email() (neues day_comparison-Argument)
  ↓
render_html() / render_plain() (neue Sektion render_day_comparison_html/plain)
  ↓
TripReportConfig (neues Toggle show_yesterday_comparison)
```

## Feature Breakdown

### P0 Features (Must Have — MVP)

---

#### Feature 1: Datierter Snapshot-Speicher

**Kategorie:** Service (WeatherSnapshotService)
**Scoping:** 2 Dateien, ~80 LOC, Medium
**Abhaengigkeiten:** Keine
**GitHub Issue:** #747

**Was:** `WeatherSnapshotService.save()` speichert zusaetzlich als `{trip_id}_{YYYY-MM-DD}.json`. Neue Methode `load_dated(trip_id, date)`. Retention: max. 7 datierte Snapshots pro Trip (mtime-sortiert, aelteste loeschen). Bestehende `{trip_id}.json` bleibt fuer Rueckwaertskompatibilitaet erhalten (Alert-System liest sie noch).

**Akzeptanzkriterien:**
- [x] `save_dated()` schreibt auch `{trip_id}_2026-06-11.json` (datiertes Duplikat)
- [x] `load_dated(trip_id, date(2026,6,10))` laedt den Snapshot vom 10.06. zurueck
- [x] Nach 8 Speichervorgaengen existieren max. 7 datierte Dateien (aelteste geloescht)
- [x] Kein Mock: echter Dateisystem-Roundtrip im Test
- [x] Mandantentrennung: user_id-Pfad unveraendert
- [x] Status: IMPLEMENTED (2026-06-11) — Spec Issue #747

**Dateien:**
- `src/services/weather_snapshot.py` (MODIFIED)
- `tests/tdd/test_weather_snapshot_dated.py` (NEW)

---

#### Feature 2: DayComparisonService

**Kategorie:** Service (neu)
**Scoping:** 2 Dateien, ~120 LOC, Medium
**Abhaengigkeiten:** Feature 1 (benoetigt datierten Snapshot)
**GitHub Issue:** #748

**Was:** Neuer Service `DayComparisonService` berechnet Delta-Werte zwischen zwei Listen von `SegmentWeatherData` (heute vs. gestern). Gibt ein strukturiertes `DayComparison`-DTO zurueck: pro Segment je ein `DayComparisonEntry` mit Delta-Werten und Richtungs-Enum (BETTER / WORSE / EQUAL).

**Metriken im Vergleich:** temp_min_c, temp_max_c, wind_max_kmh, gust_max_kmh, precip_sum_mm, thunder_level_max

**Richtungslogik:**
- Temperatur: kein inherentes "besser/schlechter" — nur absolutes Delta (z.B. "+3°C")
- Niederschlag: weniger = BETTER, mehr = WORSE
- Wind/Boen: weniger = BETTER, mehr = WORSE
- Gewitter: niedriger Level = BETTER, hoeher = WORSE

**Akzeptanzkriterien:**
- [ ] `DayComparisonService.compare(today_segments, yesterday_segments)` gibt `DayComparison` zurueck
- [ ] Delta-Berechnung ist korrekt fuer alle 6 Metriken
- [ ] Richtungs-Enum wird korrekt gesetzt (BETTER/WORSE/EQUAL)
- [ ] Kein Absturz wenn Segmentanzahl heute != gestern (defensiver Abgleich per Segment-ID)
- [ ] Kein Mock: Unit-Test mit echten `SegmentWeatherData`-Objekten

**Dateien:**
- `src/services/day_comparison.py` (NEW)
- `tests/tdd/test_day_comparison_service.py` (NEW)

---

#### Feature 3: Vortag-Sektion in HTML- und Plain-Renderer

**Kategorie:** Renderer (output/renderers/email)
**Scoping:** 3 Dateien, ~100 LOC, Medium
**Abhaengigkeiten:** Feature 2 (benoetigt DayComparison-DTO)
**GitHub Issue:** #749

**Was:** Neue Render-Funktionen `render_day_comparison_html(comparison)` in `html.py` und entsprechende Textform in `plain.py`. Die Sektion erscheint nur, wenn `comparison` nicht None ist. HTML zeigt eine kompakte Tabelle mit Metrik | Vortag | Heute | Delta (Pfeil + Farbe). Plain zeigt eine eingerueckte Textliste.

**Visuelles Konzept (HTML):**
```
Vergleich zum Vortag
---
Temperatur   12–18°C → 14–22°C  (+2°/+4°C)
Niederschlag  8mm    →  2mm     (-6mm)  ✓ Besser
Wind          35km/h → 28km/h   (-7km/h) ✓ Besser
Boen          55km/h → 40km/h   (-15km/h) ✓ Besser
Gewitter     Mittel  → Keines   (↓)      ✓ Besser
```

**Akzeptanzkriterien:**
- [ ] HTML-Sektion erscheint mit korrekten Delta-Werten wenn `comparison != None`
- [ ] Sektion fehlt vollstaendig wenn `comparison is None`
- [ ] BETTER = gruener Pfeil/Text, WORSE = orange/roter Pfeil, EQUAL = grau
- [ ] Plain-Text-Variante enthaelt dieselben Daten (kein HTML)
- [ ] Kontrast WCAG-AA (Designprinzip: Lesbarkeit vor Optik)
- [ ] Kein Mock: Renderer-Test mit echtem DTO

**Dateien:**
- `src/output/renderers/email/html.py` (MODIFIED)
- `src/output/renderers/email/plain.py` (MODIFIED)
- `tests/tdd/test_day_comparison_renderer.py` (NEW)

---

#### Feature 4: Scheduler-Integration und TripReportConfig-Toggle

**Kategorie:** Scheduler + Config
**Scoping:** 3 Dateien, ~60 LOC, Simple
**Abhaengigkeiten:** Feature 1, Feature 2, Feature 3
**GitHub Issue:** #750

**Was:** Der Scheduler laedt in `_send_trip_report()` vor dem Report-Versand den datierten Vortag-Snapshot (gestern), ruft `DayComparisonService.compare()` auf und reicht das Ergebnis als `day_comparison`-Argument an `TripReportFormatter.format_email()` weiter. Neues Toggle `show_yesterday_comparison: bool = True` in `TripReportConfig`. Frontend-UI-Einbindung ist OOS (separates Feature).

**Akzeptanzkriterien:**
- [ ] Scheduler laedt Vortag-Snapshot (gestern) via `WeatherSnapshotService.load_for_date()`
- [ ] Ist kein Vortag-Snapshot vorhanden: `day_comparison=None` (kein Absturz, kein Log-Spam)
- [ ] `show_yesterday_comparison=False` in TripReportConfig unterdrueckt die Sektion
- [ ] Neues `day_comparison`-Argument ist in `format_email()` optional (rueckwaertskompatibel)
- [ ] Mandantentrennung: `WeatherSnapshotService(user_id=self._user_id)` beim Laden

**Dateien:**
- `src/services/trip_report_scheduler.py` (MODIFIED)
- `src/formatters/trip_report.py` (MODIFIED)
- `src/app/models.py` (MODIFIED — TripReportConfig Toggle)

---

### P1 Features (Should Have)

---

#### Feature 5: Frontend-Toggle in E-Mail-Einstellungen

**Kategorie:** Frontend (EditReportConfigSection)
**Scoping:** 2 Dateien, ~40 LOC, Simple
**Abhaengigkeiten:** Feature 4 (Toggle in TripReportConfig muss existieren)
**GitHub Issue:** #751

**Was:** Neue Checkbox/Toggle "Vergleich zum Vortag" in der E-Mail-Einstellungen-UI (EditReportConfigSection.svelte, Gruppe "E-Mail-Inhalt"). Liest und schreibt `show_yesterday_comparison`. Persistenz via bestehendem PUT-Endpoint.

**Akzeptanzkriterien:**
- [ ] Toggle erscheint in der E-Mail-Einstellungen-UI
- [ ] Aktivieren/Deaktivieren wird persistiert (Roundtrip Backend)
- [ ] Default: eingeschaltet
- [ ] Kein Mock: Playwright-E2E auf Staging

**Dateien:**
- `frontend/src/lib/components/EditReportConfigSection.svelte` (MODIFIED)
- `tests/e2e/test_email_settings_toggle.spec.ts` (NEW)

---

### P2 Features (Nice to Have)

---

#### Feature 6: Telegram-Kurzform des Vortag-Vergleichs

**Kategorie:** Renderer (Telegram)
**Scoping:** 2 Dateien, ~50 LOC, Simple
**Abhaengigkeiten:** Feature 2 (DayComparison-DTO)
**GitHub Issue:** #752

**Was:** Kurze Textversion des Vortag-Vergleichs im Telegram-Briefing. Max. 2-3 Zeilen, nur die auffaelligsten Deltas (groesste Abweichung zuerst). Optional — nur wenn DayComparison vorhanden.

**Akzeptanzkriterien:**
- [ ] Telegram-Briefing enthaelt "Vortag:" Zeile wenn Snapshot vorhanden
- [ ] Max. 3 Metriken, absteigend nach Abweichungsgroesse sortiert
- [ ] Entfaellt komplett wenn kein Snapshot

**Dateien:**
- `src/output/renderers/narrow.py` (MODIFIED)
- `tests/tdd/test_day_comparison_telegram.py` (NEW)

---

## Implementierungs-Reihenfolge

1. **F1 #747: Datierter Snapshot-Speicher** (Fundament — keine Abhaengigkeiten)
2. **F2 #748: DayComparisonService** (benoetigt F1)
3. **F3 #749: Renderer HTML + Plain** (benoetigt F2)
4. **F4 #750: Scheduler-Integration + Toggle** (benoetigt F1, F2, F3)
5. **F5 #751: Frontend-Toggle** (benoetigt F4, P1)
6. **F6 #752: Telegram-Kurzform** (benoetigt F2, unabhaengig von F3/F4/F5, P2)

## Abhaengigkeitsgraph

```
F1 #747: Datierter Snapshot
  |
  v
F2 #748: DayComparisonService
  |
  +----> F3 #749: Renderer (HTML + Plain)
  |            |
  |            v
  +----> F4 #750: Scheduler + Toggle
               |
               v
            F5 #751: Frontend-Toggle (P1)

F2 #748 ---> F6 #752: Telegram-Kurzform (P2, unabhaengig)
```

## Geschaetzter Aufwand

- **P0 gesamt (F1-F4):** ~360 LOC, ~10 Dateien, 4 Workflow-Zyklen
- **P1 (F5):** ~40 LOC, ~2 Dateien, 1 Workflow-Zyklus
- **P2 (F6):** ~50 LOC, ~2 Dateien, 1 Workflow-Zyklus

## Wichtige technische Entscheidungen

**Snapshot-Strategie:** Kein vollstaendiger Umbau auf datierte Dateinamen. Das bestehende `{trip_id}.json` bleibt als "letzter Snapshot" fuer das Alert-System erhalten. Zusaetzlich wird ein datiertes Duplikat `{trip_id}_{YYYY-MM-DD}.json` geschrieben. Retention max. 3 datierte Dateien.

**Kein UI-Blocker fuer MVP:** Der Toggle `show_yesterday_comparison` ist in TripReportConfig bereits im Backend vorhanden. Das Frontend-Einstellungs-UI (F5 #751) ist P1, blockiert den MVP nicht.

**Segment-Matching:** Der Vergleich arbeitet auf Ebene aggregierter Segment-Metriken (SegmentWeatherSummary), nicht auf Stunden-Level. Bei unterschiedlicher Segmentanzahl (z.B. Stage-Wechsel) wird ein Best-Effort-Matching per Segment-Index durchgefuehrt. Fehlende Segmente ergeben `None`-Deltas (kein Absturz).

## Verwandte Dokumente

- Architektur: `docs/features/architecture.md`
- API-Vertrag: `docs/reference/api_contract.md`
- WeatherSnapshot Spec: `docs/specs/modules/weather_snapshot.md`
- Bestehende Change-Detection: `src/services/weather_change_detection.py`
