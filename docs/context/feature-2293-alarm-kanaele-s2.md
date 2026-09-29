# Context: feature-2293-alarm-kanaele-s2

Issue #2293 · Epic #2345 (P1 Kanal-Parität) · Folge-Scheibe zu #2279 S1 · soll #2212 (Alarm-Seite) schließen.
Stand gemessen auf `168a66cb` (2026-09-28).

## Request Summary

Der Ortsvergleich bekommt ein eigenes `alert_channels`-Objekt (E-Mail/Telegram/SMS/Premium-SMS) wie der Trip.
Damit sind Alarm-Kanäle getrennt von den Briefing-Kanälen des Versand-Reiters (flache `send_*`) schaltbar, inklusive
E-Mail aus. Dazu gehören Go-Feld, Python-Parität, Alarme-Reiter-Schreibweg und eine Bestandsmigration flach → Objekt.

## Ist-Stand je Schicht

### Python — Lese-/Auflösungsseite FERTIG (#2279 S1)
- `src/services/alert_channels.py:29-93` `resolve_alert_channels(override, inherited, …)`: gesetzter `override` **ersetzt**
  den geerbten Anteil vollständig (Menge der truthy Kanäle, kein E-Mail-Default); danach Regel-/Metrik-Union, Tarif-Gates.
- `:123-137` `_compare_channel_inputs(preset: dict)`: liest `preset["alert_channels"]` (nur dict), geerbt = `{"email"}` +
  `send_telegram/send_sms/send_premium_sms`. `:187-213` `effective_alert_channels` dispatcht dict (Vergleich) vs. Trip.
- Aufrufer (Alarme): `compare_alert.py:110,603,632`, `compare_official_alert.py:466-472`, `compare_radar_alert.py:168`.
- Briefing-Kanäle: `compare_alert_channels.py:32-53` `effective_compare_briefing_channels` ignoriert `alert_channels`
  bewusst, E-Mail immer an (Scheduler `scheduler_dispatch_service.py:414-427,649`).
- Modell `src/app/models.py:1289-1368` `ComparePreset`: benannt nur `send_telegram`/`send_sms`; **`send_premium_sms`
  und `alert_channels` fehlen als Felder**, liegen aber in `raw` (:1368). Loader `loader.py:241-296` / `:349-357`
  (`to_dict` gibt `raw` zurück) ⇒ Roundtrip in Python verlustfrei.

### Go — Feld fehlt, Merge-Kernel ist bereits generisch (#2285)
- `internal/model/compare_preset.go:91-97`: `SendTelegram`, `SendSms`, `SendPremiumSms` (`*bool`). **Kein `SendEmail`,
  kein `AlertChannels`.** Kommentar :93-96 „hat kein alert_channels-Sub-Objekt“ muss weg; :110-112 dokumentiert:
  eigener Merge unnötig, **Struct-Feld Pflicht**, sonst verwirft `json.Unmarshal` den Schlüssel.
- Typ zum Wiederverwenden: `internal/model/trip.go:214-219` `AlertChannelsConfig{Email,Telegram,Sms,PremiumSms *bool}`;
  Trip-Feld `trip.go:151`.
- Beide PUT-Wege laufen über `applyComparePresetPatch` (`internal/handler/compare_preset.go:292-354`):
  `UpdateComparePresetHandler` (:406) und `UpdateBriefingHandler` Zweig vergleich (`briefing_subscription.go:264`).
  `mergeBriefingPatch` (`briefing_subscription.go:174-197`): Bestand → Map, Top-Level-Patch überschreibt, Objekt↔Objekt
  eine Ebene tief via `mergeConfigMap` (`config_merge.go:11-22`), dann typisierter Unmarshal. Explizites `null` löscht.
- **Heute geht ein `alert_channels` bei jedem Go-Schreibweg verloren** (PUT, `/state`-PATCH, `SaveComparePreset`
  `internal/store/compare_preset.go:209-231`, Go-Lade-Migrationen) — kein Raw-Bucket.
- Create `CreateComparePresetHandler` (:193-277) dekodiert direkt ins Struct → Default für Neuanlage entscheiden
  (Vorbild `OfficialWarnings` :254-256).

### Frontend — Alarme-Reiter schreibt heute flache Felder, E-Mail hart `true`
- `shared/AlarmeTab.svelte` :100-102 Props `sendTelegram/sendSms/sendPremiumSms`; `displayChannelState` :295-305
  (Vergleich: `email: true` fest :302-303); `handleChannelToggle` :306-311 → `onChannelToggle`;
  Telegram-Kurzstil-Schalter an `sendTelegram` gekoppelt :541; Speichern :440-474.
- `compare/alarmePropsAus.ts:95-101` Toggle → `wiz.sendTelegram/sendSms/sendPremiumSms`, E-Mail ignoriert.
- `shared/alarmeVergleichSpeicherung.ts`: Snapshot/Hydration :40-42, :69-74; `baueAlarmNutzlast` :107-140 ist laut
  Docstring **die Nahtstelle für #2293** (auch `rework_2276_s2_alarme.md:337-341`); ruft
  `compare/compareEditorSave.ts:115` `buildComparePresetSavePayload` → flache `send_*` :236-239; Rollback-Liste :186-189.
- Trip-Vorlage: `alarme-tab/alarmeDeliveryPayload.ts:91-117` (immer alle vier Booleans + `alert_channels`),
  `alarme-tab/tripChannelReconstruction.ts:19-39` (`alert_channels` vorrangig, sonst `report_config.send_*`).
- Versand-Reiter (Vergleich) `VersandTab.svelte:394-409`: E-Mail/Telegram/SMS, ohne Premium-SMS; E-Mail-Schalter
  wird **nicht** gespeichert (`versandVergleichSpeicherung.ts:79` hydratisiert `sendEmail: true` fest). Das ist #2212
  Briefing-Seite.
- **Geteilte Felder heute:** `wiz.sendTelegram`/`wiz.sendSms` schreiben BEIDE Reiter; `send_premium_sms` nur Alarme.
- Neuanlage `compareEditorSave.ts:353-386` `buildNewComparePresetPayload` schreibt die drei `send_*`.
- TS-Typ `frontend/src/lib/types.ts:633-699` `ComparePreset` ohne `alert_channels`/`send_email`; Trip-Vorlage :381.

### Migration
- Speicherort: `data/users/<uid>/briefings/<id>.json` mit `kind="vergleich"` (Trips gleiches Verzeichnis, `kind="route"`).
- Vorlage: `scripts/migrate_1361_drop_compare_hour_from_to.py` (globbt `*/briefings/*.json`, filtert kind, Dry-Run,
  Backup, zwei Phasen). `migrate_1258_official_warnings.py` globbt veraltet `compare_presets.json` — nicht kopieren.
- Äquivalenz: `{email:true, telegram:send_telegram, sms:send_sms, premium_sms:send_premium_sms}` ergibt über
  `resolve_alert_channels` exakt dieselbe Kanalmenge wie heute (Gates greifen identisch).

## Existing Specs / Doku
- `docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md` (:28, :299 Folge-Scheibe = #2293)
- `docs/context/rework-2279-alert-kanal-aufloesung.md:85-98` (Scheibenschnitt S1/S2)
- `docs/specs/modules/rework_2276_s2_alarme.md:337-341`, `rework_2276_s6c_alarme.md:74`
- `docs/specs/modules/alert_metric_channels.md:92` — verlangt, #2293 gegen die Zielform (Kanal je Metrik) zu schneiden
- `docs/specs/modules/fix_2285_compare_put_merge_kernel.md`, `compare_official_alert_channels.md`
- `docs/reference/api_contract.md` :923-934 (alert_channels nur Trip), :2114-2158 ComparePreset-DTO, :2158 „Ortsvergleich
  hat keins“ → anpassen
- Go-Testvorlage: `internal/handler/compare_preset_alert_channel_thresholds_test.go` (beide PUT-Wege, Erhalt, Merge,
  Create, Mandanten-Isolation :613)

## Dependencies
- Upstream: `AlertChannelsConfig` (Go), `mergeBriefingPatch`/`mergeConfigMap`, `resolve_alert_channels`.
- Downstream: alle Compare-Alarmpfade (Abweichung, amtliche Warnungen, Radar), Alarme-Reiter, Versand-Reiter
  (geteilte Felder), Neuanlage `/compare/new`.

## Risiken & Abweichungen vom Ticket-Text
1. **Reihenfolge Go → Migration zwingend.** Migration vor deploytem Go-Feld ⇒ jeder Go-Schreibweg löscht still.
   Deshalb Migration erst nach Prod-Deploy des Go-Felds ausführen (oder Go-Lade-Migration statt Skript — Analyse).
2. **Einfrier-Effekt ist gewollt (AC-4)**, verlangt aber: Alarme-Reiter schreibt ab sofort `alert_channels`, nie mehr
   `send_telegram/sms`. Sonst ändert der Alarme-Reiter die Briefing-Kanäle mit.
3. **Kein `send_email` beim Vergleich existiert** (Go/Python/TS). #2293 schließt #2212 nur für **Alarme**; der
   E-Mail-Schalter im Versand-Reiter (Briefing) bleibt wirkungslos → Analyse: in dieser Scheibe mitnehmen oder #2212
   offen lassen.
4. **`send_premium_sms` verwaist**, sobald der Alarme-Reiter nur noch `alert_channels.premium_sms` schreibt: kein
   Briefing-Schalter dafür, aber `effective_compare_briefing_channels` liest es. Klären (Versand-Reiter bekommt
   Premium-SMS-Schalter vs. Feld bleibt Altlast) — berührt #2275 (Premium-SMS im Compare-Briefing ist verdrahtet).
5. Telegram-Kurzstil-Schalter (`AlarmeTab.svelte:541`) an `alert_channels.telegram` umhängen.
6. `null` im Patch löscht → Client sendet immer alle vier Booleans (wie Trip).
7. #2285 macht den im Ticket geforderten eigenen Feld-Merge überflüssig — Tests auf beiden PUT-Wegen bleiben Pflicht.
8. Neuanlage-Default: `alert_channels` bei `/compare/new` setzen oder `nil` lassen (dann gelten flache Felder)?
9. Datei-Überschneidung mit #2375 (`alarmeVergleichSpeicherung.ts`, Konflikt-Retry) — nicht mitändern.
10. Veraltete Zeilenangaben im Ticket (trip.go, models.py, AlarmeTab, VersandTab); Skriptname sollte `migrate_2293_…`.

## Analysis

### Type
Feature (Folge-Scheibe S2 zu #2279).

### Verifizierte Kernbefunde (Phase 2, 2026-09-28)
- **Bestandsquelle beim PUT ist normalisiert:** beide PUT-Wege laden `original` über `s.LoadComparePresets()`
  (`internal/handler/compare_preset.go:380`), das je Preset `NormalizeComparePreset` ruft (`internal/store/compare_preset.go:78`).
  `applyComparePresetPatch` (`handler/compare_preset.go:292-354`) merged den Patch auf dieses `original` und ruft danach
  nochmals `NormalizeComparePreset` (:347). Create ruft es bei :220.
- **Keine Schreiber der flachen Kanalfelder am Merge vorbei:** `grep SendTelegram= / SendSms= / SendPremiumSms=` in
  `internal/`+`cmd/` trifft nur `internal/store/trip.go:64-90` (Trip, nicht Vergleich). Python: nur `loader.py:1871-1872`
  (Trip). ⇒ jede Änderung an `send_*` beim Vergleich läuft durch `applyComparePresetPatch` bzw. Create.
- **Premium-SMS:** Der Versand-Reiter hat im vergleich-Zweig **keinen** Premium-SMS-Schalter
  (`VersandTab.svelte:396-409`, Kommentar :150 „ADR-0049"; `versandVergleichSpeicherung.ts:122`). Die Prämisse von
  `fix_2275_compare_premium_sms_versand.md:19` („im Versand-Reiter gibt es einen Premium-SMS-Schalter") ist falsch —
  der einzige UI-Schreiber von `send_premium_sms` ist der **Alarme-Reiter** (`AlarmeTab.svelte:301` → `alarmePropsAus.ts:100`
  → `compareEditorSave.ts:239,386`). Seit #2275 (cba91954, 26.09.) schaltet also der Alarm-Premium-SMS-Schalter
  zugleich kostenpflichtige Premium-SMS-**Briefings** ein. Nutzersichtbar ⇒ eigenes Issue (Triage (a)), nicht in dieser Scheibe.
- **#2212 wird NICHT geschlossen:** beide Einträge (B1-48, B1-65) betreffen den E-Mail-Schalter im **Versand**-Reiter
  (Briefing, `send_email` fehlt; `compareHubWizardBridge.ts:346-350`). #2293 ändert nur die Alarm-Seite. PR nur „Refs #2212".
- **`alert_metric_channels.md`** (draft, Feld `AlertMetricChannels` existiert bereits als reine Verrohrung,
  `compare_preset.go:106-113`): andere Schicht („je Metrik"), besteht laut deren Zeile 92 neben `alert_channels` („je Abo").
  Kein Konflikt; `resolve_alert_channels` ist für beide Schichten ausgelegt.
- **Offene PRs** (#2440, #2116, #2095, #2094, #2084, #1997) berühren keine Datei dieser Scheibe. #2375 ist nur Issue.

### Entscheidungen (Tech Lead)
1. **Kein Migrationsskript — deterministische Materialisierung in `store.NormalizeComparePreset`:** ist `AlertChannels == nil`,
   wird es aus `{email:true, telegram:SendTelegram, sms:SendSms, premium_sms:SendPremiumSms}` gebaut (nil-Pointer ⇒ false).
   Deterministisch (keine Zeit), daher auf Lese-, Schreib- und Create-Pfad sicher (Muster `PausedAt`-Entpausen-Hälfte).
   **Begründung:** Ein Skript hat ein Fenster „Skript läuft vor Go-Deploy ⇒ jeder Go-Schreibweg löscht still"
   (BUG-DATALOSS-GR221-Muster); die Materialisierung kommt mit dem Go-Feld im selben Binary und hat dieses Fenster nicht.
   Weil `original` beim PUT bereits normalisiert geladen wird, ist `alert_channels` VOR dem Patch aus dem **alten** Stand
   materialisiert ⇒ ein Versand-Reiter-Save ändert nur `send_*` (AC-4 ab dem ersten Schreibzugriff).
   **Abweichung vom Ticket (in Spec benennen):** AC-3 (`--execute`, Backup, Report, zweiter Lauf No-Op) entfällt ersatzlos;
   dessen Absicht (Kanalmenge vorher = nachher) bleibt als Test: Tabelle aller 8 Flach-Kombinationen × Tarif-Gates,
   `resolve_alert_channels` ohne vs. mit materialisiertem `alert_channels` ⇒ identische Menge.
   Python-Leser sehen bis zum ersten Go-Schreibzugriff weiter die flachen Felder ⇒ exakt dieselbe Menge (Äquivalenz oben).
2. **Neuanlage:** Create materialisiert über denselben Normalize-Aufruf (:220) ⇒ neues Preset trägt sofort `alert_channels`.
   Ein Test fixiert das (bewusst gewählt statt „nil lassen", damit genau EIN Regelort existiert).
3. **Premium-SMS-Kopplung bleibt als Übergang:** Der Alarme-Reiter schreibt `alert_channels.premium_sms` **und** weiterhin
   `send_premium_sms`. Entkoppeln würde bei `true` einen kostenpflichtigen Briefing-Kanal hinterlassen, den kein UI-Weg mehr
   abschaltet. Eigenes AC: „Premium-SMS-Schalter im Alarme-Reiter setzt auch `send_premium_sms`" — dokumentierte Ausnahme
   von AC-4-„umgekehrt", aufgehoben durch das neue Issue (Versand-Premium-SMS-Schalter).
4. **Telegram/SMS/E-Mail entkoppelt:** Alarme-Reiter schreibt nur noch `alert_channels` (immer alle vier Booleans, weil
   `null` im Patch löscht), nie mehr `send_telegram`/`send_sms`. Versand-Reiter bleibt auf `send_*`.
5. **Hydration im Frontend** nach `tripChannelReconstruction.ts:19-39`: `alert_channels` vorrangig, sonst flache Felder
   (Defense-in-Depth, obwohl Go ab jetzt immer materialisiert ausliefert). E-Mail-Toggle im Vergleich nicht mehr hart `true`
   (`AlarmeTab.svelte:302-303`). Kurzstil-Schalter (`AlarmeTab.svelte:541`) an `alert_channels.telegram` koppeln.
6. **Alle vier Kanäle aus:** Verhalten 1:1 vom Trip-Pendant übernehmen (in Spec prüfen und benennen, keine neue Regel).

### Pflicht-Tests (RED)
- **AC-4-Kerntest, beide PUT-Wege** (`/api/compare/presets/{id}` und Briefing-PUT Zweig vergleich): Preset-Datei ohne
  `alert_channels`, `send_telegram=true`; PUT nur `{"send_telegram": false}` ⇒ `send_telegram==false` UND
  `alert_channels.telegram==true`. Umgekehrt PUT `alert_channels` ⇒ `send_telegram` unverändert.
- Roundtrip: PUT ohne `alert_channels` erhält den Bestand (beide Wege); `/state`-PATCH erhält ihn.
- Äquivalenz-Tabelle (Python, Kern) wie unter Entscheidung 1.
- Create materialisiert; GET auf Legacy-Datei liefert materialisiertes Objekt ohne Write-Back.
- Mandanten-Test zwei Nutzer (Vorlage `compare_preset_alert_channel_thresholds_test.go:613`).
- Frontend: Alarme-Reiter-Nutzlast enthält alle vier `alert_channels`-Booleans + `send_premium_sms`, aber kein
  `send_telegram`/`send_sms`; Hydration aus `alert_channels`; E-Mail-Toggle speicherbar.
- Live (Staging): E-Mail aus, Telegram an im Alarme-Reiter ⇒ Abweichungsalarm nur per Telegram (IMAP leer).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/compare_preset.go` | MODIFY | Feld `AlertChannels *AlertChannelsConfig` (Typ aus `trip.go:214-219`), Kommentar :93-96 korrigieren |
| `internal/store/compare_preset.go` | MODIFY | Materialisierung in `NormalizeComparePreset` |
| `internal/handler/compare_preset_alert_channels_test.go` | CREATE | Go-Tests (Name nach Verhalten) |
| `src/app/models.py` | MODIFY | `ComparePreset.alert_channels` + `send_premium_sms` benannt (1:1 zu Go), Loader-Roundtrip |
| `frontend/src/lib/types.ts` | MODIFY | `ComparePreset.alert_channels` |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Vergleichs-Zweig: vier Kanäle inkl. E-Mail, Kurzstil-Kopplung |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` | MODIFY | Toggle → Alarm-Kanal-State statt `wiz.send*` |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | Snapshot/Hydration/`baueAlarmNutzlast` (Nahtstelle laut Docstring) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | Nutzlast `alert_channels`, Rollback-Liste |
| `docs/reference/api_contract.md` | MODIFY | :923-934, :2114-2158 (Drift-Test) |
| Tests Python/Frontend | CREATE | siehe Pflicht-Tests |

### Scope Assessment
- Produktive Dateien: ~9; geschätzt +150–190 / −30 produktive LoC (unter 250, kein Skript).
- Risk Level: **MEDIUM** — Persistenz-Feld mit Pre-Snapshot-Hook, Fläche ist Alarm-Versand aller drei Compare-Alarmpfade;
  Materialisierung ist rein additiv und äquivalent, Deploy in EINEM Stand (Go + Frontend) hebt das Reihenfolge-Risiko auf.

### Dependencies
Upstream: `AlertChannelsConfig`, `mergeBriefingPatch`/`mergeConfigMap` (#2285), `resolve_alert_channels` (#2279 S1).
Downstream: `compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py`, Alarme-Reiter, `/compare/new`.
Sequenz: #2375 (Konflikt-Retry mit Voll-Spread) muss `alert_channels` mitführen — im jeweils späteren PR referenzieren.

### Open Questions
- Keine für den PO. Premium-SMS-Kopplungsbefund als #2448 angelegt (hebt Übergangs-Kopplung aus Entscheidung 3 auf).
