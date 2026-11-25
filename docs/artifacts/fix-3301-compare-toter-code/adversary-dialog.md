# Adversary Dialog — fix-3301-compare-toter-code
Spec: docs/specs/fast/fix-3301-compare-toter-code.md
Datum: 2026-11-25 13:29

## Checkliste
- [x] **AC-1:** Given der Stand nach #3297, When die Frontend-Produktionsquellen durchsucht werden, Then existiert `compareHourlyMetricDefs.ts` nicht mehr und kein Produktionsmodul importiert es.
- [x] **AC-2:** Given die Anlegeseite des Ortsvergleichs, When ihre Komponenten-Importkette geprüft wird, Then bindet sie weder `WeatherMetricsTab` noch einen Abschnitt `layout_kanal` ein.
- [x] **AC-3:** Given ein Ortsvergleich mit gespeichertem `hourly_metrics`, When er über `buildComparePresetSavePayload` gespeichert wird, Then bleibt `hourly_metrics` unverändert erhalten (bestehender Test bleibt grün).

## Dialog

### Runde 1
**Adversary:**
Gelöschte Testblöcke: applyHourlyMetricToggle/-FromState/orderableHourlyMetricKeys/applyHourlyReorder/hourlyKeysAusGrundauswahl
hatten ausser den zwei Test-Dateien keinen Aufrufer (Suche in frontend/src, src/, api/, internal/: nur Kommentare in
compareMetricOrder.ts:11 und tests/tdd/test_issue_1106_hourly_metrics_config.py:106). Windrichtungs-Merge (hourlyMergeOnly) lebt
serverseitig und in compareAggregationGrouping.ts:62, wurde nie über die gelöschte Datei erzwungen; Leerauswahl beim Speichern
bleibt durch compare_empty_metric_selection.test.ts (hourly_metrics nie gesendet) bewacht. Kein lebendes Verhalten unbewacht.
Mutationen (Sicherung im Scratchpad, byte-genau zurück, Index-Diffstat vorher/nachher gleich):
M1 Produktionsmodul importiert './compareHourlyMetricDefs.ts', Datei wieder angelegt: AC-1 rot (2 not ok).
M2 CompareNewEditor.svelte importiert WeatherMetricsTab: AC-2 rot.
M3 hourly_metrics im Save-Payload auf undefined: alle 3 Tests in compareEditorHourlyMetrics.test.ts rot.
(Erste M3-Variante traf nur Kommentare und war wirkungslos: Prüferfehler, nicht Testlücke.)
Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/compare_toter_code_3301.test.ts:78 — IMPORT_MUSTER/AC-1-Muster verlangen
`from` oder `import(`; ein Seiteneffekt-Import `import './compareHourlyMetricDefs.ts'` wird vom Importtest NICHT erkannt (M1b: nur der
Existenztest wurde rot). Praktisch abgesichert, weil die Datei gelöscht ist und der Import den Build brechen würde.
Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: compare_toter_code_3301.test.ts:70 (ohneKommentare) — Kommentar-Regexe ignorieren Stringkontext
(ein String wie './*.svelte' könnte Code bis zum nächsten Kommentarende maskieren). Import in derselben Zeile hinter Code wird
nicht übersehen (nur ab `//` wird gekürzt); importHuelle arbeitet auf Rohtext (konservativ). Kein reproduzierter Fehlnachweis.
**Implementierer:** Keine Reaktion nötig (kein Fix beauftragt).

### Runde 2
**Adversary:**
Nachprüfung: vier Dateien (compare_toter_code_3301, compareEditorHourlyMetrics, compare_empty_metric_selection, compareEditorSave)
29 pass / 0 fail (docs/artifacts/fix-3301-compare-toter-code/adversary-test-output.txt). Alle Mutationen zurück (cmp identisch),
Index-Diffstat vorher/nachher gleich, keine unstaged Änderungen an getrackten Dateien. Frühkonvergenz-Skepsis: Windrichtung/Leerauswahl
gezielt gesucht, AC-3 per echter Mutation als wirksam bewacht belegt. Nichts über LOW.
**Implementierer:** n/a.

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/__tests__/compare_toter_code_3301.test.ts:105
  Evidence: Existenz- und Importtest, M1 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/compare_toter_code_3301.test.ts:122
  Evidence: Importketten-Scan, M2 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:130
  Evidence: baseDisplayConfig-Spread erhält hourly_metrics; M3 rot.
  Status: CONFIRMED

Confirmation:
  AC: gelöschte Datei
  Code reference: frontend/src/lib/components/compare/compareHourlyMetricDefs.ts:1
  Evidence: keine Produktions-Aufrufer.
  Status: CONFIRMED

Confirmation:
  AC: Testanpassung
  Code reference: frontend/src/lib/components/compare/compareEditorHourlyMetrics.test.ts:14
  Evidence: nur Blöcke der gelöschten Datei entfernt.
  Status: CONFIRMED

Confirmation:
  AC: Testanpassung
  Code reference: frontend/src/lib/components/compare/__tests__/compare_empty_metric_selection.test.ts:14
  Evidence: nur AC-8-Block der gelöschten Funktion entfernt.
  Status: CONFIRMED


## Herkunft der Vorbedingungen

<!-- vom Prüfer auszufüllen, siehe `precondition_origins.py` -->

## Verdict

VERDICT: VERIFIED
Tests: 29 passed, 0 failed. Mutationen M1-M3 gefangen; 2 LOW-Anmerkungen, kein Blocker.

## Geprüfte Dateien

- sha256:b6a03df1a75a0127f3cc8701aa67c2263ddcfdd26f6e29c4d899ba1cd397a53b  frontend/src/lib/__tests__/compare_toter_code_3301.test.ts
- sha256:b73259bf77116fab13371dbf5c5b8452585b9ac6426181f05666a55ea30195ae  frontend/src/lib/components/compare/__tests__/compare_empty_metric_selection.test.ts
- sha256:b5505398cd2b45d7016e6e1e54a0ddcd0b1095d6fbedee06d9d62b7739cd5b03  frontend/src/lib/components/compare/compareEditorHourlyMetrics.test.ts
- sha256:8c4c067bb439d738dc9b1b9974cc79ff363a78d5012b8b4c9fce58ef4f36d1b9  frontend/src/lib/components/compare/compareEditorSave.ts

## Prüfbasis

- base: c8329fea43737304dd3d5e0672567063d44817d3
- blob:8e5d8c0cd003b3411b7530e47afc571f89ad71e9  frontend/src/lib/__tests__/compare_toter_code_3301.test.ts
- blob:1cc62e1f71fcbd8f737b9b67ad4c1c861de72acf  frontend/src/lib/components/compare/__tests__/compare_empty_metric_selection.test.ts
- blob:1f6c320d65966c87ecb8837e74906dca16d3ff9e  frontend/src/lib/components/compare/compareEditorHourlyMetrics.test.ts
- blob:2272c6168f7ad4eb89a0b210d6e172c2ba573a31  frontend/src/lib/components/compare/compareEditorSave.ts
