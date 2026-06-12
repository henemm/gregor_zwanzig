---
entity_id: issue_774_metrics_summary_persist
type: module
created: 2026-06-12
updated: 2026-06-12
status: implemented
version: "1.0"
tags: [bug, frontend, trip-editor, report-config, persistence]
---

# Issue #774 — Metriken-Überblick Checkbox persistieren + Einklapp-Element entfernen

## Approval

- [x] Approved (2026-06-12)

## Purpose

Im „Metriken"-Reiter eines Trips wird die „E-Mail-Inhalt"-Karte gerendert, deren
Checkbox „Metriken-Überblick" (`report_config.show_metrics_summary`) jedoch beim
Speichern nicht persistiert wird — der Reiter sendet nur `display_config`. Dieser
Bug behebt die Persistenz und entfernt zusätzlich das überflüssige
„Inhalts-Bausteine (N aktiv)"-Einklapp-Element, sodass die drei Inhalts-Checkboxen
direkt sichtbar sind.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **Identifier:** `handleSave()` (sendet aktuell kein `report_config`)
- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
- **Identifier:** Einklapp-Toggle `report-content-modules-toggle` + `contentModulesExpanded`-Block

## Estimated Scope

- **LoC:** ~25
- **Files:** 2 (WeatherMetricsTab.svelte, EditReportConfigSection.svelte)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `PUT /api/trips/{id}` | Go-API | Persistiert `report_config` (Merge, Issue #99) |
| `PUT /api/trips/{id}/weather-config` | Go-API | Persistiert `display_config` (Metriken) — bleibt unverändert |
| `EditReportConfigSection.svelte` | Frontend-Komponente | Liefert `reportConfig` per `bind:` |

## Implementation Details

### Teil 1 — Persistenz (AC-1)

Zwei Teilprobleme:

**(a) Dirty-Tracking:** `isDirty` (Z.135) und `snapshot()` (Z.139) berücksichtigen
`reportConfig` aktuell **nicht** — eine Änderung an „Metriken-Überblick" macht den Tab
nicht „dirty", der „Speichern"-Button (`weather-metrics-tab-save`, `disabled={saving || !isDirty}`)
bleibt deaktiviert. `reportConfig` muss in `isDirty`-Vergleich, `snapshot()` und den
`savedSnapshot`-Reset (in `initFromTrip` Z.212 und nach erfolgreichem Save Z.363) aufgenommen
werden, damit die Checkbox-Änderung speicherbar wird.

**(b) Persistenz:** `WeatherMetricsTab.handleSave()` muss zusätzlich zur bestehenden
`display_config`-PUT das per `bind:reportConfig` gepflegte `report_config` persistieren.
Read-Modify-Write: der bestehende `weather-config`-Call bleibt erhalten, ergänzt um einen
zweiten Call, der `report_config` über den generischen Trip-PUT speichert (der Go-Handler
merged, ohne `display_config` zu überschreiben — Issue #99).

```
async function handleSave() {
    // ... bestehender display_config-Payload + weather-config PUT ...
    if (!createMode) {
        await api.put(`/api/trips/${trip.id}/weather-config`, payload);       // unverändert
        await api.put(`/api/trips/${trip.id}`, { report_config: reportConfig }); // NEU
        onTripUpdate?.({ ...trip, display_config: payload, report_config: reportConfig });
    }
}
```

`reportConfig` ist bereits lokaler `$state` (Z.81) und wird von der Karte per
`bind:reportConfig` aktuell gehalten. Im Create-Modus (`createMode`) kein PUT
(Konsistenz mit bestehendem Verhalten).

### Teil 2 — Einklapp-Element entfernen (AC-2)

In `EditReportConfigSection.svelte` den `report-content-modules-toggle`-Button
(`Btn` mit `ChevronDown`) und die `{#if contentModulesExpanded}`-Hülle entfernen.
Der Inhalt (die drei Checkboxen `report-show-metrics-summary`, `report-show-outlook`,
`report-show-stage-stats`) bleibt erhalten und wird direkt gerendert. `ChevronDown`-Import
und ungenutzter `contentModulesExpanded`-State entfallen. `countActiveContentModules`
darf als optionaler Zähler-Text bleiben oder entfallen (kein AC-Bezug).

## Expected Behavior

- **Input:** Nutzer (eingeloggt) öffnet einen Trip → Reiter „Metriken" → E-Mail-Inhalt,
  setzt das Häkchen „Metriken-Überblick", klickt Speichern.
- **Output:** `report_config.show_metrics_summary = true` ist persistiert; nach Reload
  ist das Häkchen weiterhin gesetzt. Die drei Inhalts-Checkboxen sind ohne Aufklappen
  direkt sichtbar.
- **Side effects:** Zusätzlicher `PUT /api/trips/{id}`. `display_config` bleibt durch
  den getrennten `weather-config`-Call und den Backend-Merge unangetastet.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer mit einem Trip im „Metriken"-Reiter / When er
  das Häkchen „Metriken-Überblick" setzt, speichert und die Seite neu lädt / Then ist das
  Häkchen weiterhin gesetzt (der Wert `show_metrics_summary=true` wurde in `report_config`
  persistiert).
  - Test: Playwright-E2E gegen Staging als frisch registrierter Nutzer — Häkchen setzen,
    Speichern-Response abwarten, Seite neu laden, Checkbox-Zustand `checked` prüfen.

- **AC-2:** Given der „Metriken"-Reiter mit der E-Mail-Inhalt-Karte / When die Karte
  gerendert wird / Then sind die drei Inhalts-Checkboxen („Metriken-Überblick", „Ausblick",
  „Etappen-Kennzahlen") direkt sichtbar, ohne dass ein „Inhalts-Bausteine"-Einklapp-Element
  erst aufgeklappt werden muss.
  - Test: Playwright-E2E gegen Staging — der Toggle `report-content-modules-toggle`
    existiert nicht (count 0), und `report-show-metrics-summary` ist ohne vorherige
    Interaktion sichtbar.

- **AC-3:** Given ein Trip mit bereits konfigurierter `display_config` (Wetter-Metriken) /
  When der Nutzer im Metriken-Reiter nur die `report_config`-Checkbox ändert und speichert /
  Then bleiben die Wetter-Metriken (`display_config`) unverändert erhalten (kein Datenverlust
  durch den zusätzlichen Save).
  - Test: Playwright-E2E gegen Staging — vor/nach dem Save die Metriken-Auswahl vergleichen;
    bleibt identisch.

## Known Limitations

- Der Save löst nun zwei PUT-Requests aus (weather-config + Trip). Beide laufen über
  bestehende mandantengetrennte Endpunkte; kein neuer Datenpfad.
- „Ausblick" und „Etappen-Kennzahlen" in derselben Karte waren vom selben Bug betroffen
  und werden durch den Fix mitgeheilt (kein separater AC nötig).

## Changelog

- 2026-06-12: Implementation completed; both files updated (isDirty/snapshot/handleSave, Collapse removed)
- 2026-06-12: Initial spec created (Issue #774)
