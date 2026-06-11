---
entity_id: issue_723_email_tab_eindampfen
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [frontend, email, report-config, ui-cleanup, slice]
---

<!-- Issue #723 — E-Mail-Inhalt-Tab UI eindampfen (Slice 3 von #709) -->

# Issue 723 — E-Mail-Inhalt-Tab UI eindampfen

## Approval

- [ ] Approved

## Purpose

Den E-Mail-Inhalt-Bereich im Trip-Editor (`EditReportConfigSection.svelte`) von 9 teils doppelten und toten Optionen auf eine zweistufige Struktur mit genau 4 Steuerelementen (Format-Radio + 3 Bausteine) zu reduzieren. Das Frontend wird damit auf das seit #721/#722 bereits schlanke Backend-Modell ausgerichtet: Ausführlich- oder Kompakt-Format wählen, darunter drei klar benannte Bausteine, die im Kompakt-Modus deaktiviert sind — keine Doppelungen, keine Felder ohne Backend-Entsprechung.

## Source

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (Kern-Umbau)
- **File:** `frontend/src/lib/types.ts` (`show_outlook?: boolean` ergänzen)
- **File:** `frontend/src/lib/components/edit/reportConfigWrite.ts` (Helper anpassen)
- **File:** `frontend/e2e/issue-619-mail-elements-ui.spec.ts` (Regression mitziehen)
- **File:** `frontend/src/lib/components/edit/issue_693_email_config_cleanup.test.ts` (node-Test anpassen)
- **File:** `frontend/src/lib/components/edit/issue_619_report_config_write.test.ts` (node-Test anpassen)
- **File:** `tests/tdd/test_issue_613_email_redesign.py` (roten AC-6-Test neu schreiben)
- **Identifier:** `EditReportConfigSection` (Svelte-Komponente)

## Estimated Scope

- **LoC:** ~120 (−150 Svelte/TS, +30 neue `show_outlook`-Verdrahtung + Test-Anpassungen)
- **Files:** 7
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ReportConfig` (`frontend/src/lib/types.ts`) | TypeScript-Interface | Datenmodell für alle report-config-Felder; muss `show_outlook?: boolean` erhalten |
| `reportConfigWrite.ts` — `buildReportConfigPayload` | Helper-Funktion | Baut das Write-Back-Objekt für den PUT; muss `show_outlook` inkludieren und entfernte Felder via `...originalReportConfig`-Spread erhalten |
| `reportConfigWrite.ts` — `countActiveContentModules` | Helper-Funktion | Zählt aktive Bausteine für den Collapse-Header; von 5 auf 3 konfigurierbare Bausteine reduzieren (`show_stage_stats`, `show_metrics_summary`, `show_outlook`) |
| `reportConfigWrite.ts` — `CONTENT_MODULE_DESCRIPTIONS` | Konstante | Labels/Descriptions für die 3 verbleibenden Bausteine; Einträge für entfernte Felder bleiben im Objekt (rückwärtskompatibel), werden aber nicht mehr gerendert |
| `reportConfigWrite.ts` — `DAILY_SUMMARY_METRICS` / `toggleDailySummaryMetric` / `dailySummaryMetricsSummary` | Helper-Funktionen | Tages-Summe-Gruppe entfällt aus dem UI; Funktionen bleiben im Modul bis keine Tests mehr darauf zeigen |
| `originalReportConfig` ($state, Svelte) | Lokaler State | Basis-Spread beim Write-Back; sichert Bestandsdaten aller aus dem UI entfernten Felder |
| GET/PUT `/api/auth/profile` (Go-API, Port 8090) | Endpunkt | Liest und schreibt `report_config` pro Nutzer; keine Änderung am Endpunkt |
| `models.ReportConfig` (`src/app/models.py:733`) | Python-Modell | Backend bereits verdrahtet für `show_outlook`, `show_stage_stats`, `show_metrics_summary`; keine Änderung |
| Playwright (`frontend/e2e/`) | Testtool | E2E-Tests gegen Staging als eingeloggter Nutzer |
| `issue-619-mail-elements-ui.spec.ts` | E2E-Test | Referenziert entfernte testids (`report-show-quick-take`, `report-show-stability`, `report-show-highlights`, `daily-summary-metric-*`); muss mitgezogen werden |
| `issue_693_email_config_cleanup.test.ts` | node-Test | Referenziert `countActiveContentModules` und Bausteine; auf 3-Bausteine-Modell anpassen |
| `issue_619_report_config_write.test.ts` | node-Test | Prüft Write-Back-Payload; `show_outlook` ergänzen, entfernte Felder-Assertions entfernen |
| `test_issue_613_email_redesign.py` | pytest | AC-6 prüft Stirnlampe/Test-Zusammenfassung/„report morning" und ist bereits rot; neu schreiben |

## Implementation Details

### Schritt 1: `types.ts` — `show_outlook` ergänzen

```typescript
// frontend/src/lib/types.ts — ReportConfig
show_outlook?: boolean;   // NEU — steuert Ausblick-Block (Großwetterlage + nächste Etappen + Sicherheit%)
```

Das Feld wird nach dem bestehenden Muster als optional deklariert. Default im UI: `true` wenn der Wert aus `reportConfig` fehlt.

### Schritt 2: `EditReportConfigSection.svelte` — State bereinigen

Lokale `$state`-Variablen, die entfernt werden:
- `show_compact_summary`
- `show_daylight`
- `wind_exposition_min_elevation_m`
- `show_quick_take_tags`
- `show_stability`
- `show_highlights`
- `dailySummaryMetrics`
- `dailySummaryExpanded`
- `showAdvanced`

Neue lokale `$state`-Variable:
```typescript
let show_outlook = $state(true);  // Default true wenn aus reportConfig fehlt
```

Initialisierung im `$effect`:
```typescript
if (typeof c.show_outlook === 'boolean') show_outlook = c.show_outlook;
// fehlend → bleibt true (Default)
```

### Schritt 3: Write-Back — Bestandsdaten-Schutz via Spread

Der `$effect`-Write-Back muss alle entfernten Felder via Spread erhalten:

```typescript
// PFLICHT: originalReportConfig als Basis — entfernte Felder kommen via Spread mit
const payload = buildReportConfigPayload({
    ...originalReportConfig,        // Basis: alle persistierten Felder
    show_outlook,                   // überschreibt mit UI-Wert
    show_stage_stats,
    show_metrics_summary,
    email_format,
    // show_compact_summary, show_daylight, wind_exposition_min_elevation_m etc.
    // kommen automatisch aus originalReportConfig — NIEMALS explizit auf undefined setzen
});
```

Dadurch bleiben `show_compact_summary`, `show_daylight`, `wind_exposition_min_elevation_m`, `show_quick_take_tags`, `show_stability`, `show_highlights`, `daily_summary_metrics` beim nächsten PUT unverändert erhalten.

### Schritt 4: `reportConfigWrite.ts` — Helper anpassen

`countActiveContentModules` auf 3 Bausteine reduzieren:
```typescript
export function countActiveContentModules(ui: MailElementUi): number {
    return [
        ui.show_stage_stats,
        ui.show_metrics_summary ?? false,
        ui.show_outlook ?? true,
    ].filter(Boolean).length;
}
```

`MailElementUi`-Interface: `show_outlook?: boolean` ergänzen; `show_quick_take_tags`, `show_stability`, `show_highlights`, `daily_summary_metrics` entfernen (Interface-Aufräumung — Implementierung in `buildReportConfigPayload` bleibt rückwärtskompatibel).

`DAILY_SUMMARY_METRICS`, `toggleDailySummaryMetric`, `dailySummaryMetricLabel`, `dailySummaryMetricsSummary` bleiben im Modul, bis node-Tests nicht mehr darauf zeigen — dann in einem separaten Cleanup entfernen.

### Schritt 5: UI-Struktur nach dem Umbau

```
[Card: E-Mail-Inhalt]
  [Format-Schalter — Radio]
    ○ Ausführlich (HTML)    data-testid="report-email-format-full"
    ○ Kompakt (Nur-Text)    data-testid="report-email-format-compact"

  [Kompakt-Hinweis]  (nur sichtbar wenn compact)
    data-testid="report-compact-hint"

  [Inhalts-Bausteine (N aktiv)]  — disabled + opacity:0.45 + pointer-events:none wenn compact
    data-testid="report-content-modules-toggle"  (Collapse-Button)
    data-testid="report-content-modules-body"    (Collapse-Body)

    ☑ Metriken-Überblick       data-testid="report-show-metrics-summary"
    ☑ Ausblick                 data-testid="report-show-outlook"          ← NEU
    ☑ Etappen-Kennzahlen       data-testid="report-show-stage-stats"
```

Entfernte DOM-Elemente (testids die verschwinden):
- `report-show-quick-take`
- `report-show-stability`
- `report-show-highlights`
- `daily-summary-metric-*` (alle)
- `report-daily-summary-toggle`
- `report-daily-summary-body`
- `report-show-advanced`
- `report-compact-summary`
- `report-show-daylight`
- `report-wind-exposition`

### Schritt 6: Test-Mitziehung

`frontend/e2e/issue-619-mail-elements-ui.spec.ts`:
- Assertions auf entfernte testids entfernen (`report-show-quick-take`, `report-show-stability`, `report-show-highlights`, `daily-summary-metric-*`)
- Neue Assertion auf `report-show-outlook` ergänzen
- Persistenz-Roundtrip für `show_outlook` ergänzen (Checkbox an → Save → Reload → Checkbox an)

`issue_693_email_config_cleanup.test.ts` + `issue_619_report_config_write.test.ts`:
- `countActiveContentModules`-Tests auf 3-Bausteine-Modell anpassen
- Write-Back-Tests: `show_outlook`-Assertions ergänzen, entfernte Felder-Assertions entfernen

`tests/tdd/test_issue_613_email_redesign.py::TestAC6SectionsPreserved`:
- Ist bereits rot (prüft Stirnlampe/Test-Zusammenfassung/„report morning")
- Komplett neu schreiben: prüft stattdessen HTTP-Level-Roundtrip `show_outlook` via PUT `/api/auth/profile` → GET → `report_config.show_outlook` == gesetzter Wert (echter API-Call, kein Mock)

## Expected Behavior

- **Input:** `reportConfig`-Prop mit beliebigem bestehenden `ReportConfig`-Objekt (inkl. alter Trips ohne `show_outlook`)
- **Output:** UI zeigt genau Format-Schalter + 3 Bausteine; alle entfernten Felder sind aus dem DOM verschwunden; `show_outlook` ist im Write-Back-Payload enthalten
- **Side effects:** PUT `/api/auth/profile` mit `report_config` behält alle bisher persistierten Felder unverändert (via Spread), auch wenn sie nicht mehr im UI steuerbar sind

## Acceptance Criteria

- **AC-1:** Given der Trip-Editor ist geöffnet und der Reports-Tab ist aktiv / When die E-Mail-Inhalt-Karte gerendert wird / Then sind genau 3 Bausteine sichtbar (`report-show-metrics-summary`, `report-show-outlook`, `report-show-stage-stats`) und der Format-Schalter (`report-email-format-full`, `report-email-format-compact`) ist vorhanden — keine weiteren Checkbox-Elemente für entfernte Optionen im DOM
  - Test: Playwright gegen Staging — `locator('[data-testid="report-show-quick-take"]').count()` == 0, `locator('[data-testid="report-show-outlook"]')` sichtbar

- **AC-2:** Given ein Trip mit bisher gespeicherten Werten für `show_quick_take_tags`, `show_stability`, `show_highlights`, `daily_summary_metrics`, `show_compact_summary` / When der Nutzer die Ausblick-Checkbox umschaltet und speichert / Then liefert GET `/api/auth/profile` alle ursprünglichen Werte der entfernten Felder unverändert zurück — kein Datenverlust durch Spread-Beibehaltung
  - Test: Playwright — PUT mit nur `show_outlook`-Änderung, dann GET, dann Vergleich der übrigen `report_config`-Felder via JSON-Assertion

- **AC-3:** Given `show_outlook` fehlt im gespeicherten `report_config` (alter Trip ohne dieses Feld) / When der Reports-Tab geöffnet wird / Then ist die Ausblick-Checkbox angehakt (Default `true`), und nach einem Save enthält der PUT-Payload `show_outlook: true`
  - Test: Playwright gegen Staging — Nutzer-Account ohne `show_outlook` im Profil anlegen, Tab öffnen, Checkbox-Zustand prüfen, Save auslösen, GET-Response auf `show_outlook === true` prüfen

- **AC-4:** Given Format-Schalter steht auf "Kompakt (Nur-Text)" / When die Bausteine-Gruppe sichtbar ist / Then sind alle 3 Bausteine-Checkboxen deaktiviert (`disabled`-Attribut gesetzt) und optisch gedimmt (`opacity: 0.45`) — kein Baustein ist anklickbar
  - Test: Playwright — `report-email-format-compact`-Radio klicken, dann `locator('[data-testid="report-show-outlook"] input[type="checkbox"]').isDisabled()` == true

- **AC-5:** Given Format-Schalter steht auf "Ausführlich (HTML)" / When die Ausblick-Checkbox umgeschaltet und gespeichert wird / Then zeigt GET `/api/auth/profile` → `report_config.show_outlook` den neuen Wert, und ein erneutes Öffnen des Tabs zeigt die Checkbox im gespeicherten Zustand
  - Test: Playwright — `report-show-outlook`-Checkbox anklicken → `edit-save-btn` klicken → Seite neu laden → `report-show-outlook`-Checkbox-Zustand muss dem gespeicherten Wert entsprechen

- **AC-6:** Given die node-Tests `issue_693_email_config_cleanup.test.ts` und `issue_619_report_config_write.test.ts` / When `npm test` im frontend-Verzeichnis läuft / Then bestehen alle Tests grün — `countActiveContentModules` liefert für 3 aktive Bausteine den Wert 3, kein Test referenziert mehr entfernte Felder
  - Test: `cd frontend && node --test src/lib/components/edit/issue_693_email_config_cleanup.test.ts src/lib/components/edit/issue_619_report_config_write.test.ts` — Exit 0, keine failing assertions

## Known Limitations

- Entfernte Felder (`show_compact_summary`, `show_daylight`, `wind_exposition_min_elevation_m`, `show_quick_take_tags`, `show_stability`, `show_highlights`, `daily_summary_metrics`) bleiben im `ReportConfig`-TypeScript-Interface und im Python-Modell erhalten — sie sind über das UI nicht mehr steuerbar, aber ihre Werte in der Persistenz bleiben gültig. Eine Entfernung aus dem Modell erfordert eine separate Migration mit Rollback-Plan (vgl. CLAUDE.md Daten-Schema-Reworks-Pflicht).
- `DAILY_SUMMARY_METRICS` und zugehörige Helper in `reportConfigWrite.ts` werden erst dann aus dem Modul gelöscht, wenn keine node-Tests mehr darauf zeigen — vermeidet Regressions-Risiko durch unbedachte Löschung.
- `tests/tdd/test_issue_613_email_redesign.py::TestAC6SectionsPreserved` ist vor dem Fix bereits rot und muss komplett neu geschrieben werden (nicht gepatcht), da er auf inzwischen entfernten Konzepten basiert.

## Changelog

- 2026-06-11: Initial spec erstellt — Issue #723, Slice 3 von Epic #709
