# Context: feat-1260-telegram-kurzstil

## Request Summary

Nutzer (PO) möchte in der Kanal-Konfiguration einen opt-in Schalter, der Telegram
mit **exakt dem kurzen SMS-Stil** beliefert statt mit der reichen Multi-Bubble-Darstellung.
Gilt für: Trip-Briefings (Morgen/Abend), Trip-Alarme und **amtliche Ortsvergleich-Warnungen**.
Reguläre Ortsvergleich-Briefings/-Alarme sind bewusst **nicht** im Scope (dort existiert
heute gar kein Telegram/SMS-Versand — PO-Entscheidung „Trips + Vergleich-Warnungen").

Issue: https://github.com/henemm/gregor_zwanzig/issues/1260 (Label priority:critical, type:feature)

## Kern-Erkenntnis (Scope-Treiber)

Telegram bekommt in **allen** Pfaden einen **eigenen** Renderer — nie den SMS- oder E-Mail-Renderer.
Der kurze SMS-Text wird bei Trip-Briefings ohnehin schon miterzeugt (`TripReport.sms_text`),
muss also nur zu Telegram „umgeleitet" werden. Für Alarme existiert `render_sms` ebenfalls.
Es gibt **keine** deklarative channel→renderer-Tabelle; die Wahl ist imperativ im
`NotificationService`.

Historie: Es existiert ein **totes** Konfig-Feld `UnifiedWeatherDisplayConfig.telegram_kurzform`
(`src/app/models.py:580`, Issue #614), das Issue #1001 (Multi-Bubble-Redesign) **bewusst
stillgelegt** hat (`trip_report.py:235-239`, AC-10). Dieses Feature schaltet das Konzept
opt-in wieder scharf — reiche Darstellung bleibt Default.

## Related Files

### Rendering (SMS-Kurzstil = Ziel-Format)
| File | Relevance |
|------|-----------|
| `src/output/renderers/sms_trip.py:176` | `SMSTripFormatter.format_sms()` — Trip-Briefing-SMS (≤160) |
| `src/output/renderers/sms/__init__.py:11` | `render_sms()` TokenLine→wire (sms_format.md v2.0) |
| `src/output/renderers/alert/render.py:507` | `render_sms(msg, limit=140)` — Trip-Alarm-SMS |
| `src/output/renderers/alert/official_alerts.py:1509` | `render_official_alert_sms(limit=140)` — amtl. Compare-SMS |

### Rendering (Telegram heute = zu ersetzen bei aktivem Schalter)
| File | Relevance |
|------|-----------|
| `src/output/renderers/narrow.py:359` | `render_telegram_bubbles()` — reiche Trip-Briefing-Bubbles (#1001) |
| `src/output/renderers/alert/render.py:472` | `render_telegram()` — Trip-Alarm-Telegram (HTML) |
| `src/output/renderers/alert/official_alerts.py:1333` | `render_official_alert_telegram()` — amtl. Compare-Telegram |
| `src/output/renderers/trip_report.py:189-233` | erzeugt BEIDE (`telegram_bubbles` + `sms_text`) im `TripReport` |

### Dispatch (wo Renderer↔Kanal entschieden wird — hier greift der Schalter)
| File | Relevance |
|------|-----------|
| `src/services/notification_service.py:211` | `send_trip_report()` — Briefing-Dispatch |
| `src/services/notification_service.py:267-287` | Telegram-Bubble-Versand (parse_mode=HTML, suppress_subject) |
| `src/services/notification_service.py:256-264` | SMS-Versand (`report.sms_text or report.email_plain`) |
| `src/services/notification_service.py:723` | `_dispatch_alert_message()` — Trip/Compare-Dev-Alert-Dispatch (Email 774 / Telegram 790 / SMS 803) |
| `src/services/notification_service.py:648/668` | `_dispatch_compare_official_{telegram,sms}` — amtl. Compare |
| `src/output/channels/telegram.py` | `TelegramOutput.send()` — reiner Transport (HTML-Truncate, 400-Fallback) |
| `src/output/channels/sms.py` | `SMSOutput.send()` — reiner Transport (seven.io) |
| `src/output/channels/base.py:69` | `get_channel(name, settings)` — Transport-Factory |

### Konfiguration (wo der neue Schalter lebt)
| File | Relevance |
|------|-----------|
| `src/app/models.py:580` | `UnifiedWeatherDisplayConfig.telegram_kurzform` (totes Feld, #614/#1001) |
| `src/app/models.py:726-728` | `TripReportConfig.send_email/send_sms/send_telegram` |
| `src/app/models.py:756` | `TripReportConfig.email_format` ("full"/"compact") — **Vorbild** für einen Kanal-Stil-Schalter (#722) |
| `src/app/models.py:820` | `AlertRule.channels` (per-Regel-Override, #638) |
| `src/app/models.py:895-896` | `ComparePreset.send_telegram/send_sms` |
| `src/app/loader.py:246-247,522-523,573-574,634-635` | Persistenz-Merge (RMW!) |
| `internal/model/trip.go:142,152-154,177` | Go: `AlertChannels`, `AlertChannelsConfig`, flache Sends |
| `internal/model/compare_preset.go:48,86-87` | Go: `DisplayConfig`, `SendTelegram/SendSms` |

### Frontend (Bedien-Schalter — geteilte Komponenten, Invariante!)
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/VersandTab.svelte` | Trip-Versand-Tab (send_telegram/send_sms State) |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte:87-140` | Kanal-Checkboxen E-Mail/Telegram/SMS |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Alarm-Kanäle (Trip + Compare via context) |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte:31-44` | Telegram/SMS/E-Mail Alarm-Toggles |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte:454-473` | `email_format` full/compact Radio — **Vorbild** für Stil-Schalter |
| `frontend/src/lib/types.ts:225-226` | TS-Typ `email_format` — Muster für neues Feld |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Compare-Kanäle |

## Existing Patterns

- **Pro-Kanal-Stil-Schalter existiert bereits** für E-Mail: `email_format: "full"|"compact"`
  (`models.py:756`, FE `EditReportConfigSection`, Dispatch-Verzweigung `notification_service.py:974-992`).
  → Blaupause für einen `telegram_style`/`telegram_kurzform`-Schalter.
- **DTO trägt bereits beide Formate** (`sms_text` + `telegram_bubbles` im `TripReport`) — Dispatch
  wählt nur aus. Umleiten heißt: an der Dispatch-Verzweigung `sms_text` statt Bubbles an Telegram geben.
- **Kanal-Ableitung Alerts:** `trip_alert.py:988` `_effective_alert_channels()`; amtl. Compare
  `compare_official_alert.py:183` `_effective_channels()`.
- **Trip/Compare-Teilung (PO-Invariante):** Bedien-Schalter MUSS geteilte Komponente sein
  (`shared/`), kein Compare-Nachbau.

## Dependencies

- **Upstream:** `TripReport`-Erzeugung (`trip_report.py`), Alert-Renderer (`alert/render.py`,
  `official_alerts.py`), Config-Modelle (`models.py`, Go-Structs), Loader-Merge (`loader.py`).
- **Downstream:** `NotificationService`-Dispatch, `TelegramOutput`/`SMSOutput`-Transport,
  Frontend-Konfig-Tabs, Vorschau-Karten (`ChannelFidelity*`).

## Existing Specs

- `docs/specs/modules/feat_1001_telegram_redesign.md` — Multi-Bubble-Telegram (das hier opt-in teilrücknehmen)
- `docs/specs/modules/output_channel_renderers.md` — Renderer-Signaturen (`render_sms` §A3)
- `sms_format.md` v2.0 — SMS-Wire-Format
- E-Mail `email_format` full/compact (#722) als struktureller Präzedenzfall

## Risks & Considerations

1. **Multi-User-Isolation (PFLICHT):** neuer datenbewegender Konfig-Pfad — mit **zwei** Nutzern
   testen; nie `user_id="default"`-Fallback.
2. **Datenverlust-Regel (RMW):** neues Konfig-Feld → Loader-Merge, nie Replace; Roundtrip-Test.
   Go+Python müssen dasselbe Feld verstehen.
3. **`telegram_kurzform` reaktivieren vs. neues Feld:** Altes Feld sitzt auf
   `UnifiedWeatherDisplayConfig` (per Trip), nicht auf `TripReportConfig`. In Analyse klären,
   ob reaktivieren oder sauber neu (Analogie zu `email_format` auf `TripReportConfig`).
4. **Telegram hat kein 160-Zeichen-Limit:** SMS-Format behalten, harte Kürzung ggf. weglassen
   (PO offen gelassen — in Analyse festlegen). Alert-SMS ist 140-capped.
5. **renderer_mail_gate (#811):** deckt `src/output/renderers/alert/*.py`. Wenn wir die
   Alert-Renderer NICHT editieren, sondern nur die vorhandene `render_sms`-Ausgabe im Dispatch
   umleiten, wird das Gate nicht getriggert. Bevorzugter Weg.
6. **Compare-Scope strikt:** NUR amtliche Warnungen (haben Telegram/SMS). Reguläre
   Compare-Briefings bleiben E-Mail-only — nicht anfassen.
7. **Trip/Compare-Sharing-Invariante:** ein geteilter Schalter, kein Compare-Duplikat.
8. **Inline-Keyboard/Aktionen** der reichen Bubbles entfallen im Kurzstil — bewusst
   (Kurzstil = eine kurze Zeile, keine Navigation).

## Analysis

### Type
Feature (opt-in, additiv).

### Technischer Ansatz — Dispatch-Redirect statt Renderer-Edit (bestätigt)
Der Schalter greift am **Dispatch**, nie am Renderer. Alle betroffenen Pfade haben den
SMS-Text bereits fertig oder ohne Renderer-Edit anforderbar:
- **Trip-Briefing** (`notification_service.py:267-287`): `report.sms_text` liegt schon im DTO
  → bei Schalter an `bubbles = [report.sms_text]`, `parse_mode=None`.
- **Trip-Abweichungs-Alarm** (`_dispatch_alert_message` :743-744): `sms_body`+`telegram_body`
  werden schon beide berechnet → Zeilentausch im Telegram-Zweig.
- **Trip-AMTLICHE Warnung** (`send_official_alert` :475-560): `render_official_alert_sms`
  bereits importiert (:490), muss im Telegram-Zweig zusätzlich aufgerufen werden.
  **Fund: vierter Dispatch-Pfad, in der PO-Liste nicht separat benannt** — teilt die
  Kanal-Auflösung `_effective_alert_channels()` mit den Trip-Abweichungs-Alarmen.
- **Amtl. Compare-Warnung** (`_dispatch_compare_official_telegram` :648-666): analog.

→ Nur `notification_service.py`, `trip_alert.py`, `compare_official_alert.py`, `models.py`,
`loader.py` werden angefasst. `renderer_mail_gate` (#811) deckt u.a. `trip_report.py`,
`sms_trip.py`, `alert/*.py` — die fassen wir NICHT an → **Gate triggert nicht**.

### Konfig-Feld-Entscheidung (Empfehlung, adoptiert)
**Neues Feld, KEIN Reaktivieren von `telegram_kurzform`** (falscher Ort = Anzeige-Config;
semantisch mit #614/#1001 belastet; Reaktivierung würde Alt-Werte still wiederbeleben).
- Trip: `TripReportConfig.telegram_style: str = "rich"` (`"rich"|"kurzform"`), exakt das
  `email_format`-Muster. Liegt opak im `report_config`-Blob → **keine Go-Struct-Änderung**,
  generischer `mergeConfigMap()` deckt RMW automatisch (verifiziert `config_merge.go`).
- Compare: Key in `ComparePreset.display_config["telegram_style"]` — wird bereits feldweise
  gemerged (#1159-Fix, `compare_preset.go`), ebenfalls **keine Go-Änderung**. Präzedenzfall:
  `metric_alert_levels` liegt genauso als DisplayConfig-Sub-Key.

### 160/140-Kappung (Empfehlung, adoptiert)
**1:1 beibehalten** — „exakt der SMS-Stil". Bereits gerenderten String weiterverwenden.
**Pflicht-Detail:** Redirect zwingend mit `parse_mode=None` (SMS-Text ist nicht HTML-escaped;
mit `parse_mode="HTML"` würde ein zufälliges `&`/`<` die Bot-API mit „can't parse entities"
abweisen). Gehört als AC in die Spec.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `src/app/models.py` | MODIFY | `TripReportConfig.telegram_style` |
| `src/app/loader.py` | MODIFY | load+save Merge des neuen Feldes |
| `src/services/notification_service.py` | MODIFY | Redirect in 4 Dispatch-Stellen |
| `src/services/trip_alert.py` | MODIFY | Style aus `report_config` auflösen + durchreichen |
| `src/services/compare_official_alert.py` | MODIFY | `_effective_telegram_style(preset)` |
| `frontend/.../shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | Kurzstil-Schalter Telegram-Zeile |
| `frontend/.../shared/AlarmeTab.svelte` | MODIFY | Kurzstil im Alarm-Kontext (geteilt) |
| `frontend/src/lib/types.ts` | MODIFY | Typ `telegram_style` |
| `tests/tdd/*` | CREATE | RMW-Roundtrip + Redirect je Pfad, Multi-User |

### Scope Assessment
- Backend ~65–90 LoC, Frontend ~60–100 LoC, inkl. Tests grob 300–450 LoC.
- Risk Level: MEDIUM (kritischer Versandpfad, aber additiv/opt-in; kein Renderer-/Gate-Edit).

### Slice-Reihenfolge
S1 Config-Feld+Persistenz Trip → S2 Trip-Briefing-Redirect → S3 Trip-Alarme-Redirect
(Abweichung+amtlich) → S4 Compare-amtlich-Redirect → S5 Frontend-Schalter (gebündelt).
Jede Backend-Scheibe eigenständig per API/Config test- und auslieferbar.

### Risiken
- **Inline-Keyboard/Aktionen** (z.B. PAUSE/SKIP) entfallen im Kurzstil — inhärent zu „SMS-Stil",
  als Known Limitation in Spec.
- Geteilter `_dispatch_alert_message()` bedient auch (nicht-Scope) reguläre Compare-Alarme →
  Style-Parameter mit sicherem Default `"rich"` explizit durchreichen, keine implizite Kopplung.
- Multi-User + RMW: Roundtrip-Test (PUT-Teilbody → GET → Feld erhalten) je Feld, zwei Nutzer.

### Open Questions (an PO) — GEKLÄRT
- [x] Fällt die **amtliche Wetterwarnung eines Trips** (vierter Pfad) unter „Trip-Alarme"?
  → **PO 2026-07-15: JA, beide.** Abweichungs-Alarme UND amtliche Trip-Warnungen bekommen
  den Kurzstil (Konsistenz).

### Finaler Scope (PO-bestätigt)
Kurzstil-Schalter opt-in für: (1) Trip-Briefing Morgen/Abend, (2) Trip-Abweichungs-Alarme,
(3) Trip-amtliche Warnungen, (4) amtliche Ortsvergleich-Warnungen. NICHT: reguläre
Ortsvergleich-Briefings/-Alarme (heute E-Mail-only, nicht anfassen).
