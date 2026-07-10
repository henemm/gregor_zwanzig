# Context: Nowcasting im Orts-Vergleich (#1041)

## Request Summary

Nowcasting (Regen-Kurzfrist-Info) soll — **konfigurierbar** analog zur amtliche-Alerts-Checkbox (#1040) — auch im Orts-Vergleich ("Compare") erscheinen. Kernfrage der Analyse: **Quellen-Entscheidung** — echtes radarbasiertes Météo-France-Nowcast ("Pluie dans l'heure" / AROME-PI) vs. Wiederverwendung der bestehenden `radar_service`-Kette (RADOLAN/INCA/DPC + AROME-via-Open-Meteo) vs. Open-Meteo direkt.

Blocker aufgehoben: Epic #1033 (amtliche Alerts) ist seit 2026-07-07 geschlossen.

## Nutzungskontext (entscheidend für die Quellen-Frage)

Der Orts-Vergleich ist ein **Planungs-/Tagesentscheidungs-Werkzeug** für den VOR-ORT-Urlauber (Konfiguration vor dem Urlaub), **kein Unterwegs-Alarm**. Das relativiert den Mehrwert von 5-Minuten-Radar-Schärfe: Für "wo wird es morgen trockener" reicht Modell-Granularität womöglich völlig.

## Related Files

### Compare-Rendering & Konfig-Kette (#1040-Vorbild, die zu spiegelnde 6-Datei-Kette)

| Datei | Relevanz |
|------|-----------|
| `internal/model/compare_preset.go:38` | `OfficialAlertsEnabled *bool json:"official_alerts_enabled,omitempty"` — Pointer-Pattern (nil/true = Default, false = strukturell kein Fetch). Direktes Vorbild für neues `NowcastEnabled`. |
| `internal/handler/compare_preset.go:214-218` | Read-Modify-Write-Nil-Merge im Update-Handler (Datenverlust-Schutz) |
| `src/services/comparison_engine.py:48,188-205` | `run(..., official_alerts_enabled=True)` — Fetch-Gate + Ergebnis nach `LocationResult` |
| `src/services/scheduler_dispatch_service.py:245,276` | Realer Versandpfad: `preset.get("official_alerts_enabled", True)` → Engine-Aufruf; analog `hourly_enabled` |
| `src/app/user.py:148,174` | `class LocationResult` mit `official_alerts: List[OfficialAlert]` — hier würde `nowcast: Optional[NowcastResult]` andocken |
| `frontend/.../steps/Step5Versand.svelte:136-140` | Checkbox via `ChannelToggle` — Ort der neuen Nowcast-Checkbox |
| `frontend/.../compareWizardState.svelte.ts:40,175,227` | Svelte-State + Save-Payload |
| `frontend/src/lib/types.ts:497` | TS-Typ `official_alerts_enabled?: boolean` |

### Compare-Renderer

| Datei | Relevanz |
|------|-----------|
| `src/output/renderers/comparison.py:142-179` | **Versand-Einstiegspunkt** `render_compare_email(...)` → ruft HTML + Text |
| `src/output/renderers/email/compare_html.py:654-764` | `render_compare_html` v2 (kein Winner/Score, alphabetisch). Body-Sektionsliste Z. 704-734 — Einbaustelle für neue Nowcast-Sektion |
| `compare_html.py:317-358` | `_render_warn_lead` — Guard-Vorbild ("nur wenn ≥1 Ort betroffen") für eine `_render_nowcast_lead` |
| `.claude/hooks/email_spec_validator.py` | Compare-Mail-Validator (`X-GZ-Mail-Type: compare`) — tolerant ggü. neuer optionaler Sektion, solange Warn-Zeile bleibt |

### Nowcast-Bestand (Wiederverwendungs-Kandidat)

| Datei | Relevanz |
|------|-----------|
| `src/services/radar_service.py:76,118` | **`RadarNowcastService.get_nowcast(lat, lon) -> NowcastResult`** — bereits **generisch pro Koordinate**, keine Trip-Kopplung. Zentrale Wiederverwendungs-Schnittstelle |
| `radar_service.py:65-73` | `NowcastResult`: `onset_minutes`, `intensity_label`, `source`, `is_convective` |
| `radar_service.py:95,154` | `intensity_to_text`, `format_now_text(result, tz=, include_source=)` |
| `radar_service.py:201-234` | Quellen-Kette bbox-geroutet: RADOLAN→INCA→DPC→AROME-FR→ICON-D2→Open-Meteo |
| `src/services/trip_alert.py:33` | `radar_alert_due(result, threshold_min)` — reine, koordinaten-agnostische "Regen-in-X-Min"-Funktion |
| `src/services/trip_command_processor.py:1075-1092` | Präzedenz: nutzt `get_nowcast` bereits **trip-frei** pro Waypoint |
| `docs/context/issue-734-radar-nowcast.md` | **Vorentscheidungs-Doku:** bewertet MF-Direkt-Portal (GRIB/WMS/WCS) als teuer/komplex; Open-Meteo-AROME-HD (`arome_france_hd_15min`) als "sauberster Fit" |
| `docs/specs/modules/radar_nowcast.md` | Bestehende Nowcast-Spec (#656) |

### Météo-France-Zugang

| Datei | Relevanz |
|------|-----------|
| `src/services/official_alerts/vigilance.py:35-90` | MF-Portal-Zugriff: **einfacher `apikey`-Header** (kein OAuth2!) gegen `https://public-api.meteofrance.fr/public/...`, ENV `GZ_METEOFRANCE_APIKEY`; National-Call TTL-gecacht (bewusst gegen Compare-Ort-Sturm) |
| `src/services/official_alerts/meteo_forets.py:40-88` | Zweiter MF-Consumer — **dupliziert** das httpx+Cache-Muster (kein gemeinsamer Helper) |
| `src/providers/openmeteo.py:107-115,796-823` | `meteofrance_arome`-Regionalmodell existiert, aber `fetch_forecast` nutzt **nur `hourly`, kein `minutely_15`** — Nowcast liegt separat in radar_service |

## Existing Patterns

- **Konfig-Toggle-Kette (#1040/#1107):** Go `*bool`-Pointer (Default true, RMW-Merge) → Python `preset.get(...)` im Scheduler → Engine-Fetch-Gate → LocationResult-Feld → Renderer-Sektion → Svelte `ChannelToggle`. Ein `nowcast_enabled` folgt 1:1.
- **Nowcast pro Koordinate:** `RadarNowcastService.get_nowcast(lat,lon)` ist bereits generisch (2 Präzedenz-Consumer trip-frei).
- **MF-Anti-Sturm:** TTL-Cache in `vigilance.py` (ein National-Call pro Fenster statt pro Ort) — Referenz falls eine neue MF-Quelle pro-Ort im Compare abgefragt würde.

## Dependencies

- **Upstream:** `RadarNowcastService` → BrightSky/GeoSphere/RadarDPC/Open-Meteo-Provider; MF-Portal via `GZ_METEOFRANCE_APIKEY`.
- **Downstream:** Compare-Versandpfad (`scheduler_dispatch_service.py` → `comparison_engine.py` → `comparison.py`/`compare_html.py`), Compare-Mail-Validator.

## Existing Specs

- `docs/specs/modules/radar_nowcast.md` — Nowcast-Kern (#656)
- `docs/specs/modules/issue_1040_alerts_toggle.md` — **verbindliche** Toggle-Spec (die `issue_1040_official_alerts_config_toggle.md`-Variante ist SUPERSEDED)
- `docs/context/issue-734-radar-nowcast.md` — Quellen-Vorbewertung MF-Direkt vs. Open-Meteo-AROME

## SCOPE-PIVOT (PO-Entscheidung 2026-07-10)

**Das Feature gehört in die Orts-Vergleichs-ALERTS, NICHT in die Vergleichs-Briefing-Mail.**

Begründung des PO auf die Analyse-Fragen:
- Frage „Zweck": **Feature zurückstellen** (bezogen auf die Briefing-Mail) — der 60-Minuten-Kurzfristwert passt nicht zur Tages-Planungsmail (Zeit-Widerspruch bestätigt: Nowcast-Horizont `radar_service.py:59` = 60 Min ab Versand; Compare plant Tagesfenster `hour_from=9..hour_to=16`, `scheduler_dispatch_service.py:236-241`, target_date=today).
- Frage „Datenquelle": „Für die Hauptmail braucht es am Tagesbeginn/-ende keinen Kurzfristwert. **Aber für die Alerts ist dieses Feature wichtig.**"
- Frage „Standard an/aus": „**Das Feature gehört in die Alerts, nicht in die Vorhersage.**"

**Neuer Zielbereich:** Radar-/Regen-Kurzfrist-**Alarm** für Vergleichsorte ("an einem deiner Orte fängt es gleich an zu regnen / Gewitter zieht auf") — als neuer Alarm-Typ im bestehenden Orts-Vergleichs-Alert-System (Epic #1095, Scheiben #1168/#1169/#1170 live). Vorbild: Trip-Radar-Alarme (`trip_alert.py:check_radar_alerts`, `radar_alert_service.py`, `radar_alert_due`).

Die Quellen-Entscheidung (radar_service wiederverwenden vs. neuer MF-Radar-Client) bleibt relevant, aber sekundär — `RadarNowcastService.get_nowcast` ist unverändert der wiederverwendbare Kern. Empfehlung A (Wiederverwendung) steht weiterhin.

Die Renderer-/Briefing-Mail-Kette (compare_html.py, comparison.py, das #1040-Toggle in der Vorhersage) ist damit **nicht mehr** der Einbaupfad. Re-Analyse der Compare-Alert-Pipeline läuft.

## Analysis (nach Scope-Pivot: Compare-Radar-Alarm)

### Type
Feature — neuer Alarm-Typ im Orts-Vergleichs-Alert-System.

### Architektur-Entscheidung: Parallelpfad (nicht in die Deviation-Engine)
Die Compare-Alarm-Engine `DeviationAlertEngine` (`src/services/deviation_alert_engine.py:204`) ist strukturell auf **„Metrik-Δ ≥ Schwelle" gegen Snapshot-Anker** festgelegt (Change-Detection cached vs. fresh `PointWeatherData`, `metric_alert_levels`). Ein Radar-Onset („Regen beginnt in <N Min") ist **kein** numerischer Δ und hat keine Schwellen-Repräsentation → passt nicht in `evaluate()`, es gibt keinen Erweiterungspunkt.
**→ Wie beim Trip: Radar-Alarm als eigener Parallelpfad**, neben den Metrik-Alarmen. Trip-Vorbild: `check_radar_alerts()` (`trip_alert.py:628`) + eigener Endpoint `/radar-alert-checks` (`scheduler.py:70`), separat von `/alert-checks`.

### Andockpunkt
`CompareAlertService._detect_triggered_locations` (`compare_alert.py:117-147`) iteriert bereits pro Ort mit aufgelösten `loc.lat/loc.lon`. Der neue Pfad (neuer `CompareRadarAlertService.check_radar_alerts()` + Endpoint `/compare-radar-alert-checks`) nutzt dieselbe Preset-/Ort-Iteration und ruft je Ort `RadarNowcastService().get_nowcast(loc.lat, loc.lon)`.

### Wiederverwendbar (kein Neubau)
- `RadarNowcastService.get_nowcast(lat, lon) -> NowcastResult` (`radar_service.py:118`) — unverändert, pro Compare-Ort.
- `radar_alert_due(result, threshold_min)` (`trip_alert.py:33`), Trip-Schwelle onset ≤ 20 Min, konvektiv immer durch.
- `DeviationAlertEngine.is_quiet_hours()` / `is_cooldown_active()` (`:71/:85`) — statisch, location-generisch, 1:1 nutzbar.
- Bündelung mehrerer Orte eines Presets in EINE Mail (Muster `send_multi_location_deviation_alert`, `notification_service.py:369`).
- Compare-Alarm-Konfig existiert bereits: `AlertCooldownMinutes/QuietFrom/QuietTo` (Pointer), Editor-Tab „Alarme" `CompareAlarmSection.svelte` (reusable Trip-Controls).

### Portierungsarbeit (das eigentliche Delta)
Trip-Radar-Nachricht ist trip-verdrahtet: `radar_alert_service.build_onset_alert_message(trip, active, ...)` (`:31`) und `NotificationService.send_radar_alert(trip=..., )` (`:459`) verlangen Trip + Segment (Etappe-N-Label, km_from/to). Für Compare auf ein **Ort-Objekt (Name + lat/lon, ohne Etappen-km)** generalisieren — analog zur #1169-Generalisierung `send_deviation_alert → send_multi_location_deviation_alert`.

### Konfig-Feld
Neuer Radar-Alarm-Schalter im Compare-Preset (Go `internal/model/compare_preset.go`, Pointer-Pattern, RMW-Merge im Handler) + Toggle im „Alarme"-Tab (`CompareAlarmSection.svelte`). Default: **opt-in (aus)** — Netzwerkkosten je Ort, konservativ; PO kann überstimmen.

### Scope Assessment
- Dateien: Backend ~4 neu/geändert (`compare_radar_alert.py` neu, `scheduler.py`, `notification_service.py`+`radar_alert_service.py` generalisieren), Go 2, Frontend ~4.
- **Geschätzte LoC deutlich > 250** (Service + Endpoint + Nachricht-Generalisierung + Konfig + Frontend) → **Slicing nötig** (LoC-Limit 250/Workflow; kein Override ohne PO). Präzedenz: #1095 selbst war in #1168/#1169/#1170 geschnitten.
- Risk Level: MEDIUM (neuer Versandpfad, Netzwerk je Ort, State/Cooldown, Datenverlust bei Preset-Save).

### Slicing-Vorschlag
- **Slice 1 (MVP, Backend):** `CompareRadarAlertService` + Endpoint + generalisierte Onset-Nachricht + Cooldown/QuietHours-Wiederverwendung + einfacher Konfig-Schalter (Backend-Lesung, Default aus). E-Mail-only, Ort-Bündelung. Liefert den Alarm end-to-end (Schalter zunächst über Preset-JSON/Default).
- **Slice 2 (Frontend):** Radar-Schalter im „Alarme"-Tab des Compare-Editors.
Falls Slice 1 > 250 LoC: Nachricht-Generalisierung vorziehen (eigener Mini-Slice).

### PO-Entscheidungen (2026-07-10)
- **Zwei Scheiben** bestätigt: Slice 1 = Alarm (Backend, end-to-end), Slice 2 = Ein/Aus-Schalter im Editor.
- **Onset-Schwelle wie Trip:** Regen in ≤ 20 Min, konvektiv (Gewitter/Hagel) immer durch. 1:1 übernehmen.

## Risks & Considerations

1. **Kern der Analyse — Quellen-Entscheidung mit starkem Prior:** Der Bestand routet FR bereits über AROME-via-Open-Meteo (modellbasiert), und Doku #734 hat MF-Direkt-Portal (GRIB/WMS) schon als teuer/komplex verworfen. Ein neuer MF-AROME-PI-Radar-Client wäre **neue Infrastruktur** (eigener httpx+Cache, kein gemeinsamer MF-Helper vorhanden). Frage: Rechtfertigt der Compare-Nutzungskontext (Tagesplanung, kein Unterwegs-Alarm) diesen Aufwand, oder genügt Wiederverwendung von `radar_service`?
2. **Netzwerkkosten pro Ort:** Compare hat ≥3 Orte. `get_nowcast` je Ort = mehrere Provider-Calls je Ort. Default vermutlich `False` (opt-in), Anti-Sturm-Caching beachten.
3. **Darstellung in der Compare-Mail:** onset_minutes/intensity je Ort — als Übersichts-Zeile (analog Warn-Zeile) und/oder Lead-Bar? Muss v2-Layout (kein Winner) respektieren und Validator nicht brechen.
4. **Datenverlust-Regel:** Neues Preset-Feld erfordert RMW-Merge im Go-Handler (Pointer-Pattern), sonst Cross-Save-Verlust.
5. **`confidence`-Analogie:** Anders als `confidence_pct` (#710) ist Nowcast eine echte lokale Wettergröße pro Ort — als Compare-Feature legitim.
