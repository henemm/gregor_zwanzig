# Mini-Spec: #832 Segment-Label „Etappe N" → „Segment N" im Abweichungs-Alert

## Was ändert sich

- `src/output/renderers/email/helpers.py:769`: `"Etappe {s.segment.segment_id}, "` → `"Segment {s.segment.segment_id}, "`
- Das erzeugte Label lautet dann: `Segment 1, km 0–5.9, 07:00–09:00` (konsistent mit dem Fallback-Pfad ohne km-Werte)

## Was darf sich nicht ändern

- Fallback-Pfad (ohne km-Werte): gibt bereits `"Segment N (HH:MM–HH:MM)"` aus — bleibt unverändert
- Ziel-Pfad: `"🏁 Ziel, ..."` — bleibt unverändert
- Funktionssignatur und Logik von `build_segment_label` — keine Änderung
- Alle anderen Renderer (`alert_compact.py`, `plain.py`, `html.py`) rufen `build_segment_label` auf — kein Änderungsbedarf dort

## Manuelle Test-Schritte

1. Staging: Abweichungs-Alert manuell triggern (oder Snapshot manipulieren)
2. Empfangene Mail prüfen: Label muss `Segment 1, km X–Y, HH:MM–HH:MM` lauten, nicht `Etappe 1, ...`

## Acceptance Criteria

**AC-1:** Given `build_segment_label` wird mit km-Werten > 0 aufgerufen, When das Label gebildet wird, Then enthält es `"Segment N, km X–Y, HH:MM–HH:MM"` und nicht `"Etappe N, ..."`.

## Inline-Test

- [ ] `test_build_segment_label_km_path_uses_segment_not_etappe`: `build_segment_label` mit km-Werten > 0 gibt String zurück, der mit `"Segment "` beginnt und nicht `"Etappe "` enthält
