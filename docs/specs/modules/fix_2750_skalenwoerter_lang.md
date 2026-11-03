---
entity_id: fix_2750_skalenwoerter_lang
type: module
created: 2026-11-03
updated: 2026-11-03
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2750, python, email, bug]
---

# Skalenwörter der Mails folgen der Nutzersprache (#2750)

**Issue:** #2750 · **Epic:** #2644 · **ADR:** 0104 · **Konventionen:** `docs/reference/i18n_konventionen.md`

## Approval

- [ ] Approved

## Purpose

Englische Nutzer bekamen in der Trip-Briefing-Mail (Stundentabelle im Modus „Einfach“) und im 3-Tages-Ausblick von Trip- und Vergleichs-Mail deutsche Wortstufen („mäßig“, „trocken“, „wahrscheinlich“, „wechselhaft“ …). Die Skalenwort-Funktionen in `src/services/weather_metrics.py` sind seit P1 sprachfähig (`lang`, Katalogschlüssel `api.skala.*`), die Aufrufer reichten `lang` aber nicht weiter. Der Fix reicht `lang` durch; Deutsch bleibt byte-gleich, Protokoll-Token (Kürzel, `sms_code`, `compact_label`) bleiben unberührt.

## Source

- **File:** `src/output/renderers/email/helpers.py` — `fmt_val` (Wind/Böen/Niederschlag, Modus `simplified`, Klartext)
- **File:** `src/output/renderers/compare_outlook_metric_ids.py` — `format_outlook_value(..., *, lang="de")`, `_friendly_outlook_text(..., lang="de")` (vier Wortskalen; zusätzlich Gewitter-/Niederschlagsart-Wort an `_fmt_thunder`/`_fmt_precip_type`, die `lang` bereits kennen)
- **File:** `src/output/renderers/email/outlook.py` — `build_outlook_row(..., lang="de")` reicht `lang` an `format_outlook_value`
- **File:** `src/output/renderers/email/compare_html.py` — `_build_location_outlook_rows` reicht das vorhandene `lang` weiter
- **File:** `src/services/trip_report_scheduler.py` — Trip-Ausblick: `build_outlook_row(..., lang=self._lang)`

## Known Limitations

- Himmelsrichtung (`degrees_to_compass`) und Wolkensymbol im Ausblick bleiben unverändert (sprachneutral bzw. bestehendes Verhalten).
- Telegram-/SMS-Pfade außerhalb der geteilten Ausblick-Zellen sind nicht Teil dieses Fixes.

## Acceptance Criteria

**AC-1:** Given ein Trip mit Wind, Böen und Niederschlag im Modus „Einfach“ und ein Nutzer mit Sprache Englisch / When die Trip-Briefing-Mail gerendert wird / Then zeigt die Stundentabelle die englischen Wortstufen aus dem Katalog (z. B. „moderate“, „dry“) und kein deutsches Skalenwort.

**AC-2:** Given derselbe Trip mit einem Nutzer ohne Sprachfeld oder mit Sprache Deutsch / When die Trip-Briefing-Mail gerendert wird / Then stehen die deutschen Wortstufen unverändert in der Mail und alle deutschen Golden-Dateien bleiben byte-gleich.

**AC-3:** Given ein Ortsvergleich mit Ausblick-Größen (Wind, Böen, Niederschlag, Regenwahrscheinlichkeit, Sonne) im Modus „Einfach“ und Sprache Englisch / When die Vergleichs-Mail gerendert wird / Then zeigen Klartext und HTML im 3-Tages-Ausblick englische Wortstufen und kein deutsches Skalenwort.

**AC-4:** Given derselbe Ortsvergleich mit Sprache Deutsch / When die Vergleichs-Mail gerendert wird / Then zeigt der Ausblick die deutschen Wortstufen wie bisher.

**AC-5:** Given ein Nutzer mit Sprache Englisch und ein Trip-Ausblick mit Böen und Niederschlag im Modus „Einfach“ / When der Zeitplaner das Briefing über den echten Versandpfad verschickt / Then enthält die zugestellte Mail (HTML und Klartext) englische Wortstufen und kein deutsches Skalenwort, während ein deutscher Nutzer dieselbe Mail mit deutschen Wortstufen erhält.

## Tests

- `tests/tdd/test_skalenwoerter_mail_sprache.py` (AC-1 bis AC-5, echte Renderer bzw. echter Versandpfad, kein Mock-Theater)
- Bestandsschutz: `tests/golden/email/`, `tests/golden/test_vergleichs_mail_golden.py`, `tests/tdd/test_issue_811_mode_matrix.py`
