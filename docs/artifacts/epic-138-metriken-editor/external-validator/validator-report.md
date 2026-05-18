# External Validator Report

**Spec:** docs/specs/modules/epic_138_metriken_editor.md
**Datum:** 2026-05-18
**Server:** https://staging.gregor20.henemm.com
**Trip für UI-Test:** `validator-test-with-dc` (Trip „Mit DisplayConfig")

## Zusammenfassung

Epic 138 ist auf dem Staging-Server **nicht deployed**. Der Wetter-Metriken-Tab zeigt
weiterhin den Platzhaltertext „Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)".
Zusätzlich fehlt das in §1 der Spec geforderte Feld `has_friendly_format` in der
`/api/metrics`-Antwort vollständig (0 von 25 Metriken). Damit sind alle UI-bezogenen
Acceptance Criteria (AC-1 bis AC-7, AC-10) und die Backend-Erweiterung nicht testbar/erfüllt.

Nebenbeobachtung: Die Spec spricht von **26** Metriken (AC-2), die laufende API liefert
**25** Metriken in 5 Kategorien (temperature 4, wind 3, precipitation 6, atmosphere 9, winter 3).
Selbst nach Deploy würde AC-2 nicht erfüllbar sein, solange die Diskrepanz nicht aufgelöst
ist.

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | `data-testid="weather-metrics-tab"` sichtbar, kein Platzhalter, Checkboxen+Save-Button | `02_metrics_tab_opened.png`, `04_placeholder_zoom.png` — Platzhalter „Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)" ist sichtbar; kein `data-testid="weather-metrics-tab"` im DOM (`probe_results.json` AC1_tabRoot=false) | **FAIL** |
| 2 | 26 Metrik-Checkboxen `weather-metrics-tab-checkbox-{id}` in 5 Kategorie-Abschnitten | 0 Checkboxen im DOM (`probe_results.json` AC2_checkboxCount=0); zusätzlich liefert `/api/metrics` nur 25 IDs (siehe `metrics_api_dump.json`) | **FAIL** |
| 3 | Template-Dropdown `weather-metrics-tab-template` mit 7+1 Optionen | Dropdown existiert nicht (`probe_results.json` AC3_dropdownExists=false) | **FAIL** |
| 4 | Template-Auswahl ändert Checkboxen, nicht `use_friendly_format` | Nicht testbar — Dropdown und Checkboxen fehlen | **FAIL** |
| 5 | 9 eligible Metriken haben `format-raw-{id}` + `format-indicator-{id}`, andere 17 nicht | 0 raw/indicator-Buttons im DOM (`probe_results.json` AC5_rawButtonIds=[], AC5_indButtonIds=[]) | **FAIL** |
| 6 | PUT-Body enthält genau 26 Metrik-Objekte mit `metric_id`, `enabled`, `use_friendly_format` | Save-Button `weather-metrics-tab-save` existiert nicht; kein PUT triggerbar (`probe_results.json` AC6_saveBtnExists=false) | **FAIL** |
| 7 | „Roh"-Toggle persistiert nach Reload | Nicht testbar — Toggle fehlt | **FAIL** |
| 8 | `WeatherConfigDialog` enthält `use_friendly_format` im Payload, GET liefert es zurück | Indirekt nicht testbar im UI: validator hat keine Location/Subscription auf Staging (`/api/locations` und `/api/subscriptions` sind beide leer); Spec §1 (`has_friendly_format`) ist Voraussetzung für die Roh/Indikator-Buttons im Dialog und ist nicht deployed → mindestens **AMBIGUOUS**, aufgrund fehlendem Backend-Feld faktisch **FAIL** | **FAIL** |
| 9 | `EditWeatherSection` emittiert `use_friendly_format` im `displayConfig` | Nicht direkt im laufenden System validierbar (interner Svelte-Emission-Effekt); Voraussetzung `has_friendly_format` aus `/api/metrics` fehlt → kein Roh/Indikator-Toggle, kein zu emittierender Wert | **FAIL** |
| 10 | `weather-metrics-tab-success` / `weather-metrics-tab-error` nach Speichern | Nicht testbar — Tab-Komponente und Save-Button fehlen | **FAIL** |

## Findings

### F-1: Komplette Frontend-Komponente nicht deployed
- **Severity:** CRITICAL
- **Expected:** „Wetter-Metriken"-Tab zeigt vollständigen Inline-Editor mit Checkboxen, Template-Dropdown, Save-Button (Spec §5/§6, AC-1, AC-2, AC-3, AC-6, AC-10).
- **Actual:** Tab zeigt unveränderten Platzhaltertext „Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)". DOM enthält weder `data-testid="weather-metrics-tab"` noch eine einzige `weather-metrics-tab-checkbox-*` oder `weather-metrics-tab-save`.
- **Evidence:** `02_metrics_tab_opened.png`, `04_placeholder_zoom.png`, `probe_results.json` (alle Probes zeigen 0/false).

### F-2: Backend-Feld `has_friendly_format` fehlt in /api/metrics
- **Severity:** CRITICAL
- **Expected:** Spec §1 — jedes Metrik-Objekt in `/api/metrics` enthält `has_friendly_format: bool`. 9 eligible Metriken (`wind_direction, thunder, cape, cloud_total, cloud_low, cloud_mid, cloud_high, visibility, sunshine`) → `true`, alle anderen → `false`.
- **Actual:** Keine einzige Metrik in der `/api/metrics`-Antwort hat das Feld `has_friendly_format`. Damit hätten auch nach UI-Deploy weder `WeatherMetricsTab`, noch `WeatherConfigDialog`, noch `EditWeatherSection` eine Datenquelle, um zu entscheiden, für welche Metriken die Roh/Indikator-Buttons gerendert werden — AC-5, AC-8, AC-9 (Roh/Indikator-UX) wären unerfüllbar.
- **Evidence:** `metrics_api_dump.json`; gezählt 0/25 Metriken mit dem Feld (Output `probe_metrics.txt`).

### F-3: Metrik-Anzahl-Diskrepanz Spec ↔ API
- **Severity:** HIGH
- **Expected:** Spec §5 und AC-2 sagen „26 Metriken in 5 Kategorien", Save-Payload „Alle 26 Metrik-IDs müssen mitgesendet werden".
- **Actual:** `/api/metrics` liefert **25** Metriken (temperature: 4, wind: 3, precipitation: 6, atmosphere: 9, winter: 3). Selbst wenn die Frontend-Komponente deployt würde, könnte AC-2 („genau 26 Checkboxen") und AC-6 („genau 26 Metrik-Objekte") nicht erfüllt werden, ohne dass entweder die API um eine weitere Metrik erweitert oder die Spec auf 25 korrigiert wird.
- **Evidence:** `metrics_api_dump.json` mit Ausgabe „TOTAL: 25, Categories: 5".

### F-4: WeatherConfigDialog-Test (AC-8) blockiert durch fehlende Stammdaten
- **Severity:** MEDIUM (Methodik-Lücke; durch F-1/F-2 ohnehin Folge-FAIL)
- **Expected:** AC-8 testet UI-Flow „Dialog speichert, GET liefert use_friendly_format zurück".
- **Actual:** Validator-Account hat keine Locations und keine Subscriptions auf staging (`/api/locations` = `[]`, `/api/subscriptions` = `[]`). Selbst wenn der Dialog korrekt gepatcht wäre, ließe er sich ohne Stammdaten gar nicht öffnen.
- **Evidence:** zwei curl-Aufrufe oben.

## Verdict: BROKEN

### Begründung

1. **Hauptkomponente fehlt vollständig auf staging.** Der „Wetter-Metriken"-Tab zeigt
   unverändert den Platzhaltertext, den die Spec §6 entfernen sollte. Damit fallen AC-1,
   AC-2, AC-3, AC-4, AC-5, AC-6, AC-7 und AC-10 unmittelbar durch.
2. **Backend-Vorbedingung (§1) nicht erfüllt.** `/api/metrics` liefert das Feld
   `has_friendly_format` für **null** der 25 Metriken. Ohne dieses Feld kann die UI
   gar nicht entscheiden, für welche Metriken die Roh/Indikator-Toggles zu rendern
   sind — AC-5/8/9 wären auch nach Frontend-Deploy nicht erfüllbar.
3. **Metrik-Anzahl-Inkonsistenz.** Spec verlangt 26 Metriken, API liefert 25 — auch
   nach vollständigem Deploy würde AC-2/AC-6 mit der aktuellen API blockieren.

Die Spec ist in keiner einzigen UI-AC nachweisbar erfüllt. Das ist ein klares
**BROKEN** — vor allem deshalb, weil im Git-Workspace zwar offenbar Implementierungs-
spuren existieren, aber weder Commit noch Deploy auf staging stattgefunden hat. Ein
ordentlicher Post-Push-Workflow (Push → Staging-Auto-Deploy → Validator) wurde
übersprungen.

### Nächste Schritte für die Implementierer-Session

- `api/routers/config.py` und die Frontend-Änderungen committen und über
  `deploy-gregor-prod.sh` bzw. die normale Push→Auto-Deploy-Pipeline auf staging
  bringen.
- Backend-Diff verifizieren: `curl /api/metrics | grep has_friendly_format` muss
  in jedem Objekt fündig werden, und die 9 eligible IDs müssen `true` haben.
- Spec ↔ API auf die Metrik-Anzahl abgleichen: entweder Spec auf 25 korrigieren
  (inkl. AC-2/AC-6) oder die fehlende 26. Metrik in den Katalog aufnehmen.
- Nach erneutem Deploy diese Validator-Session erneut starten.
