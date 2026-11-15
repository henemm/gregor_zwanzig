---
entity_id: fix_2946_sichtweite_einheit
type: bugfix
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: fix-2946-sichtweite-einheit
tags: [wetter-reiter, sichtweite, einheit, api-metrics]
---

# Sichtweite-Einheit im Wetter-Reiter korrigieren (Bug #2946)

## Approval

- [ ] Approved

## Purpose

Im Wetter-Reiter (Trip und Orts-Briefing) zeigt die Zeile "Sichtweite" Meter-Grenzwerte mit der Einheit "km" (z. B. "unter 300 km", "grün: ab 1000 km"). Die Grenzwerte sind in Meter gespeichert; die Texte müssen daher in Meter laufen, wie im Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` ("m · Minimum", "ab 1000 m"). Layout und Mail-Spaltenköpfe zeigen weiterhin km.

## Source

- **File:** `api/routers/config.py` (Python-Core, `GET /api/metrics`) und `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` (Frontend)
- **Identifier:** Metrik-Liste in `GET /metrics` (Feld `unit`, neu `threshold_unit`); `eigenschaftenAusKatalog`, `gruenZeile`, `untertitel`, `erklaersatz`

Ursache: `GET /metrics` liefert `unit = display_unit or unit`. Für `visibility` ist `unit="m"`, `display_unit="km"` (`src/app/metric_catalog.py`), das API-Feld `unit` also "km". `ampelModell.ts` setzt diese Einheit in Grünzeile, Untertitel und Erklärsatz ein, die Ampel-Grenzwerte liegen aber in der Speicher-Einheit (Meter).

## Estimated Scope

- **LoC:** +40/-5
- **Files:** 5
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` | module | Quelle von `unit` (Speicher-Einheit) und `display_unit`; bleibt unverändert |
| `internal/router/router.go` | module | Go-Proxy reicht die Antwort ohne Struct durch, neues Feld kommt ohne Go-Änderung an |
| `frontend/.../wetter-tab/wetterTabLaden.ts` | module | Aufrufer von `eigenschaftenAusKatalog` |
| `frontend/.../trip-detail/HubOverview.svelte` | module | Aufrufer von `eigenschaftenAusKatalog` (zeigt keine Einheit im Text) |
| `frontend/src/routes/_home/homeHeroProps.ts` | module | Aufrufer von `eigenschaftenAusKatalog` |
| `frontend/.../organisms/wetter-tab/MetrikZeile.svelte` | component | Zeigt die drei Texte an (keine Änderung) |
| `docs/reference/api_contract.md` | doc | SSOT der DTOs, Feld wird dokumentiert |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/config.py` | MODIFY | additives Feld `threshold_unit: m.unit` je Metrik in `GET /metrics`; `unit` bleibt unverändert |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | MODIFY | `MetrikEigenschaften.threshold_unit`; `eigenschaftenAusKatalog` liest es (Rückfall auf `unit`); Grünzeile, Untertitel, Erklärsatz nutzen die Grenzwert-Einheit |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/ampelModell.test.ts` | MODIFY | falsche Erwartung (Z. 200, `einheit: 'km'`) auf `'m'`; neuer Test aus echter Katalog-Antwort-Form |
| `tests/unit/test_metrics_endpoint_threshold_unit.py` | CREATE | pytest für `threshold_unit` (visibility und alle übrigen Metriken) |
| `docs/reference/api_contract.md` | MODIFY | Feld `threshold_unit` in der Zeile `/api/metrics` dokumentieren |

### Estimated Changes

- Files: 5
- LoC: +40/-5

## Implementation Details

Option A (gewählt, Mockup-konform): Meter durchgehend, über ein additives API-Feld.

1. `GET /metrics` liefert je Metrik zusätzlich `threshold_unit` = Katalog-`unit` (Einheit, in der die Ampel-Grenzwerte gespeichert sind). `unit` bleibt die Anzeige-Einheit (`display_unit or unit`) für Layout, Spaltenköpfe und Mail-Vorschau (Abnehmer: `ActiveMetricRow`, `BucketSectionOff`, `MetricOffShelf`, `WeatherV2Reihenfolge`, `WeatherConfigDialog`, `TablePreview`).
2. `eigenschaftenAusKatalog` übernimmt `threshold_unit` in die Metrik-Eigenschaften; fehlt das Feld (ältere Antwort), gilt `unit` als Rückfall.
3. `gruenZeile`, `untertitel` und `erklaersatz` verwenden die Grenzwert-Einheit statt `unit`. Das sind die einzigen drei Verwendungen von `MetrikEigenschaften.unit`.
4. Das Einheiten-Token "m" ist sprachneutral und wird nicht über den Katalog übersetzt (ADR-0104) ⇒ DE und EN zeigen dasselbe "m".
5. Alle übrigen Metriken haben keine `display_unit`; dort ist `threshold_unit == unit`, ihr Verhalten ändert sich nicht.

Verworfen: B (km mit Umrechnung) widerspricht dem Mockup, erzeugt Bruchzahlen (0,3 km) und braucht Umrechnung auch bei der Eingabe. C (im Frontend `visibility` hart auf "m") ist Sonderfall-Hartkodierung statt Katalog als Quelle.

Nicht betroffen: Ampel-Leiste (zeigt nur Zahlen), Korridor-/Vergleichs-Editor (`compareMetricCatalogLoader.ts`, eigener Katalog), Go-Code.

Trip/Ortsvergleich-Teilung: Die Änderung liegt in `shared/wetter-tab`, Trip und Orts-Briefing erhalten sie mit demselben Code. Kanäle: keine Briefing- oder Alarm-Inhalte betroffen (nur Editor-Texte).

## Expected Behavior

- **Input:** Katalog-Antwort von `GET /api/metrics` mit `visibility: unit="km", threshold_unit="m"`.
- **Output:** In der Sichtweite-Zeile: Untertitel "m · Minimum" (DE/EN gleiches Token), Grünzeile "ab 1000 m", Erklärsatz mit "m" (z. B. "unter 300 m"). Alle anderen Zeilen unverändert.
- **Side effects:** keine; `unit` bleibt, nur ein Feld kommt hinzu.

## Test Plan

Kern-Schicht (deterministisch, ohne Netz, benannte Dateien; kein Mock-Theater, die Frontend-Eingabe ist die Antwort-Form der echten API, nicht eine handgeschriebene Eigenschaft):

### Automated Tests (TDD RED)

- [ ] **node --test** `frontend/src/lib/components/shared/wetter-tab/__tests__/ampelModell.test.ts`: GIVEN Katalog-Antwort im echten API-Format (visibility `unit="km"`, `threshold_unit="m"`), über `eigenschaftenAusKatalog` eingelesen / WHEN Grünzeile, Untertitel und Erklärsatz gebildet werden / THEN enthalten alle drei "m" und keines "km" (rot vor dem Fix).
- [ ] **node --test** gleiche Datei: GIVEN Antwort ohne `threshold_unit` (ältere API) / WHEN Texte gebildet werden / THEN Rückfall auf `unit`.
- [ ] **node --test** gleiche Datei: GIVEN Metrik ohne `display_unit` (z. B. Temperatur) / WHEN Texte gebildet werden / THEN Einheit unverändert.
- [ ] **node --test** gleiche Datei: bestehende Erwartung `{ ab: 2000, einheit: 'km' }` auf `'m'` korrigiert.
- [ ] **pytest** `uv run pytest tests/unit/test_metrics_endpoint_threshold_unit.py`: GIVEN die echte FastAPI-App (TestClient) / WHEN `GET /metrics` / THEN visibility hat `unit="km"` und `threshold_unit="m"`; für jede andere Metrik gilt `threshold_unit == unit`.
- [ ] **E2E auf Staging** (`/e2e-verify`, Playwright): GIVEN Trip und Orts-Briefing mit Sichtweite / WHEN Wetter-Reiter geöffnet, Sprache DE und EN / THEN Sichtweite-Zeile zeigt "m"; Layout-Reiter zeigt weiterhin "km".

## Definition of Done

- [ ] AC-1, AC-3, AC-5, AC-7 durch den Modell-Test (node --test) mit Katalog-Antwort im echten API-Format belegt, vor dem Fix rot nachgewiesen, Kern-Schicht grün
- [ ] AC-4 und AC-6 durch den pytest gegen die FastAPI-App belegt (visibility `unit="km"`, `threshold_unit="m"`; sonst `threshold_unit == unit`)
- [ ] AC-1 bis AC-4 auf Staging belegt (Trip und Orts-Briefing, Sprache DE und EN, Layout-Reiter weiterhin km)
- [ ] `threshold_unit` in `docs/reference/api_contract.md` dokumentiert
- [ ] Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Sichtweite im Wetter-Reiter / When der Nutzer die Zeile Sichtweite ansieht / Then zeigt der Untertitel "m · Minimum", die Grünzeile "ab 1000 m" und der Erklärsatz einen Meter-Wert mit "m", an keiner dieser Stellen steht "km".
  - Test: Wetter-Reiter eines Trips auf Staging öffnen, Sichtweite-Zeile lesen; Modell-Test mit Katalog-Antwort im echten API-Format.

- **AC-2:** Given ein Orts-Briefing (Ortsvergleich) mit Sichtweite / When der Nutzer den Wetter-Reiter öffnet / Then zeigt die Sichtweite-Zeile dieselben Meter-Angaben wie beim Trip, da beide denselben Code nutzen.
  - Test: Wetter-Reiter eines Orts-Briefings auf Staging öffnen und mit der Trip-Zeile vergleichen.

- **AC-3:** Given die Oberfläche steht auf Englisch / When der Nutzer die Sichtweite-Zeile ansieht / Then erscheint ebenfalls "m" (nicht "km"), und die Sprache DE zeigt dieselbe Einheit "m".
  - Test: Nutzersprache DE und EN umschalten, Sichtweite-Zeile in beiden Sprachen prüfen.

- **AC-4:** Given die Sichtweite wird im Layout-Reiter oder in der Mail-Vorschau mit Spaltenkopf angezeigt / When der Nutzer sie öffnet / Then steht dort weiterhin "km".
  - Test: Layout-Reiter auf Staging öffnen, Einheit der Sichtweite-Spalte prüfen; API-Test: `unit="km"` bleibt für visibility.

- **AC-5:** Given Metriken ohne abweichende Anzeige-Einheit (z. B. Temperatur, Wind, Niederschlag) / When der Nutzer deren Zeilen im Wetter-Reiter ansieht / Then bleiben Untertitel, Grünzeile und Erklärsatz unverändert zum bisherigen Stand.
  - Test: Modell-Test mit Nicht-Sichtweite-Metriken; pytest: für alle Metriken außer visibility gilt `threshold_unit == unit`.

- **AC-6:** Given der Python-Core läuft / When die Metrik-Liste über `GET /api/metrics` abgerufen wird / Then enthält jede Metrik zusätzlich das Feld `threshold_unit` (für Sichtweite "m", Anzeige-Einheit `unit` weiter "km").
  - Test: pytest gegen die FastAPI-App, Antwort auf `threshold_unit` und `unit` prüfen.

- **AC-7:** Given eine ältere API-Antwort ohne `threshold_unit` / When der Wetter-Reiter die Texte bildet / Then fällt er auf `unit` zurück und zeigt keinen Fehler und keine leere Einheit.
  - Test: Modell-Test mit Antwort ohne das neue Feld.

## Known Limitations

- Die Anzeige-Einheit im Layout bleibt km, im Wetter-Reiter gilt m; das ist gewollt (Mockup) und beruht auf zwei getrennten Feldern.
- Neue Metriken mit abweichender `display_unit` werden automatisch über `threshold_unit` richtig behandelt, brauchen keine Frontend-Sonderfälle.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additives API-Feld im bestehenden Muster (`label_de`/`label_en`), keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth) berührt; Einheiten-Token bleibt sprachneutral gemäß ADR-0104.

## Changelog

- 2026-11-15: Initial spec created (Issue #2946)
