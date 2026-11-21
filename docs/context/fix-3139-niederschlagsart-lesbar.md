# Context: fix-3139-niederschlagsart-lesbar

## Request Summary
Issue #3139: Im Trip-Telegram-Briefing (Kurzübersicht/Zeilen) erscheint die Metrik Niederschlagsart als `PT PrecipType.RAIN`. Erwartet: lesbares Wort in der Nutzersprache (DE/EN, ADR-0104), über den vorhandenen Katalog, kein Sonderweg.

## Befund (reproduziert 2026-11-21, origin/main cfdf76918)
`fmt_val('precip_type', PrecipType.RAIN, ampel={})` → `PrecipType.RAIN`, ebenso mit `html=True`.
`fmt_val` ist die gemeinsame Zellformatierung von Telegram (`narrow.py::_cell`), Trip-Mail HTML (`email/html.py:618`) und Trip-Mail Text (`email/plain.py:124/139`). Der Fehler betrifft damit **alle drei** Trip-Darstellungen, nicht nur Telegram (Kanal-Parität ADR-0095).

## Related Files
| File | Relevance |
|------|-----------|
| src/output/renderers/email/helpers.py:790 `fmt_val` | kein Zweig für `precip_type`, Endet in `str(val)` (Zeile ~957) → Ursache |
| src/output/renderers/email/helpers.py:196 / trip_report.py:669 | Row-Aufbau: `precip_type` = letzter Wert der Stunden (Enum bleibt Enum) |
| src/output/renderers/email/compare_html.py:272-283 `_fmt_precip_type` | vorhandene Darstellung Orts-Vergleich: Enum → `t("vergleich.niederschlagsart.<key>", lang)` |
| src/i18n/messages/{de,en}/vergleich.json:47-50 | Katalogtexte Regen/Schnee/Mischniederschlag/Eisregen bzw. Rain/Snow/Mixed precipitation/Freezing rain |
| src/output/renderers/narrow.py:88-103 `_cell` | Telegram-Zelle ruft `fmt_val` mit `lang` |
| src/app/models.py:50 `PrecipType`; :133 Feld `precip_type` | Enum RAIN/SNOW/MIXED/FREEZING_RAIN |
| src/app/metric_catalog.py:570 | Metrik `precip_type`, col_key `precip_type`, compact_label `PT` |
| tests/helpers/telegram_briefing_fixture.py | Golden-Fixture fürs Telegram-Briefing |

## Existing Patterns
- Gewitter (`thunder`) hat in `fmt_val` einen eigenen Wortzweig mit `lang` (thunder_label) — gleiches Muster für Niederschlagsart.
- Orts-Vergleich formatiert Niederschlagsart bereits über `_fmt_precip_type` + Katalog → wiederverwenden (eine Quelle), nicht duplizieren.
- Trip-SMS nutzt Protokoll-Kürzel (`_dominant_precip_type_code`, sms_trip.py:219) — Protokoll-Token, bleibt unberührt.

## Weitere Enum-Felder (Prüfauftrag aus Issue)
`ForecastDataPoint` hat genau zwei Enum-Felder: `thunder_level` (hat eigenen Zweig) und `precip_type` (fehlt). Keine weiteren Enum-Felder landen in `str(val)`.

## Dependencies
- Upstream: i18n `t()`, PrecipType-Enum, Katalog vergleich.json.
- Downstream: Telegram-Trip-Briefing, Trip-Mail HTML + Plain; Compare-Pfad ruft `fmt_val` ebenfalls (compare_html.py:800/805/1169), aber Niederschlagsart läuft dort über `_fmt_precip_type`.

## Existing Specs
- docs/specs/modules/telegram_output.md, feat_1260_telegram_kurzstil.md, i18n_p7_telegram_2669.md

## Risks & Considerations
- Import-Zirkel: helpers.py ↔ compare_html.py (compare_html importiert aus helpers) → lokaler Import oder Formatierer in neutrales Modul verschieben.
- HTML-Pfad: Wort muss HTML-escaped bzw. reines Wort sein (Katalogtexte ohne Sonderzeichen).
- Telegram-Zeilenbreite: „Mischniederschlag“ ist lang; Umbruch über `_wrap` vorhanden.
- Unbekannter Wert / String statt Enum → `–` (wie `_fmt_precip_type`), nie Programmname.
- Renderer-Commit-Gate (Mail-Inhalt) greift wegen Trip-Mail-Änderung.

## Analysis

### Type
Bug

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/metric_format.py | MODIFY | neue `precip_type_label(v, *, lang)` + `_PRECIP_TYPE_KEYS` (Körper aus `_fmt_precip_type`, Katalog `vergleich.niederschlagsart.*`); Schlüssel robust per `.upper()` normalisieren; None/unbekannt → `NO_VALUE` |
| src/output/renderers/email/compare_html.py | MODIFY | `_fmt_precip_type` bleibt echte `def`, delegiert an `precip_type_label` (Identitätsvergleich `fmt is _fmt_precip_type` Z. 291 + Importe comparison.py:41, compare_outlook_metric_ids.py:549 bleiben gültig) |
| src/output/renderers/email/helpers.py | MODIFY | `fmt_val`: Zweig `if key == "precip_type": return precip_type_label(val, lang=lang)` direkt nach dem `thunder`-Zweig (nach None-Check, vor Ampel-/Modus-Code) → wirkt für Telegram, Trip-Mail HTML und Plain |
| tests/tdd/test_fix_3139_niederschlagsart_lesbar.py | CREATE | RED aus Nutzersicht: Telegram-Briefing über `render_telegram_bubbles` + Golden-Fixture (DE/EN), Trip-Mail HTML + Plain; Grenzfälle None, String „RAIN“/„rain“, unbekannt |

### Scope Assessment
- Files: 3 Produktiv + 1 Test
- Estimated LoC: ca. +25 Produktiv / -10, +40–60 Test
- Risk Level: LOW (neuer Zweig für einen Schlüssel, der bisher nur Programmnamen lieferte; Compare-Ausgabe bleibt identisch)

### Technical Approach
Eine Wortquelle für Trip und Compare: Formatierer in das neutrale Modul `output/metric_format.py` verschieben (bricht den Import-Zirkel helpers ↔ compare_html), Compare-Hülle delegiert, `fmt_val` bekommt Wortzweig analog Gewitter. Katalogschlüssel bleiben `vergleich.niederschlagsart.*` (kein Duplikat-Schlüssel, keine Namensraum-Migration; i18n-Konvention „nie zwei Schlüssel für denselben Text“). Keine Ampel für Niederschlagsart; auch `format_modes=raw` liefert das Wort.

### Dependencies
i18n `t()`, `PrecipType` (str-Enum, Name == Wert). Row-Wert kommt aus helpers.py:196 / trip_report.py:669 (`values[-1]` der Stunden, Enum; über Snapshot-Roundtrip/JSON ggf. String).

### Befunde / Abgrenzung
- Es gibt drei Wortquellen für Niederschlagsart: `PRECIP_TYPE_LABEL_DE` (metric_format.py:302, Ad-hoc-Abruf), `inbound.niederschlagsart.*` (Befehlsantworten, Satzmitte klein, „Schneeregen“/„sleet“), `vergleich.niederschlagsart.*` (Zellen). Konsolidierung NICHT Scope von #3139 → Nebenbefund-Issue prüfen/anlegen.
- Telegram-Spaltenbreite `precip_type` = 35 (channel_layout.py:67); lange Wörter („Mischniederschlag“, „Mixed precipitation“) passen, Umbruch über `_wrap` im Test mit prüfen.
- Vor Fix: `grep -rn "PrecipType\.\(RAIN\|SNOW\)" tests` auf Erwartungstexte, die den Programmnamen festschreiben.
- Renderer-Commit-Gate greift (Trip-Mail-Inhalt) → Modus-Matrix-Test + `briefing_mail_validator.py` frisch grün.
- Weitere Enum-Felder in `str(val)`: keine (nur `thunder_level` mit eigenem Zweig).

### Regressionstests
tests/tdd/test_metric_format.py, tests/tdd/test_issue_811_mode_matrix.py, tests/test_vergleichs_mail_zweisprachig.py, tests/unit/test_compare_metric_parity.py, tests/tdd/test_outlook_metric_ampelfarben.py, tests/tdd/test_thunder_origin_compare.py, tests/tdd/test_adhoc_metrik_formatierung.py

### Open Questions
keine (Produktentscheidung nicht nötig: lesbares Wort in Nutzersprache ist im Issue vorgegeben)
