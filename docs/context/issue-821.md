# Context: issue-821 — Absolute Thunder-Regel feuert doppelt bei detect_changes(include_absolute=True)

## Request Summary
Eine absolute `THUNDER_LEVEL`-Regel erzeugt bei `detect_changes(..., include_absolute=True)`
**zwei** WeatherChanges für denselben Übergang (z.B. NONE→HIGH): einmal über den seit #816
per `setdefault` geseedeten Δ-Threshold, einmal über den Absolut-Pfad. Soll als ein
Change erscheinen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/weather_change_detection.py` | `from_alert_rules` (Δ-Seed via setdefault, Z.221-223) + `detect_changes` (Δ-Loop + Absolut-Pfad) — Bug-Ort |
| `src/services/trip_alert.py:448` | **Einziger** Produktiv-Aufrufer — nutzt `include_absolute=False` (Δ-only-Alert-Pfad) |
| `tests/unit/test_issue_222_alert_rules_detection.py:281` | `test_ac9_thunder_level_high_with_threshold_2_fires` — aktuell `@xfail(strict=False)`, verweist auf #821 |
| `tests/unit/test_issue_222_alert_rules_detection.py:118` | `test_absolute_rule_goes_to_absolute_rules_list` (F222-A) — in #817 korrigiert, **grün**, bleibt gültig (Seed bleibt) |
| `src/app/metric_catalog.py` | `get_change_detection_map()` — Quelle der Δ-Defaults |

## Root Cause
`from_alert_rules`: für eine ABSOLUTE-Regel wird per `setdefault(field, catalog_default)`
ein Δ-Threshold geseedet, damit absolute-only-Trips auf dem Δ-Alert-Pfad
(`include_absolute=False`, #816) symmetrische Δ-Alerts bekommen.
Bei `include_absolute=True` laufen **beide** Pfade: der Δ-Loop feuert (Δ2 > 1.0) **und**
`_detect_absolute_changes` feuert (ordinal 2 ≥ 2.0) → ein Übergang = zwei Changes.

## Produktiv-Wirkung
**Latent / test-only.** Der einzige Produktiv-Aufrufer (`trip_alert.py:448`,
Forecast-Alert-Versand) nutzt `include_absolute=False` → nur der Δ-Change feuert.
`from_alert_rules` + `include_absolute=True` (Default) kommt aktuell in `src/` **nicht** vor
(nur Tests). Der Default-Konstruktor-Pfad (Katalog-Defaults statt `from_alert_rules`) hat
keine `_absolute_rules` → kein Doppelfeuern. Fix ist Korrektheits-/Regress-Vorsorge.

## Existing Patterns
- Δ-Seed via `setdefault` (#816 C) — bleibt, damit absolute-only-Trips Δ-Alerts kriegen.
- Severity-Override-Map `_severity_overrides` pro Feld (#222) — Vorbild für feld-getaggte Sets.
- `include_absolute`-Flag (#816) trennt Δ-only-Alert vom kombinierten Briefing/Legacy-Pfad.

## Dependencies
- Upstream: `metric_catalog.get_change_detection_map`, `AlertRule`/`AlertMetric`/`AlertRuleKind`.
- Downstream: `trip_alert.py` (Δ-only), Briefing-Change-Berechnung (Default `True`, derzeit kein
  `from_alert_rules`-Pfad).

## Risks & Considerations
- Δ-Seed für absolute-only-Trips (include_absolute=False) **darf nicht** kaputtgehen — der Fix
  muss feld-selektiv nur den Doppel-Change bei include_absolute=True unterdrücken.
- Ein Feld mit **explizitem** DELTA-Threshold **und** absoluter Regel: explizit gesetzter Δ darf
  NICHT unterdrückt werden (Nutzer will beides) — nur rein-geseedete Felder dedupen.
- F222-A (`_thresholds == {"gust_max_kmh": 20.0}`) bleibt gültig: Seed bleibt erhalten.
