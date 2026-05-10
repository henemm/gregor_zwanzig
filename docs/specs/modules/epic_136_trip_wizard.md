---
entity_id: epic_136_trip_wizard
type: module
created: 2026-05-09
updated: 2026-05-09
status: approved
version: "1.0"
tags: [sveltekit, frontend, wizard, trip-creation, epic-136, master-spec]
---

# Epic 136 — Trip-Wizard (Master-Spec, Issues #160–#165)

## Approval

- [x] Approved (2026-05-09)

## Purpose

Definiert das gemeinsame Fundament fuer den vollstaendig neu gebauten Trip-Wizard auf `/trips/new` — Datenmodell-Erweiterungen (`Trip.shortcode`, `Trip.activity`), Verzeichnisstruktur unter `frontend/src/lib/components/trip-wizard/`, zentrales Wizard-State-Schema, geteilte Helper (`wizardHelpers.ts`) sowie das Mapping der fuenf neuen UI-Aktivitaetsprofile auf die vier kanonischen Aggregations-Profile aus `activity_profile.md`. Diese Master-Spec ist die Single Source of Truth fuer alle sechs Sub-Issues (#160 Shell, #161 Step 1, #162 Step 2, #163 Step 3, #164 Step 4, #165 Vorlagen) — die UI-Detailspezifikation jedes Schritts erfolgt in eigenen Sub-Specs, die sich auf dieses Dokument beziehen.

## Source

### Neu (NEU)

- `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` — zentrale Svelte-5-Runes-State-Klasse fuer den 4-Schritt-Wizard
- `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` — `newId()`, `today()`, `addDays()`, `mapActivityToProfile()`, `formatStageNumber()`, `isPauseStage()`
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` — Shell-Komponente (Stepper + Step-Slot + Vor/Zurueck) — Detail in Sub-Spec zu #160
- `frontend/src/lib/components/trip-wizard/Stepper.svelte` — generischer 4-Step-Stepper — Detail in Sub-Spec zu #160
- `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` — Sub-Spec zu #161
- `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` — Sub-Spec zu #162
- `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` — Sub-Spec zu #163
- `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` — Sub-Spec zu #164
- `frontend/src/lib/components/trip-wizard/templates/TemplatePicker.svelte` — Sub-Spec zu #165
- Sub-Spec-Dateien (Stubs, jeweils mit Verweis auf diese Master-Spec):
  - `docs/specs/modules/epic_136_step0_shell.md`
  - `docs/specs/modules/epic_136_step1_profile.md`
  - `docs/specs/modules/epic_136_step2_stages.md`
  - `docs/specs/modules/epic_136_step3_waypoints.md`
  - `docs/specs/modules/epic_136_step4_briefings.md`
  - `docs/specs/modules/epic_136_step5_templates.md`

### Edit (EDIT)

- `internal/model/trip.go` — Felder `Shortcode string` und `Activity string` zur `Trip`-Struktur hinzufuegen (omitempty)
- `frontend/src/lib/types.ts` — `Trip.shortcode?: string`, `Trip.activity?: ActivityType`, neuer `ActivityType`-Union-Typ; `Waypoint.suggested?: boolean` (transientes Wizard-Flag)
- `frontend/src/routes/trips/new/+page.svelte` — ersetzt den 3-Zeilen-Mount des alten `TripWizard` durch `TripWizardShell`
- `frontend/src/routes/trips/new/+page.server.ts` — bleibt strukturell unveraendert; ggf. spaeter Vorlagen-Liste laden (Sub-Issue #165)

### Delete (folgt nach Sub-Issues)

Die folgenden Dateien werden geloescht, sobald der neue Wizard alle Sub-Issues #160–#165 ablaufen kann. Loeschung erfolgt im letzten Sub-Issue oder als Cleanup-Folge-Issue (NICHT im Rahmen dieser Master-Spec):

- `frontend/src/lib/components/wizard/TripWizard.svelte`
- `frontend/src/lib/components/wizard/WizardStepper.svelte`
- `frontend/src/lib/components/wizard/WizardStep1Route.svelte`
- `frontend/src/lib/components/wizard/WizardStep2Stages.svelte`
- `frontend/src/lib/components/wizard/WizardStep3Weather.svelte`
- `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte`
- `frontend/src/lib/components/edit/TripEditView.svelte` (importiert die alten Wizard-Steps; Edit-Pfad-Refactor ist Folge-Issue, siehe Not In Scope)

## Child Issues

| Issue | Titel | Bereich | Sub-Spec |
|-------|-------|---------|----------|
| #160 | Wizard: Shell + 4-Schritt-Stepper | Wrapper-Layout, Stepper, Vor/Zurueck-Navigation | `epic_136_step0_shell.md` |
| #161 | Step 1: Aktivitaetsprofil + Eckdaten | 5 ProfileChips + Name/Kuerzel/Zeitraum | `epic_136_step1_profile.md` |
| #162 | Step 2: GPX-Multi-Upload + Drag-Sort + Pause | Drop-Zone, sortierbare Etappen, Pausentag, T01-Nummerierung | `epic_136_step2_stages.md` |
| #163 | Step 3: KI-Waypoints bestaetigen | Etappen links, Waypoint-Confirm-UI rechts | `epic_136_step3_waypoints.md` |
| #164 | Step 4: Briefings & Kanaele | Kanal-Toggles, ReportRow, ThresholdRow | `epic_136_step4_briefings.md` |
| #165 | Trip-Vorlagen | Rechte Spalte in Step 2: GR20, KHW, Stubai | `epic_136_step5_templates.md` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/ui/btn/Btn.svelte` | component (Epic #133) | Vor/Zurueck/Speichern-Buttons, "Pause einfuegen" |
| `$lib/components/ui/g-card/GCard.svelte` | component (Epic #133) | Container fuer Step-Inhalte und Vorlagen-Karten |
| `$lib/components/ui/pill/Pill.svelte` | component (Epic #133) | Etappen-Pills (T01, T02 ...) und Profil-Chips |
| `$lib/components/ui/eyebrow/Eyebrow.svelte` | component (Epic #133) | Step-Titel-Eyebrow ("Schritt 2 von 4") |
| `$lib/components/ui/dot/Dot.svelte` | component (Epic #133) | Stepper-Done/Pending-Indikator |
| `$lib/components/ui/topo/TopoBg.svelte` | component (Epic #133) | Optionaler Hintergrund auf Profil-Chips |
| `$lib/components/ui/elev-sparkline/ElevSparkline.svelte` | component (Epic #133) | Hoehenprofil pro Etappe in Step 3 |
| `frontend/src/lib/types.ts` | file (edit) | Aufnahme von `ActivityType`, `Trip.shortcode`, `Trip.activity`, `Waypoint.suggested` |
| `internal/model/trip.go` | file (edit) | Aufnahme von `Trip.Shortcode`, `Trip.Activity` |
| `internal/handler/trip.go` | file (referenz) | Read-Modify-Write-Pflicht aus CLAUDE.md §Daten-Schema-Reworks |
| `POST /api/trips` | API endpoint | Persistiert Trip am Ende von Step 4 |
| `POST /api/gpx/upload` | API endpoint | Liefert Stage aus hochgeladenem GPX (Step 2) — bestehend |
| `POST /api/gpx/parse` | API endpoint | Liefert Segmente + KI-Waypoint-Vorschlaege (Step 3) — bestehend |
| `docs/specs/modules/activity_profile.md` | spec | Kanonische 4-Werte-Whitelist fuer `aggregation.profile` (Backend-Behavior-Key) |
| `docs/specs/modules/gpx_multi_import.md` | spec | Multi-Upload-Logik (`naturalSort`, `uploadGpx`, `commitPending`) — wandert nach Step 2 |
| `docs/specs/modules/elevation_analysis.md` | spec | Wetterscheiden-Erkennung — Basis fuer Step 3 |
| `docs/specs/modules/hybrid_segmentation.md` | spec | Segmentierungs-Pipeline — Basis fuer Step 3 |
| Epic #133 Lauf A + B | prerequisite | Tokens und alle Atom-Komponenten muessen deployed sein |
| Epic #134 Cockpit | prerequisite | "Neuer Trip"-CTA in Topbar verlinkt auf `/trips/new` |

## Implementation Details

### 1. Datenmodell-Patches

#### 1.1 `internal/model/trip.go`

Zwei neue Felder zur `Trip`-Struktur — beide optional (`omitempty`), brechen keinen Bestand:

```go
type Trip struct {
    ID               string                 `json:"id"`
    Name             string                 `json:"name"`
    Shortcode        string                 `json:"shortcode,omitempty"`
    Activity         string                 `json:"activity,omitempty"`
    Stages           []Stage                `json:"stages"`
    AvalancheRegions []string               `json:"avalanche_regions,omitempty"`
    Aggregation      map[string]interface{} `json:"aggregation,omitempty"`
    WeatherConfig    map[string]interface{} `json:"weather_config,omitempty"`
    DisplayConfig    map[string]interface{} `json:"display_config,omitempty"`
    ReportConfig     map[string]interface{} `json:"report_config,omitempty"`
}
```

`Activity` ist ein `string` (kein Go-Enum), die Werte werden Frontend-seitig kanonisiert. Die Validierung der erlaubten Werte erfolgt im Frontend und in der Save-Pipeline (siehe 1.4); das Backend nimmt den String unveraendert entgegen, weil das `aggregation.profile`-Feld die behaviorrelevante Whitelist haelt (siehe `activity_profile.md` §11.A8).

#### 1.2 `frontend/src/lib/types.ts`

```typescript
export type ActivityType = 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb';

export interface Waypoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  elevation_m: number;
  time_window?: string;
  suggested?: boolean;   // transientes Wizard-Flag (Step 3); wird beim Save entfernt
}

export interface Trip {
  id: string;
  name: string;
  shortcode?: string;
  activity?: ActivityType;
  stages: Stage[];
  avalanche_regions?: string[];
  aggregation?: Record<string, unknown>;
  weather_config?: Record<string, unknown>;
  display_config?: Record<string, unknown>;
  report_config?: Record<string, unknown>;
}
```

`ActivityType` ist Frontend-Single-Source-of-Truth fuer die fuenf neuen UI-Profile. `Waypoint.suggested` ist explizit transient — die Save-Pipeline (1.4) strippt das Flag, bevor `POST /api/trips` ausgeloest wird, und persistiert nur bestaetigte Wegpunkte.

#### 1.3 Mapping UI-Aktivitaet → Aggregations-Profil

Das bestehende `aggregation.profile` (Werte aus `activity_profile.md`: `wintersport | wandern | summer_trekking | allgemein`) bleibt der Backend-Behavior-Key. Frontend mappt:

| UI-Aktivitaet (`activity`) | Aggregations-Profil (`aggregation.profile`) | Begruendung |
|----------------------------|---------------------------------------------|-------------|
| `trekking` | `summer_trekking` | Alpine Mehrtagestour-Semantik |
| `skitour` | `wintersport` | Schnee/Lawinen-Logik |
| `hochtour` | `summer_trekking` | mangels eigenem Profil; Folge-Issue falls Aggregations-Semantik abweichen muss |
| `klettersteig` | `summer_trekking` | alpine Tageslogik |
| `mtb` | `allgemein` | generischer Default |

Implementierung in `wizardHelpers.ts`:

```typescript
import type { ActivityType } from '$lib/types';

export type AggregationProfile = 'wintersport' | 'wandern' | 'summer_trekking' | 'allgemein';

export function mapActivityToProfile(activity: ActivityType): AggregationProfile {
  switch (activity) {
    case 'skitour':       return 'wintersport';
    case 'trekking':      return 'summer_trekking';
    case 'hochtour':      return 'summer_trekking';
    case 'klettersteig':  return 'summer_trekking';
    case 'mtb':           return 'allgemein';
  }
}
```

#### 1.4 Save-Pipeline (Schritt 4 → `POST /api/trips`)

Wird ausgeloest, sobald der User in Step 4 "Speichern" klickt. Reihenfolge:

1. WizardState in plain JSON serialisieren (`state.toTrip()`).
2. Etappen mit `waypoints.length === 0` bleiben als Pausentag erhalten (kein Filter).
3. Aus jedem Wegpunkt das `suggested`-Flag entfernen (`{ ...wp, suggested: undefined }`); rejected suggestions sind bereits aus dem Array geloescht (Step 3).
4. `aggregation.profile` aus `state.activity` ableiten (`mapActivityToProfile`); falls vom User in Step 4 explizit ueberschrieben, gewinnt User-Wahl.
5. `POST /api/trips` mit dem vollstaendigen Trip-Body.
6. Bei HTTP 201 + `id` in der Response: Redirect auf `/trips/${id}` (Trip-Uebersicht aus Epic #135 — falls noch nicht vorhanden, Fallback auf `/`).
7. Bei Fehler: Inline-Fehlermeldung am Save-Button, kein Toast (Konsistenz mit Cockpit-Pattern aus Epic #134).

Edit-Pfad (`PUT /api/trips/{id}`) ist NICHT Teil dieser Master-Spec; der bestehende `TripEditView`-Pfad bleibt vorerst aktiv, bis ein Folge-Issue den Edit-Refactor anstoesst.

---

### 2. Verzeichnisstruktur

```
frontend/src/lib/components/trip-wizard/
├── wizardState.svelte.ts          # zentrale Runes-State-Klasse (siehe 3.1)
├── wizardHelpers.ts               # newId, today, addDays, mapActivityToProfile, formatStageNumber, isPauseStage
├── TripWizardShell.svelte         # Shell: Stepper + Step-Slot + Vor/Zurueck (Sub-Issue #160)
├── Stepper.svelte                 # 4-Step-Indikator mit Done/Active/Pending (Sub-Issue #160)
├── steps/
│   ├── Step1Profile.svelte        # Sub-Issue #161
│   ├── Step2Stages.svelte         # Sub-Issue #162
│   ├── Step3Waypoints.svelte      # Sub-Issue #163
│   └── Step4Briefings.svelte      # Sub-Issue #164
└── templates/
    └── TemplatePicker.svelte      # Sub-Issue #165
```

Die alten Komponenten unter `frontend/src/lib/components/wizard/` und `frontend/src/lib/components/edit/TripEditView.svelte` bleiben waehrend des Uebergangs unangetastet — bis zum Cleanup-Folge-Issue.

---

### 3. Wizard-State-Schema

#### 3.1 Zentrale Runes-State-Klasse

`wizardState.svelte.ts` exportiert eine Klasse mit `$state`-Feldern, die alle vier Steps ueber `setContext`/`getContext` teilen. Sub-Specs der einzelnen Steps duerfen ausschliesslich Felder aus diesem Schema lesen/schreiben — kein Step-lokaler Trip-State.

```typescript
import type { Stage, Waypoint, ActivityType } from '$lib/types';

export interface BriefingConfig {
  channels: {
    email: boolean;
    signal: boolean;
    telegram: boolean;
    sms: boolean;
  };
  reports: {
    morning: { enabled: boolean; time: string };  // "06:00"
    evening: { enabled: boolean; time: string };  // "18:00"
  };
  thresholds: {
    gust_kmh: number | null;        // Boeen
    precip_mm: number | null;       // Niederschlag
    thunder_level: 'NONE' | 'MED' | 'HIGH' | null;
    snow_line_m: number | null;     // Schneefallgrenze
  };
}

export class WizardState {
  // Step 1
  activity = $state<ActivityType | null>(null);
  name = $state('');
  shortcode = $state('');
  startDate = $state('');           // ISO yyyy-mm-dd
  endDate = $state('');             // ISO yyyy-mm-dd; derived in Step 2

  // Step 2
  stages = $state<Stage[]>([]);     // leeres waypoints-Array == Pausentag

  // Step 3
  // (Wegpunkte leben innerhalb stages[i].waypoints; suggested-Flag siehe 1.2)

  // Step 4
  briefings = $state<BriefingConfig>({
    channels: { email: true, signal: false, telegram: false, sms: false },
    reports: { morning: { enabled: true, time: '06:00' }, evening: { enabled: true, time: '18:00' } },
    thresholds: { gust_kmh: null, precip_mm: null, thunder_level: null, snow_line_m: null }
  });

  // Navigation
  currentStep = $state<1 | 2 | 3 | 4>(1);
  saveStatus = $state<'idle' | 'saving' | 'ok' | 'error'>('idle');
  saveError = $state<string | null>(null);

  // Derived
  derivedAggregationProfile = $derived(
    this.activity ? mapActivityToProfile(this.activity) : null
  );

  // ... Methoden: nextStep(), prevStep(), addStage(), addPauseStage(), reorderStages(), toTripPayload()
}
```

#### 3.2 Pausentag-Konvention

Stage mit `waypoints.length === 0` ist ein Pausentag. KEIN neues Feld am Modell. UI-Logik:

```typescript
export function isPauseStage(stage: Stage): boolean {
  return !stage.waypoints || stage.waypoints.length === 0;
}
```

Render-Konsequenz: Pausentage zeigen statt Etappennamen den Text "Pausentag" und keinen ElevSparkline.

#### 3.3 Etappen-Nummerierung "T01"

Reine UI-Concern, NICHT persistieren. Wird aus dem Stage-Index berechnet:

```typescript
export function formatStageNumber(index: number): string {
  return `T${String(index + 1).padStart(2, '0')}`;
}
```

Pausentage bekommen keine T-Nummer (UI-Entscheidung in Sub-Spec zu #162).

#### 3.4 KI-Waypoint-Vorschlaege (Step 3)

Backend-Pipeline ist fertig (`POST /api/gpx/parse` aus `src/web/pages/gpx_upload.py`). Step 3 ruft den Endpoint pro Etappe auf, erhaelt Vorschlaege, fuegt sie mit `suggested: true` ins `waypoints`-Array ein. User-Aktion:

- "Bestaetigen" → `wp.suggested = false` (wird beim Save zu festem Wegpunkt; Flag entfernt)
- "Verwerfen" → Wegpunkt aus dem Array entfernen

Render-Hinweis (Detail in Sub-Spec zu #163): orange-gestrichelte Pins fuer `suggested === true`, durchgehende Pins fuer bestaetigte Wegpunkte.

---

### 4. Vertraege Master-Spec ↔ Sub-Specs

Diese Master-Spec **garantiert** den Sub-Issues:

1. `WizardState`-Klasse ist verfuegbar und wird von `TripWizardShell` per Context bereitgestellt (`setContext('trip-wizard-state', state)`).
2. `wizardHelpers.ts` exportiert `newId`, `today`, `addDays`, `mapActivityToProfile`, `formatStageNumber`, `isPauseStage`.
3. Datenmodell-Felder `Trip.shortcode`, `Trip.activity`, `Waypoint.suggested` sind auf BE+FE persistierbar bzw. typisiert.
4. Mapping UI-Aktivitaet → Aggregations-Profil ist getestet (1.3).
5. Save-Pipeline (1.4) ist zentral — Step 4 ruft nur `state.save()` auf.

Sub-Specs **muessen liefern**:

1. UI-Detail jedes Schritts (Layout, Atom-Verwendung, Validierung, E2E-Tests).
2. Verweis auf diese Master-Spec im Frontmatter (`related: epic_136_trip_wizard`).
3. Akzeptanzkriterien je Sub-Issue.
4. Keine Aenderungen am `WizardState`-Schema ohne Update dieser Master-Spec.

---

### 5. Implementierungsreihenfolge

1. **Master-Spec genehmigen** (dieses Dokument; `[x] Approved`)
2. **Modell-Patches** — `internal/model/trip.go` + `frontend/src/lib/types.ts` (Felder hinzufuegen, kompiliert ohne Bruch)
3. **Helper + State** — `wizardHelpers.ts` + `wizardState.svelte.ts` mit Unit-Tests fuer `mapActivityToProfile` und `formatStageNumber`
4. **Sub-Issue #160** — Shell + Stepper, mountet leere Steps 1–4, integriert in `/trips/new`
5. **Sub-Issue #161** — Step 1 Profil/Eckdaten
6. **Sub-Issue #162** — Step 2 GPX-Multi-Upload + Drag-Sort + Pause
7. **Sub-Issue #163** — Step 3 KI-Waypoints
8. **Sub-Issue #164** — Step 4 Briefings + Save-Pipeline scharf schalten
9. **Sub-Issue #165** — Vorlagen (rechte Spalte in Step 2)
10. **Cleanup-Folge-Issue** — alter `wizard/`-Ordner und `edit/TripEditView.svelte` loeschen, Edit-Pfad refaktorieren

## Expected Behavior

- **Input:** User klickt im Cockpit (Epic #134) auf den CTA "Neuer Trip" oder navigiert direkt auf `/trips/new`.
- **Output:**
  - `TripWizardShell` rendert mit Stepper (4 Schritte: Profil, GPX, Wegpunkte, Briefings) und initial aktivem Schritt 1.
  - Jeder Schritt liest und schreibt zentralen `WizardState` per Svelte-Context.
  - Pausentage sind Etappen mit leerem `waypoints`-Array; T-Nummern werden im UI berechnet.
  - Beim Klick auf "Speichern" in Step 4 wird `POST /api/trips` aufgerufen; bei Erfolg Redirect auf `/trips/${id}`, bei Fehler Inline-Anzeige.
- **Side effects:**
  - Persistente Felder `Trip.shortcode` und `Trip.activity` landen im JSON-Persistenz-Layer (data/users/...). Bestaende ohne diese Felder bleiben gueltig (omitempty).
  - `aggregation.profile` wird beim Save automatisch aus `activity` abgeleitet (sofern nicht explizit gesetzt).
  - `Waypoint.suggested`-Flag wird vor dem Save gestrippt — kein transienter UI-State landet in der Persistenz.

## Known Limitations

- Edit-Pfad (`/trips/[id]/edit` ueber `TripEditView`) bleibt waehrend dieses Epics auf den alten Wizard-Komponenten — Refactor ist Folge-Issue. Solange darf der alte `wizard/`-Ordner NICHT geloescht werden.
- `hochtour` und `klettersteig` mappen aktuell beide auf `summer_trekking`. Falls die Aggregations-Semantik fuer diese Profile abweichen muss, eroeffnet ein Folge-Issue eine Erweiterung des kanonischen Enums in `activity_profile.md` §A8.
- Vorlage GR20 (Korsika) hat aktuell keine GPX-Daten im Repo (nur Golden-Outputs fuer SMS/Email-Tests). Sub-Issue #165 wird das adressieren — entweder GPX-Beschaffung oder Skope-Anpassung auf KHW + Stubai.
- Save-Pipeline hat keinen optimistischen UI-State — bei langsamen API-Calls sieht der User zwischen Klick und Redirect den Save-Status `'saving'` ohne weiteren Feedback; ist akzeptierter Zwischenstand.
- Bei mehreren Trips mit ueberlappendem Zeitraum gibt es keine Konfliktwarnung — Sub-Issue #161 koennte das spaeter ergaenzen.
- `WizardState.startDate` und `WizardState.endDate` sind als `string | null` typisiert (Implementation), nicht als leerer String (Spec §3.1 Pseudo-Code). Bewusste Abweichung: `null` ist semantisch klarer fuer „nicht gewaehlt"; Aufrufer von `addDays(state.startDate, ...)` muessen vorher null-checken. Spec §3.1 ist als Schema-Skizze zu verstehen, nicht als wortgetreue Vorgabe.
- `WizardState.toTripPayload()` mappt `briefings` (Channels, Reports, Thresholds) noch NICHT auf `Trip.report_config`. Sub-Issue #164 (Step 4 Briefings & Kanaele) ist verantwortlich, das Mapping zu ergaenzen — bis dahin gehen Briefing-Einstellungen beim Speichern verloren. Dieses Master-Fundament liefert nur das Schema und den State, nicht die Persistenz-Bruecke.

## Not In Scope

- **Edit-Pfad-Refactor** (`TripEditView.svelte`) — eigenes Folge-Issue, nachdem alle Sub-Issues #160–#165 gemerged sind.
- **Backend-Aggregations-Profil-Erweiterung** — falls fuer `hochtour`/`klettersteig` eigene Aggregations-Semantik noetig wird, ist das ein eigener Spec gegen `activity_profile.md` (Whitelist-Erweiterung in Python + Go gemaess §A8).
- **Risk-Engine-Integration** in Etappen-Pills — gehoert zu einem spaeteren Epic.
- **Trip-Vorlage GR20** mit GPX-Daten — Sub-Issue #165 entscheidet ueber Skope.
- **Aenderungen an Sidebar, Layout, Auth-Guards, Hooks**.
- **Drag-and-Drop-Bibliothek-Wahl** — Sub-Spec zu #162 entscheidet (vermutlich `svelte-dnd-action` oder native HTML5 DnD).
- **Loeschen alter `wizard/`-Komponenten** — Cleanup-Folge-Issue, NICHT in dieser Master-Spec.

## Acceptance Criteria

| # | Kriterium | Pruefung |
|---|-----------|----------|
| 1 | `Trip.Shortcode` und `Trip.Activity` Felder existieren in `internal/model/trip.go` mit `omitempty`-Tag | Grep + Go-Build gruen |
| 2 | `Trip.shortcode?: string` und `Trip.activity?: ActivityType` existieren in `frontend/src/lib/types.ts` | Grep + `tsc --noEmit` gruen |
| 3 | `ActivityType`-Union mit genau 5 Werten ist exportiert | Grep + Unit-Test gegen Type-Set |
| 4 | `Waypoint.suggested?: boolean` ist als optional in `types.ts` deklariert | Grep |
| 5 | Verzeichnis `frontend/src/lib/components/trip-wizard/` existiert mit Unterordnern `steps/` und `templates/` | `ls` |
| 6 | `wizardHelpers.ts` exportiert `newId`, `today`, `addDays`, `mapActivityToProfile`, `formatStageNumber`, `isPauseStage` | Grep + Unit-Tests |
| 7 | `mapActivityToProfile` deckt alle 5 UI-Werte und liefert nur 4 kanonische Aggregations-Werte zurueck | Unit-Test (5 Cases, exhaustiv) |
| 8 | `formatStageNumber(0) === 'T01'`, `formatStageNumber(9) === 'T10'`, `formatStageNumber(99) === 'T100'` | Unit-Test |
| 9 | `WizardState`-Klasse exportiert in `wizardState.svelte.ts` mit allen Feldern aus 3.1 | Grep + Type-Check |
| 10 | Sub-Spec-Stubs fuer #160–#165 existieren in `docs/specs/modules/` mit Verweis auf diese Master-Spec | Grep `epic_136_trip_wizard` in jeder Sub-Spec |
| 11 | Bestaende ohne `shortcode`/`activity`/`suggested` laden ohne Fehler | Existing trips load test (Roundtrip) |
| 12 | Loaded-Trip ohne `activity` rendert in Step 1 mit `null`-Auswahl, ohne Crash | Manuell + E2E auf bestehendem GR221-Trip |

## Changelog

- 2026-05-10: §3.1 erweitert um additives Feld `get canAdvanceStep1(): boolean`
  (Getter, nicht `$derived` — Plain-Node-Test-Kompatibilitaet,
  Svelte-5-reaktivitaets-kompatibel da Read von `$state`-Feldern). Detail in
  Sub-Spec [`epic_136_step1_profile.md`](./epic_136_step1_profile.md) §6.
  Folge-Steps (#162–#164) ergaenzen analog `canAdvanceStep2/3/4`.
- 2026-05-09: Implementation Iter-2 abgeschlossen — Backend-Validator `validateTrip` akzeptiert jetzt Stages mit leerem `waypoints[]` (Pausentage), `BriefingConfig.thresholds` auf `number | null` mit `null`-Defaults umgestellt. F004 (`startDate`-Type) und F006 (`briefings`→`report_config`-Mapping) als Known Limitations dokumentiert. Adversary-Validator: alle HIGH/MEDIUM-Findings erledigt.
- 2026-05-09: Implementation Iter-1 abgeschlossen — `Trip.Shortcode` + `Trip.Activity` (Go), `ActivityType` + `Trip.shortcode?`/`Trip.activity?`/`Waypoint.suggested?` (TS), `wizardHelpers.ts` (6 Helper) und `wizardState.svelte.ts` (`WizardState` mit `BriefingConfig`, Save-Pipeline, Step-Navigation) angelegt. 23 TS-Tests + 5 Go-Tests grün.
- 2026-05-09: Initial Master-Spec erstellt — Datenmodell-Patches, Verzeichnisstruktur, WizardState-Schema, Mapping-Tabelle, Save-Pipeline, Vertraege zu Sub-Specs (Issues #160–#165). Tech-Lead-Entscheidungen vom 2026-05-09 (User-approved): Bestand wird ersetzt, neuer Ordner `trip-wizard/`, neue Felder `shortcode`+`activity`, Pausentag = leeres `waypoints`-Array, T01-Nummerierung als UI-Concern, KI-Vorschlaege via `suggested`-Flag.
