# Context: feat-1256-s8-mobile — Scheibe 8 von #1256 (Mobile-Vervollständigung)

## Request Summary

Scheibe 8 der Programm-Spec `docs/specs/modules/issue_1256_compare_ui_rewire.md`
(v1.3, PO-go pauschal 2026-07-13): Mobile-Vervollständigung des Orts-Vergleichs —
AC-21 (Liste dense+Chevron), AC-22 (Hub-Übersicht 2×2 mit 4 Stats), AC-23
(MCompareActionSheet → Lifecycle-Aktionsliste), AC-24 (Editor Lock-Toast +
floating CTA). Spiegelt die geteilten Organismen aus S4/S6/S7 auf Mobile.

## Soll-Quellen (Handoff-4, entpackt im Session-Scratchpad `handoff4/`)

| Quelle | Relevanz |
|---|---|
| `gregor-zwanzig-mobile/project/screen-compare-list-mobile.jsx` (Z. 48-57) | AC-21: `CompareTile dense trailing={Chevron}` — Chevron STATT Kebab; darüber Inline-Stats Aktiv/Pausiert/Drafts |
| `gregor-zwanzig-mobile/project/screen-compare-detail-mobile.jsx` | AC-22/23: Mobile-Hub hat die GLEICHEN 6 Tabs (MTab, scrollbar) wie Desktop; Übersicht = Status-Pill+Region → 2×2-Grid mit GENAU 4 Stats (Status / Nächster Versand / Zuletzt raus / Kanäle mit NAMEN) → SummaryRows mit `go(tab)`-Sprung → Vorschau-Hinweis-Karte. `CDM_lifecycleActions`: draft = nur „Entwurf löschen"; sonst Toggle/Archivieren/Löschen |
| `current/jsx/screen-compare-editor-mobile.jsx` | AC-24: Lock-Toast + floating CTA (Soll-Fidelity) |

## Ist-Befunde (Related Files)

| File | Relevanz / Befund |
|---|---|
| `frontend/src/routes/compare/+page.svelte:89-97` | Mobile-Liste rendert `CompareTile dense={true}` — aber MIT `onAction` (Kebab) |
| `frontend/src/lib/components/compare/CompareTile.svelte:155-163` | **AC-21-Lücke:** Kebab wird UNCONDITIONAL gerendert, keine `trailing`/Chevron-Prop. Spec-Annahme „bereits vorhanden" stimmt NICHT — S7-Fix f610e35a brauchte deshalb `:visible`-Selektoren (Desktop+Mobile-Kebab, gleiches aria-label) |
| `frontend/src/routes/compare/[id]/+page.svelte:199-273` | **AC-22-Lücke:** Mobile-Hub = Bespoke-Block OHNE Tabs (#493): TopBar + 5 (nicht 4) Stat-Cards (Status/Nächster/**Briefings**/Zuletzt/Kanäle `col-span-2` mit **Anzahl** via `channelCountLabel` statt Namen) + flache Standort-Liste. Kein Zugriff auf geteilte Organismen |
| `frontend/src/lib/components/compare/CompareTabs.svelte:615-664` | Desktop-Monitoring-Streifen: 5 Stats als flex-wrap; Tabs enthalten bereits `CorridorEditor context="vergleich"` (Z. 776) + `VersandTab context="vergleich"` (Z. 807) + hubPutQueue-Serialisierung (S7) |
| `frontend/src/lib/components/mobile/MCompareActionSheet.svelte:27` | **AC-23-Lücke:** nutzt `compareActions(status)` (voller Umfang), soll `compareLifecycleActions()` (subscriptionHelpers.ts:245, seit S3) |
| `frontend/src/lib/components/compare/CompareEditor.svelte:416-432, 1117, 1269-1277` | **AC-24 im Ist erfüllt:** `showLockToast` (2s Timer) + sticky Mobile-CTA (`data-testid="cm-mobile-cta"`); nur Live-E2E-Nachweis nötig. Spec-Zeilenangabe 372-390 ist gedriftet → real 416-432 |
| `frontend/src/lib/components/compare/__tests__/issue_493_compare_mobile.test.ts:63-69` | Alt-Assertion „nutzt compareActions()" — wird durch AC-23 ersetzt (Datei ist issue-nummeriert, Bestandsschutz #1196; Assertion-Ersatz laut Spec explizit erlaubt) |

## Existing Patterns

- **TripTabs.svelte:198-202 (Vorbild, Trip/Compare-Teilungs-Invariante):** EIN
  Tab-System; im Tab-Inhalt schaltet `{#if isMobileViewport}` auf
  `CorridorEditorMobile` um. KEIN doppelter DOM-Baum, keine doppelten testids.
- `CorridorEditorMobile.svelte` existiert (`shared/corridor-editor/`), genutzt in
  `CompareEditor.svelte:1254` (context="vergleich") und `TripTabs.svelte:199`
  (context="route").
- **`VersandTab.svelte` hat KEINE `dense`-Prop** (Spec-Scheibentext nennt sie) —
  Ist-Zustand: ein Markup für beide Viewports.
- Desktop/Mobile-Umschaltung Seitenebene: `hidden desktop:block` /
  `desktop:hidden` (Breakpoint 900px, AC-21/22-Viewport).
- hubPutQueue (`compareHubWizardBridge.ts`, S7): JEDER Hub-Preset-PUT muss
  seriell durch die Queue (F004-Klasse) — gilt automatisch, wenn Mobile dieselben
  CompareTabs-Pfade nutzt statt eigener PUT-Pfade.

## Dependencies

- Upstream: `subscriptionHelpers.ts` (`compareLifecycleActions`, `STATUS_MAP`,
  Label-Helfer), `compareHubWizardBridge.ts` (hubPutQueue), geteilte Organismen
  `CorridorEditor(Mobile)`, `VersandTab`, `LayoutTab` (S4), `Sheet`/`MTab`-Mobile-Atome.
- Downstream: Playwright-Suiten `playwright.1256-s2` (18 Tests, davon Mobile-
  Klickpfade), `.1256-s6` (7), `.1256-s7` (8, `:visible`-Selektoren wegen
  Doppel-Kebab!), `issue_493_compare_mobile.test.ts`, testid-Bestand C6
  (`compare-detail-stat-briefings` existiert heute DOPPELT: CompareTabs:642 +
  Mobile-Block:252).

## Existing Specs

- `docs/specs/modules/issue_1256_compare_ui_rewire.md` — Programm-Spec v1.3,
  Scheibe 8 = Zeilen 487-505, ACs 21-24 = Zeilen 901-933. ACs sind PO-freigegeben
  (pauschales go 2026-07-13).
- `docs/specs/modules/issue_493_compare_mobile.md` §4 — Alt-Spec des Bespoke-
  Mobile-Pfads (wird durch S8 teilweise überholt).

## Risks & Considerations

- **Kern-Architekturentscheidung (Analyse):** AC-22 spricht vom „Übersicht-Tab"
  des mobilen Hubs — im Ist hat Mobile KEINE Tabs. Soll-JSX verlangt dieselben
  6 Tabs. Konsequenz der Scheibenbeschreibung („über dieselben geteilten
  Organismen statt eines eigenen Mobile-Bespoke-Pfads"): Bespoke-Block
  zurückbauen und CompareTabs auch mobil rendern (TripTabs-Muster
  `isMobileViewport` im Monitoring-Streifen + Idealwerte-Tab), NICHT den
  Bespoke-Block ausbauen (wäre Verstoß gegen Teilungs-Invariante).
- **Doppelte testids / `:visible`-Falle:** Wenn CompareTabs mobil UND desktop
  gerendert würde (zwei DOM-Bäume), verdoppeln sich alle Hub-testids →
  bestehende Playwright-Suiten brechen. TripTabs-Muster (ein Baum, CSS/JS-
  Viewport-Switch) vermeidet das; zusätzlich würde ein zweiter CompareTabs-
  Mount doppelte Fetches + doppelte hubPutQueue-Instanzen erzeugen (S4-F001-
  Lifecycle-Klasse!).
- **AC-21 ist KEIN bloßer Regressionsnachweis** (Spec-Annahme falsch): Chevron-
  trailing muss in CompareTile ergänzt, Mobile-Kebab entfernt werden. Folge:
  `:visible`-Workarounds in S7-Suite ggf. obsolet, aber nicht brechen lassen.
  Kachel-Aktionen wandern mobil vollständig in Detail-Hub (Chevron = nur
  Navigation) — deckt sich mit Fluss-Prototyp Liste→Detail.
- LoC-Schätzung ~170 hängt an der Wiederverwendung; Bespoke-Block-Rückbau
  zählt negativ. Budget 250, Override nur mit PO-Erlaubnis.
- `compareLifecycleActions()` (S3) vs. Soll `CDM_lifecycleActions` (draft = nur
  Löschen): Deckungsgleichheit in Analyse verifizieren (Draft-Zweig!).
- Workflow läuft im Worktree `intake-1194`; Spec-Gates lösen gegen Hauptrepo
  auf; vor `complete` ff-merge ins Hauptrepo (bekannte Worktree-Lockout-Falle).

## Analysis

### Type
Feature (Scheibe 8 der Programm-Spec #1256, ACs 21-24 bereits PO-freigegeben)

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/CompareTile.svelte` | MODIFY | AC-21: im `dense`-Modus Chevron statt Kebab rendern (Soll: `screen-compare-list-mobile.jsx:48-57`, `trailing`-Chevron). `dense` wird NUR von der mobilen Liste genutzt (einziger Aufrufer `compare/+page.svelte:93`) — isoliert |
| `frontend/src/routes/compare/+page.svelte` | MODIFY | AC-21: `onAction` an der mobilen Kachel entfällt (Chevron = reine Navigation) |
| `frontend/src/lib/components/mobile/MCompareActionSheet.svelte` | MODIFY | AC-23: `compareActions()` → `compareLifecycleActions()`. Hub-`handleAction` (`[id]/+page.svelte:104-119`) behandelt `pause/resume/archive/trash` BEREITS — keine Handler-Änderung |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | AC-22: Bespoke-Mobile-Inhalt (2×2-5-Karten-Grid + Standort-Liste, Z. 240-272) entfällt; stattdessen wird `CompareDetail` EINMAL (außerhalb der CSS-Blöcke) gemountet und versorgt beide Viewports. Mobile-TopBar + Kontext-Unterzeile BLEIBEN (Playwright AC-28 klickt den Back-Pfeil `compare-flow-navigation.spec.ts:360-377`) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | AC-22: `isMobileViewport` (matchMedia 899px, Muster `TripTabs.svelte:117-124`); Monitoring-Streifen mobil = 2×2-Grid mit GENAU 4 Stats (Status/Nächster Versand/Zuletzt raus/Kanäle-NAMEN via vorhandenem `channelsLabel`); Idealwerte-Tab mobil = `CorridorEditorMobile` (Muster `TripTabs.svelte:198-202`); Tab-Leiste bleibt `Segmented` (Trip-Präzedenz: KEIN MTab auf Detail-Tab-Flächen) |
| `frontend/src/lib/components/compare/__tests__/issue_493_compare_mobile.test.ts` | MODIFY | Alt-Assertions auf den Bespoke-Block (`grid-cols-2` :163-171) + loose `compareActions`-Regex (:63-71, matcht substring-mäßig auch `compareLifecycleActions`!) ersetzen — AC-23-Test muss präzise sein |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY (optional) | `channelCountLabel` verliert letzten Nutzer → Totcode-Kandidat (+ `channelCountLabel.test.ts` DELETE) |
| Neue Tests | CREATE | AC-22-DOM-Test (genau 4 Stats mobil), AC-21/24-Playwright (playwright.1256-s8-Suite), AC-23-Unit-Assertion |

### Scope Assessment
- Files: 7-9
- Estimated LoC: ca. +160/−90 (Netto Produktivcode ~+70; Tests ~+120) — Budget 250 realistisch, kein Override geplant
- Risk Level: MEDIUM

### Technical Approach (Empfehlung)

**Ein-Mount-Strategie:** `CompareDetail` wird in `[id]/+page.svelte` genau EINMAL
gerendert (nicht je CSS-Block) — vermeidet Doppel-Fetches, doppelte
hubPutQueue-Instanzen (S4-F001-/S7-Klasse) und doppelte testids. Nur das
Seiten-Chrome (Desktop-Header vs. Mobile-TopBar) bleibt CSS-geswitcht
(`hidden desktop:block` / `desktop:hidden`). Innerhalb von `CompareTabs`
schaltet `isMobileViewport` (a) den Monitoring-Streifen auf das 4-Stat-2×2 und
(b) den Idealwerte-Tab auf `CorridorEditorMobile` — exakt das TripTabs-Muster
(Teilungs-Invariante erfüllt, kein Bespoke-Pfad mehr).

### Dependencies
- `compareLifecycleActions()` (S3) ist deckungsgleich mit Soll-`CDM_lifecycleActions`
  (draft = nur „Entwurf löschen") — `compare_hub_lifecycle_actions.test.ts` bleibt grün.
- `compare-hub-briefing-times.spec.ts` nutzt `:visible.first()` → überlebt Ein-Mount.
- Hub-Kebab-Tests (`:380-461`) nutzen `button[aria-label="Weitere Aktionen"]:visible` —
  Mobile-`⋯`-Button bleibt (öffnet weiterhin das Sheet), Assumption unverändert.
- `isMobileViewport` ist 3× kopiert (TripTabs/CompareEditor/TripNewEditor, kein
  geteilter Helper) — S8 legt KEINEN 4. Klon an, sondern einen kleinen Helper
  (`$lib/utils`), Bestandsstellen bleiben unangetastet (Konsolidierung → #1199).

### Open Questions
- [x] Bespoke ersetzen oder ausbauen? → Ersetzen (Ein-Mount, Scheibentext + Teilungs-Invariante)
- [x] MTab für mobile Tab-Leiste? → Nein, `Segmented` wie TripTabs (Trip-Präzedenz, kein AC verlangt MTab)
- [x] VersandTab `dense`-Prop? → Nicht nötig für ACs; Versand-/Layout-Tab rendern mobil das geteilte Markup unverändert (bewusste Auslassung, kein AC)
- [x] Edit-Stift in Mobile-TopBar? → Bleibt (kein S8-AC; /edit-Ablösung ist S9, GATED)
