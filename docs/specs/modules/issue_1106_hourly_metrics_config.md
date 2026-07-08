---
entity_id: issue_1106_hourly_metrics_config
type: feature
created: 2026-07-08
updated: 2026-07-08
status: implemented
version: "1.0"
tags: [compare, hourly, display_config, resolver, validator]
workflow: fix-1106-hourly-metrics-config
---

# Ortsvergleich C: Metriken im Stundenverlauf konfigurierbar (#1106)

## Approval

- [x] Approved
- [x] Implemented (2026-07-08)

## Purpose

Die Stundentabelle jeder Ort-Sektion in der Compare-Mail zeigt aktuell 7 fest verdrahtete
Wetter-Spalten (Temp, Gef., Wind, Böen, Regen, Wolken, UV) ohne dass der Nutzer beeinflussen
kann, welche davon erscheinen. Dieses Slice macht die Spalten konfigurierbar — analog zum
Resolver-Pattern für die Übersichtstabelle aus #1104 — und erweitert das Metrik-Inventar
gleichzeitig um drei bislang im Stundenverlauf gar nicht sichtbare, sicherheitsrelevante
Datenpunkte (Gewitter-Risiko, Regenwahrscheinlichkeit, Sicht), während die eher dekorative
Wolken-Spalte entfällt. Default bleibt "alle Spalten sichtbar", weil der Ortsvergleich am
Frühstückstisch in Ruhe gelesen wird, nicht unter Zeitdruck unterwegs.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `_render_hour_row`, `_render_hour_table`, `_render_location_section`,
  `render_compare_html` — sowie neue Konstante `HOUR_METRICS` (ersetzt `_HOUR_COLUMNS`).
- **Neues Modul:** `src/output/renderers/compare_hourly_metric_ids.py` —
  `resolve_hourly_metrics()`, kanonischer ID-Resolver für das Stundenverlauf-Vokabular
  (eigenständig, kein Reuse von `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`, da
  Rohwerte pro Stunde ≠ Aggregate der Übersicht).

> **Schicht-Hinweis:** Python-Core (`src/output/renderers/`, `src/services/`) für Resolver +
> Renderer-Loop-Umbau + Versandpfad-Wiring. SvelteKit-Frontend
> (`frontend/src/lib/components/compare/`) für die neue Checkbox-UI im Schritt "Versand" und
> den Preset-Save-Pfad. **Kein Go-Struct-Change nötig** — `display_config` ist bereits
> `map[string]interface{}` (`internal/model/compare_preset.go:33`) und wird transparent
> durchgereicht. **Validator-Hook** (`.claude/hooks/email_spec_validator.py`) ist Kern-Teil des
> Scopes, nicht optional — ohne Anpassung ist jeder E2E-Test mit gefiltertem Stundenverlauf
> strukturell nicht bestehbar.

## Estimated Scope

- **LoC:** ~380-450 (Implementierung ~200-240: Renderer-Loop-Umbau + 3 neue Formatier-/
  Sev-Funktionen + Resolver + Validator-Umbau + Wiring; Frontend ~90-110; Tests ~150-180).
  Höher als die ursprüngliche Plan-Schätzung (~300-350), weil der PO den Scope in der
  Analyse-Phase um 3 neue Spaltentypen (kategorial/Prozent/Meter) erweitert hat — siehe
  Kontext-Dokument, Abschnitt "Scope-Erweiterung ggü. ursprünglichem Issue-Text".
- **Files:** ~10-11 geändert/neu (exkl. neuer Tests), siehe Affected Files unten.
- **Effort:** medium-high

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | `_HOUR_COLUMNS` entfernen, neue Konstante `HOUR_METRICS` (9 Metrik-Defs mit `key`/`label`/`fmt`/`sev` bzw. `kind="categorical"` für Gewitter); `_render_hour_row`/`_render_hour_table` auf Loop über `_visible_hour_metrics(hourly_metrics)` umbauen; `_render_location_section`/`render_compare_html` erhalten neuen Parameter `hourly_metrics: set \| None = None` |
| `src/output/renderers/compare_hourly_metric_ids.py` | CREATE | `resolve_hourly_metrics()` + `FRONTEND_TO_HOURLY_METRIC_ID`-Dict, analog `compare_metric_ids.py`, aber eigenes Vokabular (Rohwerte statt Aggregate) |
| `src/output/renderers/comparison.py` | MODIFY | `render_compare_email()` erhält Parameter `hourly_metrics`, reicht ihn an `render_compare_html()` durch (analog `enabled_metrics`, Z.117-147) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `display_config.get("hourly_metrics")` lesen (neben Z.251-270), via `resolve_hourly_metrics()` auflösen, an `render_compare_email()` durchreichen |
| `.claude/hooks/email_spec_validator.py` | MODIFY | `_HOUR_COLUMNS_V2` (Z.126-127) wird kanonische Superset-Liste (10 Header inkl. "Zeit"); Exakt-Vergleich (Z.249-254) → Teilmengen-mit-Reihenfolge-Prüfung + Mindestspalten-Regel (≥2: "Zeit" + mind. 1 Wert-Spalte) |
| `docs/specs/modules/issue_1108_email_spec_validator_v2.md` | MODIFY | Abschnitt zum `_HOUR_COLUMNS_V2`-Vertrag um Teilmengen-Semantik ergänzen |
| `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` | CREATE | Katalog der 9 wählbaren Stundenverlauf-Metriken (Frontend-IDs + Label) für die Checkbox-UI |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | Neues State-Feld `hourlyMetricKeys`, Load/Save analog `activeMetricKeys` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | Neues Edit-Feld `hourlyMetricKeys?: string[]` → `displayConfig.hourly_metrics` im Save-Payload-Mapping |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | MODIFY | Neue Checkbox-Sektion "Metriken im Stundenverlauf" unterhalb der bestehenden "Anzahl Orte"-Sektion (Z.181-198) |
| `tests/tdd/test_issue_1106_hourly_metrics_config.py` | CREATE | Resolver-Unit-Test + Renderer-Loop-Test + echte Staging-Mail-Verifikation (kein Mock) |
| `frontend/src/lib/components/compare/compareEditorHourlyMetrics.test.ts` | CREATE | Pure-Function Round-Trip-Test für `hourlyMetricKeys` in `buildComparePresetSavePayload()` |

Go: **keine Änderung nötig** — `DisplayConfig map[string]interface{}` bleibt generisch.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.comparison::render_compare_email(hourly_metrics=)` | Neu, dieses Slice | Neuer Kwarg, analog `enabled_metrics` |
| `output.renderers.email.compare_html::render_compare_html(hourly_metrics=)` | Neu, dieses Slice | Neuer Kwarg, filtert `HOUR_METRICS` |
| `output.renderers.compare_metric_ids::resolve_enabled_metrics` | Vorbild, unverändert | Resolver-Pattern-Referenz (kein Code-Reuse, anderes Vokabular) |
| `app.models::ForecastDataPoint` (`src/app/models.py:87-138`) | Upstream, unverändert | Liefert bereits alle 9 benötigten Rohwert-Attribute inkl. `thunder_level` (Z.101), `pop_pct` (Z.103), `visibility_m` (Z.118) — **keine Model-/Aggregations-Änderung nötig**, diese Felder werden bereits normalisiert und in `hourly_data` befüllt (Trip-Briefing-Pfad nutzt sie bereits, s. `helpers.py:1190-1250`) |
| `output.renderers.email.html::_THUNDER_LEVEL_LABEL`/`_THUNDER_LEVEL_BG` (Z.1160-1161) | Format-Vorbild | Enum-Label/Farb-Mapping für die neue Gewitter-Spalte |
| `output.renderers.email.helpers::format_stage_summary` (Z.1190-1250, `rain_probability`/`thunder`/`visibility`-Zweige) | Format-Vorbild | Referenz für Rundung/Einheiten der 3 neuen Metriken (Text-Form ist Trip-Briefing-spezifisch, hier wird nur die *numerische/kategoriale Kurzform* für Tabellenzellen übernommen) |
| `.claude/hooks/email_spec_validator.py::_HOUR_COLUMNS_V2` (Z.127) | Downstream, MUSS in diesem Slice angepasst werden | Sonst blockt jeder E2E-Test mit gefilterter Spaltenauswahl das Gate — kein optionales Nice-to-have |
| Issue #1104 (`compare_metric_ids.py`/`resolve_enabled_metrics`) | Muster-Referenz | Analoges additives `display_config`-Feld, identisches Resolver-Prinzip (None=alle, defensiv gegen ungültigen Input) |
| Issue #1131 (Follow-up) | Abgegrenzt, NICHT Teil dieses Slices | Entfernung des Alt-Pfads `compare_subscription.py` |

## Implementation Details

**Resolver (`compare_hourly_metric_ids.py`, analog `compare_metric_ids.py`):**

```
FRONTEND_TO_HOURLY_METRIC_ID: dict[str, str] = {
    "temp_c": "t2m_c", "wind_chill_c": "wind_chill_c", "wind_kmh": "wind10m_kmh",
    "gust_kmh": "gust_kmh", "precip_mm": "precip_1h_mm", "uv_index": "uv_index",
    "thunder_level": "thunder_level", "pop_pct": "pop_pct", "visibility_m": "visibility_m",
}

def resolve_hourly_metrics(hourly_metrics: list[str] | None) -> set[str] | None:
    # None/leer/nicht-Liste -> None (= alle 9 sichtbar, Default).
    # Unbekannte IDs werden verworfen statt Absturz. Bildet Auswahl komplett
    # auf nichts Mappbares ab -> ebenfalls None (keine leere Tabelle).
```

Exakte Frontend-ID-Namen sind Implementierungsdetail des Developer-Agenten (müssen mit
`compareHourlyMetricDefs.ts` übereinstimmen) — Vertrag ist: 9 Einträge, "Zeit" nicht enthalten.

**Renderer (`compare_html.py`):**

`HOUR_METRICS` ersetzt `_HOUR_COLUMNS` als Liste von Dicts (Reihenfolge = Spaltenreihenfolge,
IMMER: Temp, Gef., Wind, Böen, Regen, UV, Gewitter, Regenwahrscheinlichkeit, Sicht):

```
HOUR_METRICS = [
    {"key": "t2m_c", "label": "Temp", "fmt": <°C, 0 decimals>, "sev": _sev_temp},
    {"key": "wind_chill_c", "label": "Gef.", "fmt": <°C, 0 decimals>},
    {"key": "wind10m_kmh", "label": "Wind", "fmt": <km/h, 0 decimals>, "sev": _sev_wind},
    {"key": "gust_kmh", "label": "Böen", "fmt": <km/h, 0 decimals>, "sev": _sev_gust},
    {"key": "precip_1h_mm", "label": "Regen", "fmt": <mm, 1 decimal, "." bei 0>, "sev": _sev_rain},
    {"key": "uv_index", "label": "UV", "fmt": <int>, "sev": _sev_uv},
    {"key": "thunder_level", "label": "Gew.", "kind": "categorical",
     "labels": _THUNDER_LEVEL_LABEL, "bg": _THUNDER_LEVEL_BG},  # Vorbild html.py:1160-1161
    {"key": "pop_pct", "label": "Regen-W.", "fmt": <%, int>, "sev": _sev_pop},
    {"key": "visibility_m", "label": "Sicht", "fmt": <km, 1 decimal>, "sev": _sev_visibility},
]
```

`_visible_hour_metrics(hourly_metrics: set | None) -> list[dict]` analog `_visible_metrics()`
(Z.169-176): `None` → alle 9, sonst Filter nach `key in hourly_metrics`. "Zeit" bleibt außerhalb
dieser Liste, fest verdrahtete erste Spalte in `_render_hour_row`/`_render_hour_table`
(unverändert wie bisher). `_render_hour_row(dp, visible)` iteriert über `visible` statt über
7 hartkodierte Zellen; kategoriale Einträge (Gewitter) rendern `NONE` als "—" (kein Wert), sonst
Label aus `_THUNDER_LEVEL_LABEL` mit Hintergrundfarbe aus `_THUNDER_LEVEL_BG`.

**Validator (`email_spec_validator.py`):**

`_HOUR_COLUMNS_V2` wird die kanonische 10-Spalten-Superset-Liste (Reihenfolge wie `HOUR_METRICS`
plus "Zeit" an Position 0). Prüfung ändert sich von Exakt-Gleichheit zu:

```python
if header_cols[0] != "Zeit" or len(header_cols) < 2:
    FAIL  # Zeit fehlt oder keine einzige Wert-Spalte (Mindestspalten-Regel)
if [c for c in _HOUR_COLUMNS_V2 if c in header_cols] != header_cols:
    FAIL  # Fremdspalte oder Umsortierung
```

Damit werden weiterhin Erosion (Fremdspalten-Einschleusung) und Sinnlos-Konfiguration (0
Wert-Spalten) verhindert, aber jede gültige Teilmenge in korrekter Reihenfolge akzeptiert.

**Frontend:** `compareHourlyMetricDefs.ts` listet die 9 Metriken (Label = Spaltenname, IDs
identisch zu `FRONTEND_TO_HOURLY_METRIC_ID`-Keys). `Step5Versand.svelte` bekommt eine neue
Checkbox-Sektion analog dem bestehenden Idealwerte-Muster (`Step3Idealwerte.svelte:26-116`),
alle 9 Checkboxen standardmäßig angehakt (Default = alle sichtbar).

## Expected Behavior

- **Input:** `ComparePreset.display_config.hourly_metrics` (Liste von Frontend-Metrik-IDs oder
  fehlend/leer/`null`).
- **Output:** Die tatsächlich per E-Mail versendete Compare-Mail zeigt in jeder Ort-Sektion im
  Stundenverlauf genau die Spalten "Zeit" + die resolvte Teilmenge (in fester Reihenfolge:
  Temp, Gef., Wind, Böen, Regen, UV, Gewitter, Regenwahrscheinlichkeit, Sicht — jeweils nur
  die ausgewählten). Fehlt `hourly_metrics` oder ist leer/ungültig, erscheinen alle 9 Spalten
  (Default). Wolken erscheint nie mehr, unabhängig von der Konfiguration.
- **Side effects:** Keine — reine Lesezugriffe auf bereits persistierte Preset-Felder, kein
  neuer Netzwerk-Call, keine Schema-Migration.

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset ohne das Feld `hourly_metrics` (Bestandsdaten oder nie
  angefasste Einstellung), When der Versand ausgelöst wird, Then zeigt die tatsächlich
  zugestellte Compare-Mail in jeder Ort-Sektion alle 9 Wert-Spalten (Temp, Gef., Wind, Böen,
  Regen, UV, Gewitter, Regen-W., Sicht) plus "Zeit" — kein Zeitdruck-Kontext rechtfertigt eine
  reduzierte Default-Ansicht.
  - Test: Echtes Preset ohne `hourly_metrics` über den realen Preset-Pfad speichern, Versand
    real auslösen, zugestellte Mail via IMAP aus `gregor-test@henemm.com` abrufen, die
    Spalten-Header der Stundentabelle im HTML zählen und gegen die 10 erwarteten Header prüfen.

- **AC-2:** Given ein Nutzer hat im Compare-Editor eine Teilmenge der Stundenverlauf-Metriken
  ausgewählt (z.B. nur Temp + Wind + Gewitter) und gespeichert, When der Versand ausgelöst wird,
  Then zeigt die zugestellte Mail in jeder Ort-Sektion ausschließlich diese Teilmenge plus
  "Zeit" — keine weiteren Spalten, keine fehlenden.
  - Test: Preset mit `display_config.hourly_metrics=["temp_c","wind_kmh","thunder_level"]`
    über den echten Preset-Pfad speichern, Versand real auslösen, zugestellte Mail abrufen,
    Header-Zeile der Stundentabelle exakt gegen `["Zeit","Temp","Wind","Gew."]` prüfen.

- **AC-3:** Given eine beliebige Metrik-Auswahl (auch eine leere ungültige Auswahl, die
  vollständig auf nicht-mappbare IDs zeigt), When der Versand ausgelöst wird, Then ist "Zeit"
  immer die erste Spalte jeder Stundentabelle — sie ist nie Teil der wählbaren Liste und kann
  durch keine Konfiguration entfernt werden.
  - Test: Drei reale Versandläufe (kein `hourly_metrics`, gültige Teilmenge, Liste aus
    ausschließlich unbekannten IDs) gegen die echte Staging-Mail — in allen drei Fällen ist
    "Zeit" der erste Header-Eintrag jeder Ort-Sektion.

- **AC-4:** Given ein Preset mit `hourly_metrics`, das die drei neuen Metriken enthält
  (`thunder_level`, `pop_pct`, `visibility_m`), When der Versand ausgelöst wird, Then zeigt die
  zugestellte Mail für Stunden mit Gewitter-Risiko den Wortlaut "mittel"/"hoch" (kategorial,
  keine reine Zahl) mit sichtbarer Hintergrundfarbe bei "hoch", für Regenwahrscheinlichkeit
  einen Prozentwert und für Sicht einen plausiblen Distanzwert (nicht die rohe Meter-Zahl ohne
  Einheit) — jeweils für mindestens eine Stunde mit einem Nicht-Null-Wert im Testzeitraum.
  - Test: Preset mit allen 3 neuen Metriken aktiv über echten Preset-Pfad senden, zugestellte
    Mail abrufen, mindestens eine Tabellenzelle je neuer Spalte auf plausiblen, nicht-leeren
    Inhalt mit Einheit/Label prüfen (kein Dateiinhalt-Check gegen Code — Beweis gegen die real
    zugestellte Mail).

- **AC-5:** Given eine beliebige Metrik-Auswahl inkl. der Voreinstellung "alle", When der
  Versand ausgelöst wird, Then enthält keine zugestellte Compare-Mail mehr eine
  "Wolken"-Spalte im Stundenverlauf — die Metrik ist vollständig entfernt, nicht nur
  standardmäßig abgewählt.
  - Test: Preset ohne explizite Auswahl (Default "alle") real versenden, zugestellte Mail
    abrufen, Header-Zeile der Stundentabelle auf Abwesenheit von "Wolken" prüfen.

- **AC-6:** Given eine E-Mail, deren Stundentabelle nur die Spalte "Zeit" ohne jede
  Wert-Spalte enthält (z.B. durch einen Rendering-Fehler oder eine zukünftige Regression),
  When `email_spec_validator.py` gegen diese Mail läuft, Then schlägt der Validator mit
  Exit-Code ungleich 0 fehl und benennt die fehlende Mindestspalten-Regel als Ursache.
  - Test: Reale, aus einer präparierten Test-Fixture gerenderte HTML-Mail mit nur "Zeit" als
    Spalte gegen den echten Validator-Lauf prüfen (Validator-Unit-Test mit echtem HTML-String,
    kein Mock des Validators selbst) — Exit-Code und Fehlermeldungstext verifizieren.

- **AC-7:** Given eine real zugestellte Compare-Mail mit einer gültigen Teilmenge von
  Stundenverlauf-Spalten (z.B. 4 von 9 plus "Zeit"), When `email_spec_validator.py` gegen diese
  Mail läuft, Then passiert die Mail das Gate (Exit-Code 0) — der Umbau von Exakt- auf
  Teilmengen-Prüfung darf gültige, aus diesem Feature resultierende Konfigurationen nicht
  fälschlich blocken.
  - Test: Echte, über Staging real versendete Compare-Mail mit Teilmengen-Konfiguration (aus
    AC-2) durch `uv run python3 .claude/hooks/email_spec_validator.py` laufen lassen, Exit-Code
    0 verifizieren.

- **AC-8:** Given ein Nutzer wählt die Metriken in einer vom Standard abweichenden
  UI-Reihenfolge aus (z.B. zuerst Sicht, dann Temp anklicken), When der Versand ausgelöst wird,
  Then erscheinen die gewählten Spalten in der zugestellten Mail trotzdem in der festen
  kanonischen Reihenfolge (Temp, Gef., Wind, Böen, Regen, UV, Gewitter, Regenwahrscheinlichkeit,
  Sicht) — die Klick-Reihenfolge im Frontend hat keinen Einfluss auf die Spaltenreihenfolge in
  der Mail.
  - Test: Preset mit `display_config.hourly_metrics=["visibility_m","temp_c"]` (bewusst in
    "falscher" Reihenfolge übergeben) real versenden, zugestellte Mail abrufen, Header-Zeile
    gegen `["Zeit","Temp","Sicht"]` (kanonische Reihenfolge, nicht Eingabereihenfolge) prüfen.

## Known Limitations

- **`compare_subscription.py`-Alt-Pfad bleibt unverändert:** CLI-only, kein aktiver
  App-Versandpfad. Entfernung ist eigenes Follow-up-Issue **#1131**, nicht Teil dieses Slices.
- **Übersichtstabelle (#1105) und Sektions-Toggles (#1107) nicht Teil dieses Slices:** Nur die
  Stundenverlauf-Spalten pro Ort-Sektion werden konfigurierbar, nicht die Metriken-x-Orte-Matrix
  oder das Ein-/Ausblenden ganzer Report-Elemente (Winner-Box, Tags, Warnungen, Matrix).
- **`top_n_details`/Anzahl-Orte-Filter (#1104) bleibt orthogonal:** Laut PO-Entscheidung
  (`comparison.py`-Docstring, 2026-07-08) zeigt die Mail aktuell immer alle Orte im
  Stundenverlauf; dieses Slice ändert daran nichts — es filtert nur die *Spalten* innerhalb
  jeder gezeigten Ort-Sektion, nicht die *Anzahl* der Sektionen.
- **Keine neue Daten-/Aggregations-Logik nötig:** `thunder_level`/`pop_pct`/`visibility_m`
  existieren bereits als normalisierte `ForecastDataPoint`-Attribute und werden von der
  `ComparisonEngine` bereits unverändert in `hourly_data` durchgereicht (genutzt vom
  Trip-Briefing-Pfad). Dieses Slice ist reine Rendering-/Konfigurations-Arbeit, keine
  Provider-/Normalizer-Änderung.
- **Frontend-Metrik-ID-Namen sind Implementierungsdetail:** Die exakten Strings in
  `FRONTEND_TO_HOURLY_METRIC_ID` (z.B. `"temp_c"` vs. `"t2m"`) sind kein Vertrag der Spec,
  solange Resolver und `compareHourlyMetricDefs.ts` konsistent zueinander sind und die 9
  kanonischen Renderer-Keys (`t2m_c`, `wind_chill_c`, `wind10m_kmh`, `gust_kmh`,
  `precip_1h_mm`, `uv_index`, `thunder_level`, `pop_pct`, `visibility_m`) korrekt erreichen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dieses Slice wiederholt 1:1 das bereits etablierte, dokumentierte
  Resolver-Pattern aus #1104 (`resolve_enabled_metrics`/`_visible_metrics`) für ein zweites,
  paralleles Vokabular (Stunden-Rohwerte statt Übersicht-Aggregate). Es führt keine neue
  Architektur-Komponente, keine neue Abhängigkeit und keinen neuen Persistenz-Mechanismus ein —
  `display_config` bleibt das bestehende untypisierte dict, nur um einen weiteren additiven Key
  (`hourly_metrics`) erweitert, exakt wie `top_n`/`active_metrics` zuvor. Die 3 neuen
  Metrik-Typen (kategorial/Prozent/Meter) sind Formatierungs-Detail innerhalb des bestehenden
  Zellen-Rendering-Ansatzes, keine neue Datenschicht.

## Changelog

- 2026-07-08: Initial spec created (Issue #1106, Slice C von #1094/#1092 Teil B).
- 2026-07-08: Implementiert und live. `compare_hourly_metric_ids.py` (Resolver),
  `HOUR_METRICS`-Umbau in `compare_html.py`, Checkbox-UI in `Step5Versand.svelte`,
  Validator-Umbau auf Teilmenge-mit-Reihenfolge in `email_spec_validator.py`.
  Adversary-Fix-Runde 2: Cross-Location-Konsistenz ergänzt (eine Config gilt
  mail-weit für alle Orte, nicht pro Ort-Tabelle einzeln geprüft). Siehe
  `docs/reference/mail_validators.md` §1 für den aktualisierten Validator-Vertrag.
