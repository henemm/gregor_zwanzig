---
entity_id: issue_1216_slice2_compare_official_alert
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [official-alerts, compare, alert-trigger, email, telegram, sms, convergence]
---

# Ortsvergleich-Standalone-Alarm für amtliche Warnungen (#1216 Slice 2a, Backend)

## Approval

- [x] Approved (PO „go", 2026-07-11; inkl. LoC-Override 500)

## Purpose

Der Ortsvergleich löst bei neuen/eskalierten amtlichen Warnungen einen **eigenständigen Alarm** aus — analog zum Trip-Standalone-Alarm (Slice 1), mit **denselben** Präsentations-Renderern, aber **Orts-Scope** statt Segment-Scope. Versand gebündelt je Preset über E-Mail/Telegram/SMS (Kanal-Auflösung wie beim Trip). Diese Slice liefert die Backend-Logik; die UI (Editor-Schalter) folgt in Slice 2b.

## Source

- **File:** `src/services/compare_official_alert.py` (CREATE — `CompareOfficialAlertService`)
- **File:** `src/services/notification_service.py` (MODIFY — `send_multi_location_official_alert`)
- **File:** `src/output/renderers/alert/official_alerts.py` (MODIFY — `build_compare_official_alert_notices` mit Orts-Scope)
- **File:** `api/routers/scheduler.py` (MODIFY — Endpoint `/api/scheduler/compare-official-alert-checks`, prefixierter Router)
- **Identifier:** `CompareOfficialAlertService.check_all_compare_presets`, `send_multi_location_official_alert`, `build_compare_official_alert_notices`

Schicht: **Python-Core / Domain-Backend** (`src/services/`, `src/output/`, `api/`).

## Estimated Scope

- **LoC:** ~250–300 (neuer Service + Notification-Methode + Notice-Builder + Endpoint) → **LoC-Override wahrscheinlich nötig, PO fragen**
- **Files:** 3 MODIFY + 1 CREATE + Tests
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareAlertService` (compare_alert.py) | reuse-pattern | Preset-Loop, ThrottleStore, Tageslimit, `_load_presets`, `_notification_service_for` |
| `TripAlertService.check_official_alert_triggers` | reuse-pattern | Detect-Logik (fetch, dedup, neu/eskaliert) |
| `render_official_alert_subject/html/telegram/sms` (Slice 1) | reuse | Präsentation, kontext-agnostisch |
| `dedupe_official_alerts`, `get_official_alerts_for_location` | reuse | Bündelung + Fetch je Ort |
| `AlertStateService`, `alert_daily_limit` | reuse | State (`{preset_id}:{location_id}`) + Tageslimit (kein Zeit-Cooldown, s. Impl.) |
| `Settings.can_send_telegram/can_send_sms`, `sms_allowed` | reuse | Kanal-Auflösung wie Trip |

## Implementation Details

### CompareOfficialAlertService (Vorbild `CompareAlertService`)
`check_all_compare_presets() -> int`: lädt Presets; je Preset: Toggle-Gate `preset.get("official_alert_triggers_enabled", True)` überspringt bei falsy; **Tageslimit** (`alert_daily_limit.is_allowed`); Detect je Ort; bei ≥1 Treffer **EIN** gebündelter Versand; danach State + Limit fortschreiben. Gibt Anzahl versendeter (gebündelter) Alarme zurück.

**Kein Zeit-Cooldown-Gate** (Adversary F002, bewusst): der `alert_state`-Vergleich (Key `official_alert:{region}:{hazard}`, Trigger nur neu/eskaliert) IST das persistente Anti-Spam-Gedächtnis — anders als der Δ-Wetter-Pfad ohne Level-Gedächtnis. Ein Zeit-Cooldown würde eine echte **Eskalation** (GELB→ORANGE) bis `cooldown_minutes` unterdrücken → widerspräche dem Sicherheits-Zweck. Spam-Obergrenze allein über `alert_daily_limit`. **Kein `ThrottleStore` für diesen Pfad** (kein toter write-only-record).

**Detect (analog Trip):** je Preset-Ort `get_official_alerts_for_location(loc.lat, loc.lon)` → getaggt mit Ortsname; `dedupe_official_alerts` über alle Orte; State `AlertStateService(user_id).load(f"{preset_id}:{location_id}")`, Trigger nur wenn Key `official_alert:{region_label}:{hazard}` neu ODER `level` gestiegen. State-Schreibung erst NACH erfolgreichem Versand.

### Orts-Scope-Notices — `build_compare_official_alert_notices(preset_location_names, tagged_alerts)`
Analog `build_official_alert_notices`, aber Scope = **Ortsnamen**:
- `scope_label` = „alle Orte" wenn betroffene Orte == alle Preset-Orte; sonst Aufzählung („nur Ort B", „Ort A, Ort C").
- `sms_scope` = kompakt (z.B. „alleOrte" / „nur B").
- `affected_chips` = betroffene Ortsnamen; `free_chips` = übrige Preset-Orte (durchgestrichen).
Nutzt die Slice-1-`OfficialAlertNotice`-Struktur unverändert.

### send_multi_location_official_alert (Vorbild `send_multi_location_deviation_alert`)
Signatur: `(preset_name, locations, tagged_alerts, effective_channels, *, mail_sink=None, sms_sink=None, telegram_sink=None)` — `locations` trägt **Name UND Koordinaten** (lat/lon), damit `alert_tz = tz_for_coords(locations[0].lat, locations[0].lon)` berechnet werden kann (Adversary F001: KEIN hartes `ZoneInfo("UTC")` — sonst falsche lokale Zeiten in HTML/Telegram/SMS). Rendert Betreff/HTML/Telegram/SMS über die Slice-1-Renderer (Präfix = `preset_name`, `tz=alert_tz` an alle drei); E-Mail-Body = HTML; SMS via `sms_sink`/`SMSOutput`, Telegram via `telegram_sink`/`TelegramOutput`.

### Kanal-Auflösung (wie Trip)
`_effective_channels(preset)`: E-Mail immer (wenn `empfaenger`/`mail_to`); `telegram` wenn `preset.get("send_telegram", False)` UND `can_send_telegram()`; `sms` wenn `preset.get("send_sms", False)` UND `can_send_sms()` UND `sms_allowed(user_id)`. Default (ohne Schalter) = nur E-Mail.

### Scheduler-Endpoint
`POST /api/scheduler/compare-official-alert-checks` → `CompareOfficialAlertService(user_id).check_all_compare_presets()` (am `/api/scheduler`-prefixierten Router, konsistent mit den Geschwister-Endpoints; Adversary F004).

## Expected Behavior

- **Input:** Compare-Presets des Nutzers (dict) + live amtliche Warnungen je Ort.
- **Output:** je Preset mit Treffer EIN gebündelter Alarm (Betreff/HTML/Telegram/SMS im Vorlagen-Format, Orts-Scope) an die Preset-Kanäle.
- **Side effects:** `alert_state` (`{preset_id}:{location_id}`) + `alert_daily_limit` fortgeschrieben (kein ThrottleStore).

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit zwei Orten und einer neuen amtlichen GELB-Warnung an einem Ort (via echte Fake-Quelle registriert), Toggle aktiv / When `CompareOfficialAlertService(user_id).check_all_compare_presets()` läuft / Then wird genau EIN gebündelter Alarm versendet und der `alert_state` unter `{preset_id}:{location_id}` mit Key `official_alert:{region}:{hazard}` fortgeschrieben.
  - Test: echter Service-Lauf mit registrierter Fake-OfficialAlertSource + mail_sink; Assert 1 Versand + State-Datei-Eintrag; kein Mock.

- **AC-2:** Given zwei Orte A und B eines Presets, dieselbe Warnung (gleiche region_label+hazard) an BEIDEN / When der Alarm gerendert wird / Then erscheint die Warnung **einmal** (dedupliziert) mit `scope_label` „alle Orte"; deckt sie nur Ort B ab, lautet der Betreff-Scope „nur <OrtB>" und Ort A steht als freier (durchgestrichener) Chip im HTML.
  - Test: `build_compare_official_alert_notices` + `render_official_alert_subject/html`; Assert Dedup (1×), „alle Orte" bzw. „nur <OrtB>" + line-through für freien Ort.

- **AC-3:** Given ein Preset mit `send_telegram=True` und `send_sms=True` und global konfiguriertem Telegram+SMS / When ein Alarm feuert / Then wird über E-Mail (HTML), Telegram (fette erste Zeile) UND SMS (GSM-7 ≤140) versendet — je genau EINMAL gebündelt.
  - Test: `send_multi_location_official_alert` mit mail_sink + sms_sink + Telegram-Spy/Seam; Assert alle drei Kanäle je 1× aufgerufen, SMS ASCII ≤140.

- **AC-4:** Given eine bereits gemeldete GELB-Warnung (State gesetzt) / When der Check erneut läuft mit unveränderter Stufe / Then feuert KEIN erneuter Alarm; steigt die Stufe auf ORANGE, feuert er wieder.
  - Test: 3-Runden-Service-Lauf (neu → dedup → Eskalation), Assert 1/0/1 Versände.

- **AC-5:** Given ein Preset OHNE `send_telegram`/`send_sms` (Default) / When ein Alarm feuert / Then wird NUR per E-Mail versendet (kein Telegram/SMS), auch wenn global konfiguriert.
  - Test: `_effective_channels` + Dispatch; Assert nur E-Mail-Kanal.

- **AC-6:** Given ein Preset mit `official_alert_triggers_enabled=False` / When der Check läuft / Then wird die amtliche-Warnung-Quelle über den Trigger-Pfad NICHT abgefragt (Fetch-Counter 0) und kein Alarm versendet.
  - Test: registrierte Fake-Quelle mit Call-Counter; Assert `fetch_calls == 0`.

- **AC-7:** Given zwei verschiedene Nutzer mit je eigenem Preset und Warnung / When beide Checks laufen / Then bleibt jeder Alarm im `user_id`-Scope (State/Versand pro Nutzer isoliert), niemals `"default"`.
  - Test: zwei `user_id`, Assert getrennte State-Pfade + kein Cross-User-Versand.

- **AC-8:** Given der Scheduler-Endpoint `POST /api/scheduler/compare-official-alert-checks?user_id=<u>` (gleicher Prefix wie die Geschwister-Endpoints) / When er aufgerufen wird / Then delegiert er an `CompareOfficialAlertService(u).check_all_compare_presets()` und liefert die Anzahl versendeter Alarme.
  - Test: FastAPI-Route-Test (TestClient) mit präpariertem Preset; Assert Delegation + Response.

## Known Limitations

- **Nur Backend (Slice 2a).** UI-Schalter (Trigger + Kanäle) im Compare-Editor + Go-Scheduler-Eintrag folgen in Slice 2b. Bis dahin sind `send_telegram/send_sms` per Default aus → faktisch E-Mail-only, Telegram/SMS-Capability aber vorhanden + getestet.
- Kanal-Auflösung nutzt globale User-Telegram/SMS-Config (wie Trip), keine pro-Preset-Empfänger für Telegram/SMS.
- Deviation-/Radar-Compare-Alarme bleiben E-Mail-only (außerhalb Scope; Konvergenz-Folge).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (gemeinsamer Official-Alert-Renderer) + ADR-0021 (geteilter Dispatch) — beide bestehend, additiv erweitert. Keine neue ADR: Slice 2 folgt der Konvergenz-Richtung (Epic #1204) durch geteilte Renderer + Struktur-Analogie zu `CompareAlertService`.
- **Rationale:** Compare = „abgewandelter Trip" mit denselben Funktionen (PO-Vorgabe), Orts-Scope statt Segment-Scope.

## Changelog

- 2026-07-11: Initial spec (Slice 2a) erstellt
- 2026-07-11: Adversary-Korrekturen F001 (alert_tz via Koordinaten), F002 (kein Zeit-Cooldown, State-Dedup), F004 (Endpoint unter /api/scheduler)
