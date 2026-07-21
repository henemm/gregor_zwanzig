---
entity_id: feat_1301_f2a_compare_new_trip_pattern
type: feature
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [epic-1301, epic-1273, compare, trip-new-pattern, progressive-editor]
---

# Epic #1301 Scheibe F2a — `/compare/new` als Progressive-Tab-Editor nach Trip-Muster

## Approval

- [x] Approved (PO-Freigabe 2026-07-19, inkl. LoC-Override 950)

## Purpose

Die Anlege-Strecke des Ortsvergleichs (`/compare/new`) läuft heute über `CompareEditor mode="create"`
(`frontend/src/lib/components/compare/CompareEditor.svelte`, 1.686 Zeilen) — einen eigenständigen
Stepper/Tab-Hybrid mit eigener Freischalt-Logik (`compareEditorLogic.ts`), eigenem Layout-Tab
(Attrappe: `channel_layouts`, das der Compare-Renderpfad nie liest — #1301-Grundbefund) und ohne
Wetter-Metriken-Grundauswahl (Lücke seit C1: `WeatherMetricsTab` wird im heutigen Create-Modus gar
nicht gemountet). Der bereits umgesetzte Trip-Anlege-Editor `TripNewEditor` (#622) etabliert dagegen
das PO-verbindliche Muster: „Anlegen ist der Erstellen-Modus desselben Tab-Editors" — Progressive
Tabs, reine Freischalt-Logik als Funktionen (`tripNewLogic.ts`), lokaler State, EIN `POST` am Schluss.

**PO-Richtung (2026-07-19, verankert in `CLAUDE.md` § „Trip/Ortsvergleich-Code-Teilung"):**
„Möglichst viel Code zwischen Trip und Ortsvergleich teilen; der Compare-Editor funktioniert wie der
Trip-Editor." Ein neuer Compare-Baustein, zu dem ein Trip-Pendant existiert, ist laut derselben
Konvention nur mit dokumentierter Begründung zulässig — diese Spec dokumentiert die Ausnahme (siehe
ADR unten): die Anlege-Shell selbst ist wie beim Trip-Vorbild je Domäne eigen, geteilt sind die
Organismen und das Logik-Muster.

Diese Scheibe (F2a) ersetzt `/compare/new` durch `CompareNewEditor` — den strukturellen Spiegel von
`TripNewEditor` — zusammengesetzt aus den bereits geteilten Organismen (`WeatherMetricsTab`,
`CorridorEditor`, `AlarmeTab`, `VersandTab`) plus dem wiederverwendeten `Step2Orte` und einer neu
extrahierten geteilten Stundenverlauf-Komponente. Der Alt-Editor (`CompareEditor.svelte`) bleibt in
F2a **unangetastet als Rollback-Punkt** im Repo; seine Löschung ist F2b (separater Workflow).

## Source

- **Analyse:** `docs/context/f2a-1301-compare-new-trip-pattern.md` (3 parallele Explore-Agenten:
  Trip-Vorbild, heutiger Compare-Anlege-Fluss, Organismen-Readiness + E2E-Verträge).
- **Vorbild-Spec:** `docs/specs/_archive/modules/issue_622_trip_new_progressive_editor.md` (+ `issue_661_trip_new_mobile.md`).
- **E2E-Vertragslage:** `docs/specs/_archive/modules/epic_1273_s4c_e2e_migration.md` (Testid-Familien auf `/compare/new`).
- **S5-Programmplan:** `docs/features/epic-1273-compare-one-surface.md`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (#622) | Produktivcode, Vorbild | Struktureller Spiegel: `TAB_DEFS` (Z. 38-45), lokaler State, `beforeNavigate`-Guard (Z. 332-339, Muster) |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` (#622) | Produktivcode, Vorbild | Reine Funktionen `unlockedTabs`/`doneTabs`/`progressCount`/`canSave` — Vorbild für `compareNewLogic.ts` |
| `frontend/src/lib/components/compare/compareEditorLogic.ts` | Produktivcode, Basis | `TAB_ORDER` (Z. 11), `unlockedTabs`/`doneTabs` (Z. 27-45) — bestehende Freischalt-Kette wird um den neuen Wetter-Metriken-Tab erweitert, nicht verworfen |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Produktivcode, unverändert | `saveNewPreset()` (Z. 90-153): einziger `POST /api/compare/presets`, Redirect `goto('/compare/'+id)` (Z. 148) — bleibt der Persistenz-Weg, keine Änderung nötig |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | Produktivcode, wiederverwendet | 424 Zeilen, Context `compare-wizard-state`; #1080/#301/#951-Verhalten unverändert übernommen |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Produktivcode, geteilt | `context="vergleich"` (Z. 71/85), arbeitet nur auf `wiz`-State, kein PUT im vergleich-Zweig (Z. 596-624) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | Produktivcode, geteilt | `isFreshCompareCreate` (Z. 62) — explizite Anlage-Unterstützung mit Profil-Prefill, `syncToWizard()` (Z. 105-121) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Produktivcode, geteilt | 378 Zeilen, `context="vergleich"`, Save nur route-abhängig (kein Zwangs-PUT im Create) |
| `frontend/src/lib/components/shared/VersandTab.svelte` | Produktivcode, geteilt | 303 Zeilen, `context="vergleich"`, `activation`-Snippet für Aktivierungs-Banner |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Produktivcode, Quelle der Extraktion | Z. 1349-1373 (`hub-layout-hourly-wrap`, `ALL_HOURLY_METRICS`-Schleife) — Vorlage für die neu zu extrahierende geteilte Stundenverlauf-Komponente |
| `frontend/src/routes/compare/new/+page.svelte` | Produktivcode, wird umgebaut | Aktuell `<CompareEditor mode="create" locations={data.locations} />`, Server-Load liefert `data.locations`/`data.profile` |
| 21 Playwright-E2E-Dateien unter `frontend/e2e/` | Test, teilweise betroffen | slice4/layout-tab-vergleich/sortable-list-shared (Compare-Anteil) testen die entfallende Layout-Attrappe; restliche `/compare/new`-Specs (slice1/3, 951, 1080, s8d, 682, 718 AC-2, flow-navigation) laufen mit erhaltenen Testids gegen den neuen Editor weiter |

## Design-Entscheidung

`CompareNewEditor` ist ein **struktureller Spiegel von `TripNewEditor`** — eigene Shell im neuen
Verzeichnis `frontend/src/lib/components/compare-new/`, eigene reine Logikdatei `compareNewLogic.ts`
nach dem Vorbild `tripNewLogic.ts`. Geteilt sind ausschließlich die vier Organismen
(`WeatherMetricsTab`, `CorridorEditor`, `AlarmeTab`, `VersandTab`), der wiederverwendete
`Step2Orte`-Baustein und die neu extrahierte Stundenverlauf-Komponente — nicht die Shell selbst.
Das entspricht exakt dem bereits akzeptierten Präzedenzfall `TripNewEditor` (Trip-Pendant vorhanden =
dokumentierte Ausnahme von der Teilungs-Invariante, s. `CLAUDE.md`). Eine generische
Shell-Extraktion (eine Editor-Rahmen-Komponente für Trip UND Compare) ist ein möglicher **späterer**
Refactor (Radar-Kandidat), nicht Teil von F2a — die beiden Domänen unterscheiden sich im Tab-Inhalt
(Etappen/GPX vs. Orte) stark genug, dass eine vorzeitige Abstraktion hier mehr Kopplung als Nutzen
brächte.

Der Layout-Tab der neuen Seite enthält **ausschließlich** den C2-Stundenverlauf (Stundenverlauf-Toggle
+ Metrik-Auswahl, `CompareTabs.svelte:1349-1373`) als extrahierte geteilte Komponente
(`shared/CompareHourlyLayoutControls.svelte`), verwendet vom Hub UND von der neuen Anlege-Seite. Der
alte Wizard-Layout-Organism (channel-tabs, Top-N-Ranking, SMS-Budget/DnD-Sortierung —
`display_config.channel_layouts`, vom Compare-Renderpfad nie gelesen) entfällt **ersatzlos**, kein
Attrappen-Transfer.

## Scope

### Neue Dateien

| Datei | Beschreibung |
|-------|--------------|
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Editor-Shell: Tab-Bar (7 Tabs, s. u.), Fortschrittsbalken, Hero, „Briefing aktivieren"-CTA, mobile CSS-only-Switch (Vorbild `.tn-desktop`/`.tn-mobile`, `TripNewEditor.svelte:1046-1058`) |
| `frontend/src/lib/components/compare-new/compareNewLogic.ts` | Reine Funktionen: `unlockedTabs`, `doneTabs`, `progressCount`, `canActivate` — kein DOM, kein State-Mutieren, Vorbild `tripNewLogic.ts` |
| `frontend/src/lib/components/compare-new/__tests__/compareNewLogic.test.ts` | Kern-Unit-Tests (node:test) für alle Funktionen aus `compareNewLogic.ts`, netzfrei |
| `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte` | Extrahierte C2-Stundenverlauf-Komponente (Toggle + `{#each ALL_HOURLY_METRICS}`-Schleife), Props `wiz: CompareWizardState`, genutzt von Hub UND Anlege-Seite |
| `frontend/src/lib/components/shared/__tests__/CompareHourlyLayoutControls.struct.test.ts` | AST-/Struktur-Test: verifiziert die `{#each ALL_HOURLY_METRICS as metric}`-Schleife existiert (Anti-Hand-Kopie, Vorbild-Muster analog C2-Kern) |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `frontend/src/routes/compare/new/+page.svelte` | Mountet `<CompareNewEditor locations={data.locations} profile={data.profile} groups={data.groups} />` statt `CompareEditor mode="create"`; `setContext`-Aufrufe für `compare-wizard-state`/`compare-wizard-profile` bleiben (State-Instanziierung wandert ggf. in `CompareNewEditor`, Context-Namen unverändert, damit `Step2Orte`/Organismen unverändert funktionieren) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Z. 1349-1373 (`hub-layout-hourly-wrap`-Block) durch `<CompareHourlyLayoutControls wiz={wizardState} />` ersetzen — Verhalten identisch, keine neue Testid-Änderung nötig (bestehende Testids `compare-layout-hourly-*` wandern in die extrahierte Komponente) |
| `frontend/src/lib/components/compare/compareEditorLogic.ts` | **Unverändert** — bleibt Basis für `CompareEditor.svelte` (Alt-Editor lebt bis F2b); `compareNewLogic.ts` ist eine neue, eigene Datei, kein Umbau der bestehenden |

### E2E-Umbauten (Teil von F2a, nicht F2b)

| Datei | Änderung |
|-------|----------|
| `frontend/e2e/compare-editor-slice4.spec.ts` | Compare-Anteil der Layout-Attrappen-Blöcke (channel-tabs/Top-N/SMS-Budget-DnD) löschen bzw. auf `compare-layout-hourly-*`-Testids der neuen Seite umschreiben; verbleibende `/compare/new`-Testfälle (Z. 160, 184, 208, 243) bleiben als Regression gegen den neuen Editor bestehen |
| `frontend/e2e/layout-tab-vergleich.spec.ts` | Vollständig auf `/compare/new` + neue Layout-Tab-Testids (`compare-layout-hourly-*`) umschreiben; Wizard-Attrappen-Blöcke (channel-tabs/Top-N) löschen |
| `frontend/e2e/sortable-list-shared.spec.ts` | Compare-Teil (DnD über den alten Layout-Wizard-Tab) löschen — DnD-Abdeckung bleibt über den Trip-Kontext bestehen (SortableList ist geteilt, Trip-Block unangetastet) |
| `frontend/e2e/compare-editor-slice1.spec.ts`, `-slice3.spec.ts`, `issue-1080-*.spec.ts`, `issue-951-sheet-bottomnav.spec.ts` (Compare-Teil), `compare-editor-fidelity-s8d.spec.ts`, `issue-682-compare-editor-mobile.spec.ts`, `issue-718-idealwert-validation.spec.ts` AC-2, `compare-flow-navigation.spec.ts` (Create-ACs), `versand-tab-vergleich.spec.ts` AC-6 | **Regression, unverändert erwartet grün** — testen erhaltene Testids (`compare-editor-name/-activate/-continue-*/-profile-*`, `compare-step2-*`, `cm-mobile-*`/`top-app-bar-*`) gegen `/compare/new`; laufen ohne Codeänderung weiter, sofern `CompareNewEditor` dieselben Testids rendert |

**Alt-Editor bleibt unangetastet:** `CompareEditor.svelte`, `compareEditorLogic.ts`, `Step2Orte.svelte`
(weiterhin importiert, nicht gelöscht) bleiben vollständig im Repo — Rollback-Punkt, falls
`CompareNewEditor` in Staging Regressionen zeigt (Muster S3: alte Route/Komponente bleibt bis
Folge-Scheibe verifiziert ist).

## Tab-Struktur (7 Tabs)

| # | Tab | Freischalt-Bedingung | Optional | „Done"-Bedingung | visited-Flag |
|---|-----|----------------------|----------|-------------------|--------------|
| 1 | Vergleich (Name/Region/Profil) | immer offen | nein | Name gesetzt | — |
| 2 | Orte | Name gesetzt | nein | ≥2 Orte gewählt | — |
| 3 | Wetter-Metriken | ≥2 Orte gewählt | nein | Tab besucht | `metrikenVisited` |
| 4 | Wertebereiche | `metrikenVisited` | nein | Tab besucht | `idealsVisited` |
| 5 | Layout (Stundenverlauf) | `idealsVisited` | nein | Tab besucht | `layoutVisited` |
| 6 | Alarme | `layoutVisited` | nein | Tab besucht | `alarmeVisited` |
| 7 | Versand | `alarmeVisited` | nein | Tab besucht | `versandVisited` |

Freischalt-Kette entspricht der heutigen Kette aus `compareEditorLogic.ts` (Name → ≥2 Orte →
visited-Kaskade), erweitert um den neuen Wetter-Metriken-Tab zwischen Orte und Wertebereiche (schließt
die C1-Lücke: der heutige Create-Modus mountet `WeatherMetricsTab` gar nicht). „Briefing aktivieren"
ist erst aktiv, wenn `versandVisited` — analog zum Trip-Vorbild, wo „Tour speichern" erst nach
Zeitplan-Besuch aktiv wird.

### `compareNewLogic.ts` — Signaturen

```ts
export type CompareNewTabId =
	'vergleich' | 'orte' | 'metriken' | 'idealwerte' | 'layout' | 'alarme' | 'versand';

export interface CompareNewProgress {
	name: string;
	pickedCount: number;
	metrikenVisited: boolean;
	idealsVisited: boolean;
	layoutVisited: boolean;
	alarmeVisited: boolean;
	versandVisited: boolean;
}

export function unlockedTabs(p: CompareNewProgress): Set<CompareNewTabId>;
export function doneTabs(p: CompareNewProgress): Set<CompareNewTabId>;
export function progressCount(done: Set<CompareNewTabId>): number; // done.size, max 7
export function canActivate(done: Set<CompareNewTabId>): boolean;  // done.has('versand')
```

Reine Funktionen, kein DOM, keine Svelte-Runes — Vorbild `tripNewLogic.ts:14-68`. `pickedCount` liest
aus `wiz.pickedIds.length`, alle `*Visited`-Flags werden von `CompareNewEditor.svelte` beim
Tab-Wechsel (`$effect` oder `onclick`-Handler analog `TripNewEditor`) gesetzt und NICHT zurückgesetzt
(einmal besucht bleibt besucht, wie im Trip-Vorbild).

## Known Limitations

- **Kein Backend-Change.** `POST /api/compare/presets` (bestehend) bleibt unverändert; keine neue
  Route, kein neues Feld.
- **Alte Wizard-Layout-Attrappe entfällt ersatzlos.** `channel_layouts` (Top-N-Ranking,
  SMS-Budget/DnD-Sortierung, Channel-Tabs) wurde vom Compare-Renderpfad nie gelesen
  (#1301-Grundbefund) — die neue Seite bildet diese Funktion bewusst nicht nach. Nutzer, die diese
  UI vorher bedient haben, verloren dadurch de facto keine Funktion (die Einstellung hatte nie
  Mail-Wirkung).
- **Generische Shell-Extraktion (Trip + Compare) ist NICHT Teil dieser Scheibe.** `CompareNewEditor`
  und `TripNewEditor` bleiben zwei eigenständige Komponenten mit strukturell ähnlichem, aber nicht
  geteiltem Rahmen-Code (Tab-Bar-Rendering, Lock-Flash, Fortschrittsbalken-Markup). Ein Folge-Refactor
  könnte diesen Rahmen extrahieren — Radar-Kandidat, hier bewusst nicht vorgezogen, um F2a nicht mit
  einer zweiten, unabhängigen Architekturentscheidung zu vermengen.
- **`Step2Orte.svelte` bleibt unter `steps/`**, kein Umzug nach `compare-new/` in dieser Scheibe (laut
  Design-Entscheidung 5 des Kontexts ggf. Umzug in F2b, nicht hier).
- **Mobile-Parität ist Pflicht**, aber die konkreten `cm-mobile-*`/`top-app-bar-*`-Anker müssen 1:1 aus
  den bestehenden E2E-Verträgen (`fidelity-s8d`, `issue-682`) erhalten bleiben — kein neues
  Mobile-Konzept, sondern Wiederverwendung des Trip-Vorbild-Musters (`.tn-desktop`/`.tn-mobile`,
  CSS-only @899px).

## Test Plan

1. **Kern-Unit (netzfrei, node:test):** `compareNewLogic.test.ts` — alle Kombinationen der
   Freischalt-Kette (leerer Start, Name ohne Orte, ≥2 Orte ohne Metriken-Besuch, vollständige Kette,
   `canActivate` false/true), analog `tripNewLogic.test.ts`.
2. **Struktur-Test (Anti-Hand-Kopie):** `CompareHourlyLayoutControls.struct.test.ts` prüft per
   AST/Text-Muster, dass die Komponente über `{#each ALL_HOURLY_METRICS as metric}` iteriert statt die
   Metrik-Liste hart zu kopieren — verhindert stille Divergenz zwischen Hub- und Anlege-Nutzung
   (Vorbild-Prinzip: Anti-Hand-Kopie wie bei den C2-Kern-Tests).
3. **E2E-Regression gegen die neue Seite:** alle in der Scope-Tabelle als „unverändert erwartet grün"
   gelisteten Dateien laufen ohne Codeänderung gegen `CompareNewEditor`, weil die tragenden
   Testid-Familien (`compare-editor-name/-activate/-continue-*/-profile-*`, `compare-step2-*`,
   `corridor-editor-vergleich`, `compare-step5-*`, `cm-mobile-*`/`top-app-bar-*`) erhalten bleiben.
4. **E2E gezielt neu/umgeschrieben:** `compare-editor-slice4.spec.ts`, `layout-tab-vergleich.spec.ts`,
   `sortable-list-shared.spec.ts` (Compare-Anteil) — Attrappen-Blöcke raus, neuer Layout-Tab-Inhalt
   (`compare-layout-hourly-*`) geprüft.
5. **Staging-Verifikation (echter Klickpfad, PFLICHT vor „E2E bestanden"):** Name eingeben → 2 Orte
   wählen (Bibliothek + Smart-Import-Pfad) → Wetter-Metriken-Tab öffnen und mind. eine Metrik
   umschalten → Wertebereiche-Tab öffnen → Layout-Tab öffnen und Stundenverlauf-Toggle setzen →
   Alarme-Tab öffnen → Versand-Tab öffnen → „Briefing aktivieren" klicken → echter
   `POST /api/compare/presets` (Netzwerk-Log geprüft, kein Mock) → Redirect auf `/compare/{id}` (Hub) →
   der neu erzeugte Vergleich zeigt die im Anlege-Flow gesetzten Werte (Metriken, Stundenverlauf,
   Wertebereiche) im Hub korrekt an — Nachweis, dass kein Wert auf dem Weg verloren geht.
6. **Mandantentrennung:** wie bei jedem datenbewegenden Endpoint mit zwei verschiedenen Testnutzern
   verifizieren, dass Nutzer A keinen Vergleich von Nutzer B anlegt/sieht (CLAUDE.md-Pflicht).

## Estimated Scope

- **LoC:** grobe Schätzung **~850-950 geänderte/neue Zeilen**: `CompareNewEditor.svelte`
  (~450-550 Z., analog `TripNewEditor.svelte`-Größenordnung minus Etappen/GPX-Komplexität, plus
  7 statt 6 Tabs), `compareNewLogic.ts` (~70 Z.), `compareNewLogic.test.ts` (~90 Z.),
  `CompareHourlyLayoutControls.svelte` (~40 Z., reine Extraktion aus `CompareTabs.svelte`) +
  Struktur-Test (~30 Z.), `+page.svelte`-Umbau (~15 Z.), `CompareTabs.svelte`-Anpassung (~-25/+3 Z.),
  E2E-Umbau der drei Layout-Attrappen-Dateien (~150-200 Z. Diff). Das **250-LoC-Workflow-Limit wird
  damit deutlich überschritten** — Ursache ist strukturell (neue Editor-Shell + Logik + Tests +
  E2E-Umbau lassen sich nicht sinnvoll unter 250 LoC splitten, ohne einen halbfertigen Editor zu
  committen). **Empfehlung: `loc_limit_override 900`** vor Implementierungsstart einholen (PO-Freigabe
  laut Regel-Budget nötig).
- **Files:** 4 neu (Editor, Logik, 2 Tests), 3 geändert (Route, `CompareTabs.svelte`,
  `CompareHourlyLayoutControls.svelte` als 4. neue Datei bereits gezählt), ~3 E2E-Dateien mit
  substanziellem Umbau (slice4/layout-tab-vergleich/sortable-list-shared, Compare-Anteil), ~10 weitere
  E2E-Dateien als reine Regression ohne Codeänderung.
- **Effort:** hoch — neue Fachlogik (Freischalt-Kette + Tab-Shell), aber überwiegend mechanisches
  Zusammensetzen bereits vorhandener, anlage-tauglicher Organismen (kein neuer Organism-Code).

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet `/compare/new`, When die Seite lädt, Then erscheint der
Progressive-Tab-Editor `CompareNewEditor` (Hero „Neuen Vergleich anlegen" + Fortschrittsbalken + 7
Tabs) und **nicht** mehr `CompareEditor mode="create"` — kein Stepper-Wizard-Layout.

**AC-2:** Given der Erstellen-Modus ohne jede Eingabe, When die Seite lädt, Then ist nur der Tab
„Vergleich" klickbar, alle übrigen 6 Tabs sind gesperrt (⊘ + Tooltip mit Sperrgrund); ein Klick auf
einen gesperrten Tab wechselt NICHT den aktiven Tab, sondern zeigt Flash/Tooltip — exakt nach der
Freischalt-Tabelle dieser Spec.

**AC-3:** Given der Tab „Vergleich", When der Nutzer einen Namen einträgt, Then schaltet der
Orte-Tab frei und die Hero-Überschrift zeigt den eingetragenen Namen; Region und Profil sind optional
und beeinflussen die Freischaltung nicht.

**AC-4:** Given der Orte-Tab, When der Nutzer mindestens 2 Orte auswählt (Bibliothek oder
Smart-Import, `Step2Orte` unverändert wiederverwendet), Then schaltet der Wetter-Metriken-Tab frei;
bei weniger als 2 Orten bleibt er gesperrt.

**AC-5:** Given der neu freigeschaltete Wetter-Metriken-Tab, When der Nutzer ihn öffnet, Then rendert
`WeatherMetricsTab context="vergleich"` mit demselben Verhalten wie im Hub (Grundauswahl der
Wetter-Metriken je Ort) — diese Grundauswahl existierte im alten Create-Modus überhaupt nicht (C1-Lücke,
wird hier geschlossen); der Besuch schaltet den Wertebereiche-Tab frei.

**AC-6:** Given der Wertebereiche-Tab, When der Nutzer ihn öffnet, Then rendert derselbe
`CorridorEditor context="vergleich"` (bzw. `CorridorEditorMobile` im mobilen Viewport) wie im Hub, mit
`isFreshCompareCreate`-Profil-Prefill (keine vorherigen Korridore); der Besuch schaltet den Layout-Tab
frei.

**AC-7:** Given der Layout-Tab, When der Nutzer ihn öffnet, Then zeigt er **ausschließlich** die
Stundenverlauf-Steuerung (Toggle + Metrik-Auswahl) über die neu extrahierte, geteilte Komponente
`CompareHourlyLayoutControls` — keine Channel-Tabs, kein Top-N-Ranking, kein SMS-Budget-DnD (alte
Attrappe entfällt ersatzlos); der Besuch schaltet den Alarme-Tab frei.

**AC-8:** Given die Tabs Alarme und Versand, When sie geöffnet werden, Then rendern sie dieselben
Komponenten wie der Hub (`AlarmeTab context="vergleich"`, `VersandTab context="vergleich"` mit
Aktivierungs-Banner-Snippet); der Versand-Tab-Besuch macht „Briefing aktivieren" aktiv (vorher
deaktiviert mit Hinweis).

**AC-9:** Given der vollständige Anlege-Flow (Versand-Tab besucht), When der Nutzer „Briefing
aktivieren" klickt, Then erfolgt genau EIN `POST /api/compare/presets` mit Name, Orten, Wetter-Metrik-
Grundauswahl, Wertebereichen, Stundenverlauf-Konfiguration, Alarm- und Versand-Einstellungen, gefolgt
von `goto('/compare/{id}')` (Redirect auf den Hub); vorher ist der Aktivieren-Button deaktiviert.

**AC-10:** Given `CompareEditor.svelte` (Alt-Editor), When der neue Flow live ist, Then bleibt die
Komponente inklusive `compareEditorLogic.ts` und der Wiederverwendung von `Step2Orte.svelte`
unverändert und ungelöscht im Repo — kein Import mehr von `/compare/new` aus, aber vollständig
vorhanden als Rollback-Punkt (Löschung ist F2b, nicht F2a).

**AC-11:** Given die 3 betroffenen Layout-E2E-Dateien (`compare-editor-slice4.spec.ts`,
`layout-tab-vergleich.spec.ts`, `sortable-list-shared.spec.ts`), When sie nach der Migration gegen
Staging laufen, Then prüfen sie ausschließlich noch existierende Funktionen (Stundenverlauf-Toggle
über `compare-layout-hourly-*`-Testids bzw. den unveränderten Trip-DnD-Pfad) — kein Testfall wartet
mehr auf channel-tabs/Top-N/SMS-Budget-DnD im Compare-Kontext.

**AC-12:** Given die übrigen `/compare/new`-E2E-Dateien mit erhaltenen Testids (slice1, slice3,
1080, 951 Compare-Teil, s8d, 682, 718 AC-2, flow-navigation Create-ACs, versand-tab AC-6), When sie
nach der Migration ohne Codeänderung gegen Staging laufen, Then sind sie unverändert grün — kein
Regressionsverlust durch den Editor-Austausch.

**Nachtrag nach Implementierung (Developer-Agent-Befund, lokaler Preview-Lauf):** Zwei Fälle standen
fälschlich in der „ohne Codeänderung grün"-Liste von AC-12 — die von AC-4/AC-5 **genehmigte**
Freischalt-Kette (neuer Wetter-Metriken-Tab zwischen Orte und Wertebereiche, 7 statt 6 Tabs) erzwingt
ihre Anpassung; die fachliche Aussage der Tests bleibt unverändert erhalten:

1. `compare-editor-slice1.spec.ts` **AC-3** prüfte fix „6 Fortschritts-Segmente" und „N / 6". Der neue
   `CompareNewEditor` hat gemäß der Freischalt-Tabelle **7 Tabs** (`compareNewLogic.ts` →
   `CompareNewTabId`: vergleich · orte · metriken · idealwerte · layout · alarme · versand); der
   Fortschrittsbalken iteriert die 7 Tab-Definitionen. Der Test wurde auf **7 Segmente / „N / 7"**
   angepasst (Zahl aus `compareNewLogic.ts` abgeleitet, im Test begründet) — Aussage („Fortschritt
   zeigt je Tab ein Segment und steigt mit der ersten Eingabe") unverändert.
2. `compare-editor-slice3.spec.ts` **AC-4/AC-6/AC-7/AC-8/AC-9/AC-10** klickten Orte → Wertebereiche
   direkt. Da Wertebereiche jetzt erst nach Besuch des Wetter-Metriken-Tabs frei ist (AC-4/AC-5), wurde
   der gemeinsame Helper `openIdealwerte()` um einen **echten Klick auf den Metriken-Tab** ergänzt (kein
   `goto`); alle Assertions bleiben unverändert.
3. **Continue-CTA-Benennung ehrlich (Adversary F002):** Der Weiter-Knopf auf dem Orte-Tab trug zunächst
   `compare-editor-continue-idealwerte`, navigierte aber zum neuen Metriken-Tab (Etikettenschwindel). Die
   Continue-Kette wurde durchgängig **ziel-benannt**: Orte-Fuß → `compare-editor-continue-metriken`,
   Metriken-Fuß → `compare-editor-continue-idealwerte`, danach `-layout`/`-alarme`/`-versand`. Betroffene
   E2E-Referenzen nachgezogen: `issue-718-idealwert-validation.spec.ts` (Orte-Gate-Knopf →
   `-continue-metriken`), `compare-editor-fidelity-s8d.spec.ts` AC-16/AC-17 (Knopf-Testid + Ziel-Tab +
   eingeschobener Metriken-Schritt).
4. **Drei weitere Create-Ketten (Adversary F003)** klickten Orte → Wertebereiche direkt und scheitern an
   der genehmigten Kette; um einen echten Metriken-Tab-Klick ergänzt (Assertions unverändert):
   `compare-flow-navigation.spec.ts` (`reachLayoutTabWithTwoLocations` + Aktivieren-Flow),
   `versand-tab-vergleich.spec.ts` (AC-6 Create-Teil), `compare-editor-fidelity-s8d.spec.ts` (Create-Kette).
5. **Weitere Attrappen- und Mobil-Ketten-Folgen (im lokalen Regressionslauf aufgedeckt):**
   `compare-flow-navigation.spec.ts` AC-8/AC-9/AC-10 prüften den entfernten LayoutTab-/channel_layouts-
   Organism (`layout-tab`-Organism, `compare-step4-layout-preview`, `channel-tab-telegram`,
   Spalten-Rechnung) — analog AC-11 auf den neuen Layout-Tab-Inhalt umgeschrieben (AC-8:
   `compare-layout-hourly-*` sichtbar; AC-9: Attrappe abwesend; AC-10 ersatzlos entfallen, da
   Telegram-Spalten-Rechnung Teil der entfernten Attrappe war). `compare-editor-fidelity-s8d.spec.ts`
   Mobil-CTA- und App-Leisten-Tests (S8d AC-8..AC-12, AC-15) um den Wetter-Metriken-Schritt bzw. den
   fünften CTA-Klick der 7-Tab-Kette ergänzt; Aussagen (CTA-Label je Tab, „…"→„Aktivieren"-Bereitschaft,
   Titelwechsel, kein Boden-CTA auf Versand) unverändert.
6. **F001-Härtung (Adversary):** `compare-editor-slice4.spec.ts` AC-9 trifft im Flow echte Auswahlen
   (Wetter-Metrik umschalten, Wertebereiche via Profil-Prefill, Stundenverlauf-Metrik setzen) und
   prüft Payload-Vollständigkeit (`display_config.active_metrics` + `corridors` +
   `display_config.hourly_metrics`) plus GET-Roundtrip auf das gespeicherte Preset (Hub-Wahrheit).

**Nicht F2a (weiterhin offen):** `issue-1080-compare-new-url.spec.ts` AC-1/AC-4 + AC-3 (Smart-Import-
Koordinaten) scheitern **auch gegen den Alt-Editor** (Preview-Stack/Resolver-Umgebung, bewiesen per
Rück-Swap) und der Hub-Header-Kebab-Fall (`compare-flow-navigation.spec.ts` AC-5, Adversary F004 LOW)
ist ein vorbestehender Befund — beide sind kein Regressionsverlust dieser Scheibe (Sammel-Eintrag #1199).

Kein weiterer Regressionsverlust: die übrigen in AC-12 genannten Dateien laufen unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0029 (neu, `docs/adr/0029-anlege-shell-je-domaene-eigen.md` — Datei wird bei
  Implementierung angelegt, diese Spec reserviert nur die Nummer; nächste freie Nummer nach ADR-0028).
- **Rationale:** `CompareNewEditor` wird als eigenständige, domänen-eigene Anlege-Shell gebaut statt
  als Wiederverwendung/Erweiterung einer generischen Editor-Rahmen-Komponente — obwohl mit
  `TripNewEditor` (#622) ein Trip-Pendant existiert und die Trip/Compare-Teilungs-Invariante
  (`CLAUDE.md`) neue Compare-Komponenten mit Trip-Pendant standardmäßig als Verstoß wertet. Die
  Ausnahme ist hier dokumentiert und begründet: (1) das Trip-Vorbild selbst etabliert dieses Muster —
  `TripNewEditor` ist bereits eine eigene Shell, keine Erweiterung eines noch generischeren
  Editor-Rahmens; (2) die Tab-Inhalte unterscheiden sich strukturell stark (Etappen/GPX-Verwaltung mit
  Auto-Datum vs. Orte-Auswahl mit Bibliothek/Smart-Import) — eine vorzeitige Shell-Abstraktion würde
  Kopplung zwischen zwei noch in Bewegung befindlichen Bereichen einführen (Compare steht laut Epic
  #1273/#1301 mitten in einer Konvergenz-Serie); (3) **geteilt bleibt, was tatsächlich identisch ist:**
  die vier Organismen (`WeatherMetricsTab`, `CorridorEditor`, `AlarmeTab`, `VersandTab`), der
  wiederverwendete `Step2Orte`, das Logik-*Muster* (reine Freischalt-Funktionen à la `tripNewLogic.ts`)
  und ab dieser Scheibe zusätzlich `CompareHourlyLayoutControls` (vorher dupliziert, jetzt extrahiert).
  Eine generische Rahmen-Extraktion bleibt ein möglicher **späterer** Schritt (Radar-Kandidat), sobald
  beide Domänen stabiler sind — hier bewusst nicht vorgezogen, um F2a nicht mit einer zweiten,
  unabhängigen Architekturentscheidung zu vermengen.

## Changelog

- 2026-07-19: Initial spec created
