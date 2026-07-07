# Context: 1087 — Amtliche Warnungen in Trip-Briefings + Trip-Toggle

## Request Summary
Amtliche Warnungen (Official Alerts) sollen querschnittlich auch in Trip-Briefing-Mails
erscheinen (heute nur im Orts-Vergleich), inkl. der bestehenden FR-Quellen aus #1033
(Vigilance, Météo des forêts, Massiv-Sperren). Dazu: **eine gemeinsame Warn-Render-Komponente**
(kein Copy-Paste, #1073 Punkt 6), das `official_alerts`-Datenfeld auf eine allgemeinere
Orts-/Etappen-Abstraktion heben, und ein Trip-Toggle `official_alerts_enabled` (Default `true`,
Pointer-Muster, Read-Modify-Write-Merge) analog #1040.

## Related Files

### Datenfeld & Fetch (bestehend, konsum-neutral)
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/base.py:45` | `get_official_alerts_for_location(lat, lon)` — reine Fkt Koordinaten→Warnliste, fail-soft pro Quelle, wirft nie. Registry `_REGISTERED_SOURCES`. |
| `src/services/official_alerts/models.py:14` | `OfficialAlert` (frozen): `source, hazard, level (1=grün…4=rot), label, valid_from, valid_to, url, region_label`. |
| `src/app/user.py:174` | `LocationResult.official_alerts: List[OfficialAlert]` — **Compare-only** DTO-Feld (das ist die Abstraktion, die gehoben werden soll). |
| `src/services/comparison_engine.py:187-205` | Fetch-Gating im Compare: bei `official_alerts_enabled=True` → fetch, sonst `[]` (strukturell kein Fetch). |

### Compare-Renderer (Vorbild für gemeinsame Komponente — ZWEI Darstellungen!)
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py:144` | `_render_official_alerts_block(locations)` — **HTML-Badges** (div, kein table), Level→Farbe (1-2 G_SUCCESS, 3 G_WARNING, 4+ G_DANGER). Eingehängt bei `:627`/`:676`. **Gate-relevant.** |
| `src/output/renderers/comparison.py:418-420` | **Plain-Text/SMS**-Darstellung: `for alert in loc.official_alerts: lines.append("⚠️ Amtliche Warnung: {label}")`. **NICHT gate-relevant.** |

### Trip-Briefing-Mail-Pfad (aktiver Pfad = Segment, NICHT TripForecastService!)
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:541` | `_send_trip_report_outcome()` — baut `segments` (`:572`), fetch weather (`:608`), `_build_trip_report_request` (`:787`), `send_trip_report` (`:743`). **Idealer Fetch-Punkt** nach `:608` pro `seg.segment.start_point.lat/lon`. |
| `src/services/notification_service.py:~55-88` | `TripReportRequest`-DTO — **kein** Alert-Feld; hier bzw. an `format_email` (`:186`) käme `official_alerts` hinzu. |
| `src/output/renderers/trip_report.py:56` | `TripReportFormatter.format_email()` → `render_email(...)` (`:142`). **Gate-relevant.** |
| `src/output/renderers/email/__init__.py:32` | `render_email()` — Verteiler: compact (`:76`, text-only) vs. html (`:106`) + plain (`:130`). **Gate-relevant.** |
| `src/output/renderers/email/html.py:729` | `render_html()` — Body-Assemblierung `:1489-1508` (Einhängepunkt globaler Warn-Block zw. `{changes_html}` und `{segments_html}`); Segment-Schleife `:896-1020` (`seg.start_point.lat/lon`). **Gate-relevant.** |
| `src/output/renderers/email/plain.py` | Plain-Text-Trip-Mail. **Gate-relevant.** |

### Trip-Toggle (Go + Python + Frontend), Vorbild #1040
| File | Relevance |
|------|-----------|
| `internal/model/trip.go:88-106` | `Trip`-Struct; Pointer-bool-Muster vorhanden (`Waypoint.Confirmed *bool` :76). Neues Feld: `OfficialAlertsEnabled *bool` nach :105. |
| `internal/handler/trip.go:140-249` | `UpdateTripHandler` mit `tripUpdateRequest`-DTO (Pointer-Felder), Merge `if req.X != nil { existing.X = req.X }` (~:208). |
| `internal/model/compare_preset.go:34-38` | #1040-Vorbild: `OfficialAlertsEnabled *bool json:"...,omitempty"`. |
| `internal/handler/compare_preset.go:214-219` | #1040-Merge-Muster (nil = Feld fehlte, false gültig). |
| `src/app/trip.py:168-200` | Python `Trip`-Dataclass; neues Feld `official_alerts_enabled: Optional[bool] = None`. `Waypoint.lat/lon` :73-74. |
| `src/app/loader.py:412-430 / ~1078` | Load (`data.get(...)`) + konditionale Serialisierung (`is not None`, damit `False` persistiert). |
| `frontend/src/lib/types.ts:263-281` | `interface Trip` — neues `official_alerts_enabled?: boolean`. (#1040-Feld bei `:495` in `ComparePreset`.) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte:52-68` | Aktiver Alerts-Tab, `buildSaveFn` `api.put('/api/trips/${id}', {...})` — Einbauort Toggle. |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte:110-117` | #1040-Toggle-UI (`ChannelToggle`) — direkte Vorlage. |

## Existing Patterns
- **Pointer-bool-Toggle (#1040):** `*bool` + `omitempty`; nil=Feld fehlte (Altdaten), Default `true` beim Lesen interpretiert, `false` bewusst gesetzt. Merge nur wenn Request-Feld nicht-nil.
- **Fetch-Gating:** `if enabled: fetch else []` (strukturell kein Fetch, nicht nur ausblenden). Vorbild `comparison_engine.py:187`.
- **Fail-soft Alert-Fetch:** `get_official_alerts_for_location` wirft nie; Aufrufer additiv im Erfolgszweig.
- **Read-Modify-Write-Merge:** BUG-DATALOSS-GR221 — Trip-Save nie Replace.
- **Zwei Render-Formate:** HTML-Badges (compare_html) + Plain-Zeilen (comparison.py). Gemeinsame Komponente muss beide liefern (HTML + Plain/SMS-Parität, AC-2).

## Dependencies
- **Upstream:** `official_alerts`-Registry (alle #1033-Quellen + kommende AT/IT #1085/#1086 hängen dort → Anzapfen bringt automatisch alle).
- **Downstream:** Trip-Briefing-Mail (Scheduler + Manual-Send), Compare-Renderer (Regression-Schutz), Trip-Editor-Frontend.

## Existing Specs / Referenzen
- Issue #1040 (Compare-Toggle) — direkte Vorlage für Toggle-Full-Stack.
- Issue #1033 / #1034 — Alert-Fundament + Compare-Darstellung.
- Epic #1073 Punkt 2 (querschnittlich) + Punkt 6 (kein Copy-Paste).
- Tests-Vorbilder: `tests/tdd/test_issue_1040_alerts_toggle.py`, `internal/handler/compare_preset_official_alerts_test.go`.

## Risks & Considerations
- **R1 — Renderer-Mail-Gate (#811):** `email/html.py`, `email/plain.py`, `trip_report.py` sind gate-relevant → Commit blockt bis `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py` erfolgreich. `comparison.py` ist NICHT gate-relevant.
- **R2 — Falscher Datenpfad:** Trip-Briefing nutzt Segment-Pfad (`SegmentWeatherData`/`TripReportRequest`), NICHT `TripForecastService`/`TripForecastResult`. Alert-Feld muss an `TripReportRequest`/Segment andocken.
- **R3 — Gemeinsamer Renderer, kein Duplikat (AC-2):** Extraktion muss von Compare UND Trip genutzt werden; Compare-Badge muss unverändert bleiben (Regression). Zielort der geteilten Komponente sollte gate-bewusst gewählt werden (z.B. `src/output/renderers/alert/` — bereits gate-relevant, oder ein Helper).
- **R4 — Datenverlust beim Toggle-Save:** Read-Modify-Write mit zwei verschiedenen Nutzern testen (AC-3, Multi-User-Pflicht).
- **R5 — Two-format-Parität:** SMS-Trip-Renderer (`sms_trip.py`) ggf. auch betroffen (Plain/SMS-Parität) — im Scope prüfen.
- **R6 — compact-Modus:** `render_compact()` ist text-only (keine HTML-Tabellen) — Warn-Block auch dort konsistent liefern.

---

## Analysis

### Type
Feature (querschnittliche Verfügbarkeit + Toggle).

### Design-Entscheidungen (Plan/Sonnet-Bewertung)

**(a) Gemeinsame Render-Komponente — Zielort:**
Neues **gate-relevantes** Modul `src/output/renderers/alert/official_alerts.py` mit
`render_official_alerts_html(entries)` + `render_official_alerts_plain(entries)`, Input generisch
`list[tuple[str, list[OfficialAlert]]]`. Die HTML-Funktion ist der **verbatim verschobene** Rumpf
aus `compare_html.py:151-169` (Level→Farbe identisch) → Compare-Badge byte-gleich (AC-2).
NICHT `email/helpers.py` (falscher „email"-Scope, da `comparison.py` nicht zur Email-Familie
gehört und nicht aus `email/*` importieren soll). Dedupe/Aggregation als geteilter Helper im
selben Modul: `collect_trip_alert_entries(segments)`, gruppiert nach `region_label`, **ein** Block
pro Briefing.

**(b) Datenfeld heben — Zielobjekt:**
`official_alerts: list[OfficialAlert] = field(default_factory=list)` auf **`SegmentWeatherData`**
(`models.py:386`, nicht-frozen, additiv → kein Roundtrip-Bruch), symmetrisch zu
`LocationResult.official_alerts`. Entscheidender Vorteil: `segments` wird **bereits** an alle
Renderer durchgereicht (`render_email:35` → `render_html/plain/compact`, `SMSTripFormatter`) →
**null neue kwargs** in der Render-Kette. Alternative (Feld auf `TripReportRequest`) verworfen —
zu viel Signatur-Churn. Die „allgemeinere Abstraktion" ist die Tupel-Schnittstelle am Render-Rand,
keine gemeinsame Basisklasse.

**(c) Trip-Fetch-Ort:**
`trip_report_scheduler.py::_send_trip_report_outcome`, nach `_fetch_weather` (`:608`), vor
`_build_trip_report_request` (`:725`). Pro **eindeutigem** Segment-`start_point.(lat,lon)`
(Dedupe über gerundete Koordinaten), Ergebnis je `SegmentWeatherData.official_alerts`. Gate:
`if trip.official_alerts_enabled is not False:` (strukturell kein Fetch bei explizit `False`).
Fail-soft try/except um die Schleife (analog `comparison_engine.py:190-198`), Error-Segmente
(`has_error`) überspringen.

**(d) Format-Entscheidungen:**
- **Compact:** Warnungen als kurze Textzeile aufnehmen (Sicherheitsrelevanz — sonst funktionaler Verlust).
- **SMS (`sms_trip.py`):** bewusst **ausschließen** (160-Zeichen-Limit) — keine sinnvolle Parität, dokumentieren.
- **Compare-Plain (`comparison.py:418`):** Format `⚠️ Amtliche Warnung: {label}` exakt reproduzieren (NICHT gate-abgesichert → dedizierter Test).

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/alert/official_alerts.py` | CREATE | Shared HTML+Plain-Renderer + `collect_trip_alert_entries` Dedupe (~60) |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_render_official_alerts_block` → Thin-Wrapper (~+5/-15) |
| `src/output/renderers/comparison.py` | MODIFY | Plain-Zeilen → Shared-Call (~+3/-2) |
| `src/app/models.py` | MODIFY | `SegmentWeatherData.official_alerts` Feld (~+2) |
| `src/services/trip_report_scheduler.py` | MODIFY | Fetch-Schleife + Dedupe + fail-soft + Toggle-Gate (~+24) |
| `src/output/renderers/email/html.py` | MODIFY | entries + `{official_alerts_html}` Platzhalter (~+14) |
| `src/output/renderers/email/plain.py` | MODIFY | entries + append (~+8) |
| `src/output/renderers/email/compact.py` | MODIFY | Textzeile (~+8) |
| `internal/model/trip.go` | MODIFY | `OfficialAlertsEnabled *bool` (~+1) |
| `internal/handler/trip.go` | MODIFY | Merge `if req.X != nil` (~+4) |
| `src/app/trip.py` | MODIFY | `official_alerts_enabled: Optional[bool] = None` (~+1) |
| `src/app/loader.py` | MODIFY | load + save (`is not None`) (~+4) |
| `frontend/src/lib/types.ts` | MODIFY | `Trip`-Interface Feld (~+1) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | MODIFY | Toggle-Control (Vorlage `Step5Versand.svelte:110-117`) (~+15) |

### Scope Assessment
- Files: 14 (1 CREATE, 13 MODIFY), 3 Sprachen (Python, Go, Svelte)
- Estimated src LoC: ~150–170 (unter 250-Limit; TDD-Tests separat, könnten Gesamtdelta an die Grenze bringen → dann Split B (Toggle) erwägen)
- Risk Level: **HIGH** (Mail-Gate, Multi-Format, Cross-Domain-Refactoring)

### Implementierungs-Reihenfolge
1. Shared-Modul `alert/official_alerts.py` (HTML = exakter Move) + Golden-Test auf Compare-HTML → AC-2 vor Compare-Umstellung verifiziert.
2. Compare umstellen (`compare_html.py` Wrapper, `comparison.py` Plain) → Byte-Gleichheit.
3. Datenfeld heben (`SegmentWeatherData`) + Scheduler-Fetch (default-on).
4. Trip-Renderer (`html.py`, `plain.py`, `compact.py`) binden Shared-Komponente ein.
5. Toggle: Go-Model+Handler → `trip.py`+`loader.py` → Scheduler-Gate → Frontend.

### Open Questions
- [ ] Ein Alerts-Block **oben im Briefing** (gruppiert, dedupliziert) vs. pro Segment-Block — Empfehlung: oben/gruppiert (vermeidet Wiederholung). PO-Freigabe via ACs.
- [ ] Compact/SMS-Behandlung wie unter (d) — via ACs bestätigen.
