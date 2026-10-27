# Context: feat-2327-gps-etappenfortschritt

## Request Summary
Enthält eine eingehende Garmin-inReach-Premium-SMS Koordinaten (Kartenlink), soll der Etappen-Fortschritt daraus aktualisiert werden — nur wenn die Koordinate innerhalb ±100 m der geplanten Route liegt. Bewusste, PO-bestätigte Abweichung von „Planposition ist die legitime Positionsquelle" (Epic #2506, Issue #2327). Braucht ein ADR.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/inbound_sms_reader.py` | `split_link_code` (:96-124) verwirft Link + Koordinaten (`split(GARMIN_MARKER,1)[0]`, :121). `_poll_journal` (:193), `_verarbeite_befehl` (:340, `user_id` nur aus Go-Antwort, AC-9). Einhängepunkt für neuen `extract_position`. Gate ist seit #2323 nicht mehr der Link-Marker → Koordinaten optional. |
| `src/services/trip_segments.py` | `position_at_time` (:561), `_interpolate_point` (:520), `_remaining_km` (:666), `points_with_passage_times` (:707, Docstring „Planposition ist die legitime Positionsquelle"), `points_from_km` (:739, Vorbild für Fortschritts-Override), `resolve_current_segment`. Es gibt kein `segment_weather.py` mit Planposition. |
| `src/utils/geo.py` | `haversine_km` (:19). Kein Punkt-zu-Strecke-Abstand, kein Snapping → neu. |
| `src/core/gpx_parser.py` | Nur Parser, keine Distanzfunktion. |
| `src/services/track_resolution.py` | `resolve_stage_track_km` (:129), `_match_track` (:50), `_persistiere_distanzen` (:287, `_mutate`-Muster). Trackpunkte aus Nutzer-`gpx_dir`. |
| `src/app/models.py` / `src/app/trip.py` | `GPXPoint`, `GPXTrack`, `TripSegment`; `Trip`, `Stage`, `Waypoint` (Trip hält nur Wegpunkte). |
| `src/app/loader.py` | `get_data_dir(user_id)` (:1308), `save_trip`, `_write_trip_locked`. |

## Konsumenten der Planposition (Blast Radius)
- `src/services/trip_alert.py` ~2201-2240 (Radar-/Nowcast-Messpunkte), :2705 (`km_measured`)
- `src/services/trip_report_scheduler.py:2364-2385` (Starkregen-Hinweis im Briefing)
- `src/services/trip_command_processor.py:3088-3094` (Position/Standort), :3184-3261 (`strecke`, Regenradar)
- `src/services/radar_service.py:157`, `src/output/renderers/alert/project.py:384`

## Existing Patterns
- Eine einzige Text-Zerlegung (`split_link_code`, D9 #2154) — Koordinaten-Parser daneben, nicht daneben-duplizieren.
- Read-Modify-Write mit Merge (ADR-0101). Fortschrittswert besser in eigene Datei pro Nutzer/Trip unter `data/users/<user_id>/` mit Ablauf — nicht ins Trip-JSON (Go roundtrippt es).
- `points_from_km`: Startpunkt aus Nutzer-km statt Planposition = Vorbild für Override.

## Dependencies / Specs / ADRs
- Nächste freie ADR: **0102**; Index-Drift-Test `tests/test_adr_index_drift.py`. Verwandt: 0049, 0093, 0095, 0088, 0056, 0101. Keine ADR zur Planposition vorhanden.
- Specs: `feat_1676_s1_premium_sms_rueckkanal.md`, `fix_2323_premium_sms_gate_generisch.md`, `feat_2261_sz8_messpunkt_position.md`, `fix_2017_nowcast_messpunkt.md`, `feat_2051_s2a_raeumliche_ausdehnung.md`, `feat_2051_s4_strecke_kommando.md`, `inbound_command_channels.md`.
- `docs/reference/premium_sms_format.md` §4 (Z.50-66) nennt Koordinaten nicht → ergänzen.
- Tests: `tests/unit/test_inbound_sms_reply_learning.py`, `tests/tdd/_befehl_e2e_fixtures.py:1277`, `tests/fixtures/befehl_antwortzeit/seven_journal_*.json`.

## Risks & Considerations
- **Koordinatenformat unbelegt:** Im Repo nur Fixture-Annahme `inreachlink.com/g-0Ab1Cd2Ef... (51.9956, 7.7136)`. Kein `maps.garmin.com`/`extId`-Beleg. Vor der Spec echtes Journal-Material prüfen (Prod-Journal per `sudo -n -u claude-gregor` lesbar, siehe Memory) bzw. echte Premium-SMS über zweite seven.io-Nummer.
- Segment-Projektion nötig (Trackpunkte weit auseinander); 100 m = 0,1 km; Track-Quelle ist GPX im Nutzer-Bestand, nicht Wegpunkte.
- Multi-User: `user_id` nur aus Go-Antwort, Koordinaten nur gegen Trips dieses Nutzers; Test mit zwei Nutzern.
- Mehrdeutigkeit: Route kann sich selbst kreuzen/zurücklaufen → Projektion auf Etappe des heutigen Tages einschränken.
- Gültigkeitsdauer des Fortschritts (Verfall zum Etappenende/Tageswechsel) und Wirkung auf alle Konsumenten (siehe oben) ist Analyse-Thema.
- Alle vier Kanäle gleichrangig: Wirkung betrifft die Ausgaben aller Kanäle gleich (zentrale Positionsquelle, keine Kanal-Sonderlogik).
- Reine Positions-SMS ohne Befehl wäre möglich (`befehl` leer) — Verhalten/Antwort klären.

## Analysis

### Type
Feature (bewusste, PO-bestätigte Abweichung von „Planposition ist die legitime Positionsquelle"; ADR-0102 nötig).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/inbound_sms_reader.py` | MODIFY | `extract_position(text)` neben `split_link_code`; Aufruf in `_verarbeite_befehl`/`_poll_journal`; Koordinate nur nach `user_id` aus Go-Antwort verwenden |
| `src/utils/geo.py` | MODIFY | Punkt-zu-Strecke-Abstand (Projektion auf Segment) |
| `src/services/track_resolution.py` o. neues `src/services/position_fix.py` | CREATE/MODIFY | Snapping auf Track der Heute-Etappe, ±100 m, Fortschritts-km |
| Fortschrittsdatei `data/users/<uid>/…` | CREATE (Laufzeitdaten) | eigener Wert mit Ablauf, nicht im Trip-JSON (Go roundtrippt es) |
| `src/services/trip_segments.py` | MODIFY | `position_at_time` / `points_with_passage_times` liest Override, sonst Planposition (Vorbild `points_from_km`) |
| Konsumenten (`trip_alert`, `trip_report_scheduler`, `trip_command_processor`, `radar_service`) | prüfen | sollen über die zentrale Positionsquelle automatisch wirken; kein Kanal-Sonderfall |
| `docs/adr/0102-*.md` + `docs/adr/README.md` | CREATE | Entscheidung dokumentieren (Index-Drift-Test) |
| `docs/reference/premium_sms_format.md` §4 | MODIFY | Koordinaten ergänzen |
| Tests | CREATE | Parser (Fixture mit echtem Format), Snapping ±100 m (99/101 m), Zwei-Nutzer-Test, Ablauf, Mehrdeutigkeit |

### Scope Assessment
- Files: ca. 6 Code + 2 Docs + 3–4 Tests
- Estimated LoC: +250…350 produktiv (LoC-Override wahrscheinlich nötig)
- Risk Level: MITTEL–HOCH (zentrale Positionsquelle mit 5 Konsumenten; Fehlsnapping verfälscht Alarme/Regenradar)

### Technical Approach
1. **Parsen:** ein eigener `extract_position` neben `split_link_code` (eine Zerlegungsstelle, D9). Koordinaten sind optional; ohne Koordinaten Verhalten unverändert.
2. **Plausibilität:** Abstand zur Route der **heutigen Etappe** ≤ 0,1 km, sonst verwerfen + loggen (Selbstkreuzung/Rückläufe damit entschärft). Punkt-zu-Strecke-Abstand fehlt (`haversine_km` reicht nicht, Trackpunkte weit auseinander); lokale Equirectangular-Projektion genügt auf dieser Skala.
3. **Wirkung:** Fortschritts-km als eigener Wert mit Zeitstempel; `position_at_time` bevorzugt ihn solange frisch; Verfall zum Etappenende/Tageswechsel. Zentral, damit alle vier Kanäle gleich wirken.
4. **Persistenz:** eigene Datei je Nutzer/Trip, Read-Modify-Write (ADR-0101), `user_id` nur aus Go-Antwort.
5. **ADR-0102:** „plausibler GPS-Fix überschreibt Planposition"; verwandt 0049, 0093, 0095, 0101.

### Dependencies
#2323 (Gate nicht mehr am Link, erledigt), #2154 (`split_link_code`), ADR-0101; Konsumenten siehe oben.

### Open Questions
- [ ] **Koordinatenformat unbelegt.** Im Repo nur die Fixture-Annahme `(51.9956, 7.7136)`; aus dem Gedächtnis liefert Garmin typischerweise „… sent this message from: Lat … Lon …" — nicht verifiziert. Vor der Spec echtes Material beschaffen (Prod-Journal / echte inReach-Nachricht) und als Fixture aufzeichnen.
- [ ] Gültigkeitsdauer des Fix (bis Etappenende vs. feste Stunden)?
- [ ] Reine Positions-SMS ohne Befehl: nur aufnehmen, keine bezahlte Antwort (Vorschlag)?
- [ ] Neuester plausibler Fix gewinnt, auch wenn er hinter einem früheren liegt (Vorschlag)?
- [ ] Mehrere Trips mit Heute-Etappe: alle prüfen, bei Mehrdeutigkeit verwerfen (Vorschlag).

## Vertragsfestlegung aus /40 (Tech Lead, 2026-10-26)
`position_at_time`, `points_with_passage_times`, `points_along_remaining_route` bekommen das Keyword `user_id: str | None = None`
(ohne Wert bit-identisch zu heute). Grund: `Trip` kennt keinen Eigentuemer; Nachschlagen nur ueber `trip.id` waere ein
Cross-User-Datenleck (AC-9, gleiche Trip-ID bei zwei Nutzern). Folge fuer /50: die Konsumenten `trip_alert.py`,
`trip_command_processor.py` (`_show_now`, `_show_strecke`), `trip_report_scheduler.py` (`_build_starkregen_hint`) reichen nur ihre
bereits vorhandene `user_id` durch (reines Durchreichen, keine Kanal-Sonderlogik, Entscheidung 6 bleibt im Kern gewahrt).
Weitere Vertragspunkte: `services.position_fix.record_position_fix(user_id, lat, lon, observed_at)`;
`extract_position(text) -> (lat, lon) | None`; seven.io-Zeitstempel = Europe/Berlin ohne Zone; Fix wird in `_verarbeite_befehl`
nach der Zuordnung VOR der Befehlsantwort aufgenommen.
