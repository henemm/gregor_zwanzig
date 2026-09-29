---
entity_id: feat_2293_s2_compare_alarm_kanaele
type: feature
created: 2026-09-28
updated: 2026-09-28
status: draft
version: "1.0"
tags: [alerts, compare, channels, frontend, go, python]
---

# Alarm-Kanäle für den Ortsvergleich: `alert_channels` in Go/Python, Alarme-Reiter, Versand-Premium-SMS (Issue #2293, Scheibe S2, Epic #1374/#2345)

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich bekommt ein eigenes, persistiertes `alert_channels`-Objekt
(E-Mail/Telegram/SMS/Premium-SMS) für den Alarm-Versand — bislang existiert
diese Auflösung seit #2279 (S1) nur im Python-Kern und liest den Roh-Dict;
ohne Go-Struct-Feld verwirft jeder Go-Schreibweg ein per API gesetztes
`alert_channels` (BUG-DATALOSS-GR221-Muster). Diese Scheibe macht den Schalter
für den Nutzer erreichbar: Go-Feld + deterministische Materialisierung (ersetzt
das im Ticket vorgesehene Migrationsskript), Python-Modellparität, Umbau des
geteilten Alarme-Reiters auf das Trip-Muster (E-Mail nicht mehr hart an),
Trennung der Alarm- von der Briefing-Nutzlast gegen einen Same-Tab-Race
(#2381-Muster), und — als Teil derselben Scheibe statt separater Freigabe —
ein eigener Premium-SMS-Schalter im Versand-Reiter (löst #2448 mit ab, das die
heutige stille Kopplung „Alarm-Premium-SMS-Klick schaltet Briefing-Premium-SMS
mit" beschreibt).

## Source

- **Go:** `internal/model/compare_preset.go`, `internal/store/compare_preset.go`,
  `internal/handler/compare_preset.go`, `internal/handler/briefing_subscription.go`
- **Python:** `src/app/models.py`, `src/app/loader.py`, `src/services/alert_channels.py` (unverändert, Leser)
- **Frontend:** `frontend/src/lib/components/shared/AlarmeTab.svelte`,
  `frontend/src/lib/components/shared/VersandTab.svelte`,
  `frontend/src/lib/components/compare/alarmePropsAus.ts`,
  `frontend/src/lib/components/compare/versandPropsAus.ts`,
  `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts`,
  `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`,
  `frontend/src/lib/components/compare/compareEditorSave.ts`,
  `frontend/src/lib/types.ts`

Betroffene Schichten: **Go-API** (`internal/`), **Python-Core**
(`src/app/models.py`, `src/app/loader.py` — reine Modellparität, kein neuer
Leser), **Frontend** (`frontend/src/lib/components/{shared,compare}/`).

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/model/compare_preset.go` | MODIFY | Feld `AlertChannels *AlertChannelsConfig \`json:"alert_channels,omitempty"\`` (Typ aus `trip.go:214-219`, unverändert wiederverwendet) direkt nach `SendPremiumSms` (heute Zeile 97); Kommentar an `SendPremiumSms` (Zeilen 93-96, „der Ortsvergleich hat kein alert_channels-Sub-Objekt wie der Trip") korrigieren — die Prämisse ist ab dieser Scheibe falsch |
| `internal/store/compare_preset.go` | MODIFY | Neue Funktion `materializeAlertChannels(p, cleanupLegacyPremiumSms bool)` (EIN Regelort, Nachtrag Abschnitt 7); `NormalizeComparePreset` (Zeilen 21-42) ruft sie mit `false`, `normalizeLoadedComparePreset` (Zeilen 56-82) zusätzlich VOR dem `NormalizeComparePreset`-Aufruf (Zeile 78) mit `true` |
| `internal/handler/compare_preset_alert_channels_test.go` | CREATE | Go-Tests (Name nach Verhalten, Vorlage `compare_preset_alert_channel_thresholds_test.go`): beide PUT-Wege, Roundtrip, Create, Mandanten-Isolation, Alt-Bestand-Bereinigung (AC-15/16/17) |
| `src/app/models.py` | MODIFY | `ComparePreset`-Dataclass (ab Zeile 1288): `send_premium_sms: Optional[bool] = None` und `alert_channels: Optional[dict] = None` ergänzen (1:1 zu Go, analog zu `alert_metric_channels` zwei Zeilen darüber) |
| `src/app/loader.py` | MODIFY | `ComparePreset(...)`-Konstruktion (ab Zeile 248): `send_premium_sms=data.get("send_premium_sms")` und `alert_channels=data.get("alert_channels")` ergänzen (analog `alert_metric_channels=data.get(...)`, Zeile 293) |
| `src/services/compare_alert_channels.py` | MODIFY | `effective_compare_briefing_channels` (Zeilen 29-49): Premium-SMS-Opt-in zählt nur als Briefing-Kanal, wenn `preset.get("alert_channels") is not None` (Nachtrag Abschnitt 7) |
| `tests/tdd/test_compare_premium_sms_legacy_cleanup.py` | CREATE | Python-Kern-Test für AC-15/AC-16 (Briefing-Guard vor jedem Go-Schreibzugriff) |
| `frontend/src/lib/types.ts` | MODIFY | `ComparePreset`-Interface (ab Zeile 632): `alert_channels?: { email: boolean; telegram: boolean; sms: boolean; premium_sms: boolean }` ergänzen |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `CompareEditorEdits` (Zeile 29ff): neues optionales Feld `alertChannels?: { email: boolean; telegram: boolean; sms: boolean; premium_sms: boolean }`; Body-Bau (Zeile 205ff): `...(edits.alertChannels !== undefined ? { alert_channels: edits.alertChannels } : {})`; `buildNewComparePresetPayload` (Zeile 353ff) sendet ab jetzt IMMER `alert_channels` (neben `send_premium_sms`, Zeile 386) mit den drei Neuanlage-Feldern, damit `AlertChannels` beim Create nie `nil` ist (Nachtrag Abschnitt 7) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Vergleichs-Zweig: E-Mail-Toggle real (nicht mehr hart `true`, Zeilen 295-305), Kurzstil-`disabled` an den Alarm-Telegram-Zustand statt an `sendTelegram` (Zeile ~541), Persistenz-Brücke sendet Kanal-Objekt statt drei Flach-Felder |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` | MODIFY | `onChannelToggle` (Zeilen 95-101): schreibt ein Alarm-Kanal-Objekt (alle vier Kanäle inkl. E-Mail) statt `wiz.sendTelegram/sendSms/sendPremiumSms`; neue Hydrations-Funktion `reconstructCompareAlertChannels` (Vorbild `tripChannelReconstruction.ts`) |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | `AlarmSnapshot`/`AlarmHydrationTarget`: `channels`-Feld (vier Booleans) statt `sendTelegram?/sendSms?/sendPremiumSms?`; `baueAlarmNutzlast` (Zeile 107ff) übergibt `alertChannels`, entfernt `send_telegram`/`send_sms`/`send_premium_sms` aus dem fertigen Body; `rollbackAlarmSnapshot`-Feldliste angepasst |
| `frontend/src/lib/components/compare/versandPropsAus.ts` | MODIFY | `VersandZustandsQuelle`/Rückgabe-Bündel: `sendPremiumSms` als neuntes Klasse-A-Feld + `onSendPremiumSmsChange` (#2448) |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | MODIFY | `VersandSnapshot`/`VersandHydrationTarget`: `sendPremiumSms` ergänzen; `hydrateVersandFieldsFromPreset`, `versandSnapshotAus`, `rollbackVersandSnapshot`-Feldliste (Zeilen 192-202) erweitern; `baueVersandNutzlast` (Zeile 122ff) übergibt `sendPremiumSms`, entfernt `alert_channels` aus dem fertigen Body; veralteten ADR-0049-Kommentar korrigieren |
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | Vergleichs-Zweig (Zeilen 394-409): `sendPremiumSms`/`onSendPremiumSmsChange`-Props ergänzen, an `VTBriefingChannels` durchreichen (`channels.premium_sms`, `onPremiumSmsChange`) — Anwesenheit von `onPremiumSmsChange` ist das bestehende Freischalt-Gate der Komponente (`VTBriefingChannels.svelte:57-63`) |
| `docs/reference/api_contract.md` | MODIFY | :923-934 (Abschnittstitel/-text auf „Trip UND Ortsvergleich" verallgemeinern), :2158 (Kommentar „Ortsvergleich hat keins" korrigieren, `AlertChannels`-Feld in der DTO-Tabelle ergänzen) |

## Estimated Scope

- **LoC:** produktiv ≈ +215/−20 (Go ≈ +45, Python ≈ +10, Frontend ≈ +160/−20 inkl. Nachtrag Altbestand-Bereinigung); Tests zusätzlich ≈ +400 (Go + Python + Frontend, mehrere neue Dateien inkl. `test_compare_premium_sms_legacy_cleanup.py`).
- **Files:** 16 produktiv (3 neu: ein Go-Test, zwei Python-Tests), plus mehrere neue Frontend-Testdateien.
- **Effort:** medium-high.
- **Hinweis LoC-Limit:** die produktive Schätzung liegt über dem 250-LoC-Standardlimit (Go-Materialisierung inkl. Altbestand-Bereinigung + Python-Parität + 3 Frontend-Speicherwege + Versand-Premium-SMS in einer Scheibe). Vor `/50-implement` `workflow.py set-field loc_limit_override 300` setzen (nach `workflow.py status`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go::AlertChannelsConfig` | type | wiederverwendeter Go-Typ, keine Änderung nötig |
| `internal/handler/compare_preset.go::applyComparePresetPatch`/`mergeBriefingPatch` (#2285) | function | generischer Feld-Level-Merge, kein eigener Merge-Code für `alert_channels` nötig |
| `src/services/alert_channels.py::resolve_alert_channels`/`_compare_channel_inputs` (#2279 S1) | function | unveränderter Leser — profitiert von der Materialisierung, ohne selbst geändert zu werden |
| `frontend/.../shared/alarme-tab/tripChannelReconstruction.ts`, `alarmeDeliveryPayload.ts` | module | Vorbild für die Compare-Hydration/-Nutzlast (Trip-Muster: immer alle vier Booleans) |
| `frontend/.../shared/versand-tab/VTBriefingChannels.svelte` | component | bereits gemeinsame Komponente, Premium-SMS-Block wird nur über die Prop `onPremiumSmsChange` freigeschaltet — keine Komponentenänderung nötig |

## Implementation Details

### 1. Go — Feld + Materialisierung (ersetzt Migrationsskript, Entscheidung 1)

`internal/model/compare_preset.go`: neues Feld

```go
AlertChannels *AlertChannelsConfig `json:"alert_channels,omitempty"`
```

direkt nach `SendPremiumSms` (heute Zeile 97). Der Kommentar an `SendPremiumSms`
(„der Ortsvergleich hat kein alert_channels-Sub-Objekt wie der Trip, die
Kanaele sind flache Top-Level-Felder") entfällt/wird korrigiert — er
beschreibt ab dieser Scheibe nicht mehr den Ist-Stand.

`internal/store/compare_preset.go::NormalizeComparePreset` (Zeilen 21-42)
bekommt einen zusätzlichen Block:

```go
if p.AlertChannels == nil {
    email := true
    telegram := p.SendTelegram != nil && *p.SendTelegram
    sms := p.SendSms != nil && *p.SendSms
    premiumSms := p.SendPremiumSms != nil && *p.SendPremiumSms
    p.AlertChannels = &model.AlertChannelsConfig{
        Email: &email, Telegram: &telegram, Sms: &sms, PremiumSms: &premiumSms,
    }
}
```

Deterministisch (keine Zeit, keine I/O) und damit sicher auf **jedem**
Aufrufpfad von `NormalizeComparePreset`: Lesepfad (`normalizeLoadedComparePreset`
→ `LoadComparePresets`/`LoadComparePreset`, Datei `store/compare_preset.go`
Zeilen 61-173), Schreibpfad (`SaveComparePreset`, Zeilen 209-231) und
Merge-Pfad (`applyComparePresetPatch` ruft `store.NormalizeComparePreset(&p)`
nach dem Merge, `internal/handler/compare_preset.go`). Beide PUT-Wege
(`UpdateComparePresetHandler`, `internal/handler/compare_preset.go:357-406`;
`UpdateBriefingHandler`-Zweig `vergleich`, `internal/handler/briefing_subscription.go`)
laden `original` über `s.LoadComparePresets()` — `alert_channels` ist damit
**vor** dem Merge aus dem alten Bestand materialisiert. Ein Versand-Reiter-PUT,
das `alert_channels` nicht mitschickt, überschreibt es folglich nie (AC-4 ab
dem ersten Schreib- oder Lesezugriff, nicht erst nach einer Migration).

`CreateComparePresetHandler` (`internal/handler/compare_preset.go:193-277`)
ruft `store.NormalizeComparePreset(&preset)` bereits (Zeile ~220) — ein neues
Preset trägt damit sofort ein materialisiertes `alert_channels`
(`{email:true, telegram:false, sms:false, premium_sms:false}`, da `SendTelegram`
u.a. bei Neuanlage `nil` sind), ohne eigenen Code (Entscheidung 2).

> **Nachtrag (Implementation Details Abschnitt 7):** der obige Materialisierungs-Block
> wird in eine eigene Funktion `materializeAlertChannels(p, cleanupLegacyPremiumSms bool)`
> gezogen, weil der Lade-Pfad zusätzlich einen Altbestand-Sonderfall braucht
> (ein Alt-Bestand-`send_premium_sms=true` ohne `alert_channels` wird beim Lesen
> auf `false` zurückgesetzt). Die hier gezeigte Ableitungslogik bleibt inhaltlich
> unverändert — Abschnitt 7 ist die vollständige, verbindliche Fassung.

### 2. Python — Modellparität (kein neuer Leser)

`src/app/models.py::ComparePreset` (Dataclass ab Zeile 1288): zwei neue
optionale Felder, 1:1 zu Go, an der Stelle wo `send_telegram`/`send_sms`
bereits stehen bzw. direkt vor `alert_metric_channels`:

```python
send_premium_sms: Optional[bool] = None
alert_channels: Optional[dict] = None
```

`src/app/loader.py` (Konstruktion ab Zeile 248): `send_premium_sms=data.get("send_premium_sms")`
neben Zeile 277, `alert_channels=data.get("alert_channels")` neben Zeile 293
(`alert_metric_channels`). `src/services/alert_channels.py::_compare_channel_inputs`
(Zeilen 123-137) liest weiterhin über das **Roh-Dict** (`preset.get("alert_channels")`)
— unverändert, kein Aufrufer wird umgestellt. Diese Änderung schließt nur die
Modellparitäts-Lücke, die #2279 S1 als Known Limitation offen ließ (Datei
`docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md` — dort nicht
Scope). `raw` (Zeile ~1368) roundtrippt unverändert.

### 3. Frontend — geteilter Alarme-Reiter auf Trip-Muster (Entscheidungen 4, 5, 6)

**Hydration (`alarmePropsAus.ts`):** neue Funktion `reconstructCompareAlertChannels(preset)`
nach dem Vorbild `tripChannelReconstruction.ts::reconstructTripAlertChannels`
(Datei `frontend/src/lib/components/shared/alarme-tab/tripChannelReconstruction.ts:18-43`):
Vorrang `preset.alert_channels` (seit Go-Materialisierung bei jedem geladenen
Preset gesetzt), Defense-in-Depth-Rückfall `{email:true, telegram:send_telegram,
sms:send_sms, premium_sms:send_premium_sms}` für den (nach dieser Scheibe nur
theoretischen) Fall eines Rohobjekts ohne `alert_channels`. Ersetzt die
bisherige `email: true`-Festlegung in `AlarmeTab.svelte` (Zeilen 295-305).

**Zustand (`AlarmeTab.svelte`):** der Vergleichs-Zweig nutzt ab jetzt
dieselbe lokale `AlertChannelState`-Bruecke wie der Trip-Zweig
(`routeChannelState`/`displayChannelState`, Zeilen 294-311) statt der
Sonderableitung mit hartem `email: true`; `handleChannelToggle` toggelt alle
vier Kanäle uniform (kein `sendTelegram === undefined`-Unterschied mehr
zwischen den Kontexten für diese Entscheidung). Der Kurzstil-Schalter
(Zeile ~541, `disabled={!(sendTelegram ?? false)}`) bindet stattdessen an den
Alarm-Telegram-Zustand (`displayChannelState.telegram`) — Entscheidung 5,
weil `sendTelegram` ab dieser Scheibe ein reines Briefing-Feld ist und mit dem
Alarm-Kanal auseinanderlaufen kann.

**Nutzlast (`alarmeVergleichSpeicherung.ts`):** `AlarmSnapshot`/
`AlarmHydrationTarget` bekommen ein Feld `channels: AlertChannelState` (vier
Pflicht-Booleans, Vorbild `buildAlarmeDeliveryPayload`,
`frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts:91-105`,
das bei fehlendem Kanal wirft statt still zu defaulten) anstelle der drei
optionalen Flach-Felder. `baueAlarmNutzlast` (Zeile 107ff) ruft
`buildComparePresetSavePayload(preset, {..., alertChannels: current.channels})`
und entfernt danach `send_telegram`/`send_sms`/`send_premium_sms` aus dem
zurückgegebenen `body` (Payload-Trennung, s. Abschnitt 4). `rollbackAlarmSnapshot`
(Zeilen 166-190) bekommt `channels` statt der drei Flach-Felder in seiner
Feldliste.

### 4. Payload-Trennung gegen den Same-Tab-Race (Entscheidung/Vorgabe 3)

Beide Reiter bauen ihren Body über `buildComparePresetSavePayload`
(`compareEditorSave.ts:115-118`) mit `{...original, ...}` (Zeile 205) — jedes
Feld aus `original`, das der Aufrufer nicht explizit überschreibt, wandert
unverändert in den Body. Da der Server (`applyComparePresetPatch`) den
kompletten Body als Overlay behandelt (kein sparses Patch-DTO, #2285 AC-3
betrifft nur Server-verwaltete Felder), würde ein veraltetes `original` (Same-Tab:
Alarme-Reiter speichert, während der Versand-Reiter noch das vor diesem Save
gemountete `preset` hält) das inzwischen geänderte Feld beim nächsten Save des
anderen Reiters zurückschreiben — exakt das Muster aus
`reference_etag_schuetzt_nicht_gegen_stale_payload_im_selben_tab.md` (#2381):
ETag/If-Match schützen nur gegen einen fremden Zwischen-Schreiber, nicht gegen
den eigenen, veralteten Spread.

Festlegung: **Nach dem Aufruf von `buildComparePresetSavePayload` entfernt
jeder Reiter die Felder des jeweils anderen aus dem fertigen `body`**, bevor er
ihn zurückgibt:

- `baueAlarmNutzlast` (`alarmeVergleichSpeicherung.ts`): `delete body.send_telegram`,
  `delete body.send_sms`, `delete body.send_premium_sms`.
- `baueVersandNutzlast` (`versandVergleichSpeicherung.ts`): `delete body.alert_channels`.

Damit trägt die Alarm-Nutzlast nie einen (potenziell veralteten) Briefing-Kanal-Wert
und umgekehrt — ein Save des einen Reiters kann das Feld des anderen nicht mehr
versehentlich überschreiben, selbst wenn sein `original`-Snapshot veraltet ist.
Diese Trennung deckt ausschließlich die vier hier betroffenen Felder ab; das
allgemeine Full-Spread-Risiko der übrigen ~30 Felder bleibt bestehen (siehe
Known Limitations, Bezug #2375).

### 5. Versand-Reiter: eigener Premium-SMS-Schalter (#2448)

`versandPropsAus.ts`: `sendPremiumSms` wird ein neuntes Klasse-A-Feld
(Wert + eigener Rückruf + Mitglied der Speicher-Brücke, analog `sendTelegram`/
`sendSms`, Zeilen 44-46/65-67/82-87). `VersandTab.svelte` (Vergleichs-Zweig,
Zeilen 394-409): neue Props `sendPremiumSms?: boolean`,
`onSendPremiumSmsChange?: (an: boolean) => void`; an `VTBriefingChannels`
durchgereicht als `channels.premium_sms` und `onPremiumSmsChange` — die
Anwesenheit von `onPremiumSmsChange` ist bereits das bestehende Freischalt-Gate
der Komponente (`VTBriefingChannels.svelte:57-63`: ohne die Prop bleibt der
feste „bald verfügbar"-Platzhalter stehen, wie heute im Vergleichs-Zweig).
Tarif-Sichtbarkeit (`premium_sms_allowed`) läuft bereits **innerhalb** von
`VTBriefingChannels`/`premiumSmsChannelState.ts` — identisch für beide
Kontexte, keine Änderung dort nötig.

`versandVergleichSpeicherung.ts`: `VersandSnapshot`/`VersandHydrationTarget`
bekommen `sendPremiumSms: boolean`; `hydrateVersandFieldsFromPreset` liest
`preset.send_premium_sms ?? false`; `versandSnapshotAus` und
`rollbackVersandSnapshot` (Feldliste Zeilen 192-202) nehmen das Feld auf;
`baueVersandNutzlast` übergibt `sendPremiumSms: current.sendPremiumSms` an
`buildComparePresetSavePayload` (das Feld `sendPremiumSms` existiert dort
bereits, Zeile 82, bisher nur vom Alarme-Reiter benutzt) und entfernt
anschließend `alert_channels` aus dem Body (Abschnitt 4). Der Kommentar
„`sendPremiumSms` ist KEIN Versand-Feld im Ortsvergleich (ADR-0049)" wird
entfernt — ADR-0049 äußert sich nicht zum Ortsvergleich, die Prämisse war ein
Code-Kommentar, kein ADR-Text (siehe Architektur-Entscheidung unten).

Als Folge schreibt der Alarme-Reiter **ab dieser Scheibe nie mehr**
`send_premium_sms` — nur noch `alert_channels.premium_sms` (Entscheidung 3 des
Kontexts, „Premium-SMS-Kopplung bleibt als Übergang", ist damit durch #2448
aufgehoben und **verworfen**, nicht umgesetzt).

### 6. „Alle vier Kanäle aus" (Entscheidung 6)

Beleg: `_compare_channel_inputs` (`src/services/alert_channels.py:123-137`)
liefert bei gesetztem `alert_channels`-Dict `override = preset["alert_channels"]`;
`resolve_alert_channels` (Zeilen 29-93) ersetzt bei gesetztem `override`
`inherited` **vollständig** durch die truthy gesetzten Kanäle (Zeile 68-69) —
sind alle vier `false`, ist das Ergebnis die leere Menge. Die drei
Compare-Alarmservices (`compare_alert.py:110,603,632`, `compare_official_alert.py:472`,
`compare_radar_alert.py:168`) übergeben `metrics` nie (Default `None`), der
Metrik-Arm (`_metric_channel_sets`, Zeilen 170-184) greift also für den
Vergleich strukturell nie ein. `rule_channel_sets` ist beim Vergleich immer
`[]` (Zeile 137, „der Vergleich kennt keine Alarm-Regeln") — die leere
`inherited`-Menge bleibt damit unverändert (Zeilen 71-77). Es existiert **kein**
Guard, der ein Preset mit allen vier Kanälen aus im Handler (`validateComparePreset`,
`internal/handler/compare_preset.go:112`) oder im Frontend (`AlarmeTab.svelte`,
`alarmePropsAus.ts`) ablehnt oder warnt — identisch zum Trip (dort ebenfalls
kein Guard, `internal/handler/trip.go`, geteilter Kern
`resolve_alert_channels`). **Festgelegtes Verhalten (1:1 vom Trip übernommen,
keine neue Regel):** alle vier Kanäle aus ist eine zulässige Konfiguration und
führt dazu, dass eine ausgelöste Alarm-Meldung über **keinen** Kanal zugestellt
wird (weder E-Mail noch Telegram/SMS/Premium-SMS) — ohne Fehler, ohne
Blockade, ohne UI-Warnung.

### 7. Altbestand-Bereinigung: ungewollte Premium-SMS-Briefings (Nachtrag)

**Befund (PO-Briefing):** Seit #2275 (cba91954, 26.09.) setzt der
Premium-SMS-Schalter im Alarme-Reiter `send_premium_sms` — und
`effective_compare_briefing_channels` (`src/services/compare_alert_channels.py:29-49`)
liest genau dieses Feld als Briefing-Opt-in. Für einen Ortsvergleich-Altbestand
ohne `alert_channels` war der Alarme-Reiter (`alarmePropsAus.ts:95-101`, vor
dieser Scheibe) der **einzige** UI-Weg, der `send_premium_sms` schreiben
konnte — einen Versand-Schalter dafür gab es am Ortsvergleich nie
(`VersandTab.svelte`, Vergleichs-Zweig, hatte vor Abschnitt 5 kein
`onPremiumSmsChange`). Die Nutzer-Absicht hinter einem gesetzten
`send_premium_sms=true` bei einem Alt-Preset war also nachweislich „Premium-SMS
für Alarme", nie „Premium-SMS-Briefings bestellen". Ohne Korrektur behalten
betroffene Bestandsnutzer nach dieser Scheibe weiterhin kostenpflichtige
Premium-SMS-Briefings, die sie nie über einen Briefing-Schalter aktiviert
haben.

**Go — EIN Regelort, zwei Aufrufstellen mit unterschiedlichem Flag:**
`internal/store/compare_preset.go` bekommt eine neue, nicht exportierte
Funktion, die die komplette Materialisierungslogik aus Abschnitt 1 aufnimmt
und um die Alt-Bestand-Bereinigung erweitert:

```go
// materializeAlertChannels ist der EINE Regelort fuer die AlertChannels-
// Materialisierung (Issue #2293 S2). cleanupLegacyPremiumSms=true nur beim
// Lesen einer Bestandsdatei (normalizeLoadedComparePreset): vor dieser
// Scheibe war der Alarme-Reiter der einzige UI-Weg, der send_premium_sms
// schreiben konnte -- ein gesetztes send_premium_sms ohne vorhandenes
// alert_channels traegt also eine Alarm-, keine Briefing-Absicht.
// cleanupLegacyPremiumSms=false bei Create und beim PUT-Merge-Nachlauf
// (NormalizeComparePreset direkt): dort kann send_premium_sms aus dem NEUEN
// Versand-Schalter stammen und muss unangetastet bleiben.
func materializeAlertChannels(p *model.ComparePreset, cleanupLegacyPremiumSms bool) {
    if p.AlertChannels != nil {
        return
    }
    email := true
    telegram := p.SendTelegram != nil && *p.SendTelegram
    sms := p.SendSms != nil && *p.SendSms
    premiumSms := p.SendPremiumSms != nil && *p.SendPremiumSms
    p.AlertChannels = &model.AlertChannelsConfig{
        Email: &email, Telegram: &telegram, Sms: &sms, PremiumSms: &premiumSms,
    }
    if cleanupLegacyPremiumSms && premiumSms {
        falseVal := false
        p.SendPremiumSms = &falseVal
    }
}
```

`NormalizeComparePreset` (Zeilen 21-42, aufgerufen von Create/`SaveComparePreset`/
Merge-Nachlauf) ruft `materializeAlertChannels(p, false)`.
`normalizeLoadedComparePreset` (Zeilen 56-82, der Lade-Pfad aus der Datei,
`LoadComparePresets`/`LoadComparePreset`) ruft **zusätzlich, vor** dem
bestehenden `NormalizeComparePreset(p)`-Aufruf (Zeile 78),
`materializeAlertChannels(p, true)`. Der `if p.AlertChannels != nil { return }`-Guard
macht den zweiten (Zeile 78 dahinter liegenden) Aufruf zum No-Op, sobald der
erste bereits materialisiert hat — die Ableitungslogik existiert exakt
einmal, nur der Bereinigungs-Zweig wird kontextabhängig zu- oder abgeschaltet.
Ein PUT auf ein bereits (beim vorangegangenen `LoadComparePresets()`)
materialisiertes Preset trifft in `applyComparePresetPatch`s
`NormalizeComparePreset`-Nachlauf immer auf `p.AlertChannels != nil` — die
Bereinigung greift dort nie ein zweites Mal und kann ein frisch vom
Versand-Schalter gesetztes `send_premium_sms` nicht nachträglich zurücksetzen.

**Neuanlage bleibt unberührt, weil sie nie in den Bereinigungs-Zweig läuft:**
`buildNewComparePresetPayload` (`compareEditorSave.ts:353-386`, Frontend)
sendet ab jetzt immer ein `alert_channels`-Objekt mit — `CreateComparePresetHandler`
dekodiert den Body damit direkt mit `preset.AlertChannels != nil`, der
`materializeAlertChannels`-Aufruf (egal mit welchem Flag) ist dort ein No-Op.

**Python — dieselbe Bedingung, konsistent für das Zeitfenster vor dem ersten
Go-Schreibzugriff** (ein GET schreibt nicht zurück, s. AC-7): `effective_compare_briefing_channels`
(`src/services/compare_alert_channels.py:29-49`) zählt `send_premium_sms` nur
dann als Briefing-Kanal, wenn `alert_channels` im Preset-Dict existiert:

```python
if (
    preset.get("send_premium_sms")
    and preset.get("alert_channels") is not None
    and premium_sms_allowed(user_id)
):
    channels.add("premium_sms")
```

Die Alarm-Seite ist von alldem unberührt: `_compare_channel_inputs`
(`src/services/alert_channels.py:123-137`) liest `alert_channels.premium_sms`
unverändert für den Alarm-Versand — AC-3 (Äquivalenz der Alarm-Kanalmenge)
gilt weiter uneingeschränkt, die Bereinigung betrifft ausschließlich die
Briefing-Seite (`send_premium_sms`/`effective_compare_briefing_channels`).

## Expected Behavior

- **Input:** PUT `/api/compare/presets/{id}` bzw. PUT `/api/briefings/{id}?kind=vergleich`
  mit `{"alert_channels": {...}}` (Alarme-Reiter, immer alle vier Booleans)
  oder mit `{"send_telegram": ..., "send_sms": ..., "send_premium_sms": ...}`
  (Versand-Reiter) — nie beides gemeinsam aus demselben Reiter.
- **Output:** `alert_channels` steuert ausschließlich den Alarm-Versand
  (Abweichung, amtliche Warnung, Regenradar); `send_telegram`/`send_sms`/
  `send_premium_sms` steuern ausschließlich das planmäßige Briefing. Jedes GET
  liefert ab dieser Scheibe für **jedes** Preset ein materialisiertes
  `alert_channels`-Objekt (auch für Alt-Presets ohne eigenen Schreibzugriff).
- **Side effects:** keine Datenumformung auf der Festplatte allein durch ein
  GET (Materialisierung ist reine In-Memory-Auflösung beim Laden, kein
  Write-Back). Ein PUT/POST persistiert das materialisierte Objekt.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich im Hub, When der Nutzer im Alarme-Reiter
  E-Mail abschaltet und Telegram anlässt, Then persistiert `alert_channels`
  mit `email:false, telegram:true` über PUT, andere Felder bleiben unberührt.

- **AC-2:** Given ein Preset mit gesetztem `alert_channels`, When ein Client
  ein PUT ohne dieses Feld schickt (z. B. der Versand-Reiter), Then bleibt
  `alert_channels` unverändert erhalten — geprüft auf **beiden** PUT-Wegen
  (`/api/compare/presets/{id}` und `/api/briefings/{id}?kind=vergleich`).

- **AC-3:** Given ein Bestands-Preset ohne `alert_channels` (nur flache
  `send_telegram`/`send_sms`/`send_premium_sms`, alle 8 Kombinationen,
  Nutzer mit und ohne Premium-Tier), When die materialisierte
  `alert_channels`-Menge mit der vorherigen (rein flachen) Auflösung
  verglichen wird, Then liefern beide exakt dieselbe Kanalmenge — die
  Materialisierung ändert kein beobachtbares Alarmverhalten.

- **AC-4:** Given ein Ortsvergleich mit gesetztem `alert_channels`, When der
  Nutzer im Versand-Reiter Telegram abschaltet, Then ändert sich nur
  `send_telegram`, `alert_channels` bleibt exakt wie im Alarme-Reiter
  gesetzt — und umgekehrt (Alarme-Reiter-Änderung lässt `send_telegram`/
  `send_sms`/`send_premium_sms` unverändert), geprüft auf beiden PUT-Wegen.

- **AC-5:** Given zwei Nutzer, When jeder seine Alarm-Kanäle an einem
  gleichnamigen Preset setzt, Then sieht keiner die Werte des anderen
  (eigenes Verzeichnis, eigener Store).

- **AC-6:** Given die Neuanlage eines Ortsvergleichs, When das Preset
  angelegt wird, Then trägt die Server-Antwort sofort ein materialisiertes
  `alert_channels`-Objekt (`{email:true, telegram:false, sms:false,
  premium_sms:false}` bei Standard-Neuanlage ohne Opt-ins).

- **AC-7:** Given eine Legacy-Preset-Datei ohne `alert_channels`-Schlüssel,
  When sie per GET gelesen wird, Then liefert die Antwort ein materialisiertes
  `alert_channels`-Objekt, aber die Datei auf der Festplatte bleibt
  unverändert (kein Write-Back durch reines Lesen).

- **AC-8:** Given der Versand-Reiter des Ortsvergleichs, When der Nutzer
  (mit Premium-Tarif) dort den Premium-SMS-Schalter aktiviert, Then
  persistiert `send_premium_sms:true` und der Schalter ist nach einem Reload
  weiterhin aktiv — sichtbar/bedienbar unter denselben Tarif-Bedingungen wie
  beim Trip.

- **AC-9:** Given der Alarme-Reiter des Ortsvergleichs, When der Nutzer dort
  den Premium-SMS-Alarm-Kanal umschaltet, Then ändert sich ausschließlich
  `alert_channels.premium_sms` — `send_premium_sms` (Briefing) bleibt exakt
  auf seinem vorherigen Wert (Entkopplung, löst die stille Kopplung aus
  #2448).

- **AC-10:** Given der Nutzer ändert im selben Tab kurz hintereinander erst
  den Alarme- dann den Versand-Reiter (oder umgekehrt) ohne zwischenzeitigen
  Reload, When beide Speichervorgänge abgeschlossen sind, Then überschreibt
  keiner der beiden PUTs das vom anderen gerade gesetzte Feld — die
  Alarm-Nutzlast enthält nie `send_telegram`/`send_sms`/`send_premium_sms`,
  die Versand-Nutzlast nie `alert_channels`.

- **AC-11:** Given der Alarme-Reiter des Ortsvergleichs, When der Tab
  geöffnet wird, Then zeigt er den tatsächlichen `alert_channels`-Bestand
  (E-Mail-Schalter ist bedienbar, nicht mehr fest „an") und der
  Telegram-Kurzstil-Schalter ist genau dann aktiv, wenn
  `alert_channels.telegram` an ist — unabhängig vom Briefing-Telegram-Zustand.

- **AC-12:** Given ein Ortsvergleich mit `alert_channels` = alle vier Kanäle
  aus, When ein Abweichungs-, Radar- oder amtlicher Alarm ausgelöst wird,
  Then wird er über keinen Kanal zugestellt (kein Fehler, keine Sperre beim
  Speichern) — identisches Verhalten zum Trip mit derselben Konfiguration.

- **AC-13 (Live, Staging):** Given ein per API angelegter Test-Ortsvergleich
  mit `alert_channels={email:false, telegram:true, sms:false,
  premium_sms:false}`, When über den Testeinspeisungs-Weg
  (`docs/specs/modules/alarm_testeinspeisung.md`) ein Abweichungsalarm
  ausgelöst wird, Then trifft die Meldung im Telegram-Live-Test
  (`GZ_ENV=staging`) ein und das IMAP-Postfach `gregor-test@henemm.com`
  bleibt für diesen Alarm leer.

- **AC-14 (Live, Staging):** Given derselbe Test-Ortsvergleich, When der
  Versand-Reiter-Premium-SMS-Schalter über die API gesetzt und danach erneut
  gelesen wird, Then ist `send_premium_sms` persistiert; When anschließend
  über die API der Alarme-Reiter-Premium-SMS-Kanal umgeschaltet wird, Then
  bleibt `send_premium_sms` beim erneuten Lesen unverändert.

- **AC-15 (Altbestand-Bereinigung, Nachtrag):** Given ein
  Ortsvergleich-Altbestand ohne `alert_channels` mit `send_premium_sms=true`,
  When die Briefing-Kanäle in Python aufgelöst werden (Zeitfenster vor jedem
  Go-Schreibzugriff auf dieses Preset) bzw. When das Preset über Go geladen
  und anschließend per PUT gespeichert wird, Then ist Premium-SMS in beiden
  Fällen **kein** Briefing-Kanal mehr (`send_premium_sms=false` nach dem
  Go-Speichern) — aber weiterhin ein Alarm-Kanal
  (`alert_channels.premium_sms=true`).

- **AC-16 (Gegenprobe, Nachtrag):** Given ein Ortsvergleich MIT gesetztem
  `alert_channels` und `send_premium_sms=true` (vom neuen Versand-Schalter
  gesetzt, Abschnitt 5), When Briefing-Kanäle aufgelöst bzw. das Preset
  geladen und gespeichert wird, Then bleibt Premium-SMS ein Briefing-Kanal —
  die Bereinigung greift ausschließlich bei fehlendem `alert_channels`.

- **AC-17 (Mandanten-Test, Nachtrag):** Given zwei Nutzer mit je einem
  Ortsvergleich-Altbestand ohne `alert_channels` und `send_premium_sms=true`,
  When beide Presets geladen und gespeichert werden, Then wird bei jedem
  Nutzer nur sein eigenes Preset bereinigt (`send_premium_sms=false`,
  `alert_channels.premium_sms=true`) — keine Vermischung zwischen den
  Nutzerverzeichnissen.

## Abweichungen vom Ticket

1. **Ticket-AC-3 (Migrationsskript `--execute`, Backup, Report, zweiter Lauf
   No-Op) entfällt ersatzlos.** Ersetzt durch deterministische Materialisierung
   in `store.NormalizeComparePreset` (Implementation Details Abschnitt 1) +
   Äquivalenztest AC-3. Grund: ein Skript hat ein Zeitfenster „Skript läuft vor
   Go-Deploy ⇒ jeder Go-Schreibweg löscht das per API gesetzte `alert_channels`
   still" (BUG-DATALOSS-GR221-Muster); die Materialisierung kommt mit dem
   Go-Feld im selben Binary und hat dieses Fenster nicht.

2. **Ticket-Titel „schließt #2212" gilt nicht.** #2212 betrifft den
   E-Mail-Schalter im **Versand**-Reiter (Briefing, `send_email` fehlt am
   Ortsvergleich vollständig — Go/Python/TS). Diese Scheibe löst ausschließlich
   die Alarm-Seite (E-Mail im Alarme-Reiter). PR-Text: „Refs #2212", kein
   „Closes #2212".

3. **Ein eigener Feld-Merge in Go entfällt** — seit #2285 ist
   `applyComparePresetPatch`/`mergeBriefingPatch` generisch preserve-by-default;
   das im Ticket geforderte manuelle Merge-Handling ist überflüssig. Tests auf
   **beiden** PUT-Wegen bleiben trotzdem Pflicht (AC-2, AC-4).

4. **#2448 wird in dieser Scheibe mit erledigt** (Premium-SMS-Schalter im
   Versand-Reiter, AC-8/AC-9/AC-14) statt als separates Ticket — PO-Regel:
   eine bekannte, nutzersichtbare Abweichung (heutige stille Kopplung
   Alarm-Premium-SMS-Klick ⇒ Briefing-Premium-SMS an) wird nicht befristet zur
   Freigabe vorgelegt, sondern im selben Ticket gefixt. PR-Text: „Refs #2448".

5. **Entscheidung 3 aus der Analyse („Premium-SMS-Kopplung bleibt als
   Übergang") ist verworfen**, nicht umgesetzt — aufgehoben durch Punkt 4.

6. **Nachtrag (PO-Briefing):** zusätzlich zur reinen Entkopplung (Punkt 4/5)
   wird der bestehende Altbestand bereinigt (AC-15/16/17, Implementation
   Details Abschnitt 7) — eine bekannte, nutzersichtbare Fehlauslösung
   (kostenpflichtige Premium-SMS-Briefings, die nie über einen
   Briefing-Schalter bestellt wurden) wird in derselben Scheibe behoben statt
   als offenes Risiko stehengelassen (PO-Regel).

## Mutations-Gegenprobe

- **(a)** Materialisierungs-Block in `NormalizeComparePreset` entfernen ⇒
  AC-3, AC-6, AC-7 werden rot (Legacy-GET und Neuanlage liefern kein
  `alert_channels`, Äquivalenztest hat nichts zu vergleichen bzw. scheitert am
  fehlenden Feld).
- **(b)** `omitKeys`/`delete`-Zeilen in `baueAlarmNutzlast` weglassen (keine
  Entfernung von `send_telegram`/`send_sms`/`send_premium_sms` aus dem Body)
  ⇒ AC-10 wird rot (ein veraltetes `original` im Alarm-Save überschreibt einen
  zwischenzeitlich geänderten Versand-Kanal).
- **(c)** Dieselbe Entfernung in `baueVersandNutzlast` für `alert_channels`
  weglassen ⇒ AC-10 wird in der Gegenrichtung rot.
- **(d)** In `_compare_channel_inputs`/`resolve_alert_channels` bei komplett
  leerem Override auf `{"email"}` zurückfallen (statt echte leere Menge) ⇒
  AC-12 wird rot (Alarm geht trotz „alle aus" per E-Mail raus).
- **(e)** Kurzstil-`disabled`-Bindung in `AlarmeTab.svelte` weiterhin an
  `sendTelegram` statt an `displayChannelState.telegram` lassen ⇒ AC-11 wird
  rot (Kurzstil-Schalter reagiert auf den Briefing- statt den Alarm-Zustand).
- **(f)** Alarme-Reiter setzt weiterhin zusätzlich `send_premium_sms` ⇒ AC-9
  wird rot (Briefing-Premium-SMS ändert sich durch einen reinen
  Alarm-Kanal-Klick).
- **(g)** Altbestand-Bereinigung entfernen (`materializeAlertChannels` wird nie
  mit `cleanupLegacyPremiumSms=true` aufgerufen, bzw. der `if cleanupLegacyPremiumSms
  && premiumSms`-Block entfällt) ⇒ AC-15 wird rot (ein Alt-Bestand mit
  `send_premium_sms=true` ohne `alert_channels` behält `send_premium_sms=true`
  nach Go-Load+PUT).
- **(h)** Python-Guard entfernen (`preset.get("alert_channels") is not None`
  aus `effective_compare_briefing_channels` streichen) ⇒ AC-15 wird im
  Python-Kern-Teil rot (Premium-SMS zählt trotz fehlendem `alert_channels`
  weiter als Briefing-Kanal, im Zeitfenster vor dem ersten Go-Schreibzugriff).

## Test-Plan

| AC | Datei | Schicht |
|---|---|---|
| AC-1, AC-2, AC-4 | `internal/handler/compare_preset_alert_channels_test.go` | Go |
| AC-5 | `internal/handler/compare_preset_alert_channels_test.go` (Vorbild Zeile 613 der Thresholds-Testdatei) | Go |
| AC-6, AC-7 | `internal/handler/compare_preset_alert_channels_test.go` | Go |
| AC-3, AC-12 | `tests/tdd/test_compare_alert_channel_equivalence.py` (neu) | Python Kern |
| AC-8, AC-14 (Persistenz-Teil) | `frontend/.../shared/__tests__/versand_vergleich_premium_sms.test.ts` (neu) | Frontend |
| AC-9 | `frontend/.../shared/__tests__/alarme_vergleich_premium_sms_entkoppelt.test.ts` (neu) | Frontend |
| AC-10 | `frontend/.../shared/__tests__/compare_alarm_versand_nutzlast_trennung.test.ts` (neu) | Frontend |
| AC-11 | `frontend/.../shared/__tests__/compare_alarme_kanal_hydration.test.ts` (neu); bestehende `telegram_kurzstil_shared_toggle.test.ts` anpassen | Frontend |
| AC-13, AC-14 (Live-Teil) | Live-E2E über Testeinspeisung + Staging-API, `GZ_ENV=staging` | Live |
| AC-15 (Go-Teil), AC-16, AC-17 | `internal/handler/compare_preset_alert_channels_test.go` (Vorbild Mandanten-Test Zeile 613 der Thresholds-Testdatei) | Go |
| AC-15 (Python-Teil) | `tests/tdd/test_compare_premium_sms_legacy_cleanup.py` (neu) | Python Kern |

Kern-Schicht (Go, Python) offline, keine Marker. Frontend-Tests laufen über
`node --test` (kein Vitest), lösen den Prüfling relativ zur eigenen
Testdatei auf. Live-ACs ausschließlich in `/e2e-verify`, nie im
Kern-Testlauf.

## Known Limitations

- **Payload-Trennung deckt nur die vier hier betroffenen Felder ab.** Das
  allgemeine Risiko eines veralteten `{...original}`-Spreads bei den übrigen
  ~30 Feldern des Ortsvergleichs (Same-Tab-Race, #2381-Muster) bleibt
  bestehen — gehört in einen allgemeineren Fix (Bezug #2375, Konflikt-Retry).
- **`send_email` existiert weiterhin nicht am Ortsvergleich** (Go/Python/TS).
  #2212 bleibt auf der Briefing-Seite offen; diese Scheibe ändert daran
  nichts.
- **Jede bestehende GET/PUT-Antwort für einen Ortsvergleich trägt ab dieser
  Scheibe ein zusätzliches `alert_channels`-Feld**, das vorher fehlte
  (`omitempty` griff bei `nil`). Bestehende Tests, die eine vollständige
  JSON-Gleichheit ohne dieses Feld prüfen, müssen angepasst werden.
- **Python liest `alert_channels` weiterhin nur über das Roh-Dict**
  (`_compare_channel_inputs`), das neue Dataclass-Feld ist reine
  Modellparität ohne eigenen Konsumenten (analog `alert_metric_channels` seit
  S1) — keine Verhaltensänderung im Python-Kern durch diese Scheibe.
- **Bewusste Verhaltensänderung (Nachtrag, AC-15):** bei betroffenen
  Bestandsnutzern (denen der Alarme-Reiter vor dieser Scheibe still
  `send_premium_sms=true` gesetzt hat) schaltet die Bereinigung das
  Premium-SMS-Briefing ab, das sie nie über einen Briefing-Schalter bestellt
  hatten. Das ist **gewollt** — PO-Regel: ein bekannter, nutzersichtbarer
  Fehler (hier: ungewollter kostenpflichtiger Versand) wird in derselben
  Scheibe behoben und nie als offenes Risiko stehengelassen. Die
  Alarm-Zustellung (`alert_channels.premium_sms`) bleibt von der Bereinigung
  unberührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0021 (geteilte Alert-Engine), ADR-0023
  (`kind`-Diskriminierung) und ADR-0049 (Premium-SMS als vierter Kanal)
  gelten unverändert weiter.
- **Rationale:** ADR-0049 äußert sich nicht zum Ortsvergleich (sie beschreibt
  ausdrücklich nur die S2a-Lieferung fürs Trip-Briefing und benennt
  `AlertChannelsConfig`/Go als *künftige* Lieferposition von S2b, also genau
  diese Scheibe). Der Kommentar „im vergleich-Zweig ist Premium-SMS kein Kanal
  (ADR-0049)" in `VersandTab.svelte`/`versandVergleichSpeicherung.ts` war ein
  irreführender Code-Kommentar, kein ADR-Beschluss — seine Korrektur ist keine
  ADR-Abweichung. Diese Scheibe führt keine neue Entscheidungsfläche ein: sie
  hebt eine bereits im Trip produktiv gehärtete Struktur (`alert_channels`
  als Go-Feld, geteilte Auflösung) auf den zweiten `kind`-Wert, exakt im Sinne
  von ADR-0021.

## Changelog

- 2026-09-28: Initial spec created (Scheibe S2 zu #2279, Epic #1374/#2345;
  #2448 als Teilumfang aufgenommen, Ticket-AC-3/Migrationsskript verworfen).
- 2026-09-28: Nachtrag (PO-Briefing) — Altbestand-Bereinigung für ungewollte
  Premium-SMS-Briefings ergänzt: Go-Regelort `materializeAlertChannels`
  (Lade-Pfad setzt `send_premium_sms=false` bei fehlendem `alert_channels`),
  Python-Guard in `effective_compare_briefing_channels`, AC-15/16/17,
  Mutations-Gegenproben (g)/(h), Neuanlage sendet `alert_channels` immer mit.
