# Context: fix-1094-compare-config

## Request Summary
Der Compare-Editor-Umbau (Epic #677/#438, Ablösung des Legacy-`SubscriptionForm`) hat mehrere Konfigurationsmöglichkeiten des Orts-Vergleichs entfernt bzw. wirkungslos gemacht. Issue #1094 (Teil B von #1092) fordert, diese 5 Punkte wiederherzustellen und in der E-Mail-Ausgabe **wirksam** zu machen.

## Die 5 Bug-Punkte → Fundstelle

| Punkt | Forderung | Ist-Zustand (Fundort) |
|-------|-----------|-----------------------|
| **2** | „Schneehöhe" soll weg / nicht wählbar | `snow_depth` an **zwei** Stellen wählbar: Frontend `compareMetricDefs.ts:30` (`SNOW_DEPTH`, im „＋ Metrik"-Menü `Step3Idealwerte.svelte:141`, Default im WINTERSPORT-Profil `compareMetricDefs.ts:65`) **und** Katalog `metric_catalog.py:401` (kein `selectable=False`, anders als `confidence` `:228`) → erscheint auch über `/api/metrics` im Layout-Tab |
| **3** | Metriken in E-Mail konfigurierbar | Matrix-Metriken **hardcodiert** über `CE_PROFILES` (`compare_html.py:37-54`); `enabled_metrics`-Filter existiert (`:432-434`), greift aber **nicht**: ID-Mismatch — `display_config.metrics[].metric_id` = Katalog-IDs (`snow_depth`, `wind`…), CE_PROFILES nutzt andere IDs (`snow_depth_cm`, `wind_max`…) → Filter matcht nie |
| **4** | Elemente/Sektionen konfigurierbar | Sektions-Reihenfolge/-Präsenz **fest** im `html_doc`-Template (`compare_html.py:661-682`: winner, tags, warnings, alerts, matrix, hourly). Kein `report_config`-Äquivalent wie beim Trip |
| **5** | Anzahl Orte im Stundenverlauf | Renderer **respektiert** `top_n` (`compare_html.py:531-537`), aber **UI-Control fehlt** (war in `SubscriptionForm.svelte:201-213`, jetzt tot). `ComparePreset`-DTO (`types.ts:478-496`) hat **kein** `top_n`-Feld |
| **6** | Metriken im Stundenverlauf konfigurierbar | Stundenverlauf-Metriken **hardcodiert** Temp/Wind/Wolken (`compare_html.py:547-549`, Header `:566-569`). Kein DTO-Feld, keine UI |

## Related Files

### Frontend — Compare-Editor
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareEditor.svelte` | 5-Tab-Shell (Vergleich/Orte/Idealwerte/Layout/Versand) |
| `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte` | Metrik-Auswahl (add/remove) + Idealwerte — hier hängt Schneehöhe |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | Pro-Kanal Spalte-vs-Detailzeile (`:168` nutzt `/api/metrics` + Bucket-Muster) |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | Kanäle, Horizont, Zeitfenster, Versandzeit |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | `ALL_METRICS`, `SNOW_DEPTH` (`:30`), Profil-Defaults |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | State — enthält toten `includeHourly`/`topN` (`:41-42`), nicht im Preset-Save-Pfad |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Preset-Save (`display_config`: region, ideal_ranges, channel_layouts, active_metrics) |
| `frontend/src/lib/types.ts` | `ComparePreset` (`:478-496`) — **kein** `top_n`/`include_hourly` |
| `frontend/src/lib/components/SubscriptionForm.svelte` | **Tote** Legacy-Quelle der verlorenen Controls (`top_n` `:201`, `include_hourly` `:215`) |

### Backend — Renderer + Modell
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py` | **Aktiver** HTML-Renderer. Hardcodierte Matrix/Hourly-Metriken, Sektionen |
| `src/services/compare_subscription.py` | Service — reicht `top_n`, `display_config`, `activity_profile` durch (`:104-141`) |
| `src/output/renderers/comparison.py` | `render_comparison_html` ist Legacy/tot für E-Mail; `render_comparison_text` aktiv |
| `src/app/user.py` | `CompareSubscription` (`:116-144`, hat `top_n`/`include_hourly`/`display_config`), `LocationResult` (`:147`) |
| `src/app/metric_catalog.py` | `snow_depth` (`:401`), `get_all_metrics()` selectable-Filter (`:442`), `confidence` selectable=False-Muster (`:228`) |

### Backend/Frontend — Trip-VORBILD (Muster zum Spiegeln)
| File | Relevance |
|------|-----------|
| `src/app/models.py` | `UnifiedWeatherDisplayConfig` (`:542`), `MetricConfig` (`:482`), `TripReportConfig` (`:692-747` Element-Toggles) |
| `src/output/renderers/trip_report.py` | Respektiert `display_config` (Metriken, `:97/146`) + `report_config` (Element-Toggles, `:128-168`) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Metrik-Editor-Orchestrierung, `/api/metrics` (`:226`) |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | „E-Mail-Inhalt"-Karte = Element/Sektions-Toggles (`:442-521`) |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Bucket-/Payload-Logik |
| `api/routers/config.py` | `GET /metrics` (`:30-55`) → selectable-gefiltert |

## Existing Patterns (Trip = Referenz)
Trip nutzt 3 entkoppelte Schichten, die Compare spiegeln kann:
1. **Katalog-Quelle:** `GET /api/metrics` (selectable-gefiltert) → gruppiert nach Kategorie.
2. **Zwei Persistenz-Blobs:** `display_config` (Metrik-Auswahl/Reihenfolge/Format, `MetricConfig`-Liste) + `report_config` (Element-Toggles, `TripReportConfig`).
3. **Reine Logik + UI:** `metricsEditor.ts` + `WeatherMetricsTab`/`EditReportConfigSection`.

Compare hat Schicht 1 im Layout-Tab bereits, aber Schicht-2-Element-Toggles (`report_config`-Pendant) fehlen, und der Renderer honoriert `display_config` wegen des ID-Mismatches nicht.

## Dependencies
- **Upstream:** `/api/metrics` (Katalog), `CE_PROFILES` (Aktivitätsprofil-Metrikzuordnung), `LocationResult`-Attributnamen (`snow_depth_cm`, `wind_max`, …)
- **Downstream:** Compare-E-Mail (`X-GZ-Mail-Type: compare`), Telegram/SMS-Compare-Pfade, Winner-Box/Matrix-Score (`comparison_scoring.py`)

## Existing Specs / Referenzen
- `docs/features/epic-438-compare-wizard.md` — Wizard-Steps
- `docs/reference/mail_validators.md` — `email_spec_validator.py` (Compare-Pfad)
- Memory: `project_issue_1092_ortsvergleich_split.md`, `project_epic_677_compare_editor.md`, `project_issue_710` (confidence selectable=false Muster)

## Risks & Considerations / offene Fragen für Analyse-Phase
1. **DTO-Doppelung:** Backend `CompareSubscription` (`user.py`) trägt `top_n`/`include_hourly`, Frontend `ComparePreset`/`/api/compare/presets` **nicht**. Die Mapping-Kette Preset↔Subscription muss in Analyse geklärt werden — sonst wird ein neues UI-Feld persistiert, kommt aber nie im Renderer an.
2. **Punkt 2 (Schneehöhe) — Entscheidung PO nötig:** komplett aus Compare entfernen ODER nur aus Default/Menü, aber für WINTERSPORT-Profil behalten? „weg **bzw.** nicht wählbar" ist mehrdeutig. Betrifft 2 Orte (compareMetricDefs.ts + metric_catalog selectable).
3. **Punkt 3 ID-Mismatch:** Fix muss CE_PROFILES-IDs ↔ Katalog-IDs mappen, sonst filtert `enabled_metrics` weiter falsch.
4. **Punkte 4 & 6 = echte Neubauten** (Element-Toggles + Hourly-Metrik-Auswahl existieren nirgends), nicht bloß „Wiederherstellen" — DTO-Erweiterung + Renderer-Auswertung nötig.
5. **Regression-Verifikation:** Jeder der 5 Punkte muss in **echt zugestellter Staging-Compare-Mail** (`email_spec_validator.py`) nachgewiesen werden — das war die Lücke, die #1094 entstehen ließ.
6. **Schema-Erweiterung** an `CompareSubscription`/`ComparePreset` → Read-Modify-Write-Merge Pflicht (Bestandsdaten!), Snapshot-Hook `data_schema_backup.py` greift bei `user.py`-Edits.

## Analysis

### Type
Bug / Regression — mit substanziellem Neubau-Anteil (P4, P6).

### Kern-Root-Cause (tiefer als der Bug-Titel)
Der Bug ist **nicht** primär der Renderer, sondern der **Versandpfad**. Es existieren zwei getrennte, nicht verbundene Systeme:

- **Preset-Pfad (was das UI speichert + der Versand nutzt):** UI → `POST/PUT /api/compare/presets` → **Go-Store** → `data/users/<id>/compare_presets.json`. Versand über `send_one_compare_preset` (`scheduler_dispatch_service.py:198-260`) liest daraus **nur** Basisfelder und ruft `render_compare_email(result, profile=profile)` (`:250`) — **ohne** `top_n_details`/`enabled_metrics`. `display_config` wird hier **nie** gelesen. → Alle im Editor gewählten Metriken/Layouts versickern folgenlos.
- **Subscription-Pfad (wertet Config aus, wird vom UI NICHT befüllt):** `compare_subscriptions.json` → `run_comparison_for_subscription` (`compare_subscription.py:102-145`). Nur die **CLI** ruft das auf. Für die echte Mail tot.

Kein Adapter konvertiert Preset → Subscription. Die beiden teilen nur `render_compare_email`.

### Vier inkompatible Metrik-Vokabulare (braucht kanonischen Resolver)
| Ebene | Beispiel-IDs | Ort |
|-------|--------------|-----|
| 1 Katalog `/api/metrics` | `snow_depth`, `wind`, `cloud_total` | `metric_catalog.py` |
| 2 Renderer/CE_PROFILES/LocationResult | `snow_depth_cm`, `wind_max`, `cloud_avg` | `compare_html.py:37-54` |
| 3 Frontend `active_metrics` | `snow_depth_cm`, `wind_max_kmh`, `cloud_avg_pct` | `compareMetricDefs.ts:31-40` |
| 4 Step4Layout Channel-Layout | Katalog-IDs (Ebene 1) | `Step4Layout.svelte` |

Der `enabled_metrics`-Filter (`compare_html.py:432`) matcht gegen keines stabil. → **Ein geteilter ID-Resolver ist Voraussetzung** für P3 und P6.

### Punkt-für-Punkt-Ansatz
- **P2 Schneehöhe:** PO-Entscheidung — NICHT entfernen, konfigurierbar wie alle. 0 Renderer-LoC; fällt automatisch aus P3 ab (abwählbar sobald Config wirkt). Profil = Seed (Trip-Muster).
- **P3 Matrix-Metriken:** Resolver + `send_one_compare_preset` liest `active_metrics` → `enabled_metrics`. CE_PROFILES bleibt Reihenfolge-/Default-Preset. **Winner/Score unberührt** (`comparison_scoring.py` referenziert CE_PROFILES nicht — verifiziert).
- **P4 Sektionen:** neuer schlanker `CompareReportConfig` (Bool-Toggles) analog `TripReportConfig`; feste `html_doc`-Slots → `if`-Blöcke. **Größter Brocken + Validator-Konflikt (s.u.).**
- **P5 Anzahl Orte Hourly:** Renderer kann es (`top_n_details`). Fehlt: Feld (empf. `display_config.top_n`, vermeidet Go-Struct-Migration), Wiring, UI-Control, DTO.
- **P6 Hourly-Metriken:** `_render_hourly_section` (`:547-549`) parametrisieren mit `hourly_metrics`-Liste (Resolver → `ForecastDataPoint`-Attribute). Echter Neubau.

### Risiken
- **Bestandsdaten (hoch):** neue Felder additiv + rückwärtskompatible Defaults (alle Metriken an, top_n=3); Round-Trip-Spread im Save nicht brechen.
- **Mail-Validator (hoch, nur P4):** `email_spec_validator.py:236-240` erzwingt Pflicht-Sektionen (Zeitfenster/Hourly/Empfehlung). P4-Toggles, die eine Sektion abschalten, lassen den Post-Send-Validator scheitern → Validator muss config-bewusst werden. Zusätzlich Verdacht, dass er gegen den toten `comparison.py`-Renderer zielt — separat prüfen.
- **Telegram/SMS-Compare (mittel):** Text-Renderer teilt `enabled_metrics`/`top_n` — mittesten.
- **Zwei-Backend-Drift (mittel):** `display_config`-Blob-Weg (Go reicht `map[string]interface{}` transparent durch) vermeidet Go-Struct-/Store-Migration.
- **Doppel-Renderer:** nur `compare_html.py` (aktiv) anfassen, `comparison.py` nicht mitpflegen.

### Scope Assessment
- Geschätzt **450–690 LoC** über Backend + Frontend + Go + Tests → **sprengt 250-LoC-Limit klar, nicht als EIN Workflow machbar.**
- Empfohlene Zerlegung in 4 vertikale, je testbare Slices (≤250 LoC):
  - **WF-A Fundament:** ID-Resolver + Wiring in `send_one_compare_preset` + **P5 (top_n)** als erster sichtbarer Beweis. (~120–190 LoC)
  - **WF-B:** P3 (Matrix-Metriken wirksam) + P2 (Schneehöhe abwählbar).
  - **WF-C:** P6 (Hourly-Metriken).
  - **WF-D:** P4 (Sektions-Toggles + Validator config-bewusst).
- **Folge-Scope bewusst ausklammern:** Metriken ohne `ComparisonResult`-Feld (precip/visibility/uv/thunder) — brauchen Engine+Scoring, gehören nicht in den Regressions-Fix.

### Reihenfolge (zwingend)
WF-A blockiert B/C/D — ohne die Verdrahtung wirkt keine UI-Änderung in der echten Mail. Innerhalb jedes Slice: **Config-Feld → Wiring im Sende-Service → Renderer → UI** (Backend-Wiring vor UI).

### Open Questions
- [ ] **PO-Slicing-Entscheidung:** #1094 in 4 Sub-Issues zerlegen (empfohlen) vs. ein Workflow mit LoC-Override?
- [ ] Nebenbefund-Issue für Validator-Härtung (config-bewusste Pflicht-Sektionen) + Verdacht „Validator zielt auf toten Renderer".
