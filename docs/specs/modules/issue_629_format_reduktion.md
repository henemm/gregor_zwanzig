---
entity_id: issue_629_format_reduktion
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [format-mode, weather-metrics, ui, migration, issue-629, issue-620]
---

# Format-Modell auf Roh/Einfach reduzieren (#629)

## Approval

- [ ] Approved

## Purpose

Umsetzung der PO-Entscheidung #620: App-weit bietet die Oberfläche bei Wetter-Kennzahlen
nur noch **Roh** und **Einfach** an. Die mit #435 ausgelieferten benannten Modi **Skala**
(`scale`) und **Symbol** (`symbol`) verschwinden aus der UI. Das Backend-Feld bleibt
4-wertig, die tatsächliche Briefing-Darstellung bleibt unverändert. Bestandsdaten werden
datensicher angeglichen.

## Source

- **File:** `frontend/src/lib/components/WeatherConfigDialog.svelte` (Standorte-Seite, live auf /locations)
- **File:** `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` (Trip-anlegen-Assistent)
- **File:** `src/app/loader.py` (Migrations-Normalisierung beim Laden)
- **Identifier:** Roh/Einfach-Toggle analog `ActiveMetricRow.svelte` + `metricsEditor.ts::indicatorCapable`

## Estimated Scope

- **LoC:** ~120–160
- **Files:** 3 Code + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/.../trip-detail/metricsEditor.ts` | Frontend | `indicatorCapable()` / `INDICATOR_MAP` — Single Source, welche Metriken den Toggle bekommen |
| `frontend/.../trip-detail/ActiveMetricRow.svelte` | Frontend | Referenz-Implementierung des Roh/Einfach-Toggles (v2, #587) |
| `src/app/loader.py::_resolve_format_mode` | Python-Backend | Fallback None → `default_format_mode`; bleibt erhalten |
| `src/app/metric_catalog.py` | Python-Backend | `format_modes`/`default_format_mode` bleiben **unverändert** (4-wertig) |

## Implementation Details

### Frontend (UI schrumpft)
- `WeatherConfigDialog.svelte` und `Step3Weather.svelte`: Das 4-fach-Dropdown
  (`FORMAT_MODE_LABELS` raw/scale/simplified/symbol, iteriert über `m.format_modes`)
  wird ersetzt durch denselben **Boolean-Toggle Roh/Einfach** wie in `ActiveMetricRow.svelte`.
- Gate: Toggle erscheint nur für `indicatorCapable(id)` (gemeinsamer Helper aus `metricsEditor.ts`);
  alle übrigen Metriken zeigen „nur Rohwert".
- Persistenz: „Einfach" → `use_friendly_format = true`, „Roh" → `use_friendly_format = false`.
  **Kein** explizites `format_mode = scale|symbol` mehr schreiben. Speichern als
  Read-Modify-Write (bestehende Felder erhalten).
- Die Strings „Skala", „Vereinfacht", „Symbol" als wählbare Optionen entfallen.

### Backend (unverändert lassen)
- `metric_catalog.py` `format_modes`/`default_format_mode` **nicht** anfassen → kein Bruch von
  `thunder` (nur Symbol-Renderer) und kein Default-Wechsel bei Wolken/CAPE/Sonne.
- Renderer (`helpers.py::fmt_val`) unverändert → „Einfach" rendert weiter pro Metrik den
  passenden Default (Symbol / Kompass / Kurztext).

### Migration (datensicher, Schema-Rework-Regel)
- Beim Laden in `loader.py`: persistiertes `format_mode in {"scale","symbol"}` wird zu
  `format_mode = None` normalisiert und `use_friendly_format = true` gesetzt. Damit rendert
  die Metrik bit-identisch wie zuvor (Default dieser Metriken IST scale/symbol).
- `format_mode in {"raw","simplified"}` und `None` bleiben unangetastet.
- Pre-Snapshot via Hook `data_schema_backup.py` (loader.py ist schema-relevant).
- Realität: 0 Bestandsdateien haben heute `format_mode` gesetzt → Migration praktisch No-op,
  Roundtrip-Test dient als Garantie.

## Expected Behavior

- **Input:** Nutzer wählt pro Kennzahl Roh oder Einfach; Bestands-Configs ggf. mit altem `format_mode`.
- **Output:** UI ohne Skala/Vereinfacht/Symbol; Briefing-Darstellung unverändert; persistierte
  Configs ohne explizites scale/symbol.
- **Side effects:** Keine Renderer-/Katalog-Änderung; keine Datenfeld-Verluste.

## Acceptance Criteria

- **AC-1:** Given der Wetter-Konfigurations-Dialog einer Location ist auf /locations geöffnet /
  When eine Kennzahl mit Einfach-Darstellung angezeigt wird (z.B. Bewölkung) / Then erscheinen
  genau zwei wählbare Darstellungs-Optionen „Roh" und „Einfach", und „Skala", „Vereinfacht"
  sowie „Symbol" tauchen nirgends als wählbare Option auf.
  - Test: Playwright gegen Staging als eingeloggter Nutzer — Dialog öffnen, Toggle-Optionen auslesen.

- **AC-2:** Given der Trip-anlegen-Assistent ist im Wetter-Schritt / When die Kennzahl-Liste
  angezeigt wird / Then bietet die Darstellungs-Auswahl ausschließlich Roh/Einfach (Boolean-Toggle),
  keine Skala/Vereinfacht/Symbol-Optionen.
  - Test: Playwright gegen Staging — Wizard-Schritt 3 öffnen, Optionen auslesen.

- **AC-3:** Given eine Kennzahl steht auf „Einfach" (z.B. Bewölkung=Symbol, Windrichtung=Kompass,
  Wind=Kurztext) / When das Briefing gerendert wird / Then ist der angezeigte Zellwert identisch
  zur heutigen Ausgabe — keine Darstellungs-Regression.
  - Test: Echter Render der format_email-Pipeline; Vergleich der erzeugten Zellwerte vor/nach Änderung (Golden).

- **AC-4:** Given eine persistierte Wetter-Config enthält `format_mode = "scale"` bzw. `"symbol"` /
  When sie geladen wird / Then ist `format_mode` auf None normalisiert (kein explizites scale/symbol),
  `use_friendly_format = true`, der effektiv gerenderte Modus bleibt unverändert, und alle übrigen
  Felder (enabled, aggregations, alert_*, order, bucket, morning/evening_enabled) sind erhalten.
  - Test: Echte JSON-Config schreiben → via loader laden → Felder + effektiven Modus assertieren.

- **AC-5:** Given eine Config mit vollständig befüllten MetricConfig-Feldern inkl. `format_mode`
  scale/symbol / When sie geladen → normalisiert → gespeichert → erneut geladen wird / Then
  unterscheidet sich das Ergebnis vom Input nur in der `format_mode`-Normalisierung — kein Feld
  geht verloren oder ändert sich sonst.
  - Test: Roundtrip load→save→load, vollständiger Feld-Diff (Schema-Rework-Regel).

- **AC-6:** Given der Nutzer ändert im Locations-Dialog bzw. Wizard nur den Roh/Einfach-Toggle /
  When gespeichert wird / Then bleiben alle nicht betroffenen persistierten Felder der
  Location/des Trips unverändert (Read-Modify-Write, kein Überschreiben mit UI-State).
  - Test: Playwright gegen Staging — vorher/nachher-Vergleich der gespeicherten Config über die API.

## Out of Scope

- Backend-Renderer angleichen (Emoji ↔ Kurzwort) — bleibt wie heute (PO-Entscheidung 2026-06-06).
- Katalog-`format_modes`/`default_format_mode` schrumpfen — bewusst nicht (bricht thunder, ändert Defaults).
- v2-Tabellen-Vorschau-Fidelity (#587/#632).
