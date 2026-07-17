# Context: refactor-1286-shared-versandzeit

## Request Summary
Das Versandzeit-UI (Morgen-/Abend-Briefing-Uhrzeit) existiert in Trip- und
Vergleichs-Editor als **zwei separate Svelte-Komponenten** statt einer geteilten.
Ziel: auf **eine** geteilte Komponente zusammenführen (Teilungs-Invariante,
CLAUDE.md „Trip/Ortsvergleich-Code-Teilung", Anti-Pattern #1170).
Reine Wartbarkeit — kein nutzersichtbarer Bug (#1280 ist behoben).

## Kern-Befund (verändert die Aufgabe gegenüber der Issue-Beschreibung)

Die geteilte Zielkomponente **existiert schon und ist teilweise ausgerollt**:

- `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` (242 Z.)
  ist bereits die kontextfähige Komponente mit `context: 'route' | 'vergleich'`,
  Morgen/Abend-Karten, `step={3600}`-Zeitfeldern, optionaler Trend-Karte (nur
  route) und Kanal-Empty-State. **Controlled Component** (Callback-Props, kein
  `bind`). Spec: `docs/specs/modules/versand_tab_route.md`.
- Sie wird schon genutzt vom **Compare-Editor** (`VersandTab context="vergleich"`)
  UND vom **Trip-Detail-Tab „Briefings"** (`BriefingScheduleTab.svelte` →
  `VersandTab context="route"`, Issue #1232 Scheibe 1).

Die im Issue genannte Duplikation steckt also **nicht** im Detail-Tab „Briefings"
(der ist schon migriert), sondern in den übrigen `EditReportConfigSection`-Pfaden,
die den Schedule-Block noch selbst rendern.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (542 Z.) | **Alt-Duplikat.** Rendert den Schedule-Block selbst (Z. 232–344): Morgen/Abend-Karten mit eigenem State (`bind:value`), Quick-Pick-Chips, Trend inline pro Karte. `step={3600}` seit #1280. `showSchedule`-Prop schaltet den Block. |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` (242 Z.) | **Ziel-Komponente** (geteilt, controlled). |
| `frontend/src/lib/components/shared/VersandTab.svelte` | Organismus, der VTSchedulePlan für route & vergleich verdrahtet; hält morning/evening-State + Read-Modify-Write. |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Detail-Tab „Briefings" — nutzt schon `VersandTab context="route"`. Referenz, wie route-Verdrahtung aussieht. |
| `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte:40` | Nutzt `EditReportConfigSection` mit Default-`showSchedule=true` → Duplikat-Zeitfeld. **Live-Status prüfen (Analyse).** |
| `frontend/src/lib/components/edit/TripEditView.svelte:203` | Wie oben. **Live-Status prüfen.** |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:765,990` | Anlege-Wizard, `mode="create"`, Default-Schedule → Duplikat-Zeitfeld. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:795` | Nutzt `EditReportConfigSection` mit `showSchedule={false}` → **kein** Zeitfeld, nicht betroffen. |
| `docs/specs/modules/versand_tab_route.md` / `versand_tab_vergleich.md` | Bestehende Specs der geteilten Komponente (AC-3/AC-4, KL-1/KL-2). |
| `docs/specs/modules/fix_1280_versandzeit_stunden_raster.md` | Kontext des Auslöse-Bugs (Stunden-Raster, doppelter Patch-Pfad). |

## Existing Patterns
- **Geteilter Organismus mit `context`-Diskriminierung** (`route`/`vergleich`) ist
  das etablierte Muster (VersandTab, VTSchedulePlan, AlarmeTab). Genau das soll
  auch für die verbliebenen Trip-Pfade gelten.
- VTSchedulePlan ist **controlled** (Parent hält State, Callbacks schreiben zurück);
  EditReportConfigSection ist **stateful** (`bind:value`, eigener Read-Modify-Write
  über das ganze `reportConfig`). Ein Merge muss diese State-Ownership überbrücken.
- Read-Modify-Write über den Original-Blob (change_threshold_* etc. erhalten) —
  Pflicht, darf beim Refactor nicht verloren gehen.

## Dependencies
- Upstream: `ReportConfig`-Typ, `toHHMMSS`, `Checkbox`, atoms `Card`/`Eyebrow`,
  `syncSendFlags`/Kanal-Gating.
- Downstream (was die geänderten Trip-Pfade nutzt): Anlege-Wizard-Flow, Trip-Edit-View,
  BriefingsTab. Autosave/Capture-Phase-Listener (#1269) hängen an der Mount-Kanonisierung.

## Design-/UX-Divergenzen, die beim Merge entschieden werden müssen (→ Analyse/Spec, PO)
1. **Quick-Pick-Chips** („Morgens 07:00" / „Abends 18:00") existieren NUR in
   EditReportConfigSection, nicht in VTSchedulePlan. Merge = Chips fallen im Trip
   weg ODER wandern in die geteilte Komponente (dann auch im Compare sichtbar).
2. **Karten-Styling** unterscheidet sich (Tailwind `Card.Root` vs. atoms `Card` mit
   `vt-*`-Klassen). Nach Merge sieht der betroffene Trip-Pfad anders aus → Fresh-Eyes
   + PO-Freigabe der sichtbaren Änderung.
3. **Trend-Darstellung**: EditReportConfigSection zeigt Trend inline je Report-Karte;
   VTSchedulePlan zeigt eine separate dritte „Mehrtages-Trend"-Karte (nur route).

## Risks & Considerations
- **Welche EditReportConfigSection-Pfade sind live geroutet?** Es gibt mehrere
  Editor-Varianten (TripEditView, BriefingsTab, WeatherMetricsTab, BriefingScheduleTab,
  TripNewEditor). Analyse muss klären, welche der Schedule-tragenden Pfade der Nutzer
  tatsächlich sieht und welche Legacy/tot sind — sonst refactoren wir toten Code.
- **State-Ownership-Bruch**: controlled vs. stateful. Falsch verdrahtet → Autosave-
  oder Read-Modify-Write-Regression (Datenverlust-Risiko bei reportConfig-Feldern).
- **`step={3600}`/Stunden-Heilung (#1280)** muss im geteilten Pfad erhalten bleiben —
  genau die doppelte Pflege war der Auslöser des Issues.
- Keine aktiven Prod-User (Memory) — Blast Radius gedämpft, aber Trip-Editor ist
  zentrale UI; Regression wäre sichtbar.
- Scope-Disziplin: NUR das Versandzeit-/Schedule-UI teilen, nicht die restlichen
  Blöcke von EditReportConfigSection (Kanäle, Mail-Inhalt, Metriken) mit anfassen.

## Analysis (2 Explore-Agenten, 2026-07-17)

### Type
Feature (Wartbarkeits-Refactor). Kein Bug.

### Live-Routing — der Scope ist viel kleiner als der Issue vermuten lässt
| Komponente (nutzt EditReportConfigSection mit Zeitplan) | Live? | Beleg |
|---|---|---|
| **TripNewEditor** (Anlege-Wizard, `/trips/new`, Z.765 Desktop + Z.990 Mobile) | **LIVE — einziger erreichbarer Duplikat-Pfad** | `routes/trips/new/+page.svelte`; Tab „Briefing-Zeitplan" |
| BriefingsTab (Z.40) | TOTER Code | in `TripTabs.svelte:14` importiert, nie gerendert |
| TripEditView (Z.203) | TOTER Code | `/trips/[id]/edit` → 307-Redirect, nie importiert |
| WeatherMetricsTab (Z.795) | betroffen? nein | `showSchedule={false}` — kein Zeitfeld |

Der Trip-Detail-Tab „Versand" nutzt **bereits** den geteilten `VersandTab context="route"` → `VTSchedulePlan` (`BriefingScheduleTab.svelte`). Der Anlege-Wizard ist der **einzige** verbliebene Ort mit eigenem Zeitplan-Markup.

### Wichtig: Der Wizard-Schritt zeigt die VOLLE EditReportConfigSection
Der Tab „Briefing-Zeitplan" rendert Zeitplan **+ Kanäle + Mail-Inhalt** (keine `showX`-Props gesetzt → alle Default true). Eine volle Umstellung auf `VersandTab` scheidet aus: VersandTab bündelt stattdessen Laufzeit + Alert-Zustellung (kein Mail-Inhalt). → Nur der **Zeitplan-Teil** wird geteilt, Kanäle + Mail-Inhalt bleiben in EditReportConfigSection (damit bleibt auch das `weatherChannels`-Kanal-Gating unangetastet).

### Technical Approach (empfohlen — minimal-invasiv, keine State-Kollision)
Den Inline-Zeitplan-**Markup**-Block in `EditReportConfigSection.svelte` (Z. 232–344) durch die geteilte `<VTSchedulePlan context="route" .../>` ersetzen, verdrahtet an die **bereits vorhandenen** internen `$state`-Felder (`morning_enabled`, `morning_time`, `evening_*`, `multi_day_trend_*`) via Callbacks — exakt das Muster, das `VersandTab`/`BriefingScheduleTab` schon nutzen.
- State-Ownership + Read-Modify-Write von EditReportConfigSection bleiben **unverändert** → kein Doppel-Schreiber, kein Kollisionsrisiko, `change_threshold_*` erhalten.
- `hasActiveChannel` muss EditReportConfigSection aus seinen Kanal-States ableiten und an VTSchedulePlan geben.
- Ergebnis: `VTSchedulePlan` ist die **einzige** Zeitplan-UI-Quelle. Künftige Änderungen (wie #1280 `step={3600}`) passieren nur noch dort. Invariante erfüllt.

### Sichtbare Folge (Fresh-Eyes + PO)
Der Wizard-Zeitplan sieht danach aus wie der Trip-Detail-Versand-Tab: atoms-`Card`-Styling, separate „Mehrtages-Trend"-Karte statt Trend inline pro Report. Das ist ein **Konsistenz-Gewinn** (beide Editoren gleich), aber eine sichtbare Umgestaltung.

### Entscheidung (PO, 2026-07-17)
- **Quick-Pick-Chips** („Morgens 07:00"/„Abends 18:00"): **in die geteilte Komponente `VTSchedulePlan` heben** → einheitlich in Anlege-Assistent, Trip-Detail UND Ortsvergleich. Chip-Klick nutzt dieselben `onMorningTime`/`onEveningTime`-Callbacks wie die Zeit-Eingabe. Erweitert Scope leicht (VTSchedulePlan bekommt die Chips + Testids `report-*-quickpick-*`).

### Scope Assessment
- Dateien: `EditReportConfigSection.svelte` (Block ersetzen), evtl. `VTSchedulePlan.svelte` (nur falls Chips reinkommen), + Tests. Reines Frontend, kein Backend.
- LoC: ~ −110 (Inline-Block raus) / +30–60 (Einbindung + Callbacks). Netto klein.
- Risk: MEDIUM (State-Verdrahtung heikel; Read-Modify-Write darf nicht brechen).

### Nebenbefund (nicht Teil dieses Scopes)
Toter Code `BriefingsTab.svelte` + `TripEditView.svelte` (+ Route `/trips/[id]/edit`) — separates Cleanup, → #1199 / eigenes Issue. Nicht mitfixen (Scope-Disziplin).
