# Mini-Spec: fix-1948-s2-preview-eingaben

Nachbesserung zu #1948 S2 (Staging-E2E BROKEN 2026-08-18) — behebt zugleich #1965.

## Was ändert sich

- **Bug A (`changes` → 500):** `api/routers/validator.py` prüft vor dem Rendern jeden
  `changes[].metric`-Wert gegen den Metrik-Katalog (gleiche Quelle wie
  `project.py:_resolve_metric_id`, `summary_fields` aus `app.metric_catalog._METRICS`).
  Unbekannte Metrik ⇒ HTTP 422 mit dem Metrik-Namen im Fehlertext (Parallel-Muster zur
  bestehenden `segment_id`-Prüfung AC-3). Kein 500 mehr.
- **Bug B Teil 1 (`official.segment_ids` unvalidiert):** `official[].segment_ids` werden gegen
  die Segment-IDs des geladenen Trips geprüft (dieselbe Quelle wie die AC-3-Prüfung);
  unbekannte ID ⇒ HTTP 422 mit der ID im Fehlertext. Leere Liste bleibt erlaubt
  (Bestandsverhalten „gesamte Route").
- **Bug B Teil 2 / #1965 (Renderer-Crash bei String-IDs):** `format_segment_reference()`
  (`src/output/renderers/alert/segments.py:42`) verkraftet nicht-numerische Segment-IDs:
  numerische IDs weiterhin sortiert/als Range, nicht-numerische IDs (außer „Ziel") werden
  unverändert in Original-Reihenfolge aufgezählt („Segment stage1, stage2"); „Ziel" und die
  „>4 ⇒ N Segmente"-Verdichtung bleiben unverändert. Damit ist auch der PRODUKTIV-Versandpfad
  (`trip_alert.py:1614` übergibt `str(segment_id)`) crashfrei ⇒ schließt #1965.

## Was darf sich nicht ändern

- `src/output/renderers/alert/official_alerts.py` — KEINE Zeile (inkl. #1929-Sperrzone 1896–2104).
- Verhalten für rein numerische Segment-IDs in `format_segment_reference` (byte-identische
  Ausgabe; bestehende Renderer-/Mail-Tests bleiben unverändert grün).
- Alle 15 S2-Tests + Bestands-Tests (`test_issue_221`, `test_issue_918`, `test_952`) unverändert grün.
- Keine neue Route, kein Go-/Frontend-Anteil, Endpoint bleibt seiteneffektfrei.

## Manuelle Test-Schritte (Staging, nach Deploy)

1. `alert-preview` mit `changes` und `metric="temperature"` ⇒ 422, Fehlertext nennt „temperature".
2. `changes` mit gültigem Katalog-Feld (z. B. `temp_max_c`) und echter Stage-ID ⇒ 200, fünf Felder.
3. `official` mit `segment_ids=["<echte stage-id>"]` ⇒ 200; SMS/Telegram zeigen Segment-Bezug.
4. `official` mit `segment_ids=["gibt-es-nicht"]` ⇒ 422 mit der ID.
5. Staging-E2E-Wiederholung (e2e-verify) ⇒ VERIFIED, erst dann Prod-Deploy.

## Inline-Tests (rot vor Fix, grün nach Fix)

- [ ] `changes` mit unbekannter Metrik ⇒ 422 + Name (heute: 500) — Endpoint-Test
- [ ] `official` mit unbekannter segment_id ⇒ 422 + ID (heute: 500) — Endpoint-Test
- [ ] `official` mit gültiger String-Segment-ID („stage1"-artiger Trip) ⇒ 200, fünf Felder (heute: 500)
- [ ] `format_segment_reference(["stage1","Ziel"])` ⇒ crashfrei, „Ziel" separat; numerischer
      Bestandsfall byte-identisch (Wächter direkt an der Funktion)

## Scope

~40–60 LoC produktiv in 2 Dateien (`api/routers/validator.py`, `src/output/renderers/alert/segments.py`) + Tests. Schließt #1965 mit (gleicher Wirkort); Issue-Close erst nach Prod-Selftest Exit 0.
