# Context: rework-2279-alert-kanal-aufloesung

Erhoben am 2026-09-09 für Issue #2279 (Dach-Epic #1374). Zeilenangaben gegen
`origin/main` @ `0520389` (Branch `claude/trips-ortsvergleiche-analyse-a61it9`, PR #2289).

## Request Summary

Trip und Ortsvergleich lösen ihre **Alarm-Kanäle** heute in zwei Funktionen mit
verschiedener Semantik auf. Ziel ist **eine** Auflösung `effective_alert_channels(subscription,
settings, user_id)` über dem `kind`-diskriminierten Modell (ADR-0023), ein Feld `alert_channels`
für beide kinds, die Regel „E-Mail nur an, wenn eingeschaltet" (schließt #2212 auf der
Alarmseite) und Tier-Gates genau einmal.

## Kernbefund: Nicht zwei Funktionen, sondern zwei Datenmodelle

| | Trip (`kind=route`) | Ortsvergleich (`kind=vergleich`) |
|---|---|---|
| Briefing-Kanäle | `report_config.send_email/telegram/sms/premium_sms` (`trip_report_scheduler.py:1726-1765`) | flache `send_telegram/send_sms/send_premium_sms` — **kein `send_email`** (`compare_preset.go:91-97`, KL-6 in `versand_tab_vergleich.md`) |
| Alarm-Kanäle | `trip.alert_channels` (Sub-Objekt, 4 `*bool`, `trip.go:151,204-209`); `None` ⇒ Erbe aus Briefing-Kanälen; nicht-leere `rule.channels` gewinnen (#638) | **dieselben** flachen `send_*` — bewusste Entscheidung #1270 (`compare_channel_preview_dispatch.md`): Alarm- und Briefing-Kanal sind beim Vergleich EIN Setting |
| Auflösung | `TripAlertService._effective_alert_channels` (`trip_alert.py:2871-2926`): Override → Erbe → Regel-Union → Tier-Gates SMS/Premium-SMS. **Keine** Settings-Readiness | `effective_compare_channels` (`compare_alert_channels.py:28-47`): E-Mail hart an, Telegram/SMS nur bei Opt-in **UND** `settings.can_send_*()`, SMS/Premium zusätzlich Tier-Gate |
| Aufrufer | `trip_alert.py:398,550,1070,1669,2504,2721` | Alarm: `compare_alert.py:111,603`, `compare_official_alert.py:471`, `compare_radar_alert.py:169`. **Briefing:** `scheduler_dispatch_service.py:351-363,588` |
| Frontend | `AlarmeTab.svelte` route-Zweig → `alert_channels` (alle 4 Pflicht, `alarmeDeliveryPayload.ts:106-117`); Lesen `tripChannelReconstruction.ts:18-43` | `AlarmeTab.svelte:229-250` vergleich-Zweig schreibt `wiz.sendTelegram/sendSms/sendPremiumSms` — **dieselben Runes wie `VersandTab.svelte:287-302`**; E-Mail hardcoded `true`, kein Toggle (`:218-221`) |
| Go-RMW | `handler/trip.go:401-415` Feld-Level-Merge `AlertChannels` | `handler/compare_preset.go:411-421` nil-Erbe `Send*`; `:429-444` Feld-Level-Merge `AlertChannelThresholds` (Vorlage) |
| Schwellen | `alert_channel_thresholds` (`trip.go:218`) | identischer Typ, Top-Level (`compare_preset.go:105`) — **bereits symmetrisch** |

**Sendezeit-Guards existieren in der geteilten Zustellung** (`notification_service.py::_dispatch_alert_message`):
E-Mail nur bei `can_send_email()`, Telegram nur bei `can_send_telegram()`, SMS nur bei
`can_send_sms()`; Premium-SMS entscheidet der Kanal selbst (#1701 D3). Die Readiness-Prüfung in
der Compare-Auflösung ist damit doppelt und der einzige Grund, warum die beiden Funktionen bei
identischer Konfiguration verschiedene Mengen liefern können.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:2871-2945` | Trip-Auflösung + `_briefing_channels` — Algorithmus wird der geteilte Kern |
| `src/services/compare_alert_channels.py` | Compare-Auflösung; nach Umbau nur noch **Briefing**-Resolver des Vergleichs |
| `src/services/compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py` | drei Compare-Alarmpfade → geteilte Funktion |
| `src/services/scheduler_dispatch_service.py:351-363,588` | Compare-**Briefing**-Versand — darf NICHT auf Alarm-Kanäle umgestellt werden |
| `src/services/compare_preset_access.py`, `src/app/loader.py:240-353` | Presets erreichen die Services als Roh-Dict (`preset.raw`) — neues Feld kommt ohne Umbau an |
| `src/app/models.py:1278-1345` | Python `ComparePreset` (Feldliste 1:1 zu Go) — `alert_channels` ergänzen |
| `internal/model/compare_preset.go:91-105` | Go-Struct: `AlertChannels *AlertChannelsConfig` fehlt — **ohne Feld verliert der Go-Roundtrip den Key** (kein Raw-Bucket in Go) |
| `internal/handler/compare_preset.go:280,411-444` | PUT-Merge: nil-Erbe + Feld-Level-Merge nach Vorlage Thresholds |
| `internal/handler/briefing_subscription.go:168-191` | `mergeBriefingPatch` (generischer Map-Merge, trägt Nested-Objekt voraussichtlich automatisch — zu BELEGEN) |
| `internal/handler/compare_preset_alert_channel_thresholds_test.go` | Testvorlage Go (zwei Ebenen, zwei Schreibwege) |
| `tests/tdd/test_compare_alert_channels.py` | AC-3a/3b patchen `effective_compare_channels` im Verbraucher-Modul → müssen auf die neue Verdrahtung |
| `tests/tdd/test_trip_alert_channel_precedence.py`, `test_issue_684_alert_email_guard.py`, `test_914_slice4_alert_sms_dispatch.py`, `test_issue_1069_tier_channel_gating.py` | pinnen Trip-Semantik — müssen unverändert grün bleiben |
| `scripts/migrate_1258_official_warnings.py` | Migrationsvorbild (Dry-Run, Backup, RMW) — s. Risiko 1 |

## Existing Patterns

- **Override-oder-Erbe** (Trip #1258 S3): `alert_channels=None` ⇒ Legacy-Verhalten, gesetzt ⇒ ersetzt nur den geerbten Briefing-Anteil. Dieses Muster deckt den Compare-Bestand OHNE Datenumbau: `None` ⇒ Erbe aus flachen `send_*` + E-Mail an = heutiges Verhalten.
- **Pointer-Feld + Feld-Level-Merge** in Go (`AlertChannelsConfig`, Thresholds) — Typ existiert, wird für Compare wiederverwendet (kein neuer Typ).
- **Dünner Wrapper im Verbraucher-Modul** für Verdrahtungsnachweise per `monkeypatch` (AG1 #1467).
- **Geteilte Zustellung** `_dispatch_alert_message` + `split_by_threshold` (#1533) — Readiness gehört dort hin, nicht in die Auflösung.

## Dependencies

- Upstream: `services.user_tier.sms_allowed/premium_sms_allowed`, `app.trip.Trip`, Preset-Roh-Dict, `app.config.Settings`
- Downstream: sechs Trip-Aufrufer, drei Compare-Alarmservices, `alert_log` (`effective_channels` im Unterdrückungs-Protokoll), `split_by_threshold`

## Existing Specs

- `docs/specs/modules/compare_channel_preview_dispatch.md` (#1270) — Alarm = Briefing-Kanäle beim Vergleich
- `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md` — Thresholds symmetrisch
- `docs/specs/modules/versand_tab_vergleich.md` KL-6 — kein `send_email`
- `docs/specs/modules/trip_alert.md`, ADR-0021 (geteilte Alert-Engine), ADR-0023 (`kind`), ADR-0049 (Premium-SMS)

## Risks & Considerations

1. **Migration der flachen Felder nach `alert_channels` friert die Alarm-Kanäle ein.** Solange der Compare-Alarme-Tab `wiz.sendTelegram/…` (= flache Felder) schreibt, würde ein migriertes, gesetztes `alert_channels` jede spätere Toggle-Änderung des Nutzers für Alarme wirkungslos machen (Override gewinnt). Die Migration (Issue-AC-3) gehört deshalb in die Scheibe, in der der Compare-Alarme-Tab auf das Trip-Muster (`alarmeDeliveryPayload`) wechselt — nicht in diese.
2. **Readiness-Prüfung aus der Auflösung nehmen** ändert beim Vergleich das Unterdrückungs-Protokoll (`effective_channels` listet dann Telegram auch ohne Bot-Token) — Trip-Verhalten seit je; Versand bleibt durch Sendezeit-Guards identisch.
3. **Briefing-Pfad des Vergleichs** darf nicht versehentlich Alarm-Kanäle lesen (sonst folgt das Briefing einem künftigen `alert_channels`).
4. **Go-Roundtrip:** ohne Struct-Feld verliert jeder Go-Save ein per `/api/briefings` gesetztes `alert_channels` (BUG-DATALOSS-GR221-Muster).
5. Schwellen/`AlertRules` für den Vergleich (Befund-Absatz im Issue) sind **nicht** Teil des Zielbilds — außerhalb dieser Scheibe.

## Analysis

### Type
Rework (Feature-Pfad), Tech-Lead-Entscheidung 2026-09-09 nach Plan-Gegenprobe (Sonnet).

### Scheibenschnitt (Entscheidung)

Die Plan-Gegenprobe beziffert das Gesamtzielbild auf ~550-1150 LoC (allein die Go-RMW-Testvorlage
`compare_preset_alert_channel_thresholds_test.go` hat 976 Zeilen). Daher **zwei Scheiben** nach dem
Hausmuster (#1467 S1-S4b, #1258 S1-S3):

- **S1 = dieses Ticket (#2279):** EINE Auflösung in Python, drei Compare-Alarmpfade umgehängt,
  E-Mail-Regel, Tier-Gates einmal, Readiness raus aus der Auflösung, Briefing-Resolver des
  Vergleichs sauber getrennt und umbenannt. Lesepfad für `alert_channels` beim Vergleich
  (Roh-Dict) inklusive — Bestand ohne Feld verhält sich identisch (Erbe).
- **S2 = Folge-Issue:** Go-Feld `ComparePreset.AlertChannels` + Feld-Level-Merge auf beiden
  PUT-Wegen + Go-Tests, Compare-Alarme-Tab auf das Trip-Muster (`alarmeDeliveryPayload`,
  E-Mail-Toggle → schließt #2212 in der UI), Migration flach → `alert_channels` (Dry-Run, Report,
  Backup, Snapshot-Vergleich). Bis S2 ist ein `alert_channels` auf dem Vergleich nur per
  Datei/Test erreichbar; der Go-Roundtrip würde einen per API gesetzten Key verwerfen —
  **deshalb schreibt S1 das Feld nirgends** (kein Datenverlust-Risiko, kein Split-Brain).

### Affected Files (S1)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_channels.py` | CREATE | `effective_alert_channels(subscription, settings, user_id)` = dünner Dispatcher → `_trip_channel_inputs(trip)` / `_compare_channel_inputs(preset)` → reiner Kern `resolve_alert_channels(override, inherited, rule_channel_sets, user_id)` (Muster `app/day_window.py:26`: primitive Eingaben, Adapter am Rand) |
| `src/services/trip_alert.py:2871-2926` | MODIFY | `_effective_alert_channels` wird dünner Delegat (6 Aufrufer + Tests unverändert) |
| `src/services/compare_alert.py:111,603`, `compare_official_alert.py:465-471`, `compare_radar_alert.py:169` | MODIFY | Aufruf der geteilten Funktion |
| `src/services/compare_alert_channels.py` | MODIFY | `effective_compare_channels` → `effective_compare_briefing_channels` (Readiness bleibt, nur Briefing); alter Name verschwindet |
| `src/services/scheduler_dispatch_service.py:29,351-363` | MODIFY | Umbenennung nachziehen (Briefing-Pfad bleibt auf Briefing-Resolver) |
| `tests/tdd/test_compare_alert_channels.py:175-233` | MODIFY | Verdrahtungsnachweise AC-3a/3b auf die neuen Symbole |
| `tests/tdd/test_alert_channel_resolution_parity.py` | CREATE | Paritätstabelle 16 Kombinationen × beide kinds, Bestand-Identität, E-Mail-aus, Settings-Inertheit, Tier-Gates einmal |
| `tests/tdd/test_compare_alert_email_off.py` | CREATE | Ende-zu-Ende: Vergleich mit `alert_channels.email=false` → Abweichungs-/Radar-/amtlicher Alarm ohne Mail (Sinks) |

### Scope Assessment
- Files: 8 (2 neu) · Estimated LoC: src ≈ +150/−45, tests ≈ +280 · Risk: MEDIUM (Verhaltensneutralität Bestand; Readiness-Verschiebung nur ins Protokoll sichtbar)
- LoC-Override 500 wird voraussichtlich gebraucht (Tests).

### Technical Approach
- **Kern-Algorithmus = Trip-Algorithmus** (Override → Erbe → Regel-Union → Tier-Gates). Vergleich liefert `override = preset.get("alert_channels")`, `inherited = {"email"} ∪ {telegram|sms|premium_sms bei truthy send_*}`, keine Regel-Overrides.
- **`settings` bleibt in der Signatur, ist aber inert** (Issue-Signatur, Aufrufer haben es ohnehin); ein Tripwire-Test belegt: Ergebnis unabhängig vom `Settings`-Objekt. Readiness prüft ausschließlich die Zustellung (`notification_service.py:1663-1774`, `:1214-1232`, `:1320-1345`) — Plan-Gegenprobe: kein Test pinnt eine Readiness-Filterung im Alarmpfad; `test_compare_dispatch_channel_fanout.py:253` betrifft den Briefing-Pfad, der auf dem Briefing-Resolver bleibt.
- Sichtbare Nebenwirkung: `effective_channels` im Unterdrückungs-Protokoll (`alert_log`) listet beim Vergleich jetzt auch nicht-sendebereite Opt-in-Kanäle — wie beim Trip seit je; `channels_not_sent`/`not_delivered` speisen sich aus `result.sent_channels` und bleiben korrekt.

### Dependencies
`services.user_tier` (Tier-Gates), `app.trip.Trip`/`AlertRule`, Preset-Roh-Dict via `compare_preset_access`, `notification_service` (Sendezeit-Guards, unverändert).

### Open Questions
- keine — Scheibenschnitt und Migrations-Aufschub sind Tech-Lead-Entscheidung; PO bestätigt über die ACs.
