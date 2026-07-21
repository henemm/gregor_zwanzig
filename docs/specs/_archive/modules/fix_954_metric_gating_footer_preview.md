---
entity_id: fix_954_metric_gating_footer_preview
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [telegram, sms, preview, metrics, bugfix]
---

<!-- Issue #954 — Zwei eigenständige Bugs aus der #944-Nachprüfung -->

# Fix #954 — Telegram-Fußzeile Metriken-Gating + SMS-Vorschau-Divergenz

## Approval

- [x] Approved

## Purpose

Zwei eigenständige, im echten Code verifizierte Bugs beheben: (A) die
Telegram-Fußzeile im **echten Versand** ignoriert die Metriken-Auswahl des
Trips und zeigt ⚡/Sicht/0°C-Grenze auch wenn diese Metriken deaktiviert sind;
(B) die **SMS-Vorschau** baut ihren Token-Text über einen eigenen, divergenten
Code-Pfad ohne den #944-`disabled_specs`-Fix, sodass Vorschau und echter
Versand auseinanderlaufen können.

## Source

- **File:** `src/output/renderers/narrow.py` — `_tg_day_footer()` (Zeilen 178–222), Aufruf in `render_telegram_bubbles()` (Zeile 402)
- **File:** `src/services/preview_service.py` — `render_sms_preview()` (Zeilen 201–246)
- **Referenz (KEINE Änderung):** `src/output/renderers/trip_report.py` (Zeilen 208–234, #944-Muster) und `render_telegram_preview()` (`preview_service.py:248–272`, nutzt bereits `report.telegram_bubbles`)

## Estimated Scope

- **LoC:** ~40 (Bug A: +/-20, Bug B: -20/+3)
- **Files:** 2 Quelldateien + 2 neue Testdateien
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig.get_enabled_metric_ids()` (`src/app/models.py:595`) | intern | Liefert aktivierte Metrik-IDs — Gating-Basis für Bug A, bereits genutzt in `narrow.py:400` für die Kurzübersicht derselben Bubble |
| `render_telegram_bubbles()` (`narrow.py:358`) | intern | Ruft `_tg_day_footer()` auf, hat `dc` bereits als Parameter — muss ihn durchreichen |
| `TripReportFormatter.format_email()` (`trip_report.py`) | intern | Baut `report.sms_text` (mit `disabled_specs`, #944-Fix) und `report.telegram_bubbles` — beide sind die Quelle der Wahrheit für den echten Versand |
| `render_telegram_preview()` (`preview_service.py:248`) | intern | Bereits korrektes Vorbild: gibt `report.telegram_bubbles` zurück statt neu zu rendern — Bug B übernimmt dasselbe Muster für SMS |

## Implementation Details

### Bug A — `_tg_day_footer()` Metriken-Gating

`_tg_day_footer(segments)` baut aktuell bedingungslos den ⚡-Teil (immer) und
Sicht-/0°C-Grenze-Teile (sobald Daten vorhanden) — unabhängig von der
Metriken-Auswahl des Trips. Fix: Signatur erweitert um `enabled_metric_ids:
set[str]` (oder `dc: UnifiedWeatherDisplayConfig`, dann intern
`dc.get_enabled_metric_ids()` aufgerufen). Jeder Teil wird nur noch
angehängt, wenn die zugehörige Metrik-ID enthalten ist:

- `"thunder"` in enabled_metric_ids → ⚡-Teil (wie bisher berechnet)
- `"visibility"` in enabled_metric_ids UND `min_vis is not None` → Sicht-Teil
- `"freezing_level"` in enabled_metric_ids UND `rep_freeze is not None` → 0°C-Grenze-Teil

Sind alle drei Bedingungen falsch, bleibt `parts` leer → bestehendes
`if not parts: return None` greift unverändert.

Aufrufstelle `render_telegram_bubbles()` (Zeile 402) übergibt zusätzlich
`dc.get_enabled_metric_ids()` (oder `dc` selbst, je nach gewählter Signatur) —
`dc` liegt dort bereits als Funktionsparameter vor, keine neue Abhängigkeit
nötig.

### Bug B — `render_sms_preview()` nutzt Versand-Feld statt eigenem Rendering

`render_sms_preview()` ruft aktuell zusätzlich zu `self._build_report(...)`
(das bereits ein korrektes `report.sms_text` mit `disabled_specs` liefert)
einen zweiten, redundanten `SMSTripFormatter().format_sms(...)`-Aufruf ohne
`disabled_specs` auf und gibt dessen Ergebnis zurück. Fix: der redundante
Aufruf (Import von `SMSTripFormatter`/`SMS_SYMBOL_BY_METRIC`, `clean_stage`-
Berechnung, `_thr`-Dict, `format_sms(...)`-Call) entfällt vollständig. Statt
`token_line` wird `report.sms_text` zurückgegeben:

```
return report.email_subject, report.sms_text
```

Rückgabetyp bleibt `tuple[str, str]` (email_subject, token_line) — inhaltlich
identisch zum Vorbild `render_telegram_preview()`, das bereits
`report.telegram_bubbles` statt eigenem Rendering nutzt.

## Expected Behavior

- **Input Bug A:** Trip mit `UnifiedWeatherDisplayConfig`, in dem `thunder`,
  `visibility` bzw. `freezing_level` einzeln oder in Kombination
  deaktiviert sind; Segmentdaten mit vorhandenen Gewitter-/Sicht-/
  Frostgrenze-Werten.
- **Output Bug A:** Die Fußzeile der Kurzübersicht-Bubble (echter
  Telegram-Versand via `format_email()` → `telegram_bubbles`) enthält nur
  Teile für aktivierte Metriken. Bei allen drei deaktiviert: keine
  Fußzeile (kein leerer Bindestrich-Rest).
- **Input Bug B:** Trip mit deaktivierten Metriken (z.B. `thunder`), Aufruf
  von `render_sms_preview()` über den Preview-Endpoint.
- **Output Bug B:** Zurückgegebener `token_line` ist exakt
  `report.sms_text` — identisch mit dem, was beim echten SMS-Versand
  verschickt würde (inkl. `disabled_specs`-Filterung).
- **Side effects:** Keine. Kein neuer State, keine Persistenz-Änderung.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit deaktivierten Metriken `thunder`, `visibility`
  und `freezing_level` / When ein Telegram-Briefing über den echten
  Versandpfad gerendert wird (`format_email()` → `telegram_bubbles`) / Then
  enthält die Kurzübersicht-Fußzeile weder ⚡-Teil noch Sicht-Teil noch
  0°C-Grenze-Teil — bei allen drei deaktiviert existiert gar keine Fußzeile.
  - Test: `render_telegram_bubbles()` mit `dc` ohne diese drei Metrik-IDs
    aufrufen und die Kurzübersicht-Bubble auf Abwesenheit der Fußzeilen-Zeile
    prüfen (kein String-Contains auf Dateiinhalt, sondern auf den
    gerenderten Bubble-Text).

- **AC-2:** Given derselbe Trip, aber nur `visibility` aktiviert (`thunder`
  und `freezing_level` deaktiviert), mit Sicht-, Gewitter- und
  Frostgrenzendaten in den Segmenten / When das Briefing gerendert wird /
  Then enthält die Fußzeile ausschließlich den Sicht-Teil, keinen ⚡-Teil
  und keinen 0°C-Grenze-Teil.
  - Test: Gezielter Teilmengen-Fall (nicht nur "alle aktiv" / "alle
    inaktiv"), belegt echtes Gating pro Metrik statt eines globalen
    Ein/Aus-Schalters.

- **AC-3:** Given ein Trip mit deaktivierter `thunder`-Metrik / When die
  SMS-Vorschau (`render_sms_preview()`) gerendert wird / Then ist der
  zurückgegebene Token-Text (zweites Tupel-Element) identisch mit
  `report.sms_text` (dem Text, der beim echten Versand verwendet würde) und
  enthält keine `TH`/`TH+`-Token.
  - Test: `render_sms_preview()` und der interne `_build_report()`-Aufruf
    (bzw. `report.sms_text`) für denselben Trip vergleichen — Gleichheit
    beweist, dass kein zweiter divergenter Renderpfad mehr existiert.

- **AC-4:** Given ein bestehender Aufrufer von `render_telegram_bubbles()`
  mit vollständig aktivierter Metriken-Konfiguration (Regressions-Fall) /
  When das Briefing gerendert wird / Then ist die Fußzeile inhaltlich
  identisch zum bisherigen Verhalten (⚡, Sicht, 0°C-Grenze wie zuvor,
  sofern alle drei Metriken aktiv sind) — bestehende Tests in
  `tests/tdd/test_issue_1001_telegram_bubbles.py` bleiben grün.

## Known Limitations

- Bug A ändert die Signatur von `_tg_day_footer()` (neuer Parameter für
  aktivierte Metrik-IDs bzw. `dc`). Interne Funktion, nicht öffentlich
  exportiert — Signaturänderung ist unkritisch, solange der einzige
  Aufrufer (`render_telegram_bubbles()`) mitgezogen wird.
- Bug B entfernt ausschließlich die redundante Berechnung in der
  **Vorschau**. Der echte SMS-Versandpfad (`trip_report.py`, bereits
  #944-korrekt) bleibt unverändert und ist nicht Teil dieses Fixes.
- Beide Bugs sind unabhängig voneinander behebbar und werden in einer Spec
  zusammengefasst, da sie aus derselben #944-Nachprüfung stammen und beide
  klein/eng umrissen sind.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfixes ohne neue Architekturentscheidung — beide
  Fixes wenden ein bereits etabliertes Muster an (Metriken-Gating via
  `get_enabled_metric_ids()`, Vorschau liest Versand-Feld statt eigenem
  Rendering), kein neuer Mechanismus.

## Test Coverage

Neue Testdateien (Namensregel: nach Verhalten, nicht nach Issue-Nummer):

- `tests/tdd/test_telegram_footer_metric_gating.py`
  - `test_footer_omits_thunder_part_when_thunder_disabled`
  - `test_footer_omits_visibility_part_when_visibility_disabled`
  - `test_footer_omits_freezing_level_part_when_freezing_level_disabled`
  - `test_footer_none_when_all_three_disabled`
  - `test_footer_unchanged_when_all_three_enabled` (Regression, AC-4)

- `tests/tdd/test_sms_preview_matches_sent.py`
  - `test_sms_preview_token_line_equals_report_sms_text`
  - `test_sms_preview_omits_thunder_token_when_thunder_disabled`

Alle Tests mit echten `SegmentWeatherData`/`UnifiedWeatherDisplayConfig`-
Objekten (kein Mock-Theater). Repro-Tests müssen vor dem Fix rot, danach
grün sein.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #954
