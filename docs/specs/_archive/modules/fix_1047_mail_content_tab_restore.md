---
entity_id: fix_1047_mail_content_tab_restore
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.0"
tags: [frontend, e2e, bugfix]
---

# Fix #1047: E-Mail-Inhalt-Karte im Wetter-Metriken-Tab wiederherstellen

## Approval

- [ ] Approved

## Purpose

Seit Commit `f5249782` (#942) fehlt die E-Mail-Inhalt-Karte (Ausblick, Etappen-Kennzahlen,
Vortagesvergleich, Format-Schalter Ausführlich/Kompakt) für bestehende Trips komplett aus
der Bearbeiten-Oberfläche — weder im Reiter "Wetter-Metriken" (`?tab=weather`) noch im
Reiter "Briefing-Zeitplan" (`?tab=briefings`) ist sie sichtbar. Dieser Fix stellt die Karte
im Reiter "Wetter-Metriken" wieder her (PO-Entscheidung 2026-07-06), ohne die doppelten
Morgen-/Abend-Report-Zeitplan-Karten zurückzubringen, die #942 ursprünglich entfernen wollte,
und migriert zwei dadurch veraltete E2E-Testdateien auf die tatsächliche Ziel-Oberfläche.

## Source

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
  **Identifier:** neue Prop `showSchedule`
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
  **Identifier:** Wiedereinbindung von `<EditReportConfigSection>`
- **File:** `frontend/e2e/issue-619-mail-elements-ui.spec.ts`
  **Identifier:** `openReportsSection`, AC-1, AC-5 (Testmigration)
- **File:** `frontend/e2e/issue-723-email-tab-eindampfen.spec.ts`
  **Identifier:** `openReportsSection`, AC-1, `REMOVED_TESTIDS` (Testmigration)

> Alle vier betroffenen Dateien liegen in der Frontend-Schicht (`frontend/src/...` bzw.
> `frontend/e2e/...`, SvelteKit-Oberfläche auf gregor20.henemm.com). Keine Go-API- oder
> Python-Core-Änderung nötig — die betroffenen Felder (`show_outlook`, `show_stage_stats`,
> `show_yesterday_comparison`, `email_format`) existieren bereits vollständig im
> Backend/Persistenz-Layer (#721/#722/#785).

## Estimated Scope

- **LoC:** ~60-100 (Prop + Gating in `EditReportConfigSection.svelte` ~10-15 Zeilen,
  Wiedereinbindung in `WeatherMetricsTab.svelte` ~5 Zeilen, Testmigration in beiden
  E2E-Dateien jeweils ~20-40 Zeilen durch Umschreiben der betroffenen Assertions)
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Component | Enthält Mail-Inhalt-Karte + Zeitplan-Karten; braucht neue `showSchedule`-Prop |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Component | Reiter "Inhalt" (`?tab=weather`) — Ziel-Ort der Wiedereinbindung |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Component | Reiter "Versand" (`?tab=briefings`) — bleibt unverändert (`showMailContent={false}`) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Component | Tab-Dispatcher — keine Änderung nötig |
| `frontend/e2e/issue-619-mail-elements-ui.spec.ts` | Test | Migration auf `?tab=weather` + korrekte Testids |
| `frontend/e2e/issue-723-email-tab-eindampfen.spec.ts` | Test | Migration auf `?tab=weather` + korrekte Testids |
| `docs/specs/modules/issue_736_tabs_reorg.md` | Spec (Referenz) | Ursprungsdesign: Mail-Inhalt-Karte gehört in den Inhalt-Reiter |
| `docs/specs/fast/fix-942-inhalt-tab-doppel-ui.md` | Spec (Referenz) | Fix, der die Karte fälschlich komplett entfernt hat (Overreach) |

## Implementation Details

```
1. EditReportConfigSection.svelte:
   - neue Prop `showSchedule?: boolean = true` (Default true, damit
     BriefingScheduleTab.svelte und TripNewEditor.svelte, die die Prop
     nicht übergeben, unverändert bleiben)
   - Morgen-Report-Card (aktuell Zeilen ~232-282) und Abend-Report-Card
     (aktuell Zeilen ~284-337) in {#if showSchedule}...{/if} wickeln
     (gemeinsam oder je Card, solange beide gemeinsam schaltbar sind)

2. WeatherMetricsTab.svelte:
   - Import wiederherstellen:
     import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';
   - Einbindung nach der Schwellwerte-Card (vor dem schließenden </div> der
     linken Spalte, aktuell um Zeile 638/640 — im Zweifel per grep auf
     "</Card>" gefolgt vom rechten Spalten-Kommentar suchen):

     {#if !createMode}
     <EditReportConfigSection
       bind:reportConfig
       mode="edit"
       showMailContent={true}
       showChannels={false}
       showSchedule={false}
     />
     {/if}

   - {#if !createMode}-Gating ist PFLICHT (Regressionsschutz #934: der
     Anlege-Assistent TripNewEditor.svelte zeigt die Karte bereits separat)

3. issue-619-mail-elements-ui.spec.ts:
   - openReportsSection: page.goto(`/trips/${id}?tab=briefings`)
     → page.goto(`/trips/${id}?tab=weather`)
   - AC-1: Referenzen auf `report-show-metrics-summary` entfernen (Testid
     existiert nicht mehr im DOM — Checkbox wurde in #971/#774 entfernt,
     `show_metrics_summary` wird seit #790 im Mail-Renderer unconditional
     gerendert). Verbleibende geprüfte Bausteine: report-show-outlook,
     report-show-stage-stats (plus ggf. report-show-yesterday-comparison
     als dritter tatsächlich vorhandener Baustein)
   - AC-5 ("show_metrics_summary persistiert exakt", aktuell UI-Checkbox-
     Klick-basiert): umschreiben auf Bestandsdaten-Erhalt-Pattern analog
     AC-2 im selben File — Trip mit show_metrics_summary: true anlegen,
     einen verbleibenden Baustein ändern + speichern, per GET /api/trips/{id}
     prüfen dass show_metrics_summary unverändert true geblieben ist
   - Vorbild für dieses Migrationsmuster: Commit aacb3084 (#970/#971/#1011),
     siehe `git show aacb3084 -- frontend/e2e/issue-774-metrics-summary-persist.spec.ts`

4. issue-723-email-tab-eindampfen.spec.ts:
   - openReportsSection: gleiche Umstellung auf ?tab=weather
   - AC-1 ("genau 3 Bausteine"): report-show-metrics-summary aus der Liste
     der sichtbaren Bausteine entfernen, durch die tatsächlich vorhandenen
     3 Bausteine ersetzen (report-show-outlook, report-show-stage-stats,
     report-show-yesterday-comparison)
   - REMOVED_TESTIDS-Liste um `report-show-metrics-summary` ergänzen, damit
     der Test weiterhin exakt 3 Bausteine erzwingt

5. Keine Backend-Änderung nötig.
```

## Expected Behavior

- **Input:** Nutzer öffnet einen bestehenden Trip im Reiter "Wetter-Metriken"
  (`/trips/{id}?tab=weather`).
- **Output:** Die E-Mail-Inhalt-Karte (`report-mail-content`) ist sichtbar mit den
  3 Bausteinen (Ausblick, Etappen-Kennzahlen, Vortagesvergleich) und dem
  Format-Schalter (Ausführlich/Kompakt). Die Morgen-/Abend-Report-Zeitplan-Karten
  erscheinen dort NICHT. Im Reiter "Briefing-Zeitplan" bleibt die Mail-Inhalt-Karte
  weiterhin unsichtbar (unverändertes Verhalten).
- **Side effects:** Keine Datenmodell-Änderung. Änderungen an den Bausteinen
  persistieren wie zuvor über `PUT /api/trips/{id}` und werden bei nachfolgenden
  Aufrufen korrekt aus `report_config` gelesen.

## Acceptance Criteria

- **AC-1:** Given ein bestehender Trip (nicht im Anlege-Modus) / When der Nutzer den
  Reiter "Wetter-Metriken" (`?tab=weather`) öffnet / Then ist die E-Mail-Inhalt-Karte
  (`report-mail-content`) sichtbar mit den 3 Bausteinen (`report-show-outlook`,
  `report-show-stage-stats`, `report-show-yesterday-comparison`) und dem
  Format-Schalter (`report-email-format-full`/`report-email-format-compact`).
  - Test: Playwright navigiert eingeloggt zu `/trips/{id}?tab=weather` für einen
    per API angelegten Test-Trip und prüft `toBeVisible()` auf allen genannten
    Testid-Selektoren (kein Datei-Grep, echtes gerendertes DOM).

- **AC-2:** Given der Reiter "Wetter-Metriken" ist geöffnet / When die Seite
  vollständig geladen ist / Then erscheinen die Morgen-/Abend-Report-Zeitplan-Karten
  NICHT (`morning-master-switch` und `evening-master-switch` haben Count 0) —
  Regressionsschutz gegen die #942-Doppel-UI.
  - Test: Playwright prüft `toHaveCount(0)` für `[data-testid="morning-master-switch"]`
    und `[data-testid="evening-master-switch"]` auf `?tab=weather`.

- **AC-3:** Given ein bestehender Trip / When der Nutzer den Reiter
  "Briefing-Zeitplan" (`?tab=briefings`) öffnet / Then ist die E-Mail-Inhalt-Karte
  weiterhin NICHT sichtbar (`report-mail-content` Count 0) — unverändertes
  Verhalten seit #736.
  - Test: Playwright navigiert zu `/trips/{id}?tab=briefings` und prüft
    `toHaveCount(0)` für `[data-testid="report-mail-content"]`.

- **AC-4:** Given der Reiter "Wetter-Metriken" ist geöffnet / When der Nutzer den
  Baustein `report-show-outlook` umschaltet und speichert / Then ist der neue Wert
  nach einem erneuten `GET /api/trips/{id}` in `report_config.show_outlook`
  persistiert.
  - Test: Playwright klickt die Checkbox unter `[data-testid="report-show-outlook"]`,
    wartet auf die erfolgreiche `PUT`-Response, liest danach per
    `request.get('/api/trips/{id}')` den tatsächlich gespeicherten Wert und
    vergleicht ihn mit dem erwarteten neuen Zustand.

- **AC-5:** Given der Anlege-Assistent (`/trips/new`) / When der Nutzer den
  Schritt mit der E-Mail-Konfiguration erreicht / Then erscheint die Mail-Inhalt-
  Karte weiterhin genau einmal, nicht doppelt — Regressionsschutz für #934
  (unverändertes Verhalten, `TripNewEditor.svelte` zeigt die Karte bereits separat).
  - Test: Manuelle Prüfung in Phase 6 (Validierung) — Anlege-Assistent durchklicken,
    `report-mail-content` erscheint nur im Zeitplan-Schritt, nicht im Wetter-Schritt.
    Kein automatisierter E2E-Test: der GPX-Upload-gesteuerte Freischalt-Fluss des
    Wizard-Schritts ist eigenständig fragil und unabhängig von diesem Fix; der
    Schutz selbst (`{#if !createMode}`) ist unverändert aus der Zeit vor #942
    übernommen (kein neues Risiko).

- **AC-6:** Given ein Trip mit `show_metrics_summary: true` in `report_config`
  (Feld ohne eigenes UI-Element) / When der Nutzer im Reiter "Wetter-Metriken"
  einen anderen Baustein (z.B. `report-show-stage-stats`) ändert und speichert /
  Then bleibt `show_metrics_summary` nach dem Save unverändert `true`
  (Bestandsdaten-Erhalt, Read-Modify-Write) — ersetzt den alten, auf einen nicht
  mehr existierenden UI-Klick aufgebauten Test in `issue-619` AC-5.
  - Test: Playwright legt den Trip per API mit `show_metrics_summary: true` an,
    klickt `report-show-stage-stats`, speichert, und prüft per
    `GET /api/trips/{id}` dass `report_config.show_metrics_summary === true`
    unverändert geblieben ist.

## Known Limitations

- Die beiden migrierten E2E-Dateien (`issue-619-mail-elements-ui.spec.ts`,
  `issue-723-email-tab-eindampfen.spec.ts`) decken inhaltlich weiterhin dieselben
  Acceptance Criteria wie ursprünglich ab — nur der Ziel-Reiter (`?tab=weather`
  statt `?tab=briefings`) und die Referenzen auf den nicht mehr existierenden
  Testid `report-show-metrics-summary` werden korrigiert.
- `frontend/e2e/issue-736-tabs-reorg.spec.ts` (AC-2/AC-3) prüft bereits exakt das
  Zielbild dieses Fixes und wird durch denselben Code-Fix automatisch wieder grün —
  diese Datei wird NICHT verändert, nur im Rahmen der Validierung mitverifiziert.
- Keine Backend- oder Datenmodell-Änderung; alle betroffenen Felder existieren
  bereits seit #721/#722/#785.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine UI-Korrektur (Wiederherstellung einer versehentlich entfernten
  Komponenten-Einbindung + Prop-Gating nach bereits etabliertem Muster von
  `showMailContent`/`showChannels`). Kein neues Datenmodell, keine neue Architektur.

## Changelog

- 2026-07-06: Initial spec created
