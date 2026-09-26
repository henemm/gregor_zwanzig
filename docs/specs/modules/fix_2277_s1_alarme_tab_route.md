---
entity_id: fix_2277_s1_alarme_tab_route
type: bugfix
created: 2026-09-25
updated: 2026-09-25
status: draft
version: "1.1"
tags: [trip-new, alarme, alert-channels, premium-sms, shared-component]
---

# `/trips/new` nutzt den geteilten AlarmeTab (Issue #2277 Scheibe S1, schließt #2229)

## Approval

- [ ] Approved

## Purpose

Scheibe **S1** von #2277 (Anlege-Strecke-Konvergenz) ersetzt im Alarme-Reiter von
`/trips/new` die Alt-Komponente `AlertRulesEditor` (Regel-Array-Modell, kennt keinen
Premium-SMS-Kanal) durch den geteilten `AlarmeTab.svelte` (`context="route"`,
`createMode`) — denselben Baustein, den der Trip-Hub (`AlarmeScheduleTab.svelte`) und
der Ortsvergleich bereits nutzen. Das schließt nebenbei **#2229** (Kanalauswahl beim
Anlegen kennt kein Premium-SMS). `AlarmeTab.svelte` bekommt dafür einen neuen
`createMode?: boolean`-Prop, der seinen internen Selbst-Speicher-Pfad abschaltet —
exakt das Muster, das `WeatherMetricsTab.svelte` für denselben Zweck bereits hat.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/AlarmeTab.svelte`,
  `frontend/src/lib/components/trip-new/TripNewEditor.svelte`,
  `frontend/src/lib/components/trip-new/tripNewLogic.ts`,
  `frontend/src/lib/components/trip-new/__tests__/tripNewLogic.test.ts` (erweitert),
  `frontend/src/lib/components/trip-new/__tests__/trip_new_alarme_reiter.test.ts` (neu,
  SSR-Render über `tripNewSsr.ts`),
  `frontend/src/lib/components/shared/__tests__/alarme_tab_create_mode_guard.test.ts` (neu)
- **Identifier:** `AlarmeTab` (neuer Prop `createMode?: boolean`), Mount (A) Desktop
  `TripNewEditor.svelte:859-864`, Mount (B) Mobile `TripNewEditor.svelte:1099-1104`,
  `buildCreateTripPayload()` (`tripNewLogic.ts:117`), neue reine Funktionen
  `initialCreateTripAlarmState()`, `applyAlarmChannelToggle()`,
  `applyAlarmThresholdChange()`, `applyAlarmMetricLevelChange()` (alle
  `tripNewLogic.ts`, neu)

> **Schicht-Hinweis:** ausschließlich **Frontend**
> (`frontend/src/lib/components/`). Kein Go-API-Change nötig —
> `CreateTripHandler` (`internal/handler/trip.go:158-212`) dekodiert den POST-Body
> bereits direkt in `model.Trip`; `AlertChannels`, `AlertChannelThresholds`,
> `DisplayConfig`, `OfficialWarnings` sind reguläre, bereits vorhandene Felder
> (`internal/model/trip.go:117,145-157`). Kein Python-Core-Code betroffen.

## Nicht in dieser Scheibe

- **Wertebereiche (`CorridorEditor`), Reiter-Parität außerhalb Alarme, `?from=`-Vorlage,
  Mobile-Rahmen-Asymmetrien** — AC-2..AC-7 aus #2277 sind eigene Scheiben.
- **`CreateTripChannels`/`display_config.channels` (Bericht-Versand-Kanäle) bleiben
  unangetastet.** Das ist ein anderer Namensraum als `alert_channels` (Alarm-Zustellung,
  s. Implementation Details Punkt 4) — Premium-SMS wird in dieser Scheibe **nur** für
  Alarm-Kanäle ergänzt, nicht für die Bericht-Kanalauswahl. Kein Backend-Change, keine
  Erweiterung von `CreateTripChannels`.
- **`edit/TripEditView.svelte` wird nicht angefasst.** Die Datei importiert
  `AlertRulesEditor`/`EditReportConfigSection` weiterhin, ist aber nirgends live
  gemountet (kein `<TripEditView` außerhalb eines Kommentars und
  `bug_596.test.ts`) — Aufräumen ist AC-5 des Gesamt-Epics, eigene Scheibe.
- **`AlertRulesEditor.svelte` wird nicht gelöscht.** `legacy_wizard_removed.test.ts:100`
  hält die Komponente explizit auf einer „keep"-Liste (Export aus
  `organisms/index.ts` bleibt bestehen) — diese Scheibe entfernt nur den **Mount** in
  `TripNewEditor.svelte`, nicht die Komponente selbst.
- **Radar-Alarm ist beim Anlegen strukturell nicht vorhanden.**
  `alarmeTabSections('route')` enthält keine `radar`-Sektion (s.
  `alarme-tab/alarmeTabSections.ts:11-30`) — keine eigene Handhabung nötig.
- **Kein neuer Adapter (`trip-new/alarmePropsAus.ts`).** `compare/alarmePropsAus.ts:8-13`
  dokumentiert ausdrücklich „kein Trip-Pendant". Eine gleichnamige Datei liefe in die
  Pendant-Sperre (`.claude/hooks/pendant_gate.py`); inhaltlich ist die Verdrahtung
  ohnehin keine reine Bündel-Spiegelung (s. Implementation Details Punkt 2). Die
  Verdrahtung gehört **inline in `TripNewEditor.svelte`**, analog
  `handleChannelsChange`/`handleWeatherMetricsChange`/`handleDayWindowChange`
  (`TripNewEditor.svelte:341-377`).
- **Der bestehende AlarmeTab-Vergleichs-Zweig (`context="vergleich"`) und der
  Trip-Hub-Zweig (`AlarmeScheduleTab.svelte`) werden nicht verändert.** Der neue
  `createMode`-Guard ist additiv und default-transparent (Default `undefined`/falsy —
  Standardverhalten der 3 Bestandsmounts unverändert).

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Neuer `createMode?: boolean`-Prop (Destrukturierung `:146-183`); Selbst-Speicher-`$effect` (`:414-429`) Gate von `if (!trip) return;` auf `if (!trip \|\| createMode) return;` erweitert. Kein neuer `context`-Vergleich — die HERKUNFT-Ratsche (`context_herkunft_zweige_eingefroren.test.ts`) bleibt unberührt. |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | `AlertRulesEditor`-Mounts (Desktop `:862`, Mobile `:1102`) durch `<AlarmeTab context="route" trip={stubTrip} createMode={true} …>` ersetzen (Muster `WeatherMetricsTab`-Mount `:879-883`/`:1111-1115`: `{#if !isMobileViewport}`/`{#if isMobileViewport}`-Gate, EINE dauerhafte Instanz, Sichtbarkeit über `style:display`); `import { AlertRulesEditor } from '$lib/components/organisms'` (`:18`), `activeAlertChannels`-Derivation (`:144`), `let alertRules = $state<AlertRule[]>([])` (`:90`) entfernen; EIN neuer Schatten-State `let alarm = $state<CreateTripAlarmState>(initialCreateTripAlarmState());` + sechs schlanke Rückruf-Handler, die ausschließlich die reinen Funktionen aus `tripNewLogic.ts` aufrufen (kein eigener Delta-Code in der Komponente); minimaler `metricsCatalog`-Ladepfad für die Alarm-Metrik-Zeilen (s. Implementation Details Punkt 6). |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | Neuer Export `CreateTripAlarmState` (Interface) + vier reine Funktionen `initialCreateTripAlarmState()`, `applyAlarmChannelToggle(state, kind)`, `applyAlarmThresholdChange(state, kind, level)`, `applyAlarmMetricLevelChange(state, metric, level)` — nutzen `resolveAlertChannels`/`resolveAlertChannelThresholds`/`applyThresholdChange` aus `../shared/alarme-tab/alertChannelState.ts` (keine eigene Delta-Logik zweimal geschrieben); `CreateTripState.alarm?: CreateTripAlarmState` (optional, Default via `initialCreateTripAlarmState()` — bestehende Aufrufer ohne `alarm`-Feld, z.B. `trip_new_versandkanaele_unabhaengig_von_metriken.test.ts:152-158`, bleiben unverändert lauffähig); `alertRules?: AlertRule[]` (Alt-Modell, `:98`) entfernen; `buildCreateTripPayload()` ruft `buildAlarmeDeliveryPayload()` (Wiederverwendung) mit `currentDisplayConfig = trip.display_config` (bereits aus `channels`/`metrics` gebaut) und merged das Ergebnis additiv in `trip` (Read-Modify-Write, kein Replace); alter `alertRules`-Schreibblock (`:151-153`) entfernt. |
| `frontend/src/lib/components/trip-new/__tests__/tripNewLogic.test.ts` | MODIFY | Bestehende `alertRules`-Payload-Assertions entfernen/ersetzen; neue Tests für `initialCreateTripAlarmState()`/die drei Delta-Funktionen (reine Funktionstests) sowie für `alert_channels` (inkl. `premium_sms`), `alert_channel_thresholds`, `display_config.metric_alert_levels` (additiv zu `channels`/`metrics`), `official_warnings.enabled` (Default `false`, gelesen über `initialCreateTripAlarmState()`, nicht per Hand-Literal — s. AC-4), `alert_cooldown_minutes`/`alert_quiet_from`/`alert_quiet_to`. |
| `frontend/src/lib/components/trip-new/__tests__/trip_new_alarme_reiter.test.ts` *(neu)* | CREATE | Echtes SSR-Rendering der Produktivkomponente über die bestehende Harness `tripNewSsr.ts`/`renderTripNew()` (Issue #1738, bereits vorhanden — keine neue Test-Infrastruktur nötig): Mount-Ersetzung, Premium-SMS-Sichtbarkeit, E-Mail-Default-AUS, Ein-Instanz-Zusicherung über Viewport-/Tab-Kombinationen (AC-1, AC-3, AC-6). |
| `frontend/src/lib/components/shared/__tests__/alarme_tab_create_mode_guard.test.ts` *(neu)* | CREATE | Wirkort-Test im Kern über `effekteVon()`/`umgebungFuer()` (`svelteInstanzPruefstand.ts:82,195`) gegen `AlarmeTab.svelte`, mit `baueTripSpeicherung` als gesäter Spion (s. AC-2 Testrezept) — kein realer Netzwerkzugriff möglich. |

**Zu prüfen, ob eine Saat-Anpassung nötig ist** (fahren den route-Pfad, keiner davon
zwingend zu ändern — Prüfpflicht, nicht Änderungspflicht):
`alarme_save_single_writer.test.ts`, `alarme_tab_catalog_prop_structure.test.ts`,
`alarme_delivery_payload_preserves_inactive_levels.test.ts`,
`trip_new_versandkanaele_unabhaengig_von_metriken.test.ts` (ruft
`buildCreateTripPayload()` ohne `alarm`-Feld auf — muss nach der Umstellung unverändert
grün bleiben, weil `alarm` optional mit Default ist).

Nicht angefasst (bewusst außerhalb S1, siehe „Nicht in dieser Scheibe"):
`organisms/index.ts`, `alert-rules-editor/AlertRulesEditor.svelte`,
`edit/TripEditView.svelte`, `edit/EditReportConfigSection.svelte`,
`docs/specs/_archive/modules/issue_1258_alarme_tab_official_warnings.md` (archiviert —
diese Spec ist der aktuelle Änderungsnachweis für den neuen `createMode`-Prop, analog
zu `rework_2276_s2_alarme.md`/`rework_2276_s6c_alarme.md`, die frühere Änderungen an
`AlarmeTab.svelte` je eigenständig dokumentieren, statt die archivierte Ursprungs-Spec
fortzuschreiben).

## Estimated Scope

- **LoC (produktiv, geschätzt):** ca. +140 / −25 — unter dem 250-LoC-Limit, aber
  **nicht komfortabel**. `workflow.py status` ist vor jeder Override-Ankündigung in
  `/50` die maßgebliche Quelle, nicht diese Schätzung.
- **Files:** 3 produktiv (`AlarmeTab.svelte`, `TripNewEditor.svelte`,
  `tripNewLogic.ts`), 3 Testdateien (2 neu, 1 erweitert) — Testdateien zählen nicht
  gegen das LoC-Limit.
- **Effort:** medium.
- **Risk Level: MEDIUM.** `AlarmeTab.svelte` ist ein produktiv genutzter, geteilter
  Organismus (3 weitere Mounts: Trip-Hub, Vergleichs-Hub, 2× Compare-Anlege) — der
  neue Guard ist additiv und default-transparent, Blast Radius durch die bestehenden
  Tests der anderen Mounts absicherbar. Die neue, spezifische Fehlerklasse dieser
  Scheibe (Schatten-State-Sync) ist durch die Verlagerung der Delta-Logik in reine,
  wiederverwendbare Funktionen (`tripNewLogic.ts`) UND deren direkte Verwendung in den
  Payload-Rundreise-Tests (AC-4/AC-5) strukturell eingedämmt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherMetricsTab.svelte` (`createMode`-Prop, `TripNewEditor.svelte:879-883`) | component | Lebender Präzedenzfall für „Einfach-Mount, dauerhaft im DOM, Sichtbarkeit über `style:display`, EIN Guard-Flag schaltet den Selbst-Speicher-Pfad ab" |
| `alarme-tab/alertChannelState.ts` (`resolveAlertChannels`, `resolveAlertChannelThresholds`, `applyThresholdChange`) | module | Bereits vorhandene, reine Funktionen für Default + Deltalogik — `initialCreateTripAlarmState()`/`applyAlarm*()` in `tripNewLogic.ts` rufen sie auf, statt sie nachzubauen (sonst Drift zwischen `AlarmeTab`-internem State und Schatten-State) |
| `alarme-tab/alarmeDeliveryPayload.ts` (`buildAlarmeDeliveryPayload`) | module | Bereits vorhandener Payload-Builder (nutzt der Trip-Hub-Zweig von `AlarmeTab.svelte:386-397` bereits) — `tripNewLogic.ts` ruft dieselbe Funktion wieder auf |
| `alarme-tab/tripAlertMetricsFromCatalog.ts` (`deriveActiveAlertMetricsForTrip`) | module | Dieselbe Ableitung, die `AlarmeScheduleTab.svelte:51-53` für den Trip-Hub nutzt — liefert `activeMetrics` aus `weatherMetrics` + Katalog |
| `alarme-tab/tripChannelReconstruction.ts` (`reconstructTripAlertChannels`) | module | Liest **nur Kanäle** aus `trip.alert_channels` (mit Legacy-Fallback auf `report_config.send_*`, `tripChannelReconstruction.ts:18-43`) — Rundreise-Nachweis in AC-4/AC-5 nutzt diese Funktion für Kanäle UND liest Schwellen/Metrik-Level über die beiden ANDEREN Pfade, die `AlarmeScheduleTab.svelte:66-68` tatsächlich benutzt (`trip.alert_channel_thresholds`, `trip.display_config?.metric_alert_levels`) — **keine** eigene Rekonstruktionsfunktion für diese beiden erfinden. |
| `internal/handler/trip.go:158-212` (`CreateTripHandler`) | Go-Handler | Dekodiert POST-Body direkt in `model.Trip` — akzeptiert `alert_channels`, `alert_channel_thresholds`, `display_config`, `official_warnings` bereits ohne Änderung; setzt bei fehlendem `official_warnings` hart `enabled: false` (`:186-188`) |
| `trip-new/__tests__/tripNewSsr.ts` (`renderTripNew`, `countTestid`, `bereichVon`, `outerHtml`) | Prüfstand | Bereits vorhandene SSR-Render-Harness für `TripNewEditor.svelte` (Issue #1738) — rendert die ECHTE Komponente über `svelte/server`, keine Quelltext-Greps. Wird für AC-1/AC-3/AC-6 wiederverwendet, keine neue Infrastruktur. |
| `shared/__tests__/svelteInstanzPruefstand.ts` (`umgebungFuer`, `effekteVon`) | Prüfstand | Führt `$effect`-Rümpfe wirklich aus (SSR-Prüfstand verwirft sie sonst); Import-Bindungen, die bereits in der Saat stehen, werden NICHT durch den echten Modul-Import überschrieben (`:132`) — Grundlage für den gefahrlosen `baueTripSpeicherung`-Spion in AC-2 |
| `docs/specs/modules/rework_2276_s6c_alarme.md` | spec | Formvorbild dieser Spec (Detailtiefe, Wirkort-je-Zusicherung, Mutations-Gegenproben) |

## Implementation Details

### Design-Entscheidungen

1. **`AlarmeTab.svelte` bekommt genau EINEN neuen Guard, keine neue `context`-Verzweigung.**
   Der Selbst-Speicher-`$effect` (`:414-429`) feuert heute bei jeder Kanal-/Metrik-Stufen-/
   Amtliche-Warnungen-Änderung, sobald `trip` gesetzt ist (`if (!trip) return;`) — ein PUT
   auf `/api/trips/__new__`, sobald `stubTrip` (Id `__new__`) als `trip` durchgereicht
   wird. Fix: `if (!trip || createMode) return;`. Die `sample`-Sektion (`:570`,
   `<AlertPreviewCard trip={trip!} …>`) verlangt weiterhin zwingend ein gesetztes
   `trip` im route-Zweig — `stubTrip` muss also trotzdem durchgereicht werden, der Guard
   verhindert nur den Speicherpfad, nicht die Anzeige. **Der Alarm-Schatten-State
   fließt NICHT in `stubTrip` ein** — `stubTrip` ($derived, `TripNewEditor.svelte:121-128`)
   bleibt exakt wie heute aus `name`/`stages`/`selectedActivity`/`channels`/
   `weatherMetrics`/`reportConfig` gebaut. Würde der Alarm-State zusätzlich in
   `stubTrip` einfließen, erzeugte jede Kanal-/Schwellen-Änderung eine neue
   `stubTrip`-Referenz und damit eine neue `trip`-Prop-Referenz an `AlarmeTab` —
   dieselbe `effect_update_depth_exceeded`-Fehlerklasse, die
   `handleWeatherMetricsChange`/`handleDayWindowChange` bereits dokumentieren
   (`TripNewEditor.svelte:349-355,366-369`).

2. **Kanäle, Kanal-Schwellen, Metrik-Level bleiben im lokalen Modus von `AlarmeTab`
   (Wertprops `sendTelegram`/`channelThresholds`/`metricAlertLevels` bleiben
   `undefined`) — der Schatten-State lebt als reine, exportierte Funktionen in
   `tripNewLogic.ts`, nicht als Ad-hoc-Code in der Komponente.**
   `displayChannelState` (`AlarmeTab.svelte:295-305`) hackt `email: true` fest, sobald
   `sendTelegram` eine Wertprop ist — für `context="vergleich"` richtig, für
   `route`/Neuanlage falsch: der Trip-Alarm-E-Mail-Kanal ist ein echter, editierbarer
   Kanal mit eigenem Default (`NEW_ENTITY_DEFAULT`: `telegram:true, sms:true,
   email:false, premium_sms:false`, `alertChannelState.ts:29-34`). Bleiben die drei
   Wertprops weg, verwaltet `AlarmeTab` seinen `routeChannelState`/
   `routeChannelThresholds`/`routeMetricLevels` intern selbst — die sichtbaren
   Bedienelemente funktionieren unverändert. `TripNewEditor.svelte` erfährt Änderungen
   NUR über die drei Rückrufe `onChannelToggle(kind)` (unbedingt, `:306-311`),
   `onThresholdChange(kind, level)` (unbedingt, `:339-344`),
   `onMetricLevelChange(metric, level)` (unbedingt, `:275-280`) — jeder liefert nur das
   Delta. **Damit der Schatten-State garantiert mit demselben Default startet und
   dieselbe Deltalogik anwendet wie `AlarmeTab.svelte` intern, liegt diese Logik als
   VIER reine, exportierte Funktionen in `tripNewLogic.ts`** (nicht als eigener Code in
   `TripNewEditor.svelte`):
   - `initialCreateTripAlarmState(): CreateTripAlarmState` — baut
     `{officialWarningsEnabled: false, cooldownMinutes: undefined, quietFrom: undefined,
     quietTo: undefined, channels: resolveAlertChannels(undefined), channelThresholds:
     resolveAlertChannelThresholds(undefined), metricLevels: {}}` — importiert
     `resolveAlertChannels`/`resolveAlertChannelThresholds` aus
     `../shared/alarme-tab/alertChannelState.ts`, kopiert den Default nicht von Hand.
   - `applyAlarmChannelToggle(state, kind): CreateTripAlarmState` — spiegelt
     `AlarmeTab.svelte:308` (`{...routeChannelState, [kind]: !routeChannelState[kind]}`).
   - `applyAlarmThresholdChange(state, kind, level): CreateTripAlarmState` — ruft
     `applyThresholdChange()` (bereits vorhanden) auf `state.channelThresholds` an.
   - `applyAlarmMetricLevelChange(state, metric, level): CreateTripAlarmState` —
     spiegelt `AlarmeTab.svelte:277` (`{...routeMetricLevels, [metric]: level}`).
   `TripNewEditor.svelte` hält dazu EINEN Schatten-State
   `let alarm = $state<CreateTripAlarmState>(initialCreateTripAlarmState());` und drei
   Ein-Zeilen-Handler, die die jeweilige Funktion aufrufen und `alarm` neu zuweisen —
   kein eigener Delta-Code in der Komponente, damit ein AST-/Payload-Test in
   `tripNewLogic.test.ts` dieselbe Logik prüft, die auch produktiv läuft (s. AC-4/AC-5).

3. **Amtliche Warnungen, Cooldown, Stille Stunden bleiben im Wertprop-Modus (volle
   Werte, kein Delta) — Teil desselben `alarm`-Schatten-States.**
   `handleOfficialWarningsToggle` (`AlarmeTab.svelte:230-236`) hat als einziger der
   Handler einen Early-Return im lokalen Modus — `onOfficialWarningsChange` feuert dort
   NIE. `officialWarningsEnabled` MUSS also als Wertprop gesetzt werden. Vorgabewert
   **`false`** (nicht `true`, wie der route-lokale Default für Bestands-Trips) —
   Begründung: `CreateTripHandler` setzt bei fehlendem `official_warnings` im
   POST-Body hart `enabled: false` (`internal/handler/trip.go:186-188`); mit
   Vorgabewert `true` zeigte die Anlege-Seite „an", persistierte beim ersten
   Speichern ohne Nutzerinteraktion aber „aus" — ein sichtbarer UI/Persistenz-Mismatch.
   Cooldown/Stille-Stunden sind von diesem Problem nicht betroffen (kein Hardcode-Zweig
   in `AlarmeTab`) und sind in dieser Scheibe **bewusst bereits beim Anlegen
   editierbar** (Abweichung von der ursprünglichen Analyse-Empfehlung „nur
   Vorgabewert, editierbar erst im Hub" — der Wertprop-Modus macht das ohne
   Zusatzaufwand möglich, ein künstliches Sperren wäre zusätzlicher, unbegründeter
   Code). Handler schreiben direkt `alarm = {...alarm, officialWarningsEnabled: an}`
   bzw. die entsprechenden Felder — keine eigene Reducer-Funktion nötig, weil hier
   (anders als bei Kanälen/Schwellen/Metrik-Level) kein Delta-Risiko besteht: der
   Rückruf liefert bereits den vollständigen neuen Wert.

4. **Zwei-Namensraum-Trennung: `alert_channels` ≠ `display_config.channels`.** Es
   gibt kein autoritatives `send_telegram`/`send_sms`/`send_premium_sms` auf
   Trip-Ebene zu befüllen — diese drei Felder (`internal/model/trip.go:178-182`)
   sind laut Struct-Kommentar „ABGELEITET aus ReportConfig/Stages … nicht
   autoritativ" (Briefing-Kanal-Spiegel, kein Schreibweg für Alarm-Kanäle). Der
   tatsächliche Schreibweg für Alarm-Kanäle ist
   `AlertChannels *AlertChannelsConfig json:"alert_channels,omitempty"`
   (`trip.go:151`) — exakt die Struktur, die `buildAlarmeDeliveryPayload()`
   (`alarme-tab/alarmeDeliveryPayload.ts:106-117`) bereits für den PUT des
   Hub-Mounts baut. `tripNewLogic.ts` ruft dieselbe Funktion wieder auf, statt
   Feldnamen ein zweites Mal abzuschreiben. `CreateTripChannels`
   (`display_config.channels`, Bericht-Versand) bleibt unverändert und unabhängig —
   keine Kollision zwischen Versand- und Alarm-Kanälen.

5. **Read-Modify-Write beim `display_config`-Merge (CLAUDE.md „Daten-Schema-Reworks").**
   `buildAlarmeDeliveryPayload()` schreibt `payload.display_config =
   {...(currentDisplayConfig ?? {}), metric_alert_levels: state.metricLevels}`
   (`alarmeDeliveryPayload.ts:130-135`) — additiv, NUR wenn `currentDisplayConfig`
   bereits `channels`/`metrics` enthält. `buildCreateTripPayload()` MUSS deshalb das
   bereits gebaute `trip.display_config = {channels: state.channels, metrics:
   state.weatherMetrics ?? []}` (`tripNewLogic.ts:142-145`) als
   `currentDisplayConfig` übergeben, **bevor** der Alarm-Merge passiert — sonst
   fehlen `channels`/`metrics` im finalen `display_config` (Ersetzen statt Mergen,
   dieselbe Fehlerklasse wie BUG-DATALOSS-GR221 #102).

6. **Minimaler `metricsCatalog`-Ladepfad für `activeMetrics`.** `TripNewEditor.svelte`
   lädt heute keinen Metrik-Katalog — `WeatherMetricsTab.svelte` holt sich seinen
   eigenen internen Katalog (`api.get<MetricCatalog>('/api/metrics')`, `:544`),
   exponiert ihn aber nicht als Prop/Callback nach außen. Damit der Alarme-Reiter
   beim Anlegen dieselben Zeilen zeigt wie der Trip-Hub, lädt `TripNewEditor.svelte`
   selbst minimal `api.get<MetricCatalog>('/api/metrics')` (`onMount`, fail-soft wie
   `WeatherMetricsTab.svelte:535-537`: Katalog bleibt `{}` bei Fehler) und leitet
   `activeMetrics` über die bereits vorhandene, reine Funktion
   `deriveActiveAlertMetricsForTrip(weatherMetrics, metricsCatalog)`
   (`alarme-tab/tripAlertMetricsFromCatalog.ts:58`, dieselbe Funktion wie
   `AlarmeScheduleTab.svelte:51-53`) ab. **Dieser Ladepfad selbst ist NICHT durch
   eine eigene AC bewacht** (s. Known Limitations) — er ist fail-soft und ändert
   nichts an den Kanal-/Schwellen-/Amtliche-Warnungen-Bedienelementen, die den
   Kern der ACs bilden.

### Wirkort je Zusicherung

- **Selbst-Speicher-Effekt schweigt bei `createMode` (AC-2)** → **Kern**, über
  `effekteVon()`/`umgebungFuer()` (`svelteInstanzPruefstand.ts:82,195`) gegen
  `AlarmeTab.svelte` direkt. Der SSR-Prüfstand verwirft `$effect`-Rümpfe sonst
  (Lehre aus S6b-Adversary-Finding F001). **Wichtig:** das JSON-Diff-Gate
  (`AlarmeTab.svelte:416-425`) vergleicht gegen eine Baseline, die aus denselben
  gesäten Werten berechnet wird wie der spätere Effekt-Lauf — ohne eine gezielte
  Nach-Mutation eines `route*`-Werts in `u` NACH `umgebungFuer()` wäre der Test in
  BEIDEN Fällen (`createMode` an/aus) gleichermaßen grün (0 Aufrufe), weil das
  Diff-Gate schon vor dem eigentlichen Guard-Vergleich early-returnt. Details im
  Testrezept unter AC-2.
- **Mount-Ersetzung, Premium-SMS-Sichtbarkeit, E-Mail-Default, Ein-Instanz (AC-1,
  AC-3, AC-6)** → **Kern, aber echtes SSR-Rendering statt Quelltext-Inspektion.**
  `frontend/src/lib/components/trip-new/__tests__/tripNewSsr.ts` rendert die ECHTE
  `TripNewEditor.svelte` bereits serverseitig (`svelte/server`, Issue #1738) — diese
  Scheibe nutzt dieselbe Harness weiter, keine neue Infrastruktur. Reine
  Quelltext-Regex-Checks (wie im `WeatherMetricsTab`-createMode-Präzedenzfall
  `weather_metrics_tab_create_mode_callback.test.ts`) wären hier vermeidbar, weil die
  Render-Harness bereits existiert und CLAUDE.md Dateiinhalt-Checks als
  Verhaltensnachweis verbietet, wo ein echter Nachweis möglich ist.
- **Rundreise Payload → Rekonstruktion über die drei ECHTEN Lesewege (AC-4/AC-5)**
  → **Kern**, echter Aufruf von `buildCreateTripPayload()` gefolgt von
  `reconstructTripAlertChannels()` (Kanäle) + direktem Lesen von
  `trip.alert_channel_thresholds` (Schwellen) + `trip.display_config
  ?.metric_alert_levels` (Metrik-Level) — exakt die drei Pfade, die
  `AlarmeScheduleTab.svelte:56,66-68` beim Öffnen eines Bestandstrips benutzt.
  Reine Funktionen, kein Netzwerk nötig.
- **Kein Live-E2E in dieser Scheibe.** Weder `issue-661-trip-new-mobile.spec.ts` noch
  `trip-new-loads-without-effect-loop.spec.ts` berühren den Alarme-Reiter (grep-geprüft,
  keine Regression durch diese Änderung an bestehenden Specs). Der volle
  Erstell-Durchlauf ist über AC-4/AC-5 im Kern bit-genau nachgewiesen (echter
  Payload-Builder + echte Rekonstruktionswege); der manuelle Staging-Klick-Durchlauf
  (Pflicht bei jeder UI-Änderung, `docs/reference/operations_playbook.md`) bleibt bei
  `/70-deploy` bestehen.

## Expected Behavior

- **Input:** Im Alarme-Reiter von `/trips/new` (Desktop und Mobile) werden Amtliche
  Warnungen (Default aus), Metrik-Alarmschwellen (leer, bis Metriken im
  Wetter-Metriken-Reiter gewählt sind), Kanäle (Telegram/SMS an, E-Mail/Premium-SMS
  aus — Neuanlage-Default), Kanal-Schwellen (je Kanal „gering"), Cooldown und Stille
  Stunden bedient — dieselben Bedienelemente wie im Trip-Hub, nur ohne eigenen
  Speicherpfad.
- **Output:** Änderungen bleiben lokal im Anlege-Dialog (kein PUT), bis der Nutzer
  auf „Speichern" klickt — dann fließen sie als Teil des EINEN `POST /api/trips` in
  `alert_channels`, `alert_channel_thresholds`, `display_config.metric_alert_levels`,
  `official_warnings`, `alert_cooldown_minutes`, `alert_quiet_from`,
  `alert_quiet_to`.
- **Side effects:** Keine. Der `createMode`-Guard macht `AlarmeTab.svelte` im
  Anlege-Kontext seiteneffektfrei bzgl. Netzwerkzugriffen (außer dem bereits
  bestehenden, ungeänderten `/api/auth/profile`-Fetch für das Premium-SMS-Gate,
  `AlarmeTab.svelte:192-202`, und dem neuen, fail-soften `/api/metrics`-Fetch in
  `TripNewEditor.svelte`).

## Acceptance Criteria

- **AC-1:** Given `/trips/new` zeigt im Alarme-Reiter heute `AlertRulesEditor`
  (`data-testid="alert-rules-editor"`, Regel-Array-Modell, Kanalauswahl ohne
  Premium-SMS, `TripNewEditor.svelte:862,1102`) / When der Mount an beiden Stellen
  (Desktop, Mobile) durch `<AlarmeTab context="route" trip={stubTrip}
  createMode={true} …>` ersetzt wird / Then rendert `renderTripNew({activeTab:
  'alerts', isMobileViewport: false})` (echtes `svelte/server`-Rendering,
  `tripNewSsr.ts`) genau ein `data-testid="alarme-tab"`, null
  `data-testid="alert-rules-editor"` und genau ein
  `data-testid="alert-channel-toggle-premium_sms"` (Premium-SMS-Kanalzeile aus
  `AlertChannelPicker.svelte:148`, schließt #2229).
  - Test: Kern — `frontend/src/lib/components/trip-new/__tests__/trip_new_alarme_reiter.test.ts`,
    `renderTripNew()` + `countTestid()` (beide aus `tripNewSsr.ts`).
  - Mutations-Gegenprobe: `AlertRulesEditor`-Mount an einer der beiden Stellen
    wiederherstellen ⇒ `alert-rules-editor` taucht wieder auf UND `alarme-tab`
    fehlt an dieser Stelle ⇒ Test wird rot.

- **AC-2:** Given der Selbst-Speicher-`$effect` in `AlarmeTab.svelte` (`:414-429`)
  feuert heute bei jeder Kanal-/Metrik-Stufen-Änderung, sobald `trip` gesetzt ist,
  über `buildAlarmeSaveFn()` → `baueTripSpeicherung(api, trip!.id, …)`
  (`shared/tripSpeicherung.ts:32-42`, reine Konstruktion, kein I/O bis die
  zurückgegebene Funktion aufgerufen wird) / When `stubTrip` (Id `__new__`) als
  `trip` UND `createMode={true}` übergeben werden / Then bleibt der Effekt-Rumpf
  wirkungslos — `baueTripSpeicherung` wird kein einziges Mal aufgerufen.
  - Test: Kern — `alarme_tab_create_mode_guard.test.ts`. Rezept:
    1. `umgebungFuer('AlarmeTab.svelte', { trip: stubTrip, createMode: true,
       baueTripSpeicherung: spion })` — `spion` ist eine gesäte Zähl-Attrappe; nach
       der Import-Bindungsregel von `umgebungFuer()` (`svelteInstanzPruefstand.ts:132`,
       „`lokal in u` → real-Import wird NICHT gebunden") ersetzt sie die echte
       `baueTripSpeicherung`-Bindung vollständig, kein `api`/Netzwerkzugriff möglich.
    2. Danach GEZIELT `u.routeChannelState` verändern (z.B. `premium_sms` umdrehen)
       — ohne diesen Schritt wäre der Test in beiden Fällen (`createMode` an/aus)
       gleichermaßen grün, weil das JSON-Diff-Gate (`:416-425`) sonst schon vor dem
       Guard-Vergleich early-returnt (`_prevAlarmeJson` wird aus denselben Saat-Werten
       berechnet wie `currentJson`).
    3. `effekteVon(ast, quelle, u)` einsammeln, alle Rückrufe ausführen.
    4. Assert `spion`-Zähler `=== 0`.
    5. Positiv-Gegenprobe im selben Testblock: Schritte 1-4 wiederholen mit
       `createMode: undefined` ⇒ Assert `spion`-Zähler `=== 1`.
  - Mutations-Gegenprobe: `if (!trip || createMode) return;` zurück zu
    `if (!trip) return;` verfälschen ⇒ Schritt 4 liefert ebenfalls `1` statt `0` ⇒
    Test wird rot. Kein anderer bestehender Test (Trip-Hub-, Vergleichs-Mounts) fängt
    diese Mutation, weil keiner von ihnen `createMode` überhaupt setzt.

- **AC-3:** Given `displayChannelState` (`AlarmeTab.svelte:295-305`) hackt
  `email: true` fest, sobald `sendTelegram` als Wertprop gesetzt ist / When
  `TripNewEditor.svelte` die Kanal-Wertprops (`sendTelegram`/`channelThresholds`/
  `metricAlertLevels`) bewusst NICHT setzt (lokaler Modus) / Then rendert
  `renderTripNew({activeTab: 'alerts', isMobileViewport: false})` den
  E-Mail-Kanal-Schalter (`data-testid="alert-channel-toggle-email"`, enthält ein
  `role="switch"`-Element, `atoms/Switch.svelte:68-70`) im UNCHECKED-Zustand
  (`aria-checked="false"`) — Beweis, dass der Zustand vom internen route-Default
  (E-Mail aus) kommt, nicht von einem festverdrahteten `true`.
  - Test: Kern — `trip_new_alarme_reiter.test.ts`, `renderTripNew()` +
    `outerHtml(html, 'alert-channel-toggle-email')` + Regex auf
    `aria-checked="false"` innerhalb dieses Ausschnitts.
  - Mutations-Gegenprobe: `sendTelegram={alarm.channels.telegram}` versehentlich als
    Wertprop im `<AlarmeTab …>`-Tag ergänzen ⇒ `aria-checked` kippt auf `"true"`
    (der Hardcode-Zweig `displayChannelState` greift) ⇒ Test wird rot.

- **AC-4:** Given `CreateTripHandler` setzt bei fehlendem `official_warnings` im
  POST-Body hart `enabled: false` (`internal/handler/trip.go:186-188`), der
  route-lokale Default in `AlarmeTab.svelte` für BESTANDS-Trips aber `true` zeigt
  (`:224-226`) / When `initialCreateTripAlarmState()` (die REALE, produktiv
  genutzte Funktion — kein Hand-Literal im Test) `officialWarningsEnabled: false`
  liefert und `buildCreateTripPayload({..., alarm: initialCreateTripAlarmState()})`
  aufgerufen wird / Then liefert das Ergebnis `official_warnings.enabled === false`.
  - Test: Kern — `tripNewLogic.test.ts` ruft `initialCreateTripAlarmState()` direkt
    auf (nicht `{officialWarningsEnabled: false, ...}` von Hand geschrieben), damit
    eine Mutation am PRODUKTIVEN Default auch wirklich gefangen wird.
  - Mutations-Gegenprobe: den Default in `initialCreateTripAlarmState()` von `false`
    auf `true` verfälschen ⇒ dieser Test wird rot. Ein Test, der stattdessen
    `{officialWarningsEnabled: false}` von Hand baut, würde diese Mutation NICHT
    fangen (Finding, das dieses AC-Design gezielt vermeidet).

- **AC-5:** Given ein vollständiger Anlege-Durchlauf (Premium-SMS-Kanal an, eine
  Metrik-Stufe gesetzt, eine Kanal-Schwelle auf „hoch" gesetzt) entsteht
  ausschließlich durch Aufrufe der drei reinen Funktionen
  `applyAlarmChannelToggle()`/`applyAlarmThresholdChange()`/
  `applyAlarmMetricLevelChange()` auf `initialCreateTripAlarmState()` / When
  `buildCreateTripPayload({..., alarm})` mit diesem Ergebnis aufgerufen wird und das
  Payload anschließend über die DREI ECHTEN Lesewege zurückgelesen wird, die
  `AlarmeScheduleTab.svelte:56,66-68` beim Öffnen eines Bestandstrips benutzt —
  `reconstructTripAlertChannels(trip)` (Kanäle), `trip.alert_channel_thresholds`
  (Schwellen), `trip.display_config?.metric_alert_levels` (Metrik-Level) / Then
  liefern alle drei Lesewege exakt die Werte, die über die Reducer-Funktionen gesetzt
  wurden (Rundreise ohne Verlust).
  - Test: Kern — `tripNewLogic.test.ts`, echte Aufrufkette aus Reducer-Funktionen →
    `buildCreateTripPayload()` → den drei echten Lesefunktionen/-pfaden, keine
    Fixture-Attrappe.
  - Mutations-Gegenprobe: `currentDisplayConfig`-Argument beim Aufruf von
    `buildAlarmeDeliveryPayload()` in `buildCreateTripPayload()` weglassen (`undefined`
    statt `trip.display_config`) ⇒ `display_config.channels`/`metrics` fehlen im
    Ergebnis-Payload ⇒ dieser Test wird rot (Read-Modify-Write-Regression, CLAUDE.md
    „Daten-Schema-Reworks").

- **AC-6:** Given der heutige `AlertRulesEditor`-Mount sitzt in
  `{:else if activeTab === 'alerts'}` OHNE `isMobileViewport`-Gate (Desktop-Zweig
  `:859-864`, Mobile-Zweig `:1099-1104` je eigenständig) — bei Tab-Wechsel weg und
  zurück würde ein neu gemountetes `AlarmeTab` seinen internen State
  (`routeChannelState` u.a.) auf den Anfangswert zurücksetzen und dem Schatten-State
  widersprechen / When `AlarmeTab` wie `WeatherMetricsTab` gemountet wird
  (`{#if !isMobileViewport}`/`{#if isMobileViewport}`-Gate, dauerhaft im DOM,
  `style:display={activeTab === 'alerts' ? '' : 'none'}`) / Then liefert
  `countTestid(renderTripNew({...}), 'alarme-tab')` in JEDER der drei Kombinationen
  GENAU 1: `{activeTab:'alerts', isMobileViewport:false}`,
  `{activeTab:'alerts', isMobileViewport:true}`,
  `{activeTab:'route', isMobileViewport:false}` (Instanz existiert, ist aber per
  `style:display` verdeckt) — in KEINER Kombination existieren zwei Instanzen
  gleichzeitig.
  - Test: Kern — `trip_new_alarme_reiter.test.ts`, `renderTripNew()` +
    `countTestid()` über die drei Kombinationen.
  - Mutations-Gegenprobe: das `isMobileViewport`-Gate entfernen (zurück zu
    ungegatetem `{:else if activeTab === 'alerts'}`) ⇒ bei
    `{activeTab:'route', isMobileViewport:false}` liefert `countTestid` `0` statt `1`
    (Instanz existiert nur noch während des `alerts`-Tabs) ⇒ Test wird rot.

- **AC-7 (Strukturwächter, kein Verhaltensnachweis — Muster `rework_2276_s6c_alarme.md`
  AC-6):** Given `AlertRulesEditor`-Mount, `activeAlertChannels`-Derivation
  (`TripNewEditor.svelte:144`), `let alertRules = $state<AlertRule[]>([])` (`:90`)
  und die `alertRules`-Zeile im Payload-Builder (`tripNewLogic.ts:151-153`) sind
  Alt-Modell-Code / When diese vier Stellen entfernt werden / Then referenziert
  weder `TripNewEditor.svelte` noch `tripNewLogic.ts` mehr `alertRules`/
  `activeAlertChannels`/`AlertRule` (Typ-Import inklusive, falls sonst ungenutzt),
  UND `AlertRulesEditor.svelte` bleibt als Datei bestehen (kein Löschen).
  - Test: Kern — Source-Inspection (zulässig hier, weil es eine reine
    Abwesenheits-/Strukturzusicherung ist, kein Verhaltensnachweis): keine der vier
    Fundstellen mehr in `TripNewEditor.svelte`/`tripNewLogic.ts`;
    `legacy_wizard_removed.test.ts` (unverändert) bleibt grün, weil es nur den
    Export aus `organisms/index.ts` prüft, nicht den Mount in `TripNewEditor.svelte`.
  - Mutations-Gegenprobe: `let alertRules = $state<AlertRule[]>([]);` wieder
    einfügen, ohne sie zu verwenden ⇒ der Test wird rot (verbotener Bezeichner
    gefunden) — verhindert stillen toten Code aus einem unvollständigen Rückbau.

## Known Limitations

- **Kein neues Live-E2E in dieser Scheibe.** Begründung und Kern-Ersatznachweis s.
  „Wirkort je Zusicherung" oben.
- **Der `/api/metrics`-Ladepfad für `activeMetrics` ist NICHT durch eine eigene AC
  bewacht.** Eine Mutation, die `activeMetrics` fest auf `[]` setzt, fängt kein Test
  dieser Scheibe — der Reiter zeigte dann dauerhaft den „keine Metriken
  gewählt"-Hinweis, obwohl im Wetter-Metriken-Reiter bereits Metriken aktiv sind.
  Bewusst akzeptiert für S1: der Fetch ist fail-soft (kein Blocker fürs Anlegen) und
  betrifft nur die Metrik-Zeilen-Anzeige, nicht Kanäle/Amtliche-Warnungen/Cooldown/
  Stille-Stunden, die den Kern der ACs bilden. Sollte eine spätere Scheibe den
  Katalog-Ladepfad wiederverwenden oder erweitern, gehört ein SSR-Render-Nachweis
  (Katalog + `weatherMetrics` über `stateOverride` säen) dorthin.
- **`CreateTripChannels` (Bericht-Kanäle) bekommt in dieser Scheibe kein
  Premium-SMS.** #2229 bezieht sich ausschließlich auf die Alarm-Kanalauswahl: die
  Bericht-Kanalauswahl (Versand-Tab) ist ein separates Thema, hier bewusst
  unangetastet (s. „Nicht in dieser Scheibe").
- **`docs/specs/_archive/modules/issue_1258_alarme_tab_official_warnings.md` wird
  nicht nachgeführt.** Die Datei ist archiviert; diese Spec dokumentiert die
  `createMode`-Ergänzung an `AlarmeTab.svelte` eigenständig, im selben Muster wie
  `rework_2276_s2_alarme.md`/`rework_2276_s6c_alarme.md` es für ihre jeweiligen
  Änderungen an derselben Datei bereits tun.
- **Cooldown/Stille-Stunden sind beim Anlegen editierbar** — eine bewusste Abweichung
  von der ursprünglichen Analyse-Empfehlung („nur Vorgabewert, editierbar erst im
  Hub"). Der Wertprop-Modus macht Editierbarkeit ohne Zusatzcode möglich (s.
  Implementation Details Punkt 3); ein künstliches Sperren wäre selbst zusätzlicher,
  unbegründeter Code gewesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Der `createMode`-Guard folgt exakt dem bereits produktiv erprobten
  Muster von `WeatherMetricsTab.svelte` (`createMode?: boolean`-Prop schaltet den
  internen Selbst-Speicher-Pfad ab, Änderungen fließen stattdessen über
  Delta-Rückrufe nach oben) — kein neuer Architekturentscheid, sondern dieselbe,
  bereits akzeptierte Lösung auf einen zweiten Organismus angewendet
  (`docs/adr/README.md` enthält keinen gesonderten Eintrag für dieses Muster, weil
  es unterhalb der ADR-Schwelle „Grundsatzentscheidung" liegt). Die Verzicht-
  Entscheidung gegen einen neuen Adapter (`trip-new/alarmePropsAus.ts`) ist ebenfalls
  keine Architekturentscheidung, sondern eine Anwendung der bereits bestehenden
  Pendant-Sperre (`compare/alarmePropsAus.ts:8-13`).

## Changelog

- 2026-09-25: Initial spec created (Scheibe S1 von #2277, schließt #2229)
- 2026-09-25 (v1.1, Adversary-Vorprüfung durch advisor): AC-5 korrigiert auf die drei
  tatsächlichen Lesewege (`reconstructTripAlertChannels` liest NUR Kanäle, nicht
  Schwellen/Metrik-Level); Schatten-State als reine, exportierte Funktionen in
  `tripNewLogic.ts` verlagert, damit AC-4/AC-5-Gegenproben am produktiven Default
  wirken statt an einem Hand-Literal im Test; AC-2-Testrezept um die
  Diff-Gate-Falle (vakuum-grün ohne gezielte Nach-Mutation) und den
  `baueTripSpeicherung`-Spion präzisiert; AC-1/AC-3/AC-6 von Quelltext-Inspektion
  auf echtes SSR-Rendering über die bereits vorhandene `tripNewSsr.ts`-Harness
  umgestellt; Known Limitations um den ungeprüften Katalog-Ladepfad und die
  bewusste Cooldown/Stille-Stunden-Abweichung von der Analyse-Empfehlung ergänzt.
