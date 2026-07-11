# Context: feat-1216-slice2-compare-official-alert (#1216 Slice 2)

## Request Summary
Der Ortsvergleich soll bei amtlichen Warnungen einen **eigenständigen Alarm** auslösen — analog zum Trip-Standalone-Alarm (Slice 1) und mit **denselben** Präsentations-Renderern (kontext-agnostisch aus Slice 1). Heute hat Compare gar keinen eigenständigen amtlichen Alarm.

## Ausgangslage (Slice 1 live)
Die vier kontext-agnostischen Renderer existieren bereits: `render_official_alert_subject/html/telegram/sms` + `OfficialAlertNotice`-DTO (`scope_label`, `sms_scope`, `affected_chips`, `free_chips`) + `build_official_alert_notices(trip, tagged)`. Trip-Dispatch: `NotificationService.send_official_alert(trip, notices, ...)`.

## Related Files (Vorbilder + Ziele)
| Datei | Rolle |
|------|------|
| `src/services/compare_alert.py` | **Struktur-Vorbild** (`CompareAlertService.check_all_compare_presets`): Preset-Loop, ThrottleStore(`compare_preset`), Tageslimit, Detect-pro-Ort, gebündelter Versand, State `{preset_id}:{location_id}`, Empfänger `_notification_service_for`, `_load_presets` |
| `src/services/trip_alert.py:920` `check_official_alert_triggers` | **Detect-Vorbild**: `get_official_alerts_for_location(lat,lon)`, `dedupe_official_alerts`, Trigger nur neu/eskaliert, State-Key `official_alert:{region}:{hazard}` |
| `src/services/notification_service.py:446` `send_official_alert` | **Dispatch-Vorbild** — aber `trip`-gebunden → neuer `send_multi_location_official_alert` nötig |
| `src/output/renderers/alert/official_alerts.py` | Slice-1-Renderer + `build_official_alert_notices` (heute trip-spezifisch → Compare-Variante mit Orts-Scope) |
| `api/routers/scheduler.py:60` `/compare-alert-checks` | Endpoint-Vorbild → neuer `/compare-official-alert-checks` |
| `src/services/comparison_engine.py:188` | `official_alerts_enabled`-Fetch (#1040) — nur Rendering; Compare-Alert fetcht selbst |
| `src/services/alert_state.py` | generisch, `entity_id`-basiert — **direkt wiederverwendbar** |

## Wiederverwendbar (nichts neu erfinden)
`AlertStateService`, `alert_daily_limit`, `ThrottleStore`, `get_official_alerts_for_location`, `dedupe_official_alerts`, `_notification_service_for`, `_load_presets`, **die vier Slice-1-Renderer**.

## Neu zu bauen
1. `CompareOfficialAlertService` (`src/services/compare_official_alert.py`) — Detect + State + gebündelter Dispatch je Preset.
2. `NotificationService.send_multi_location_official_alert(...)` — Preset-Kontext statt Trip; nutzt die Slice-1-Renderer mit **Orts-Scope**.
3. Compare-Variante der Notice-Erzeugung: `scope_label`/`chips` mit **Ortsnamen** statt Segmenten (`alle Orte` / `nur Ort B`; sms_scope analog).
4. Neues Preset-Feld `official_alert_triggers_enabled` (Toggle) + Default-Gate.
5. Scheduler-Endpoint `/compare-official-alert-checks` + Go-Scheduler-Eintrag.
6. Frontend-Toggle im Compare-Editor (Alerts-Bereich, analog Radar-Toggle #1041 Slice 2).

## KERN-SCOPE-BEFUND (PO-Entscheidung)
**Compare ist strukturell E-Mail-only.** `compare_alert.py:206` und `compare_radar_alert.py:115` hardcoden `channels={"email"}`; Compare-Presets haben **kein** Telegram/SMS-Feld (nur `empfaenger` = E-Mail). Der Trip-Standalone-Alarm geht über die Trip-Kanäle (E-Mail/Telegram/SMS); Compare kann das heute für KEINEN Alarmtyp.
→ „Compare official-alert über Telegram/SMS" wäre KEIN reines Slice-2, sondern ein **breiterer Umbau** (Kanal-Config + UI für ALLE Compare-Alarme). Nur den amtlichen Alarm auf Telegram/SMS zu heben (Deviation/Radar aber nicht) wäre inkonsistent.

## Aufgelöste Scope-Richtung (PO 2026-07-11)
- **Kanäle: E-Mail + Telegram + SMS** (PO-Entscheidung, volle Trip-Parität). Compare nutzt DIESELBE Kanal-Auflösung wie Trip: E-Mail an `empfaenger`; Telegram/SMS über **globale User-Config** (`can_send_telegram/sms` + `sms_allowed`) gated durch **pro-Preset-Schalter** `send_telegram`/`send_sms` (neue Preset-Felder, analog `report_config.send_telegram/send_sms`). Default aus → bis UI (2b) faktisch E-Mail-only, aber Capability testbar.
- **Slicing: Backend zuerst, dann UI** (PO).

## Delivery-Slicing
- **2a (Backend, DIESER Workflow):** `CompareOfficialAlertService` (Detect+State+gebündelter Dispatch je Preset) + `NotificationService.send_multi_location_official_alert` (E-Mail/Telegram/SMS über die drei Slice-1-Renderer) + Compare-Kanal-Resolver (Preset-Schalter + globale Config) + Orts-Scope-Notices (`alle Orte`/`nur Ort B`) + Preset-Toggle `official_alert_triggers_enabled` + Scheduler-Endpoint `/compare-official-alert-checks`. E2E via Service testbar (synthetisches Preset mit Schaltern an → alle 3 Kanäle dispatchen).
- **2b (Folge-Workflow):** Compare-Editor-UI (Trigger-Toggle + Kanal-Schalter) + Go-Scheduler-Eintrag.

**LoC-Hinweis:** 2a wird voraussichtlich > 250 LoC (neuer Service + Notification-Methode + Resolver + Notice-Builder) → LoC-Override bei Approval erfragen.

## Risks & Considerations
- Renderer-Mailgate (alert/*.py) — Commit-Gate wie Slice 1 (Radar-Validator No-Op-Falle).
- Konvergenz-Richtung #1204: Bausteine teilen, nie „analog Trip" nachbauen — hier erfüllt durch geteilte Renderer + Struktur-Kopie mit Orts-Scope.
- Dedup-Konsistenz mit `dedupe_official_alerts` (kein Regress #1172/#1200/#1217).
- Multi-User: `user_id` durchreichen, nie `"default"`.
