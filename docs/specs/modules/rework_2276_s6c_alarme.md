---
entity_id: rework_2276_s6c_alarme
type: refactor
created: 2026-09-21
updated: 2026-09-21
status: draft
version: "1.0"
tags: [compare, alarme, wertprops, ratsche, refactor]
---

# Alarme-Fläche des Ortsvergleichs auf Wertprops (Issue #2276, Scheibe S6c, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Scheibe **S6c** von #2276 (Epic #2345) stellt den geteilten Alarme-Organismus
`AlarmeTab.svelte` (`context="route"|"vergleich"`) im **Vergleichs-Zweig** vom
Zustandsobjekt `wiz` (Compare-Wizard-Bus) auf reine **Wertprops +
Änderungs-Rückrufe** um — nach dem in S6b (`CompareHourlyLayoutControls.svelte`,
live seit `8207c157`) erprobten Muster. Der `wiz`-Zugriff verschwindet dabei
nicht, er **wandert zum Elternteil hoch**: eine neue Bündel-Funktion
`alarmePropsAus(wiz)` baut das Prop-Bündel, das alle drei Vergleichs-Mounts
identisch einspeisen. Verhalten bleibt unverändert — AC-1 des Tickets
(Organismus persistiert selbst) ist bereits seit S2 live, S6c zahlt auf
**AC-2** (HERKUNFT-Abbau) und **AC-4** (Klebeschicht ohne Importeur) ein.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/AlarmeTab.svelte`,
  `frontend/src/lib/components/compare/alarmePropsAus.ts` (neu),
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`,
  `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`,
  `frontend/src/lib/components/shared/__tests__/compare_alarme_wertprops.test.ts` (neu),
  `frontend/src/lib/components/shared/__tests__/alarme_tab_laedt_keine_compare_klebeschicht.test.ts`,
  `frontend/e2e/compare-alarme-wertprops.spec.ts` (neu),
  `.github/ci_e2e_specs.txt`
- **Identifier:** `AlarmeTab` (Props: 13 Wertprop-Felder + Rückrufe, neue Prop
  `zonenBezug`), `alarmePropsAus(wiz)` (`compare/alarmePropsAus.ts`, neu),
  Mount (B) `CompareTabs.svelte:1044-1054`, Mount (C)
  `CompareNewEditor.svelte:396`, Mount (D) `CompareNewEditor.svelte:487`

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`). Kein Go-API- und kein Python-Core-Code in
dieser Scheibe.

## Nicht in dieser Scheibe

- **Die Kind-Bausteine bleiben unangetastet.** Kein Kind
  (`ChannelToggle`, `AlertMetricLevelTable`, `AlertChannelPicker`,
  `TelegramKurzstilToggle`, `AlertCooldownCard`, `AlertQuietHoursCard`,
  `VTAlertSample`, `AlertPreviewCard`) kennt `wiz` — sie bekommen bereits
  primitive Werte. Insbesondere `AlertCooldownCard.svelte` und
  `AlertQuietHoursCard.svelte` bleiben **unverändert**, weil ihre
  `$bindable`-Props (`AlertCooldownCard.svelte:5`,
  `AlertQuietHoursCard.svelte:10-11`) durch Funktions-Bindungen bedient werden
  (siehe Implementation Details).
- **Der Trip-Zweig (`context="route"`) wird nicht angefasst** — weder in
  `AlarmeTab.svelte:345` inhaltlich noch in
  `trip-detail/AlarmeScheduleTab.svelte:60-69`. Die neue Prop `zonenBezug`
  bekommt einen Vorgabewert, der genau das heutige Verhalten des Trip-Mounts
  abdeckt (siehe unten) — die Datei bleibt deshalb **außerhalb** der
  Affected-Files-Liste.
- **Der Speicherweg bleibt unverändert:** `erstelleAlarmeVergleichSpeicherung`,
  `hubPutQueue` (`compareHubWizardBridge.ts:340-352`), Voll-Spread-Payload
  (`buildComparePresetSavePayload`), Rollback, Read-Modify-Write. Diese
  Scheibe verschiebt nur die **Quelle** der gelesenen/geschriebenen Werte, nie
  den Weg, auf dem sie persistiert werden.
- **`hydrateAlarmFieldsFromPreset`, `wiz.saveNewPreset()` auf der Anlege-Seite
  und die `alert_channels`-Struktur (#2293) sind unberührt.**
- **Kein zweiter Sub-Schnitt nach Feldgruppen.** Eine Aufteilung würde die
  Ratschen-Umstellung mehrfach durchlaufen — genau den teuren, riskanten Teil.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | 13 `wiz`-Felder an den 21 in der Analyse gemessenen Stellen (Lesen: `:171,186,199(bleibt),216,243,280,345(fällt zu `!trip`),450,460,468,475`; Schreiben: `:175,222,255-257,286-296,453,460,468,477`) → Wertprops + Rückrufe; 14 HERKUNFT-Zweige fallen (siehe Schicksals-Tabelle); 2 `bind:`-Stellen (Cooldown, Stille Stunden) → Funktions-Bindungen; neue Prop `zonenBezug` mit Vorgabewert `'der Trip'` |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` | CREATE | Eine Stelle, die aus `wiz` das komplette Prop-Bündel (13 Werte + zugehörige Rückrufe + `zonenBezug: 'des ersten Orts'`) für `AlarmeTab` baut — von allen drei Vergleichs-Mounts identisch benutzt |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Mount (B) `:1044-1054` von `wiz={wizardState}` + Einzel-Props auf `{...alarmePropsAus(wizardState)}` im Markup-Ausdruck; `catalog`, `preset`, `saveController`, `enqueueHubWrite`, `onCompareUpdate` bleiben eigenständige Props (nicht Teil des Bündels) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Mounts (C) `:396` und (D) `:487` von `{wiz}` auf `{...alarmePropsAus(wiz)}` — **sonst verlieren sie ihre Bedienelemente** (Regel „Prop da → Bedienelement da", S6b-Muster); `catalog` bleibt eigenständige Prop |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | 14 der 18 `AlarmeTab.svelte`-Einträge **bewusst** aus `EINGEFROREN` streichen (`:199,424,443,482` bleiben mit neuen Zeilennummern), `EINGEFROREN_SOLL_ANZAHL` 67 → 53 (oder → 54, falls die `:345`-Äquivalenz in `/40` nicht beweisbar ist — siehe Entscheidung zu `:345`), Begründung je gestrichenem Eintrag in der Commit-Nachricht — im selben Commit wie der jeweilige Rückbau |
| `frontend/src/lib/components/shared/__tests__/compare_alarme_wertprops.test.ts` | CREATE | Wirkort-Guard im Kern über `effekteVon()` (`svelteInstanzPruefstand.ts:188`) an den **negativen** Wirkorten (Trip, `/compare/new` ohne `preset`/`saveController`) + AST-Wächter über die Prop-Verdrahtung aller drei Vergleichs-Mounts |
| `frontend/src/lib/components/shared/__tests__/alarme_tab_laedt_keine_compare_klebeschicht.test.ts` | MODIFY | Saat von `wiz: wizStub()` auf die neuen Einzel-Wertprops umgestellt; **Gegenprobe ergänzt** (Bridge-Import künstlich einschleusen ⇒ muss rot werden), sonst wird der Ladetest nach dem Umbau vakuum-grün |
| `frontend/e2e/compare-alarme-wertprops.spec.ts` | CREATE | Verhaltensgleichheit im Browser am Hub-Mount (B): Alarm-Konfiguration ändern, speichern, Reload, unverändert |
| `.github/ci_e2e_specs.txt` | MODIFY | Genau **eine** neue Spec aufnehmen (`e2e/compare-alarme-wertprops.spec.ts`), `E2E_MIN_SPECS` und `E2E_MIN_EXECUTED_HAUPT` exakt nachziehen (Werkzeug: `npx playwright test --list` auf die neue Datei) |

**Zu prüfen, ob eine Saat-Anpassung nötig ist** (alle fahren den
Vergleichs-Pfad, keiner davon zwingend zu ändern — Prüfpflicht, nicht
Änderungspflicht):
`alarme_vergleich_flush_beim_reiterwechsel.test.ts`,
`alarme_vergleich_kein_zurueckschreiben.test.ts`,
`alarme_vergleich_konflikt_nochmal_speichern.test.ts`,
`alarme_vergleich_ruecknahme_waehrend_put.test.ts`,
`compare_hub_alarme_bridge.test.ts`,
`compare_alarme_channel_threshold_save.test.ts`,
`alarme_tab_catalog_prop_structure.test.ts`,
`alarme_tab_unalertable_hint_structure.test.ts`, sowie
`alarme_save_single_writer.test.ts` Teil (a) (`:40-52`), dessen Grün von der
`:345`-Entscheidung abhängt (siehe unten).

## Estimated Scope

- **LoC (produktiv, geschätzt):** ca. +170 / −60 — unter dem 250-LoC-Limit,
  aber **nicht komfortabel**. Vor einer Override-Ankündigung in `/50` ist
  `workflow.py status` zu befragen, nicht aus dieser Schätzung abzuleiten.
- **Files:** 4 produktiv (davon 1 neu), plus 3 Testdateien, 1 neue E2E-Spec,
  1 CI-Positivliste (Testdateien zählen nicht gegen das LoC-Limit).
- **Effort:** medium.
- **Risk Level: MITTEL–HOCH.** Der Wirkort liegt in Prop-Verdrahtung und
  `$effect`, die der SSR-Harness (`generate: 'server'`, kein DOM) nicht
  sieht; zwei der drei Mounts (C/D, `/compare/new`) sind in der CI-Ampel
  unbewacht; die Ratschen-Umschreibung (14 Einträge auf einmal) ist die
  größte Einzeländerung an diesem Wächter seit seiner Einführung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareHourlyLayoutControls.svelte` (S6b, live `8207c157`) | component | Lebender Präzedenzfall für Wertprops + Rückrufe statt `wiz`, Regel „Prop da → Bedienelement da" |
| `compare_stundenverlauf_wertprops.test.ts:410-522` | test | Vorbild für den Wirkort-Guard über `effekteVon()` an negativen Orten (Trip, `/compare/new`) — Lehre aus S6b-Adversary-Finding F001 |
| `frontend/src/lib/components/shared/__tests__/svelteInstanzPruefstand.ts:75,188` | Prüfstand | `umgebungFuer()` und `effekteVon()` — führt `$effect`-Rümpfe wirklich aus, statt sie zu verwerfen |
| `context_herkunft_zweige_eingefroren.test.ts` | test | Die 67er-Ratsche selbst; enthält heute alle 18 `AlarmeTab.svelte`-Einträge |
| `docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md` | spec | Ratschen-Vertrag: „eine Zeile → eine Zeile", Streich-Pflicht statt automatischem Nachzug — in S6c bewusst durchbrochen (siehe Design-Entscheidung 1) |
| `docs/specs/modules/rework_2276_s6b_wetter_metriken.md` | spec | Formvorbild; Regel „`wiz`→Wertprops und HERKUNFT-Abbau sind zwei getrennte Wirkungen" |
| `alarme_tab_laedt_keine_compare_klebeschicht.test.ts` | test | AC-9 aus S2 (kein Laufzeit-Import der Klebeschicht) — Saat muss der neuen Prop-Form folgen |
| `alarmeVergleichSpeicherung.ts:185-235` | module | Speicherweg, den S6c nicht anfasst — `erstelleAlarmeVergleichSpeicherung`, `alarmSnapshotAus` |
| `compareHubWizardBridge.ts:340-352` | module | `hubPutQueue` — bleibt, sonst bauen zwei PUTs aus demselben stalen `currentPreset`, der zweite bekommt 200 OK mit veraltetem Body |

## Implementation Details

### Design-Entscheidungen

1. 🔴 **Die S6b-Regel „zeilentreu, nur ein Eintrag fällt" ist in S6c
   bewusst nicht anwendbar — und das ist eine dokumentierte Abweichung, keine
   Nachlässigkeit.** Grund: ~24 neue Prop-Zeilen entstehen im `interface
   Props` und im `let {…}`-Destrukturierungsblock von `AlarmeTab.svelte`,
   also **oberhalb aller 18 eingefrorenen Einträge**. Jede Zeilennummer
   verschiebt sich zwangsläufig; Zeilenzahl-Wiederherstellung wäre Verrenkung,
   nicht Sorgfalt. Weil Mengengleichheit auf `Datei:Zeile` ihre Beweiskraft
   verliert, sobald 14 Einträge fallen und 4 auf neuen Zeilen weiterleben (ein
   **neuer** Zweig könnte eine frei gewordene Nummer besetzen), hält diese
   Spec **je Eintrag Schicksal UND Bedingungstext wörtlich** fest — geprüft
   wird am Inhalt, nicht an der Position.

2. **Schicksals-Tabelle der 18 Ratschen-Einträge in `AlarmeTab.svelte`**
   (Basis `8207c157`, Bedingungstext wörtlich aus dem Quelltext gelesen):

   | alt | Bedingung (wörtlich) | Schicksal | Grund |
   |---|---|---|---|
   | `:171` | `context === 'vergleich' ? (wiz?.officialWarningsEnabled ?? false) : officialWarningsEnabled` | **FÄLLT** | reine Quellenwahl |
   | `:174` | `if (context === 'vergleich') {` (Schreiben `officialWarningsEnabled`) | **FÄLLT** | reine Zielwahl |
   | `:186` | `context === 'vergleich'` (Lesen `activeMetricKeys`, Ableitung `effectiveActiveMetrics`) | **FÄLLT** | reine Quellenwahl |
   | `:199` | `context === 'vergleich'` (Ableitung `unalertableSelectedMetricNames`, route strukturell `[]`) | **BLEIBT** | FACHLICH — route liefert strukturell immer `[]` (dort gibt es keine Metrik-Auswahl), jeder daraus gebildete Satz wäre sachlich falsch (#1435 AC-7) |
   | `:216` | `context === 'vergleich'` (Lesen `metricAlertLevels`) | **FÄLLT** | reine Quellenwahl |
   | `:221` | `if (context === 'vergleich') {` (Schreiben `metricAlertLevels`) | **FÄLLT** | reine Zielwahl |
   | `:243` | `context === 'vergleich'` (Lesen Kanäle `sendTelegram`/`sendSms`/`sendPremiumSms`) | **FÄLLT** | reine Quellenwahl |
   | `:253` | `if (context === 'vergleich') {` (Schreiben Kanäle) | **FÄLLT** | reine Zielwahl |
   | `:280` | `context === 'vergleich'` (Lesen `channelThresholds`) | **FÄLLT** | reine Quellenwahl |
   | `:285` | `if (context === 'vergleich') {` (Schreiben `channelThresholds`) | **FÄLLT** | reine Zielwahl |
   | `:345` | `if (context !== 'route') return;` | **FÄLLT** (bedingt, siehe Entscheidung unten) | zeilentreu → `if (!trip) return;`, **wenn** die Äquivalenz in `/40` durch einen Wirkort-Test bewiesen wird — gelingt der Beweis nicht, **bleibt** `:345` stehen |
   | `:367` | `context === 'vergleich' && wiz && preset && saveController` | **FÄLLT** | nennt `wiz`; wird zum Fähigkeits-Gate ohne `context`/`wiz` (z.B. `preset && saveController`) |
   | `:379` | `if (context !== 'vergleich' \|\| !wiz \|\| !vergleichSpeicherung) return;` | **FÄLLT** | zeilentreu → `if (!vergleichSpeicherung) return;` (identisches Muster zu S6b AC-4) |
   | `:424` | `{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}` | **BLEIBT** | Markup ohne eigenen `wiz`-Bezug; hängt an der fachlichen Zusicherung aus `:199` — solange `:199` fachlich bleibt, ist dieser Zweig ihr notwendiger Anzeige-Zwilling |
   | `:443` | `{#if context === 'vergleich'}` (Kurzstil-Schalter) | **BLEIBT** | DARSTELLUNG — im Trip steht derselbe Schalter im Versand-Reiter, nicht hier (#1260 S5) |
   | `:459` | `{#if context === 'vergleich'}` (Cooldown-Karte) | **FÄLLT** | beide Zweige rendern dieselbe Komponente mit demselben einzigen Attribut; einziger Unterschied ist das Bindungsziel — mit Wertprop + Funktions-Bindung bleibt ein Mount übrig, der Wächter hat nichts mehr zu unterscheiden |
   | `:467` | `{#if context === 'vergleich'}` (Stille Stunden) | **FÄLLT** | dito; der einzige echte Unterschied `zonen_bezug` (`"des ersten Orts"` vs. `"der Trip"`) wandert an die Aufrufstelle als Prop `zonenBezug` mit Vorgabewert `'der Trip'` |
   | `:482` | `{#if context === 'vergleich'}` (Beispielwarnung, `VTAlertSample` vs. `AlertPreviewCard`) | **BLEIBT** | FACHLICH — Ort- statt Etappen-Subjekt, zwei verschiedene Komponenten, kein Quellenwahl-Fall |

   **Bilanz: 14 fallen, 4 bleiben (mit neuen Zeilennummern). Ratsche 67 → 53**
   (oder → 54, falls `:345` stehen bleibt — siehe unten). Die drei Einträge
   `alarme-tab/alarmeTabSections.ts:27, :38, :42` werden **nicht** angefasst;
   ihre Zeilennummern dürfen sich nicht verschieben.

3. **Entscheidung zu `:345` (bewusst, begründungspflichtig im Commit).**
   `:345` ist der **Trip**-Speicherweg-Guard, gehört also inhaltlich nicht zur
   Wirkung „Vergleichs-Zweig auf Wertprops". Die S6b-Regel „`wiz`→Wertprops
   und HERKUNFT-Abbau nie koppeln" spräche dafür, ihn liegen zu lassen.
   **Dagegen und entscheidend:** S6c ist die **einzige verbleibende Scheibe**,
   die `AlarmeTab.svelte` öffnet (S6d Wertebereiche, S6e Versand, S6f Bilanz
   berühren diese Datei nicht mehr). Bliebe `:345` stehen, wäre er ein
   Waisenkind gegen die S6-Zielaussage „keine HERKUNFT-Zweige in `shared/`"
   und fiele erst in der Bilanz-Scheibe unangenehm auf. Deshalb fällt `:345`
   **zeilentreu** (eine Zeile → eine Zeile) zu `if (!trip) return;` — dieselbe
   Bauart, die S6b in seiner AC-4 einmalig und begründet angewandt hat.
   Äquivalenz ist beweispflichtig: In den drei Vergleichs-Mounts ist `trip`
   nie gesetzt, im Trip-Mount (`AlarmeScheduleTab.svelte:60-69`) immer. Ein
   Wirkort-Test im Kern (Mechanik aus AC-4, `effekteVon()` an den negativen
   Orten) muss das bewachen. **Beide Ausgänge sind
   zulässig:** Lässt sich die Äquivalenz in `/40` nicht sauber zeigen, bleibt
   `:345` stehen und die Ratsche endet bei **54** statt 53 — das ist dann kein
   Scheitern der Scheibe, sondern das dokumentierte Ergebnis.

4. **`alarmePropsAus(wiz)` statt dreifacher Inline-Glasur.** S6b hat inline
   Pfeilfunktionen gewählt, *weil benannte Adapter zeilenverschiebend gewesen
   wären* — dieses Argument trägt hier **nicht mehr**, weil sich die Zeilen in
   `AlarmeTab.svelte` durch den HERKUNFT-Abbau ohnehin verschieben (siehe
   Design-Entscheidung 1). Bei **drei** Mounts × 13 Feldern wären
   Inline-Adapter an jeder Einbettung rund 60 Zeilen fast gleiche Glasur —
   dreifache Gelegenheit zur Drift, genau das Anti-Pattern, das #2276 abbaut.
   Stattdessen **eine** Funktion `alarmePropsAus(wiz)` in
   `compare/alarmePropsAus.ts`, die das komplette Bündel (13 Werte + Rückrufe
   + `zonenBezug: 'des ersten Orts'`) baut.
   🔴 **Form-Auflage (prüfbar, kein Prosa-Wunsch):** `alarmePropsAus(wiz)`
   wird an **allen drei** Vergleichs-Mounts **im Markup-Ausdruck selbst**
   aufgerufen — `{...alarmePropsAus(wiz)}` — **nicht** in eine Variable im
   Instanz-Skript gehoben. Ein einmal berechnetes, in einer Skript-Variable
   eingefrorenes Objekt bestünde SSR-Prüfstand und AST-Wächter anstandslos und
   fiele erst im Browser auf (die `$state`-Lesezugriffe würden dann außerhalb
   des reaktiven Renderns registriert). Diese Form kann ein AST-Wächter
   tatsächlich messen — „ist reaktiv" kann er nicht.

5. **Zwei `bind:`-Stellen werden zu Funktions-Bindungen.** Svelte ist auf
   `^5.55.2` (`frontend/package.json:27`), Funktions-Bindungen
   (`bind:x={() => wert, (v) => rueckruf(v)}`) sind seit 5.9 verfügbar.
   `AlarmeTab.svelte:459` (Cooldown, heute `bind:cooldown_minutes={wiz!.alertCooldownMinutes}`)
   und `:467` (Stille Stunden, heute
   `bind:quiet_from={wiz!.alertQuietFrom} bind:quiet_to={wiz!.alertQuietTo}`)
   werden zu `bind:cooldown_minutes={() => cooldownMinutes, onCooldownChange}`
   bzw. den entsprechenden Paaren für `quiet_from`/`quiet_to`. Die Kind-Bausteine
   `AlertCooldownCard.svelte` und `AlertQuietHoursCard.svelte` bleiben dadurch
   **unverändert** — ihre `$bindable`-Props sehen von außen keinen Unterschied
   zwischen zweiwegiger State-Bindung und Funktions-Bindung.

6. **Neue Prop `zonenBezug` mit Vorgabewert `'der Trip'`.** Der Trip-Mount
   (`trip-detail/AlarmeScheduleTab.svelte:60-69`) übergibt heute **kein**
   `zonen_bezug` an `AlarmeTab` — der bisherige `context==='vergleich'`-Zweig
   an `:467` setzt `zonen_bezug="der Trip"` nur für den `else`-Fall (Trip)
   hart. Der Vorgabewert `'der Trip'` deckt dieses Verhalten vollständig ab,
   ohne die Trip-Datei anzufassen. Die drei Vergleichs-Mounts liefern
   `zonenBezug: 'des ersten Orts'` über `alarmePropsAus(wiz)`.

### Wirkort je Zusicherung (Lehre aus S6b-Adversary-Finding F001)

Der Adversary zeigte in S6b, dass der SSR-Prüfstand `$effect`-Rückrufe verwarf
und die E2E-Spec nur im Hub lief, wo die Vergleichs-Speicherung strukturell
immer aktiv ist — eine Mutation an den negativen Orten war dort
**unbeobachtbar**. Für S6c gilt deshalb je Zusicherung ein festgelegter
Wirkort:

- **Verhalten im Browser am Hub-Mount (B)** → neue E2E-Spec
  `frontend/e2e/compare-alarme-wertprops.spec.ts`.
- **Wirkort-Guard an den negativen Orten** (Trip `context: 'route'`,
  `/compare/new` mit `preset: null`/`saveController: null`) → **Kern**, über
  `effekteVon()` (`shared/__tests__/svelteInstanzPruefstand.ts:188`), Muster
  aus `compare_stundenverlauf_wertprops.test.ts` (ab ~`:410`).
- **`/compare/new` behält seine Bedienelemente** → **Kern**, AST-Wächter über
  alle drei Vergleichs-Mounts — keine gelistete E2E-Spec berührt `/compare/new`
  im Alarme-Reiter, eine Regression dort führe sonst grün durch die Ampel.
- **Keine Klebeschicht geladen (AC-4 aus #2276)** →
  `alarme_tab_laedt_keine_compare_klebeschicht.test.ts`, Saat auf die neue
  Prop-Form angepasst **plus Gegenprobe** (Bridge-Import künstlich
  einschleusen ⇒ muss rot werden) — ohne Gegenprobe wird der Ladetest nach
  dem Umbau vakuum-grün, weil er dann nur noch beweist, dass ein Objekt ohne
  `wiz`-Feld gerendert werden kann, nicht dass die Bridge fehlt.

**Bewusst KEINE zweite E2E-Spec für `/compare/new`:** Das bräche die
Scheiben-Disziplin (eine Spec je Scheibe, S2–S6b) und landet in der
dokumentierten `global.setup`-ENOENT-Klasse (`ci_e2e_specs.txt:185-187`). Der
Anlege-Mount wird stattdessen im Kern bewacht (siehe oben).

## Expected Behavior

- **Input:** Im Alarme-Reiter des Ortsvergleichs (Hub `/compare/[id]` sowie
  Anlege-Desktop/-Mobil `/compare/new`) werden Amtliche Warnungen,
  Metrik-Alarmschwellen, Kanäle (Telegram/SMS/Premium-SMS), Kanal-Schwellen,
  Telegram-Kurzstil, Cooldown, Stille Stunden und Radar-Alarm bedient — wie
  heute.
- **Output:** Dieselbe sichtbare Auswahl, derselbe Speicherweg im Hub (ein
  PUT je Änderung, `SaveIndicator`); keine Nutzer-sichtbare
  Verhaltensänderung. Intern liest/schreibt `AlarmeTab` keine `wiz`-Referenz
  mehr, sondern ausschließlich Wertprops und Rückrufe; `wiz` und der Aufbau
  des Prop-Bündels liegen jetzt im Elternteil (`CompareTabs.svelte`,
  `CompareNewEditor.svelte` über `alarmePropsAus`).
- **Side effects:** Der Selbst-Speicher-`$effect` (`:379`, künftig
  `if (!vergleichSpeicherung) return;`) prüft Kontext/Wizard-Vorhandensein
  nicht mehr direkt, sondern ausschließlich über `vergleichSpeicherung` —
  semantisch identisch, weil `vergleichSpeicherung` bereits `null` ist, sobald
  eine der ursprünglichen Bedingungen fehlt (Muster S6b AC-4).

## Acceptance Criteria

- **AC-1 (`AlarmeTab` ist im Vergleichs-Zweig wertprop-rein):** Given
  `AlarmeTab.svelte` liest/schreibt heute 13 Felder über `wiz` an den in der
  Analyse gemessenen Stellen (Lesen `:171,186,216,243,280,450,460,468,475`,
  Schreiben `:175,222,255-257,286-296,453,460,468,477`) / When der
  Vergleichs-Zweig auf reine Wertprops + Rückrufe (`officialWarningsEnabled`,
  `onOfficialWarningsChange`, `metricAlertLevels`, `onMetricLevelChange`,
  `sendTelegram`/`sendSms`/`sendPremiumSms`, `onChannelToggle`,
  `channelThresholds`, `onThresholdChange`, `telegramStyle`,
  `onTelegramStyleChange`, `cooldownMinutes`, `onCooldownChange`,
  `quietFrom`/`quietTo`, `onQuietHoursChange`, `radarAlertEnabled`,
  `onRadarAlertChange`, `zonenBezug`) umgestellt wird / Then enthält
  `AlarmeTab.svelte` keinen `wiz`-Zugriff und keinen Typ-Import von
  `CompareWizardState` mehr im Vergleichs-Pfad.
  - Test: Kern — Build/Typecheck bleibt grün (kein `wiz`-Symbol mehr im
    Compile-Baum von `AlarmeTab.svelte`); die tatsächliche
    Verhaltensgleichheit ist nur im Browser messbar, siehe AC-2.

- **AC-2 (Verhaltensgleichheit im Browser am Hub):** Given vor der Umstellung
  wirken alle Alarm-Bedienelemente im Alarme-Reiter des Ortsvergleichs-Hubs
  (`/compare/[id]`) und werden über den einen bestehenden PUT gespeichert /
  When derselbe Ablauf nach der Umstellung im Browser gegen Staging
  durchgeführt wird / Then bleibt das Verhalten unverändert: Amtliche
  Warnungen, Metrik-Schwellen, Kanäle, Kanal-Schwellen, Kurzstil, Cooldown,
  Stille Stunden und Radar-Alarm lassen sich setzen, die Änderung übersteht
  Speichern/Reload, und es entsteht weiterhin genau ein PUT je Änderung.
  - Test: Live-E2E — neue Spec `frontend/e2e/compare-alarme-wertprops.spec.ts`,
    Eintrag in `.github/ci_e2e_specs.txt` mit nachgezogenem
    `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT`. Der Hub ist der einzige Mount
    mit aktivem Speicherweg — nur hier ist Persistenz browserseitig
    beobachtbar.

- **AC-3 (`/compare/new` behält seine Bedienelemente an beiden Mounts):**
  Given Mount (C) (Desktop, `CompareNewEditor.svelte:396`) und Mount (D)
  (Mobil, `:487`) übergeben heute `{wiz}` + `catalog` an `AlarmeTab` / When
  beide Mounts auf `{...alarmePropsAus(wiz)}` + `catalog` umgestellt werden /
  Then rendern an beiden Mounts weiterhin alle Bedienelemente, für die
  `alarmePropsAus` einen Rückruf liefert (Regel „Prop da → Bedienelement da").
  - Test: Kern — AST-Wächter in `compare_alarme_wertprops.test.ts`, der über
    alle drei Vergleichs-Mounts prüft, dass `alarmePropsAus(wiz)` im
    Markup-Ausdruck selbst aufgerufen wird (nicht in eine Skript-Variable
    gehoben) und dass keine Einzel-Feld-Props fehlen. Keine gelistete E2E-Spec
    berührt `/compare/new` im Alarme-Reiter — ohne diesen Kern-Wächter liefe
    eine Regression an (C)/(D) grün durch die CI-Ampel (F001-Lehre aus S6b).

- **AC-4 (Wirkort-Guard: der Selbst-Speicher-Effekt schweigt an negativen
  Orten):** Given der Selbst-Speicher-`$effect` (`AlarmeTab.svelte:379`, nach
  der Umstellung `if (!vergleichSpeicherung) return;`) darf nur dort
  arbeiten, wo eine Vergleichs-Speicherung existiert / When der Effekt-Rumpf
  über `effekteVon()` an den negativen Orten (Trip, `/compare/new` mit
  `preset: null`/`saveController: null`) wirklich ausgeführt wird / Then
  bleibt der Rumpf dort wirkungslos (kein `aenderungMelden()`-Aufruf), und am
  positiven Ort (Hub, `preset`+`saveController` gesetzt) wirkt er.
  - Test: Kern — `compare_alarme_wertprops.test.ts`, Muster aus
    `compare_stundenverlauf_wertprops.test.ts:410-522`
    (`umgebungFuer()`/`effekteVon()`, `svelteInstanzPruefstand.ts:75,188`).
    Diese Zusicherung wirkt in einem `$effect`, den der SSR-Prüfstand ohne
    diesen Mechanismus verwirft — deshalb Kern mit echtem Effekt-Lauf statt
    Browser-Test, der die negativen Orte ohnehin nicht erreicht.
  - Mutations-Gegenprobe: `if (!vergleichSpeicherung) return;` auf
    `if (false) return;` verfälschen ⇒ der Effekt wirkt nirgends mehr, auch
    nicht am positiven Ort ⇒ dieser Test wird rot (Positiv-Gegenprobe im
    selben Testblock); auf `if (true) return;` verfälschen ⇒ der Effekt wirkt
    an den negativen Orten weiter ⇒ dieser Test wird rot (Negativ-Gegenprobe).
    Kein E2E-Test fängt entweder Mutation, weil nur der Hub browserseitig
    geprüft wird und dort `vergleichSpeicherung` strukturell immer gesetzt
    ist.

- **AC-5 (Klebeschicht bleibt ohne Laufzeit-Importeur, Saat + Gegenprobe):**
  Given `alarme_tab_laedt_keine_compare_klebeschicht.test.ts` sät heute
  `wiz: wizStub()` als einzelne Prop und prüft den Ladegraphen von
  `AlarmeTab.svelte` gegen `compareHubWizardBridge.ts` / When die Saat auf die
  neuen Einzel-Wertprops (Ergebnis von `alarmePropsAus(wizStub())`)
  umgestellt und eine Gegenprobe ergänzt wird, die einen künstlichen
  Laufzeit-Import der Bridge in `AlarmeTab.svelte` einschleust / Then bleibt
  der ursprüngliche Test grün (keine Bridge im Ladegraphen) und die
  Gegenprobe wird bei eingeschleustem Bridge-Import **rot**.
  - Test: Kern — derselbe Prüfling wie AC-9 aus S2, per `registerHooks`
    protokollierter Ladegraph, kein Dateiinhalt-Check.
  - Mutations-Gegenprobe: Ohne die ergänzte Gegenprobe würde der Test nach
    dem Umbau vakuum-grün — er bewiese dann nur noch, dass ein Objekt ohne
    `wiz`-Feld rendert, nicht dass die Bridge fehlt. Die Gegenprobe schließt
    genau diese Lücke.

- **AC-6 (Ratsche bewusst gepflegt — Strukturwächter, kein
  Verhaltensnachweis):** Given
  `context_herkunft_zweige_eingefroren.test.ts` hält heute 18
  `AlarmeTab.svelte`-Einträge in der eingefrorenen Soll-Liste,
  `EINGEFROREN_SOLL_ANZAHL = 67` / When im selben Commit wie der jeweilige
  Rückbau die 14 in der Schicksals-Tabelle als FÄLLT markierten Einträge
  bewusst gestrichen werden (die 4 BLEIBT-Einträge mit ihren neuen
  Zeilennummern nachgeführt) und `EINGEFROREN_SOLL_ANZAHL` auf 53 gesetzt wird
  (oder auf 54, falls die `:345`-Äquivalenz nicht beweisbar ist — siehe
  Implementation Details Punkt 3), mit Begründung je Eintrag in der
  Commit-Nachricht / Then ist der Ratschen-Test grün, und
  `alarme-tab/alarmeTabSections.ts:27,38,42` bleiben unverändert in der Liste.
  - Test: Kern — `node --test` auf `context_herkunft_zweige_eingefroren.test.ts`.
  - 🔴 Diese AC ist ein **Strukturwächter**, kein Verhaltensnachweis: die
    Zusicherung ist nicht „das Programm verhält sich richtig", sondern „die
    Zahl der HERKUNFT-Verzweigungen ist die, die diese Scheibe bewusst
    herbeigeführt hat" — eine Zeilenzahl-Prüfung wäre hier keine verbotene
    Dateiinhalt-Prüfung, weil sie eine strukturelle Eigenschaft (Anzahl +
    Fundorte einer Code-Kategorie), nicht einen Verhaltensnachweis ersetzt.
  - Mutations-Gegenprobe: Einen der 4 BLEIBT-Einträge zusätzlich aus
    `EINGEFROREN` streichen, ohne die zugehörige Bedingung im Quelltext zu
    entfernen ⇒ der reale Zählbefehl liefert den Eintrag weiterhin, der
    Mengenvergleich schlägt fehl (Ist-Menge enthält einen Eintrag, der nicht
    in der Soll-Liste steht).

## Known Limitations

- **Doppelquelle als Dauerzustand ist verboten.** „Wertprop wenn da, sonst
  `wiz`" ist genau das Anti-Muster, das S6 beseitigen soll — nur unter neuem
  Namen. Die Umstellung ist an allen drei Vergleichs-Mounts vollständig oder
  unterbleibt.
- **`:345` kann offen bleiben.** Gelingt der Äquivalenz-Beweis
  `context !== 'route'` ⇔ `!trip` in `/40` nicht sauber, bleibt `:345` stehen
  und die Ratsche endet bei 54 statt 53 (siehe Implementation Details Punkt
  3). Das ist ein zulässiges, dokumentiertes Ergebnis dieser Scheibe, kein
  Scheitern.
- **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`
  zurück** — `/70-deploy` überspringt dann die gesamte Staging-Validierung.
  Nach **jedem** Commit dieser Scheibe gegenlesen.
- **Zwei der drei Vergleichs-Mounts sind in der CI-Ampel strukturell
  unbewacht** (`/compare/new`, Mounts C/D) — deshalb trägt AC-3/AC-4 den
  Nachweis im Kern statt in einer weiteren E2E-Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Wertprops + Rückrufe statt `wiz` ist mit
  `CompareOutlookLayoutControls` (#1720 S1) und
  `CompareHourlyLayoutControls` (S6b, live `8207c157`) bereits entschieden
  und produktiv erprobt — diese Scheibe wendet dasselbe, bereits akzeptierte
  Muster auf den Alarme-Organismus an und trifft keine neue
  Architekturentscheidung. Die Bündel-Funktion `alarmePropsAus(wiz)` ist eine
  lokale Umsetzungsentscheidung innerhalb dieses Musters (begründet in
  Implementation Details Punkt 4), kein Architekturwechsel.

## Changelog

- 2026-09-21: Initial spec created (Scheibe S6c von #2276, Epic #2345)
