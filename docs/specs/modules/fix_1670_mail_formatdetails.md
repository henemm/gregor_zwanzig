---
entity_id: fix_1670_mail_formatdetails
type: module
created: 2026-11-02
updated: 2026-11-02
status: draft
version: "1.0"
tags: [output, email, compare, issue-1670]
---

# Formatdetails Trips E-Mail (Issue #1670)

## Approval

- [ ] Approved

## Purpose

Das Ticket meldet: in der Trip-Mail fehlt auf dem Handy in den Pillen des Metriken-Überblicks das
Leerzeichen vor der Uhrzeit ("Max16:00"; Desktop ist in Ordnung). Dazu hängen fünf aus #1199
übertragene Grammatik-Befunde (C5-04, 07, 13, 30, 66). Die Spec behebt die zwei real vorhandenen
Fehler (Pille mobil, Platzhalter-Strich in der Compare-Mail), schließt einen kleinen real gemessenen
Fund bei C5-30 (Wind ohne Daten zeigt "0" statt "–") und hakt die übrigen drei Befunde mit Messnachweis
ab. Nichts davon ändert Inhalt oder Kanäle, nur Darstellung.

## Source

- **Schicht:** Python-Core (`src/output/renderers/...`). Kein Frontend, kein Go.
- **File:** `src/output/renderers/email/helpers.py` — `pill_html` (Z. ~1387)
- **File:** `src/output/renderers/email/compare_html.py` — `_fmt_deg/_fmt_kmh/_fmt_uv/_fmt_pop/_fmt_visibility(_overview)/_fmt_thunder/_fmt_precip_type/_fmt_metric/_render_warn_cell`, Fußzeile "nächster Versand"
- **File:** `src/output/metric_format.py` — SSoT-Konstante `_NO_VALUE` wird als öffentliches `NO_VALUE` freigegeben
- **File:** `src/output/renderers/compare_outlook_metric_ids.py` (~Z. 492), `src/output/renderers/narrow.py` (~Z. 89), `src/output/renderers/email/outlook.py` (`_ACC_KEIN_WERT`, "–"-Literale) — auf dieselbe Konstante umstellen (reine Umstellung, Zeichen ändert sich dort nicht)
- **File:** `.claude/hooks/email_spec_validator.py` (~Z. 1005, 1042) — akzeptiert `"–"` statt `"—"` als Fehlwert-Zelle
- **Identifier:** `pill_html`, `NO_VALUE`

> **Trip/Ortsvergleich-Teilung:** Der Fix an `pill_html` betrifft nur die Trip-Mail (die Pille gibt es im
> Compare nicht). Der Platzhalter ist eine EINE Konstante für beide Mails (geteilt, kein neues
> Compare-Pendant). Es entsteht keine neue Komponente.
> **Mandantentrennung:** keine Nutzerdaten bewegt, reiner Renderer, keine `user_id`-Berührung.
> **Kanäle (ADR-0095):** siehe Abschnitt "Kanalparität".

## Estimated Scope

- **LoC:** ca. +40/-15 Code, ca. +120 Test
- **Files:** 5 Code-Dateien, 1 Validator, 2 neue Testdateien, Anpassung bestehender Tests/Golden (siehe Test Plan)
- **Risiko:** niedrig bis mittel (Optik der Pille in Outlook/Gmail; viele bestehende Tests erwarten "—")

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pill_html` / `build_metrics_summary_pills` (`helpers.py`) | Code | Pillen-Darstellung (AC-1, AC-2) |
| `output.metric_format.NO_VALUE` | Konstante | einziger Platzhalter der Compare-Mail (AC-3, AC-4) |
| `email_spec_validator.py` | Hook | akzeptiert „–“ als Fehlwert (AC-4) |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; ADR-0095 (Kanal-Parität) bleibt gewahrt
- **Rationale:** reine Darstellungs-Korrektur im E-Mail-HTML (Pille, Platzhalterzeichen) ohne neue Entscheidungsfläche; SMS/Telegram/Premium-SMS bleiben unberührt.

## Messungen und Entscheidungen (Befund je Punkt, mit Nachweis)

Gemessen am 2026-11-02 im Worktree mit echten Renderern (`render_compare_html`, `build_outlook_row`,
`render_outlook_table`, `render_outlook_plain`, `pill_html`) auf echten `ForecastDataPoint`-/`LocationResult`-Objekten.

| Punkt | Messung | Entscheidung |
|---|---|---|
| (a) Pille | `pill_html` liefert `display:inline-flex;align-items:center`; einziger Aufrufer `html.py:1302`; Pillen liegen in einem Flex-Container (`html.py:1304`, `display:flex;gap:6px;flex-wrap:wrap`). Quelltext der Labels enthält das Leerzeichen ("Max 11:00"). | FIX (AC-1, AC-2). Pille wird `inline-block` mit `vertical-align:middle`. |
| C5-13 EM/EN DASH | Compare-Mail mit 3 Orten (einer ohne Daten), gerendert: 220 Zellen mit "—" (Übersicht, Stundentabellen, Tagestabellen, Warn-Zelle) und 12 Zellen mit "–" (Ausblick, aus `compare_outlook_metric_ids.py`/`outlook.py`) in DERSELBEN Mail. Reale Mehrfachschreibung bestätigt. | FIX (AC-3, AC-4). |
| C5-66 `TH`-Doppelkürzel | `HAZARD_SMS_SYMBOLS` (`hazard_symbols.py:15-21`) führt seit #2417 AC-27 `TS` für amtliche Gewitter-Warnung; `TH`/`TH+` steht nur noch im Metrik-Katalog (`metric_catalog.py:492,510`, ThunderLevel) und im Radar-Alarm-Kürzel (`alert/render.py:1115`, ebenfalls Gewitter). Beide `TH` bedeuten dasselbe (Gewitter). Bestehender Wächter: `tests/tdd/test_hazard_symbols.py`, `tests/tdd/test_sms_snow_symbols.py:722`. | ERLEDIGT durch #2417, nur abhaken. Kein neuer Code, kein neuer Test. |
| C5-04 `@4` vs `04:00` | Ausblick-HTML-Zelle zeigt tatsächlich `mittel @14` und für Stunde 4 `mittel @4` (ungepaddet); die Pille zeigt `ab 04:00`/`Max 04:00`. Die `@H`-Schreibweise ist bewusst die kanalübergreifende Onset-Notation (Doku in `outlook.py`-Modulkopf: HTML-Ausblick `mittel @14`, Telegram `⚡mittel@14(hoch@18)`, SMS `TH:M@14(H@18)`; Tests `test_thunder_level_word_and_onset_hour.py` binden sie). | KEIN FIX, gewollt: Tabellenzelle/Token-Form (kompakt, SMS-/Telegram-gleich, ADR-0095) gegen Satzform der Pille ("ab 04:00"). Eine Angleichung würde die Ausblick-Zelle verbreitern und die Kanalgleichheit der Onset-Notation brechen. Im Ticket abhaken. |
| C5-07 Compare mit explizitem `outlook_metrics` | Gerendert mit `metrics=[temperature, wind, gust, thunder, precipitation]`: Ausblick-HTML `Thdr | mittel @14`, Klartext `Thdr ⚡mittel@14`. Mit und ohne explizite Auswahl zeigt die Gewitter-Zelle denselben Onset (`@14`); seit #1848 A3 baut `thunder_cell_html`/`thunder_cell_plain` die Zelle in BEIDEN Zweigen aus derselben Quelle. | NICHT REPRODUZIERBAR (durch #1848 A3 erledigt). Kein Fix. Im Ticket abhaken. |
| C5-30 Wind vs. Böen | Wind (`summary.wind_max_kmh`, `_compute_wind`) und Böen (`max` über `hourly_gust`) entstehen aus DERSELBEN Punktliste: Compare `day_points`, Trip `seg_weather[*].timeseries.data` (`trip_report_scheduler.py` ~3037, `aggregate_stage` = Max über Segment-Maxima derselben Zeitreihen). Kein Fensterunterschied. Gemessen: gleiche Daten ergeben Wind 15 / Böen 25. Nur bei widersprüchlichen Rohdaten (Böen<Wind) zeigt die Mail beides unverändert (30 / 20); das ist dann Datenlage, nicht Rechenfehler. | KEIN Fenster-/Aggregat-Fix, KEINE Böen-Anhebung (eine Angleichung der Böen an den Wind würde Daten erfinden; Leitlinie "nur Daten"). ABER gemessener realer Fund: fehlen alle Windwerte, zeigt die Wind-Zelle `0` (`int(summary.wind_max_kmh or 0)`, `outlook.py` ~627), die Böen-Zelle bei fehlenden Daten `–`. "0 km/h" ist ein erfundener Wert, → FIX AC-5. |

## Acceptance Criteria

**AC-1:** Given eine Trip-Mail mit aktiviertem Metriken-Überblick und Pillen mit Uhrzeit (z. B. "Max 16:00", "ab 15:00 · …", "stärkste 14:00") / When das Mail-HTML gerendert wird / Then ist keine Pille mehr ein Flex-Container (weder `display:inline-flex` noch `display:flex` im Pillen-Stil), sie hat `display:inline-block` mit `vertical-align:middle`, und der Container um die Pillen behält seinen Abstand (`gap:6px`, `flex-wrap:wrap`), sodass sich die Pillen weiter umbrechen.

**AC-2:** Given dieselbe Trip-Mail / When der sichtbare Text jeder Pille aus dem gerenderten HTML gelesen wird / Then steht vor jeder Uhrzeit (HH:00) in der Pille ein normales Leerzeichen und der Text jeder Pille ist zeichengleich zum Stand vor der Änderung (der Fix ändert nur die Darstellung, nicht den Wortlaut); der Rot-Nachweis ist, dass der heutige Code `inline-flex` liefert.

**AC-3:** Given eine gerenderte Compare-Mail mit mindestens drei Orten, von denen einer keine Daten hat (Übersichtsmatrix, Stundentabellen, Tagestabellen, Warn-Zelle, 3-Tages-Ausblick) / When alle Tabellenzellen und Spans der ganzen Mail durchsucht werden / Then besteht keine Zelle und kein Span allein aus dem EM DASH "—"; jeder "kein Wert"-Platzhalter ist ausschließlich der EN DASH "–", derselbe Strich wie in der Trip-Mail und im Ausblick.

**AC-4:** Given die Compare-Mail in Deutsch und in Englisch / When sie gerendert wird / Then stammt der Platzhalter für "kein Wert" überall aus der einen Konstante `output.metric_format.NO_VALUE` (kein eigenes "—"- oder "–"-Literal mehr in `compare_html.py`, `compare_outlook_metric_ids.py`, `narrow.py`), und der Validator `email_spec_validator.py` behandelt `"–"` als zulässige Fehlwert-Zelle (Exit 0 gegen eine Compare-Mail mit leeren Zellen).

**AC-5:** Given ein Ausblick (Trip-Altform-Zeile und Compare ohne Spaltenauswahl) mit Tagen, für die gar keine Windwerte vorliegen / When das Ausblick-HTML gerendert wird / Then zeigt die Wind-Zelle "–" (nicht "0"), die Böen-Zelle ebenfalls "–", und bei vorhandenen Winddaten bleibt die Zelle unverändert (Wind 15 / Böen 25 bleibt 15 / 25); Wind und Böen kommen weiterhin aus derselben Punktliste, es wird kein Wert angehoben oder angeglichen.

**AC-6:** Given ein Ausblick, in dem Böen und Wind aus denselben Stunden stammen / When Wind und Böen verglichen werden / Then gilt für jede Zeile, deren Eingangsdaten Böen >= Wind je Stunde haben, im gerenderten Ausblick Böen >= Wind (Invariante als Messbeleg gegen künftiges Auseinanderlaufen der Fenster; bei Eingangsdaten mit Böen < Wind wird bewusst nichts verfälscht).

**AC-7:** Given die Befunde C5-04, C5-07, C5-66 (Abhaken, kein Code) / When die Spec umgesetzt ist / Then sind sie im Ticket #1670 mit Verweis auf den Abschnitt "Messungen und Entscheidungen" abgehakt (C5-66 erledigt durch #2417, C5-07 erledigt durch #1848 A3, C5-04 gewollte Kompaktnotation `@H` kanalübergreifend); es entsteht dafür weder Code noch ein neuer Test, die bestehenden Wächter (`test_hazard_symbols.py`, `test_thunder_level_word_and_onset_hour.py`) bleiben grün.

## Kanalparität (ADR-0095)

SMS, Telegram, Premium-SMS bleiben unberührt: Die Änderungen liegen ausschließlich im HTML der
E-Mail (`pill_html`) und im Platzhalter der Compare-HTML-Mail. Die Token-Notation `@H`, die
SMS-Kürzel (`TS`/`TH`) und alle Texte der anderen Kanäle werden nicht angefasst; die Inhalte
(welche Wetterdaten wann erscheinen) bleiben in allen vier Kanälen gleich. AC-5 betrifft nur die
HTML-Ausblick-Zelle; `_trend_note` und SMS-Wind-Tokens lesen `wind_kmh` weiter wie bisher.
Entwickler-Hinweis zu AC-5: die Anzeige "–" bei fehlendem Wind darf `format_trend_tokens`/`_trend_note`
nicht brechen; wird dafür `row["wind_kmh"]` auf `None` gesetzt, sind alle Leser davon (Token-Pfad,
Schwellen-Hintergrund `_outlook_cell_bg`) mitzuziehen, sonst nur die HTML-Zelle ändern.

## Test Plan (nach Verhalten benannt, keine Mocks, echte DTOs und Renderer)

- `tests/test_trip_mail_pille_textfluss.py` — AC-1, AC-2: echte Trip-Mail über den Renderer, Pillen per BeautifulSoup lesen.
- `tests/test_compare_mail_ein_platzhalterzeichen.py` — AC-3, AC-4: Compare-Mail (3 Orte, einer leer, de und en), alle Zellen/Spans prüfen; Konstante wird referenziert.
- `tests/test_ausblick_wind_ohne_daten_zeigt_strich.py` — AC-5, AC-6: `build_outlook_row` + `render_outlook_table` mit echten Punkten (Winddaten fehlen / vorhanden / Böen >= Wind).
- Bestehende Tests mit "—"-Erwartung nachziehen (Auswahl: `tests/tdd/test_compare_html_email.py`, `test_issue_1110_compare_mail_v2.py`, `test_compare_hour_table_columns.py`, `tests/unit/test_compare_extra_daily_metrics.py`, `test_compare_mail_metric_format_from_register.py`, `test_compare_matrix_metric_selection.py`, `test_gewitter_zelle_zusammenfassung_sprache.py`, `test_thunder_origin_four_places.py`, `tests/fixtures/compare_mail_structure_golden.json` u. a.; Fundliste per `grep` auf "—" in Compare-Tests). Statische Pillen-Fixtures (`issue_974_evening_night_mail.html`, `test_issue_833_gate.py`) sind Validator-Eingaben, kein Renderer-Ergebnis, und bleiben.

## Gates

- **Renderer-Commit-Gate (#811):** `helpers.py`/`compare_html.py`/`outlook.py` liegen unter `src/output/renderers/email/` → vor dem Commit `tests/tdd/test_issue_811_mode_matrix.py` grün UND `briefing_mail_validator.py` Exit 0 gegen eine echt zugestellte Staging-Mail (Trip-Briefing, full und compact).
- **Compare zusätzlich:** `uv run python3 .claude/hooks/email_spec_validator.py` Exit 0 gegen die echt zugestellte Staging-Compare-Mail (≥3 Orte); "E2E bestanden" für den Orts-Vergleich nur bei Exit 0 (Validator vorher auf `"–"` umgestellt, AC-4).
- Mobile Gegenprobe (AC-1/AC-2) im echten Mail-Client ist Nachsicht des PO-Screenshots, kein automatisierbares Gate; der Test prüft das Verhalten (kein Flex um den Textknoten), nicht nur eine CSS-Zeichenkette.

## Nicht-Ziele

Kein Anheben der Böen auf den Wind, keine Änderung der `@H`-Notation, keine Änderung der Klartext-/Telegram-/SMS-Platzhalter, kein Umbau von Hazard-Kürzeln.

## Changelog

- 2026-11-02: Erstfassung (Analyse + Messungen, Issue #1670).
