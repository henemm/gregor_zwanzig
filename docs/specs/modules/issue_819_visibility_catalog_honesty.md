---
entity_id: issue_819_visibility_catalog_honesty
type: module
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [metric-catalog, consistency, issue-819, follow-up-814]
---

# Visibility-Katalog-Ehrlichkeit (numerisch-only)

## Approval

- [ ] Approved

## Purpose

Bereinigt die in #814 entstandene Katalog-Inkonsistenz: Die Metrik `visibility` wird
seit #814 ausschließlich als km-Zahl gerendert (kein Einfach-Modus, kein Frontend-
Umschalter), trägt im Katalog aber weiterhin Friendly-Format-Metadaten, sodass
`MetricDefinition.has_friendly_format` fälschlich `True` liefert. Diese Spec macht den
Katalog ehrlich, **ohne** das gerenderte Verhalten zu ändern.

## Source

- **File:** `src/app/metric_catalog.py`
- **Identifier:** `MetricDefinition(id="visibility", ...)` (~Zeilen 291–307)

## Estimated Scope

- **LoC:** ~7 (≈4 Katalog-Zeilen + 3 Test-Asserts)
- **Files:** 1 Quell-Datei + 2 Test-Dateien
- **Effort:** low

## Dependencies

- **Upstream:** `MetricDefinition.has_friendly_format` (property = `bool(friendly_label)`),
  `format_modes`, `default_format_mode`.
- **Downstream (Prod-Konsumenten von `has_friendly_format`/`format_modes` für visibility):**
  - `src/output/renderers/email/helpers.py:786` `build_friendly_keys` — liest
    `has_friendly_format`. Wird durch den **unbedingten** km-Zweig in `fmt_val`
    (`helpers.py:536`) neutralisiert → keine sichtbare Änderung.
  - `src/output/renderers/email/helpers.py:810` `_AMPEL_CAPABLE_METRIC_IDS` — enthält
    visibility **nicht** → HTML-Ampel-Pfad unberührt.
  - `src/app/loader.py:40` `_resolve_format_mode` — Bestandsdaten mit
    `format_mode="simplified"` fallen graceful (Warning, kein Crash) auf "raw".

## Behavior / Constraints

- **Verhaltens-inert (PFLICHT):** Die echt gerenderte Briefing-Mail zeigt `visibility`
  vor und nach der Änderung als km-Zahl in **allen** Modus-Kombinationen
  ({full,compact} × {Einfach,Roh}). Bewacht durch
  `tests/tdd/test_issue_811_mode_matrix.py::test_visibility_numeric_km_no_english_word`.
- **Backward Compatibility:** Bestehende Trips mit `display_config`-Eintrag
  `format_mode="simplified"` für visibility laden weiter (Feld bleibt verbatim
  persistiert), die Render-Auflösung fällt auf "raw" — exakt das gewünschte ehrliche
  Verhalten, kein Datenverlust.

## Out of Scope

- Die bereits **jetzt** roten, veralteten Sicht-Tests, die die in #814/β3 entfernte
  `TripReportFormatter._fmt_val`-API rufen (`TestVisibilityLevelFormatting`,
  `TestFmtValFriendlyToggle`, `test_config_persistence::test_visibility_friendly_*`,
  `test_friendly_format_email_and_alerts::test_visibility_*`,
  `test_friendly_format_and_alerts_config::TestFmtValFriendlyVisibility`). Diese
  gehören zum Test-Hygiene-Sweep **#815** und sind dort zu **löschen** (nicht
  umzuschreiben), da visibility keinen Friendly-Modus mehr besitzt.

## Acceptance Criteria

**AC-1:** Given die Metrik-Definition für `visibility` im Katalog, When ihre Friendly-
Metadaten abgefragt werden, Then liefert `get_metric("visibility").has_friendly_format`
den Wert `False` (weil `friendly_label` leer ist).

**AC-2:** Given die Metrik-Definition für `visibility` im Katalog, When `format_modes`
und `default_format_mode` abgefragt werden, Then ist `format_modes == ("raw",)` und
`default_format_mode == "raw"`.

**AC-3:** Given eine persistierte MetricConfig mit `use_friendly_format=True` für
`visibility`, When `loader._resolve_format_mode` den Modus auflöst, Then ergibt sich
"raw" (statt vormals "simplified"), weil der Katalog-Default jetzt "raw" ist.

**AC-4:** Given eine echt gerenderte Briefing-Mail über den `render_email`-Pfad, When
`visibility` in jeder Modus-Kombination ({Einfach,Roh}) gerendert wird, Then erscheint
die Sicht als km-Zahl ohne englisches Wort (good/fair/poor/fog) — das gerenderte
Verhalten bleibt gegenüber dem Stand vor dieser Änderung unverändert.

## Test Strategy

- **AC-1/AC-2:** Direkter Katalog-Zugriff via `get_metric("visibility")` (kein Mock).
- **AC-3:** `loader._resolve_format_mode` mit echtem persistiertem Dict.
- **AC-4:** Regressions-Guard `test_issue_811_mode_matrix.py::test_visibility_numeric_km_no_english_word`
  — rendert die echte Mail über `render_email` (mock-frei) und prüft km-Ausgabe.

## Changelog

- 2026-06-14: Initial spec created (Folge-Bug aus #814, Katalog-Ehrlichkeit visibility).
