# Context: fix-2210-mail-renderfehler

## Request Summary
#2210 (aus Triage #1199): vier Renderfehler in zugestellten Mails — englischer Wochentag in der Klartext-Kopfzeile der Vergleichs-Mail, negative Temperaturspannen `-12–-4°C`, Gewitter „0 %" in der Mobil-Stundenliste, Stundentabelle als leeres Gerüst bei abgewählten Metriken.

## Befund je Eintrag (Stand origin/main 906731153)
| ID | Fundstelle (aktuell) | Status |
|----|----------------------|--------|
| C2-52 | `src/output/renderers/comparison.py:226` — `target_date.strftime('%A, %d.%m.%Y')` im `de`-Zweig; `en`-Zweig nutzt schon `fmt_weekday`/`fmt_date_numeric` (`src/i18n/format.py:37`). Kommentar im Code: „de: bisheriger strftime-Ausdruck unveraendert (Golden, Spec Known Limitations)" → Golden-Tests/Spec pinnen evtl. den Ist-Stand, in /20-analyse prüfen. | echter Fehler |
| C2-79 | `src/output/renderers/email/helpers.py:1533` (`format_temp_span`, Aufrufer `helpers.py:1558`, `compact_summary.py:380`) und `_range_pill` (`helpers.py:1493`, gleiche Formel `min–max`). Negative Werte lesen sich als `-12–-4`. | echter Fehler; Darstellung ist Designentscheidung (Spec) |
| C3-35 | `src/output/renderers/email/html.py:311 _render_mobile_hour_list` — **ohne Aufrufer** (grep src/tests: nur Definition). Mehrere Specs nennen sie „toter Code" (`fix_1794_arome_precip_prob_null.md:72`, `ampel_schwellen_renderer.md:398`, `fix_1418...:248`). Kein nutzersichtbarer Fehler; die Mobil-Ansicht läuft über `_render_mobile_compact_rows` → `_render_html_table` (Gewitter dort als Enum, `html.py:801`). | toter Code → Rückbau statt Fix (Spec entscheidet) |
| C3-41 | `html.py:909 _allowed_col_keys_for_horizon` liefert bei komplett abgewählten Metriken bereits eine leere Menge (#1405 S3, AC-24). Aber `_render_html_table` (`html.py:~657`) zeichnet bei leerer Spaltenmenge trotzdem ein `Time`+`Risk`-Gerüst; nur `_render_mobile_compact_rows` (`html.py:~880`) bricht bei `not cols` mit `""` ab. Aufrufe mit `allowed_keys` an `html.py:1201/1212/1255/1272`. | vermutlich echter Fehler im Desktop-Pfad; in Analyse per Renderaufruf belegen |

## Existing Patterns
- i18n-Helfer `fmt_weekday`/`fmt_date_numeric` in `src/i18n/format.py` (de+en, kein Locale-Abhängigkeit).
- Gemeinsame Spannenformel `format_temp_span` — wird von Kachel und Kurzzusammenfassung benutzt (eine Änderung wirkt auf beide).
- „Abgewählt heißt abgewählt" (#1405 S3).

## Dependencies / Dependents
- Upstream: `i18n.format`, `get_metric`/Metrikregister, `UnifiedWeatherDisplayConfig`.
- Downstream: Trip-Briefing-Mails (full/compact), Vergleichs-Mail (Klartext), `compact_summary.py`.

## Existing Specs
`docs/specs/modules/` : `briefing_mail_inhalt.md`, `fix_1794_arome_precip_prob_null.md`, `ampel_schwellen_renderer.md`, `fix_1405_s*`, `compare_*`; `docs/reference/mail_validators.md`, `renderer_email_spec.md`.

## Risks & Considerations
- Renderer-Commit-Gate: Änderungen an Mail-Inhalts-Dateien brauchen frischen Modus-Matrix-Test + Validator (Orts-Vergleich: `email_spec_validator.py`; Trip: `briefing_mail_validator.py`).
- Golden-Tests zum Wochentag könnten den englischen Ist-Stand festschreiben.
- Format der negativen Spanne ist Produktfrage (Vorschlag: „−12 bis −4°C" bzw. `-12…-4`) — Spec-Vorschlag, keine PO-Rückfrage nötig, sofern an bestehende Konventionen angelehnt.
- C3-35: Rückbau toter Funktion + ggf. Spec-Verweise; Mutations-Gegenprobe sinnlos für toten Code → Entfernung durch „kein Aufrufer"-Test absichern.

## Analysis

### Type
Bug (vier Renderfehler, Sammel-Issue #2210)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/comparison.py:224-227 | MODIFY | de-Zweig: `fmt_weekday(target_date,'de',kurz=False)` + `fmt_date_numeric(...,'de')` statt `strftime('%A, %d.%m.%Y')` (C2-52); Sprach-Zweig entfällt, beide Sprachen über i18n-Helfer |
| src/output/renderers/email/helpers.py:1533 `format_temp_span` | MODIFY | Negative Werte: Trennwort statt Bindestrich-Kollision, z. B. `-12 bis -4°C` (C2-79); wirkt auf Kachel (helpers.py:1558) UND Kurzzusammenfassung (compact_summary.py:380) |
| src/output/renderers/email/html.py:311 `_render_mobile_hour_list` | DELETE | Funktion ohne Aufrufer (grep src/tests), Specs nennen sie „toter Code" -> Rückbau (C3-35); kein nutzersichtbarer Fehler |
| src/output/renderers/email/html.py:~665 `_render_html_table` | MODIFY | Bei `allowed_col_keys` gesetzt und `cols` leer: `""` zurückgeben, wie `_render_mobile_compact_rows` (C3-41, „abgewählt heißt abgewählt"); Aufrufer 1199/1253/1304 prüfen, dass `""` keine Folgefehler macht |
| docs/specs/modules/ (neue Spec fix_2210_...) | CREATE | ACs auf Deutsch |
| tests/ (neue Testdatei) | CREATE | RED-Tests aus Nutzersicht |

### Befunde der Analyse
- `_range_pill` (helpers.py:1493) bedient nur Nicht-Temperatur-Größen (Wolken %, ...), nie negative Werte -> **kein Änderungsbedarf**; Eintrag C2-79 betrifft allein `format_temp_span`.
- C2-52: Kommentar „Golden, Spec Known Limitations" im Code; in der Compare-Spec fand sich kein Eintrag, der den englischen Wochentag festschreibt. Golden-Tests mit `Monday` in tests/ nicht gefunden (nur Fixtures fremder Feeds). Beim Anpassen vorhandene de-Golden prüfen.
- C3-41: im Code belegt: bei leerem `cols` baut `_render_html_table` weiter Kopf mit `Time`+`Risk`. Per Renderaufruf in der Spec-/TDD-Phase rot nachzuweisen.
- C3-35: nur Rückbau; Absicherung durch „kein Aufrufer/Symbol existiert nicht"-Test (# doc-compliance-test).

### Scope Assessment
- Files: 3 Source + 1 Spec + 1-2 Tests
- Estimated LoC: +40 / -110 (Löschung der toten Funktion überwiegt)
- Risk Level: MEDIUM — `format_temp_span` ist geteilt (Kachel + Kurzzusammenfassung), Mail-Inhalts-Dateien lösen Renderer-Commit-Gate aus (Modus-Matrix-Test + `briefing_mail_validator.py` bzw. `email_spec_validator.py` frisch grün)

### Technical Approach
Vier kleine, unabhängige Korrekturen in einem Workflow. Negativformat: Spanne `lo bis hi°C` nur wenn mindestens ein Wert negativ ist, sonst unverändert `lo–hi°C` (keine Änderung für Plusgrade, minimale Golden-Wirkung). Wochentag über vorhandene i18n-Helfer.

### Dependencies
`i18n.format`, `format_temp_span` (Kachel + compact_summary), `visible_cols`, Metrikregister; Downstream Trip-Briefing full/compact, Vergleichs-Mail Klartext.

### Open Questions
- [ ] Keine PO-Rückfrage nötig (Darstellung `-12 bis -4°C` als Spec-Vorschlag, an Konvention „bis" angelehnt).
