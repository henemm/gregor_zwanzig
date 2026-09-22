---
entity_id: rework_2276_s6e_versand
type: module
created: 2026-09-22
updated: 2026-09-22
status: draft
version: "1.0"
tags: [compare, versand, wertprops, ratsche, refactor]
---

# Versand-Fläche des Ortsvergleichs auf Wertprops (Issue #2276, Scheibe S6e, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Scheibe **S6e** von #2276 (Epic #2345) stellt den geteilten Organismus `VersandTab.svelte`
(`context="route"|"vergleich"`) im **Vergleichs-Zweig** vom Prop `wiz: CompareWizardState` auf
reine **Wertprops + Änderungs-Rückrufe** um — nach dem in S6c (`AlarmeTab.svelte`, live
`c737159e`) und S6d (`CorridorEditor(Mobile).svelte`, live `930ccdc0`) erprobten Muster. Der
`wiz`-Zugriff verschwindet aus `shared/VersandTab.svelte` und wandert zu den Elternteilen hoch:
eine neue Bündel-Funktion `versandPropsAus(wiz)` (`compare/versandPropsAus.ts`) baut das
Prop-Bündel, das alle **drei** Vergleichs-Mounts identisch einspeisen. Verhalten bleibt
unverändert.

Anders als S6c/S6d hat diese Scheibe **eine** Datei (kein Desktop/Mobil-Duplikat), aber **drei
Feldklassen statt einer** (Design-Entscheidung 2): sieben Snapshot-Felder mit Bündel-Mitgliedschaft
in der Speicherweg-Brücke, ein achtes Feld (`sendEmail`) mit eigenem Wertprop+Rückruf, aber
bewusst **außerhalb** der Brücke, und drei tote Legacy-Restfelder mit Wertprop ohne eigenen
Rückruf, ausschließlich über eine generische Rollback-Senke beschreibbar (Muster
`onAlarmFeldSetzen`, S6c). Diese Scheibe ist die **letzte**, die eine `wiz`-Referenz aus einem
`shared/`-Organismus abbaut, bevor S6f die verbleibende Bilanz zieht (`compareHubWizardBridge`
ohne produktiven Importeur).

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/VersandTab.svelte`,
  `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`,
  `frontend/src/lib/components/compare/versandPropsAus.ts` (neu),
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`,
  `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`,
  `frontend/src/lib/components/shared/__tests__/compare_versand_wertprops.test.ts` (neu)
- **Identifier:** `VersandTab` (Props im Vergleichs-Zweig: acht Wertprops
  `sendEmail`/`sendTelegram`/`sendSms`/`morningEnabled`/`morningTime`/`eveningEnabled`/
  `eveningTime`/`endDate` + drei Legacy-Lesewerte `alertCooldownMinutes`/`alertQuietFrom`/
  `alertQuietTo` + acht `onXChange`-Rückrufe + `onVersandFeldSetzen`; unveränderte Props
  `context`/`activation`/`preset`/`saveController`/`enqueueHubWrite`/`onCompareUpdate`),
  `versandPropsAus(wiz)` (`compare/versandPropsAus.ts`, neu), `versandZustandsBruecke(werte,
  setzen)` (`versandVergleichSpeicherung.ts`, neu), Mount (B, Hub) `CompareTabs.svelte:1070`,
  Mount (C, Anlegen Desktop) `CompareNewEditor.svelte:407`, Mount (D, Anlegen Mobil)
  `CompareNewEditor.svelte:493`, Mount (A, Trip) `BriefingScheduleTab.svelte:130`
  (unverändert, kein `wiz`)

Betroffene Schicht: ausschließlich **Frontend** (`frontend/src/lib/components/`). Kein
Go-API- und kein Python-Core-Code in dieser Scheibe.

## Nicht in dieser Scheibe

- **Kein neuer E2E-Test.** `frontend/e2e/compare-versand-speichert-selbst.spec.ts` (S5, in der
  CI-Ampel via `.github/ci_e2e_specs.txt`) deckt die Hub-Fläche bereits vollständig ab (AC-1
  Morgen-Zeit → ein PUT, AC-5 „Bis auf Weiteres", AC-4 Reiterwechsel-Flush mit Alarme, AC-6
  Konflikt, AC-7 Pausieren, AC-11 Reload-Überleben aller übrigen Felder inkl. der drei
  Legacy-Restfelder). Anders als S6d gibt es hier keinen Verhaltens-Kontrast zwischen zwei
  Flächen, den eine neue Spec zeigen müsste — die bestehende Spec bleibt der
  Verhaltensgleichheits-Nachweis.
- **`hydrateVersandFieldsFromPreset`, `baueVersandNutzlast`, `flushPendingVersandSave` bleiben
  inhaltlich unverändert.** Diese Scheibe ersetzt nur die Zulieferung des
  `VersandHydrationTarget`, nicht die Nutzlast-Erzeugung.
- **`mergeReportConfig.ts` und der Route-Zweig (`context="route"`) werden nicht angefasst.**
  Mount (A) bleibt exakt wie heute — kein `wiz`, kein Self-Save.
- **Die drei toten Legacy-Restfelder bekommen KEIN Bedienelement.** Die Alert-Zustellungs-Sektion
  bleibt in `AlarmeTab.svelte` (#1258 S4) — diese Scheibe rührt daran nicht.
- **`hub_versand_inline.test.ts` wird nicht angefasst.** Der Test prüft ausschließlich die reine
  Funktion `hydrateVersandFieldsFromPreset`, mountet `VersandTab` nicht — unbeteiligt am Umbau.
- **`versand_tab_laedt_keine_compare_klebeschicht.test.ts` (AC-8 aus S5) bleibt unverändert
  grün** — `VersandTab` importierte auch vorher keine Compare-Klebeschicht, der Umbau ändert
  daran nichts.
- **Kein Sub-Schnitt nach Feldern.** Die acht Wertprops + drei Legacy-Lesewerte wandern gemeinsam
  — eine Aufteilung würde die Ratschen-Umstellung mehrfach durchlaufen.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | `wiz?: CompareWizardState`-Prop und der Typ-Import (`:18`) entfallen; Props-Block bekommt acht Wertprops + drei Legacy-Lesewerte + neun Rückrufe (acht `onXChange` + `onVersandFeldSetzen`); `vergleichActiveChannelCount` (`:193-195`) liest die Wertprops statt `wiz.*`; `makeWizChannelHandler` (`:218-223`) entfällt, ersetzt durch direkte Rückruf-Aufrufe je Kanal; Self-Save-Block (`:271-291`) baut lokal `versandZustandsBruecke(werte, setzen)` aus den sieben Snapshot-Feldern + drei Legacy-Feldern (NICHT `sendEmail`) und übergibt sie als `zustand` an `erstelleVersandVergleichSpeicherung`; Markup (`:330-373`) liest/schreibt die neuen Props statt `wiz?.*` |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | MODIFY | `VersandVergleichSpeicherungOptionen.wiz` → `zustand`, `versandVergleichSpeicherungAktiv`s Parameterfeld `wiz` → `zustand` (Zeile 221 bleibt an Position, Text ändert sich zu `!!p.zustand` — Auflage A1); neue Funktion `versandZustandsBruecke(werte, setzen)` **unterhalb Zeile 221**, praktisch ans Dateiende (nach Zeile 300) — ein `Proxy`, `get` liest frisch aus `werte()`, `set` reicht an `setzen` weiter, keine Namensumleitung nötig (Snapshot- und Prop-Namen sind identisch) |
| `frontend/src/lib/components/compare/versandPropsAus.ts` | **CREATE** | Übersetzung Wizard-Zustand → Prop-Bündel: acht Werte (`sendEmail`, sieben Snapshot-Felder) + acht `onXChange`-Rückrufe + drei Legacy-Lesewerte (`alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo`, ohne eigenen Rückruf) + `onVersandFeldSetzen`-Rollback-Senke (`wiz[feld] = wert`, analog `onAlarmFeldSetzen`). Liegt in `compare/`, nicht `shared/` (Muster `alarmePropsAus.ts`/`corridorPropsAus.ts`) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Mount B (`:1070-1079`): `wiz={wizardState}` → `{...versandPropsAus(wizardState)}` inline im Markup-Ausdruck (Aufrufform-Pflicht, Auflage A-Form), übrige Props (`activation`/`preset`/`saveController`/`enqueueHubWrite`/`onCompareUpdate`) unverändert |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Mounts C (`:407`, Desktop) + D (`:493`, Mobil): `{wiz}` → `{...versandPropsAus(wiz)}`, `activation` bleibt separat |
| `frontend/src/lib/components/shared/__tests__/compare_versand_wertprops.test.ts` | **CREATE** | Kern-AST-Wächter analog `compare_alarme_wertprops.test.ts`: AC-1 (kein `wiz`/`CompareWizardState`-Identifier mehr im Instanz-Skript), AC-3 (alle drei Mounts streuen `versandPropsAus(wiz)` identisch, kein Feld fehlt, Aufrufform Markup-Ausdruck), AC-4 (Wirkort-Guard über `effekteVon()`/`umgebungFuer()`: Self-Save-Effekt wirkt nur bei `preset`+`saveController`) |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Neuer 🔴 VERTRAG-Absatz (drittes Beispiel nach S6c/S6d): der Zeilenzahl-Vertrag gilt zusätzlich NICHT für `VersandTab.svelte` — **0 Einträge gestrichen, 3 nachgeführt** (`:284`, `:294`, `:330` auf ihre in GREEN gemessenen neuen Zeilennummern, per `BLEIBT_MIT_INHALT` mit wortgleichem Bedingungstext gefesselt). `EINGEFROREN_SOLL_ANZAHL` bleibt **47** (keine Streichung). `versandVergleichSpeicherung.ts:221` bleibt unverändert in Position und OHNE neue Fesselung (alter, positionsbasierter Vertrag, Auflage A1) |

**7 Dateien** (2 CREATE, 5 MODIFY).

**Zu prüfen, ob eine Saat-Anpassung nötig ist** (Prüfpflicht, nicht Änderungspflicht — mounten
`VersandTab` mit `wiz={...}` bzw. `{wiz}` und laufen nach dem Umbau nur weiter, wenn sie auf die
neuen Props umgestellt werden): die SSR-Modultests, die `VersandTab` selbst rendern (nicht die
reinen Funktions-Tests von `versandVergleichSpeicherung.ts`, die unverändert grün bleiben, weil
sie nur `VersandHydrationTarget`-kompatible Objekte instanziieren). Genaue Liste wird in `/40`
durch Grep auf `wiz={` in `shared/__tests__/` und `compare/__tests__/` neu erhoben (die im
Kontext-Dokument genannten ~18 Dateien sind ein grober Vorbefund, keine verbindliche Zählung).

## Estimated Scope

- **LoC (produktiv, geschätzt):** ca. **+180 / −60** — der Großteil ist der neue AST-Wächter
  (`compare_versand_wertprops.test.ts`) und `versandPropsAus.ts`; die drei
  Ratschen-Nachführungen sind klein (drei Einträge, nicht 22 wie in S6d).
- **Files:** 7 produktiv + eine unbekannte, aber wahrscheinlich zweistellige Zahl an
  Testdateien, die `wiz={...}` auf `VersandTab` mounten (Saat-Anpassung, s.o.).
- **Effort:** medium.
- **Risk Level: NIEDRIG–MITTEL.** Ein Baustein (kein Duplikat-Paar), das Muster ist zum dritten
  Mal erprobt, die Ratschen-Bewegung ist klein (3 statt 6/22 Einträge). Der einzige neue Aspekt
  gegenüber S6c/S6d ist die Drei-Feldklassen-Unterscheidung (`sendEmail` außerhalb der Brücke) —
  ein Übersehen dieser Nuance würde entweder den cosmetic Email-Toggle stillegen (AC-4-Bruch)
  oder `versandSnapshotAus` ein fremdes Feld sehen lassen (AC-5/Payload-Kontamination).
- **LoC-Limit 250/Workflow wird voraussichtlich überschritten** (Testdateien-Saat-Anpassung
  allein potenziell >100 LoC) — `workflow.py set-field loc_limit_override 500` vor `/40`
  einplanen, analog S6c/S6d.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alarmePropsAus.ts`/`onAlarmFeldSetzen` (S6c, live `c737159e`) | module | Präzedenzfall für Bündel-Modul UND für die Rollback-Senken-Konstruktion (`onVersandFeldSetzen`) der drei toten Legacy-Felder |
| `corridorZustandsBruecke`/`corridorPropsAus.ts` (S6d, live `930ccdc0`) | module | Präzedenzfall für den Proxy-Adapter OHNE Namensumleitung (Snapshot- und Prop-Namen sind bei Versand ebenfalls identisch) |
| `compare_alarme_wertprops.test.ts` | test | Formvorbild für `compare_versand_wertprops.test.ts` (AC-1 AST-Scan, AC-3 Drei-Mount-Bündel-Parität, AC-4 Wirkort-Guard) |
| `frontend/src/lib/components/shared/__tests__/svelteInstanzPruefstand.ts` | Prüfstand | `umgebungFuer()`/`effekteVon()` — führt den Self-Save-`$effect`-Rumpf wirklich aus |
| `context_herkunft_zweige_eingefroren.test.ts` | test | Die 47er-Ratsche selbst; enthält heute die drei positionsstrikten `VersandTab.svelte`-Einträge |
| `frontend/e2e/compare-versand-speichert-selbst.spec.ts` (S5) | test | Bestehender Verhaltensgleichheits-Nachweis am Hub — bleibt unverändert grün, kein neuer E2E |
| `docs/specs/modules/rework_2276_s6c_alarme.md` | spec | Formvorlage; Design-Entscheidung zur Rollback-Senke `onAlarmFeldSetzen` wird hier auf drei tote Felder übertragen |
| `docs/specs/modules/rework_2276_s6d_wertebereiche.md` | spec | Formvorlage; Design-Entscheidung zur Namensumleitungs-Freiheit und zur Zeilenzahl-Vertrag-Erweiterung wird hier übernommen |
| `docs/context/rework-2276-s6e-versand.md` | context | Abgeschlossene Analyse dieser Scheibe (inkl. zweier Korrekturen ggü. der ursprünglichen Kontext-Fassung, siehe Fußnote) |

> **Korrektur ggü. dem Kontext-Dokument (bindend):** `rework-2276-s6e-versand.md` behauptete in
> einer früheren Fassung, `sendEmail` könne im Markup hartcodiert (`email: true`) werden. Das ist
> **falsch** — `VersandTab.svelte:335/339` liest/schreibt `wiz.sendEmail` reaktiv über eine
> klickbare Checkbox (`VTBriefingChannels.svelte:127`), und `vergleichActiveChannelCount`
> (`:193-195`) hängt davon ab. **Verbindlich:** `sendEmail` bleibt Wertprop + eigener
> `onSendEmailChange`-Rückruf, schreibt `wiz.sendEmail` direkt und liegt **außerhalb** der
> Speicherweg-Brücke (siehe Implementation Details, Design-Entscheidung 2). Das Kontext-Dokument
> wurde inzwischen nachgeführt — diese Spec ist die verbindliche Fassung.

## Implementation Details

### Design-Entscheidungen

1. **`versandPropsAus(wiz)` statt dreifacher Inline-Glasur (Muster `alarmePropsAus`).**
   Bei drei Mounts × elf Feldern (acht Wertprops + drei Legacy-Lesewerte) wären Inline-Adapter
   dreifache Gelegenheit zur Drift. Eine Funktion in `compare/versandPropsAus.ts` baut das
   komplette Bündel.
   🔴 **Form-Auflage (prüfbar, kein Prosa-Wunsch):** `versandPropsAus(wiz)` wird an **allen
   drei** Vergleichs-Mounts **im Markup-Ausdruck selbst** aufgerufen — `{...versandPropsAus(wiz)}`
   — **niemals** in eine Skript-Variable gehoben (Begründung identisch zu S6c/S6d: ein
   eingefrorenes Objekt bestünde SSR-Prüfstand und AST-Wächter, fiele erst im Browser auf).

2. **Drei Feldklassen, nicht eine — die zentrale Neuerung dieser Scheibe gegenüber S6c/S6d.**
   - **Klasse A (sieben Snapshot-Felder):** `sendTelegram`, `sendSms`, `morningEnabled`,
     `morningTime`, `eveningEnabled`, `eveningTime`, `endDate`. Wertprop + eigener `onXChange`
     (schreibt `wiz.<feld> = wert`) UND Mitgliedschaft in `versandZustandsBruecke`s `werte()`
     (der Speicherweg braucht den frischen Wert für Snapshot/Payload/Rollback).
   - **Klasse B (`sendEmail`, ein Feld, S6e-eigen):** Wertprop + eigener `onSendEmailChange`
     (schreibt `wiz.sendEmail = wert`), aber **NICHT** in `versandZustandsBruecke`s `werte()`.
     Begründung: `VersandSnapshot`/`VersandHydrationTarget` (`versandVergleichSpeicherung.ts:35-59`)
     kennen `sendEmail` nicht — `ComparePreset` hat kein `send_email`-Feld, `baueVersandNutzlast`
     sendet es nie. Nähme die Brücke `sendEmail` dennoch auf, sähe `versandSnapshotAus` ein
     Feld, das der Payload-Baustein ignoriert — reines Rauschen im Diff-Gate, ohne fachlichen
     Sinn. Der Checkbox-Toggle bleibt trotzdem voll interaktiv (Verhaltensgleichheit): er ist
     schon heute persistenzlos (`hydrateVersandFieldsFromPreset` setzt bei jedem Laden
     `sendEmail: true` fix) — diese Eigenschaft ändert sich nicht, sie wird nur nicht
     versehentlich in einen Baustein hineingezogen, der sie nicht kennt.
   - **Klasse C (drei tote Legacy-Restfelder):** `alertCooldownMinutes`, `alertQuietFrom`,
     `alertQuietTo`. Wertprop **ohne eigenen** `onXChange` (kein Bedienelement im Versand-Reiter,
     Alert-Zustellung liegt seit #1258 S4 in `AlarmeTab.svelte`) — aber Mitgliedschaft in
     `versandZustandsBruecke`s `werte()`, weil `baueVersandNutzlast` sie mitsenden MUSS (Spec
     S5 Punkt 6, AC-11: sonst nullt der Versand-PUT die Alarm-Zustellungsfelder). Schreibweg
     ausschließlich über die generische Rollback-Senke `onVersandFeldSetzen(feld, wert)` —
     exaktes Vorbild `alarmePropsAus.ts:129-131` (`onAlarmFeldSetzen`, Kommentar dort: „KEIN
     Bedienelement schreibt hierüber").

3. **`versandZustandsBruecke(werte, setzen)` als Proxy-Adapter (Muster
   `corridorZustandsBruecke`, keine Namensumleitung).** `versandVergleichSpeicherung.ts` braucht
   eine lebendige, mutierbare `VersandHydrationTarget`-Referenz: `rollbackVersandSnapshot`
   schreibt `target[field] = before[field]` direkt, `erstelleVersandVergleichSpeicherung` hält
   die Referenz in einer Closure und liest sie bei jedem `aenderungMelden()` neu. Die Brücke ist
   ein `Proxy` über einem leeren Objekt: `get` liest bei jedem Zugriff frisch aus `werte()` (den
   zehn aktuellen Feldern — sieben Snapshot- + drei Legacy-Felder, NICHT `sendEmail`), `set`
   reicht den geänderten Wert an `setzen` weiter. Bei den sieben Snapshot-Feldern ruft `setzen`
   den passenden `onXChange`-Rückruf auf, bei den drei Legacy-Feldern `onVersandFeldSetzen`.
   Snapshot- und Prop-Namen sind bei Versand identisch (`sendTelegram`, `sendSms`, …) — die
   `PROP_JE_FELD`-Namensumleitung aus S6c entfällt, wie bei S6d.
   **Platzierung ist Pflicht, keine Vorliebe (Auflage A1):** die Brücke steht **unterhalb Zeile
   221** — legte man sie an eine frühere Position, verschöbe das den eingefrorenen Eintrag
   `versandVergleichSpeicherung.ts:221` nach unten und machte die Ratsche rot, ohne dass
   inhaltlich etwas falsch wäre.

4. **Optionsfeld `wiz` → `zustand` — Zeile 221 bleibt an Position, nur ihr Text ändert sich
   (Auflage A1, Nuance ggü. S6d).** `VersandVergleichSpeicherungOptionen.wiz` und
   `versandVergleichSpeicherungAktiv`s Parameterfeld `wiz` werden zu `zustand` umbenannt. Zeile
   221 (`return p.context === 'vergleich' && !!p.wiz && !!p.preset &&
   !!p.saveController;`) **bleibt auf ihrer Position**, ihr **Text** ändert sich zu
   `!!p.zustand`. Weil diese Zeile heute **keine** `BLEIBT_MIT_INHALT`-Fesselung trägt und ihre
   Position stabil bleibt, gilt für sie weiterhin der **alte, positionsbasierte Vertrag** — wie
   `wertebereicheVergleichSpeicherung.ts:200` in S6d. Keine neue Fesselung nötig, aber die
   Textänderung MUSS im selben Commit erfolgen wie die Umbenennung in `VersandTab.svelte`, sonst
   kompiliert der Baustein nicht.

5. **Zeilenzahl-Vertrag wird für `VersandTab.svelte` ausgesetzt — drittes Beispiel nach
   S6c/S6d, aber mit anderer Bilanz: 0 gestrichen, 3 nachgeführt.** Der Kommentarblock von
   `context_herkunft_zweige_eingefroren.test.ts` sagt heute: „Fuer alle Dateien AUSSERHALB von
   `AlarmeTab.svelte` und den beiden Corridor-Bausteinen gilt der alte Vertrag unveraendert
   weiter: verschobene Zeilennummer = Befund, kein Nachtrag." Diese Ausnahme muss für S6e um
   `VersandTab.svelte` erweitert werden — sonst würde die durch die Prop-Erweiterung im
   Script-Teil (acht Wertprops + drei Legacy-Lesewerte + neun Rückrufe, alle **oberhalb** der
   Markup-Zeilen `:284`/`:294`/`:330`) verursachte Verschiebung fälschlich als Regression
   gemeldet. `/50` schreibt einen neuen Absatz nach dem S6c/S6d-Muster: „🔴 STAND S6e: der
   Zeilenzahl-Vertrag gilt zusätzlich NICHT für `VersandTab.svelte` — dort werden **0** Einträge
   gestrichen und **3** auf neue Zeilennummern nachgeführt, per `BLEIBT_MIT_INHALT` inhaltlich
   gefesselt." Anders als S6c (14/4) und S6d (6/22) verändert sich hier die Gesamtzahl **nicht**
   — alle drei Einträge sind Darstellungs-Zweige (Route/Vergleich-Weiche selbst), keiner ist ein
   reines `wiz`-Symptom, das entfernt werden könnte (siehe `/20-analyse`-Klärung 1). Die neuen
   Zeilennummern werden **in GREEN gemessen, nicht in dieser Spec vorweggenommen** (Muster S6d:
   RED setzt nur die Vertragserweiterung, GREEN trägt die gemessenen Nummern samt
   `BLEIBT_MIT_INHALT`-Bedingungstext nach).

6. **`versandVergleichSpeicherung.ts:221` bekommt bewusst KEINE neue `BLEIBT_MIT_INHALT`-Fesselung**
   (siehe Design-Entscheidung 4) — Parallel-Entscheidung zu `wertebereicheVergleichSpeicherung.ts:200`
   in S6d.

### Wirkort je Zusicherung

| Zusicherung | Wirkort | Warum |
|---|---|---|
| AC-1 (kein `wiz`/`CompareWizardState` mehr) | Kern — AST/Compile | Statischer Fakt |
| AC-2 (Wirkort-Guard: Self-Save-Effekt wirkt nur an Fläche B) | Kern — `effekteVon()`/`umgebungFuer()` | `$effect`-Rumpf, den SSR sonst verwirft — Muster `compare_alarme_wertprops.test.ts` AC-4 |
| AC-3 (alle drei Mounts speisen dasselbe Bündel, Aufrufform) | Kern — AST-Wächter | Mounts C/D sind in der CI-Ampel strukturell unbewacht (`versand-tab-vergleich.spec.ts` ist NICHT in `.github/ci_e2e_specs.txt`) |
| AC-4 (`sendEmail` bleibt eigenständig interaktiv, außerhalb der Brücke) | Kern — AST/Werte-Test | Statisch prüfbar: Bündel enthält `sendEmail`+Rückruf, Brücke `werte()` NICHT |
| AC-5 (drei tote Legacy-Felder überleben Rollback/Payload unverändert) | Kern — bestehende SSR-Modultests | Regressionsnetz, unverändert lauffähig, da `versandZustandsBruecke` dieselbe `VersandHydrationTarget`-Schnittstelle erfüllt |
| AC-6 (Ratsche bewusst gepflegt) | Kern — `node --test` | Struktur-, kein Verhaltensnachweis |
| AC-7 (Verhaltensgleichheit am Hub) | bestehende E2E, unverändert grün | `compare-versand-speichert-selbst.spec.ts` deckt bereits alle relevanten Abläufe ab — kein neuer Test nötig |
| AC-8 (Fläche A bleibt unverändert) | bestehende E2E, unverändert grün | `versand-tab.spec.ts` (Route-Kontext), Regressionsschutz ohne neue Spec |

### Reihenfolge (Implementation Note)

`versandPropsAus.ts` und `versandZustandsBruecke` zuerst (sonst kompiliert der Baustein-Umbau
nicht), dann `VersandTab.svelte`, dann die drei Elternteile
(`CompareTabs.svelte`/`CompareNewEditor.svelte`), zuletzt die Ratschen-Nachführung (braucht die
endgültigen Zeilennummern — RED schreibt die Vertragserweiterung, GREEN misst und trägt die drei
neuen Zeilennummern samt `BLEIBT_MIT_INHALT` nach). Die Scheibe bleibt unteilbar: die Brücke von
den `VersandTab.svelte`-Änderungen zu trennen hinterließe einen nicht kompilierenden
Zwischenstand.

## Expected Behavior

- **Input:** Im Reiter „Versand" des Ortsvergleichs (Hub `/compare/[id]` sowie Anlege-Desktop/
  -Mobil `/compare/new`) werden Briefing-Kanäle (E-Mail/Telegram/SMS) getoggelt, Morgen-/
  Abend-Zeitplan gesetzt, das Enddatum der Alarmierung gesetzt oder „Bis auf Weiteres" geklickt —
  wie heute.
- **Output:** Dieselbe sichtbare Auswahl, derselbe Speicherweg im Hub (ein PUT je Änderung über
  `versandVergleichSpeicherung`, Diff-Gate, Rollback), derselbe (persistenzlose) Email-Toggle,
  derselbe Dual-Write in den Wizard-Zustand beim Anlegen; keine nutzer-sichtbare
  Verhaltensänderung. Intern liest/schreibt `VersandTab` im Vergleichs-Zweig keine
  `wiz`-Referenz mehr, sondern ausschließlich Wertprops und Rückrufe; `wiz` und der Aufbau des
  Prop-Bündels liegen jetzt in den Elternteilen (`CompareTabs.svelte`, `CompareNewEditor.svelte`
  über `versandPropsAus`).
- **Side effects:** `versandVergleichSpeicherungAktiv({context, zustand, preset,
  saveController})` prüft `wiz`-Vorhandensein nicht mehr direkt, sondern über die Brücke
  `zustand` — semantisch identisch, weil `versandZustandsBruecke` an Fläche A/C/D entweder gar
  nicht gebaut wird oder ihre Werte über die Rückrufe genauso `undefined`/leer bleiben wie vorher
  `wiz`.

## Acceptance Criteria

- **AC-1 (`VersandTab` ist im Vergleichs-Zweig wertprop-rein):** Given `VersandTab.svelte` liest/
  schreibt heute `wiz` an den gemessenen Stellen (Prop `:55`, Zähler `:194`, Schreiber
  `:218-222`, Selbst-Speicher-Block `:271-291`, Markup `:330-373`) und importiert den Typ
  `CompareWizardState` (`:18`) / When der Vergleichs-Zweig auf acht Wertprops
  (`sendEmail`/`sendTelegram`/`sendSms`/`morningEnabled`/`morningTime`/`eveningEnabled`/
  `eveningTime`/`endDate`) + drei Legacy-Lesewerte + neun Rückrufe umgestellt wird / Then
  enthält die Datei keinen `wiz`-Zugriff und keinen `CompareWizardState`-Typ-Import mehr.
  - Test: Kern — AST-Scan in `compare_versand_wertprops.test.ts` (Muster AC-1 aus
    `compare_alarme_wertprops.test.ts`): kein `wiz`- und kein `CompareWizardState`-Identifier
    mehr im Instanz-Skript; die Prop-Schnittstelle bindet alle elf freigegebenen Namen.

- **AC-2 (Wirkort-Guard: der Selbst-Speicher-Effekt wirkt nur an Fläche B):** Given
  `vergleichSpeicherung` entsteht nur, wenn `versandVergleichSpeicherungAktiv({context, zustand,
  preset, saveController})` wahr ist / When der Effekt-Rumpf über `effekteVon()` an den
  negativen Orten (Fläche A Trip, Fläche C/D Anlegen mit `preset: null`/`saveController: null`)
  wirklich ausgeführt wird / Then bleibt der Rumpf dort wirkungslos (kein
  `aenderungMelden()`-Aufruf), und am positiven Ort (Fläche B, `preset`+`saveController`
  gesetzt) wirkt er.
  - Test: Kern — `compare_versand_wertprops.test.ts`, Muster `compare_alarme_wertprops.test.ts`
    AC-4 (`umgebungFuer()`/`effekteVon()`).
  - Mutations-Gegenprobe: `versandVergleichSpeicherungAktiv` auf `() => false` verfälschen ⇒ der
    Effekt wirkt nirgends mehr, auch nicht am positiven Ort ⇒ Test wird rot (Positiv-Gegenprobe);
    auf `() => true` verfälschen ⇒ der Effekt wirkt an den negativen Orten weiter ⇒ Test wird rot
    (Negativ-Gegenprobe). Kein E2E-Test fängt diese Mutation, weil nur der Hub browserseitig
    geprüft wird und dort die Bedingung strukturell immer erfüllt ist.

- **AC-3 (alle drei Vergleichs-Mounts speisen dasselbe Bündel ein, Aufrufform geprüft):** Given
  Mount (B) `CompareTabs.svelte:1070`, Mount (C) `CompareNewEditor.svelte:407`, Mount (D)
  `CompareNewEditor.svelte:493` übergeben heute `wiz`/`{wiz}` / When alle drei Mounts auf
  `{...versandPropsAus(wiz)}` umgestellt werden / Then rendern an allen drei Mounts weiterhin
  alle Bedienelemente, für die `versandPropsAus` einen Rückruf liefert, UND
  `versandPropsAus(wiz)` steht im Markup-Ausdruck selbst (nicht in einer Skript-Variable
  gehoben).
  - Test: Kern — AST-Wächter in `compare_versand_wertprops.test.ts`, der über alle drei
    Vergleichs-Mounts prüft, dass `versandPropsAus(wiz)` als Spread-Ausdruck im Markup-Knoten
    selbst aufgerufen wird und keine der elf Prop-Bindungen fehlt. `versand-tab-vergleich.spec.ts`
    (Mounts C/D) ist NICHT in `.github/ci_e2e_specs.txt` — ohne diesen Kern-Wächter liefe eine
    Regression an Fläche C/D grün durch die CI-Ampel (F001-Lehre aus S6b/S6c/S6d).
  - Mutations-Gegenprobe: `{...versandPropsAus(wiz)}` in eine Skript-Variable
    `const versandProps = versandPropsAus(wiz)` heben und `{...versandProps}` spreaden ⇒ dieser
    Wächter wird rot (ein reines Werte-Diff bliebe grün, weil die Werte selbst korrekt sind — nur
    ihre Reaktivität bricht, was erst im Browser sichtbar würde).

- **AC-4 (`sendEmail` bleibt eigenständig interaktiv, außerhalb der Speicherweg-Brücke):** Given
  `wiz.sendEmail` wird heute über eine klickbare Checkbox (`VTBriefingChannels.svelte:127`)
  gelesen (`:335`) und geschrieben (`:339`, `makeWizChannelHandler('sendEmail')`), fließt aber
  NIE in `VersandSnapshot`/die Nutzlast ein / When `versandPropsAus` `sendEmail` +
  `onSendEmailChange` als eigenständiges Paar bündelt, das `wiz.sendEmail` direkt schreibt / Then
  bleibt die Checkbox interaktiv (Wert reflektiert `sendEmail`, `vergleichActiveChannelCount`
  zählt sie mit), UND `versandSnapshotAus`/`baueVersandNutzlast` sehen das Feld weiterhin nicht
  (`versandZustandsBruecke`s `werte()` enthält `sendEmail` NICHT).
  - Test: Kern — `compare_versand_wertprops.test.ts`: Bündel-Test prüft, dass `sendEmail` +
    `onSendEmailChange` im Rückgabewert von `versandPropsAus` stehen; separater Test ruft
    `versandZustandsBruecke` auf und prüft, dass `Object.keys`/`get`-Zugriffe auf `sendEmail`
    NICHT über die zehn Snapshot-relevanten Felder laufen (Abwesenheits-Zusicherung, Muster
    `compare_alarme_wertprops.test.ts` AC-6-Äquivalenzbeweis).
  - Mutations-Gegenprobe: `sendEmail` versehentlich zusätzlich in `versandZustandsBruecke`s
    `werte()` aufnehmen ⇒ dieser Abwesenheits-Test wird rot, auch wenn alle anderen Tests grün
    blieben (das Feld würde im Diff-Gate mitverglichen, ohne dass ein Payload-Feld existiert —
    ein Fehler, den kein bestehender Test heute fängt, weil `sendEmail` bisher hart an `wiz`
    hing).

- **AC-5 (drei tote Legacy-Restfelder überleben Rollback und Payload unverändert):** Given
  `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` haben kein Bedienelement im
  Versand-Reiter, müssen aber weiter durch Snapshot/Payload/Rollback laufen (S5 AC-11,
  BUG-DATALOSS-GR221-Klasse) / When sie als Wertprops ohne eigenen Rückruf gebündelt werden und
  nur über `onVersandFeldSetzen` (Rollback-Senke) beschreibbar sind / Then sendet
  `baueVersandNutzlast` weiterhin alle drei Felder mit dem aktuellen Wert, und
  `rollbackVersandSnapshot` schreibt bei einem gescheiterten PUT über `onVersandFeldSetzen`
  zurück auf `wiz.<feld>`.
  - Test: bestehende SSR-Modultests von `versandVergleichSpeicherung.ts` (Regressionsnetz) laufen
    ohne inhaltliche Änderung grün — sie instanziieren `VersandHydrationTarget`-kompatible
    Objekte und prüfen deren Verhalten, nicht die Quelle der Referenz.
  - Mutations-Gegenprobe: die drei Legacy-Felder aus `versandZustandsBruecke`s `werte()`
    entfernen ⇒ `baueVersandNutzlast` sendet `undefined` für sie ⇒ ein bestehender S5-Test
    (AC-11, Reload-Überleben aller übrigen Felder) wird rot.

- **AC-6 (Ratsche bewusst gepflegt — Strukturwächter, kein Verhaltensnachweis):** Given
  `context_herkunft_zweige_eingefroren.test.ts` hält heute `VersandTab.svelte:284/294/330` als
  drei positionsstrikte Einträge, `EINGEFROREN_SOLL_ANZAHL = 47` / When im selben Commit wie der
  Umbau die drei Einträge auf ihre neu gemessenen Zeilennummern nachgeführt und per
  `BLEIBT_MIT_INHALT` mit wortgleichem Bedingungstext gefesselt werden, der Kommentarblock um die
  Versand-Ausnahme vom Zeilenzahl-Vertrag erweitert wird und `EINGEFROREN_SOLL_ANZAHL` bei 47
  bleibt / Then ist der Ratschen-Test grün, und `versandVergleichSpeicherung.ts:221` bleibt
  unverändert an seiner Position (ohne neue Fesselung).
  - Test: Kern — `node --test` auf `context_herkunft_zweige_eingefroren.test.ts`.
  - 🔴 Diese AC ist ein **Strukturwächter**, kein Verhaltensnachweis: die Zusicherung ist nicht
    „das Programm verhält sich richtig", sondern „die Zahl und Lage der HERKUNFT-Verzweigungen
    ist die, die diese Scheibe bewusst herbeigeführt hat".
  - Mutations-Gegenprobe: einen der drei nachgeführten Einträge zusätzlich aus `EINGEFROREN`
    streichen, ohne die zugehörige Bedingung im Quelltext zu entfernen ⇒ der reale Zählbefehl
    liefert den Eintrag weiterhin, der Mengenvergleich schlägt fehl. Zusätzlich: einen
    `BLEIBT_MIT_INHALT`-Eintrag auf eine fremde, tatsächlich existierende Zeile im
    8-Zeilen-Fenster setzen, ohne den Bedingungstext anzupassen ⇒ die `zeile`-Prüfung schlägt
    fehl.

- **AC-7 (Verhaltensgleichheit am Hub, bestehender E2E-Nachweis):** Given
  `compare-versand-speichert-selbst.spec.ts` deckt heute Morgen-Zeit-Änderung (ein PUT), „Bis auf
  Weiteres", Reiterwechsel-Flush mit Alarme, Konflikt-Handling, Pausieren und Reload-Überleben ab
  / When `VersandTab` im Hub-Mount auf `versandPropsAus(wizardState)` umgestellt wird / Then
  bleibt die Spec ohne Änderung grün.
  - Test: Live-E2E — `frontend/e2e/compare-versand-speichert-selbst.spec.ts` (bereits in
    `.github/ci_e2e_specs.txt`), keine neue Datei.

- **AC-8 (Fläche A bleibt vollständig unverändert):** Given die Tour (`/trips/[id]`) hat heute
  keinen `compare-wizard-state`-Context, `wiz` ist dort nie gesetzt, der Speicherweg läuft über
  `saveController` / When `VersandTab` auf Wertprops umgestellt wird, ohne dass sich an Mount (A)
  etwas ändert (`BriefingScheduleTab.svelte:130` reicht weiterhin nur
  `trip`/`onTripUpdate`/`saveController`/`reportConfig`/`onJump` durch) / Then bleibt das
  Verhalten der Tour identisch.
  - Test: bestehende E2E `frontend/e2e/versand-tab.spec.ts` bleibt ohne Änderung grün — reiner
    Regressionsnachweis, keine neue Spec nötig.

## Known Limitations

- **Doppelquelle als Dauerzustand ist verboten.** „Wertprop wenn da, sonst `wiz`" ist genau das
  Anti-Muster, das S6 beseitigen soll. Die Umstellung ist an allen drei Vergleichs-Mounts
  vollständig oder unterbleibt.
- **`sendEmail` bleibt persistenzlos.** Der Toggle wirkt nur innerhalb der Sitzung (kein
  `send_email`-Feld auf `ComparePreset`) — eine vorbestehende Known Limitation (S7-Freigabe,
  `hydrateVersandFieldsFromPreset`-Kommentar), die diese Scheibe unverändert weiterträgt, nicht
  behebt.
- **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only` zurück** —
  `/70-deploy` überspringt dann die gesamte Staging-Validierung. Nach **jedem** Commit dieser
  Scheibe gegenlesen.
- **Mounts C/D sind in der CI-Ampel strukturell unbewacht** (`versand-tab-vergleich.spec.ts`
  nicht in `.github/ci_e2e_specs.txt`) — deshalb trägt AC-3 den Nachweis im Kern statt in einer
  weiteren E2E-Spec.
- **`versandVergleichSpeicherung.ts:221` behält seine Position ohne neue `BLEIBT_MIT_INHALT`-
  Fesselung** (Design-Entscheidung 4/6) — ihr Schutz bleibt der alte, positionsbasierte Vertrag.
  Eine künftige Scheibe, die diese Zeile erneut inhaltlich ändert, MUSS erneut prüfen, ob eine
  Fesselung inzwischen nötig geworden ist.
- **Die konkreten neuen Zeilennummern für `VersandTab.svelte:284/294/330`-Nachfolger stehen erst
  nach GREEN fest** — diese Spec legt nur die Vertragserweiterung und die Bilanz (0/3) fest, wie
  bei S6d.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Wertprops + Rückrufe statt `wiz` ist mit `CompareOutlookLayoutControls`
  (#1720 S1), `CompareHourlyLayoutControls` (S6b, live `8207c157`), `AlarmeTab` (S6c, live
  `c737159e`) und `CorridorEditor(Mobile)` (S6d, live `930ccdc0`) bereits entschieden und
  produktiv erprobt — diese Scheibe wendet dasselbe, bereits akzeptierte Muster auf den
  Versand-Organismus an und trifft keine neue Architekturentscheidung. Die Bündel-Funktion
  `versandPropsAus(wiz)`, der Proxy-Adapter `versandZustandsBruecke` und die Drei-Feldklassen-
  Unterscheidung (Design-Entscheidung 2) sind lokale Umsetzungsentscheidungen innerhalb dieses
  Musters, kein Architekturwechsel.

## Changelog

- 2026-09-22: Initial spec created (Scheibe S6e von #2276, Epic #2345)
