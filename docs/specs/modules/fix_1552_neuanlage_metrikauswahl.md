---
entity_id: fix_1552_neuanlage_metrikauswahl
type: bugfix
created: 2026-08-06
updated: 2026-08-06
status: draft
version: "1.0"
tags: [trip, trip-new, weather-metrics, register, bugfix]
---

<!-- Issue #1552 — Trip-Neuanlage verwirft die Wetter-Metrik-Auswahl still -->

# Trip-Neuanlage verwirft die Wetter-Metrik-Auswahl still

## Approval

- [ ] Approved

## Purpose

Beim Anlegen eines neuen Trips zeigt der Reiter „Wetter-Metriken" eine
Auswahl von ankreuzbaren Wettergrößen, die der Nutzer bestätigen oder
ändern kann. Diese Auswahl geht beim Speichern vollständig verloren — der
neue Trip landet immer mit einer leeren Wettergrößen-Liste in der
Datenbank, unabhängig davon, was im Dialog sichtbar angehakt war. Ein Trip
mit leerer Liste bekommt strukturell keine Wetter-Alarme. Zusätzlich zeigt
der Anlege-Dialog heute eine andere Vorbelegung (11 vorbelegte Größen) als
die, die tatsächlich in Briefings landet, wenn nie gespeichert wurde (7
Größen) — diese Spec richtet die Anzeige am wirksamen Siebener-Satz aus
(PO-Entscheidung 2026-08-06) und schließt den Speicherverlust.

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
  — fehlender Rückkanal aus dem Anlege-Modus (`createMode`); Vorbelegungs-
  Fallback bei Zeile 337
- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
  — hält `weatherMetrics = $state([])` ohne je beschrieben zu werden
  (Zeile 60), mountet `WeatherMetricsTab` zweimal (Desktop/Mobile, Zeile
  780/1005)
- **File:** `src/app/metric_catalog.py` — `MetricDefinition`-Register,
  `default_enabled`-Feld (Zeile 40), `build_default_display_config()`
  (Zeile 671)
- **File:** `src/output/renderers/trip_metric_ids.py` — hartkodierte
  `DEFAULT_TRIP_METRIC_IDS`
- **File:** `api/routers/config.py` — `GET /api/metrics` (Zeile 58)
- **File:** `frontend/src/lib/types.ts` — `MetricEntry`-Interface (Zeile
  159), Single Source of Truth für die Katalog-Antwort im Frontend

> **Schicht-Hinweis:** betrifft Frontend (`frontend/src/lib/components/...`)
> UND Python-Core (`src/app/`, `src/output/renderers/`, `api/routers/`).
> Kein Go-Anteil — `internal/handler/trip.go` wurde geprüft und braucht
> keine Änderung (s. Implementation Details).

## Estimated Scope

- **LoC:** ~45–60 Quelle, ~90–140 Tests (deutlich unter dem 250-LoC-Limit)
- **Files:** 6 geänderte Quelldateien, 2–3 Testdateien (1 bestehend
  erweitert, 1–2 neu)
- **Effort:** low-medium

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/metric_catalog.py` | MODIFY | Neues Feld `trip_default_rank: Optional[int] = None` auf `MetricDefinition`; explizit gesetzt auf den 7 Ziel-IDs (Rang 1–7) |
| `src/output/renderers/trip_metric_ids.py` | MODIFY | `DEFAULT_TRIP_METRIC_IDS` wird aus dem Register abgeleitet (sortiert nach `trip_default_rank`) statt als Literal geführt |
| `api/routers/config.py` | MODIFY | `GET /api/metrics` liefert zusätzliches Feld `trip_default_enabled` (= `trip_default_rank is not None`) je Wettergröße |
| `frontend/src/lib/types.ts` | MODIFY | `MetricEntry` bekommt `trip_default_enabled: boolean` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Neuer Prop `onWeatherMetricsChange`, neuer `$effect` (Muster `onChannelsChange`, Zeile 509-514); Vorbelegungs-Fallback (Zeile 337) liest `trip_default_enabled` statt `default_enabled` |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Neuer Handler `handleWeatherMetricsChange`, Prop an beiden `WeatherMetricsTab`-Mounts (Zeile 780, 1005) |
| `tests/unit/test_trip_metric_ids.py` | MODIFY | Bestehender Order-Test (Zeile 32-35) bleibt Regressionsschutz; neuer Test: Ableitung aus dem Register liefert dieselbe Menge/Reihenfolge |
| `tests/unit/test_metric_catalog_trip_defaults.py` (NEU) | CREATE | Register-Ebene: genau 7 IDs mit `trip_default_rank` gesetzt, korrekte Reihenfolge, alle 7 `selectable=True` |
| `frontend/.../trip-new/__tests__/*.test.ts` (erweitert oder neu) | MODIFY/CREATE | Verhaltensnachweis: eine im Anlege-Dialog sichtbar geänderte Auswahl landet im Speicher-Payload |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_trip_active_metrics()` / `DEFAULT_TRIP_METRIC_IDS` (`trip_metric_ids.py`, #1394) | intern (MODIFY) | Bestehender Fall-A/Fall-B-Mechanismus des Trip-Versands — bleibt inhaltlich unverändert, nur die Herkunft der Sieben-ID-Liste wechselt von Literal zu Register-Ableitung |
| `onChannelsChange`-Muster (`WeatherMetricsTab.svelte`/`TripNewEditor.svelte`, #622) | intern (Vorbild) | Bereits funktionierender Rückkanal für Kanal-Änderungen im Anlege-Modus — der neue Metrik-Rückkanal ist strukturell identisch |
| `get_all_metrics()` (`metric_catalog.py`) | intern (bestehend) | Filtert bereits auf `selectable=True` — Grundlage für die Ableitung von `DEFAULT_TRIP_METRIC_IDS` |
| `buildWeatherConfigMetrics()` (`metricsEditor.ts`, bestehend) | intern (unverändert) | Baut aus `buckets`/`friendlyMap` eine vollständige Metrik-Liste mit `enabled`-Flag je Katalog-Eintrag — liefert bei vollständiger Abwahl korrekt Fall B (Einträge mit `enabled=false`), nicht `[]` |
| `.claude/hooks/pendant_gate.py` (#1481 B) | Gate | Keine neu angelegte Compare-/Trip-Pendant-Datei in dieser Scheibe — nur Bestandsdateien geändert |
| `.claude/hooks/touched_tests_gate.py` (#1481 A) | Gate | Prüft `tests/unit/` der geänderten Dateien vor Commit |

## Implementation Details

### A) Fehlender Rückkanal (Kernfix)

`WeatherMetricsTab.svelte` bekommt einen neuen optionalen Prop
`onWeatherMetricsChange?: (metrics: WeatherConfigMetric[]) => void` und
einen `$effect`, der — analog zum bestehenden Kanal-Rückkanal (Zeile
509-514) — im Anlege-Modus bei jeder Änderung von `buckets`/`friendlyMap`/
`horizonsMap`/`aggregationsMap` den aktuellen Payload
(`buildWeatherPayload().metrics`) nach oben emittiert:

```
$effect(() => {
    if (createMode && onWeatherMetricsChange) {
        onWeatherMetricsChange(buildWeatherPayload().metrics);
    }
});
```

`TripNewEditor.svelte` bekommt einen Handler `handleWeatherMetricsChange`
(Muster `handleChannelsChange`, Zeile 295-297), der `weatherMetrics`
überschreibt, und übergibt ihn an beiden Mount-Stellen (Desktop Zeile 780,
Mobile Zeile 1005) als neuen Prop. `weatherMetrics` fließt danach
unverändert über `tripNewLogic.ts:buildCreateTripPayload()` (Zeile
142-145) in den POST-Body — dieser Teil ist bereits korrekt verdrahtet und
bleibt unangetastet.

Kein Endlosschleifen-Risiko: `initFromTrip()` — die Funktion, die
`buckets` aus `trip.display_config.metrics` aufbaut — läuft im
Anlege-Modus nur einmal beim ersten Laden des Katalogs (`load()`, guarded
durch `Object.keys(catalog).length === 0`, Zeile 438). Der neue Rückschreib-
Effekt ändert nur `weatherMetrics` in `TripNewEditor`, was den
`stubTrip`-Snapshot aktualisiert, aber `initFromTrip()` nicht erneut
auslöst.

### B) Register-Angleichung — geprüft, NICHT wie im Briefing vorgeschlagen umgesetzt

**Gemessene Abweichung vom vorgeschlagenen Weg** (Umsetzungsrichtung im
Auftrag: `default_enabled` global auf den Siebener-Satz umstellen):
`default_enabled` speist nicht nur die Anzeige im Trip-Anlege-Dialog,
sondern auch `build_default_display_config()` (`metric_catalog.py:671`).
Diese Funktion ist der Fallback für **jeden** Fall, in dem `display_config`
komplett `None` ist (nicht nur „Metrik-Liste leer") — Laufzeitpfad
u.a. `report_config_resolver.py:130`, `trip_report.py:121,402` — sowie
die Vorbelegung für neue Orte/Alarm-Abonnements
(`WeatherConfigDialog.svelte:51`, Route `/locations`) und wird direkt oder
indirekt von über 100 Test-Aufrufstellen (golden/characterization Tests
unter `tests/golden/`, `tests/integration/`, `tests/tdd/`) als Fixture
genutzt. Eine globale `default_enabled`-Änderung auf den Siebener-Satz
würde die Wettergrößen-Vorbelegung für Orte/Abonnements mitverändern (vom
PO nicht verlangt) und liefe Gefahr, einen zweistelligen Teil dieser Tests
rot zu ziehen — beides weit außerhalb des Umfangs dieser Scheibe.

**Gewählte Lösung:** ein neues, zusätzliches Feld
`trip_default_rank: Optional[int] = None` auf `MetricDefinition`, explizit
gesetzt auf genau den 7 Ziel-Größen (`temperature=1, wind=2, gust=3,
precipitation=4, thunder=5, freezing_level=6, visibility=7` — dieselbe
Reihenfolge wie die bisherige `DEFAULT_TRIP_METRIC_IDS`-Liste, s.
Reihenfolge-Erhalt unten). `default_enabled` bleibt für alle Größen exakt
wie heute — keine Änderung an `build_default_display_config()`, an
`WeatherConfigDialog.svelte` oder an einem der ~100 Testaufrufe.
`trip_default_rank` ist eine reine Zusatz-Markierung „gehört zum
Trip-Anlege-Standard", unabhängig von `default_enabled`.

`DEFAULT_TRIP_METRIC_IDS` in `trip_metric_ids.py` wird aus dem Register
abgeleitet:

```
DEFAULT_TRIP_METRIC_IDS: tuple[str, ...] = tuple(
    m.id for m in sorted(
        (m for m in get_all_metrics() if m.trip_default_rank is not None),
        key=lambda m: m.trip_default_rank,
    )
)
```

`GET /api/metrics` (`config.py:58`) liefert zusätzlich
`"trip_default_enabled": m.trip_default_rank is not None` je Größe (kein
Rang-Wert im Frontend nötig — die Reihenfolge des Fall-A-Rückfalls ist
reine Backend-Logik). `MetricEntry` (`types.ts:159`) bekommt das
gleichnamige Feld. `WeatherMetricsTab.svelte:337` liest
`metricById[id]?.trip_default_enabled` statt `default_enabled`.

Damit bleibt **eine Quelle** für „was ist Trip-Anlege-Standard" (das
Register, `trip_default_rank`) — sowohl der Server-Rückfall
(`DEFAULT_TRIP_METRIC_IDS`) als auch die Frontend-Vorbelegung lesen
denselben Marker, keine zweite Liste, keine Frontend-Konstante
(Struktur-Test `tripActiveMetricNames_noHardcodedVocabulary_structure.test.ts`
bleibt unverletzt).

### C) Reihenfolge-Erhalt (Regressionsschutz)

`tests/unit/test_trip_metric_ids.py:32-35` zementiert die exakte
Reihenfolge `["temperature", "wind", "gust", "precipitation", "thunder",
"freezing_level", "visibility"]`. Eine Ableitung nach Katalog-
Deklarationsreihenfolge (statt nach explizitem Rang) würde `visibility`
vor `freezing_level` einsortieren (Deklarationsreihenfolge im Register) und
diesen Test sowie die tatsächliche Spaltenreihenfolge im Briefing für
Bestandstrips ohne gespeicherte Auswahl unbeabsichtigt ändern. Der
explizite `trip_default_rank` verhindert das unabhängig von einer
künftigen Umsortierung der `MetricDefinition`-Deklarationen.

### Gemessen, betrifft diese Scheibe NICHT: Go-Handler

`internal/handler/trip.go:131-191` (`CreateTripHandler`) setzt für
`display_config.metrics` keine eigenen Defaults und normalisiert das Feld
nicht — das ist unverändert korrekt: der vollständige, bereits validierte
Payload aus dem Frontend (nach Fix A) wird 1:1 persistiert, wie bei jedem
anderen `display_config`-Feld auch.

## Expected Behavior

- **Input:** Anlege-Dialog `/trips/new`, Reiter „Wetter-Metriken" — Nutzer
  bestätigt die Vorbelegung, ändert sie, oder wählt alle Größen bewusst ab.
- **Output:** Der beim Speichern gesendete Trip enthält exakt die zuletzt
  im Dialog sichtbar angehakten Wettergrößen (bzw. bei bewusster
  Komplett-Abwahl eine vollständige Liste mit `enabled=false` je Größe,
  nicht `[]`). Die Vorbelegung im Dialog zeigt genau die 7 Größen, die auch
  ein Trip ohne je gespeicherte Auswahl tatsächlich versendet.
- **Side effects:** Bestandstrips ohne gespeicherte Auswahl ändern beim
  Öffnen im Editor ihre angezeigte Vorbelegung (von der bisherigen
  10er-Anzeige auf die 7 tatsächlich versendeten Größen) — ihr Versand
  bleibt dabei unverändert, weil er schon vorher auf denselben 7 Größen
  beruhte. Orte- und Abonnement-Konfiguration bleiben vollständig
  unberührt.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer legt einen neuen Trip an und öffnet den Reiter
  „Wetter-Metriken", ohne die vorgeschlagene Auswahl zu verändern / When er
  den Trip speichert / Then enthält der gespeicherte Trip genau die 7
  vorgeschlagenen Wettergrößen (Temperatur, Wind, Böen, Niederschlag,
  Gewitter, Nullgradgrenze, Sichtweite) als aktiviert, und sein erstes
  Briefing zeigt exakt diese 7 Größen.
  - Test: Anlege-Dialog durchlaufen ohne die Wetter-Auswahl anzufassen,
    speichern, gespeicherten Trip-Datensatz UND ein daraus gerendertes
    Briefing prüfen — kein Dateiinhalt-Check.

- **AC-2:** Given ein Nutzer hakt beim Anlegen zusätzliche Wettergrößen an
  oder bestehende ab, bevor er speichert / When der Trip gespeichert wird /
  Then enthält der gespeicherte Trip genau die beim Speichern sichtbar
  angehakten Größen — nicht die ursprüngliche Vorbelegung und nicht eine
  leere Liste.
  - Test: im Anlege-Dialog mindestens eine Größe zusätzlich anhaken und
    eine vorbelegte abwählen, speichern, gespeicherten Trip-Datensatz
    prüfen.

- **AC-3:** Given ein Nutzer hakt beim Anlegen alle Wettergrößen bewusst ab
  / When der Trip gespeichert wird / Then wird diese bewusste Leerauswahl
  übernommen — das erste Briefing zeigt keinen
  Wettergrößen-Überblicksblock, nicht die 7 Standardgrößen.
  - Test: im Anlege-Dialog alle Größen abwählen, speichern, ein daraus
    gerendertes Briefing prüft das Fehlen des Überblicksblocks.

- **AC-4:** Given ein Trip, der vor diesem Fix ohne gespeicherte
  Wettergrößen-Auswahl angelegt wurde / When sein Briefing erzeugt wird /
  Then zeigt es weiterhin genau dieselben 7 Standardgrößen wie vor dieser
  Änderung — der tatsächliche Versand ändert sich für solche Bestandstrips
  nicht.
  - Test: bestehenden Trip-Datensatz mit fehlender/leerer Metrik-Liste
    rendern, Ergebnis vor und nach dem Fix vergleichen.

- **AC-5:** Given derselbe Bestandstrip wie AC-4 / When ihn ein Nutzer im
  Editor öffnet / Then zeigt der Reiter „Wetter-Metriken" jetzt genau die 7
  tatsächlich versendeten Größen als angehakt — nicht mehr die bisher
  zusätzlich angezeigten, aber nie versendeten Größen.
  - Test: Editor mit einem Bestandstrip ohne gespeicherte Auswahl öffnen,
    angezeigte angehakte Größen prüfen.

- **AC-6:** Given ein Trip, bei dem ein Nutzer zuvor bewusst alle
  Wettergrößen abgewählt und gespeichert hat / When er im Editor geöffnet
  wird / Then zeigt der Reiter weiterhin „alles aus" — die Vorbelegung mit
  den 7 Standardgrößen darf diese bereits gespeicherte, bewusste
  Entscheidung nicht überschreiben.
  - Test: Editor mit einem Trip öffnen, dessen gespeicherte Metrik-Liste
    Einträge mit durchgehend `enabled=false` enthält; angezeigte Auswahl
    muss leer bleiben.

- **AC-7:** Given die Wetter-Einstellungen für einen Ort oder ein
  Alarm-Abonnement / When ein Nutzer dort eine neue Konfiguration anlegt /
  Then bleibt die dort vorgeschlagene Wettergrößen-Auswahl exakt wie vor
  diesem Fix — sie ist nicht Teil dieser Änderung.
  - Test: Orte-/Abonnement-Konfigurationsdialog vor und nach dem Fix
    vergleichen, keine Abweichung in der vorgeschlagenen Auswahl.

- **AC-8:** Given der Server / When das Frontend die Liste der
  Wettergrößen abruft / Then bezieht das Frontend die Information „gehört
  zur Trip-Vorbelegung" ausschließlich aus dieser Serverantwort — ohne eine
  eigene, fest im Frontend-Code stehende Liste von Wettergrößen-Namen.
  - Test: bestehender Struktur-Test
    `tripActiveMetricNames_noHardcodedVocabulary_structure.test.ts` bleibt
    grün.

## Nicht in dieser Scheibe

- **`default_enabled` global umstellen** — geprüft und bewusst verworfen
  (s. Implementation Details B): zu großer Blast Radius (Orte/Abonnements,
  `build_default_display_config()`, >100 Testaufrufstellen). Eine
  eigenständige Änderung, falls der PO die Orte/Abo-Vorbelegung später
  ebenfalls auf den Siebener-Satz ausrichten will.
- **Ortsvergleich-Anlage (`/compare/new`, `CompareNewEditor.svelte`)** —
  gemessen: `WeatherMetricsTab` läuft dort ohne `createMode` und
  persistiert die Vergleichs-Metrik-Auswahl über einen eigenen
  `wiz.activeMetricKeys`-Mechanismus (CompareTabs Hub-Hydrate/-Flush,
  `toggleCompareMetric`), nicht über den hier reparierten Rückkanal — die
  exakte Fehlerklasse aus #1552 tritt dort strukturell nicht in derselben
  Form auf. Unklar geblieben (nicht abschließend gemessen): ob die
  ebenfalls im Vergleichs-Anlege-Kontext sichtbare „02 — Grundauswahl"-
  Karte (dieselbe Komponente, Toggle-Pfad über `buckets`/`onToggleMetric`)
  dort tatsächlich wirkungslos ist. Eigener Prüfauftrag empfohlen, kein
  Teil dieser Scheibe.
- **`temperature_cold`** behält implizites `default_enabled=True`, obwohl
  es wegen `selectable=False` nirgends in einer Auswahl-UI erscheint —
  kosmetischer Bestand, unverändert seit vor diesem Fix.
- **Neue Alarm-Regeln für neu angelegte Trips** — dass ein Trip mit
  aktivierten Größen jetzt auch tatsächlich Alarme bekommen kann, ist eine
  Folge dieses Fixes, aber keine eigene AC dieser Scheibe (die
  Alarm-Erzeugung selbst ist unverändertes Bestandsverhalten, s.
  `tests/tdd/test_issue_946_alert_architecture.py`).

## Test Plan

Test-Politik (CLAUDE.md „Zwei Schichten"): Kern-Tests deterministisch ohne
Netz/Live-Dienste sind Pflicht. Keine neuen Testdateien mit Issue-Nummer im
Namen.

### Automated Tests (TDD RED)

- [ ] Test 1 (Python, Register): GIVEN das Metrik-Register / WHEN
  `get_all_metrics()` nach `trip_default_rank` gefiltert wird / THEN sind
  es genau 7 Einträge, alle `selectable=True`, in der Reihenfolge
  temperature, wind, gust, precipitation, thunder, freezing_level,
  visibility.
- [ ] Test 2 (Python, Ableitung): GIVEN `trip_metric_ids.py` / WHEN
  `DEFAULT_TRIP_METRIC_IDS` importiert wird / THEN entspricht es exakt der
  bisherigen Literal-Liste (Regressionsschutz gegen den bestehenden
  Order-Test `test_trip_metric_ids.py:32-35`).
- [ ] Test 3 (Frontend, Rückkanal-Verhalten): GIVEN `WeatherMetricsTab` im
  Anlege-Modus mit `onWeatherMetricsChange` / WHEN eine Wettergröße
  an-/abgewählt wird / THEN wird der Callback mit der aktualisierten
  Metrik-Liste aufgerufen (nicht nur „Komponente rendert", sondern
  konkreter Payload-Inhalt).
- [ ] Test 4 (Frontend, End-to-End der Anlage): GIVEN den Anlege-Flow in
  `TripNewEditor.svelte` / WHEN eine Größe abgewählt und gespeichert wird /
  THEN enthält der an `buildCreateTripPayload()` übergebene State genau die
  angepasste Auswahl (nicht die anfängliche `[]`).
- [ ] Test 5 (Frontend, API-Feld): GIVEN die `/api/metrics`-Antwort / WHEN
  `metricById[id].trip_default_enabled` für die Vorbelegung im
  Anlege-Dialog gelesen wird / THEN zeigt der Dialog ohne Nutzereingriff
  genau die 7 Größen als angehakt an.
- [ ] Test 6 (Regression, dritter Zustand): GIVEN ein Trip mit gespeicherter,
  vollständig deaktivierter Metrik-Liste / WHEN der Editor ihn lädt / THEN
  bleibt die Anzeige „alles aus" (kein Rückfall auf `trip_default_enabled`).
- [ ] Test 7 (Regression, Orte/Abo unberührt): GIVEN
  `WeatherConfigDialog.svelte` (Orte/Abonnements) / WHEN eine neue
  Konfiguration angelegt wird / THEN bleibt die vorgeschlagene Auswahl
  identisch zum Stand vor diesem Fix (`default_enabled` unverändert).

### Live-E2E (Staging, vor „E2E bestanden")

Neuer Trip über den echten Anlege-Dialog auf Staging anlegen, Auswahl
NICHT verändern, speichern, erstes Briefing per IMAP abrufen und mit
`.claude/hooks/briefing_mail_validator.py` gegen die erwarteten 7
Standardgrößen prüfen (AC-1). Zweiter Durchlauf: alle Größen im
Anlege-Dialog bewusst abwählen, Briefing zeigt keinen
Wettergrößen-Überblicksblock (AC-3).

## Known Limitations

- `trip_default_rank` ist eine reine Zusatz-Markierung, unabhängig von
  `default_enabled` — beide Felder müssen künftig unabhängig gepflegt
  werden, falls sich die Zielmenge des einen oder anderen ändert; es gibt
  keinen automatischen Abgleich zwischen ihnen.
- Der Ortsvergleich-Anlage-Pfad (`/compare/new`) wurde nur soweit
  gemessen, wie nötig war um festzustellen, dass die exakte Fehlerklasse
  aus #1552 dort strukturell nicht auftritt — eine vollständige Prüfung
  des dortigen Grundauswahl-Kartenverhaltens ist offen (s. „Nicht in dieser
  Scheibe").
- Migrierte Bestandstrips ohne gespeicherte Auswahl zeigen nach diesem Fix
  im Editor eine andere (kleinere) Vorbelegung als vorher — gewollte
  Konsequenz der PO-Entscheidung „eine Quelle", kein Fehler.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe repariert eine fehlende Datenweiterleitung
  im Anlege-Flow und gleicht eine Register-Zusatzmarkierung an einen
  bereits bestehenden, dokumentierten Server-Vertrag
  (`DEFAULT_TRIP_METRIC_IDS`, ADR-los seit #1394) an. Keine neue
  Architektur-, Kanal- oder Persistenzentscheidung.

## Changelog

- 2026-08-06: Initial spec erstellt — Issue #1552.
