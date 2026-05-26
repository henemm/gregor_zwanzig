---
entity_id: issue_300_wizard_redesign
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [frontend, wizard, svelte, redesign, issue-300]
---

# Issue #300 — Trip-Wizard Redesign: Neue Schritt-Struktur Route/Etappen/Wetter/Reports

## Approval

- [ ] Approved

## Purpose

Ersetzt die bestehende 4-Schritt-Struktur des Trip-Wizards (`/trips/new`) durch eine
inhaltlich neu gegliederte Abfolge: Route → Etappen → Wetter → Reports. Der GPX-Upload
wandert von Step 2 nach Step 1, die Wegpunkt-KI-Vorschläge (Step 3 alt) entfallen als
eigene Phase, stattdessen erhält der Wizard einen dedizierten Wetter-Konfigurations-Schritt
sowie eine übersichtliche Report-Karten-Ansicht als Abschluss.

Das Redesign macht den Wizard linear und aufgabenfokussiert: Zuerst die Route definieren,
dann die erkannten Etappen prüfen, dann die Wetter-Metriken konfigurieren, abschließend
die Briefing-Typen aktivieren — so spiegelt die Wizard-Reihenfolge die natürliche
Vorbereitungslogik eines Weitwanderers wider.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` (geändert)
  - `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (geändert)
  - `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` (komplett ersetzt)
  - `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` (geändert)
  - `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` (NEU)
  - `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` (NEU)
  - `frontend/e2e/trip-wizard-step1.spec.ts` (angepasst)
  - `frontend/e2e/trip-wizard-step3.spec.ts` (komplett umgeschrieben)
  - `frontend/e2e/trip-wizard-step4.spec.ts` (angepasst)
  - `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` (angepasst)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `HorizonChip.svelte` — `frontend/src/lib/components/ui/horizon-chip/` | Svelte-Komponente (vorhanden) | Drei Horizont-Toggle-Chips (HEUTE/MORGEN/ÜBERMORGEN) pro Metrik in Step 3 |
| `MetricCheckbox.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Metrik-Toggle-Zeilen in Step 3 Wetter-Tabelle |
| `metricsEditor.ts` — `frontend/src/lib/components/trip-detail/` | TypeScript-Modul (vorhanden) | Metrik-Katalog-Logik, `WeatherConfigMetric`-Interface, Default-Prüfung |
| `AlertRulesEditor.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Kriterien-Text für Warnungen-Card in Step 4 Reports |
| `GCard`, `Btn`, `Eyebrow`, `Pill` | Design-System-Atome (vorhanden) | UI-Bausteine in allen Steps |
| `GET /api/metrics` | Go-Backend-Endpoint (vorhanden) | Metrik-Katalog für Step 3 beim Mount laden |
| `WizardState` — `wizardState.svelte.ts` | TypeScript-Klasse (geändert) | Zentraler State für alle Steps, neues Feld `weatherMetrics` |

## Scope

**Nur Frontend.** Keine Änderungen am Go-Backend oder Python-Backend.

Nicht in Scope:
- `Trip.display_config` Backend-Felder — bestehende `map[string]interface{}`-Struktur bleibt
- KI-Wegpunkt-Vorschläge — `Step3Waypoints.svelte` bleibt als leerer Fallback erhalten
- Trend-Vorschau Card (Step 4) — Platzhalter `"Demnächst"`, kein Backend-Anschluss
- Änderungen an bestehenden `/trips/[id]` Detail-Seiten-Tabs

## Implementation Details

### Step 1 — Route (ersetzt Step1Profile.svelte komplett)

**Entfernte Elemente:**
- 5 Activity-Chips (Alpen-Trekking, Skitouren, Hochtour, Klettersteig, MTB)
- Kürzel-Feld (`shortcode`)
- GPX-Upload-Bereich (wandert nach Step 1 als Haupt-Element)

**Neue Struktur:**

```
[Trip-Name Input]          ← Pflichtfeld, bleibt
[Region Input]             ← optional, bleibt
[Startdatum Input]         ← Pflichtfeld, bleibt
[GPX-Dropzone — groß]      ← NEU: von Step2 hierher verschoben
  Button: "Aus Dateisystem wählen"
  Button: "Vom letzten Trip kopieren"
Link: "Etappen manuell anlegen →"   ← leitet direkt zu Step 2
```

**State-Migration:** GPX-Upload-Logik (`pendingFiles`, `commitPending`, DnD-Handler) aus
`Step2Stages.svelte` nach `Step1Profile.svelte` (neu: Step1Route) verschieben. Die Logik
bleibt byte-gleich, nur der Container wechselt.

**`canAdvanceStep1` — geändert:**

```typescript
// Vorher: activity !== null && name.trim().length > 0 && startDate.length > 0
// Nachher: Activity-Prüfung entfällt
get canAdvanceStep1(): boolean {
  return (
    this.name.trim().length > 0 &&
    typeof this.startDate === 'string' &&
    this.startDate.length > 0
  );
}
```

---

### Step 2 — Etappen (ändert Step2Stages.svelte)

**Entfernte Elemente:**
- Drop-Zone und File-Input-Bereich (ist jetzt in Step 1)

**Neue / geänderte Elemente:**

```
Header: "N ETAPPEN ERKANNT AUS N GPX"   ← Badge-Stil, N aus stages.length
[Button: "Zusammenführen"]
[Button: "+ Etappe einschieben"]
[DnD-Liste der Etappen]
  Pro Etappe: Nummer · Name · Datum · km · ↑m · WP-Zähler · "+N Vorschläge"-Pill
```

**Vorschläge-Pill:**
- Nur anzeigen wenn `stage.waypoints.filter(wp => wp.suggested).length > 0`
- Style: orange-dashed Pill (`variant="outlined"`, Accent-Farbe)
- Text: `+N Vorschläge`

**TemplatePicker** bleibt unverändert erhalten.

**`canAdvanceStep2`** bleibt unverändert: `stages.length > 0`.

---

### Step 3 — Wetter (neu: Step3Weather.svelte)

**Neue Datei.** Kein Code aus bestehenden Komponenten, sondern Komposition aus
wiederverwendbaren Bausteinen.

**Props:** keine (liest aus `wizard: WizardState` via Context)

**State (lokal):**

```typescript
let metrics = $state<WeatherConfigMetric[]>([]);
let loading = $state(true);
```

**Mount-Hook:**

```typescript
onMount(async () => {
  const data = await api.get<WeatherConfigMetric[]>('/api/metrics');
  metrics = data;
  // wizard.weatherMetrics initialisieren falls noch leer
  if (wizard.weatherMetrics.length === 0) {
    wizard.weatherMetrics = data.filter(m => m.enabled);
  }
  loading = false;
});
```

**Template-Struktur:**

```svelte
<div class="step3-weather" data-testid="step3-weather">
  <Eyebrow>Aktivitätsprofil</Eyebrow>
  <select bind:value={wizard.activity} data-testid="activity-dropdown">
    <option value={null}>Standard (kein Profil)</option>
    <option value="alpine_trekking">Alpen-Trekking</option>
    <option value="ski_touring">Skitouren</option>
    <option value="alpine_climbing">Hochtour</option>
    <option value="via_ferrata">Klettersteig</option>
    <option value="mtb">MTB</option>
  </select>

  {#if wizard.activity === null}
    <p class="hint" data-testid="activity-hint">Standard-Metriken werden verwendet.</p>
  {/if}

  <Eyebrow>Metriken</Eyebrow>
  <p class="summary">
    {enabledCount} Metriken aktiv · {customCount} angepasst
  </p>

  {#each metrics as metric}
    <div class="metric-row" data-testid="metric-row-{metric.id}">
      <span class="metric-name">{metric.label}</span>
      {#if isNonDefault(metric)}
        <Pill variant="filled" size="sm">HINZUGEFÜGT</Pill>
      {/if}
      <div class="horizon-chips">
        <HorizonChip horizon="today" bind:active={metric.horizons.today} />
        <HorizonChip horizon="tomorrow" bind:active={metric.horizons.tomorrow} />
        <HorizonChip horizon="day_after" bind:active={metric.horizons.day_after} />
      </div>
      <span class="format-label">{metric.format === 'raw' ? 'Roh' : 'Indikator'}</span>
    </div>
  {/each}
</div>
```

**`canAdvanceStep3`** bleibt `true` (kein Gate).

---

### Step 4 — Reports (neu: Step4Reports.svelte)

**Neue Datei.** Vier Cards in einem 2×2-Grid.

**Template-Struktur:**

```svelte
<div class="step4-reports" data-testid="step4-reports">
  <div class="reports-grid">

    <!-- Card 1: Abend-Briefing -->
    <GCard data-testid="card-evening">
      <Eyebrow>Abend-Briefing</Eyebrow>
      <label>
        <input type="checkbox" bind:checked={wizard.briefings.reports.evening.enabled} />
        Aktiv
      </label>
      <input type="time" bind:value={wizard.briefings.reports.evening.time}
             data-testid="evening-time" />
      <!-- Kanal-Chips aus wizard.briefings.channels -->
      <ChannelChips bind:channels={wizard.briefings.channels} />
    </GCard>

    <!-- Card 2: Morgen-Update -->
    <GCard data-testid="card-morning">
      <Eyebrow>Morgen-Update</Eyebrow>
      <label>
        <input type="checkbox" bind:checked={wizard.briefings.reports.morning.enabled} />
        Aktiv
      </label>
      <input type="time" bind:value={wizard.briefings.reports.morning.time}
             data-testid="morning-time" />
      <ChannelChips bind:channels={wizard.briefings.channels} />
    </GCard>

    <!-- Card 3: Warnungen (Wachhund) -->
    <GCard data-testid="card-alerts">
      <Eyebrow>Warnungen</Eyebrow>
      <Pill variant="outlined">AUTARK</Pill>
      <!-- Aktive AlertRules als Freitext-Summary -->
      <p class="criteria-summary">{alertSummary}</p>
      <ChannelChips bind:channels={wizard.briefings.channels} />
    </GCard>

    <!-- Card 4: Trend-Vorschau (Platzhalter) -->
    <GCard data-testid="card-trend" class="disabled">
      <Eyebrow>Trend-Vorschau</Eyebrow>
      <Pill variant="outlined">Demnächst</Pill>
    </GCard>

  </div>
</div>
```

**`canAdvanceStep4`** bleibt `true`.

---

### WizardState — Änderungen

**Neues Feld:**

```typescript
weatherMetrics = $state<WeatherConfigMetric[]>([]);
```

`WeatherConfigMetric` wird aus `metricsEditor.ts` importiert (kein neues Interface).

**`canAdvanceStep1` — geändert:** Activity-Prüfung entfernen (siehe Step-1-Detail oben).

**`toTripPayload()` — Erweiterung:**

```typescript
// Nach dem bestehenden report_config-Block einfügen:
if (this.weatherMetrics.length > 0) {
  trip.display_config = {
    ...(trip.display_config ?? {}),
    metrics: this.weatherMetrics
  };
}
```

**`shortcode`-Feld** bleibt in `WizardState` erhalten (rückwärtskompatibel), wird nur
nicht mehr aus dem Wizard-UI gesetzt. `toTripPayload()` schreibt es weiterhin wenn
`shortcode.trim().length > 0` — da Step 1 kein Shortcode-Feld mehr hat, bleibt es leer.

---

### TripWizardShell — Änderungen

**`stepLabels`:**

```typescript
// Vorher: ['Profil', 'GPX-Import', 'Wegpunkte', 'Briefings']
// Nachher:
const stepLabels = ['Route', 'Etappen', 'Wetter', 'Reports'];
```

**`stepSubLabels`:**

```typescript
const stepSubLabels = [
  'Name & GPX hochladen',
  'Etappen prüfen',
  'Metriken konfigurieren',
  'Briefings einrichten'
];
```

**Imports:**

```typescript
// Entfernen:
import Step3Waypoints from './steps/Step3Waypoints.svelte';
import Step4Briefings from './steps/Step4Briefings.svelte';
// Hinzufügen:
import Step3Weather from './steps/Step3Weather.svelte';
import Step4Reports from './steps/Step4Reports.svelte';
```

---

### E2E-Tests — Anpassungen

**`trip-wizard-step1.spec.ts`:**
- Alle `data-testid="activity-chip-*"`-Referenzen entfernen
- `data-testid="gpx-dropzone"` als Erwartung hinzufügen
- Test für `canAdvanceStep1` ohne Activity prüfen (Name + Startdatum reicht)

**`trip-wizard-step3.spec.ts`:**
- Komplett umschreiben: prüft `step3-weather`, `activity-dropdown`, `metric-row-*`
- Kein Bezug zu `step3-waypoints` mehr

**`trip-wizard-step4.spec.ts`:**
- Prüft vier Cards: `card-evening`, `card-morning`, `card-alerts`, `card-trend`
- `card-trend` muss `disabled`-Klasse haben

---

### LoC-Budget

| Datei | Delta |
|-------|-------|
| `Step1Profile.svelte` → Route (Ersatz) | ~0 (Umbau, GPX-Logik verschoben) |
| `Step2Stages.svelte` (GPX entfernt, Header neu) | −30 |
| `Step3Weather.svelte` (NEU) | +150 |
| `Step4Reports.svelte` (NEU) | +140 |
| `wizardState.svelte.ts` (1 Feld + toTripPayload) | +15 |
| `TripWizardShell.svelte` (Labels + Imports) | +6 / −6 |
| **Gesamt** | ~+275 netto (override auf 300 LoC gesetzt) |

## Expected Behavior

- **Input:** Leerer Wizard-State beim Öffnen von `/trips/new`
- **Output:** Vollständig ausgefüllter Trip mit `name`, `startDate`, `stages`, `activity`, `weatherMetrics`, `report_config` nach Klick auf "Speichern" in Step 4
- **Side effects:** `POST /api/trips` wird beim finalen Speichern abgesetzt; bei Erfolg: Redirect auf `/trips`

## Acceptance Criteria

**AC-1:** Given der Wizard wird auf `/trips/new` geöffnet /
When Step 1 gerendert wird /
Then sind die Step-Labels in der Fortschrittsleiste "Route", "Etappen", "Wetter", "Reports" — kein "Profil", "GPX-Import", "Wegpunkte", "Briefings" mehr sichtbar.

**AC-2:** Given Step 1 (Route) ist geöffnet /
When der User nur Name und Startdatum ausfüllt (kein Activity-Chip, keine GPX) /
Then ist der "Weiter"-Button aktiv und der User kann zu Step 2 navigieren — Activity ist kein Pflichtfeld mehr.

**AC-3:** Given Step 1 (Route) ist geöffnet /
When der User eine GPX-Datei in die Dropzone zieht /
Then wird die Datei sofort verarbeitet und der User kann zu Step 2 wechseln, ohne dass in Step 2 ein Upload-Bereich erscheint.

**AC-4:** Given Step 2 (Etappen) zeigt erkannte Etappen aus einer GPX /
When N Etappen mit Wegpunkt-Vorschlägen vorhanden sind /
Then zeigt jede betroffene Etappe eine orange-dashed Pill mit dem Text "+N Vorschläge" und der Header lautet "N ETAPPEN ERKANNT AUS N GPX".

**AC-5:** Given Step 3 (Wetter) wird geöffnet /
When der Metrik-Katalog von `/api/metrics` geladen wurde /
Then zeigt jede aktivierte Metrik ihren Namen, drei HorizonChips (HEUTE/MORGEN/ÜBERMORGEN) und ein Format-Label (Roh oder Indikator) in einer Tabellenzeile.

**AC-6:** Given Step 3 (Wetter) ist geöffnet und `wizard.activity` ist null /
When der Hinweistext geprüft wird /
Then ist der Text "Standard-Metriken werden verwendet." sichtbar und der "Weiter"-Button ist trotzdem aktiv (kein Gate).

**AC-7:** Given Step 3 (Wetter) und der User wählt im Dropdown "Skitouren" /
When die Auswahl bestätigt wird /
Then ist `wizard.activity === 'ski_touring'` und der Hinweistext verschwindet.

**AC-8:** Given Step 4 (Reports) wird geöffnet /
When die vier Report-Cards gerendert werden /
Then sind "Abend-Briefing", "Morgen-Update" und "Warnungen" interaktiv (Checkbox + Zeit/Kanal) und "Trend-Vorschau" trägt die CSS-Klasse `disabled` sowie das Badge "Demnächst" — ohne interaktive Elemente.

**AC-9:** Given Step 4 (Reports) zeigt die Abend-Briefing-Card /
When der User die Uhrzeit auf "20:00" ändert /
Then enthält `wizard.briefings.reports.evening.time === '20:00'` und `toTripPayload()` schreibt `report_config.evening_time: "20:00:00"`.

**AC-10:** Given der User hat `weatherMetrics` in Step 3 konfiguriert (nicht leer) /
When `toTripPayload()` aufgerufen wird /
Then enthält das zurückgegebene Trip-Objekt `display_config.metrics` mit dem konfigurierten Metrik-Array.

## Out of Scope

- Activity-basierte Metrik-Vorauswahl (welche Metriken bei "Skitouren" default aktiv sind) — das ist Katalog-Logik im Backend, nicht im Wizard
- "Vom letzten Trip kopieren"-Button (UI-Element vorhanden, Funktion als no-op oder deaktiviert bis eigenem Issue)
- Step 3 Wetter: Speichern von Metrik-Änderungen zurück in den Katalog — nur in `wizard.weatherMetrics` gehalten, kein PUT auf `/api/metrics`
- Trend-Vorschau Card (Step 4): vollständige Implementierung (separates Issue)
- `Step3Waypoints.svelte` — bleibt als leere Fallback-Datei erhalten, wird nicht gelöscht

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Labels + Imports (~12 LoC) |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `weatherMetrics`-Feld + `canAdvanceStep1` + `toTripPayload()` (~20 LoC) |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Komplett ersetzt: Activity-Chips + Shortcode entfernt, GPX-Dropzone als Hauptelement |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Drop-Zone entfernt, neuer Badge-Header, Vorschläge-Pill (~−30 / +20 LoC) |
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | Leer belassen (Fallback) |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` | NEU (~150 LoC) |
| `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` | NEU (~140 LoC) |
| `frontend/e2e/trip-wizard-step1.spec.ts` | Activity-Chip-Refs entfernt, GPX-Dropzone-Ref ergänzt |
| `frontend/e2e/trip-wizard-step3.spec.ts` | Komplett umgeschrieben (Wetter-Step) |
| `frontend/e2e/trip-wizard-step4.spec.ts` | 4-Cards-Layout geprüft |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | `canAdvanceStep1`-Tests: Activity-Pflicht entfernen |

## Known Limitations

- `"Vom letzten Trip kopieren"` in Step 1 ist als Button sichtbar, aber funktionslos bis ein separates Issue die Kopier-Logik implementiert (API-Endpoint für Trip-Klonen existiert nicht).
- `Step3Waypoints.svelte` bleibt als leere Datei erhalten, um bestehende Import-Referenzen (falls vorhanden) nicht zu brechen. Sie rendert nichts.
- Wenn `/api/metrics` in Step 3 fehlschlägt, zeigt der Step einen Lade-Spinner ohne Fallback-Metriken — Fehler-Handling (Retry, Toast) ist nicht Teil dieser Spec.

## Changelog

- 2026-05-26: Initial spec erstellt (Issue #300 — Trip-Wizard Redesign Route/Etappen/Wetter/Reports).
