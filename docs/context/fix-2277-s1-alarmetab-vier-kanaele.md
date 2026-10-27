# Context: fix-2277-s1-alarmetab-vier-kanaele

## Request Summary
Scheibe S1 von #2277 (Anlege-Strecke-Konvergenz): `/trips/new` soll den geteilten
`shared/AlarmeTab.svelte` (`context="route"`) statt der Alt-Komponente
`AlertRulesEditor` zeigen — analog zu `/compare/new`, das `AlarmeTab
context="vergleich"` bereits nutzt. Schließt nebenbei #2229 (Alt-Komponente kennt
`premium_sms` nicht in der Kanalauswahl).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Mountet aktuell `AlertRulesEditor` an zwei Stellen (Zeile 862 Desktop, 1102 Mobile) mit `bind:rules={alertRules} activeChannels={activeAlertChannels}`. `activeAlertChannels` (Zeile 144) ist die Fundstelle von #2229: `(['email','telegram','sms'] as const).filter(...)` — kein `premium_sms`. `stubTrip` ($derived, Zeile 121) ist das bereits etablierte Muster für „Trip ohne Backend-ID" in dieser Datei; `VersandTab` und `WeatherMetricsTab` (mit `createMode={true}`) nutzen es schon. |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | Hält `alertRules?: AlertRule[]` im State (Zeile 98) und schreibt es beim Anlegen unverändert in `trip.alert_rules` (Zeile 151-152) — das ALTE Datenmodell (Array von Regeln). Muss für S1 durch das NEUE Modell ersetzt/ergänzt werden (siehe unten). |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Der geteilte Ziel-Organismus. Route-Zweig-Props: `trip`, `onTripUpdate`, `saveController`, `activeMetrics`, `metricLevels`, `onMetricLevelChange`, plus gemeinsame Felder `existingChannels`, `onChannelToggle`, `existingChannelThresholds`, `profileOverride`. **Kein `createMode`-Prop** (anders als `WeatherMetricsTab`). Speicherpfad des route-Zweigs (`buildAlarmeSaveFn`, Zeile ~399) ruft `baueTripSpeicherung<Trip>(api, trip!.id, ...)` — non-null Assertion auf `trip.id`, nur sicher wenn kein `saveController` übergeben wird (dann bleibt der Zweig inaktiv, Kommentar Zeile 127/435 — bisher nur für den Compare-Anlege-Fall dokumentiert, AC-7 aus #1258). |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` | Referenz-Muster für einen DIREKTEN (adapterlosen) route-Mount: liest `metricLevels`, `activeMetrics`, `existingChannels` (via `reconstructTripAlertChannels(trip)`) aus einem bereits **persistierten** `Trip` und reicht sie unverändert an `AlarmeTab` durch. Setzt `trip.id` voraus — für `/trips/new` NICHT direkt übertragbar. |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` | Adapter-Muster für den Compare-Zweig: übersetzt Wizard-Zustand in Wertprops + Rückrufe, KEIN Speicherzugriff nötig (Wizard hält den State, Compare speichert zentral beim „Anlegen"). Kommentar (Zeile 8-13) sagt ausdrücklich: gehört NICHT nach `shared/`, hat „bewusst kein Trip-Pendant" — Begründung war, dass der (damals einzige) Trip-Mount (Hub) adapterlos direkt speichert. Für die Anlege-Seite gilt diese Begründung nicht (kein `trip.id`) — hier braucht es ein eigenes, analoges Adapter-Muster für `route`, das noch nicht existiert. |
| `frontend/src/lib/components/shared/alarme-tab/tripChannelReconstruction.ts` | `reconstructTripAlertChannels(trip)` — rekonstruiert `existingChannels` aus einem persistierten Trip. Für einen frischen `stubTrip` ohne bisherige Alarm-Konfiguration liefert das vermutlich nur Vorgabewerte — zu prüfen in Analyse. |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Nutzt ebenfalls noch `AlertRulesEditor`/`EditReportConfigSection` (Zeile 10, 8) — **aber NICHT live gemountet** (kein `<TripEditView` in `frontend/src/routes` oder anderen `.svelte`-Dateien außer einem Kommentar und `bug_596.test.ts`). Tote Code-Fläche; für S1 irrelevant, gehört zu AC-5 (Aufräumen). |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Referenz für die Hydrations-Choreografie beim Mounten in einer Anlege-Seite: `alarmeHydrated`/`hydrateAlarmeTab()` lädt `alarmeCatalog` (`loadCompareSelectionEntries()`) vor dem ersten Render von `AlarmeTab` — analoges Katalog-Laden könnte auch für `/trips/new` nötig sein (`catalog`-Prop, `CompareSelectionEntry[]`). Zu klären: braucht der route-Zweig überhaupt `catalog`? (Props-Kommentar deutet auf reinen Compare-Bezug: „#1435 E1a-2").|

## Existing Patterns
- **Geteilter Organism mit `context`-Prop**: etabliertes Muster seit #1258/#2276 (`AlarmeTab`, `VersandTab`, `WeatherMetricsTab`, `CorridorEditor`) — S1 fügt sich ein, erfindet keine neue Architektur.
- **`stubTrip` + `createMode`**: `VersandTab` und `WeatherMetricsTab` sind in `TripNewEditor.svelte` bereits erfolgreich mit einem nicht-persistierten Trip-Objekt verdrahtet. `WeatherMetricsTab` hat dafür einen expliziten `createMode`-Prop, der den internen Autosave-Pfad abschaltet und stattdessen Änderungen über `onChannelsChange`/`onWeatherMetricsChange`/`onDayWindowChange`-Rückrufe nach oben reicht. `AlarmeTab` hat dieses Muster noch NICHT.
- **Adapter pro Kontext, nicht in `shared/`**: `compare/alarmePropsAus.ts` demonstriert das gewollte Muster — eine Kontext-eigene Übersetzungsschicht außerhalb von `shared/`, damit die HERKUNFT-Ratsche (`context_herkunft_zweige_eingefroren.test.ts`, 47 eingefrorene `context===`/`!==`-Verzweigungen unter `shared/`) nicht wächst.

## Dependencies
- **Upstream:** `AlarmeTab.svelte` selbst (muss ggf. um einen `createMode`-ähnlichen Guard erweitert werden, damit der Speicherpfad bei fehlendem `trip.id` nicht greift/crasht); `reconstructTripAlertChannels`; Backend-Schema für `display_config.metric_alert_levels` / `alert_channel_thresholds` (POST beim Anlegen muss diese Felder akzeptieren — zu verifizieren, ähnlich wie AC-2 für Korridore).
- **Downstream:** Kein bekannter Konsument von `activeAlertChannels`/`alertRules` in `TripNewEditor.svelte` außer dem Alt-Mount selbst und dem Payload-Aufbau in `tripNewLogic.ts`.

## Existing Specs
- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — Spec des geteilten `AlarmeTab` (Hub-Wiring S3, D4, AC-13..15). Enthält vermutlich die Begründung für „kein `createMode`" — vor der Analyse gegenlesen.
- `docs/specs/modules/rework_2276_s6c_*.md` (und benachbarte S6-Specs) — Muster für Compare-Adapter-Bau, als Vorlage für einen Route-Anlege-Adapter.

## Risks & Considerations
- **`AlarmeTab` fehlt ein `createMode`-Äquivalent.** Ohne `saveController`/`onTripUpdate` bleibt der interne Speicherzweig zwar inaktiv (verhindert den Crash auf `trip!.id`), aber es ist ungeklärt, ob und wie Änderungen dann überhaupt nach oben in `TripNewEditor` durchgereicht werden — die vorhandenen Rückrufe (`onMetricLevelChange`, `onChannelToggle`) wirken bereits jetzt direkt auf Wertprops, das könnte für die Anlege-Seite ausreichen, wenn `TripNewEditor` sie wie `wiz` im Compare-Fall gegenspiegelt. Muss in `/20-analyse` geklärt werden, ob `AlarmeTab.svelte` selbst angefasst werden muss (erhöht Blast Radius: 3 bestehende Mounts nicht brechen) oder ob ein reiner Adapter außenherum reicht.
- **Datenmodell-Bruch:** `tripNewLogic.ts` baut den Anlege-Payload aktuell aus `alertRules: AlertRule[]` (Alt-Modell). Der geteilte `AlarmeTab` arbeitet mit `metric_alert_levels`/Channel-Flags/`alert_channel_thresholds` (neues Modell, das der Hub bereits persistiert). Der Anlege-Payload-Builder muss auf das neue Modell umgestellt werden — Schema-Rework-Regel greift (Read-Modify-Write ist hier nicht relevant, da Neuanlage, aber `internal/model/*.go`/`src/app/models.py` ggf. betroffen, falls das Backend die POST-Route für Neuanlagen bisher nur `alert_rules` kennt, nicht `metric_alert_levels`).
- **HERKUNFT-Ratsche:** `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` friert 47 `context===`/`!==`-Fundstellen unter `shared/` ein. Ändert die Spec `AlarmeTab.svelte` selbst (z.B. neuer `createMode`-Guard), zählt jede neue `context`-Verzweigung gegen dieses Kontingent — Ratsche ggf. mit begründeter Ausnahme (S1-Eintrag im Kommentarkopf, analog S6c-S6g) nachführen, niemals kommentarlos wachsen lassen.
- **#2229 wirklich schließen:** Die im Issue genannte zweite Fundstelle `edit/TripEditView.svelte` ist tote Code-Fläche (nicht gemountet) — reicht als Begründung, #2229 trotzdem allein über den `TripNewEditor`-Fix zu schließen, ohne `TripEditView` anzufassen (das gehört zu AC-5/Aufräumen).
- **Katalog-Hydration:** Unklar, ob `AlarmeTab` im route-Zweig überhaupt einen `catalog`-Prop braucht (scheint compare-spezifisch für Feature #1435). Falls nicht, entfällt die in `CompareNewEditor` nötige Hydrations-Choreografie (`alarmeHydrated`) für S1 — spart Komplexität.

## Analysis

### Type
Bugfix/Rework (Scheibe S1 von Feature-Issue #2277, schließt #2229 mit)

### Kernbefund: `AlarmeTab.svelte` braucht einen `createMode`-Guard — zwei Zwänge widersprechen sich sonst

Code-Belege (gelesen, nicht vermutet):

1. **`$effect` (Zeile 414-429) speichert IMMER, wenn `trip` gesetzt ist.** Gate ist nur
   `if (!trip) return;` — danach `saveController.schedule(...)` ODER (ohne
   `saveController`) `void buildAlarmeSaveFn()()`. `buildAlarmeSaveFn()` ruft
   `baueTripSpeicherung(api, trip!.id, ...)` → ein echter `PUT
   /api/trips/__new__`, sobald `stubTrip` (Id `__new__`) als `trip` durchgereicht
   wird und der Nutzer einen Kanal/eine Metrik-Stufe ändert. `routeChannelState`
   (Zeile 306-311) und `routeMetricLevels` (Zeile 275-280) mutieren bei jeder
   Interaktion **immer lokal**, unabhängig davon, ob ein Rückruf zusätzlich
   existiert — nur bei Cooldown/Stille-Stunden gibt es einen `if (onCooldownChange)
   {…return;}`-Ausweg (Zeile 356-376). Ein reiner „`trip` weglassen"-Ansatz
   scheitert an Punkt 2.
2. **Die `sample`-Sektion (Zeile 565-571) verlangt `trip` zwingend im
   route-Zweig:** `<AlertPreviewCard trip={trip!} alertRules={trip?.alert_rules
   ?? []} />` — `trip!` ist eine Non-Null-Assertion, aber zur Laufzeit bricht das,
   wenn `trip` tatsächlich `undefined` ist (kein Guard, kein `vergleich`-Pendant
   wie bei `VTAlertSample`). `AlarmeTab` OHNE `trip` zu mounten ist also keine Option.

**Konsequenz:** `stubTrip` MUSS als `trip` durchgereicht werden (deckt Punkt 2),
UND `AlarmeTab.svelte` braucht einen neuen `createMode?: boolean`-Prop, der den
`$effect` an der Wurzel abschaltet (`if (!trip || createMode) return;`) — exakt
das Muster, das `WeatherMetricsTab` bereits für denselben Zweck hat. Ohne diesen
Guard feuert jede Kanal-/Metrik-Stufen-Änderung in `/trips/new` einen PUT auf
einen nicht existenten Trip.

Wichtig für den Blast Radius: `createMode` ist ein **eigenständiges Flag**, KEIN
`context===`/`context!==`-Vergleich — die HERKUNFT-Ratsche
(`context_herkunft_zweige_eingefroren.test.ts`, 47 eingefrorene Fundstellen)
zählt nur `context`-Verzweigungen und bleibt dadurch unberührt, keine
Ratschen-Ausnahme nötig. Die drei bestehenden Mounts (`AlarmeScheduleTab`,
`CompareTabs`-Hub, `CompareNewEditor` ×2) übergeben `createMode` nie →
Standardverhalten unverändert (Default `undefined`/falsy).

### Bereits geklärte offene Fragen aus dem Kontext (10-context)

- **Kein `catalog`-Prop nötig für route:** `effectiveActiveMetrics` (Zeile
  242-249) nutzt `activeMetricKeys`/`catalog` nur, wenn `activeMetricKeys !==
  undefined` — für route bleibt das undefiniert, der Zweig fällt auf
  `activeMetrics ?? []` zurück. Keine Katalog-Hydration für S1 nötig.
- **Kein Radar-Toggle im route-Kontext:** `alarmeTabSections()`
  (`alarmeTabSections.ts:11-30`) fügt die `radar`-Sektion strukturell NUR bei
  `context === 'vergleich'` ein — für S1 irrelevant.
- **Backend akzeptiert die neuen Felder beim Anlegen bereits, ungeprüft war das
  nicht nötig:** `CreateTripHandler` (`internal/handler/trip.go:158-212`)
  dekodiert den POST-Body direkt in `model.Trip` — `SendTelegram`, `SendSms`,
  `SendPremiumSms`, `AlertChannelThresholds` und `DisplayConfig` (Freiform-Map,
  trägt `metric_alert_levels`) sind reguläre Felder dieses Structs. **Kein
  Backend-Change nötig für S1.**
- **Datenmodell-Mismatch beim Default „Amtliche Warnungen":** `CreateTripHandler`
  setzt bei fehlendem `official_warnings` im Payload hart `enabled: false`
  (Zeile 186-188, Issue #1258 AC-4). `AlarmeTab` OHNE `trip.official_warnings`
  zeigt lokal aber `true` als Vorgabewert (Zeile 224-226:
  `trip?.official_warnings?.enabled ?? trip?.official_alert_triggers_enabled
  !== false` → `undefined !== false` = `true`). Mit `stubTrip` (kein
  `official_warnings`-Feld) zeigt die Oberfläche „an", das Backend würde bei
  fehlendem Feld im Payload aber „aus" persistieren — ein sichtbarer
  Trugschluss. Fix: `TripNewEditor` muss `officialWarningsEnabled={false}` +
  `onOfficialWarningsChange` explizit an `AlarmeTab` durchreichen (Wertprop
  überschreibt den lokalen Default, Zeile 227-229) UND diesen Wert aktiv in den
  Anlege-Payload schreiben.
- **`AlertRulesEditor` bleibt als Datei erhalten (kein Löschen in S1):**
  `legacy_wizard_removed.test.ts:100` hält `AlertRulesEditor` explizit auf einer
  „keep"-Liste; `edit/TripEditView.svelte` importiert die Komponente weiterhin
  (toter Code, nicht gemountet). S1 entfernt nur den MOUNT in
  `TripNewEditor.svelte`, nicht die Komponente selbst — Löschen ist AC-5,
  eigene Scheibe.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Neuer `createMode?: boolean`-Prop; `$effect`-Gate erweitern auf `if (!trip \|\| createMode) return;`. Kein neuer `context`-Vergleich (Ratsche unberührt). |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Mounts `AlertRulesEditor` (Zeile 862 Desktop, 1102 Mobile) durch `AlarmeTab context="route" trip={stubTrip} createMode={true} …` ersetzen; `activeAlertChannels`-Derivation (Zeile 144, kennt kein `premium_sms`, schließt #2229) entfernen; neuer lokaler State für Kanäle/Metrik-Stufen/Schwellen/`officialWarningsEnabled` aus den `AlarmeTab`-Rückrufen. |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | `CreateTripChannels` um `premium_sms` erweitern; `CreateTripState`/`buildCreateTripPayload` von `alertRules: AlertRule[]` (Alt-Modell) auf `metric_alert_levels`, `alert_channel_thresholds`, `send_telegram`/`send_sms`/`send_premium_sms`, `official_warnings` (Neu-Modell) umstellen. |
| `frontend/src/lib/components/trip-new/alarmePropsAus.ts` *(neu)* | CREATE | Adapter analog `compare/alarmePropsAus.ts` — übersetzt `TripNewEditor`-State in `AlarmeTab context="route"`-Props/Rückrufe. Bewusst AUSSERHALB `shared/`, damit die HERKUNFT-Ratsche nicht wächst (gleiche Begründung wie beim Compare-Pendant). |
| `frontend/src/lib/components/trip-new/__tests__/tripNewLogic.test.ts` | MODIFY | Bestehende `alertRules`-Payload-Assertions auf das neue Modell umstellen; neuer Test für `premium_sms`-Kanalflag. |
| `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` | MODIFY | `createMode`-Prop als Ergänzung dokumentieren (Spec ist Quelle der Wahrheit für `AlarmeTab`). |

Nicht angefasst (bewusst außerhalb S1, siehe oben): `organisms/index.ts`,
`alert-rules-editor/AlertRulesEditor.svelte`, `edit/TripEditView.svelte`,
`edit/EditReportConfigSection.svelte` — gehören zu AC-5 (Aufräumen, eigene Scheibe).

### Scope Assessment
- Files: 5 MODIFY + 1 CREATE (+ 1 Spec-Doku)
- Estimated LoC: ca. +150/-40 (grob: AlarmeTab-Guard ~8, TripNewEditor-Wiring ~60-80, tripNewLogic.ts ~30-40, neuer Adapter ~60-80, Tests zusätzlich) — **nah am 250-LoC-Workflow-Limit, `loc_limit_override` in `/40-tdd-red` wahrscheinlich nötig**, Doku zählt nicht mit.
- Risk Level: MEDIUM — greift in einen produktiv genutzten, geteilten Organism (`AlarmeTab.svelte`) ein, der von 3 weiteren Mounts genutzt wird; Guard ist additiv und default-transparent, Blast Radius durch bestehende Tests der anderen 3 Mounts absicherbar.

### Technical Approach
1. `AlarmeTab.svelte`: `createMode?: boolean`-Prop ergänzen, `$effect`-Gate um `|| createMode` erweitern. Kein Eingriff in Sektionen-Logik nötig (Katalog/Radar bereits korrekt route-exklusiv/-frei).
2. `trip-new/alarmePropsAus.ts`: neuer Adapter, der TripNewEditor-eigenen State (Kanäle inkl. `premium_sms`, Metrik-Stufen, Schwellen, `officialWarningsEnabled`) in die route-Props von `AlarmeTab` übersetzt — Rückrufe schreiben zurück in denselben State.
3. `TripNewEditor.svelte`: `AlertRulesEditor`-Mounts (Desktop+Mobile) durch `<AlarmeTab context="route" trip={stubTrip} createMode={true} activeMetrics={…} metricLevels={…} existingChannels={…} existingChannelThresholds={…} officialWarningsEnabled={false} {...alarmePropsAus(state)} />` ersetzen (Aufrufform als Markup-Ausdruck, nicht als eingefrorene Skript-Variable — Muster aus `compare/alarmePropsAus.ts`-Kommentar Zeile 15-19 übernehmen). `activeAlertChannels` entfernen.
4. `tripNewLogic.ts`: Payload-Builder auf das Neu-Modell umstellen, `official_warnings: { enabled: officialWarningsEnabled }` immer explizit mitschicken (schließt den Default-Mismatch).
5. Tests: `tripNewLogic.test.ts` aktualisieren; Adversary-Mutationsprobe insbesondere auf den `createMode`-Guard (Mutation: Guard entfernen → muss ein Test rot werden lassen, sonst Finding) und auf die Premium-SMS-Kanalwahl (#2229).

### Dependencies
- **Upstream:** keine Backend-Änderung nötig (bereits verifiziert). `AlarmeTab.svelte`-Änderung ist Voraussetzung für alles Weitere.
- **Downstream:** keine bekannten Konsumenten von `activeAlertChannels`/`alertRules` außerhalb des Alt-Mounts selbst.
- **Reihenfolge:** `AlarmeTab.svelte`-Guard zuerst (isoliert testbar gegen die 3 Bestandsmounts), dann Adapter, dann `TripNewEditor`-Wiring, dann `tripNewLogic.ts`-Payload.

### Open Questions
- [ ] Cooldown/Stille-Stunden/Radar sind in AC-1 nicht erwähnt — bleiben sie beim Anlegen auf Vorgabewert (nicht editierbar) oder sollen sie in S1 bereits mit-editierbar sein? (Radar entfällt strukturell für route ohnehin, s.o.) Empfehlung: Vorgabewert, editierbar erst im Hub nach dem Anlegen — hält S1 im LoC-Rahmen.

## Nachtrag (30-write-spec, vor Spec-Erstellung verifiziert — Code gelesen, nicht vermutet)

Der Kernbefund (createMode-Guard) ist bestätigt, aber vier Annahmen der Analyse
waren nach genauerem Lesen des AKTUELLEN `AlarmeTab.svelte` (Stand S6c,
`shared/AlarmeTab.svelte:73-475`) falsch oder unvollständig. Alle vier MÜSSEN
in die Spec einfließen:

1. **`displayChannelState` hackt `email: true` fest, sobald `sendTelegram`
   (Wertprop) gesetzt ist** (`AlarmeTab.svelte:294-305`: `sendTelegram ===
   undefined ? routeChannelState : {telegram, sms, premium_sms, email: true}`).
   Das ist für `context="vergleich"` richtig (E-Mail dort implizit), für
   `route`/Neuanlage FALSCH — der Trip-Alarm-E-Mail-Kanal ist ein echter,
   editierbarer Kanal mit eigenem Default (`NEW_ENTITY_DEFAULT`:
   `telegram:true, sms:true, email:false, premium_sms:false`,
   `alertChannelState.ts:27-32`). **Konsequenz:** Kanäle, Kanal-Schwellen UND
   Metrik-Level MÜSSEN im **lokalen Modus** bleiben (`sendTelegram`,
   `channelThresholds`, `metricAlertLevels` als Props **weglassen**, NICHT
   auf einen Wert setzen) — nur so bleibt `resolveAlertChannels`/
   `resolveAlertChannelThresholds` mit dem echten Neuanlage-Default aktiv und
   der E-Mail-Toggle bedienbar. Die drei zugehörigen Rückrufe
   (`onChannelToggle`, `onThresholdChange`, `onMetricLevelChange`) feuern
   auch im lokalen Modus **unbedingt** (kein Early-Return, anders als bei
   Amtlichen Warnungen — siehe Punkt 2) und liefern NUR das Delta
   (`kind`/`metric`+`level`), keinen Vollzustand. TripNewEditor muss deshalb
   einen eigenen Schatten-State führen, der mit **demselben** Default
   (`resolveAlertChannels(undefined)` bzw.
   `resolveAlertChannelThresholds(undefined)`, nicht von Hand kopiert) startet
   und dieselbe Deltalogik anwendet wie `AlarmeTab.svelte` intern
   (`{...bisher, [kind]: !bisher[kind]}` bzw. `applyThresholdChange`).
   `officialWarningsEnabled`/`cooldownMinutes`/`quietFrom`/`quietTo` sind von
   diesem Problem NICHT betroffen (kein Hardcode-Zweig) und können im
   Wertprop-Modus bleiben (Punkt 2).

2. **Amtliche Warnungen brauchen zwingend den Wertprop-Modus, sonst gibt es
   GAR KEINE Rückmeldung.** `handleOfficialWarningsToggle`
   (`AlarmeTab.svelte:230-236`) hat als einziger der Handler einen
   Early-Return im lokalen Modus (`if (officialWarningsEnabled === undefined)
   { routeOfficialWarningsEnabled = checked; return; }`) — der Rückruf
   `onOfficialWarningsChange` feuert dort NIE. Also: `officialWarningsEnabled`
   MUSS als Wertprop gesetzt werden (kein Hardcode-Risiko wie bei Kanälen).
   Default laut Backend-Beleg (`internal/handler/trip.go:178-181`): fehlt
   `official_warnings` im POST-Body, setzt `CreateTripHandler` hart
   `enabled: false`. Die Spec MUSS `officialWarningsEnabled` mit Vorgabewert
   `false` führen (nicht `true`, wie der bisherige route-lokale Default
   `routeOfficialWarningsEnabled` es für BESTANDS-Trips tut) — sonst zeigt
   die Anlege-Seite „an", persistiert aber „aus". Weil das eine sichtbare
   Verhaltensentscheidung ist (was der Nutzer beim Anlegen zuerst sieht),
   gehört sie als **eigene AC**, nicht in die Implementation Details versteckt.

3. **Einfach-Mount, dauerhaft gemountet — wie bei `WeatherMetricsTab`, nicht
   wie beim heutigen `AlertRulesEditor`.** Der jetzige Alt-Mount
   (`TripNewEditor.svelte:860-863` Desktop, `:1098-1101` Mobile) sitzt in
   `{#if activeTab === 'alerts'}` OHNE `isMobileViewport`-Gate — bei jedem
   Tab-Wechsel weg-und-zurück würde ein neu gemountetes `AlarmeTab` seinen
   internen State (`routeChannelState` u.a., NUR `$state`-initialisiert, kein
   `bind:`) auf den Anfangswert zurücksetzen und den Schatten-State in
   TripNewEditor widersprechen; zwei gleichzeitige Instanzen (Desktop+Mobile,
   ohne Viewport-Gate) schrieben unabhängig in denselben Rückkanal (identische
   Fehlerklasse wie WeatherMetricsTab Fix-Loop 3/4,
   `TripNewEditor.svelte:865-869`). **Fix:** `AlarmeTab` genau wie
   `WeatherMetricsTab` mounten — EINE Instanz über `{#if !isMobileViewport}`/
   `{#if isMobileViewport}` (Issue #932/#941-Muster), dauerhaft im DOM,
   Sichtbarkeit über `style:display={activeTab === 'alerts' ? '' : 'none'}`
   statt `{#if activeTab === 'alerts'}`. Das macht das ganze
   Remount-Sync-Problem gegenstandslos (State lebt genau einmal, die ganze
   Sitzung über).

4. **Kein neuer Adapter-Datei — Pendant-Sperre, und die Übersetzung ist
   keine reine `wiz`→Props-Spiegelung mehr.** `compare/alarmePropsAus.ts:8-13`
   sagt ausdrücklich „hat bewusst kein Trip-Pendant". Eine neue
   `trip-new/alarmePropsAus.ts` wäre genau das Gegenstück und liefe in
   `pendant_gate.py` (Gleichname-Erkennung über Präfix-Abgleich,
   `_gegenstueck()`) — nur mit `gz-eigenstaendig:`-Kopfzeile passierbar. Weil
   der Zuschnitt wegen Punkt 1 ohnehin KEINE reine Wertprop-Spiegelung ist
   (Kanäle/Schwellen/Metrik-Level brauchen echten Schatten-State mit eigener
   Deltalogik, kein Bündel-Objekt aus einer Quelle), gehört die Verdrahtung
   **inline in `TripNewEditor.svelte`** — genau das Muster, das dort für
   `WeatherMetricsTab` bereits über `handleChannelsChange`/
   `handleWeatherMetricsChange`/`handleDayWindowChange`
   (`TripNewEditor.svelte:341-377`) etabliert ist. Kein `trip-new/
   alarmePropsAus.ts` in den Affected Files.

5. **Payload-Feld-Korrektur (faktischer Fehler in der bisherigen Affected-
   Files-Zeile zu `tripNewLogic.ts`):** Es gibt KEIN autoritatives
   `send_telegram`/`send_sms`/`send_premium_sms` auf Trip-Ebene zu befüllen —
   diese drei Felder (`internal/model/trip.go:177-182`) sind laut
   Struct-Kommentar „ABGELEITET aus ReportConfig/Stages bei jedem Load
   (store.normalizeTrip) — nicht autoritativ" (Briefing-Kanäle, NICHT
   Alarm-Kanäle). Der tatsächliche Schreibweg für Alarm-Kanäle ist
   `AlertChannels *AlertChannelsConfig json:"alert_channels,omitempty"`
   (`trip.go:151`, Unterobjekt `{email,telegram,sms,premium_sms}` — exakt die
   Struktur, die `buildAlarmeDeliveryPayload()`
   (`shared/alarme-tab/alarmeDeliveryPayload.ts:106-117`) bereits für den PUT
   des Hub-Mounts baut). `CreateTripHandler`
   (`internal/handler/trip.go:158-176`) dekodiert den POST-Body direkt in
   `model.Trip` — kein Backend-Change nötig (das war schon richtig), aber
   `tripNewLogic.ts` muss `alert_channels`, `alert_channel_thresholds` und
   `display_config.metric_alert_levels` schreiben, NICHT die drei Flach-Felder.
   Empfehlung: `buildAlarmeDeliveryPayload()` direkt in `buildCreateTripPayload()`
   wiederverwenden (`currentDisplayConfig` = das bereits gebaute
   `{channels: state.channels, metrics: state.weatherMetrics}` als Basis
   übergeben, sonst überschreibt der `metric_alert_levels`-Spread die Report-
   `channels`/`metrics`-Schlüssel nicht additiv, sondern es fehlen sie, weil
   `buildAlarmeDeliveryPayload` `display_config` NEU aufbaut statt zu mergen).
   Reine Namensraum-Trennung bestätigt: `display_config.channels` (Bericht-
   Versand, `CreateTripChannels`) und `alert_channels` (Alarm-Zustellung) sind
   unabhängige Felder — keine Kollision zwischen Versand- und Alarm-Kanälen.

Diese fünf Punkte ersetzen/präzisieren den bisherigen „Kernbefund"- und
„Technical Approach"-Abschnitt oben, wo sie ihm widersprechen — der
Grundbefund (createMode-Guard nötig) bleibt unverändert richtig.
