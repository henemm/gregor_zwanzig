# Context: Issue #300 — Wizard-Redesign (4-Schritt-Neue-Tour)

## Request Summary

Der bestehende Trip-Wizard (`/trips/new`) muss auf das Claude-Design-Soll umgestellt werden:
Schritte von **Profil/GPX/Wegpunkte/Briefings** zu **Route/Etappen/Wetter/Reports**.
Das sind 3 von 4 Schritten, die entweder komplett neu (Wetter) oder wesentlich umgebaut werden müssen.

## Ist-Zustand (was schon existiert)

| Schritt | Aktueller Label | Inhalt |
|---------|-----------------|--------|
| 1 | Profil & Eckdaten | 5 Activity-Chips + Name + Kürzel + Region + Startdatum |
| 2 | GPX-Import | Drag-Drop GPX + DnD-Sortierung + Pausentag + Templates |
| 3 | Wegpunkte | KI-Vorschläge bestätigen (Etappen-Liste + ProfileChart + WaypointRows) |
| 4 | Briefings | Kanäle (4 Toggles) + 2 ReportRows (morning/evening) + AlertRulesEditor |

## Soll-Zustand (Issue #300 + Screenshots)

| Schritt | Neuer Label | Inhalt |
|---------|-------------|--------|
| 1 | Route | Trip-Name (links) + Region (rechts) + GPX-Dropzone + 2 Buttons + Link "Manuell" |
| 2 | Etappen | Erkannte Etappen-Liste + "N Etappen aus N GPX" Header + "Zusammenführen" + Vorschläge-Pills |
| 3 | Wetter | Aktivitätsprofil-Dropdown + Metriken-Tabelle mit 3-Horizon-Toggles pro Zeile |
| 4 | Reports | 4 Cards (2×2): Abend-Briefing, Morgen-Update, Warnungen/Wachhund, Trend-Vorschau |

## Gap-Analyse (was fehlt / muss umgebaut werden)

### Schritt 1 (Route) — Umbau
- **Entfernen:** 5 Activity-Chips (Trekking/Skitour/Hochtour/Klettersteig/MTB), Kürzel-Feld
- **Hinzufügen:** GPX-Dropzone **in Step 1** (wird aus Step 2 hochgezogen oder Step-Reihenfolge angepasst)
- **Hinzufügen:** "Aus Dateisystem wählen" + "Vom letzten Trip kopieren" Buttons
- **Hinzufügen:** "Ohne GPX: Etappen manuell anlegen →" Link
- **Behalten:** Trip-Name + Region + (Startdatum implizit via Etappen)
- **Aktivitätsprofil verschiebt sich** → jetzt Dropdown in Schritt 3

### Schritt 2 (Etappen) — Umbau
- Aktuell: Schritt 2 IST der GPX-Upload + Etappenanlage
- Im Soll: Schritt 2 zeigt die **bereits erkannten Etappen** (nach GPX-Upload in Schritt 1)
- Header: "N ETAPPEN ERKANNT AUS N GPX" Badge + "Zusammenführen" + "+ Etappe einschieben"
- Etappen-Zeile: Nummer · Name · Datum · km · ↑Höhe · WP-Zähler · "+N Vorschläge" (orange dashed pill)
- Footer: "← Zurück" + Hilfetext + "Pausentag einfügen" + "Weiter →"
- **Weitgehend bereits implementiert** — kleine Layout-Anpassungen nötig

### Schritt 3 (Wetter) — Komplett neu ⚠️
- **Komplett neu bauen** — existiert nicht
- Aktivitätsprofil-Dropdown (Alpen-Trekking Sommer, Skitouren, etc.) → setzt WizardState.activity
- "N Metriken aktiv · N angepasst" Summary-Text
- Metriken-Tabelle mit pro Zeile:
  - Metrik-Name + Beschriftung (z.B. "AM WICHTIGSTEN")
  - 3 HorizonChips (HEUTE/MORGEN/ÜBERMORGEN) — toggle-bar
  - Format-Label (Roh / Indikator / Roh + Indikator)
  - "…" Context-Menü
  - "HINZUGEFÜGT" Badge für non-template Metriken
  - Letzte Zeile deaktiviert = grayed out (Metrik nicht im Template)
- Benötigt: neue WizardState-Felder für `weatherMetrics` (Array mit MetricId + enabled + horizons)
- **HorizonChip.svelte existiert bereits** — wiederverwendbar
- Vorhandene Metrik-Infra: `horizonHelpers.ts`, `MetricCheckbox.svelte`, `WeatherMetricsTab.svelte` (für Trip-Detail)

### Schritt 4 (Reports) — Umbau
- **Entfernen:** Kanäle-Sektion + 2 ReportRows + AlertRulesEditor (vollständig ersetzen)
- **Bauen:** 4 Cards im 2×2 Grid:
  1. Abend-Briefing (Uhrzeit + Metriken-Text + Kanal-Chips + "Tour speichern" CTA am Ende)
  2. Morgen-Update (Uhrzeit + Metriken-Text + Kanal-Chips)
  3. Warnungen/Wachhund (kein Zeitfeld, "AUTARK" Badge + Kriterien-Text + Kanal-Chips)
  4. Trend-Vorschau (Sonntag + Uhrzeit + "5-Tage Übersicht" Text + Kanal-Chips)
- Kanal-Chips: kleine Pill-Tags (E-Mail, Signal, SMS) + "+ Kanal" Hinzufügen-Button

## Vorhandene Bausteine (wiederverwendbar)

| Baustein | Pfad | Für |
|----------|------|-----|
| `HorizonChip.svelte` | `src/lib/components/ui/horizon-chip/` | Schritt 3 Toggles |
| `horizonHelpers.ts` | `src/lib/utils/` | Horizon-Logik |
| `MetricCheckbox.svelte` | `src/lib/components/trip-detail/` | Metrik-Zeile Schritt 3 |
| `WeatherMetricsTab.svelte` | `src/lib/components/trip-detail/` | Referenz-Impl für Schritt 3 |
| `metricsEditor.ts` | `src/lib/components/trip-detail/` | Metriken-State-Logik |
| `AlertRulesEditor.svelte` | `src/lib/components/alert-rules-editor/` | Ggf. für Warnungen-Card |
| `TripWizardShell.svelte` | `src/lib/components/trip-wizard/` | Shell bleibt, Labels ändern |
| `WizardState` | `src/lib/components/trip-wizard/wizardState.svelte.ts` | Neue Felder ergänzen |
| `Step2Stages.svelte` | `src/lib/components/trip-wizard/steps/` | Basis für neuen Schritt 2 |
| `Btn`, `Pill`, `GCard`, `Eyebrow` | `src/lib/components/ui/` | Design-System |

## Abhängigkeiten

**Upstream (unser Code nutzt):**
- `$lib/api` — GPX-Upload-Endpoint, Trip-Save-Endpoint
- `$lib/types` — `Trip`, `Stage`, `ActivityType`, `AlertRule`
- Design-System Tokens (app.css)
- Backend: `internal/handler/` (Trip-CRUD, Metric-Presets)

**Downstream (nutzt unseren Code):**
- `/trips/new/+page.svelte` → `TripWizardShell`
- `WizardState.save()` → Backend `POST /api/trips`

## Backend-Änderungen nötig?

- **Schritt 3 Metriken:** Die Metrik-Horizonte müssen beim `save()` in den Trip-Payload. 
  Das bestehende Trip-Model hat `aggregation_profile` für Metriken (WeatherMetricsTab). 
  Vermutlich können die Horizonte als `display_metrics` im Trip-Payload gespeichert werden.
- **Warnungen/Wachhund:** AlertRules bereits im WizardState vorhanden → nur UI-Änderung
- **Trend-Vorschau:** Neuer Report-Typ — braucht Backend-Feld in `report_config`

## Risiken & Entscheidungen

1. **Activity-Position:** Activity-Chips wandern von Step 1 (Profil) zu Step 3 (Dropdown). 
   `WizardState.canAdvanceStep1` muss angepasst werden (kein `activity` mehr dort).
2. **Step-Merge vs. Step-Umbau:** Step 2 (aktuell GPX-Upload) und neuer Step 1 (GPX-Upload) 
   sind faktisch dasselbe — die Lösung ist, Step 1 **umzubauen** statt neu zu bauen.
3. **Schritt 3 Datenmodell:** Braucht neues `weatherMetrics[]` Feld in WizardState + 
   Mapping in `toTripPayload()` auf Backend-Format.
4. **Step 3 Template-Vorausfüllung:** Wer liefert die Default-Metriken für ein Template? 
   Vermutlich `metricsEditor.ts` oder Backend `/api/metric-presets`.
5. **Schritt 4 Übergangs-Kompatibilität:** Step 4 ersetzt AlertRulesEditor komplett — 
   AlertRules müssen irgendwo in neuen Report-Cards integriert werden.

## Betroffene Dateien

| Datei | Änderung |
|-------|---------|
| `src/lib/components/trip-wizard/TripWizardShell.svelte` | Step-Labels + Stepper-Sub-Labels |
| `src/lib/components/trip-wizard/wizardState.svelte.ts` | +`weatherMetrics`, anpassen `canAdvanceStep1` |
| `src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Komplett umbauen → Route-Step |
| `src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Header + Vorschläge-Pills ergänzen |
| `src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | Ersetzen durch neuen Wetter-Step |
| `src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Ersetzen durch 4-Cards-Reports |
| `src/lib/components/trip-wizard/steps/` | Neue Datei: `Step3Weather.svelte` |
| `src/lib/components/trip-wizard/steps/` | Neue Datei: `Step4Reports.svelte` |
| `internal/model/` | Ggf. neuer Report-Typ `trend_preview` |

## Scope-Einschätzung

**Groß.** 4 Schritt-Komponenten + WizardState-Erweiterung + evtl. Backend-Änderungen.
Empfehlung: Issue #300 in Sub-Issues aufteilen oder schrittweise angehen:
1. Step 1 (Route-Umbau) — unabhängig, kein Backend
2. Step 2 (Etappen-Layout-Anpassung) — kein Backend
3. Step 3 (Wetter-Template) — neues WizardState-Feld + evtl. Backend
4. Step 4 (4 Report-Cards) — WizardState-Änderung, evtl. Backend für Trend-Vorschau
