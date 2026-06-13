# Context: bug-801-803-mail-segmente-vortag

## Request Summary
Zwei verwandte Briefing-/Alert-Mail-Bugs: (#801) Update-/Alert-Mail zeigt „km 0.0–0.0",
weil der Wetter-Snapshot `distance_from_start_km` nicht persistiert; (#803) die
Vortags-Zeile trägt das missverständliche Label „Vortag:" und ist oft zu dünn
(nur eine Metrik überschreitet die grobe Spürbarkeitsschwelle).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/weather_snapshot.py` | **#801 Root Cause + Schema-Datei.** `_serialize_segment` (Z.229–256) speichert pro Punkt nur lat/lon/elevation; `_reconstruct_segment` (Z.285–307) setzt `distance_from_start_km` per GPXPoint-Default 0.0 + `distance_km/ascent_m/duration_hours` hart auf 0.0 |
| `src/services/trip_alert.py` | #801 Konsument: Update-Pfad lädt Snapshot statt frisch zu rechnen |
| `src/output/renderers/email/html.py:325` | #801 Render: `km {start.distance_from_start_km:.1f}–{end…:.1f}` |
| `src/output/renderers/email/plain.py:209` | #801 Render (Plain) gleiche km-Zeile |
| `src/services/day_comparison.py` | **#803 Root Cause.** `summarize_day_comparison` (Z.115) + `_summarize_legacy` (Z.138) + `_summarize_metric_driven` (Z.192). Label „Vortag: heute … als gestern" hier; `_get_threshold` (Z.180) liest `default_change_threshold`, Fallback 5.0 |
| `src/app/metric_catalog.py` | #803b Schwellen-Quelle. temperature/wind_chill/dewpoint = `default_change_threshold=5.0` (Z.73/82/103). **ACHTUNG: Z.418 dokumentiert, dass dieses Feld DOPPELT genutzt wird — auch als Alert-Δ-Default** |
| `src/output/renderers/email/html.py:572-585` | #803 Mail-Konsument: ruft `summarize_day_comparison(..., selected_metrics=[...])` |
| `src/output/renderers/narrow.py:317-361` | Telegram baut EIGENE „Vortag: "-Zeile (Z.361) — gleiche Ambiguität, engerer Platz |
| `src/app/models.py:273` | `GPXPoint.distance_from_start_km: float = 0.0` (Default-Quelle des Bugs) |

## Existing Patterns
- **Snapshot-Serialisierung additiv:** `_serialize_summary` (Z.201) omit-None; Roundtrip
  über `_deserialize_*`. Neue Felder additiv → alte Snapshots fallen via `.get(..., default)`
  sauber zurück.
- **Vortags-Zeile metrik-getrieben (#799):** `_summarize_metric_driven` filtert ausgewählte
  Metriken über `_get_threshold`, sortiert nach |avg_delta|, Cap 6, Wortmapping `_DIRECTION_WORDS`.
- **Schwellen-SSoT:** `metric_catalog.default_change_threshold` ist die EINE Quelle, aber
  doppelt belegt (Alert-Δ + Vortags-Salienz).

## Dependencies
- **#801 Upstream:** `SegmentWeatherData.segment.{start,end}_point` (GPXPoint), `models.py`.
- **#801 Downstream:** Alert-Mail-Render (html/plain), `trip_alert.py`-Vergleichspfad.
- **#803 Upstream:** `metric_catalog`, `DayComparison`-Entries.
- **#803 Downstream:** Mail-HTML + Mail-Plain (über `summarize_day_comparison`), Telegram (eigene Zeile).

## Existing Specs
- `docs/specs/modules/weather_snapshot.md` v1.0 (#801 — Schema-Datei, muss aktualisiert werden)
- `docs/specs/modules/issue_748_day_comparison_service.md` v1.0 (#803)

## Risks & Considerations
- **#801 ist Schema-relevant** (`weather_snapshot.py`) → CLAUDE.md-Pflicht: Pre-Snapshot-Backup
  (Hook automatisch) + **Roundtrip-Test** (save alt → load → assert km erhalten) + additive
  Rückwärtskompatibilität für bestehende Snapshot-JSONs (fallen auf 0.0 zurück, kein Crash).
- **#803b Schwellen-Kopplung:** `default_change_threshold` senken (5,0 → 3,0) ändert AUCH die
  Alert-Empfindlichkeit. Sauberer: separate Salienz-Schwelle für die Vortags-Zeile, statt den
  geteilten Katalog-Wert zu mutieren. Trade-off in PO-Summary klären.
- **#803a Konsistenz:** Telegram (`narrow.py`) hat dieselbe „Vortag:"-Ambiguität bei engem
  Platz. Mail = explizite Beschwerde; Telegram-Anpassung ist Konsistenz-Folge.
- Beide Bugs backend-only (kein Frontend) → E2E-Pfad = Staging-Mail + briefing_mail_validator.
