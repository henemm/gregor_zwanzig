# Context: refactor-2991-compare-zeilenliste

## Request Summary

Issue #2991 (Folge aus Paritäts-Bestandsaufnahme #1986, Eintrag NEU-10, nur im Issue-Body von #1986 vermerkt):
Klartext- und HTML-Vergleichsmail sollen ihre Zeilen aus EINER Zeilenliste ableiten. Die Doppelung wird zu
einem Baustein zusammengeführt; der bewachende Paritätstest bleibt als Regressionswächter. Kein Ausfall,
`priority:medium`. Reiner Umbau, kein sichtbares Verhalten soll sich ändern (Golden-Snapshot bleibt).

## Entry Points

- `render_compare_email()` `src/output/renderers/comparison.py:535` ruft `render_compare_html()`
  (`email/compare_html.py:1799`) und `render_comparison_text()` (`comparison.py:187`).
- Einziger Aufrufer: `compare_email_rendern()` `src/services/compare_briefing_aufbau.py:97`
  (Scheduler `scheduler_dispatch_service.py:948`, Vorschau `compare_preview_service.py:96`,
  `placements_view_service.py:795`, `compare_briefing_aufbau.py:199`).

## Doppelungen (Kern des Tickets)

| Zeilenentscheidung | HTML | Klartext | Stand |
|---|---|---|---|
| Übersicht: welche Zeilen, Reihenfolge | `_visible_metrics()` `compare_html.py:874` auf `build_cv2_metrics`/`CV2_ZEILEN` `:338` | eigene Tabelle `_PLAIN_ROWS_UNSORTED` `comparison.py:86-138`, `_sort_by_cv2_order` `:141`, `_ordered_rows()` `:171-184` („Semantik identisch zu _visible_metrics") | **doppelt** |
| Übersicht: Werteformat | `fmt` in `CV2_ZEILEN` bzw. `_fmt_metric` (`_render_overview_row` `:811`) | eigene Lambdas in `_PLAIN_ROWS` via `_fmt_overview_cell` `:691` | **doppelt** |
| Einfach-Form | `_friendly_overview_html` `:780` | `_friendly_overview_text` `comparison.py:664` | doppelt (teilt `_friendly_outlook_text`) |
| Labels | `derive_row_labels` | `derive_row_labels(..., form="long")` `comparison.py:331` | geteilt |
| Auswahl-Lücke | `rowless_count` gegen CV2-Keys `:1004` | `rowless_count` gegen `_PLAIN_ROWS_BY_ID` `:353` | Funktion geteilt, Schlüsselmenge doppelt |
| Stundenspalten | `_visible_hour_metrics(build_hour_metrics)` `:1223` | `_visible_hour_metrics(_hour_zeilen())` `:377` | geteilt; Zellenlogik doppelt (`:435-469` vs `_render_hour_row` `:1160`) |
| Abschnitte/Überschriften je Ort | `_render_location_section`, `_per_location` | eigener Puffer `:379-494` | doppelt (fachlich teils absichtlich unterschiedlich) |
| Legenden-Bedingung | `:1687` | `:507` | kopiert |
| Fallback, Warn-Nichtverfügbar, Reihenfolge, Befehlsblock | geteilt | geteilt | ok |

Kernpaar laut #1986 (`docs/specs/modules/paritaets_bestandsaufnahme.md:55`,
`docs/context/feature-1986-paritaets-bestandsaufnahme.md:44`): `_PLAIN_ROWS` gegen `compare_html`.

## Dependents von `_PLAIN_ROWS` (Vorsicht)

- Telegram `render_compare_telegram` `comparison.py:822`: `_plain_metric_cell` `:770` (Label-Key `vergleich.zeile.*` + fmt aus `_PLAIN_ROWS_BY_ID`), `_fmt_overview_cell`.
- `_NIE_EINGESTELLT_IDS` `comparison.py:656` (aus `_PLAIN_ROWS` abgeleitet): SMS `render_compare_sms` `:1208`, `orte_sms.py:102`, `compact_compare.py:211`, `placements_view_service.py:833`.
- `placements_view_service.py:918` importiert `_visible_metrics` direkt.

## Existing Tests

- `tests/unit/test_compare_mail_plaintext_html_label_parity.py` (#1401): Labels gleich (Übersicht + Stunden).
- `tests/unit/test_compare_metric_parity.py` (#1324): Zeilen + Werte je Fassung, kein Kreuzvergleich.
- `tests/test_compare_top_n_render_invariance.py:408` + `tests/fixtures/compare_mail_structure_golden.json`: Struktur-Snapshot beider Fassungen (Regressionsanker für reinen Umbau).
- Weitere: `test_compare_mail_blocks.py`, `test_compare_metric_default_order_ssot.py`, `test_compare_matrix_metric_selection.py`, `test_mail_metric_name_forms.py`, `tests/tdd/test_issue_1125_plaintext_metrics.py`.
- Es fehlt: ein Test, der Zeilenmenge/-reihenfolge/-werte Klartext gegen HTML direkt vergleicht.

## Existing Specs / ADRs

- `docs/specs/modules/paritaets_bestandsaufnahme.md` (#1986), Geschwister: `refactor_2989_compare_default_order_ssot.md` (NEU-8), `refactor_2990_kanal_ableitung_eine_quelle.md` (NEU-9).
- `compare_metric_parity.md`, `fix_1401_a2_mailtabellen.md`, `compare_briefing_aufbau.md`, `feat_3039_vergleich_kanal_layouts.md`, `feat_3390_ortsvergleich_telegram_zeilen.md`.
- ADR-0127 (ein Katalog, eine Verarbeitung), ADR-0042 (Namensform folgt Platzgrenze), ADR-0068, ADR-0095.

## Risks

- Mail-Inhalt: Renderer-Commit-Gate + Golden-Snapshot; Ausgabe muss byte-gleich bleiben (Klartext `"-"` vs HTML `NO_VALUE`, Dedup-Unterschiede bewusst erhalten).
- `_PLAIN_ROWS` speist Telegram/SMS/Compact/Placements: Umbau darf deren Ausgabe nicht ändern.
- Scope-Grenze ±250 LoC: Abschnitts-/Stundenzellen-Doppelung evtl. als Folge-Issue abtrennen; Kern = Übersichtszeilen (Liste, Reihenfolge, Format, Auswahl-Lücke).

## Analysis

### Type
Refactor (Doppelung beseitigen, #1986 NEU-10). Kein Bug, kein neues Feature.

### Format-Vergleich Klartext vs HTML (Übersicht, 25 Zeilen)
Gleich bei 22 Zeilen. Abweichend, bewusst erhalten (reiner Umbau):
- `wind_direction_avg`: Klartext `213°`, HTML `213 °` (`_fmt_metric` setzt Leerzeichen bei Einheit ≠ °C/%).
- `sunny_hours`: Klartext `4h`, HTML `4 h`.
- Fehlender Wert: Klartext `-`, HTML `NO_VALUE` (`–`).
LocationResult-Felder `wind_direction_avg`, `cloud_*_avg`, `sunny_hours` sind `Optional[int]` (keine Roh-Floats).

### Varianten (Plan-Agent, Schätzung)
| | A: eine Zeilenliste + ein Filter, Klartext-Format je Schlüssel | B: A + gemeinsamer Zellformatter | C: A + Stundenzellen/Abschnitte |
|---|---|---|---|
| Prod-Dateien | 2–3 | 4–5 | 5–6 |
| Netto-LoC | ca. −60 bis −90 | ca. −80 | > +250 (Grenze gerissen) |
| Sichtbar | nur: HTML zeigt doppelte IDs nicht mehr doppelt | `213 °`/`4 h` in Klartext, Telegram, Compact; Golden ändert sich | Risiko Stunden-/Abschnittslogik |
| Risiko | niedrig | mittel (Telegram-Breite, ADR-0042) | hoch |

### Entscheidung (Tech Lead): Variante A
1. **Ein Filter** `select_cv2_rows(rows, enabled_metrics)` in `compare_html.py` (aus `_visible_metrics` herausgezogen): `None` → alle, `[]` → keine, `warn` raus, Duplikate per `dict.fromkeys` entfernt, unbekannte IDs übersprungen. `_visible_metrics` nutzt ihn und stellt die Warnzeile voran.
2. **Klartext** nimmt `select_cv2_rows(CV2_ZEILEN, enabled_metrics)` als Zeilenliste (ersetzt `_ordered_rows(_PLAIN_ROWS, …)` + `_CV2_BY_KEY`-Nachschlag an `comparison.py:330`).
3. **Klartext-Format** wird reine Zuordnung `_PLAIN_FMT: dict[key, fmt]` (keine eigene Reihenfolge, keine Label-Spalte). Import-Check: Schlüsselmenge == CV2-Schlüssel ohne `warn` (ersetzt Fail-fast von `_sort_by_cv2_order`).
4. **Abgeleitete Sichten bleiben** für Telegram/Compact/SMS/Placements unverändert: `_PLAIN_ROWS` = `tuple((k, f"vergleich.zeile.{k}", _PLAIN_FMT[k]) for k in CV2-Schlüssel ohne warn)`, `_PLAIN_ROWS_BY_ID`, `_NIE_EINGESTELLT_IDS`.
5. **Auswahl-Lücke**: beide Pfade zählen `rowless_count` gegen dieselbe Schlüsselmenge (CV2 ohne `warn`).
6. Entfallen: `_PLAIN_ROWS_UNSORTED`, `_DAILY_PLAIN_ROWS` (als Teilliste), `_sort_by_cv2_order`, `_ordered_rows`.

**Dedup:** `_visible_metrics` dedupliziert heute NICHT (`compare_html.py:903`), `_ordered_rows` schon. Gemeinsamer Filter dedupliziert → einzige sichtbare Änderung: HTML zeigt eine doppelt gespeicherte Metrik nur noch einmal (wie Klartext, Telegram, SMS, `rowless_count` bereits). Begründet, kein PO-Thema.

**Nicht drin (Folge-Issue anlegen):** Stundenzellen-Schleife (`comparison.py:435-469` vs `_render_hour_row`), Abschnitts-/Überschriftenlogik je Ort, Legenden-Bedingung, Einfach-Form-Doppel (`_friendly_overview_text`/`_html`), Format-Angleichung `°`/`h`/`-`.

### Affected Files
| Datei | Change |
|---|---|
| `src/output/renderers/email/compare_html.py` | MODIFY: `select_cv2_rows` neu, `_visible_metrics` nutzt ihn, Docstring `rowless_count`/`:911` |
| `src/output/renderers/comparison.py` | MODIFY: `_PLAIN_FMT`, abgeleitete `_PLAIN_ROWS`, Zeilenwahl `:330`, `rowless_count` `:353`; Löschen der Alt-Mechanik |
| `tests/unit/test_compare_metric_default_order_ssot.py` | MODIFY: Tests auf `_sort_by_cv2_order`/`_PLAIN_ROWS_UNSORTED` auf neuen Import-Check umstellen |
| `tests/unit/test_compare_plaintext_html_rows_one_list.py` | CREATE: Klartext-Zeilen == HTML-Zeilen (Menge+Reihenfolge) für `None`, `[]`, Teilmenge, Duplikat, unbekannte ID, `warn`; gleiche Auswahl-Lücke; `_NIE_EINGESTELLT_IDS` == CV2-Schlüssel ohne warn (len ≥ 20) |
| ggf. `tests/helpers/compare_order.py`, `tests/tdd/test_channel_metric_matrix.py` | nur falls Importe brechen (Sichten bleiben, daher voraussichtlich nicht) |

### Scope / Risk
2 Prod-Dateien, ca. −60 bis −90 LoC netto, Tests ca. +80. Risiko niedrig–mittel (Mail-Inhalt, Renderer-Commit-Gate). Regressionsanker: Golden-Snapshot `tests/fixtures/compare_mail_structure_golden.json` (`tests/test_compare_top_n_render_invariance.py`), Label-Paritätstest `tests/unit/test_compare_mail_plaintext_html_label_parity.py`, `tests/tdd/test_channel_metric_matrix.py` (Telegram).

### Open Questions
Keine PO-Fragen (reiner Umbau, ohne sichtbare Änderung außer Dedup).
