---
entity_id: issue_822_radar_nowcast_segment_tests
type: tests
created: 2026-06-15
updated: 2026-06-15
status: draft
version: 1.0
spec: docs/specs/modules/issue_822_radar_nowcast_segment.md
---

# Test-Manifest: #822 Radar-/Regen-Nowcast-Alert segmentbewusst machen

Mock-frei. DI-Seam `frame_source` (Callable(lat,lon)->frames) liefert deterministische
Regen-Frames. Kein Mock()/patch()/MagicMock. Skip nur bei fehlender SMTP-Infrastruktur.

## AC-Test-Mapping

| AC | Test | Datei | Beweis |
|----|------|-------|--------|
| AC-1 | `test_ac1_segment_helper_roundtrip_bit_identical` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | ImportError → RED; nach Impl: bit-identische Segmentliste vs. TripReportSchedulerService |
| AC-2 | `test_ac2_segment_selection_by_time` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Falsche Koordinaten von get_nowcast → RED; nach Impl: B.start_point bei 13:30, A bei 07:00, kein Alert bei 21:00 |
| AC-3 | `test_ac3_nowcast_called_at_segment_coordinates` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | waypoints[0]-Koordinaten statt Segment-Startpunkt → RED; nach Impl: active.start_point |
| AC-4 | `test_ac4_mail_body_contains_segment_label_and_cooldown` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Kein Segment-Label im Body → RED; nach Impl: „Etappe N, km X–Y" + Cooldown-Text |
| AC-5 | `test_ac5_onset_time_in_tour_timezone` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | TypeError: tz-Parameter fehlt → RED; nach Impl: Onset in Tour-TZ |
| AC-6 | `test_ac6_cooldown_display_reflects_trip_setting` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Kein „90 Minuten"/„2 Stunden" im Body → RED; nach Impl: dynamischer Cooldown-Text |
| AC-7 | `test_ac7_throttle_recording_unchanged` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | REGRESSION-GUARD: Throttle-Semantik aus #773 — kann schon grün sein |
| AC-8 | `test_ac8_mandantentrennung_isolated` | `tests/tdd/test_issue_822_radar_nowcast_segment.py` | REGRESSION-GUARD: Mandantentrennung aus #773 — kann schon grün sein |

## RED-Erwartung

- AC-1: `ImportError: cannot import name 'convert_trip_to_segments' from 'services.trip_segments'`
- AC-2: `AssertionError` — get_nowcast mit falschen Koordinaten (waypoints[0] statt aktives Segment)
- AC-3: `AssertionError` — get_nowcast mit WP0_LAT/WP0_LON statt SEG_LAT/SEG_LON
- AC-4: `AssertionError` — Body enthält kein „Etappe"
- AC-5: `TypeError` — format_now_text() got unexpected keyword argument 'tz'
- AC-6: `AssertionError` — Body enthält weder „90 Minuten" noch „2 Stunden"
- AC-7: REGRESSION-GUARD (grün erwartet)
- AC-8: REGRESSION-GUARD (grün erwartet)
