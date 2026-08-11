---
entity_id: fix_1745_a_alarm_kanal_premium_sms_ui
type: module
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [sms, premium, garmin, alarm, channel, frontend, compare]
---

<!-- Issue #1745 (Scheibe A) -- Premium-SMS als vierter Kanal in der
     Alarm-Kanal-Auswahl (Trip UND Ortsvergleich). Vorbild/Formatvorlage:
     feat_1717_s3_premium_sms_ui.md (Versand-Reiter, eine Scheibe frueher).
     Nachfolger: Scheibe B (eigenes Issue) -- Radar-/Regen-Alarme auf
     denselben Aufloesungsweg umstellen. Kontext-Grundlage:
     docs/context/fix-1745-alarm-kanaele-premium-sms.md. -->

# Alarm-Kanal-Auswahl: Premium-SMS als vierter Kanal — Scheibe A

## Approval

- [x] Approved — PO, 2026-08-11 („approved", Klartext). Freigegeben wurde der Wortlaut inklusive
  der vom Orchestrierer nachgetragenen AC-13/AC-14 und der vier zusätzlichen Bestands-Testdateien;
  ausdrücklich mit freigegeben ist die Zeilen-Ausnahme (`loc_limit_override 650`).

## Purpose

Premium-SMS (Garmin inReach) ist seit #1701 im Backend ein vollwertiger vierter Alarm-Kanal —
aber der Alarme-Reiter (Trip UND Ortsvergleich) kennt ihn nicht. Solange der Haken in der
Oberfläche fehlt, erreicht **kein einziger Alarm** (Gewitter, Änderung, amtliche Warnung) das
Garmin-Gerät, obwohl das Backend sendebereit ist. Diese Scheibe macht Premium-SMS in der
bestehenden Alarm-Kanal-Auswahl sichtbar, schaltbar und speicherbar — für Trip und
Ortsvergleich gleichermaßen.

## Abgrenzung (nicht in dieser Scheibe)

- **Radar-/Regen-Alarme (Scheibe B, eigenes Issue):** `_radar_effective_channels()`
  (`src/services/trip_alert.py:826-856`) bleibt unverändert — sie liest weiterhin
  ausschließlich `report_config`, nicht `trip.alert_channels`. **Nutzersichtbare Folge:** ein
  hier gesetzter Premium-SMS-Haken wirkt sofort für Gewitter-, Änderungs- und amtliche Alarme
  (alle drei lesen `_effective_alert_channels`) — **nicht** für Regen-/Radar-Alarme, bis Scheibe
  B den Aufllösungsweg vereinheitlicht.
- **Kein Backend-Code.** Der Go-Handler-Merge (`internal/handler/trip.go:371-407`,
  `internal/handler/compare_preset.go:407-416`) transportiert `PremiumSms`/`SendPremiumSms`
  bereits feldweise (#1701 ausgeliefert). `_effective_alert_channels()`
  (`src/services/trip_alert.py:1491-1546`) und `compare_alert_channels.py:44-45` kennen den
  Kanal ebenfalls bereits. Diese Scheibe ändert **keine** Python- oder Go-Datei.
- **`AlertRulesEditor`** (Reiter „Alarmregeln", Pro-Regel-Kanal-Overrides, `TripEditView.svelte`,
  `TripNewEditor.svelte`) — vorbestehende Dreier-Aufzählung, gebucht als Nebenbefund in #1199.
- **Kein neues ADR.** ADR-0049 legt den Kanalnamen bereits fest, ADR-0046 verpflichtet zur
  Schwellenanwendung — beide sind bereits erfüllt (`AlertChannelPicker` wendet Schwellen
  generisch an, `alert_channel_threshold.py:20-35`).
- **Kein neuer Geräte-Zustellungsnachweis.** Dass eine aktivierte Premium-SMS tatsächlich am
  Garmin-Gerät ankommt, ist mit #1533 bereits belegt (Generalprobe) und wird hier nicht erneut
  bewiesen.

## Source

**Frontend (`frontend/src/lib/components/...`, SvelteKit) — der gesamte Umfang dieser Scheibe:**

- **File:** `shared/alarme-tab/alertChannelState.ts` (MODIFY, ≈+25 LoC) — `ALERT_CHANNEL_ORDER`
  wird `['telegram', 'sms', 'email', 'premium_sms']`, `AlertChannelState`/
  `AlertChannelThresholdState` bekommen das vierte Feld, `NEW_ENTITY_DEFAULT` bekommt
  `premium_sms: false` (D1), `hasAnyExplicitChannelValue()` prüft den vierten Kanal mit
  (Landmine 2), `channelWarningNeeded()` prüft den vierten Kanal mit (Landmine 4, unten),
  `resolveAlertChannelThresholds()`/`coerceThreshold()` decken `premium_sms` ab. `ChannelKind`
  ist bereits als `(typeof ALERT_CHANNEL_ORDER)[number]` definiert — die Erweiterung um
  `'premium_sms'` propagiert automatisch in jede Stelle, die `ChannelKind` importiert (statt
  einer eigenen, lokalen Drei-Werte-Union — s. `AlarmeTab.svelte` unten).
- **File:** `shared/AlertChannelPicker.svelte` (MODIFY, ≈+20 LoC) — `CHANNEL_LABELS['premium_sms']
  = 'Premium-SMS (Garmin inReach)'`, `CHANNEL_SUB['premium_sms']` (Sub-Text analog den
  bestehenden drei). Neue optionale Prop `disabledChannels?: Partial<Record<ChannelKind,
  string>>` (Wert = Hinweistext) — Zeile rendert **sichtbar**, aber `Switch` bekommt
  `disabled={!!disabledChannels?.[kind]}` (D3: gesperrt, nicht versteckt). Kein
  `{#if context === 'route'}` — die Komponente kennt gar keinen `context`-Parameter, die
  Kanalzeile erscheint dadurch strukturell in **beiden** Flächen gleichermaßen (D6).
- **File:** `shared/alarme-tab/premiumSmsAlarmGate.ts` (NEU, ≈20 LoC) — reine Funktion
  `derivePremiumSmsAlarmGate(profile: { premium_sms_allowed?: boolean } | null | undefined):
  { disabled: boolean; hint: string | null }`. **Bewusst NICHT** `premiumSmsChannelState()`
  (`shared/versand-tab/premiumSmsChannelState.ts`) — die verrechnet zusätzlich
  `premium_sms_reply_state` zu `disabled`, genau die Bereitschaftsfrage, die der Alarmpfad nicht
  stellt (`trip_alert.py:847-855`, `notification_service.py:1499`). Einziger Eingang:
  `premium_sms_allowed` (D2/D3).
- **File:** `shared/AlarmeTab.svelte` (MODIFY, ≈+40 LoC) —
  - neue optionale Prop `profileOverride?: { premium_sms_allowed?: boolean } | null` (Testhaken,
    Muster `VTBriefingChannels.svelte:60,74,82`);
  - `onMount`-Fetch von `/api/auth/profile` **nur wenn `profileOverride === undefined`** (Muster
    `VTBriefingChannels.svelte:81-109`) — **ein** Fetch-Ort deckt alle vier Mount-Punkte, da
    `AlertChannelPicker` ausschließlich von `AlarmeTab` eingebunden wird;
  - `displayChannelState` (Zeile ≈190-194): `vergleich`-Zweig ergänzt um
    `premium_sms: wiz?.sendPremiumSms ?? false`;
  - `handleChannelToggle` (Zeile ≈195-205): `vergleich`-Zweig bekommt einen vierten Zweig
    `else if (kind === 'premium_sms') wiz.sendPremiumSms = !wiz.sendPremiumSms;`;
  - `handleThresholdChange` (Zeile ≈226-243, **Landmine 1**): das bisher explizit dreifeldige
    Rückschreibe-Objekt `{ telegram, sms, email }` wird durch die vollständige,
    bereits-berechnete `updated`-Struktur ersetzt (`applyThresholdChange()` liefert nach der
    Typ-Erweiterung ohnehin alle vier Felder) — kein Feld-für-Feld-Picking mehr, das beim
    nächsten neuen Kanal denselben Fehler wiederholen könnte;
  - Props-Typen (Zeile ≈78, 83: `onChannelToggle`, `existingChannelThresholds`) werden von der
    lokalen `'telegram' | 'sms' | 'email'`-Union auf den importierten `ChannelKind`
    umgestellt — TypeScript/`svelte-check` (CI-Pflichtcheck) macht damit jede vergessene
    Fallunterscheidung zum Compile-Fehler statt zu stillem Datenverlust.
- **File:** `shared/alarme-tab/tripChannelReconstruction.ts` (MODIFY, ≈+8 LoC) — D4:
  `trip.alert_channels` gesetzt, aber ohne `premium_sms`-Schlüssel → `premium_sms: false` (kein
  Fallback auf `report_config.send_premium_sms`); geerbter Briefing-Zweig liest
  `rc.send_premium_sms ?? false`; letzter Fallback (kein `alert_channels`, kein `report_config`)
  → `premium_sms: false`.
- **File:** `shared/alarme-tab/alarmeDeliveryPayload.ts` (MODIFY, ≈+10 LoC) —
  `AlarmeChannelsState`/`AlarmeChannelThresholdsState` bekommen `premium_sms`; der
  Laufzeit-Guard (Zeile ≈85-94) prüft jetzt vier explizite boolean-Werte statt drei (D7 —
  Pflichtfeld, keine stille Lücke); Payload-Objekt (`alert_channels`, `alert_channel_thresholds`)
  sendet `premium_sms` immer explizit mit.
- **File:** `compare/compareWizardState.svelte.ts` (MODIFY, ≈+3 LoC) — neue Rune
  `sendPremiumSms = $state(false);` (Default aus, D1); `saveNewPreset()` reicht
  `sendPremiumSms: this.sendPremiumSms` an `buildNewComparePresetPayload` durch. **Nicht**
  angefasst: `saveComparePreset()` (Wizard-Klassenmethode) — toter Code, kein Aufrufer mehr
  (Known Limitations).
- **File:** `compare/compareEditorSave.ts` (MODIFY, ≈+6 LoC) — `CompareEditorEdits.sendPremiumSms
  ?: boolean` + Round-Trip-Zeile (Muster `sendTelegram`/`sendSms`, Zeile ≈61-62/189-190);
  `NewComparePresetFields.sendPremiumSms: boolean` (**Pflichtfeld**, analog `sendTelegram`/
  `sendSms` in derselben Interface, Zeile ≈245-246) + unbedingte Payload-Zeile
  `send_premium_sms: fields.sendPremiumSms` (Zeile ≈310-311).
- **File:** `compare/compareHubWizardBridge.ts` (MODIFY, ≈+10 LoC, **Landmine 3**) — `HubEdit`
  bekommt `sendPremiumSms?: boolean`, `buildHubPutPayload()` reicht es an
  `buildComparePresetSavePayload` durch (Zeile ≈125-196); `AlarmHydrationTarget` bekommt
  `sendPremiumSms?: boolean`; `hydrateAlarmFieldsFromPreset()` setzt
  `state.sendPremiumSms = preset.send_premium_sms ?? false` (Zeile ≈488-522);
  `AlarmSnapshot.sendPremiumSms?: boolean`; `flushPendingAlarmSave()` sendet es mit
  (Zeile ≈577-602); `rollbackAlarmSnapshot()`s Feldliste (Zeile ≈628-644) bekommt
  `'sendPremiumSms'` als fünften Eintrag.
- **File:** `compare/CompareTabs.svelte` (MODIFY, ≈+2 LoC) — `currentAlarmSnapshot()`
  (Zeile ≈575-596) ergänzt um `sendPremiumSms: wizardState.sendPremiumSms`.
- **File:** `frontend/src/lib/types.ts` (MODIFY, ≈+4 LoC) — `Trip.alert_channels` (Zeile ≈367)
  bekommt `premium_sms?: boolean` (optional — Bestandstrips liefern den Schlüssel nicht,
  s. D4); `Trip.alert_channel_thresholds` (Zeile ≈371) und `ComparePreset.alert_channel_thresholds`
  (Zeile ≈663) bekommen `premium_sms?: string`; `ComparePreset` bekommt
  `send_premium_sms?: boolean` neben den bestehenden `send_telegram`/`send_sms` (Zeile ≈639-640).

**Test-Dateien:**

- **File:** `shared/__tests__/alarme_alert_channel_defaults.test.ts` (MODIFY, ≈+40 LoC) — AC-1
  (Order), AC-2, AC-3, AC-4. **Bestand wird bewusst mitgezogen und läuft nach der
  Typ-Erweiterung zunächst rot** (`deepEqual`-Assertions gegen Drei-Element-Arrays, Zeile
  27-29, 31-51, 58-68) — das ist der Beweis, dass diese Tests etwas bewachen, kein
  Kollateralschaden.
- **File:** `shared/__tests__/alarme_trip_channel_reconstruction.test.ts` (MODIFY, ≈+15 LoC) —
  AC-7 (Zeile 27-51 wird ebenfalls zunächst rot laufen, dieselbe Erwartung).
- **File:** `shared/alarme-tab/alertChannelThresholds.test.ts` (MODIFY, ≈+25 LoC) — AC-12
  (Zeile 45-48, 71-82 werden ebenfalls zunächst rot laufen).
- **File:** `shared/alarme-tab/__tests__/premiumSmsAlarmGate.test.ts` (NEU, ≈40 LoC) — AC-5,
  AC-6, reine Funktionsprüfung.
- **File:** `shared/__tests__/alarme_tab_premium_sms_channel_row_render.test.ts` (NEU, ≈50 LoC) —
  AC-1, SSR-Rendering von `AlarmeTab` in beiden Kontexten via `svelte/server`.
- **File:** `compare/__tests__/compare_hub_alarme_bridge.test.ts` (MODIFY, ≈+30 LoC) — AC-9
  (vollständige Bridge-Kette: Hydration, Snapshot, Flush, Rollback).
- **File:** `compare/__tests__/compare_new_preset_payload.test.ts` (MODIFY, ≈+10 LoC) — AC-11.
- **File:** `frontend/e2e/feat-1745-a-alarm-premium-sms.spec.ts` (NEU, ≈180 LoC, Live-E2E,
  Staging, Marker `live`) — AC-8, AC-10, **AC-14** (echter Klickpfad, Muster
  `feat-1461-s3b2b-compare-kanal-schwelle.spec.ts`).

🔴 **Nachtrag des Orchestrierers 2026-08-11 — vier weitere Bestands-Testdateien, die D7 rot macht.**
Die ursprüngliche Fassung dieser Spec nannte sie nicht. Nachgemessen per
`grep -rn "buildAlarmeDeliveryPayload" frontend/src -l`: **fünf** Testdateien rufen den Builder auf,
nicht eine. Macht D7 `premium_sms` zum Pflichtfeld im Laufzeit-Guard
(`alarmeDeliveryPayload.ts:85-94`), **wirft** jeder Aufruf ohne das vierte Feld. Betroffen und
mitzuziehen:

- **File:** `shared/__tests__/alarme_delivery_consolidated_save.test.ts` (MODIFY, ≈+12 LoC) — ruft
  den Builder an zehn Stellen mit dreifeldigem `channels`-Objekt auf.
- **File:** `shared/__tests__/alarme_save_single_writer.test.ts` (MODIFY, ≈+8 LoC) — dieselbe
  Aufrufform, plus `deepEqual` gegen `payload.alert_channels`.
- **File:** `shared/alarme-tab/__tests__/alarme_delivery_payload_preserves_inactive_levels.test.ts`
  (MODIFY, ≈+4 LoC).
- **File:** `shared/__tests__/official_alerts_content_single_writer.test.ts` (MODIFY, ≈+4 LoC).

Das ist **kein** Kollateralschaden, sondern der Beleg, dass der Guard etwas bewacht — dieselbe
Lesart wie bei den `deepEqual`-Tests oben. Wer beim Grünziehen versucht ist, das vierte Feld
stattdessen optional zu machen, hebt D7 auf; das wäre eine Spec-Änderung, keine Testreparatur.

## Estimated Scope

- **LoC (Produktivcode):** ≈ 148 (elf MODIFY-Dateien + ein NEU-Helfer).
- **LoC (Tests):** ≈ 420 (neun MODIFY-Testdateien + drei NEU-Testdateien, davon eine
  Live-E2E-Spec mit drei Klickpfaden). Enthält die vier vom Orchestrierer nachgetragenen
  Bestands-Testdateien (D7-Folge) und AC-13/AC-14.
- **Gesamt erwartet:** ≈ 570. Überschreitet das Default-Limit von 250/Workflow deutlich —
  `loc_limit_override 650` bei Implementierungsbeginn nötig. Begründung: vier Mount-Punkte, **drei**
  getrennte Persistenzwege (Trip-PUT, Compare-Hub-PUT, Compare-Neuanlage-POST), vier zu fixende
  Bestandslücken und neun Bestands-Testdateien, die den vierten Kanal bewachen und deshalb
  mitgezogen werden müssen. Doku zählt nicht mit.
- **Files:** 4 CREATE (1 Frontend-Modul + 3 Tests, davon 1 E2E) + 17 MODIFY.
- **Effort:** medium-high (keine neue Fachlogik im Backend — reine Sichtbarmachung und
  vollständige Verdrahtung eines bereits bestehenden Kanals über vier Flächen).
- **Risiko:** MEDIUM. Größtes Einzelrisiko ist die Vergleichs-Speicherkette (Landmine 1 + 3) —
  zwei unabhängige Stellen kodieren dieselbe Vier-Felder-Liste, eine vergessene Stelle erzeugt
  einen sichtbaren, aber wirkungslosen Haken (der gemeldete Bug in neuer Form). Zweites Risiko:
  der bislang nicht dokumentierte zweite Persistenzpfad für `/compare/new` (s. „Eigener Fund"
  unten).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_1701_alarm_premium_sms.md` | Vorgänger-Spec, live | Backend-Kanal fertig — `_effective_alert_channels()`, Go-Merge, `compare_alert_channels.py` |
| `docs/specs/modules/feat_1717_s3_premium_sms_ui.md` | Vorgänger-Spec, live | `ConnectionProfile.premium_sms_allowed` bereits vorhanden (`channelConnectionStatus.ts:33`) — keine erneute Erweiterung nötig; Formatvorbild dieser Spec |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | ADR | Kanalname `premium_sms`, „eigenes Tarif-Gate, keine Delegation an SMS" |
| `docs/adr/0046-*.md` (Kanal-Schwelle) | ADR | Pflicht zur Schwellenanwendung — bereits erfüllt, `AlertChannelPicker` wendet sie generisch an |
| `shared/versand-tab/channelConnectionStatus.ts::ConnectionProfile` | module | einzige kanonische Profilform, liefert `premium_sms_allowed` — wird gelesen, nicht verändert |
| `shared/alarme-tab/alertChannelState.ts::ALERT_CHANNEL_ORDER`/`ChannelKind` | module, MODIFY | Kern-Erweiterung, propagiert generisch in Picker, Props-Typen, Guards |
| `shared/versand-tab/VTBriefingChannels.svelte` | Vorbild, NICHT wiederverwendet als Modul | `profileOverride`-Testhaken + `onMount`-Fetch-Muster (Zeile 60,74,82,81-109) — kopiert als Muster, nicht importiert |
| `compare/compareHubWizardBridge.ts::flushPendingAlarmSave`/`hydrateAlarmFieldsFromPreset`/`rollbackAlarmSnapshot` | module, MODIFY | bestehende Alarm-Bridge-Kette, um ein fünftes Feld erweitert |
| `frontend/e2e/feat-1461-s3b2b-compare-kanal-schwelle.spec.ts` | Test-Vorbild | Struktur- und Namensmuster für die neue Live-E2E-Spec (Klick → PUT-Body-Prüfung → Reload) |

## Implementation Details

### Kein Kontext-Gate — anders als der Versand-Reiter

Im Versand-Reiter ist Premium-SMS für `context="vergleich"` bewusst ausgeschlossen (ADR-0049,
reiner Trip-Briefing-Kanal). Im Alarm-Pfad gilt das Gegenteil: `compare_alert_channels.py:44-45`
und `ComparePreset.SendPremiumSms` (`internal/model/compare_preset.go:97`) sehen den Kanal
**ausdrücklich auch für den Vergleich** vor (#1701 AC-4). `AlertChannelPicker` kennt strukturell
gar keinen `context`-Parameter — die vierte Zeile entsteht automatisch in beiden Flächen, sobald
`ALERT_CHANNEL_ORDER` sie enthält. Ein kopiertes `{#if context === 'route'}` wäre hier ein
Fehler, kein Schutz.

### Tarif-Gate: schlanker Helfer statt Wiederverwendung des Versand-Zustandshelfers

`premiumSmsChannelState()` verrechnet Tarif **und** Rückadress-Frische zu `disabled` — für den
Versand-Reiter richtig (dort entscheidet die Frische über Sendebereitschaft), für den Alarmpfad
falsch: Weder `_effective_alert_channels()` noch `_dispatch_alert_message()`
(`notification_service.py:1499`) stellen die Bereitschaftsfrage für Premium-SMS — das Backend
versucht den Versand unabhängig vom Rückadress-Alter. Volle Wiederverwendung würde also einen
Haken sperren, den das Backend anstandslos bedienen würde. `derivePremiumSmsAlarmGate()` liest
deshalb ausschließlich `premium_sms_allowed`.

### Landmine 4 (eigener Fund, nicht im Kontextdokument benannt): `channelWarningNeeded()`

`channelWarningNeeded()` (`alertChannelState.ts:53-55`) prüft heute hart drei Felder
(`!telegram && !sms && !email`). Ein Trip/Preset mit **ausschließlich** Premium-SMS aktiv würde
ohne Fix fälschlich den Warnhinweis „kein Kanal — Alerts gehen nirgends hin" zeigen, obwohl ein
Alarm zugestellt würde — dieselbe Fehlerklasse, die AC-12 in `feat_1717_s3_premium_sms_ui.md` für
den Versand-Reiter bereits einmal behoben hat. Gemessen beim Nachlesen des Kontextdokuments,
dort nicht erwähnt.

### Eigener Fund: `/compare/new` hat einen zweiten, unabhängigen Persistenzpfad

Das Kontextdokument beschreibt unter „Die vollständige Speicherkette im Ortsvergleich (der
einzige lebende Weg)" ausschließlich den Hub-PUT-Pfad (`/compare/[id]`). Für `/compare/new`
existiert ein **zweiter, ebenfalls lebender** Pfad: `wiz.saveNewPreset()`
(`compareWizardState.svelte.ts:111-159`, aufgerufen von `CompareNewEditor.svelte:195`) baut über
`buildNewComparePresetPayload()` (`compareEditorSave.ts:289-...`) einen **POST**-Body — nicht
über `buildHubPutPayload`/`buildComparePresetSavePayload`. `CompareNewEditor.svelte` mountet
`AlarmeTab context="vergleich"` (Zeile 412, 499) — ein dort gesetzter Premium-SMS-Haken landet
ausschließlich im `wiz.sendPremiumSms`-Feld und muss deshalb **zusätzlich** über
`NewComparePresetFields`/`buildNewComparePresetPayload()` verdrahtet werden (AC-11), sonst geht
er beim Aktivieren eines neuen Vergleichs verloren — unabhängig von Landmine 1 und 3, die beide
nur den Hub-Pfad betreffen. Zur Kontrolle: `saveComparePreset()` (die *Wizard-Klassenmethode*,
nicht zu verwechseln mit dem gleichnamigen, tatsächlich toten Funktions-Namensraum) hat laut
Grep über `frontend/src` **keinen** Aufrufer — nur `saveNewPreset()` ist live.

### Vier-Felder-Pflicht statt Drei-Felder-Default (D7)

`buildAlarmeDeliveryPayload()`s Laufzeit-Guard (`alarmeDeliveryPayload.ts:85-94`) verlangt heute
drei explizite boolean-Werte. Diese Scheibe macht daraus vier — Konsequenz: der **erste**
Alarm-Save eines Bestandstrips nach dem Rollout persistiert `premium_sms: false` explizit (statt
den Schlüssel einfach fehlen zu lassen), selbst wenn nur der Cooldown geändert wurde. Entschieden
für Konsistenz mit den drei Bestandsfeldern (die verhalten sich seit `#1461` bereits so) und
gegen einen fünften Sonderfall „ein Feld ist optional, drei sind Pflicht". Kein stiller Default,
keine neue Fehlerklasse — nur dieselbe Regel auf ein viertes Feld angewendet.

## Entscheidungen (D1–D7)

- **D1 — Neuanlage-Default `false`.** `NEW_ENTITY_DEFAULT` bekommt `premium_sms: false`.
  Kostenkanal (Satelliten-SMS) — wird bewusst angehakt, nie automatisch.
- **D2 — Tarif-Gate NUR über `premium_sms_allowed`.** Kein Zusammenhang mit
  `premium_sms_reply_state` (Rückadress-Frische) — der Alarmpfad stellt diese Frage bewusst
  nicht (`trip_alert.py:851-854`, `notification_service.py:1499`).
- **D3 — Unter Tarif `standard`: sichtbar und gesperrt**, mit Hinweis, **nicht** versteckt.
  `premium_sms_allowed` ist nur ab Tarif `premium` wahr (`user_tier.py:33`), SMS bereits ab
  `standard` (`user_tier.py:14`).
- **D4 — Rekonstruktion: fehlender Schlüssel bedeutet `false`.** Ist `trip.alert_channels`
  gesetzt, aber ohne `premium_sms`-Schlüssel (heutiger Bestand aller Trips), zeigt der Picker
  **aus** — kein Rückfall auf `report_config.send_premium_sms`. Sobald `alert_channels`
  existiert, ersetzt es den geerbten Anteil vollständig (deckt sich mit #1258 S3 AC-15).
- **D5 — Beschriftung und Anordnung** wörtlich „Premium-SMS (Garmin inReach)", als vierte Zeile
  direkt unter SMS — identisch zum Versand-Reiter.
- **D6 — Im Ortsvergleich verhält sich Premium-SMS wie Telegram/SMS, nicht wie E-Mail.**
  E-Mail bleibt im Vergleich hart verdrahtet (`compare_alert_channels.py:39`). Kein
  `{#if context === 'route'}`-Gate — Premium-SMS ist im Alarm-Pfad ausdrücklich auch für den
  Vergleich vorgesehen (#1701 AC-4).
- **D7 — Persistenz-Nebenwirkung bewusst in Kauf genommen.** `premium_sms` wird im
  Trip-Kanal-Guard zum Pflichtfeld (Konsistenz mit den drei Bestandsfeldern) — der erste
  Alarm-Save nach dem Rollout schreibt `premium_sms: false` explizit statt den Schlüssel fehlen
  zu lassen. Kein stiller Default.

## Landminen

1. **`AlarmeTab.svelte:226-243` (`handleThresholdChange`).** Der `vergleich`-Zweig baute das
   Rückschreibe-Objekt bisher explizit dreifeldig und hätte ein berechnetes `premium_sms` still
   verworfen. Fix: die vollständige `updated`-Struktur wird durchgereicht statt einzelner Felder
   gepickt. Geprüft in AC-8/AC-10 (Live-E2E — Komponenten-Klickpfad, node:test kann Svelte nicht
   mounten, ADR-0020).
2. **`hasAnyExplicitChannelValue()` (`alertChannelState.ts:32-38`).** Prüfte bisher nur drei
   Kanäle — ein Bestand mit ausschließlich `premium_sms` gälte als „kein Bestand" und würde vom
   Neuanlage-Default überschrieben (dieselbe Fehlerklasse wie Adversary Fix-Loop 1/F001 für die
   drei Bestandskanäle). Geprüft in AC-3.
3. **`buildHubPutPayload`/`HubEdit` (`compareHubWizardBridge.ts:125-195`).** Kodiert die
   Feldliste ein zweites Mal neben `buildComparePresetSavePayload` — vergessen, geht der Haken
   beim nächsten Hub-Speichern verloren. Geprüft in AC-9 (Kern-Ebene, pure Funktionen) und AC-10
   (Live-E2E, tatsächlicher PUT-Body).
4. **`channelWarningNeeded()` (`alertChannelState.ts:53-55`) — eigener Fund.** Prüft bisher nur
   drei Kanäle; ein Trip/Preset mit ausschließlich Premium-SMS aktiv zeigte ohne Fix fälschlich
   „kein Kanal — Alerts gehen nirgends hin". Geprüft in AC-4.

## Expected Behavior

- **Input:** Nutzer öffnet den Alarme-Reiter eines Trips (`/trips/[id]`) oder eines
  Ortsvergleichs (`/compare/[id]`, `/compare/new`) und klickt auf den Premium-SMS-Haken bzw.
  eine Dringlichkeits-Stufe (nur wenn der Tarif es erlaubt).
- **Output:** Trip: `alert_channels.premium_sms`/`alert_channel_thresholds.premium_sms` werden
  im selben konsolidierten PUT mitgeschrieben (bestehender Speicherpfad, unverändert bis auf das
  vierte Feld). Ortsvergleich: `send_premium_sms`/`alert_channel_thresholds.premium_sms` landen
  je nach Fläche im Hub-PUT (`/compare/[id]`) oder im Anlege-POST (`/compare/new`).
- **Side effects:** Gewitter-, Änderungs- und amtliche Alarme erreichen ab dieser Scheibe auch
  Premium-SMS, sobald der Haken gesetzt ist (`_effective_alert_channels()` kennt den Kanal
  bereits). Regen-/Radar-Alarme bleiben unverändert am Briefing-Flag hängen (Scheibe B).

## Acceptance Criteria

- **AC-1:** Given der Alarme-Reiter zeigt seit #1258 drei Kanalzeilen (Telegram, SMS, E-Mail) /
  When ein Nutzer den Alarme-Reiter eines Trips ODER eines Ortsvergleichs öffnet / Then erscheint
  eine vierte Zeile „Premium-SMS (Garmin inReach)" direkt unter SMS — in **beiden** Flächen
  gleichermaßen, keine ist gegenüber der anderen eingeschränkt.
  - Prüfort: (a) `ALERT_CHANNEL_ORDER` als reine Reihenfolge-Zusicherung, (b) SSR-Rendering von
    `AlarmeTab` mit `context="route"` UND `context="vergleich"` — beide zeigen
    `alert-channel-row-premium_sms` nach `alert-channel-row-sms`.
  - Test: `shared/__tests__/alarme_alert_channel_defaults.test.ts::alert_channel_order_hat_vier_kanaele_premium_sms_zuletzt`,
    `shared/__tests__/alarme_tab_premium_sms_channel_row_render.test.ts::beide_kontexte_zeigen_premium_sms_zeile`

- **AC-2:** Given ein Nutzer legt einen neuen Trip ODER einen neuen Ortsvergleich an, ohne
  jemals eine Kanal-Einstellung berührt zu haben / When der Alarme-Reiter zum ersten Mal
  gerendert wird / Then ist Premium-SMS **nicht** angehakt — anders als Telegram und SMS, die
  beim Neuanlegen bereits an sind.
  - Prüfort: `resolveAlertChannels(undefined)` — reine Funktion, keine Bestandsdaten übergeben.
  - Test: `shared/__tests__/alarme_alert_channel_defaults.test.ts::neuanlage_default_premium_sms_aus`

- **AC-3:** Given ein Bestand hat ausschließlich beim Premium-SMS-Kanal einen expliziten Wert
  gesetzt (Telegram/SMS/E-Mail unbekannt) / When der Alarme-Reiter den Ist-Zustand auflöst /
  Then wird dieser Bestand erkannt und übernommen — die Oberfläche überschreibt ihn **nicht**
  mit dem Neuanlage-Default, nur weil die anderen drei Kanäle fehlen.
  - Prüfort: `resolveAlertChannels({ premium_sms: true })` — dieselbe Fehlerklasse, die für die
    drei Bestandskanäle bereits einmal behoben wurde (Adversary Fix-Loop 1/F001).
  - Test: `shared/__tests__/alarme_alert_channel_defaults.test.ts::bestand_nur_premium_sms_wird_erkannt`
  - Mutation: `hasAnyExplicitChannelValue()` bleibt bei der Drei-Felder-Prüfung.

- **AC-4:** Given ein Trip oder Ortsvergleich hat ausschließlich Premium-SMS als Alarm-Kanal
  aktiviert, alle anderen drei sind aus / When der Alarme-Reiter den Warnhinweis „kein Kanal —
  Alerts gehen nirgends hin" berechnet / Then erscheint dieser Hinweis **nicht** — die
  Oberfläche behauptet nicht, dass kein Alarm zugestellt wird, während tatsächlich einer
  zugestellt würde.
  - Prüfort: `channelWarningNeeded({ telegram: false, sms: false, email: false, premium_sms:
    true })` liefert `false`.
  - Test: `shared/__tests__/alarme_alert_channel_defaults.test.ts::warnhinweis_bleibt_aus_bei_nur_premium_sms`
  - Mutation: `channelWarningNeeded()` bleibt bei der Drei-Felder-Prüfung.

- **AC-5:** Given ein Nutzer hat Tarif `standard` (nicht `premium`) / When der Alarme-Reiter den
  Sperrzustand für die Premium-SMS-Zeile berechnet / Then bleibt die Zeile gesperrt, mit einem
  Hinweis, der auf den fehlenden Tarif hinweist — unabhängig davon, ob dieser Nutzer sonst schon
  eine gelernte Rückadresse hätte.
  - Prüfort: `derivePremiumSmsAlarmGate({ premium_sms_allowed: false })` — reine Funktion.
  - Test: `shared/alarme-tab/__tests__/premiumSmsAlarmGate.test.ts::gesperrt_ohne_premium_tarif`

- **AC-6:** Given ein Nutzer hat Tarif `premium`, aber sein Garmin-Gerät hat sich noch nie
  gemeldet (keine gelernte Rückadresse) / When der Alarme-Reiter den Sperrzustand berechnet /
  Then ist die Premium-SMS-Zeile **trotzdem aktivierbar** — der Alarmpfad stellt anders als der
  Versand-Reiter keine Bereitschaftsfrage zur Rückadresse.
  - Prüfort: `derivePremiumSmsAlarmGate({ premium_sms_allowed: true })` — das Ergebnis hängt
    strukturell an keinem `reply_state`-Feld, weil die Funktion es gar nicht entgegennimmt.
  - Test: `shared/alarme-tab/__tests__/premiumSmsAlarmGate.test.ts::aktivierbar_ohne_gelernte_rueckadresse`
  - Mutation: `derivePremiumSmsAlarmGate()` bekommt zusätzlich einen `reply_state`-Parameter und
    sperrt bei `!== 'fresh'`.

- **AC-7:** Given ein Bestandstrip hat `trip.alert_channels` bereits gesetzt (E-Mail/Telegram/SMS
  explizit), aber noch keinen `premium_sms`-Schlüssel (heutiger Zustand aller Trips), UND
  `report_config.send_premium_sms` ist im Trip-Briefing bereits aktiv / When der Alarme-Reiter
  beim ersten Öffnen den Ist-Zustand rekonstruiert / Then zeigt die Premium-SMS-Zeile **aus** —
  der im Briefing aktive Haken wird nicht automatisch in den Alarm-Kanal übernommen.
  - Prüfort: `reconstructTripAlertChannels(trip)` mit `alert_channels` ohne `premium_sms`-Schlüssel
    und `report_config.send_premium_sms = true`.
  - Test: `shared/__tests__/alarme_trip_channel_reconstruction.test.ts::fehlender_premium_sms_schluessel_bedeutet_aus_kein_briefing_fallback`
  - Mutation: die Rekonstruktion liest bei fehlendem Schlüssel `report_config.send_premium_sms`
    statt fest `false`.

- **AC-8:** Given im Alarme-Reiter eines Ortsvergleichs wird die Dringlichkeits-Schwelle für
  Premium-SMS auf „hoch" gesetzt / When gespeichert und die Seite anschließend neu geladen wird
  / Then zeigt der Regler weiterhin „hoch" — nicht zurückgesprungen auf den Startwert „gering".
  - Prüfort: **der echte Klickpfad** im Ortsvergleichs-Hub (`/compare/[id]`) — die einzige Naht,
    an der Landmine 1 tatsächlich wirkt; node:test kann `AlarmeTab.svelte`s Handler-Funktion
    nicht isoliert aufrufen (ADR-0020, kein Komponenten-Mounting).
  - Test: `frontend/e2e/feat-1745-a-alarm-premium-sms.spec.ts::hub_premium_sms_schwelle_ueberlebt_speichern_und_reload`
  - Mutation: `handleThresholdChange()`s `vergleich`-Zweig bleibt bei der Drei-Felder-Konstruktion.

- **AC-9:** Given die Bridge-Kette des Ortsvergleichs-Hubs (Hydration, Snapshot, PUT-Aufbau,
  Fehler-Rollback) kennt heute Telegram und SMS, aber nicht Premium-SMS / When ein Preset mit
  `send_premium_sms: true` geladen, unverändert gespeichert und bei einem fehlgeschlagenen
  PUT zurückgerollt wird / Then bleibt der Wert an **jeder** Stelle der Kette korrekt erhalten —
  weder beim Laden verloren, noch beim Speichern vergessen, noch beim Rollback fälschlich
  überschrieben.
  - Prüfort: `hydrateAlarmFieldsFromPreset`/`flushPendingAlarmSave`/`buildHubPutPayload`/
    `rollbackAlarmSnapshot` — alle vier sind reine, node:testbare Funktionen (kein
    Komponenten-Mounting nötig).
  - Test: `compare/__tests__/compare_hub_alarme_bridge.test.ts::sendPremiumSms_durchlaeuft_hydration_flush_und_rollback`
  - Mutation: `buildHubPutPayload()` reicht `edit.sendPremiumSms` nicht an
    `buildComparePresetSavePayload` durch (Landmine 3).

- **AC-10:** Given im Alarme-Reiter eines Ortsvergleichs (Hub) wird der Premium-SMS-Haken
  angeklickt (Kanal ein) / When gespeichert und die Seite neu geladen wird / Then bleibt der
  Haken angehakt, und der beim Klick ausgelöste PUT-Body enthält `send_premium_sms: true`.
  - Prüfort: derselbe echte Klickpfad wie AC-8 — beweist zusätzlich, dass `AlarmeTab.svelte`s
    `handleChannelToggle` (vergleich-Zweig) UND `CompareTabs.svelte`s `currentAlarmSnapshot()`
    den neuen Kanal tatsächlich in den PUT-Body tragen, nicht nur die darunterliegenden reinen
    Funktionen aus AC-9.
  - Test: `frontend/e2e/feat-1745-a-alarm-premium-sms.spec.ts::hub_premium_sms_haken_ueberlebt_speichern_und_reload`
  - Mutation: `currentAlarmSnapshot()` (`CompareTabs.svelte:575-596`) liest `sendPremiumSms`
    nicht aus `wizardState`.

- **AC-11:** Given ein Nutzer legt einen neuen Ortsvergleich an (`/compare/new`) und aktiviert im
  Alarme-Schritt den Premium-SMS-Haken, bevor er „Briefing aktivieren" klickt / When der
  Vergleich angelegt wird / Then enthält der POST-Body `send_premium_sms: true` — der Haken geht
  auf dem Weg zur Neuanlage nicht verloren (unabhängig vom Hub-Pfad aus AC-9/AC-10, der hier
  gar nicht durchlaufen wird).
  - Prüfort: `buildNewComparePresetPayload()` — die tatsächliche Payload-Bau-Funktion hinter
    `CompareWizardState.saveNewPreset()`.
  - Test: `compare/__tests__/compare_new_preset_payload.test.ts::sendPremiumSms_landet_im_post_body_der_neuanlage`
  - Mutation: `NewComparePresetFields.sendPremiumSms` wird zur Interface hinzugefügt, aber nicht
    in `buildNewComparePresetPayload()`s Rückgabe-Objekt aufgenommen.

- **AC-12:** Given der Trip-Alarme-Reiter baute seine Kanal-Payload bisher mit einem
  Laufzeit-Guard, der drei explizite boolean-Werte verlangt / When die Payload nach dieser
  Scheibe gebaut wird / Then verlangt der Guard **vier** explizite boolean-Werte — ein Aufruf
  ohne `premium_sms` wirft einen Fehler, statt den Kanal still weniger präzise zu senden.
  - Prüfort: `buildAlarmeDeliveryPayload()` — (a) Aufruf mit allen vier Kanal-Werten liefert ein
    `alert_channels`-Objekt mit vier Feldern, (b) Aufruf ohne `premium_sms` wirft.
  - Test: `shared/alarme-tab/alertChannelThresholds.test.ts::alarme_delivery_payload_verlangt_vier_kanal_werte`
  - Mutation: der Guard prüft weiterhin nur `email`/`telegram`/`sms`.

- **AC-13:** Given der Alarme-Reiter wird gerendert, bevor die Tarif-Auskunft des Nutzers vorliegt
  (Server-Rendering, erster Frame, oder die Abfrage schlägt fehl) / When die Premium-SMS-Zeile
  ihren Sperrzustand berechnet / Then ist sie in diesem Zustand **gesperrt**, und der Hinweistext
  behauptet **nicht**, dem Nutzer fehle der Premium-Tarif — er sagt, dass die Auskunft noch aussteht.
  - Prüfort: `derivePremiumSmsAlarmGate(null)` **und** `derivePremiumSmsAlarmGate(undefined)` —
    beide liefern `disabled: true` mit einem Hinweistext, der sich vom Tarif-Hinweis aus AC-5
    unterscheidet.
  - Begründung: Beim Server-Rendering läuft `onMount` nie, das Profil ist dort **immer** unbekannt.
    Ein in diesem Zustand klickbarer Haken ließe sich setzen und speichern, ohne je zu wirken —
    das Tarif-Gate sitzt serverseitig (`user_tier.py:33`). Genau diese vorgespiegelte Kontrolle
    ist der Kern von #1745. Fail-closed ist der Preis dafür, dass ein Premium-Nutzer die Zeile für
    den Bruchteil einer Sekunde gesperrt sieht.
  - Test: `shared/alarme-tab/__tests__/premiumSmsAlarmGate.test.ts::gesperrt_solange_tarif_unbekannt`
  - Mutation: `derivePremiumSmsAlarmGate()` liefert bei fehlendem Profil `disabled: false`.

- **AC-14:** Given ein Nutzer öffnet den Alarme-Reiter eines **Trips** (nicht eines Ortsvergleichs)
  und aktiviert den Premium-SMS-Haken / When gespeichert und die Seite neu geladen wird / Then
  bleibt der Haken angehakt, und der ausgelöste PUT-Body enthält
  `alert_channels.premium_sms: true`.
  - Prüfort: **der echte Klickpfad auf `/trips/[id]`** — der Trip speichert über
    `buildAlarmeDeliveryPayload` und damit über eine **andere** Kette als der Ortsvergleich
    (AC-8/AC-10 prüfen ausschließlich die Compare-Bridge). „Strukturell derselbe Code" gilt für
    die Komponente, **nicht** für den Speicherweg.
  - Begründung, warum das nicht als Known Limitation durchgehen darf: Der Trip ist der Fall, an dem
    dieses Issue aufgefallen ist (KHW 403), und der einzige, der vor dem Tourtermin zählt. Eine
    Scheibe, die den Compare-Weg beweist und den Trip-Weg annimmt, beweist das Falsche.
  - Test: `frontend/e2e/feat-1745-a-alarm-premium-sms.spec.ts::trip_premium_sms_haken_ueberlebt_speichern_und_reload`
  - Mutation: `buildAlarmeDeliveryPayload()` nimmt `premium_sms` entgegen, schreibt es aber nicht
    in das `alert_channels`-Objekt der Payload.

## Mutations-Gegenprobe

| AC | Gezielte Verfälschung | Test, der dadurch rot werden MUSS |
|---|---|---|
| AC-1 | `ALERT_CHANNEL_ORDER` bleibt dreiwertig ODER `AlarmeTab`s `channels`-Sektion wird für `vergleich` hinter ein `{#if}` gestellt | `alert_channel_order_hat_vier_kanaele_premium_sms_zuletzt`, `beide_kontexte_zeigen_premium_sms_zeile` |
| AC-2 | `NEW_ENTITY_DEFAULT.premium_sms` auf `true` gesetzt | `neuanlage_default_premium_sms_aus` |
| AC-3 | `hasAnyExplicitChannelValue()` prüft weiterhin nur drei Felder | `bestand_nur_premium_sms_wird_erkannt` |
| AC-4 | `channelWarningNeeded()` prüft weiterhin nur drei Felder | `warnhinweis_bleibt_aus_bei_nur_premium_sms` |
| AC-5 | `derivePremiumSmsAlarmGate()` liefert `disabled: false` unabhängig vom Tarif | `gesperrt_ohne_premium_tarif` |
| AC-6 | `derivePremiumSmsAlarmGate()` bekommt einen `reply_state`-Parameter und sperrt zusätzlich danach | `aktivierbar_ohne_gelernte_rueckadresse` |
| AC-7 | Rekonstruktion liest bei fehlendem Schlüssel `report_config.send_premium_sms` statt fest `false` | `fehlender_premium_sms_schluessel_bedeutet_aus_kein_briefing_fallback` |
| AC-8 | `handleThresholdChange()`s `vergleich`-Zweig bleibt bei `{telegram, sms, email}` | `hub_premium_sms_schwelle_ueberlebt_speichern_und_reload` |
| AC-9 | `buildHubPutPayload()` lässt `sendPremiumSms` beim Durchreichen weg | `sendPremiumSms_durchlaeuft_hydration_flush_und_rollback` |
| AC-10 | `currentAlarmSnapshot()` liest `wizardState.sendPremiumSms` nicht | `hub_premium_sms_haken_ueberlebt_speichern_und_reload` |
| AC-11 | `buildNewComparePresetPayload()` nimmt `fields.sendPremiumSms` entgegen, aber lässt es im Rückgabe-Objekt weg | `sendPremiumSms_landet_im_post_body_der_neuanlage` |
| AC-12 | Laufzeit-Guard bleibt bei drei Pflichtfeldern | `alarme_delivery_payload_verlangt_vier_kanal_werte` |
| AC-13 | `derivePremiumSmsAlarmGate()` liefert bei unbekanntem Profil `disabled: false` | `gesperrt_solange_tarif_unbekannt` |
| AC-14 | `buildAlarmeDeliveryPayload()` nimmt `premium_sms` entgegen, schreibt es aber nicht ins `alert_channels`-Objekt | `trip_premium_sms_haken_ueberlebt_speichern_und_reload` |

## Known Limitations

- ~~**Trip-Klickpfad hat keinen eigenen E2E-Nachweis.**~~ 🔴 **Vom Orchestrierer verworfen und durch
  AC-14 ersetzt (2026-08-11).** Die ursprüngliche Begründung — „strukturell derselbe Code
  (`AlarmeTab.svelte`, `route`-Zweig)" — trifft für die **Komponente** zu, nicht für den
  **Speicherweg**: der Trip persistiert über `buildAlarmeDeliveryPayload`, der Ortsvergleich über
  die Bridge-Kette. Zwei verschiedene Ketten, und die Trip-Kette ist die, an der dieses Issue
  aufgefallen ist. Ein Nachweis, der die eine Kette prüft und die andere annimmt, prüft das
  Falsche.
- **`compareWizardState.saveComparePreset()` bleibt toter Code.** Kein Aufrufer mehr
  (`CompareEditor.svelte` existiert nicht mehr) — nicht angefasst, wie im Kontextdokument
  vermerkt. Verwechslungsgefahr mit `saveNewPreset()` (live, s. „Eigener Fund" oben) bleibt
  bestehen, solange der Name nicht aufgeräumt wird.
- **Namenskollision Trip vs. Compare bleibt bestehen.** `Trip.SendPremiumSms` ist ein
  abgeleitetes Briefing-Flag, `ComparePreset.SendPremiumSms` das Alarm-Opt-in (R8 aus dem
  Kontextdokument) — diese Scheibe benennt das Frontend-Pendant bewusst `sendPremiumSms` auf der
  Wizard-Rune-Ebene (analog `sendTelegram`/`sendSms`, die dieselbe Doppelbedeutung tragen), löst
  die zugrunde liegende Namensmehrdeutigkeit aber nicht auf.
- **Kein automatischer Soll-Ist-Abgleich zwischen den beiden Feldlisten** (`buildHubPutPayload`
  vs. `buildComparePresetSavePayload`, Landmine 3). AC-9 beweist Verhaltensgleichheit zum
  Prüfzeitpunkt, keine strukturelle Garantie, dass eine künftige fünfte Kanal-Erweiterung nicht
  erneut nur eine der beiden Stellen träfe — dieselbe Grenze, die `feat_1717_s3_premium_sms_ui.md`
  für die dortige Dedupe-Logik bereits dokumentiert hat.
- **Radar-/Regen-Alarme bleiben absichtlich unverändert** (Scheibe B). Ein Nutzer, der nach
  dieser Scheibe den Premium-SMS-Haken setzt, könnte annehmen, dass jetzt **alle** Alarmtypen
  ankommen — das stimmt für Gewitter-, Änderungs- und amtliche Alarme, nicht für Regen-/
  Radar-Alarme. Kein UI-Hinweis auf diese Teilmenge ist Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Diese Scheibe exponiert ausschließlich die in ADR-0049 bereits
  getroffene Entscheidung (Kanalname `premium_sms`, eigenes Tarif-Gate) und die in ADR-0046
  festgelegte Pflicht zur Schwellenanwendung in der Alarm-Oberfläche — sie trifft keine neue
  Architekturentscheidung und weicht von keiner bestehenden ab.

## Changelog

- 2026-08-11: Initial spec erstellt — Issue #1745, Scheibe A (Premium-SMS in der
  Alarm-Kanal-Auswahl)
