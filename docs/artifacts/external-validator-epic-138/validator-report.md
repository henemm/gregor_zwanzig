# External Validator Report

**Spec:** docs/specs/modules/epic_138_metriken_editor.md
**Datum:** 2026-05-18T00:00:00Z
**Server:** https://staging.gregor20.henemm.com
**Trip-ID (verwendet):** `validator-test-with-dc`

## Zusammenfassung

Die in Epic #138 spezifizierten Aenderungen sind auf Staging **nicht ausgeliefert**. Der Wetter-Metriken-Tab zeigt unveraendert den Platzhaltertext „Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)" — der spezifizierte Inline-Editor ist nicht vorhanden. Das in §1 geforderte API-Feld `has_friendly_format` fehlt vollstaendig in der Antwort von `GET /api/metrics`. Zusaetzlich gibt die API nur 25 Metriken zurueck, waehrend Spec und AC-2 von 26 ausgehen.

## Beweise

- `01_trip_detail.png` — Trip-Detail-Seite (Übersicht-Tab)
- `02_metriken_tab.png` — Wetter-Metriken-Tab nach Klick: nur Platzhaltertext sichtbar
- `body_text.txt` — Volltext des Tab-Inhalts: „Wetter-Metriken / Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)"

## Checklist

| #  | Expected Behavior | Beweis | Verdict |
|----|-------------------|--------|---------|
| AC-1  | Metriken-Tab zeigt `data-testid="weather-metrics-tab"`, kein Platzhaltertext | `02_metriken_tab.png`: Platzhaltertext sichtbar; Playwright: Selektor `[data-testid="weather-metrics-tab"]` nicht gefunden | **FAIL** |
| AC-2  | 26 Metrik-Checkboxen mit `data-testid="weather-metrics-tab-checkbox-{id}"` in 5 Kategorien | Playwright: 0 Checkboxen; zusaetzlich: `/api/metrics` liefert nur **25** Metriken (4+3+6+9+3) | **FAIL** |
| AC-3  | Template-Dropdown mit 7 Presets + „Eigene Auswahl" | Playwright: `[data-testid="weather-metrics-tab-template"]` nicht im DOM. `/api/templates` liefert 7 Templates — UI-Seite jedoch nicht vorhanden | **FAIL** |
| AC-4  | Template-Auswahl aktiviert Checkboxen, `use_friendly_format` bleibt unveraendert | Nicht pruefbar — kein Editor im DOM | **FAIL** |
| AC-5  | Format-Buttons (raw/indicator) genau bei 9 eligible Metriken | Playwright: 0 Buttons. `/api/metrics` enthaelt zudem **kein** `has_friendly_format`-Feld (Felder pro Metrik: `id, label, unit, category, default_enabled`) | **FAIL** |
| AC-6  | Save-PUT enthaelt alle 26 Metrik-Objekte mit `enabled` + `use_friendly_format` | Speichern-Button nicht im DOM; nicht ausloesbar | **FAIL** |
| AC-7  | Roh-Toggle persistiert ueber Reload | Toggle nicht vorhanden | **FAIL** |
| AC-8  | `WeatherConfigDialog` Save-Payload enthaelt `use_friendly_format` pro Metrik | Keine Locations im Test-Account vorhanden (`/api/locations` liefert `[]`) — UI-Trigger nicht reproduzierbar | **UNKLAR** |
| AC-9  | `EditWeatherSection` emittiert `use_friendly_format` im `displayConfig` | Komponente ist Wizard-intern, nicht ohne Wizard-Trigger pruefbar | **UNKLAR** |
| AC-10 | `weather-metrics-tab-success` / `-error` erscheint nach Save | Save-Button und Tab-Editor nicht vorhanden | **FAIL** |

## Findings

### Finding 1 — Wetter-Metriken-Tab zeigt Platzhalter, Inline-Editor fehlt
- **Severity:** CRITICAL
- **Expected (Spec §6, AC-1):** Tab rendert `WeatherMetricsTab` mit `data-testid="weather-metrics-tab"`, Placeholder-Eintrag aus `TripTabs.svelte` entfernt
- **Actual:** Tab zeigt Text „Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)" — Platzhalter ist noch aktiv
- **Evidence:** `02_metriken_tab.png`, `body_text.txt`

### Finding 2 — `has_friendly_format`-Feld fehlt in `/api/metrics`
- **Severity:** CRITICAL
- **Expected (Spec §1):** Jedes Metrik-Objekt traegt `has_friendly_format: bool`; 9 eligible Metriken (`wind_direction, thunder, cape, cloud_total, cloud_low, cloud_mid, cloud_high, visibility, sunshine`) bekommen `true`
- **Actual:** Felder pro Metrik sind ausschliesslich `id, label, unit, category, default_enabled`. Kein einziger Eintrag enthaelt `has_friendly_format`
- **Evidence:** `curl -H "Cookie: gz_session=..." https://staging.gregor20.henemm.com/api/metrics` (alle 25 Eintraege gepruerft)

### Finding 3 — `/api/metrics` liefert 25 statt 26 Metriken
- **Severity:** HIGH
- **Expected (Spec §5 und AC-2):** 26 Metriken
- **Actual:** 25 (temperature: 4, wind: 3, precipitation: 6, atmosphere: 9, winter: 3)
- **Evidence:** Auszaehlung der `/api/metrics`-Antwort. Die Spec listet 26 Checkbox-IDs an — eine fehlt
- **Hinweis:** Selbst wenn das Frontend ausgeliefert waere, koennte AC-2 nicht erfuellt sein, weil der API-Katalog nur 25 Metriken anbietet

### Finding 4 — Bug-Fixes in `WeatherConfigDialog` und `EditWeatherSection` nicht verifizierbar
- **Severity:** MEDIUM
- **Expected (AC-8 / AC-9):** Save-Payloads dieser Komponenten enthalten `use_friendly_format` pro Metrik
- **Actual:** Test-Account hat keine Locations (`/api/locations` = `[]`), und der Wizard ist nicht ohne manuelle Eingaben begehbar. Ein direkter API-Roundtrip auf `PUT /api/trips/.../weather-config` mit `use_friendly_format` wird vom Go-Handler korrekt persistiert — der Bug liegt aber laut Spec **im Frontend**, nicht im Handler, und der Frontend-Pfad ist nicht testbar
- **Evidence:** `curl /api/locations` → `[]`; `PUT /api/trips/validator-test-with-dc/weather-config` mit `use_friendly_format:false` → GET liefert denselben Wert zurueck (Handler ist also nicht der Verursacher)

## Verdict: BROKEN

### Begruendung

Mindestens 8 der 10 Acceptance Criteria scheitern direkt am DOM/API-State auf Staging:

1. Der Inline-Editor existiert nicht — der Tab haengt am Platzhalter (AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-10).
2. Das in §1 geforderte API-Feld `has_friendly_format` ist nicht in der `/api/metrics`-Antwort enthalten (AC-5 zusaetzlich strukturell unmoeglich erfuellbar).
3. Der API-Katalog liefert nur 25 statt 26 Metriken — AC-2 ist auch unabhaengig vom Frontend nicht erfuellbar, solange die Backend-Quelle nicht 26 Eintraege liefert.

AC-8 und AC-9 sind UNKLAR (kein UI-Trigger im Test-Account verfuegbar), aendern am Gesamturteil aber nichts — die zentralen Spec-Punkte (§1 API-Feld, §5 neue Komponente, §6 Tab-Integration) sind nachweislich nicht in Produktion.
