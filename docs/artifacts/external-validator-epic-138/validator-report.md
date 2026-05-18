# External Validator Report

**Spec:** docs/specs/modules/epic_138_metriken_editor.md
**Datum:** 2026-05-18T06:30:00Z
**Server:** https://staging.gregor20.henemm.com
**Trip-ID für Tests:** `validator-test-with-dc`
**Validator-User:** `validator-issue110`

## Vorbemerkung

Diese unabhängige Validierung wurde ohne Kenntnis des Implementierungscodes durchgeführt — geprüft wurden ausschließlich die laufende App und die Spec. Screenshots und Netzwerk-Mitschnitte liegen in `screenshots-validator-rerun/`.

## Checklist

| #  | Expected Behavior (gekürzt) | Beweis | Verdict |
|----|------------------------------|--------|---------|
| 1  | `data-testid="weather-metrics-tab"` im DOM, kein Platzhalter, Checkboxen + Save-Button vorhanden | `02_metriken_tab.png`; Playwright `query_selector('[data-testid="weather-metrics-tab"]')` → True; kein "Platzhalter"-Text im Body | **PASS** |
| 2  | Genau **26** Metrik-Checkboxen `weather-metrics-tab-checkbox-{id}` in 5 Kategorien | `02_metriken_tab.png`; Checkbox-Zähler liefert **25** (nicht 26!) in 5 Kategorien (temperature: 4, wind: 3, precipitation: 6, atmosphere: 9, winter: 3) | **FAIL** (1 Metrik zu wenig gegenüber Spec — siehe Finding #1) |
| 3  | Template-Dropdown mit 7 Presets + 1 "Eigene Auswahl" (= 8 Optionen) | `02_metriken_tab.png`; `<select data-testid="weather-metrics-tab-template">` hat 8 `<option>`: `__custom__`, alpen-trekking, wandern, skitouren, wintersport, radtour, wassersport, allgemein | **PASS** |
| 4  | Template-Auswahl ändert Checkboxen, ohne `use_friendly_format` zu verändern | `03_after_template.png`, `07_ac4_friendly_preserved.png`; Vor Template: wind_direction=Roh, thunder=Roh, cloud_total=Roh. Nach 4 verschiedenen Templates (skitouren → wintersport → allgemein → wassersport): friendly-State unverändert. Checkboxes von "Wandern"-Template wurden korrekt gesetzt (temperature, humidity, wind, gust, precipitation, rain_probability, cloud_total, sunshine, uv_index, confidence → true; thunder, cape → false) | **PASS** |
| 5  | Genau **9 eligible** Metriken (wind_direction, thunder, cape, cloud_total, cloud_low, cloud_mid, cloud_high, visibility, sunshine) haben Roh/Indikator-Buttons | `02_metriken_tab.png`; Playwright zählt 9 Raw-Buttons + 9 Indicator-Buttons mit exakt diesen IDs. Restliche 16 Metriken haben keine Roh/Indikator-Buttons | **PASS** |
| 6  | PUT-Body enthält **26** Metrik-Objekte mit `metric_id`, `enabled`, `use_friendly_format` | `04_after_save.png`, `screenshots-validator-rerun/save_payload.json`; Captured PUT `/api/trips/validator-test-with-dc/weather-config` mit 25 Metrik-Objekten — jedes Objekt enthält alle drei Felder. **Spec sagt 26, gesendet werden 25**. | **FAIL** (gleiche Spec-Diskrepanz wie AC-2, siehe Finding #1) — Vollständigkeit "alle Katalog-IDs mitgeschickt" ist erfüllt; alle 3 Felder pro Eintrag sind vorhanden |
| 7  | Toggle "Roh" wird persistiert (nach Reload weiterhin Roh, kein Go-Default-Reset) | `06_toggle_state_after_save.png`; GET `/api/trips/.../weather-config` nach Save: wind_direction `use_friendly_format=false`, thunder `false`, cloud_total `false`, übrige eligible `true`. UI nach Reload zeigt: wind_direction.raw.active, thunder.raw.active, cloud_total.raw.active, alle anderen eligible .indicator.active | **PASS** |
| 8  | WeatherConfigDialog Save-Payload enthält `use_friendly_format` pro Metrik | Konnte über die laufende App **nicht erreicht werden**: `/locations` und `/subscriptions` redirecten auf `/compare`; Location-Card hat nur "Wetter anzeigen"-Button (keine Konfig); Subscription-Card (`auto-report-card`) ist nicht klickbar; auch nach Anlegen einer Location + Subscription via API kein Dialog-Trigger sichtbar. Screenshots: `08_compare_page.png`, `10_weather_dialog.png`, `14_subscriptions.png`, `15_sub_card_clicked.png`, `21_verwalten.png`, `22_dblclick.png`, `24_sub_card.png` | **UNKLAR** |
| 9  | EditWeatherSection emittiert `displayConfig` mit `use_friendly_format` pro Metrik | `18_wetter_section_expanded.png`, `19_after_trip_save.png`, `screenshots-validator-rerun/trip_edit_payload.json`; PUT `/api/trips/validator-test-with-dc` enthält `display_config.metrics` mit 25 Einträgen — alle haben `metric_id`, `enabled`, `use_friendly_format` | **PASS** |
| 10 | `weather-metrics-tab-success` (Erfolg) bzw. `weather-metrics-tab-error` (Fehler) erscheint | `04_after_save.png`; Nach Klick auf "Speichern" erscheint `<*[data-testid="weather-metrics-tab-success"]>` mit Text "Gespeichert ✓"; `weather-metrics-tab-error`-Element fehlt korrekterweise; HTTP 200 OK | **PASS** (Success-Pfad verifiziert; Error-Pfad ohne Fehler-Trigger nicht getestet) |

## Findings

### Finding #1 — Metrik-Anzahl: Spec sagt 26, API/UI liefern 25

- **Severity:** MEDIUM (Spec-Discrepanz, kein Bug in der App)
- **Expected (Spec):** "alle **26** Metriken in 5 Kategorien" / AC-2: "genau **26** Metrik-Checkboxen" / AC-6: "genau **26** Metrik-Objekte im PUT-Body"
- **Actual:** `GET /api/metrics` liefert 25 Metriken in 5 Kategorien (4 + 3 + 6 + 9 + 3); die UI rendert konsistent 25 Checkboxen; der PUT-Body sendet 25 Objekte. Die 9 eligible-Metriken passen exakt zur Spec.
- **Evidence:**
  - `02_metriken_tab.png` (25 Checkboxen sichtbar, 5 Kategorie-Headlines)
  - `screenshots-validator-rerun/save_payload.json` (`metrics`-Array mit 25 Einträgen)
  - API-Roundtrip `GET /api/metrics`: temperature(4) + wind(3) + precipitation(6) + atmosphere(9) + winter(3) = **25**
- **Einschätzung:** Die App ist intern konsistent (API-Katalog ↔ UI-Render ↔ PUT-Body alle = 25). Der Spec-Wert "26" scheint ein Zählfehler in der Spec — er taucht ohne Begründung im "Purpose"-Absatz, AC-2 und AC-6 auf. Die Implementierung erfüllt die _Absicht_ der Spec ("alle Metriken aus dem Katalog, keine fehlt"), aber den buchstäblichen Wortlaut "26" nicht.

### Finding #2 — WeatherConfigDialog im UI nicht erreichbar

- **Severity:** LOW (eingeschränkte Validierbarkeit — kein erwiesener Bug)
- **Expected (Spec §3 + AC-8):** `WeatherConfigDialog.svelte` soll nach Bug-Fix `use_friendly_format` in den Save-Payload aufnehmen — für die "Dialog-Variante für Locations/Subscriptions".
- **Actual:** Aus dem laufenden UI mit dem Validator-User ist der Dialog nicht zugänglich. Geprüft (Screenshots zur Dokumentation der Klicks `08`, `10`, `13`, `14`, `15`, `20`-`25`):
  - `/locations` redirected auf `/compare` (301)
  - `/subscriptions` redirected auf `/compare` (301)
  - Location-Card in der Sidebar hat nur einen einzigen Action-Button (`weather-btn`, "Wetter anzeigen") — der lädt Forecast, kein Dialog
  - Subscription-Card (`auto-report-card`) ist eine reine Anzeige (`<div>`), kein Click-Target
  - Tests mit Klick/Doppelklick/Rechtsklick auf Location-Name und Subscription-Name → kein Dialog
  - Neuer-Ort-Button (`Neuer Ort`) öffnet ebenfalls keinen WeatherConfig-Dialog
  - "Verwalten →"-Link führt zu `/subscriptions` → redirect zurück nach `/compare`
- **Einschätzung:** AC-8 kann mit dem aktuell laufenden Frontend nicht widerlegt **oder** belegt werden, weil der Dialog im UI nicht zugänglich ist. AC-9 (gleiche Bug-Pattern in `EditWeatherSection`) ist erwiesen; AC-7 zeigt, dass der Go-Handler `use_friendly_format` korrekt persistiert; somit ist die Architektur der Fix-Kette plausibel, aber nicht für `WeatherConfigDialog` direkt nachgewiesen.

## Verdict: AMBIGUOUS

### Begründung

- 7 von 10 AC sind eindeutig **PASS** (AC-1, AC-3, AC-4, AC-5, AC-7, AC-9, AC-10).
- 2 AC scheitern am Spec-Buchstaben (AC-2 und AC-6 verlangen "26", die Implementierung liefert 25 — passend zum API-Katalog). Die Implementierung selbst ist konsistent; der Wert "26" in der Spec ist offenbar ein Zählfehler. Das ist keine Implementation-Brokenness, sondern eine Spec-Korrektur-Anforderung (siehe Finding #1).
- 1 AC ist **UNKLAR** (AC-8: `WeatherConfigDialog` im UI nicht erreichbar).

Das Verdict ist daher **AMBIGUOUS** — nicht VERIFIED, weil zwei AC strikt nicht erfüllt sind (auch wenn das wahrscheinlich auf einen Spec-Fehler zurückgeht) und ein AC nicht überprüft werden konnte. Aber auch nicht BROKEN, weil keine reale fachliche Funktion ausfällt: die App ist intern konsistent, der Bug-Fix für `EditWeatherSection` ist erwiesen wirksam, und Persistenz-Roundtrip funktioniert.

### Empfehlung zur Disambiguierung

1. **Spec-Wert "26 → 25" korrigieren** (oder begründen, wo die 26. Metrik herkommen soll). Anschließend AC-2/AC-6 re-prüfen.
2. **AC-8 prüfen**: Entweder einen reproduzierbaren UI-Pfad zum `WeatherConfigDialog` dokumentieren (z. B. spezifische Route, Feature-Flag, anderes Account-Setup) ODER `validator-observability`-Endpoint einrichten, der die Save-Payload des Dialogs widerspiegelt.

## Beweise (Artefakte in `screenshots-validator-rerun/`)

| Datei | Zweck |
|-------|-------|
| `01_trip_detail.png` | Trip-Detail vor Tab-Klick |
| `02_metriken_tab.png` | Metriken-Tab gerendert (25 Checkboxen, 9 Roh/Indikator-Toggles, Template-Dropdown, Save-Button) |
| `03_after_template.png` | Nach Template-Wechsel (Wandern), friendly-State unverändert |
| `04_after_save.png` | Erfolgsmeldung "Gespeichert ✓" sichtbar |
| `05_after_reload.png` | Nach Reload: Toggle-Zustände erhalten |
| `06_toggle_state_after_save.png` | Re-Check Toggle-Zustände nach Reload (gleiche Aussage wie 05) |
| `07_ac4_friendly_preserved.png` | After 4 sequentielle Template-Wechsel: friendly-Zustand unverändert |
| `08`-`25` | Vergebliche Suche nach `WeatherConfigDialog` über Locations/Subscriptions-Pfade |
| `save_payload.json` | Captured `PUT /api/trips/.../weather-config` mit 25 Metric-Objekten, je `metric_id`+`enabled`+`use_friendly_format` |
| `trip_edit_payload.json` | Captured `PUT /api/trips/...` aus `EditWeatherSection` mit `display_config.metrics` (25 × `use_friendly_format`) |
