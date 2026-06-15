# Context: Issue #819 — Katalog-Inkonsistenz visibility.has_friendly_format

## Request Summary
visibility wurde in #814 zu einer reinen km-Zahl-Metrik (kein Einfach-Modus, kein
Frontend-Umschalter). Im Katalog blieb sie aber als `friendly_label`/`format_modes=
("raw","simplified")`/`default_format_mode="simplified"` stehen → `has_friendly_format`
liefert fälschlich `True`. Das Feld „lügt". Aufräumen ohne Verhaltens-Change.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py` (visibility def ~291–307) | Zu ändern: friendly_label entfernen, format_modes=("raw",), default_format_mode="raw" |
| `src/output/renderers/email/helpers.py:536` | fmt_val-visibility-Zweig — rendert IMMER km, mode/ampel-unabhängig → Garant der Inertness |
| `src/output/renderers/email/helpers.py:786` | `build_friendly_keys`: einziger Prod-Konsument von `has_friendly_format` für visibility |
| `src/output/renderers/email/helpers.py:810` | `_AMPEL_CAPABLE_METRIC_IDS` — visibility NICHT enthalten → HTML-Ampel unberührt |
| `src/app/loader.py:40` | `_resolve_format_mode`: stored "simplified" → fällt nach Änderung graceful auf "raw" (Warning, kein Crash) |

## Tests — currently PASSING, MUST update (das eigentliche #819-Test-Scope)
- `tests/red/test_issue_435_format_modes.py:242–244` → format_modes ("raw",), default "raw"
- `tests/red/test_issue_435_format_modes.py:285–292` → visibility use_friendly=True löst nun auf "raw" (nicht "simplified")
- `tests/unit/test_weather_metrics_ux.py::TestMetricDefinitionHasFriendlyFormat::test_visibility_has_friendly_format` → muss `has_friendly_format is False` werden

## Regression-Guard (bleibt grün, beweist Inertness)
- `tests/tdd/test_issue_811_mode_matrix.py::test_visibility_numeric_km_no_english_word`
  rendert echte Mail in {raw,friendly} → erwartet km-Zahl, kein englisches Wort.

## Out of Scope — gehört zu #815 (Test-Hygiene-Sweep, bereits rot wegen entferntem `_fmt_val`)
- `test_weather_metrics_ux.py::TestVisibilityLevelFormatting`, `::TestFmtValFriendlyToggle`
- `test_config_persistence.py::test_visibility_friendly_*`
- `test_friendly_format_email_and_alerts.py::test_visibility_*`
- `test_friendly_format_and_alerts_config.py::TestFmtValFriendlyVisibility`
Alle scheitern schon JETZT an `TripReportFormatter._fmt_val` (in #814/β3 entfernt). #819
liefert die Klarstellung: diese Tests sind in #815 zu **löschen** (nicht umzuschreiben),
da visibility keinen Friendly-Modus mehr hat.

## Backward Compatibility
Bestehende Trips mit `format_mode="simplified"` für visibility: `_resolve_format_mode`
verwirft den unbekannten Modus mit Warning und fällt auf "raw" — exakt das gewünschte
ehrliche Verhalten, kein Datenverlust (Feld bleibt verbatim persistiert; nur Render-
Auflösung ändert sich, und der visibility-Zweig zeigt ohnehin immer km).
`test_issue_629::test_ac4_kept_modes_untouched` prüft nur die verbatim-Persistenz des
Strings → bleibt grün.

## Risks & Considerations
- Risiko minimal: einziger Prod-Konsument `build_friendly_keys` wird durch den
  unbedingten km-Zweig in fmt_val neutralisiert. #811-Matrix-Test ist der Beweis.
- Kein Frontend-Change (visibility ist seit #814 nicht mehr in INDICATOR_MAP).
- LoC winzig (~4 Katalog-Zeilen + 3 Test-Asserts).
