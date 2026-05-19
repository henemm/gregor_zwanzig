---
entity_id: issue_259_briefings_tab
type: module
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
tags: [frontend, briefings, svelte, epic-135, issue-259]
parent: epic-135-trip-uebersicht
---

# Issue #259 — Trip-Übersicht: Briefing-Zeitplan-Tab implementieren

## Approval

- [ ] Approved

## Purpose

Ersetzt den Platzhalter-Text im Briefing-Zeitplan-Tab (`/trips/[id]#briefings`) mit der
vollständigen Konfigurations-UI. Bindet die bereits vorhandene Komponente
`EditReportConfigSection.svelte` in einen neuen Tab-Container (`BriefingsTab.svelte`)
ein, der lokalen State hält, die Änderungen via `PUT /api/trips/{id}` speichert und
Inline-Feedback (Erfolg / Fehler) zeigt — identisches Muster wie `AlertsTab.svelte`.

Epic #135 hat 5 von 6 Tabs vollständig implementiert; dieser Tab ist der einzige
fehlende Baustein.

## Source

- **Files:**
  - `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte` (NEU, ~60 LoC)
  - `frontend/src/lib/components/trip-detail/TripTabs.svelte` (geändert, ~5 LoC)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Svelte-Komponente (vorhanden) | Rendert die Briefing-Zeitplan-Formularfelder (Zeiten, Kanäle, Optionen) |
| `frontend/src/lib/api.ts` | Utility | `api.put()` für den Save-Call |
| `frontend/src/lib/types.ts` | TypeScript | `Trip`, `ReportConfig` — vollständig typisiert, keine Änderung nötig |
| `PUT /api/trips/{id}` | Go-Backend-Endpoint | Vorhanden; akzeptiert `{ report_config: ReportConfig }` im Body |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Svelte-Komponente | Import + Branch für `briefings`-Tab ergänzen, Platzhalter entfernen |

## Scope

**Nur Frontend.** 2 Dateien:

- **Neu:** `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte`
- **Geändert:** `frontend/src/lib/components/trip-detail/TripTabs.svelte`

Keine Änderungen an:
- `EditReportConfigSection.svelte` — wird unverändert wiederverwendet
- `internal/handler/trip.go` — Backend akzeptiert `report_config` bereits
- `frontend/src/lib/types.ts` — `ReportConfig`-Interface vollständig

## Implementation Details

### BriefingsTab.svelte

Container-Komponente nach dem gleichen Muster wie `AlertsTab.svelte`.

**Props:** `trip: Trip`

**State:**

```typescript
// Deep Copy verhindert, dass Änderungen sofort den Parent-State mutieren
let reportConfig = $state<ReportConfig>(
  JSON.parse(JSON.stringify(trip.report_config ?? {}))
);
let saving = $state(false);
let saveSuccess = $state(false);
let saveError = $state<string | null>(null);
```

**Save-Funktion:**

```typescript
async function save() {
  saving = true;
  saveSuccess = false;
  saveError = null;
  try {
    await api.put(`/api/trips/${trip.id}`, { report_config: reportConfig });
    saveSuccess = true;
    setTimeout(() => { saveSuccess = false; }, 3000);
  } catch (e: unknown) {
    saveError = e instanceof Error ? e.message : 'Fehler beim Speichern';
  } finally {
    saving = false;
  }
}
```

**Template-Struktur:**

```svelte
<div class="briefings-tab" data-testid="briefings-tab">
  <EditReportConfigSection bind:reportConfig mode="edit" />

  <div class="actions">
    <button
      type="button"
      class="btn-primary"
      data-testid="briefings-tab-save"
      disabled={saving}
      onclick={save}
    >{saving ? 'Speichere…' : 'Speichern'}</button>

    {#if saveSuccess}
      <span class="success-msg" data-testid="briefings-tab-save-success">Gespeichert.</span>
    {/if}
    {#if saveError}
      <span class="error-msg" data-testid="briefings-tab-save-error">{saveError}</span>
    {/if}
  </div>
</div>
```

**Styling:** Gleiche CSS-Klassen wie `AlertsTab.svelte` (`.btn-primary`, `.success-msg`,
`.error-msg`, `.actions`). `EditReportConfigSection` bringt eigenes Styling mit.

### TripTabs.svelte — Änderungen

**1. Import hinzufügen** (nach dem bestehenden `AlertsTab`-Import):

```typescript
import BriefingsTab from '$lib/components/briefings-tab/BriefingsTab.svelte';
```

**2. Branch im `{#each TABS}`-Block ergänzen** (nach dem `weather`-Branch, vor dem
`alerts`-Branch):

```svelte
{:else if tab.value === 'briefings' && trip}
  <BriefingsTab {trip} />
```

**3. Platzhalter-Eintrag entfernen** (Zeile 44, `PLACEHOLDERS`-Objekt):

```typescript
// Entfernen:
briefings: 'Inhalt folgt mit Issue #159 (rechte Spalte)',
```

## Expected Behavior

- **Input:** `trip: Trip` mit optionalem `report_config: ReportConfig`
- **Output:** Vollständige Briefing-Zeitplan-UI (Morgen-/Abend-Report, Zeiten, Kanäle, Optionen)
- **Side effects:** Bei Klick auf Speichern: `PUT /api/trips/{id}` mit `{ report_config }`. Bei Erfolg: 3-Sekunden-Inline-Flash. Bei Fehler: Inline-Fehlermeldung.

## Acceptance Criteria

**AC-1:** Given der User öffnet `/trips/[id]#briefings` /
When der Tab gerendert wird /
Then zeigt der Tab die `EditReportConfigSection`-Formularfelder (Morgen-/Abend-Zeit, Kanäle) — kein Platzhalter-Text "Inhalt folgt mit Issue #159" mehr.

**AC-2:** Given ein Trip hat `report_config: { morning_time: "06:30", send_email: true }` /
When der Briefing-Zeitplan-Tab geöffnet wird /
Then zeigt `EditReportConfigSection` den vorhandenen Wert "06:30" im Morgen-Zeit-Feld und E-Mail als aktiven Kanal.

**AC-3:** Given der User ändert die Abend-Zeit auf "19:00" und klickt Speichern /
When der API-Call abgesetzt wird /
Then wird `PUT /api/trips/{id}` mit `{ report_config: { ..., evening_time: "19:00" } }` aufgerufen.

**AC-4:** Given der API-Call für Speichern kehrt mit Status 200 zurück /
When der User auf Speichern geklickt hat /
Then erscheint die Meldung "Gespeichert." für 3 Sekunden und verschwindet danach automatisch.

**AC-5:** Given der API-Call für Speichern schlägt fehl (z.B. Netzwerkfehler) /
When der User auf Speichern geklickt hat /
Then erscheint eine Inline-Fehlermeldung — kein Absturz, kein leerer Screen.

**AC-6:** Given der User klickt den Speichern-Button /
When der API-Call läuft /
Then ist der Speichern-Button disabled und zeigt den Text "Speichere…", bis der Call abgeschlossen ist.

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte` | NEU (~60 LoC) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Import + briefings-Branch + PLACEHOLDERS-Cleanup (~5 LoC) |

## LoC Estimate

~65 LoC gesamt (BriefingsTab ~60, TripTabs +5).

## Known Limitations

- `EditReportConfigSection` lädt intern das User-Profil via `onMount` (für Channel-Verfügbarkeit). Im `mode="edit"` ist dieses Verhalten unverändert — kein zusätzlicher API-Call nötig.
- Der Tab hat keinen eigenen "Abbrechen"-Button: Änderungen werden nur bei explizitem Klick auf Speichern persistiert. Navigiert der User weg, gehen ungespeicherte Änderungen verloren (akzeptiertes Verhalten, konsistent mit anderen Tabs).

## Changelog

- 2026-05-19: Initial spec erstellt (Issue #259 — Briefing-Zeitplan-Tab implementieren).
