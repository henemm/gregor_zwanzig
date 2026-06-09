---
entity_id: issue_638_alerts_redesign
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [alerts, frontend, backend, schema, channels, severity]
---

# Alerts-Tab: Karten-Modell + Severity-Falle beseitigen + Kanal pro Alert

## Approval

- [x] Approved (PO 'go', 2026-06-08)

## Purpose

Der Alerts-Tab im Trip-Bearbeiten wird vom Tabellen-Paradigma auf das JSX-Karten-Modell (`TE2_AlertsTab`) umgebaut, die gefährliche Severity-Auswahl entfernt (heute werden „Info"-Alerts still verschluckt), und jeder Alert erhält eigene Kanäle (vorbelegt aus den Briefing-Kanälen, pro Alert überschreibbar) mit echtem kanalbewusstem Versand.

## Source

- **Frontend / User-UI:** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`, neue `AlertCard.svelte`, `frontend/src/lib/types.ts`
- **Go-API:** `internal/model/trip.go` (`AlertRule`-Struct)
- **Python-Backend:** `src/app/models.py` (`AlertRule`), `src/app/loader.py` (parse/serialize/migrate), `src/services/trip_alert.py` (Filter + Routing), `src/services/weather_change_detection.py` (Severity-Ableitung)

## Estimated Scope

- **LoC:** ~400–500 (Full-Stack: UI-Redesign + Go-/Python-Schema + Versand-Routing + Migration) → LoC-Override begründet
- **Files:** ~8–10
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `report_config` (send_email/send_telegram/send_sms) | upstream | Vorbelegung der Alert-Kanäle |
| `WeatherChangeDetectionService` | upstream | Severity-Ableitung + Change-Detektion |
| `EmailOutput` / `TelegramOutput` | downstream | Kanal-Versand |
| Trip-Persistenz (`loader.py`, Go `internal/store`) | downstream | Schema-Serialisierung |

## Implementation Details

### Schema-Erweiterung `AlertRule.channels`
- **Go** (`internal/model/trip.go`): `Channels []string `json:"channels,omitempty"``
- **Python** (`src/app/models.py`): `channels: list[str] = field(default_factory=list)`
- **TS** (`frontend/src/lib/types.ts`): `channels?: string[]`
- `severity` bleibt im Schema erhalten (Bestandsdaten + Cockpit-Token), wird aber **nicht mehr** zur Versand-Entscheidung genutzt und in der UI **nicht mehr** editiert.
- **Migration (kein Datenverlust, BUG-DATALOSS-GR221):** Bestands-Alerts ohne `channels` → leere Liste bedeutet „erbe Briefing-Kanäle". `_alert_rule_from_dict` nutzt `d.get("channels", [])`. `severity` weiter geparst (`d.get("severity", "warning")`).

### Severity-Falle beseitigen
- `trip_alert.py:_filter_significant_changes`: gibt **nicht mehr** nur MODERATE/MAJOR durch — jeder von einer aktiven, konfigurierten Regel ausgelöste Change wird durchgereicht. Der MINOR=stumm-Effekt entfällt.
- `weather_change_detection.py`: `rule.severity`-Override (`severity_overrides`, #222) entfernt → echte Ableitung über `_classify_severity(delta, threshold)`. Severity nur noch als Label am Change.

### Kanal pro Alert (Routing)
- `WeatherChange` trägt die auslösende `rule_id` (und/oder die effektiven `channels`), damit Changes nach Kanal gruppierbar sind.
- Effektive Kanäle eines Alerts: `rule.channels` falls gesetzt, sonst die aktiven Briefing-Kanäle aus `report_config`.
- `trip_alert.py:_send_alert`: gruppiert getriggerte Changes nach effektiven Kanälen und versendet pro Kanalgruppe (E-Mail / Telegram). Ein Alert-Kanal darf an sein, auch wenn der Briefing-Kanal aus ist.

### Frontend Karten-Modell (JSX `TE2_AlertsTab`)
- Container `AlertsTab.svelte` rendert eine `AlertCard` pro Alert statt `AlertMetricTable`.
- Karte: Label · `Metrik · Bedingung` (mono) · Switch (An/Aus) · Trennlinie · Kanal-Chips (toggle pro aktivem Briefing-Kanal).
- Infozeile: „Alert-Kanäle starten mit den aktiven Kanälen aus Wetter-Metriken als Vorbelegung — pro Alert überschreibbar."
- „+ Neuen Alert hinzufügen"-Button.
- Keine Severity-Auswahl mehr.

## Expected Behavior

- **Input:** Trip mit `alert_rules`, `report_config` (Briefing-Kanäle); Nutzer toggelt Alert an/aus und Kanal-Chips.
- **Output:** Persistierte `alert_rules` mit `channels`; bei Wetteränderung Versand an genau die pro-Alert konfigurierten Kanäle.
- **Side effects:** Persistenz (Trip JSON), E-Mail/Telegram-Versand.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktivem Alert auf eine Metrik, dessen Schwelle in den Wetterdaten überschritten wird, unabhängig von der abgeleiteten Dringlichkeit / When der Alert-Lauf (`TripAlertService`) ausgeführt wird / Then wird der Alert tatsächlich versendet (kein stilles Verschlucken früherer „Info"/MINOR-Alerts mehr).
  - Test: Python-Verhaltenstest — Trip mit Alert (frühere severity=info), Snapshot mit Schwellenüberschreitung, `check_trip()` ausführen, beweisen dass ein Alert-Versand ausgelöst wird (nicht durch den MODERATE-Filter unterdrückt).

- **AC-2:** Given ein Alert mit eigenem Kanal-Override `channels=["telegram"]`, während der Briefing-Kanal E-Mail aktiv und Telegram als Briefing-Kanal aus ist / When dieser Alert ausgelöst wird / Then erfolgt der Versand über Telegram (nicht E-Mail) — der pro-Alert-Kanal gewinnt über den Briefing-Kanal.
  - Test: Python-Verhaltenstest mit echtem lokalem SMTP-/HTTP-Sink (kein Mock); prüfen, welcher Kanal-Output aufgerufen wurde.

- **AC-3:** Given ein Alert ohne gesetzte `channels` (leere Liste) / When er ausgelöst wird / Then erbt er die aktiven Briefing-Kanäle aus `report_config` (Vorbelegung) und versendet darüber.
  - Test: Python-Verhaltenstest — Trip mit `report_config.send_email=True`, Alert ohne `channels`, beweisen dass über E-Mail versendet wird.

- **AC-4:** Given ein persistierter Trip mit Bestands-`alert_rules` **ohne** `channels`-Feld und **mit** altem `severity`-Feld / When der Trip geladen (`load_trip`) und wieder gespeichert (`save_trip`) wird / Then bleiben alle Regeln erhalten (Roundtrip ohne Datenverlust), `channels` defaultet auf leere Liste, `severity` bleibt lesbar.
  - Test: Python-Roundtrip-Test — fixtures JSON ohne `channels` laden, save, neu laden, assert Regel-Anzahl + Felder unverändert.

- **AC-5:** Given zwei verschiedene Nutzer (mandantengetrennt) mit je eigenem Trip und unterschiedlichen Alert-Kanälen / When beide Alert-Läufe ausgeführt werden / Then erhält jeder Nutzer nur die Alerts seines eigenen Trips über seine eigenen Kanäle — keine Cross-User-Vermischung.
  - Test: Python-Verhaltenstest mit zwei `user_id`-getrennten Datenverzeichnissen.

- **AC-6:** Given der Alerts-Tab im Trip-Bearbeiten auf Desktop / When er geladen wird / Then erscheint pro Alert eine Karte mit Label, `Metrik · Bedingung` (mono), An/Aus-Switch und Kanal-Chips, die Infozeile zur Kanal-Vererbung sowie „+ Neuen Alert hinzufügen" — und **keine** Severity-Auswahl mehr.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer — Karten-Struktur sichtbar, Severity-Control nicht mehr vorhanden.

- **AC-7:** Given ein Alert auf der Karte / When der Nutzer einen Kanal-Chip toggelt und speichert / Then wird `alert_rules[].channels` persistiert und nach Reload korrekt wiedergegeben.
  - Test: Playwright-E2E gegen Staging — Chip toggeln, speichern, Reload, Chip-Zustand persistiert (DB-Roundtrip).

- **AC-8:** Given das gerenderte SOLL aus `TE2_AlertsTab` (JSX) / When der Live-Alerts-Tab dagegen pixel-verglichen wird / Then liegt die Abweichung unter dem vereinbarten Fidelity-Schwellwert (Layout 1:1, Daten-Divergenz erlaubt).
  - Test: Pixel-Fidelity-Gate gegen aus JSX gerendertes Referenzbild.

## Out of Scope

- Briefing-Zeitplan-Kanal-Verkettung → bleibt in #617
- Wetter-Metriken-Tab-Layout → #587
- SMS-Versandpfad als realer Kanal (nur Vorbelegung/Persistenz; SMS-Output-Anbindung separat falls nötig)

## Changelog

- 2026-06-08: Initial spec — Issue #638 (Alerts-Tab Karten-Modell, Severity-Falle beseitigen, Kanal pro Alert). PO 'go' 2026-06-08.
