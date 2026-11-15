---
entity_id: i18n_skalenwoerter_lang_2784
type: bugfix
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: fix-2784-skalenwoerter-lang
tags: [i18n, epic-2644, issue-2784, python, telegram, alert, bug]
---

# Stufenwörter in Telegram-Briefing und Alarm-Stundenzeilen folgen der Nutzersprache (#2784)

**Issue:** #2784 (Nebenbefund aus #2750) · **Epic:** #2644 · **ADR:** 0104 · **Konventionen:** `docs/reference/i18n_konventionen.md`

## Approval

- [ ] Approved

## Purpose

Nutzer mit Sprache Englisch sehen im Telegram-Briefing (Stil `rich`) und in den Alarm-Stundenzeilen (Mail Klartext und HTML, Telegram-Alarm) noch deutsche Stufenwörter („leicht", „kein", Wind-/Regen-Adjektive im Modus „Einfach"). Die Formatierer (`fmt_val`, `thunder_label`, `format_wind_strength`, `format_precip_intensity`) sind bereits sprachfähig; die Aufrufer reichen `lang` nicht durch. Der Fix reicht `lang` durch (Muster #2750). Deutsch bleibt byte-gleich, Protokoll-Token (`TH`, `VS`, `FZ`, `Zt`, `sms_code`, `compact_label`) bleiben unberührt. *Richtigstellung (#3014):* „Zt“ war hier fälschlich als sprachneutrales Protokoll-Kürzel geführt; es ist Nutzertext und folgt seit #3014 der Kontosprache (Englisch „Hr“), siehe `docs/specs/modules/i18n_zt_kopf_sprache_3014.md`.

## Source

- **File:** `src/output/renderers/narrow.py` — `_cell`, `_narrow_table`, `_overview_line`, `_tg_day_footer` (Segment-Tabellen, Kurzübersicht, Fußzeile)
- **File:** `src/output/renderers/alert/hours.py` — `format_cell`, `row_parts`
- **File:** `src/output/renderers/alert/render.py` — `_hour_lines`, `_hours_html` (reichen `lang` an `row_parts`)

> Schicht: Python-Core (`src/output/renderers/`). Kein Frontend, keine Go-API, keine Nutzerdaten-Bewegung (keine Mandantentrennung betroffen). Trip/Vergleich-Pendant: die Renderer-Pfade sind bereits geteilt, keine Neuanlage.
> Kanäle: Telegram (Briefing und Alarm) und E-Mail (Alarm) betroffen. SMS und Premium-SMS tragen nur Protokoll-Token und bleiben unverändert.

## Estimated Scope

- **LoC:** ca. +25/-8 Source, ca. +60 Tests
- **Files:** 3 Source, 1 Golden, 1 neue Testdatei
- **Effort:** low

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/narrow.py | MODIFY | `_cell`, `_narrow_table`, `_overview_line` mit `*, lang: Lang = "de"`; `fmt_val(..., lang=lang)`; `thunder_label(x, lang=lang)` statt `THUNDER_LABEL_DE[x]` in Fußzeile und Kurzübersicht; Aufrufer reichen `lang` |
| src/output/renderers/alert/hours.py | MODIFY | `format_cell`/`row_parts` mit `lang: Lang = "de"`, an beide `fmt_val`-Aufrufe |
| src/output/renderers/alert/render.py | MODIFY | `row_parts(..., lang=lang)` in `_hour_lines`/`_hours_html` |
| tests/golden/telegram_briefing/briefing_normalstil.en.txt | MODIFY | kontrolliert nachziehen (`leicht`/`kein` zu EN); Ausblick-Gewitter bleibt deutsch |
| tests/tdd/test_2784_skalenwoerter_lang.py | CREATE | rote Nutzersicht-Tests mit echtem Renderer |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fmt_val` (`src/output/renderers/email/helpers.py`) | function | nimmt `lang` bereits, reicht an Skalenwort-Funktionen weiter (unverändert) |
| `thunder_label` (`src/app/thunder_scale.py`) | function | `thunder_label(level, lang=)` liefert `THUNDER_LABEL_EN`/`_DE` |
| `format_wind_strength`, `format_precip_intensity` (`src/services/weather_metrics.py`) | function | EN-Wörter aus Katalog `api.skala.*`, kein Katalog-Zuwachs |
| `tests/helpers/telegram_briefing_fixture` | test helper | echte Briefing-Fixture für `build_texts(lang="en")` |

## Implementation Details

`lang` wird keyword-only mit Default `"de"` bis zum Formatierer durchgereicht. `thunder_label(level, "de")` liest dieselbe Tabelle wie `THUNDER_LABEL_DE`, daher ist die deutsche Ausgabe byte-gleich. Die Pfade für Datenlücke (`?`) und Hagel bleiben unverändert, nur die Wortquelle wechselt. Fußzeile, Kurzübersicht und Segment-Tabelle verwenden dieselbe Sprache (kein Mischtext). Bestehende Direktaufrufer von `_narrow_table`/`_overview_line`/`row_parts`/`format_cell` (z. B. `tests/tdd/test_telegram_felt_temperature_overview.py`) bleiben über den Default grün.

Reihenfolge: RED-Tests, dann `hours.py` + `render.py`, dann `narrow.py`, dann Golden en geprüft nachziehen, dann Ratsche `tests/test_i18n_ratsche_narrow_telegram.py`, Modus-Matrix und Validator.

## Expected Behavior

- **Input:** Telegram-Briefing `rich` bzw. Änderungs-Alarm mit Stundenzeilen für einen Nutzer mit Sprache `en` oder `de`.
- **Output:** Bei `en` englische Stufenwörter, bei `de` unveränderte deutsche Ausgabe.
- **Side effects:** keine.

## Test Plan

### Automated Tests (TDD RED)

Echter Renderer, kein Mock-Theater.

- [ ] Test 1: GIVEN Briefing-Fixture, Sprache en, Stil rich / WHEN `build_texts(lang="en")` / THEN Fußzeile, Kurzübersicht und Segment-Tabellen enthalten kein „leicht"/„kein", Fußzeile trägt das englische Gewitter-Stufenwort, `TH`/`VS`/`FZ` bleiben.
- [ ] Test 2: GIVEN Alarm-Stundenzeilen, Sprache en, Modus simplified / WHEN Mail (Klartext + HTML) und Telegram-Alarm gerendert / THEN englische Wind-/Regen-Adjektive, keine deutschen.
- [ ] Test 3: GIVEN Alarm-Stundenzeile mit Gewitter, Sprache en / WHEN gerendert / THEN englisches Stufenwort.
- [ ] Test 4: GIVEN dieselben Eingaben, Sprache de / WHEN gerendert / THEN byte-gleich (bestehende Goldens `tests/golden/`, `tests/golden/test_telegram_briefing_golden.py`, Alarm-Tests).
- [ ] Test 5: GIVEN Telegram-Briefing en und Kurzform / WHEN gerendert / THEN Kurzform-Token und Ausblick-Gewitterzelle unverändert (deutsch, #2665).

### Renderer-Gate (Risiko)

`alert/render.py` und `hours.py` sind Mail-Inhalts-Dateien: Der Commit wird vom Renderer-Commit-Gate geblockt, bis Modus-Matrix-Test (`tests/tdd/test_issue_811_mode_matrix.py`) und der zuständige Mail-Validator gegen echt zugestellte Staging-Mail frisch grün sind. Das ist fest in Ablauf und Aufwand einzuplanen. Zusätzlich: Ratsche `tests/test_i18n_ratsche_narrow_telegram.py`.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch und ein Telegram-Briefing im Stil `rich` mit Gewitterstufe / When das Briefing gerendert wird / Then zeigen Fußzeile, Kurzübersicht und Segment-Tabellen das englische Stufenwort und kein deutsches Stufenwort („leicht", „kein"), während die Kürzel TH, VS und FZ unverändert bleiben.
  - Test: echter Briefing-Renderer mit `build_texts(lang="en")`, Prüfung auf Nutzertext ohne deutsche Stufenwörter und mit englischem Wort in der Fußzeile.

- **AC-2:** Given ein Nutzer mit Sprache Englisch, ein Änderungs-Alarm mit Stundenzeilen und Anzeige-Modus „Einfach" / When der Alarm als Mail (Klartext und HTML) und als Telegram-Nachricht gerendert wird / Then stehen in den Stundenzeilen englische Wind- und Regen-Adjektive und kein deutsches Skalenwort.
  - Test: echter Alarm-Renderer über alle drei Ausgaben, Modus simplified, Sprache en.

- **AC-3:** Given ein Nutzer mit Sprache Englisch und eine Alarm-Stundenzeile mit Gewitter / When der Alarm gerendert wird / Then zeigt die Zeile das englische Gewitter-Stufenwort statt des deutschen.
  - Test: echter Alarm-Renderer mit Gewitter-Stunde, Sprache en.

- **AC-4:** Given ein Nutzer mit Sprache Deutsch oder ohne Sprachfeld / When Telegram-Briefing und Alarm-Stundenzeilen gerendert werden / Then bleibt die Ausgabe byte-gleich zu vorher, alle deutschen Golden-Dateien und bestehenden Alarm-Tests bleiben grün.
  - Test: bestehende Goldens und Alarm-Tests unverändert, plus direkter de-Vergleich im neuen Test.

- **AC-5:** Given ein Nutzer mit Sprache Englisch und Telegram-Stil Kurzform sowie ein Briefing mit Ausblick-Gewitterzelle / When das Briefing gerendert wird / Then bleiben die Kurzform-Token und der Gewitterteil der Ausblick-Zeile unverändert (bewusst deutsch, Entscheidung #2665).
  - Test: echter Renderer, Kurzform- und Ausblick-Zeile gegen Bestandswert geprüft.

## Definition of Done

- AC-1 bis AC-5 erfüllt, RED-Tests vorher rot und nachher grün belegt.
- Golden `briefing_normalstil.en.txt` kontrolliert nachgezogen, de-Goldens unverändert.
- Modus-Matrix-Test, i18n-Ratsche und zuständiger Mail-Validator frisch grün (Renderer-Gate).
- Mutationsproben des Adversary rot nachgewiesen; alle 6 CI-Checks am PR grün.
- Staging-Verifikation bestanden, Prod-Deploy mit Selftest-Exit 0, #2784 danach geschlossen.

## Known Limitations

- Nicht im Umfang: Gewitterteil der Ausblick-Zeile im Telegram (`thunder_cell_telegram`, `src/output/renderers/email/thunder_branch.py`) bleibt nach #2665 bewusst sprachunabhängig deutsch; keine stille Umkehr ohne neue Entscheidung. Im Golden-Kommentar vermerken.
- Nicht im Umfang: `degrees_to_compass` (`src/utils/geo.py`). Alle Aufrufer nutzen den Default `en` (N/NE/E), für `en` korrekt; eine deutsche Variante würde die `de`-Ausgabe aller Kanäle ändern und ist eine eigene Produktfrage.
- Nicht im Umfang: Trend-Tabelle in `src/output/renderers/email/helpers.py` (Z. 938-952).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue, folgt ADR-0104
- **Rationale:** Reine Umsetzung der bestehenden Entscheidung (Nutzertext sprachabhängig, Protokoll-Token nie übersetzt); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-15: Initial spec created (Issue #2784)
- 2026-11-15: Pflicht-Sektion Definition of Done ergänzt (CI-Spec-Gate)
- 2026-11-15: Richtigstellung: "Zt" ist kein Protokoll-Kürzel, folgt der Kontosprache (Issue #3014)
