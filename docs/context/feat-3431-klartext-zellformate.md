# Context: feat-3431-klartext-zellformate (Issue #3431)

## Request Summary

Folge zu #3425 (Variante C, `docs/context/rework-3425-compare-bausteine.md`). Die Übersicht im
Klartext-Teil der Vergleichsmail formatiert einzelne Zellen anders als der HTML-Teil derselben Mail.
Ziel: gleiche Darstellung in beiden Teilen, ein Platzhalterzeichen für fehlende Werte (#1670).

## Gemessene Abweichungen (Ist-Stand 2026-11-27, Skript gegen `_visible_metrics(None)` vs `_PLAIN_FMT`)

| Zeile | HTML (`_fmt_metric`, Register-`unit`/`decimals`) | Klartext (`_PLAIN_FMT`) |
|---|---|---|
| `sunny_hours` | `4.0 h` | `4.0h` |
| `wind_direction_avg` | `213 °` (gerundet, `decimals=0`) | `213.4°` (ungerundet, `f"{v}°"`) |
| `cloud_low_avg` / `cloud_mid_avg` / `cloud_high_avg` | `40%` (gerundet) | `40.3%` (ungerundet, `f"{v}%"`) — **im Issue nicht genannt** |
| fehlender Wert | `–` (`NO_VALUE`, U+2013) | `-` (Literal, `comparison.py` ~301) |

Alle übrigen 19 Zeilen sind bei Testwerten 213.4 / 4.0 / 0.25 zeichengleich.
HTML-Regel (`compare_html.py:765-771`): Leerzeichen vor Einheit, außer `°C` und `%`.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/comparison.py:82-110` | `_PLAIN_FMT` — Klartext-Formate je Zeilenschlüssel |
| `src/output/renderers/comparison.py:~291-301` | Klartext-Übersichtsschleife, Platzhalter `"-"` |
| `src/output/renderers/comparison.py:132-135, 589, 700-720` | `_PLAIN_ROWS` / `_PLAIN_ROWS_BY_ID` / `_plain_metric_cell` — **dieselben Formate speisen Telegram-Vergleich** |
| `src/output/renderers/email/compact_compare.py:95-108` | Kompakt-Vergleichsmail nutzt `_PLAIN_ROWS_BY_ID`-Formate |
| `src/services/placements_view_service.py:900-909` | nutzt nur das Label (nicht das Format) |
| `src/output/renderers/email/compare_html.py:765-771` | `_fmt_metric` — HTML-Referenz |
| `src/output/metric_format.py:81` | `NO_VALUE = "–"` |

## Existing Patterns

- `format_value(metric_id, v, style=...)` aus dem Register ist die katalog-getriebene Formatierung; `_PLAIN_FMT` nutzt sie schon für Temperatur, Wind, Wolken gesamt, Schnee.
- #1670: ein Platzhalterzeichen `NO_VALUE` überall in der Vergleichsmail.

## Dependencies / Dependents

- Änderung an `_PLAIN_FMT` wirkt automatisch auch auf **Telegram-Vergleich** und **Kompakt-Vergleichsmail** (geteilte Tabelle). Entweder bewusst mitziehen (Kanal-Parität, ADR-0095) oder Klartext-Mail getrennt formatieren — Analyse-Entscheidung.
- Der Platzhalter `-` ist nur im Klartext-Mail-Pfad literal; Telegram/Kompakt lassen fehlende Zellen weg (`_plain_metric_cell` → `None`).

## Existing Specs / Tests, die den Ist-Stand pinnen (müssen bewusst angepasst werden)

- `tests/unit/test_compare_plaintext_html_rows_one_list.py:159-183` `_FORMAT_SNAPSHOT` (`4.0h`, `213°`, `40%`) — „byte-gleich halten, Angleichung nicht Teil von #3425".
- `tests/unit/test_compare_text_html_bausteine.py:292-310` AC-6-Guard: Klartext `213°`/`4.0h`, „#3431 regelt deren Angleichung".
- `tests/test_compare_mail_ein_platzhalterzeichen.py` (#1670) deckt Klartext-Compare nicht ab.
- Weitere Treffer mit `°`/`h`-Formaten u. a. `tests/tdd/test_feat_3228_windrichtung_mail.py`, `tests/unit/test_compare_mail_labels_from_register.py` — in der Analyse prüfen.

## Risks

- Sichtbare Änderung in jeder Klartext-Vergleichsmail → Renderer-Commit-Gate (Modus-Matrix-Test + `email_spec_validator.py` frisch grün).
- Unbeabsichtigte Mitänderung im Telegram-Vergleich, falls `_PLAIN_FMT` direkt geändert wird.
- Offene Produktfrage (laut Issue): Leerzeichen vor Einheit (`213 °`, `4 h`) — Specs uneinheitlich. Bei reiner HTML-Angleichung folgt sie der HTML-Regel; Frage vor der Spec klären.
- Placeholder `–` (U+2013) im Klartext unkritisch (Mail ist UTF-8); in SMS irrelevant (Orte-SMS nutzt seit #3172 Token-Zeile).

## Analysis

**Type:** Feature (Angleichung, sichtbare Formatänderung im Klartext)

**Root Cause:** Fünf Einträge in `_PLAIN_FMT` sind handgetippte Lambdas statt der katalog-getriebenen
Formatierung: `wind_direction_avg` (`f"{v}°"`), `sunny_hours` (`f"{…bare}h"`), `cloud_low/mid/high_avg`
(`f"{v}%"`). Der Platzhalter ist ein Literal `"-"` statt `NO_VALUE`.

**Gemessen:** `format_value(metric_id, v, style="plain")` liefert für alle fünf Größen bereits exakt die
HTML-Zelle (`213 °`, `4.0 h`, `40%`). Damit ist die Leerzeichen-Frage keine neue Produktentscheidung:
Der zentrale Format-Katalog (eine Quelle für alle Kanäle) setzt das Leerzeichen schon; der Klartext
weicht nur durch Handkopien ab (#1481 Anti-Duplikat). Die Stundenzeilen derselben Klartext-Mail nutzen
schon `–` für fehlende Werte; nur die Übersicht weicht ab.

### Affected Files (Change Type)

| Datei | Change | Inhalt |
|---|---|---|
| `src/output/renderers/comparison.py` | MODIFY | 5 Lambdas → `format_value(..., style="plain")`; `"-"` → `NO_VALUE`; Kommentar 79-81 aktualisieren |
| `tests/unit/test_compare_plaintext_html_rows_one_list.py` | MODIFY | `_FORMAT_SNAPSHOT`: `4.0 h`, `213 °` |
| `tests/unit/test_compare_text_html_bausteine.py` | MODIFY | AC-6-Guard: Übersichtsformate jetzt gleich statt verschieden |
| `tests/golden/vergleichs_mail/*.txt` | MODIFY | Goldens (u. a. `ortsvergleich_3orte.de.txt`, `telegram_sms.de.txt`: `Sonne 4.0 h`) neu |
| neuer TDD-Test | CREATE | Parität Klartext-Übersicht == HTML-Zelle je CV2-Zeile + Platzhalter `–` |

### Scope / Risk

~10 LoC Produktivcode, Tests/Goldens ~60 LoC. Risiko niedrig–mittel: sichtbar in Klartext-Vergleichsmail
UND (geteilte Tabelle `_PLAIN_ROWS`) im Telegram-Vergleich und der Kompakt-Vergleichsmail. Bewusst
mitgezogen: Kanal-Parität (ADR-0095), ein Format je Größe. SMS nicht betroffen (Token-Zeile, #3172).
Renderer-Commit-Gate greift (Modus-Matrix-Test + `email_spec_validator.py`).

### Technical Approach

Katalog-Formatierung wiederverwenden statt Handkopien; Platzhalter aus `metric_format.NO_VALUE`.
Gegenprobe-Test: für jede CV2-Zeile und Testwerte (inkl. Nachkommastellen) gilt Klartext-Zelle ==
HTML-Zelle (`_fmt_metric`/`fmt`), fehlender Wert == `NO_VALUE` in beiden.

Varianten:

| Variante | Produktivcode | Kanäle | Bewertung |
|---|---|---|---|
| A: `_PLAIN_FMT` auf Katalog umstellen (geteilt) | ~10 LoC | Mail-Klartext + Telegram + Kompakt gleich | **Empfohlen**: eine Quelle, Parität |
| B: nur Mail-Klartext eigene Überschreibung | ~25 LoC | Telegram behält `4.0h` | neue Parallel-Logik, verstößt #1481 |

### Open Questions

Keine offene PO-Frage: Das Leerzeichen folgt dem bestehenden zentralen Format-Katalog (HTML nutzt ihn
bereits); Freigabe erfolgt mit der Spec.
