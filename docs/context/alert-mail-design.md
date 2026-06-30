# Context: Alert-Nachricht — generisches Render-System (#914 / Issue 27)

## Request Summary
Ein ausgelöster Abweichungs-Alert (Wert hat seit dem letzten Briefing eine
Schwelle überschritten) soll generisch in vier Kanäle gerendert werden — Betreff ·
E-Mail · Telegram · SMS — rein rechnerisch (Pfeil/Δ%/über-unter), ohne Deutung der
Wetterlage. Render-Logik **einmal** im Backend (Tech-Lead-Entscheidung, siehe
#914-Kommentar); Frontend-Vorschau über Endpunkt statt zweitem TS-Renderer.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `src/app/models.py` (≈409–431) | `WeatherChange`-DTO — faktisch schon `AlertEvent` (metric/old/new/threshold/severity/direction/segment_id). Wird angereichert (km-Spanne, cmp). |
| `src/app/metric_catalog.py` | Kanonische Metrik-Registry (`MetricDefinition`, `compact_label`, unit). **Ziel-Single-Source** für neue Felder `sms_code`, `decimals`, `cmp`. |
| `src/output/renderers/email/alert_compact.py` | Heutiger E-Mail-Alert-Renderer `render_deviation_alert()` — wird durch neues Modul ersetzt/abgelöst. |
| `src/formatters/sms_trip.py` (43–52, 233–269) | `format_alert_sms()` + `SMS_SYMBOL_BY_METRIC` (doppelte SMS-Tabelle — wird entfernt). |
| `src/outputs/telegram.py` (50–96) | Telegram-Versand (subject/body). |
| `src/outputs/email.py` | E-Mail-Versand + `X-GZ-Mail-Type`-Header. |
| `src/outputs/radar_alert.py` | **GELÖSCHT (Issue #919)** — auf kanonischen Alert-Renderer migriert; `OnsetEvent` in `src/output/renderers/alert/model.py`. |
| `src/services/trip_alert.py` (848–931 `_send_alert`, Betreff-Bau) | Orchestrierung Multi-Kanal-Versand; Betreff heute ad-hoc. |
| `src/services/weather_change_detection.py` | Erzeugt `WeatherChange`-Liste (delta-only für Alerts). |
| `src/output/renderers/email/helpers.py` (737–773) | `build_segment_label()` — km-Spanne (start_km/end_km) schon vorhanden. |
| `api/routers/config.py` (30–51) | `/api/metrics` — exponiert Katalog-Subset ans Frontend; muss `sms_code`/`decimals`/`cmp` ergänzen. |
| `frontend/.../alerts-tab/AlertPreviewCard.svelte` | Holt fertiges Alert-HTML via `POST /api/trips/{id}/alert-preview` — **das Zielmuster** für die 4-Kanal-Vorschau. |
| `frontend/.../trip-detail/ChannelFidelitySMS.svelte` (14–51) | Hardcodierte `SMS_TOK` + `smsRender()` (dritte SMS-Code-Kopie — soll künftig Backend-gespeist sein). |

## Existing Patterns
- **Backend rendert, Frontend zeigt**: `alert-preview`-Endpunkt liefert fertiges HTML;
  Svelte rendert nur ein `<iframe srcdoc>`. → auf alle 4 Kanäle erweiterbar.
- **Reine Builder-Funktionen**: `radar_alert.py` war Vorbild für seiteneffektfreie Renderer — seit Issue #919 gelöscht; der Onset-Pfad läuft jetzt durch denselben kanonischen Renderer (`AlertMessage(OnsetEvent(...))`).
- **Katalog als Single Source + `/api/metrics`-Sync**: Frontend zieht Metrik-Stammdaten
  schon vom Backend (kein hartcodierter Zweit-Katalog — bis auf Compare-Wizard-Reste).
- **Severity-Sortierung** und **km-Union** existieren konzeptionell schon (severity in
  `WeatherChange`, km in `build_segment_label`).

## Dependencies
- **Upstream**: `WeatherChange`/`weather_change_detection`, `metric_catalog`,
  `alert_state` (Wiederholungsfilter), Segment-Daten (start_km/end_km).
- **Downstream**: `trip_alert._send_alert` (Versand), `email/telegram/sms`-Outputs,
  `alert-preview`-Endpunkt + Svelte-Vorschau, `/api/metrics`-Konsumenten (Wizard/Editor).

## Existing Specs
- Bezug: #687 (Alerts-Tab/Schwellen), #14 (Output-Layout/Registry), #816/#817/#821/#822
  (Abweichungs-/Radar-Alert-Kern). Mail-Validatoren: `docs/reference/mail_validators.md`.

## Risks & Considerations
- **3-fach widersprüchliche SMS-Codes** (Katalog vs. `SMS_SYMBOL_BY_METRIC` vs. Frontend);
  Konsolidierung muss bestehende SMS-Token-Bedeutung erhalten (Regress-Gefahr bei live
  versendeten SMS).
- **Mail-Gate/Validatoren**: Renderer-Änderung triggert `renderer_mail_gate.py` (Modus-
  Matrix-Test + `briefing_mail_validator`). Hier zusätzlich Alert-Pfad — passendes Gate
  prüfen (Abweichungs-Alert hat eigenen Validator-Pfad). KEIN falscher Validator.
- **Datenmodell-Schema**: `WeatherChange` ist persistenz-/alert_state-nah — Felder nur
  **additiv** ergänzen (Read-Modify-Write), keine Brüche an `alert_state`-JSON.
- **Edge Cases** (Issue): Division durch 0 bei value_from=0 (kein %), gemischte
  Richtungen, km-Union über Segmente, SMS-Überlauf `+k`, Metrik ohne SMS-Code = Fehler.
- **Generisch über ALLE alert-fähigen Metriken** testen (nicht nur CAPE) — AC-Pflicht.
- **Out of scope**: Radar-/Nowcast-Sofort-Alert (eigenes Schema), Mehrsprachigkeit,
  Push, Alert-History.

## Analysis

### Type
Feature (großes Render-/Refactoring-Feature mit Datenmodell-Erweiterung).

### Datenverfügbarkeit pro Issue-Feld (entscheidend für die ACs)
| Feld | Heute vorhanden? | Quelle / nötige Aktion |
|------|------------------|------------------------|
| `threshold` | ✅ | `WeatherChange.threshold` |
| `km_from` / `km_to` | ✅ indirekt | `segment.start_point/end_point.distance_from_start_km` — Renderer braucht die `segments`-Liste (hat sie heute schon) |
| `direction` (↑/↓) | ✅ | `WeatherChange.direction` (increase/decrease) |
| `cmp` (über/unter Schwelle) | ⚠️ verstreut | heute hartcodiert in `weather_change_detection._ALERT_METRIC_COMPARISON` → **zentralisieren** in `metric_catalog` |
| `occurred_at` (Stunde, SMS `@hh`) | ❌ fehlt komplett | **neu**: Peak-Stunde aus `ForecastDataPoint`-Liste berechnen, additiv an `WeatherChange` hängen (optional/best-effort; `@hh` ist laut Issue optional) |
| `sms_code` / `decimals` | ❌ im Katalog | **neu** in `MetricDefinition`; SMS-Code-Pflicht (CP/SN/SL/VS/HU) |

Betreff heute statisch (`trip_alert.py:883` „Wetter ändert sich seit dem Briefing") → wird informativ neu gebaut.

### Empfohlene Slice-Aufteilung (LoC-Limit 250/Workflow, Gate-Reviewbarkeit)
- **Slice 1 — Fundament (Registry + Datenmodell):** `sms_code`/`decimals`/`cmp` als
  Single Source in `metric_catalog`; doppelte `SMS_SYMBOL_BY_METRIC` entfernen;
  `_ALERT_METRIC_COMPARISON` in Katalog überführen; `occurred_at` additiv an
  `WeatherChange` + Peak-Stunde berechnen; `/api/metrics` um die Felder erweitern.
  *Geringes Außenrisiko, baut das Fundament für alles Weitere.*
- **Slice 2 — Renderer (4 Kanäle + Betreff):** neues Modul `src/output/renderers/alert/`
  mit 4 reinen Funktionen + gemeinsamen Helfern (arrow/Δ%/over_thr/severity/km_span);
  Einbindung in `trip_alert._send_alert`. *Sichtbare Format-Änderung, durch Mail-Gate
  abgesichert.*
- **Slice 3 — Vorschau:** `alert-preview`-Endpunkt auf alle 4 Kanäle erweitern; Svelte
  zeigt fertige Texte, hartcodiertes `SMS_TOK` entfällt.

### Scope Assessment
- Dateien gesamt: ~12–15; geschätzt +600…900 LoC über alle 3 Slices.
- Pro Slice: ~150–300 LoC → Slice 2 ggf. knapp am 250-Limit (Override evtl. nötig → PO).
- Risk Level: **MITTEL** — `occurred_at` berührt die Detektionslogik (Snapshot-/
  alert_state-nah); Renderer-Änderung triggert Mail-Gate; SMS-Code-Konsolidierung hat
  Live-SMS-Regress-Potenzial. Alles additiv/Read-Modify-Write haltbar.

### Open Questions (PO)
- [ ] Aufteilung in 3 Slices (empfohlen) oder ein großer Workflow (braucht LoC-Override)?
