---
entity_id: rework_2276_s6d_wertebereiche
type: module
created: 2026-09-22
updated: 2026-09-22
status: draft
version: "1.0"
tags: [compare, wertebereiche, corridor, wertprops, ratsche, refactor]
---

# Wertebereiche/Corridor-Fläche des Ortsvergleichs auf Wertprops (Issue #2276, Scheibe S6d, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Scheibe **S6d** von #2276 (Epic #2345) stellt die beiden geteilten
Corridor-Bausteine `CorridorEditor.svelte` und `CorridorEditorMobile.svelte`
(`context="route"|"vergleich"`) im **Vergleichs-Zweig** vom
Svelte-Context `compare-wizard-state` (`ws`) auf reine **Wertprops +
Änderungs-Rückrufe** um — nach dem in S6b
(`CompareHourlyLayoutControls.svelte`, live seit `8207c157`) und S6c
(`AlarmeTab.svelte`, live seit `c737159e`) erprobten Muster. Der
`getContext`-Aufruf verschwindet aus beiden `shared/`-Dateien und wandert zu
den Elternteilen hoch: eine neue Bündel-Funktion `corridorPropsAus(wiz)`
(`compare/corridorPropsAus.ts`) baut das Prop-Bündel, das alle **drei**
Vergleichs-Mounts identisch einspeisen. Verhalten bleibt unverändert.
Anders als S6b/S6c betrifft dieser Umbau **zwei** 1:1-Duplikat-Dateien
gleichzeitig (Desktop + Mobil, unteilbar) und **einen dritten Baustein**
(`wertebereicheVergleichSpeicherung.ts`), der eine lebendige, mutierbare
Objektreferenz statt reiner Werte braucht (R2) — dafür führt diese Scheibe
den Proxy-Adapter `corridorZustandsBruecke` ein (Muster
`alarmZustandsBruecke`, S6c).

Diese Scheibe ist die **vorletzte**, die `getContext` aus `shared/` abbaut
(S6f folgt mit der Bilanz/Bridge-Rückbau) — der eigentliche Wert liegt nicht
in der Ratschenzahl (der Ertrag ist mit 6 kleiner als bei S6c mit 14),
sondern darin, dass Voraussetzung für S6f (AC-4) geschaffen wird.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`,
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte`,
  `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`,
  `frontend/src/lib/components/compare/corridorPropsAus.ts` (neu),
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`,
  `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`,
  `frontend/src/lib/components/shared/corridor-editor/__tests__/compare_corridor_wertprops.test.ts` (neu),
  `frontend/e2e/compare-wertebereiche-wertprops.spec.ts` (neu),
  `.github/ci_e2e_specs.txt`
- **Identifier:** `CorridorEditor`/`CorridorEditorMobile` (Props: Wertprop-Bündel
  aus vier Feldern `corridors`/`idealRanges`/`activeMetricKeys`/`metricAlertLevels`
  + Rückrufe + unveränderte `trip`/`onTripUpdate`/`saveController`/`preset`/
  `enqueueHubWrite`/`onCompareUpdate`), `corridorPropsAus(wiz)`
  (`compare/corridorPropsAus.ts`, neu), `corridorZustandsBruecke(werte, setzen)`
  (`wertebereicheVergleichSpeicherung.ts`, neu), Mount (B, Mobil)
  `CompareTabs.svelte:1024`, Mount (B, Desktop) `CompareTabs.svelte:1027`,
  Mount (C, Desktop) `CompareNewEditor.svelte:389`, Mount (C, Mobil)
  `CompareNewEditor.svelte:485`, Mount (A, Mobil) `TripTabs.svelte:227`,
  Mount (A, Desktop) `TripTabs.svelte:229`

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`). Kein Go-API- und kein Python-Core-Code in
dieser Scheibe.

## Nicht in dieser Scheibe

- **`corridorEditorState.ts` bleibt unangetastet.** Die Datei ist bereits
  context-frei (nimmt `context` als expliziten Parameter, kein `getContext`)
  — kein Umbau nötig, auch ihr eingefrorener Ratschen-Eintrag
  (`corridorEditorState.ts:297`, `supportsMark`) bleibt auf seiner Zeile
  stehen.
- **Der Timing-/Weichen-Zweig `:240`/`:207` (`maybeSchedule`) wird NICHT
  umgebaut.** Die Verzweigung `if (context === 'vergleich') { … } else { … }`
  bleibt als Herkunfts-Weiche stehen — Begründung in Implementation Details,
  Entscheidung E4. Der naheliegende Callback-Umbau (`onAenderung`/
  `onUngueltig`) wird verworfen.
- **`hubPutQueue` wird nicht angefasst** (R7) — Schutzmechanismus gegen zwei
  PUTs aus demselben stalen `currentPreset`, kein Nebenschauplatz dieser
  Scheibe.
- **Read-Modify-Write und der Voll-Spread-Payload bleiben Pflicht** (R8,
  BUG-DATALOSS-GR221) — der Go-Handler dekodiert weiterhin in das volle
  Modell, ein Minimal-Body ist verboten.
- **Keine zweite Mobil-E2E-Spec auf Fläche C.** Wie bei S6c trägt ein
  Kern-AST-Wächter die Verdrahtungs-Zusicherung für `/compare/new` — die
  Anlege-Seite hat keinen eigenen Speicherweg, eine E2E-Spec hätte dort
  nichts zu behaupten (R1).
- **Kein separater SSR-Test für den Ungültig-Fall der Weiche `:240`/`:207`.**
  Die ursprünglich geplante CREATE-Zeile für einen AC-12-Test in
  `shared/corridor-editor/__tests__/` entfällt — Begründung in Implementation
  Details, Entscheidung E4/E5.
- **`versandVergleichSpeicherung.ts`, `alarme-tab/*`, `weather-metrics-tab/*`,
  `versand-tab/*` werden nicht angefasst** — ihre eingefrorenen
  Ratschen-Einträge dürfen sich nicht verschieben.
- **Kein zweiter Sub-Schnitt nach Feldgruppen.** Die vier Corridor-Felder
  (`corridors`/`idealRanges`/`activeMetricKeys`/`metricAlertLevels`) wandern
  gemeinsam — eine Aufteilung würde die Ratschen-Umstellung mehrfach
  durchlaufen.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | `getContext`/`ws` entfällt (`:57`); Props-Block bekommt die vier Wertprops + zugehörige Rückrufe; `syncToWizard()` schreibt nicht mehr auf `ws`, sondern ruft die Rückrufe auf; `originalLevels`/`originalActiveMetricKeys` lesen die neuen Wertprops statt `ws` (3 FÄLLT-Zweige, siehe Schicksals-Tabelle); `isFreshCompareCreate` liest die Wertprops statt `ws?.isEditMode`/`ws?.corridors` (BLEIBT, Text ändert sich — siehe Design-Entscheidung 3); `wertebereicheVergleichSpeicherungAktiv(...)`/`erstelleWertebereicheVergleichSpeicherung(...)` bekommen `corridorZustandsBruecke(...)` statt `ws` übergeben |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | MODIFY | Identisch, 1:1-Duplikat (unteilbar von der Desktop-Datei) |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | Neue Funktion `corridorZustandsBruecke(werte, setzen)` **unterhalb Zeile 200** (Auflage A2) — ein `Proxy` über einem leeren Objekt, `get` liest bei jedem Zugriff frisch aus `werte()`, `set` reicht an `setzen` weiter, ohne lokal zu speichern; `WertebereicheVergleichSpeicherungOptionen.ws` und `wertebereicheVergleichSpeicherungAktiv`s Optionsfeld `ws` → `zustand` (Auflage A3, **Zeile 200 bleibt erhalten, ihr TEXT ändert sich** von `!!p.ws` zu `!!p.zustand`); `rollbackCorridorSnapshot`/`erstelleWertebereicheVergleichSpeicherung`/`felder()` bleiben mechanisch unverändert (Queue, Diff-Gate, Read-Modify-Write, Rollback) |
| `frontend/src/lib/components/compare/corridorPropsAus.ts` | **CREATE** | Übersetzung Wizard-Zustand → Prop-Bündel (vier Werte + vier Rückrufe) für alle drei Vergleichs-Mounts. Liegt in `compare/`, nicht `shared/` (Auflage A1, Muster `alarmePropsAus.ts`) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Hub-Mounts `:1024` (Mobil) und `:1027` (Desktop) bekommen `{...corridorPropsAus(wizardState)}` zusätzlich zu den unveränderten Props `preset`/`saveController`/`enqueueHubWrite`/`onCompareUpdate` |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Anlege-Mounts `:389` (Desktop) und `:485` (Mobil) bekommen `{...corridorPropsAus(wiz)}` — `wiz` ist an `:65` bereits per `getContext` vorhanden (Auflage A4, zulässig, weil `compare-new/` nicht `shared/` ist) |
| `frontend/src/lib/components/shared/corridor-editor/__tests__/compare_corridor_wertprops.test.ts` | **CREATE** | SSR-Wächter analog `compare_alarme_wertprops.test.ts`: AST-Scan auf `ws`/`getContext`/`CompareWizardState`-Identifier in beiden Corridor-Dateien (AC-1) + Wirkort-Guard über `effekteVon()`/`umgebungFuer()` für den Selbst-Speicher-Effekt an den negativen Orten Trip/Anlegen (AC-2) + AST-Wächter über alle drei Vergleichs-Mounts, dass `corridorPropsAus(wiz)` im Markup-Ausdruck steht und kein Feld fehlt (AC-3). **Kein** Test für den Ungültig-Fall der Weiche `:240`/`:207` — dieser wandert nach E4/E5 vollständig in die E2E-Spec |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | 6 Einträge streichen (3 FÄLLT-Paare), 22 `.svelte`-Überlebende (11 Paare) auf ihre neuen Zeilennummern nachführen und per `BLEIBT_MIT_INHALT` fesseln, `EINGEFROREN_SOLL_ANZAHL` 53 → 47; Kommentarblock um die Corridor-Ausnahme vom Zeilenzahl-Vertrag erweitern (siehe Design-Entscheidung 5). `corridorEditorState.ts:297` und `wertebereicheVergleichSpeicherung.ts:200` bleiben auf ihrer Zeile stehen, unverändert in `EINGEFROREN` |
| `frontend/e2e/compare-wertebereiche-wertprops.spec.ts` | **CREATE** | Verhaltensgleichheit im Browser am Hub, Desktop **und** Mobil (AC-4/AC-5) **plus** die E5-Zusicherung: beidseitig offene Grenze am Trip (Fläche A) → dirty, am Hub (Fläche B) → kein PUT (AC-6/AC-7). Begründung der Bündelung in Design-Entscheidung 4 |
| `.github/ci_e2e_specs.txt` | MODIFY | Neue E2E-Spec `e2e/compare-wertebereiche-wertprops.spec.ts` aufnehmen, `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` mit `npx playwright test --list` nachziehen |

**10 Dateien** (3 CREATE, 6 MODIFY, 1 CI-Positivliste — die ursprünglich
geplante CREATE-Zeile für einen separaten SSR-AC-12-Test entfällt, siehe
Design-Entscheidung 4).

**Zu prüfen, ob eine Saat-Anpassung nötig ist** (Prüfpflicht, nicht
Änderungspflicht, alle fahren einen Corridor-Pfad): die 11 SSR-Modultests
unter `corridor-editor/__tests__/` (Regressionsnetz-Tabelle unten).

## Estimated Scope

- **LoC (produktiv, geschätzt):** ca. **+550 / −180** — der Großteil sind
  die 22 Ratschen-Nachführungen mit Inhalts-Fesselung, der neue AST-Wächter
  und die neue Bündel-Funktion. **Das 800er-Limit ist damit knapp** (aktuell
  Override auf 800 aktiv) — vor `/40` mit `workflow.py status` neu bewerten.
- **Files:** 10 (siehe oben) — die ursprünglich geschätzten 11 reduzieren
  sich um die entfallene AC-12-CREATE-Zeile.
- **Effort:** high.
- **Risk Level: MITTEL–HOCH.** Drei Mounts, zwei 1:1-Duplikate, ein Adapter
  mit Datenverlust-Relevanz (`corridorZustandsBruecke`), 22 gleichzeitig
  nachzuführende Ratschen-Einträge — die größte Einzeländerung an diesem
  Wächter seit S6c (14). Dämpfend: das Muster ist in S6b und S6c zweimal
  gefahren, `corridorEditorState.ts` bleibt unberührt, und `:240`/`:207`
  wird bewusst NICHT umgebaut (kein verhaltenstragender Eingriff auf einem
  ungetesteten Pfad).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alarmePropsAus.ts` (S6c, live `c737159e`) | module | Lebender Präzedenzfall für ein Bündel-Modul in `compare/`, das an drei Mounts identisch eingespeist wird — Formvorlage für `corridorPropsAus.ts` |
| `alarmZustandsBruecke` (S6c, `alarmeVergleichSpeicherung.ts`) | module | Präzedenzfall für den Proxy-Adapter, der eine lebendige Objektreferenz aus reinen Wertprops nachbildet — Vorlage für `corridorZustandsBruecke` |
| `compare_alarme_wertprops.test.ts` | test | Formvorbild für `compare_corridor_wertprops.test.ts`: AST-Scan + `effekteVon()`/`umgebungFuer()`-Wirkort-Guard + Verdrahtungs-Prüfung aller drei Mounts |
| `frontend/src/lib/components/shared/__tests__/svelteInstanzPruefstand.ts` | Prüfstand | `umgebungFuer()`/`effekteVon()` — führt `$effect`-Rümpfe wirklich aus |
| `context_herkunft_zweige_eingefroren.test.ts` | test | Die 53er-Ratsche selbst; enthält heute 30 Corridor-Einträge (14+14+1+1) |
| `docs/specs/modules/rework_2276_s6c_alarme.md` | spec | Formvorlage dieser Spec; Design-Entscheidung 1 (Zeilenzahl-Vertrag-Ausnahme) wird hier auf zwei Dateien gleichzeitig übertragen |
| `wertebereicheVergleichSpeicherung.ts:145-183` | module | `erstelleWertebereicheVergleichSpeicherung`/`rollbackCorridorSnapshot` — Speicherweg, den S6d nicht inhaltlich anfasst, nur seine `ws`-Quelle ersetzt |
| `compareHubWizardBridge.ts:340-352` | module | `hubPutQueue` — bleibt unverändert (R7) |
| `docs/context/rework-2276-s6d-corridor-wertprops.md` | context | Abgeschlossene Analyse dieser Scheibe — Grundlage dieser Spec, mit den in dieser Spec korrigierten Zahlen (siehe Fußnote unten) |

> **Korrektur ggü. dem Kontext-Dokument (bindend):** Das Analyse-Dokument
> `rework-2276-s6d-corridor-wertprops.md` nennt an mehreren Stellen eine
> Zwischenüberschrift „30 Einträge, erwartete Zielzahl 53 → 45" sowie in E2
> „24 Überlebende (12 Paare)" und in R3 „20 Überlebende (10 Paare)" — das sind
> Reste einer früheren Entwurfsfassung. **Verbindlich sind ausschließlich die
> Zahlen dieser Spec:** Zielzahl **53 → 47**, **6 fallende Einträge** (3
> Desktop/Mobil-Paare: `:57`/`:70`, `:79`/`:91`, `:89`/`:96`), **24
> Überlebende im Corridor-Umfeld** = **22 Einträge in den beiden
> `.svelte`-Dateien (11 Paare)** + **2 unveränderte Einzeleinträge**
> (`corridorEditorState.ts:297`, `wertebereicheVergleichSpeicherung.ts:200`).
> E1 (Entscheidungen-Abschnitt des Kontext-Dokuments) ist mit diesen Zahlen
> bereits konsistent — nur die Zwischenüberschrift und E2/R3 sind veraltet.
> Wer in `/40` aus dem Kontext-Dokument zitiert, muss diese Fußnote lesen.

## Implementation Details

### Design-Entscheidungen

1. **`corridorPropsAus(wiz)` statt dreifacher Inline-Glasur (Muster
   `alarmePropsAus`).** Bei drei Mounts × vier Feldern wären Inline-Adapter
   dreifache Gelegenheit zur Drift — genau das Anti-Pattern, das #2276
   abbaut. Eine Funktion in `compare/corridorPropsAus.ts` baut das komplette
   Bündel (vier Werte + vier Rückrufe).
   🔴 **Form-Auflage A1 (prüfbar, kein Prosa-Wunsch):** `corridorPropsAus(wiz)`
   wird an **allen drei** Vergleichs-Mounts **im Markup-Ausdruck selbst**
   aufgerufen — `{...corridorPropsAus(wiz)}` — **niemals** in eine Variable
   im Instanz-Skript gehoben. Ein einmal berechnetes, in einer
   Skript-Variable eingefrorenes Objekt bestünde SSR-Prüfstand und
   AST-Wächter anstandslos und fiele erst im Browser auf, weil die
   `$state`-Lesezugriffe dann außerhalb des reaktiven Renderns registriert
   würden. Diese Form kann ein AST-Wächter tatsächlich messen — „ist
   reaktiv" kann er nicht.

2. **`corridorZustandsBruecke(werte, setzen)` als Proxy-Adapter (Auflage A2,
   Muster `alarmZustandsBruecke`).** `wertebereicheVergleichSpeicherung.ts`
   braucht eine **lebendige, mutierbare Objektreferenz**, keine reinen
   Wertprops: `rollbackCorridorSnapshot` schreibt `target[field] =
   before[field]` direkt auf `ws`, und `erstelleWertebereicheVergleichSpeicherung`
   hält `ws` in einer Closure und liest es bei jedem `aenderungMelden()`
   neu (R2). Die Brücke ist ein `Proxy` über einem leeren Objekt: `get`
   liest bei jedem Zugriff frisch aus `werte()` (den vier aktuellen
   Wertprops), `set` reicht den geänderten Wert an `setzen` weiter (den
   passenden `on*Change`-Rückruf), ohne lokal zu speichern. Bei Corridor
   sind es **vier** Felder (`corridors`, `idealRanges`, `activeMetricKeys`,
   `metricAlertLevels`) — alle unter identischem Namen, die
   Namensumleitung `PROP_JE_FELD` aus S6c entfällt (S6c brauchte sie, weil
   dort Prop- und Feldname divergierten; bei Corridor sind sie gleich).
   **Platzierung ist Pflicht, keine Vorliebe:** die Brücke steht **unterhalb
   Zeile 200** — legte man sie an die S6c-Position (`:162-195`), verschöbe
   das den eingefrorenen Eintrag `:200` nach unten und machte die Ratsche
   rot, ohne dass inhaltlich etwas falsch wäre.

3. **Optionsfeld `ws` → `zustand` (Auflage A3) — mit einer Nuance ggü. S6c.**
   Der AST-Wächter zählt jeden `Identifier` mit dem gesuchten Namen, auch
   als Objektschlüssel (S6c-Lehre) — deshalb muss die Options-Schnittstelle
   `WertebereicheVergleichSpeicherungOptionen.ws` und das Feld `p.ws` in
   `wertebereicheVergleichSpeicherungAktiv` umbenannt werden. Die Zeile 200
   (`return p.context === 'vergleich' && !!p.ws && !!p.preset &&
   !!p.saveController;`) **bleibt auf ihrer Position**, ihr **Text** ändert
   sich zu `!!p.zustand`. Weil diese Zeile heute **keine**
   `BLEIBT_MIT_INHALT`-Fesselung trägt (nur die vier AlarmeTab-Einträge aus
   S6c haben eine) und ihre Position stabil bleibt, gilt für sie weiterhin
   der **alte, positionsbasierte Vertrag** — eine neue Fesselung ist NICHT
   erforderlich, aber die Textänderung MUSS im selben Commit erfolgen wie
   die Umbenennung in `CorridorEditor(Mobile).svelte`, sonst kompiliert der
   Baustein nicht. **Explizite Entscheidung dieser Spec** (Lücke aus dem
   Kontext-Dokument R2/E1 geschlossen): kein neuer `BLEIBT_MIT_INHALT`-Eintrag
   für `wertebereicheVergleichSpeicherung.ts:200`.
   **Nuance bei den 22 `.svelte`-Überlebenden:** anders als bei S6c, wo die
   vier BLEIBT-Einträge ihren `context===`-Bedingungstext byte-identisch
   behielten (nur die Zeilenposition verschob sich durch neue Prop-Zeilen
   darüber), liest **eine** der elf Corridor-Bedingungen (`isFreshCompareCreate`,
   `:95`/`:98`) den `ws`-Zustand **in derselben Zeile** wie die
   `context===`-Prüfung: `const isFreshCompareCreate = context === 'vergleich'
   && !ws?.isEditMode && (ws?.corridors ?? []).length === 0;`. Nach dem
   Umbau liest diese Zeile die Wertprops (`!isEditMode`/`(corridors ??
   []).length === 0`) statt `ws?.…` — ihr **Text ändert sich also
   zusätzlich zur Position**. `BLEIBT_MIT_INHALT` muss für diesen Eintrag
   den **nach dem Umbau gültigen** Wortlaut fesseln, nicht den heutigen. Die
   übrigen zehn Paare enthalten keinen direkten `ws`-Bezug in der
   `context===`-Zeile selbst (der `ws`-Zugriff liegt jeweils im Block
   darunter oder gar nicht vor) und behalten ihren Bedingungstext
   byte-identisch — nur ihre Position verschiebt sich.

4. **E4/E5-Konflikt aufgelöst: kein separater SSR-Test, die Zusicherung
   wandert vollständig in die E2E-Spec.** Die Analyse verwirft in E4 den
   Callback-Umbau der Weiche `:240`/`:207` unter anderem mit der Begründung,
   der Ungültig-Fall sei im Kern nicht messbar (SSR läuft ohne DOM, `$effect`
   läuft dort nie), verlangt in E5 aber einen RED-Test genau dafür und
   plant eine CREATE-Zeile für einen SSR-AC-12-Test in
   `shared/corridor-editor/__tests__/`. Das ist so **nicht baubar**:
   `maybeSchedule` (und damit die Weiche) sitzt innerhalb der `.svelte`-Dateien
   selbst, die SSR-Harness läuft mit `generate: 'server'` ohne DOM, und
   dieses Projekt hat keinen Component-Test-Runner mit DOM (Frontend-Tests
   laufen über `node --test`, kein Vitest/JSDOM — Widerspruch bereits im
   Kontext-Dokument R6 selbst angelegt).
   **Festlegung dieser Spec:** Die E5-Zusicherung wird **im Browser**
   gemessen, als zwei Testfälle in `frontend/e2e/compare-wertebereiche-wertprops.spec.ts`:
   - **Trip-Fläche (Route, A):** beidseitig offene Grenze herstellen → der
     Dirty-/Ungespeichert-Zustand wird gesetzt (Speicher-Indikator zeigt
     NICHT „Gespeichert ✓" neben dem Fehlerbanner).
   - **Vergleichs-Fläche (Hub, B):** dieselbe ungültige Grenze herstellen →
     es wird nichts persistiert, kein PUT ausgelöst.
   Die CREATE-Zeile für den separaten SSR-AC-12-Test **entfällt ersatzlos**
   (Wirkort-Argument: die Zusicherung wirkt im Browser, nicht dort, wo der
   Code textuell steht — Lehre aus S5/R6, dieselbe Lehre, die S6c zu seinem
   AC-4-Wirkort-Guard über `effekteVon()` geführt hat; hier greift
   `effekteVon()` NICHT, weil die Weiche keinen eigenständigen `$effect`
   ist, sondern eine synchrone Verzweigung innerhalb eines DOM-Event-Handlers,
   den die SSR-Harness gar nicht auslöst).
   **Platzierung in EINER neuen Datei, nicht in zwei:** Der Trip-Fall
   könnte alternativ in `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`
   ergänzt werden (dort liegt bereits die etablierte Desktop+Mobil-Abdeckung
   für Corridor/Trip). **Entscheidung: beide Fälle (Trip + Hub) bleiben in
   der neuen Datei `compare-wertebereiche-wertprops.spec.ts`**, weil (a) die
   zentrale Zusicherung dieser Scheibe genau der **Kontrast** zwischen den
   beiden Flächen ist — Route/Vergleich nebeneinander im selben Spec-File zu
   führen macht den Verhaltensunterschied direkt sichtbar, statt ihn über
   zwei Dateien zu verteilen; (b) `speicherung-ueberlebt-neuladen.spec.ts`
   prüft eine andere Eigenschaft (Reload-Überleben), nicht den
   Dirty-Zustand bei einer strukturell ungültigen Eingabe — eine
   themenfremde Ergänzung hätte die Scheiben-Disziplin dieser bereits sehr
   großen Datei weiter verwässert; (c) „keine weitere neue E2E-Datei über
   die eine geplante hinaus" bleibt eingehalten, da beide Fälle in der
   ohnehin geplanten Datei landen.

5. **Zeilenzahl-Vertrag wird für BEIDE Corridor-`.svelte`-Dateien
   ausgesetzt — als Kommentar-Änderung an der Ratsche selbst zu schreiben.**
   Der Kommentarblock von `context_herkunft_zweige_eingefroren.test.ts`
   sagt heute wörtlich: „Fuer alle Dateien AUSSERHALB von `AlarmeTab.svelte`
   gilt der alte Vertrag unveraendert weiter: verschobene Zeilennummer =
   Befund, kein Nachtrag." Diese Ausnahme muss für S6d **erweitert** werden
   — sie gilt sonst nur noch für `AlarmeTab.svelte` und ein Umbau, der die
   Zeilen von `CorridorEditor(Mobile).svelte` verschiebt, würde fälschlich
   als Regression gemeldet. `/50` schreibt in den Kommentarblock einen
   neuen Absatz nach dem S6c-Muster: „🔴 STAND S6d: der Zeilenzahl-Vertrag
   gilt zusätzlich NICHT für `CorridorEditor.svelte` und
   `CorridorEditorMobile.svelte` — dort werden 6 Einträge gestrichen und 22
   auf neue Zeilennummern nachgeführt, per `BLEIBT_MIT_INHALT` inhaltlich
   gefesselt." Dies ist **keine Nebenwirkung des Umnummerierens**, sondern
   eine eigene, benannte Änderungszeile am Kommentar — ohne sie liest sich
   der Vertrag weiterhin als „nur AlarmeTab", und ein künftiger Leser könnte
   die Corridor-Verschiebung fälschlich für einen Regressionsbefund halten.

6. **Fläche C ruft `getContext` selbst (Auflage A4) — keine offene
   Designfrage.** `CompareNewEditor.svelte:65` hat die Referenz bereits
   (`const wiz = getContext<CompareWizardState>('compare-wizard-state')`)
   und versorgt damit schon die Alarme-Mounts. Zulässig, weil die Datei in
   `compare-new/` liegt, nicht in `shared/`.

7. **Schicksals-Tabelle der 14 Corridor-Ratschen-Paare** (Basis `c737159e`,
   Bedingungstext wörtlich aus dem Quelltext gelesen, Desktop:Mobil):

   | Desktop:Mobil | Bedingung (wörtlich, Desktop) | Schicksal | Grund |
   |---|---|---|---|
   | `:57`/`:70` | `const ws = context === 'vergleich' ? getContext<CompareWizardState>('compare-wizard-state') : undefined;` | **FÄLLT** | der Context-Zugriff selbst — genau das, was diese Scheibe abbaut |
   | `:79`/`:91` | `context === 'vergleich' ? (ws?.metricAlertLevels as …) : trip?.display_config?.metric_alert_levels` (Definition `originalLevels`) | **FÄLLT** | reine Quellenwahl, dasselbe Feld nur zwei Speicherorte |
   | `:89`/`:96` | `context === 'vergleich' ? [...materializeActiveMetricKeys(ws?.activeMetricKeys ?? null)] : [];` (Definition `originalActiveMetricKeys`) | **FÄLLT** | reine Quellenwahl, reines Wizard-Feld, als Prop versorgbar |
   | `:95`/`:98` | `const isFreshCompareCreate = context === 'vergleich' && !ws?.isEditMode && (ws?.corridors ?? []).length === 0;` | **BLEIBT** (Text ändert sich, siehe Design-Entscheidung 3) | Compare-only-Produktverhalten (Profil-Prefill beim Anlegen), Trip hat kein Pendant — die BRANCH bleibt, nur ihre `ws`-Lesezugriffe werden zu Wertprops |
   | `:138`/`:126` | `if (context !== 'vergleich' \|\| compareDefs !== null \|\| compareDefsError) return;` | BLEIBT | Effect-Guard eigener Compare-Metrikkatalog (`/api/compare/metrics`), kein `ws`-Bezug in dieser Zeile |
   | `:170`/`:151` | `if (context !== 'route' \|\| routeExtraDefs !== null) return;` | BLEIBT | Spiegelbild-Guard Route-Metrikkatalog |
   | `:240`/`:207` | `if (context === 'vergleich') {` (in `maybeSchedule`) | BLEIBT | E4: Ungültig-Fall trägt dokumentierten fachlichen Unterschied (Route `setDirty()`, Vergleich bewusst nichts, F001/F005 aus S3) — keine reine Herkunfts-Weiche |
   | `:268`/`:234` | `const next = context === 'vergleich'` (in `add()`, `addCompareRow` vs. `addRow`) | BLEIBT | zwei Metrik-Domänen mit eigenen Defaults, kein `ws`-Bezug |
   | `:302`/`:297` | `{#if context === 'vergleich' && compareDefsError}` | BLEIBT | blockierender Fehlerbanner nur im Vergleich |
   | `:315`/`:310` | `{:else if context === 'vergleich' && compareDefs === null}` | BLEIBT | Ladezustand Compare-Katalog |
   | `:318`/`:313` | `{:else if context === 'route' && routeExtraDefs === null}` | BLEIBT | Ladezustand Route-Katalog |
   | `:324`/`:318` | `{#if context === 'vergleich'}` (Überschrift/Erklärtext) | BLEIBT | inhaltlich verschiedene Texte |
   | `:345`/`:330` | `{#if context === 'route' && routeDefsFailed}` | BLEIBT | Non-blocking Fallback nur Route |
   | `:474`/`:451` | `{#if context === 'vergleich'}` (Neutralitäts-Hinweis) | BLEIBT | AC-13, Compare-Eigenschaft „kein Score · kein Rang" |

   **Bilanz: 3 Paare fallen = 6 Einträge, 11 Paare bleiben = 22 Einträge.
   Ratsche 53 → 47.** `corridorEditorState.ts:297` und
   `wertebereicheVergleichSpeicherung.ts:200` bleiben unverändert in Position
   (Design-Entscheidung 3).

### Wirkort je Zusicherung

| Zusicherung | Wirkort | Warum |
|---|---|---|
| AC-1 (kein `ws`/`getContext` mehr) | Kern — AST/Compile | Statischer Fakt, im Quelltext direkt prüfbar |
| AC-2 (Selbst-Speicher-Effekt schweigt an Fläche A/C, wirkt an Fläche B) | Kern — `effekteVon()`/`umgebungFuer()` | `$effect`-Rumpf, den die SSR-Harness sonst verwirft — Muster `compare_alarme_wertprops.test.ts` AC-4 |
| AC-3 (Fläche C behält Bedienelemente, beide Mounts, Aufrufform Markup-Ausdruck) | Kern — AST-Wächter | `/compare/new` ist in der CI-Ampel strukturell unbewacht (R1); eine Regression liefe sonst grün durch |
| AC-4/AC-5 (Verhaltensgleichheit Hub, Desktop/Mobil) | E2E | Der Hub ist der einzige Mount mit aktivem, browserseitig beobachtbarem Speicherweg |
| AC-6 (Trip: ungültige Grenze → dirty) | E2E | Wirkt im DOM-Event-Handler `maybeSchedule`, den SSR nicht auslöst; kein `$effect`, den `effekteVon()` fassen könnte |
| AC-7 (Vergleich: ungültige Grenze → nichts) | E2E | Dieselbe Weiche, gegenübergestellt — R6: jeder Wirkort ohne Kern-Zugriff braucht eine E2E-Zeile |
| AC-8 (Adapter/Rollback funktioniert weiterhin) | bestehende SSR-Modultests | Regressionsnetz, unverändert lauffähig, da `corridorZustandsBruecke` dieselbe Schnittstelle (`WertebereicheZustand`) erfüllt |
| AC-9 (Ratsche 53 → 47) | Kern — `node --test` | Struktur-, kein Verhaltensnachweis |
| AC-10 (Fläche A insgesamt unverändert) | bestehende E2E, unverändert grün | Regressionsschutz ohne neue Spec |

### Reihenfolge (Implementation Note)

`corridorPropsAus.ts` und `corridorZustandsBruecke` zuerst (sonst
kompiliert der Baustein-Umbau nicht), dann die beiden `.svelte`-Dateien,
dann die beiden Elternteile (`CompareTabs.svelte`, `CompareNewEditor.svelte`),
zuletzt die Ratschen-Nachführung (braucht die endgültigen Zeilennummern —
E3: RED schreibt die Streichliste + `EINGEFROREN_SOLL_ANZAHL` 53→47, GREEN
misst und trägt die 22 neuen Zeilennummern samt `BLEIBT_MIT_INHALT` nach).
Die Scheibe bleibt **unteilbar**: Desktop und Mobil sind bestätigte
1:1-Duplikate, und die Brücke von den `.svelte`-Änderungen zu trennen
hinterließe einen nicht kompilierenden Zwischenstand.

## Expected Behavior

- **Input:** Im Reiter „Wertebereiche" des Ortsvergleichs (Hub
  `/compare/[id]` sowie Anlege-Desktop/-Mobil `/compare/new`) und im Reiter
  „Wertebereiche" der Tour (`/trips/[id]`) werden Von/Bis-Grenzen je Metrik
  per Zahlenfeld, Band-Drag oder Ordinal-Stufen gesetzt, Metriken
  hinzugefügt/entfernt, Marken gesetzt — wie heute.
- **Output:** Dieselbe sichtbare Auswahl, derselbe Speicherweg im Hub (ein
  PUT je Änderung über `wertebereicheVergleichSpeicherung`, Diff-Gate,
  Rollback), derselbe Dual-Write in den Wizard-Zustand beim Anlegen; keine
  nutzer-sichtbare Verhaltensänderung. Intern lesen/schreiben
  `CorridorEditor`/`CorridorEditorMobile` keine `ws`-Referenz mehr, sondern
  ausschließlich Wertprops und Rückrufe; `ws` und der Aufbau des
  Prop-Bündels liegen jetzt in den Elternteilen (`CompareTabs.svelte`,
  `CompareNewEditor.svelte` über `corridorPropsAus`).
- **Side effects:** `wertebereicheVergleichSpeicherungAktiv({context,
  zustand, preset, saveController})` prüft `ws`-Vorhandensein nicht mehr
  direkt, sondern über die Bridge `zustand` — semantisch identisch, weil
  `corridorZustandsBruecke` an Fläche A/C entweder gar nicht gebaut wird
  oder ihre Werte über die Rückrufe genauso `undefined`/leer bleiben wie
  vorher `ws`.

## Acceptance Criteria

- **AC-1 (Corridor-Bausteine sind im Vergleichs-Zweig wertprop-rein):**
  Given `CorridorEditor.svelte` und `CorridorEditorMobile.svelte` lesen/
  schreiben heute `ws` an den in der Schicksals-Tabelle gemessenen Stellen
  (Lesen `:57,79,89,95`, Schreiben `:223-226`, Durchreichen `:63,66`) /
  When beide Dateien auf reine Wertprops (`corridors`, `idealRanges`,
  `activeMetricKeys`, `metricAlertLevels`) + Rückrufe (`onCorridorsChange`,
  `onIdealRangesChange`, `onActiveMetricKeysChange`,
  `onMetricAlertLevelsChange`) umgestellt werden / Then enthält keine der
  beiden Dateien mehr einen `getContext`-Aufruf und keinen Typ-Import von
  `CompareWizardState`.
  - Test: Kern — AST-Scan in `compare_corridor_wertprops.test.ts` (Muster
    AC-1 aus `compare_alarme_wertprops.test.ts`): kein `getContext`- und
    kein `CompareWizardState`-Identifier mehr im Instanz-Skript beider
    Dateien; die Prop-Schnittstelle bindet alle acht freigegebenen Namen.

- **AC-2 (Wirkort-Guard: der Selbst-Speicher-Effekt wirkt nur an Fläche B):**
  Given `vergleichSpeicherung` entsteht nur, wenn
  `wertebereicheVergleichSpeicherungAktiv({context, zustand, preset,
  saveController})` wahr ist / When der Effekt-Rumpf über `effekteVon()` an
  den negativen Orten (Fläche A Trip, Fläche C Anlegen mit `preset:
  null`/`saveController: null`) wirklich ausgeführt wird / Then bleibt der
  Rumpf dort wirkungslos (kein `aenderungMelden()`-Aufruf), und am
  positiven Ort (Fläche B, `preset`+`saveController` gesetzt) wirkt er.
  - Test: Kern — `compare_corridor_wertprops.test.ts`, Muster
    `compare_alarme_wertprops.test.ts` AC-4 (`umgebungFuer()`/`effekteVon()`).
  - Mutations-Gegenprobe: `wertebereicheVergleichSpeicherungAktiv` auf
    `() => false` verfälschen ⇒ der Effekt wirkt nirgends mehr, auch nicht
    am positiven Ort ⇒ Test wird rot (Positiv-Gegenprobe); auf `() => true`
    verfälschen ⇒ der Effekt wirkt an den negativen Orten weiter ⇒ Test
    wird rot (Negativ-Gegenprobe). Kein E2E-Test fängt diese Mutation, weil
    nur der Hub browserseitig geprüft wird und dort die Bedingung
    strukturell immer erfüllt ist.

- **AC-3 (Fläche C behält ihre Bedienelemente an beiden Mounts, Aufrufform
  geprüft):** Given Mount (C, Desktop) `CompareNewEditor.svelte:389` und
  Mount (C, Mobil) `:485` übergeben heute nur `context="vergleich"` / When
  beide Mounts auf `{...corridorPropsAus(wiz)}` umgestellt werden / Then
  rendern an beiden Mounts weiterhin alle Bedienelemente, für die
  `corridorPropsAus` einen Rückruf liefert, UND `corridorPropsAus(wiz)`
  steht im Markup-Ausdruck selbst (nicht in einer Skript-Variable gehoben).
  - Test: Kern — AST-Wächter in `compare_corridor_wertprops.test.ts`, der
    über alle drei Vergleichs-Mounts (B, C-Desktop, C-Mobil) prüft, dass
    `corridorPropsAus(wiz)` als Spread-Ausdruck im Markup-Knoten selbst
    aufgerufen wird und keine der acht Prop-Bindungen fehlt. Keine
    gelistete E2E-Spec berührt `/compare/new` im Wertebereiche-Reiter —
    ohne diesen Kern-Wächter liefe eine Regression an Fläche C grün durch
    die CI-Ampel (F001-Lehre aus S6b/S6c).
  - Mutations-Gegenprobe: `{...corridorPropsAus(wiz)}` in eine
    Skript-Variable `const corridorProps = corridorPropsAus(wiz)` heben und
    `{...corridorProps}` spreaden ⇒ dieser Wächter wird rot (SSR-Prüfstand
    und ein reines Werte-Diff blieben grün, weil die Werte selbst korrekt
    sind — nur ihre Reaktivität bricht, was erst im Browser sichtbar würde).

- **AC-4 (Verhaltensgleichheit im Browser am Hub, Desktop):** Given vor der
  Umstellung wirken alle Wertebereiche-Bedienelemente im Hub
  (`/compare/[id]`, Desktop-Viewport) und werden über den einen bestehenden
  PUT gespeichert / When derselbe Ablauf nach der Umstellung im Browser
  gegen Staging durchgeführt wird / Then bleibt das Verhalten unverändert:
  Grenzen setzen (Zahlenfeld, Band-Drag), Metrik hinzufügen/entfernen,
  Marken setzen — Änderungen überstehen Speichern/Reload, genau ein PUT je
  Änderung.
  - Test: Live-E2E — `frontend/e2e/compare-wertebereiche-wertprops.spec.ts`,
    Eintrag in `.github/ci_e2e_specs.txt`.

- **AC-5 (Verhaltensgleichheit im Browser am Hub, Mobil):** Given dieselbe
  Ausgangslage wie AC-4, aber im Mobil-Viewport mit Band-Drag/Ordinal-Stufen
  über Touch-Pointer-Events / When derselbe Ablauf nach der Umstellung im
  Mobil-Viewport durchgeführt wird / Then bleibt das Verhalten identisch zu
  AC-4, inklusive funktionierendem Dual-Handle-Drag.
  - Test: Live-E2E — dieselbe Spec-Datei wie AC-4, zweiter Testfall im
    Mobil-Viewport (Muster `speicherung-ueberlebt-neuladen.spec.ts:423`).

- **AC-6 (E5, Trip-Fläche: ungültige Grenze setzt dirty):** Given der
  Ungültig-Fall der Weiche `maybeSchedule` (`:240`/`:207`) setzt im
  Trip-Kontext aktiv `setDirty()`, damit der Indikator nicht fälschlich
  „Gespeichert ✓" neben einem sichtbaren Fehlerbanner zeigt / When im
  Wertebereiche-Reiter der Tour eine beidseitig offene Grenze hergestellt
  wird (weder Von noch Bis gesetzt) / Then zeigt der Fehlerbanner den
  Validierungsfehler UND der Speicher-Indikator zeigt NICHT „Gespeichert
  ✓" für diese Änderung.
  - Test: Live-E2E — `compare-wertebereiche-wertprops.spec.ts`, Fläche A
    (Trip), Desktop.

- **AC-7 (E5, Vergleichs-Fläche: dieselbe ungültige Grenze löst nichts
  aus):** Given der Ungültig-Fall derselben Weiche delegiert im
  Vergleichs-Kontext bewusst NICHTS, damit der externe Speichern-Button im
  Hub keinen ungültigen Zwischenstand persistiert (F001/F005 aus S3) / When
  im Wertebereiche-Reiter des Hubs dieselbe beidseitig offene Grenze
  hergestellt wird / Then wird kein PUT ausgelöst und der zuletzt
  gespeicherte Serverstand bleibt unverändert.
  - Test: Live-E2E — dieselbe Spec-Datei, Fläche B (Hub), im direkten
    Kontrast zu AC-6 (derselbe Testlauf demonstriert beide Ausgänge
    nebeneinander).
  - Mutations-Gegenprobe: Die Weiche `if (context === 'vergleich') { … }
    else { … }` auf `if (true)` verfälschen (Trip nimmt fälschlich den
    Vergleichs-Pfad) ⇒ AC-6 wird rot (Trip zeigt „Gespeichert ✓" trotz
    Fehler); auf `if (false)` verfälschen ⇒ AC-7 wird rot (Vergleich löst
    einen PUT mit ungültigem Zwischenstand aus). Kein Kern-Test fängt
    beides — die Weiche liegt in einem DOM-Event-Handler, den SSR nicht
    ausführt (Design-Entscheidung 4).

- **AC-8 (Adapter `corridorZustandsBruecke` erhält den Speicherweg):**
  Given `erstelleWertebereicheVergleichSpeicherung`/
  `rollbackCorridorSnapshot` brauchen heute eine lebendige, mutierbare
  `ws`-Referenz / When `ws` durch `corridorZustandsBruecke(werte, setzen)`
  ersetzt wird (Proxy: `get` liest frisch aus den Wertprops, `set` ruft den
  passenden Rückruf) / Then bleiben Diff-Gate, EIN-PUT-Garantie, Konflikt,
  Flush und Rollback unverändert funktionsfähig.
  - Test: bestehende 11 SSR-Modultests unter `corridor-editor/__tests__/`
    (Regressionsnetz) laufen ohne inhaltliche Änderung grün — sie
    instanziieren `WertebereicheZustand`-kompatible Objekte und prüfen
    dessen Verhalten, nicht die Quelle der Referenz.

- **AC-9 (Ratsche bewusst gepflegt — Strukturwächter, kein
  Verhaltensnachweis):** Given
  `context_herkunft_zweige_eingefroren.test.ts` hält heute 30
  Corridor-Einträge in der eingefrorenen Soll-Liste,
  `EINGEFROREN_SOLL_ANZAHL = 53` / When im selben Commit wie der jeweilige
  Rückbau die 6 in der Schicksals-Tabelle als FÄLLT markierten Einträge
  gestrichen werden (die 22 BLEIBT-Einträge in beiden `.svelte`-Dateien auf
  ihre neuen Zeilennummern nachgeführt und per `BLEIBT_MIT_INHALT`
  gefesselt), `EINGEFROREN_SOLL_ANZAHL` auf 47 gesetzt und der
  Kommentarblock um die Corridor-Ausnahme vom Zeilenzahl-Vertrag erweitert
  wird / Then ist der Ratschen-Test grün, und
  `corridorEditorState.ts:297`/`wertebereicheVergleichSpeicherung.ts:200`
  bleiben unverändert in der Liste.
  - Test: Kern — `node --test` auf
    `context_herkunft_zweige_eingefroren.test.ts`.
  - 🔴 Diese AC ist ein **Strukturwächter**, kein Verhaltensnachweis: die
    Zusicherung ist nicht „das Programm verhält sich richtig", sondern „die
    Zahl der HERKUNFT-Verzweigungen ist die, die diese Scheibe bewusst
    herbeigeführt hat".
  - Mutations-Gegenprobe: Einen der 22 BLEIBT-Einträge zusätzlich aus
    `EINGEFROREN` streichen, ohne die zugehörige Bedingung im Quelltext zu
    entfernen ⇒ der reale Zählbefehl liefert den Eintrag weiterhin, der
    Mengenvergleich schlägt fehl. Zusätzlich (analog S6c AC-6, aber neu für
    Corridor): einen `BLEIBT_MIT_INHALT`-Eintrag auf eine fremde,
    tatsächlich existierende Zeile im 8-Zeilen-Fenster setzen, ohne den
    Bedingungstext anzupassen ⇒ die `zeile`-Prüfung schlägt fehl, weil an
    der neuen Position eine andere Bedingung steht.

- **AC-10 (Fläche A bleibt vollständig unverändert):** Given die Tour
  (`/trips/[id]`) hat heute keinen `compare-wizard-state`-Context, `ws` ist
  dort stets `undefined`, der Speicherweg läuft über `saveController` /
  When beide Corridor-Dateien auf Wertprops umgestellt werden, ohne dass
  sich an Mount (A) etwas ändert (`TripTabs.svelte:227/229` reichen
  weiterhin nur `trip`/`onTripUpdate`/`saveController` durch, `context`
  bleibt implizit/`'route'`) / Then bleibt das Verhalten der Tour
  identisch: Zahlenfeld-/Band-Drag-Änderungen speichern sofort per PUT,
  überstehen Reload.
  - Test: bestehende E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`
    (`:200` Desktop, `:423` Mobil) und
    `frontend/e2e/issue-953-alerts-autosave-tabswitch.spec.ts` bleiben ohne
    Änderung grün — reiner Regressionsnachweis, keine neue Spec nötig.

## Known Limitations

- **Doppelquelle als Dauerzustand ist verboten.** „Wertprop wenn da, sonst
  `ws`" ist genau das Anti-Muster, das S6 beseitigen soll. Die Umstellung
  ist an allen drei Vergleichs-Mounts vollständig oder unterbleibt.
- **`:240`/`:207` bleibt eine Herkunfts-Weiche.** Der naheliegende
  Callback-Umbau (`onAenderung`/`onUngueltig`) ist verworfen (E4) — ein
  Ratschen-Paar ist diesen Einsatz auf einem ungetesteten Pfad nicht wert.
  Fällt frühestens in S6f zur erneuten Prüfung an.
- **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`
  zurück** — `/70-deploy` überspringt dann die gesamte
  Staging-Validierung. Nach **jedem** Commit dieser Scheibe gegenlesen.
- **Zwei der drei Vergleichs-Mounts sind in der CI-Ampel strukturell
  unbewacht** (`/compare/new`, Mounts C-Desktop/C-Mobil) — deshalb trägt
  AC-3 den Nachweis im Kern statt in einer weiteren E2E-Spec.
- **`wertebereicheVergleichSpeicherung.ts:200` behält seine Position ohne
  neue `BLEIBT_MIT_INHALT`-Fesselung** (Design-Entscheidung 3) — ihr Schutz
  bleibt der alte, positionsbasierte Vertrag. Eine künftige Scheibe, die
  diese Zeile erneut inhaltlich ändert, MUSS erneut prüfen, ob eine
  Fesselung inzwischen nötig geworden ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Wertprops + Rückrufe statt `wiz`/`ws` ist mit
  `CompareOutlookLayoutControls` (#1720 S1), `CompareHourlyLayoutControls`
  (S6b, live `8207c157`) und `AlarmeTab` (S6c, live `c737159e`) bereits
  entschieden und produktiv erprobt — diese Scheibe wendet dasselbe,
  bereits akzeptierte Muster auf den Corridor-Organismus an und trifft
  keine neue Architekturentscheidung. Die Bündel-Funktion
  `corridorPropsAus(wiz)` und der Proxy-Adapter `corridorZustandsBruecke`
  sind lokale Umsetzungsentscheidungen innerhalb dieses Musters (begründet
  in Implementation Details, Design-Entscheidungen 1–2), kein
  Architekturwechsel.

## Changelog

- 2026-09-22: Initial spec created (Scheibe S6d von #2276, Epic #2345)
