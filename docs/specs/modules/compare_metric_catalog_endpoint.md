---
entity_id: compare_metric_catalog_endpoint
type: feature
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [compare, metrics, api, ssot]
workflow: fix-1350-compare-metric-catalog-source
---

# Compare-Metrik-Katalog-Endpoint

## Approval

- [ ] Approved

## Purpose

Ein neuer, read-only Backend-Endpoint (`GET /api/compare/metrics`) liefert den vollständigen
Ortsvergleich-Metrik-Katalog (25 Einträge inkl. Label/Einheit/Wertebereich/`higherIsBetter`/
Ordinal-Angaben) aus einer einzigen Backend-Quelle. Er löst Teil 1 von Issue #1350
(Strangler-Migration): das Backend wird zur autoritativen Quelle für den Compare-Katalog,
bevor in Teil 2 der Frontend-Konsument (`compareMetricDefs.ts::ALL_METRICS`) darauf
umgestellt wird. In Teil 1 wird der Endpoint **nur bereitgestellt, noch nicht konsumiert** —
das heutige Frontend-Verhalten bleibt unverändert (kein Risiko für die Editor-UI).

## Source

- **File:** `src/output/renderers/compare_metric_catalog.py` (NEU)
- **Identifier:** `COMPARE_METRIC_CATALOG` (Liste), `get_compare_metric_catalog()`

> Schicht-Hinweis: Katalog-Daten + FastAPI-Endpoint liegen im Python-Core
> (`src/output/renderers/`, `api/routers/compare.py`). Der Go-Proxy-Eintrag liegt in
> `internal/router/router.go` (reiner Passthrough, kein neuer Go-Handler nötig —
> bestehender generischer `handler.ProxyHandler` wird wiederverwendet).

## Estimated Scope

- **LoC:** ~200–240 (Katalog-Daten + Endpoint + Go-Route + Tests; `api_contract.md` zählt
  laut Projektkonvention nicht mit). Passt voraussichtlich unter das 250-LoC-Workflow-Limit;
  falls die Parity-Fixture im Test die Grenze reißt, ist ein kleiner, PO-genehmigter
  LoC-Override die richtige Reaktion — kein Kürzen der Katalog-Daten oder der Testtiefe.
- **Files:** 5 (1 neu: `compare_metric_catalog.py`; 4 geändert: `api/routers/compare.py`,
  `internal/router/router.go`, `docs/reference/api_contract.md`, plus 1 Python- und 1
  Go-Testdatei)
- **Effort:** medium (reine Daten+Endpoint-Arbeit, aber die Parität mit zwei bestehenden
  Frontend-Quellen muss exakt und vollständig sein — kein Feld darf fehlen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID` | module | Bestehende autoritative 25-Key-Liste — Katalog-Keys MÜSSEN mit diesen Keys identisch sein (keine sechste Kopie der Keyliste) |
| `frontend/.../compare/compareMetricDefs.ts::ALL_METRICS` | frontend module | Referenzquelle für Label/Unit/Decimals/Range/`higherIsBetter`/`kind`/`enumValues` — Parity-Fixture im Test |
| `frontend/.../shared/corridor-editor/corridorEditorState.ts::COMPARE_METRIC_DEFS` | frontend module | Referenzquelle für die Thunder-Sonderbehandlung (`kind: 'ordinal'`, `ordinalLabels: ['kein','mittel','hoch']`) |
| `api/routers/config.py::get_metrics` | module | Bestehendes Endpoint-Muster (Response-Form, kein `user_id`-Bezug, da statischer Katalog) |
| `internal/router/router.go` (`/api/metrics`, `/api/sms-symbols`) | module | Bestehendes Proxy-Registrierungsmuster (`handler.ProxyHandler`, keine Auth-Sonderlogik) |

## Implementation Details

**1. Katalog-Datenquelle (neu, additiv):** `src/output/renderers/compare_metric_catalog.py`
definiert exakt 25 Einträge als expliziten, angereicherten Datensatz (KEINE Ableitung aus
`MetricDefinition.summary_fields` — 5 Keys `sunny_hours_h`/`snowfall_limit_m`/
`cloud_low_avg_pct`/`cloud_mid_avg_pct`/`cloud_high_avg_pct` haben dort keine passenden
Felder; der Temp-Min/Max-Split ist Compare-eigen). Pro Eintrag:
`key, label, unit, decimals, higherIsBetter, kind, rangeMin, rangeMax, step, enumValues,
ordinalLabels`. Feldnamen der JSON-Antwort werden bewusst camelCase gehalten (statt des
sonst üblichen snake_case in `/api/metrics`), damit die Struktur 1:1 dem Frontend-Interface
`MetricDef`/`CompareMetricDef` entspricht — das minimiert die Mapping-Arbeit in Teil 2.

**2. `kind`-Auflösung (SSoT-Entscheidung, löst eine bestehende Frontend-Inkonsistenz):**
`compareMetricDefs.ts::ALL_METRICS` führt `thunder_level_max` als `kind: 'enum'`
(`enumValues: ['NONE','MED','HIGH']`), aber `corridorEditorState.ts` überschreibt es beim
Rendern zu `kind: 'ordinal'` (`ordinalLabels: ['kein','mittel','hoch']`) — so wird es dem
Nutzer tatsächlich angezeigt (3-Stufen-Band statt Enum-Dropdown, PO-Entscheidung
2026-07-12). Der Katalog übernimmt die tatsächlich sichtbare Form: `thunder_level_max` bekommt
`kind: 'ordinal'` + `ordinalLabels`, kein `enumValues`. `precip_type_dominant` bleibt
`kind: 'enum'` mit `enumValues: ['RAIN','SNOW','MIXED','FREEZING_RAIN']` (hier gibt es keine
abweichende Editor-Darstellung). Alle übrigen 23 Keys sind `kind: 'range'` mit
`rangeMin/rangeMax/step` aus `ALL_METRICS`.

**3. Keys = 1:1 `FRONTEND_TO_RENDERER_METRIC_ID`-Keys.** Der Katalog importiert die Keyliste
aus `compare_metric_ids.py` (nicht neu abtippen) und reichert sie um die Präsentationsfelder
an — das verhindert eine sechste Kopie der Keyliste und macht künftige Drift (wie #1324)
strukturell unmöglich: fehlt ein Key im Katalog, schlägt ein Test fehl.

**4. Endpoint:** `api/routers/compare.py` bekommt `GET /api/compare/metrics` (Datei nutzt
bereits das Muster voller `/api/...`-Pfade, z.B. `@router.get("/api/compare")` — kein neues
Router-Modul nötig). Response: `{"metrics": [...]}` (25 Einträge, camelCase-Felder).

**5. Go-Proxy:** `internal/router/router.go` bekommt eine Zeile analog `/api/metrics`:
```
r.Get("/api/compare/metrics", handler.ProxyHandler(deps.Config.PythonCoreURL, "/api/compare/metrics"))
```
Kein neuer Go-Handler — der generische `ProxyHandler(pythonURL, path)` reicht (kein
`user_id`-Bezug, da statischer Katalog, kein Nutzerdaten-Zugriff — analog `/api/metrics`,
`/api/templates`, `/api/sms-symbols`).

**6. `docs/reference/api_contract.md`:** neue Zeile in der Endpoint-Übersichtstabelle
(`| /api/compare/metrics | GET |`) plus ein eigener Abschnitt mit Response-DTO (analog
Abschnitt "GET /api/metrics"), inkl. Changelog-Eintrag.

**Explizit NICHT Teil dieser Spec:** keine Änderung an `compareMetricDefs.ts`,
`corridorEditorState.ts` oder einem der vier Frontend-Konsumenten; kein Umbau von
`active_metrics`/`corridors`-Persistenz; kein Ersetzen von `compare_metric_ids.py`s
ID-Resolver-Logik (`resolve_enabled_metrics` bleibt unverändert).

## Expected Behavior

- **Input:** `GET /api/compare/metrics` ohne Parameter (öffentlicher, aber
  session-authentifizierter Katalog-Read wie `/api/metrics` — kein `user_id`-Query nötig, da
  keine nutzerspezifischen Daten).
- **Output:** `{"metrics": [ {...25 Einträge...} ]}`, Reihenfolge deckungsgleich mit
  `ALL_METRICS`-Reihenfolge im Frontend (erleichtert visuellen Diff in Teil 2).
- **Side effects:** keine (rein lesend, keine Persistenz, kein State).

## Acceptance Criteria

- **AC-1:** Given der Python-Core läuft / When `GET /api/compare/metrics` über die Go-API
  aufgerufen wird / Then liefert die Antwort eine flache Liste mit genau 25 Metrik-Einträgen
  unter dem Schlüssel `metrics`.
  - Test: Kern-Test ruft den FastAPI-Endpoint (TestClient, kein Netz) auf und zählt
    `len(response["metrics"]) == 25`.

- **AC-2:** Given ein einzelner Katalog-Eintrag / When er inspiziert wird / Then trägt er
  alle Editor-Felder (`key, label, unit, decimals, higherIsBetter, kind`) plus — abhängig von
  `kind` — `rangeMin/rangeMax/step` (bei `range`), `enumValues` (bei `enum`, z.B.
  `precip_type_dominant`) oder `ordinalLabels` (bei `ordinal`, z.B. `thunder_level_max` mit
  `['kein','mittel','hoch']`).
  - Test: Kern-Test prüft für alle 25 Einträge Feld-Vollständigkeit passend zu ihrem `kind`
    (kein Eintrag ohne die für seinen `kind` erforderlichen Felder).

- **AC-3:** Given die heutige Frontend-Quelle `compareMetricDefs.ts::ALL_METRICS` (25
  Einträge, eingefroren als Test-Fixture) / When die 25 Katalog-Einträge des Endpoints
  dagegen verglichen werden / Then stimmen Key-Menge, Label, `higherIsBetter`, `kind` sowie
  `rangeMin`/`rangeMax` (wo vorhanden) für jeden der 25 Keys exakt überein — inklusive des
  Temp-Min/Max-Splits und der 5 nicht aus `summary_fields` ableitbaren Keys
  (`sunny_hours_h`, `snowfall_limit_m`, `cloud_low_avg_pct`, `cloud_mid_avg_pct`,
  `cloud_high_avg_pct`).
  - Test: Kern-Test vergleicht den Endpoint-Output gegen eine eingefrorene 25-Einträge-Liste
    (Key + Kernfelder) im Test-File — kein Dateiinhalt-Grep, sondern strukturierter
    Wertevergleich.

- **AC-4:** Given der neue Endpoint existiert / When das bestehende Compare-Editor-Frontend
  (`WeatherMetricsTab`, `CorridorEditor`, Wizard) unverändert weiterläuft / Then zeigt es
  weiterhin exakt dieselben 25 Metriken aus `compareMetricDefs.ts::ALL_METRICS` — der neue
  Endpoint wird in Teil 1 nicht konsumiert, es gibt keine sichtbare Änderung im Editor.
  - Test: bestehende Frontend-/E2E-Tests für den Ortsvergleich-Editor bleiben unverändert
    grün (Regressionsschutz, kein neuer Test nötig — Abwesenheit einer Regression wird durch
    unveränderten bestehenden Testlauf belegt).

- **AC-5:** Given eine authentifizierte Session gegen die Go-API / When
  `GET /api/compare/metrics` aufgerufen wird / Then leitet der Go-Proxy die Anfrage an den
  Python-Core-Pfad `/api/compare/metrics` weiter und gibt dessen Antwort unverändert zurück
  (Status + Body), analog zum bestehenden `/api/metrics`-Proxy.
  - Test: Go-Router-Test mit lokalem `httptest.NewServer`-Mock als `PythonCoreURL` prüft,
    dass eine Anfrage an `/api/compare/metrics` beim Mock unter `/api/compare/metrics`
    ankommt und dessen Antwort 1:1 durchgereicht wird (kein Live-Netz, kein echter
    Python-Core nötig).

## Known Limitations

- Teil 1 liefert nur den Endpoint — die Doppelpflege (`compareMetricDefs.ts` ↔
  `compare_metric_ids.py`) besteht bis Teil 2 (Frontend-Umstellung) weiter fort. Bis dahin
  bleibt das Risiko einer stillen Drift wie #1324 bestehen; Teil 1 mindert es nicht, sondern
  bereitet nur die Migration vor.
- `precip_type_dominant` wird weiterhin als `enum` geführt, obwohl der bestehende
  Corridor-Editor-Code (`corridorEditorState.ts`) es intern durch den generischen
  `'range'`-Zweig statt eines Enum-Zweigs schleust (Scale-Default `[0,100]`) — eine
  bestehende Frontend-Eigenart, die dieser Endpoint korrekt als `enum` abbildet, aber nicht
  repariert (außerhalb des Scopes von Teil 1).
- Kein Caching/Versionierung des Katalogs — bei zukünftigen Änderungen an den 25 Einträgen
  muss die Parity-Fixture in Teil 1 UND die Frontend-Quelle synchron aktualisiert werden,
  bis Teil 2 den Frontend-Konsum umstellt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additiver, rein lesender Katalog-Endpoint ohne Persistenz-, Auth-, Provider-
  oder Kanal-Änderung — keine der in `docs/adr/README.md` gelisteten Entscheidungsflächen ist
  betroffen. Die grundsätzliche SSoT-Migrationsrichtung (Backend als autoritative Quelle für
  Compare-Metrik-Präsentation) ist Teil der laufenden Konvergenz-Richtung (Epic #1230), keine
  neue Grundsatzentscheidung.

## Changelog

- 2026-07-23: Initial spec created (Teil 1 von 3, Issue #1350, Strangler-Migration)
