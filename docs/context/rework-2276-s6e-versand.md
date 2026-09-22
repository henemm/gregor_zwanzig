# Context: rework-2276-s6e-versand

**Issue:** #2276 (Epic #2345) · **Scheibe:** S6e — Versand-Fläche des Ortsvergleichs auf Wertprops
**Erhoben:** 2026-09-22 · Basis `930ccdc0` (== `origin/main`, S6d live)

## Request Summary

Die geteilte Versand-Fläche (`shared/VersandTab.svelte`, `context="route"|"vergleich"`) liest
und schreibt im Vergleichs-Zweig direkt auf dem Wizard-Store `wiz` (`CompareWizardState`) —
sowohl in den drei eingebetteten Organismen (`VTBriefingChannels`, `VTSchedulePlan`,
`VTLaufzeitVergleich`) als auch im eigenen Selbst-Speicherweg (`versandVergleichSpeicherung.ts`,
S5). S6e stellt diese Fläche — nach dem in S6b/S6c/S6d erprobten Muster — auf explizite
Wertprops plus Callbacks um; der `wiz`-Zugriff verschwindet dabei nicht, er **wandert zum
Elternteil hoch**. Verhalten bleibt unverändert (verhaltensneutraler Umbau, kein Feature).

## Ticket-Zusicherungen (Fassung #2276, gelten wortgleich für S6e)

- **AC-1**: Änderung im Hub ⇒ der Organismus persistiert selbst (ein PUT, `SaveIndicator`
  „✓ Gespeichert"), ohne `compare-wizard-state`-Context. Gilt bereits seit S5 — S6e darf das
  nicht brechen.
- **AC-2** (Zahl der `context ===`-Zweige) ist in der Ticket-Fassung unerfüllbar; prüfbare
  Neufassung seit S6a: „keine HERKUNFT-Zweige" (= kein Lesen/Schreiben von `wiz.*` oder
  Compare-Store-Typen), Darstellung/Fachlogik-Zweige (`context === 'route' | 'vergleich'` als
  Markup-Weiche) bleiben erlaubt.
- **AC-3**: Zwei Reiter kurz nacheinander ⇒ keine Änderung geht verloren (Rollback-Schutz für
  geteilte Felder `sendTelegram`/`sendSms` mit Alarme, S5-Erbe).
- **AC-4**: `compareHubWizardBridge` ohne produktiven Importeur (Bilanz erst in S6f — hier nur
  beobachten, nicht anfassen).

## Die drei Einbettungen — Speicherweg nur im Hub aktiv

| Mount | Datei:Zeile | Fläche | Props heute | Speicherweg aktiv? |
|---|---|---|---|---|
| (A) Route | `trip-detail/BriefingScheduleTab.svelte:130` | `/trips/[id]` | `trip`-basiert, kein `wiz` | ja (Trip-Weg, unverändert) |
| (B) Hub | `compare/CompareTabs.svelte:1070-1079` | `/compare/[id]` | `wiz={wizardState}`, `activation`, `preset`, `saveController`, `enqueueHubWrite`, `onCompareUpdate` | **ja — einziger** |
| (C) Anlegen Desktop | `compare-new/CompareNewEditor.svelte:407` | `/compare/new` | nur `wiz`, `activation` | nein |
| (D) Anlegen Mobil | `compare-new/CompareNewEditor.svelte:493` | `/compare/new` | nur `wiz`, `activation` | nein |

**Kernbefund für den Schnitt — identisch zu S6c:** Die Verdrahtung ist dreifach (B/C/D), der
Speicherweg einfach (nur B). (C)/(D) übergeben weder `preset` noch `saveController`;
`versandVergleichSpeicherungAktiv()` (`versandVergleichSpeicherung.ts:215`) lässt
`erstelleVersandVergleichSpeicherung` dort nie entstehen, der Save-`$effect`
(`VersandTab.svelte:283-291`) bricht sofort ab (`AC-9`/`AC-12` der S5-Spec). In (C)/(D) kommt
`wiz` aus `getContext('compare-wizard-state')`, in (B) aus einer lokalen Instanz. Persistenz der
Anlege-Seite läuft gesammelt über `wiz.saveNewPreset()`, ausserhalb von `VersandTab`.

## `wiz`-Zugriffe in `VersandTab.svelte` — alle im Baustein selbst

Datei `frontend/src/lib/components/shared/VersandTab.svelte` (400 Zeilen):

| Zeile(n) | Zugriff | Zweck |
|---|---|---|
| `55` | `wiz?: CompareWizardState` (Prop-Typ) | Import `compare/compareWizardState.svelte.ts` |
| `194` | `wiz ? [wiz.sendEmail, wiz.sendTelegram, wiz.sendSms]...` | Kanal-Zähler für Leerzustand |
| `218-222` | `makeWizChannelHandler(field)` → `wiz[field] = ...` | Kanal-Checkbox-Schreiber (3 Kanäle) |
| `271-291` | Self-Save-Block: `versandVergleichSpeicherungAktiv({context, wiz, preset, saveController})`, `erstelleVersandVergleichSpeicherung({wiz: wiz!, ...})`, `versandSnapshotAus(wiz)` | Speicherweg-Erzeugung + reaktives Melden (10 Felder) |
| `330-373` (Markup) | `wiz?.sendEmail/sendTelegram/sendSms/morningEnabled/morningTime/eveningEnabled/eveningTime/endDate`, Inline-Schreiber `if (wiz) wiz.X = v` (4×) | Werte + Schreiber für `VTBriefingChannels`, `VTSchedulePlan`, `VTLaufzeitVergleich` |

**Nicht `wiz`-gebunden, bereits Wertprops:** `VTSchedulePlan.svelte` und `VTBriefingChannels.svelte`
nehmen schon reine Value+Callback-Props (kein `wiz`-Import) — die beiden ratschen-eingefrorenen
`context === 'vergleich'`-Zweige dort (`VTSchedulePlan.svelte:55` Intro-Copy, `:83` fehlende
Mehrtages-Trend-Karte, KL-2 „kein `multi_day_trend`-Feld am `ComparePreset`") sind fachlich und
bleiben unverändert.

## Referenzmuster: `alarmZustandsBruecke` (S6c) — direkt übertragbar

`shared/alarmeVergleichSpeicherung.ts:184` löst exakt dasselbe Problem, das S6e hat: der
Selbst-Speicherweg (`erstelleAlarmeVergleichSpeicherung`, `alarmSnapshotAus`) erwartet ein
`wiz`-förmiges Objekt (`AlarmHydrationTarget`, alle Felder optional, Getter/Setter), bekommt aber
seit S6c nur noch Plain-Props + einen `onAlarmFeldSetzen(feld, wert)`-Callback:

```ts
export function alarmZustandsBruecke(
  werte: () => Record<string, unknown>,
  setzen?: (feld: string, wert: unknown) => void
): AlarmHydrationTarget {
  return new Proxy({} as AlarmHydrationTarget, {
    get: (_ziel, feld) => werte()[PROP_JE_FELD[feld as string] ?? (feld as string)],
    set: (_ziel, feld, wert) => { setzen?.(feld as string, wert); return true; }
  });
}
```

`PROP_JE_FELD` übersetzt nur dort, wo Snapshot-Feldname und Prop-Name auseinanderlaufen
(`officialAlertsEnabled` → `amtlicheWarnungenImBericht` u.a.). `AlarmeTab.svelte:439-450` baut die
Brücke aus einem Getter (liest alle relevanten `$state`/Prop-Werte frisch) und reicht sie unter
dem Namen `zustand` (statt `wiz`) an `erstelleAlarmeVergleichSpeicherung` durch —
`AlarmeVergleichSpeicherungOptionen.zustand: AlarmHydrationTarget` ersetzt dort das frühere
`wiz`-Feld 1:1, keine andere Umbenennung im Modul nötig.

`corridor-editor/wertebereicheVergleichSpeicherung.ts:217` hat dieselbe Brücke für S6d gebaut —
dort **ohne** Namensumleitung, weil Snapshot- und Prop-Namen dort bereits übereinstimmen. Bei
Versand stimmen Snapshot (`VersandSnapshot`/`VersandHydrationTarget` in
`versandVergleichSpeicherung.ts:35-59`) und die künftigen Prop-Namen ebenfalls überein
(`sendTelegram`, `sendSms`, `morningEnabled`, `morningTime`, `eveningEnabled`, `eveningTime`,
`endDate`) — **keine Namensumleitung nötig**, analog zu S6d, nicht zu S6c.

**Sonderfall `sendEmail` — KORRIGIERT (war falsch angenommen, siehe `/20-analyse`):**
`VersandSnapshot`/`VersandHydrationTarget` enthalten `sendEmail` NICHT (Kommentar
`versandVergleichSpeicherung.ts:26-27`: `ComparePreset` kennt kein `send_email`-Feld). Das
bedeutet aber NICHT, dass die Checkbox hartcodiert werden darf: `VersandTab.svelte:335`
liest `wiz?.sendEmail ?? false` **reaktiv**, `:339` schreibt per `onEmailChange` echt zurück auf
`wiz.sendEmail`, und `VTBriefingChannels.svelte:127` rendert eine **klickbare** Checkbox
(`onchange={onEmailChange}`). `wiz.sendEmail` wird zwar nie in die Nutzlast gespreadet (bleibt
beim nächsten Laden/Hydrieren stets `true`, `hydrateVersandFieldsFromPreset:80`) — der Toggle
ist also persistenzlos, aber innerhalb der Sitzung real interaktiv und speist
`vergleichActiveChannelCount` (`:193-195`). **Verhaltensneutralität verlangt: `sendEmail` bleibt
Wertprop + eigener `onSendEmailChange`-Rückruf, der `wiz.sendEmail` direkt schreibt — AUSSERHALB
der Brücke** (sonst sähe `versandSnapshotAus` ein Feld, das `baueVersandNutzlast` gar nicht
kennt). Damit gibt es **drei Feldklassen**, nicht zwei: (1) die 7 Snapshot-Felder mit
Wertprop+Callback+Brücken-Mitgliedschaft, (2) `sendEmail` mit Wertprop+Callback, aber OHNE
Brücken-Mitgliedschaft, (3) die drei toten Legacy-Felder mit Wertprop OHNE eigenen Callback, nur
über `onVersandFeldSetzen` in der Brücke beschreibbar.

**Drei tote Legacy-Restfelder** (`alertCooldownMinutes`, `alertQuietFrom`, `alertQuietTo`, Teil
von `VersandSnapshot`) haben **kein Bedienelement im Versand-Reiter** (Alert-Zustellung zog in
#1258 S4 nach `AlarmeTab.svelte` um) — sie müssen aber weiter durch Snapshot/Bridge laufen, sonst
nullt der nächste Versand-PUT die Alarm-Zustellungsfelder (`baueVersandNutzlast` Kommentar
`versandVergleichSpeicherung.ts:118-135`, AC-11 der S5-Spec). Die Brücke braucht dafür KEIN
Bedienelement-Prop — sie kann diese drei Felder aus dem gleichen Zustand lesen wie die
Alarme-Brücke sie schreibt (geteiltes `wiz`-Feld, Rollback-Schutz AC-3). **Zu klären in
`/20-analyse`:** woher die Brücke diese drei Werte bezieht, wenn `VersandTab` selbst keinen
Lese-/Schreibzugriff mehr auf sie braucht — vermutlich als reiner Getter-Prop ohne Setter
(read-only Pass-Through), analog zu `officialAlertsEnabled` in `alarmZustandsBruecke`
(Persistenzwert ohne eigenes Bedienelement im jeweiligen Reiter).

## Referenzmuster: `xxxPropsAus.ts` (S6c/S6d) — Bündelung an den drei Mounts

`compare/alarmePropsAus.ts` und `compare/corridorPropsAus.ts` bauen aus `wiz` (bzw. einer
strukturellen Teilsicht `AlarmeZustandsQuelle`/`CorridorZustandsQuelle`, NICHT
`CompareWizardState` selbst — läuft auch gegen den hydrierten Plain-Zustand der Hub-Brücke) ein
Objekt aus Werten + `onXChange`-Callbacks, das an allen drei Vergleichs-Mounts identisch per
`{...alarmePropsAus(wiz)}` im Markup-Ausdruck gespreizt wird — **niemals** in einer
Skript-Variable vorberechnet (SSR-Prüfstand + AST-Wächter sähen sonst nichts,
[[reference_pruefstand_ohnetypen_frisst_die_klammer_bei_cast]]-Nachbarlehre zur Aufrufform).
`preset`/`saveController`/`enqueueHubWrite`/`onCompareUpdate`/`activation` bleiben separate,
explizite Props an jedem Mount (nur am Hub-Mount B tatsächlich gesetzt) — sie gehören NICHT ins
Bündel.

Für S6e: `compare/versandPropsAus.ts` mit `VersandZustandsQuelle` (Teilsicht:
`sendEmail?`, `sendTelegram?`, `sendSms?`, `morningEnabled?`, `morningTime?`, `eveningEnabled?`,
`eveningTime?`, `endDate?` — die drei toten Restfelder gehören NICHT ins UI-Bündel, nur in die
Speicherweg-Brücke, siehe oben) + 8 `onXChange`-Callbacks (7 Snapshot-Felder + `sendEmail`, das
NICHT über die Brücke läuft, siehe Korrektur oben), die `wiz.<feld> = wert` schreiben, plus
`onVersandFeldSetzen` als Rollback-Senke für die drei toten Felder.

## Ratschen-Stand (vor S6e)

`shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`, `EINGEFROREN_SOLL_ANZAHL = 47`.
Für S6e relevante Einträge (Auszug):

```
'VersandTab.svelte:284',
'VersandTab.svelte:294',
'VersandTab.svelte:330',
'versandVergleichSpeicherung.ts:221',
'versand-tab/VTSchedulePlan.svelte:55',
'versand-tab/VTSchedulePlan.svelte:83',
```

`:284`/`:294`/`:330` sind die Markup-Weiche `{#if context === 'route'} … {:else if context ===
'vergleich'}` selbst — bleibt als Darstellungs-Zweig erlaubt (zwei verschiedene UI-Bäume:
`VTLaufzeitRoute` vs. `VTLaufzeitVergleich`), analog zu den 4 überlebenden AlarmeTab-Einträgen in
S6c. `versandVergleichSpeicherung.ts:221` ist die `context === 'vergleich'`-Prüfung in
`versandVergleichSpeicherungAktiv()` — bleibt (Erzeugungsbedingung, fachlich, kein `wiz`-Zugriff
an sich). Die beiden `VTSchedulePlan.svelte`-Einträge bleiben unverändert (siehe oben, bereits
Wertprops, nur Darstellungs-Unterschied). **Erwartung: die Zahl 47 sinkt in S6e nicht zwangsläufig
auf 0 neue Streichungen** — anders als in S6c/S6d ist hier ggf. **keine** Zeile aus der Liste
entfernbar, weil alle sechs Einträge bereits fachlich/darstellungsbedingt sind, nicht
`wiz`-Zugriffs-Symptome. Zu prüfen in `/20-analyse`: ob nach dem Umbau ALLE bisherigen
`wiz`-Symptomzeilen (die oben aufgeführten `VersandTab.svelte`-Zeilen 55/194/218-222/271-291/
330-373, die NICHT in der Ratsche stehen, weil sie unter der Zählmethode nicht als
„context ===“-Treffer zählen, sondern als reine `wiz.*`-Zugriffe) verschwinden — der Zählbefehl
(`docs/reference/gates_und_ratschen.md`) zählt vermutlich nur `context ===`/`context===`-Literale,
nicht jeden `wiz.*`-Zugriff. **Klären in `/20-analyse`: was genau der Zählbefehl misst**, damit
die Spec keine falsche Ziel-Zahl verspricht.

## Betroffene Testdateien (grob, ~18 Dateien mit `wiz`/`VersandTab`-Bezug)

Alle mounten `VersandTab` mit `wiz={...}` bzw. `{wiz}` und werden nach dem Umbau auf die neuen
Props umgestellt werden müssen (Kern-Layer, keine Live-Tests):

`shared/__tests__/alarme_delivery_consolidated_save.test.ts`,
`alarme_vergleich_flush_beim_reiterwechsel.test.ts`, `alarme_vergleich_kein_zurueckschreiben.test.ts`,
`legacy_wizard_removed.test.ts`, `versand_speicherung_nur_im_vergleich_hub.test.ts`,
`versand_vergleich_konflikt_nochmal_speichern.test.ts`, `versand_nutzlast_reicht_keepalive_durch.test.ts`,
`versand_vergleich_speichert_selbst.test.ts`, `versand_tab_meldet_aenderungen_reaktiv.test.ts`,
`versand_enddatum_ohne_ereignis_bleibt_wirksam.test.ts`, `versand_tab_laedt_keine_compare_klebeschicht.test.ts`,
`versand_vergleich_reiterwechsel_verliert_nichts.test.ts`, `versand_nutzlast_verliert_keine_daten.test.ts`,
`versand_vergleich_flush_vor_pausieren.test.ts`; `compare/__tests__/compare_hub_wizard_bridge.test.ts`,
`hub_put_queue.test.ts`, `hub_versand_inline.test.ts`, `versand_panel_ohne_wrapper_div.test.ts`,
`totcode_rueckbau_speicherweg.test.ts`, `issue_683_wizard_remove.test.ts`.

`versand_tab_laedt_keine_compare_klebeschicht.test.ts` ist vermutlich die AC-4/AC-8-analoge
Ratsche (kein `compareHubWizardBridge`-Import zur Laufzeit) — Pendant zu
`alarme_tab_laedt_keine_compare_klebeschicht.test.ts` aus S6c, prüfen ob sie schon existiert oder
in S6e neu entsteht.

## Dependencies

- **Upstream:** `compare/compareWizardState.svelte.ts` (`CompareWizardState`-Klasse, Felder
  `sendEmail/sendTelegram/sendSms/morningEnabled/morningTime/eveningEnabled/eveningTime/endDate`
  + die drei Legacy-Restfelder), `versandVergleichSpeicherung.ts` (Snapshot/Payload/Rollback,
  unverändert in der Kernlogik), `versand-tab/mergeReportConfig.ts` (Route-Zweig, unberührt).
- **Downstream:** `compare/CompareTabs.svelte` (Hub-Mount), `compare-new/CompareNewEditor.svelte`
  (2 Anlege-Mounts, Desktop+Mobil).

## Risiken & Besonderheiten

- **Reaktiver `$effect` (S5-Lehre):** Der Self-Save-`$effect` (`VersandTab.svelte:283-291`) ist
  SSR-only in der Kern-Harness nicht beobachtbar (`generate: 'server'`, kein DOM) — jede Änderung
  an der Bridge-Konstruktion braucht einen Staging-Browserlauf, nicht nur Kern-Tests
  ([[reference_bausteintest_beweist_die_verdrahtung_nicht]]).
- **`endDate`-Sonderfall (S5-Lehre):** „Bis auf Weiteres" mutiert `endDate` ohne
  `change`/`focusout`-Ereignis — der Snapshot-Vergleich in `versandSnapshotAus` und die neue
  Brücke müssen `endDate` weiterhin ohne Ereignis-Trigger sehen (AC-5 der S5-Spec).
- **Geteilte Felder mit Alarme (`sendTelegram`/`sendSms`):** Der diff-basierte Rollback
  (`rollbackVersandSnapshot`) darf durch die Bridge-Umstellung nicht plötzlich unbedingt
  überschreiben — Rollback schreibt aktuell direkt in `state` (künftig: über den Bridge-Setter,
  der wiederum den `onXChange`-Callback aufruft, der wiederum `wiz.X = v` schreibt — Kette prüfen).
- **Drei tote Legacy-Restfelder:** siehe oben, Klärungspunkt für `/20-analyse`.
- **Ratschen-Zähllogik:** siehe oben, Klärungspunkt für `/20-analyse` — ob 47 sinkt, gleich
  bleibt oder wie in S6b (Ratsche 68→67) leicht sinkt.

## Analysis

### Type
Refactor (verhaltensneutraler Umbau), kein Feature — analog S6c/S6d.

### Klärung 1: Ratschen-Zähllogik (`context_herkunft_zweige_eingefroren.test.ts`)
Der Zählbefehl (`docs/reference/gates_und_ratschen.md:322-323`) ist
`grep -rn 'context ===\|context !=='` unter `shared/` — er zählt **ausschließlich** die
literale Verzweigung, nicht `wiz.*`-Zugriffe. Die drei in `VersandTab.svelte` verbleibenden
`context ===`-Treffer (284/294/330, Markup-Weiche Route/Vergleich) sind Darstellungs-Zweige und
bleiben nach S6e bestehen — sie sind kein `wiz`-Symptom. **Erwartung für die Spec: die Zahl 47
sinkt durch S6e nicht** (anders als S6b/S6c/S6d, wo tatsächlich Zeilen entfernbar waren). Das ist
kein Fehlschlag der Scheibe — der eigentliche Fortschritt zeigt sich am Verschwinden der
`wiz`-Zugriffe (Zeilen 55/194/218-222/271-291/330-373), die die Ratsche nie gezählt hat, weil sie
keine `context ===`-Literale sind. Die Spec darf keine Zielzahl < 47 versprechen.

### Klärung 2: Die drei toten Legacy-Restfelder in der Brücke
Exaktes Vorbild gefunden: `alarmePropsAus.ts:129-131` — `onAlarmFeldSetzen(feld, wert)` ist
dort bereits eine **reine Rollback-Senke** für Felder ohne eigenes Bedienelement
(Kommentar dort: „KEIN Bedienelement schreibt hierüber"). Gleiches Muster für S6e:
- `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` werden in `versandPropsAus.ts` als
  reine Lesewerte aus `wiz` gebündelt (kein UI-Bedienelement in `VersandTab`, Delivery-Sektion
  liegt seit #1258 S4 in `AlarmeTab.svelte`).
- Ein generischer Rückruf `onVersandFeldSetzen(feld, wert)` (analog `onAlarmFeldSetzen`) schreibt
  `wiz[feld] = wert` — einziger Schreibweg für diese drei Felder, ausgelöst ausschließlich vom
  diff-basierten `rollbackVersandSnapshot` (nie von einer Geste).
- Damit braucht `versandZustandsBruecke` (neu, analog `corridorZustandsBruecke`/
  `alarmZustandsBruecke`) für ALLE 10 Snapshot-Felder denselben Proxy-Mechanismus — keine
  Sonderbehandlung nötig, die drei toten Felder unterscheiden sich nur darin, dass kein
  Bedienelement ihren `onXChange` aufruft.

### Namensumleitung: keine nötig
Snapshot-Feldnamen (`sendTelegram`, `sendSms`, `morningEnabled`, `morningTime`,
`eveningEnabled`, `eveningTime`, `endDate`, plus die drei Legacy-Felder) sind identisch zu den
künftigen Prop-Namen — wie S6d (`corridorZustandsBruecke`), nicht wie S6c
(`PROP_JE_FELD`-Umleitung für `officialAlertsEnabled`↔`amtlicheWarnungenImBericht`).

### Korrektur nach Advisor-Gegenprobe: Ratsche IST betroffen (nicht „KEINE ÄNDERUNG")

`context_herkunft_zweige_eingefroren.test.ts` prüft NICHT nur die Zahl 47, sondern eine
benannte `Datei:Zeile`-Liste, teils zusätzlich inhaltlich gefesselt (`BLEIBT_MIT_INHALT`). Die
Datei kennt zwei verschiedene Verträge:

- **Positionsstrikt** (Default, gilt für alle Dateien außerhalb `AlarmeTab.svelte` und den
  beiden Corridor-Bausteinen): „verschobene Zeilennummer = Befund, kein Nachtrag". Das betrifft
  `versandVergleichSpeicherung.ts:221` — Auflage A1 unten sorgt dafür, dass diese Zeile
  UNVERÄNDERT an Position 221 bleibt (nur Inhalt `!!p.wiz`→`!!p.zustand`, analog
  `wertebereicheVergleichSpeicherung.ts:200`, dort ausdrücklich ohne Fesselung erlaubt).
- **Nachführbar mit Inhalts-Fesselung** (bisher nur für S6c/AlarmeTab und S6d/Corridor
  freigegeben): Zeilennummer darf sich verschieben, wenn der Eintrag zusätzlich in
  `BLEIBT_MIT_INHALT` mit wortgleichem Bedingungstext + Kontext-Anker gefesselt wird.

**`VersandTab.svelte:284/294/330` fallen NICHT unter die zweite Kategorie** — sie stehen im
Template-Teil (Markup-Weiche `{#if context === 'route'} … {:else if context === 'vergleich'}`),
der Umbau fügt aber im SCRIPT-Teil davor (Props-Interface, Wegfall `wiz`, neue
`versandZustandsBruecke`-Konstruktion) voraussichtlich mehr Zeilen hinzu als er entfernt — die
drei Zeilennummern verschieben sich fast sicher nach unten. Das macht den Waechter **rot**, wenn
die Spec keine neue Ausnahme schafft.

**Für S6e nötig (Ergänzung zur Spec, drittes Beispiel nach S6c/S6d):** Ein neuer 🔴
VERTRAG-Absatz an `context_herkunft_zweige_eingefroren.test.ts`, der `VersandTab.svelte`
zusätzlich in die nachführbare Kategorie aufnimmt — **0 gestrichen, 3 nachgeführt** (anders als
S6c: 14/4, S6d: 6/22): die drei Einträge werden auf ihre neu gemessenen Zeilennummern
nachgezogen und in `BLEIBT_MIT_INHALT` mit ihrem wortgleichen Bedingungstext gefesselt.
`EINGEFROREN_SOLL_ANZAHL` bleibt bei 47 (keine Löschung). Betroffene Datei also **MODIFY**,
nicht „keine Änderung" — Korrektur der Affected-Files-Tabelle unten.

**Type-Import ebenfalls Teil des Rückbaus:** `VersandTab.svelte:18` importiert
`type CompareWizardState` — laut AC-2-Neufassung zählt auch das Lesen von
„Compare-Store-Typen" als HERKUNFT-Zweig-Symptom. Mit dem Wegfall der `wiz`-Prop wird dieser
Type-Import ungenutzt und muss mit entfernt werden (sonst überlebt ein stiller AC-2-Verstoß den
Umbau).

### Auflage A1 (Platzierung, analog S6d Auflage A2)
`versandVergleichSpeicherung.ts:221` ist der eingefrorene Ratschen-Eintrag (die
`context === 'vergleich'`-Prüfung in `versandVergleichSpeicherungAktiv`). Die neue Funktion
`versandZustandsBruecke` MUSS unterhalb dieser Zeile (praktisch: ans Dateiende nach Zeile 300)
eingefügt werden — sonst verschiebt sich Zeile 221 nach unten und die Ratsche schlägt fälschlich
an. Die Umbenennung `wiz`→`zustand` in `versandVergleichSpeicherungAktiv`s Parameter-Objekt UND
in `VersandVergleichSpeicherungOptionen` ist unkritisch: Zeile 221 bleibt (`p.context ===
'vergleich' && !!p.zustand && ...`) inhaltlich verändert, aber an derselben Zeilennummer mit dem
`context ===`-Literal erhalten.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | MODIFY | `Optionen.wiz`→`zustand`, `versandVergleichSpeicherungAktiv`-Param `wiz`→`zustand`, neue Funktion `versandZustandsBruecke()` unterhalb Zeile 221 (Auflage A1) |
| `frontend/src/lib/components/compare/versandPropsAus.ts` | CREATE | Bündelt `wiz` → 8 UI-Wertprops + `onXChange` je Feld (7 Snapshot-Felder + `sendEmail` außerhalb der Brücke, Korrektur oben), 3 Legacy-Lesewerte, `onVersandFeldSetzen`-Rollback-Senke — analog `alarmePropsAus.ts`/`corridorPropsAus.ts` |
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | `wiz`-Prop entfernen, alle `wiz.*`/`wiz?.*`-Zugriffe (Z. 55/194/218-222/271-291/330-373) durch Wertprops + Callbacks ersetzen, lokale `versandZustandsBruecke`-Instanz (analog `AlarmeTab.svelte:439-450`), Self-Save-Block ruft `erstelleVersandVergleichSpeicherung({..., zustand: bruecke})` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Mount B (Z. 1070-1079): `wiz={wizardState}` → `{...versandPropsAus(wizardState)}` inline im Markup-Ausdruck (Aufrufform-Pflicht wie bei `alarmePropsAus`/`corridorPropsAus`) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Mounts C (Z. 407, Desktop) + D (Z. 493, Mobil): `wiz` → `{...versandPropsAus(wiz)}`, `activation` bleibt separat |
| ~18 Testdateien (siehe Liste oben) | MODIFY | `wiz={...}`-Mounts auf neue Wertprops umstellen (mechanisch, Kern-Layer) |
| `shared/__tests__/versand_tab_laedt_keine_compare_klebeschicht.test.ts` | KEINE ÄNDERUNG | Bereits existierende Ratsche (AC-8 aus S5), bleibt grün — `VersandTab` importiert weiterhin keine Compare-Klebeschicht |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | **MODIFY** | Neuer 🔴 VERTRAG-Absatz für `VersandTab.svelte` (0 gestrichen/3 nachgeführt), die drei Einträge `VersandTab.svelte:284/294/330` auf neue Zeilennummern nachziehen + in `BLEIBT_MIT_INHALT` fesseln. `EINGEFROREN_SOLL_ANZAHL` bleibt 47 (siehe Korrektur-Abschnitt oben) |

### Scope Assessment
- Files: 7 produktiv (inkl. Ratschen-Testdatei) + ~18 Tests
- Estimated LoC: ~+120/-90 (produktiv) + ~+150/-150 (Tests, mechanisch)
- Risk Level: LOW — reines Präzedenzmuster (dritte Anwendung nach S6c/S6d), keine neue
  Architektur-Entscheidung
- **LoC-Limit 250/Workflow wird voraussichtlich überschritten** (Testdateien allein ~150-250
  LoC) — `workflow.py set-field loc_limit_override 500` vor `/40-tdd-red` einplanen, analog
  S6c/S6d-Präzedenz

### Technical Approach
Drittes Wiederholung des in S6c (`alarmZustandsBruecke`, Namensumleitung) und S6d
(`corridorZustandsBruecke`, ohne Namensumleitung) etablierten Musters:
1. `versandPropsAus(wiz)` bündelt Werte+Callbacks für die drei Mounts (B/C/D) — Aufrufform als
   Markup-Spread, nie vorberechnete Variable.
2. `VersandTab.svelte` verliert die `wiz`-Prop vollständig, bekommt stattdessen die
   gebündelten Wertprops + drei Legacy-Lesewerte + `onVersandFeldSetzen`.
3. `VersandTab.svelte` baut lokal `versandZustandsBruecke(werte, setzen)` — ein Proxy, der
   `erstelleVersandVergleichSpeicherung`/`versandSnapshotAus`/`rollbackVersandSnapshot`
   unverändert bedient (diese Funktionen kennen nur `VersandHydrationTarget`, keine
   `CompareWizardState`-Details).
4. Rollback-Schreibwege für die drei Legacy-Felder laufen ausschließlich über
   `onVersandFeldSetzen`, exakt wie `onAlarmFeldSetzen` in S6c — keine neue Mechanik.
5. Kein Kanal-Impact, keine Nutzlast-Änderung — `baueVersandNutzlast`/`hydrateVersandFieldsFromPreset`
   bleiben unverändert (Datenfluss identisch, nur die Zulieferung des `VersandHydrationTarget`
   ändert sich).

### Dependencies
Wie im Kontext-Dokument oben (`compareWizardState.svelte.ts`, `versandVergleichSpeicherung.ts`
Kernlogik unverändert, `mergeReportConfig.ts` Route-Zweig unberührt). Reihenfolge:
`versandVergleichSpeicherung.ts` (Bruecke) → `versandPropsAus.ts` (neu) → `VersandTab.svelte`
(Verdrahtung) → drei Mounts → Tests.

### Open Questions
Keine offenen technischen Fragen — beide Klärungspunkte aus dem Kontext-Dokument sind durch
S6c-Präzedenz (`onAlarmFeldSetzen`) und den Ratschen-Zählbefehl eindeutig beantwortet.

## Existing Specs

- `docs/specs/modules/rework_2276_s5_versand.md` — Speicherweg-Selbst-Save (Vorstufe, ACs 1-12,
  bleiben in Kraft)
- `docs/specs/modules/rework_2276_s6c_alarme.md` — direktes Vorbild (Bridge-Pattern)
- `docs/specs/modules/rework_2276_s6d_wertebereiche.md` — zweites Vorbild (PropsAus ohne
  Namensumleitung, Aufrufform-Auflage A1)

## Verwandt

[[project_2276_compare_speicherweg_stand]], [[reference_bausteintest_beweist_die_verdrahtung_nicht]],
[[reference_compare_end_date_sentinel_schreiben_vs_lesen]]
