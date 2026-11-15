# Context: fix-2784-skalenwoerter-lang

## Request Summary
Issue #2784 (Nebenbefunde aus #2750, Epic #2644 i18n, zugeordnet Epic #2731): Für Nutzer mit
Sprache `en` erscheinen im Telegram-Briefing (`rich`) und in den Alarm-Stundenzeilen noch deutsche
Stufenwörter (`leicht`, `kein`, Wind-/Regen-Adjektive im Modus „Einfach“). Drei Punkte prüfen und
beheben; `de` bleibt byte-gleich.

## Befund je Punkt (mit Beleg)

### Punkt 1 — Gewitter-Stufenwort im Telegram-Briefing (`rich`)
Golden `tests/golden/telegram_briefing/briefing_normalstil.en.txt` zeigt `TH leicht`,
`Air mass leicht` und `kein`/`leicht` in den Segment-Tabellen. Drei getrennte Ursachen in
`src/output/renderers/narrow.py`:
- Fußzeile `_tg_day_footer` (Z. 279/281): `THUNDER_LABEL_DE[...]` hart, obwohl `lang` vorhanden.
- Kurzübersicht `_overview_line` (Z. 574/576): `THUNDER_LABEL_DE[...]` hart; `_overview_line`
  bekommt kein `lang`.
- Segment-Tabellen `_narrow_table` → `_cell` (Z. 86–91) und Kurzübersicht (Z. 530/531):
  `fmt_val(...)` ohne `lang` → Default `"de"`.

**ADR-0104-Prüfung:** Nie übersetzt wird nur die Kurzform (Token-Zeile) von SMS/Premium-SMS/Telegram
(`telegram_style == "kurzform"`, `docs/reference/telegram_format.md` Z. 13) sowie Protokoll-Token
(`compact_label` wie `TH`, `sms_code`). Das `rich`-Briefing ist sprachabhängig (Katalog `telegram.*`,
#2669); das Stufenwort ist kein Token, sondern Nutzertext → übersetzen. `thunder_label(level, lang=)`
(`src/app/thunder_scale.py:319`) liefert `THUNDER_LABEL_EN`. Kürzel `TH`, `VS`, `FZ` bleiben.

**Bewusst NICHT im Umfang:** Gewitterteil der Ausblick-Zeile im Telegram (`thunder_cell_telegram`,
`src/output/renderers/email/thunder_branch.py:243`) — dort wurde in #2665 ausdrücklich „bleibt
sprachunabhängig deutsch“ entschieden; keine stille Umkehr ohne neue Entscheidung.

### Punkt 2 — `fmt_val` ohne `lang` in `narrow.py` und `alert/hours.py`
- `narrow.py`: siehe Punkt 1 (dieselbe Ursache).
- `src/output/renderers/alert/hours.py`: `format_cell` (Z. 152–171) ruft `fmt_val` ohne `lang`;
  `row_parts` (Z. 179) hat kein `lang`. Aufrufer `_hour_lines`/`_hours_html` in
  `src/output/renderers/alert/render.py` (Z. 1531/1545) haben `lang` bereits und rufen
  `row_parts` ohne. Wirkung bei `en`: Gewitterstufe (`fmt_val` thunder-Zweig → `thunder_label`)
  und im Modus „simplified“ Wind-/Regen-Adjektive (`format_wind_strength`/`format_precip_intensity`)
  deutsch — in Alarm-Mail (Klartext + HTML-ROH) und Alarm-Telegram.
- Andere `fmt_val`-Aufrufer (`email/html.py:606`, `email/plain.py:84/99`) reichen `lang` bereits.

### Punkt 3 — Himmelsrichtung `degrees_to_compass` (Default `en`)
`src/utils/geo.py:60`: alle Aufrufer im Produkt (Mail, Telegram, SMS, Vergleich, Befehle) nutzen
den Default `en` (N/NE/E/…), auch für `de`-Nutzer. Für `en` ist die Ausgabe damit bereits korrekt.
Eine Umstellung auf deutsche Richtungen (O/NO) für `de` würde die `de`-Ausgabe aller Kanäle
ändern (Verstoß gegen „de byte-gleich“, Epic-weit) und ist eine eigenständige Produktfrage, nicht
Teil dieses Bugs. Ergebnis: kein Code-Befund für `en`; keine Änderung.

## Related Files
| File | Relevance |
|------|-----------|
| src/output/renderers/narrow.py | Fußzeile, Kurzübersicht, Segment-Tabelle: `lang` durchreichen |
| src/output/renderers/alert/hours.py | `format_cell`/`row_parts`: `lang`-Parameter |
| src/output/renderers/alert/render.py | `_hour_lines`/`_hours_html`: `lang` an `row_parts` |
| src/output/renderers/email/helpers.py | `fmt_val` (unverändert, nimmt `lang` schon) |
| src/app/thunder_scale.py | `thunder_label(level, lang=)` |
| tests/golden/telegram_briefing/briefing_normalstil.en.txt | Golden en, wird nachgezogen |
| tests/golden/test_telegram_briefing_golden.py | Golden-Test |
| tests/test_i18n_ratsche_narrow_telegram.py | i18n-Ratsche Telegram (Umlaut/Katalog-Fragmente) |

## Existing Patterns
- `lang: Lang = "de"` als Keyword-Parameter, Durchreichen bis zum Formatierer (#2750-Muster).
- `thunder_label(level, lang=lang)` statt `THUNDER_LABEL_DE[level]`.

## Dependencies
- Upstream: `fmt_val`, `thunder_label`, `format_wind_strength`, `format_precip_intensity`.
- Downstream: Telegram-Briefing (rich), Änderungs-Alarm (Mail Klartext/HTML, Telegram).

## Existing Specs
- `docs/specs/modules/i18n_p7_telegram_2669.md` (Telegram i18n)
- Spec zu #2750 (Skalenwörter) als Vorbild

## Risks & Considerations
- Renderer-Gate: Mail-Inhalts-Commit (alert/render.py, hours.py) braucht Modus-Matrix-Test +
  Validator frisch grün.
- `de` muss byte-gleich bleiben (Golden de, bestehende Tests).
- Hagel-/`?`-Datenlücken-Pfade in Fußzeile/Übersicht unverändert lassen (nur Wortquelle tauschen).
- Kürzel (`TH`, `VS`, `FZ`, `Zt`) sind Protokoll-Token und bleiben.

## Analysis

### Type
Bug (i18n-Lücke: `lang` wird an Formatierer nicht durchgereicht)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/narrow.py | MODIFY | `_cell`, `_narrow_table`, `_overview_line` bekommen `*, lang: Lang = "de"`; `fmt_val(..., lang=lang)` an Z.91, 530/531 und den vier `_cell`-Aufrufen in `_overview_line` (Z.539/540, 594/596); `THUNDER_LABEL_DE[x]` → `thunder_label(x, lang=lang)` in `_tg_day_footer` (Z.279/281) und `_overview_line` (Z.574/576); Aufrufer Z.861/922 reichen `lang=lang` (Renderer hat `lang`, Z.722); Import Z.41 anpassen |
| src/output/renderers/alert/hours.py | MODIFY | `format_cell`/`row_parts` mit `lang: Lang = "de"`, an beide `fmt_val`-Aufrufe |
| src/output/renderers/alert/render.py | MODIFY | Z.1537/1558: `row_parts(..., lang=lang)` (`_hour_lines`/`_hours_html` haben `lang` bereits, Aufrufer übergeben es) |
| tests/golden/telegram_briefing/briefing_normalstil.en.txt | MODIFY | kontrolliert nachziehen (`leicht`/`kein` → EN); Ausblick-Gewitter bleibt deutsch (#2665) |
| tests/tdd/test_2784_*.py | CREATE | rote Nutzersicht-Tests (siehe unten) |

### Scope Assessment
- Files: 3 Source + 1 Golden + 1 neue Testdatei
- Estimated LoC: ca. +25/-8 Source, ca. +60 Tests
- Risk Level: LOW (nur Keyword-Parameter mit Default `"de"`; `thunder_label(…, "de")` liest dieselbe Tabelle `THUNDER_LABEL_DE` → de byte-gleich)

### Technical Approach
Muster aus #2750: `lang` keyword-only mit Default `"de"` bis zum Formatierer durchreichen; `thunder_label(level, lang=lang)` statt `THUNDER_LABEL_DE`. `?`-Datenlücken- und Hagel-Pfad unverändert (nur Wortquelle tauschen). Fußzeile und Kurzübersicht müssen dieselbe Sprache nutzen (kein Mischtext).

Verifiziert: `fmt_val` (email/helpers.py Z.819–859) reicht `lang` an `thunder_label`, `format_wind_strength`, `format_precip_intensity` weiter; letztere nehmen `lang` (services/weather_metrics.py Z.124/145) → EN-Wörter existieren, kein Katalog-Zuwachs nötig.

Rote Tests (echter Renderer, Nutzersicht):
1. Telegram-Briefing rich `en` (Fixture `tests/helpers/telegram_briefing_fixture`, `build_texts(lang="en")`): Fußzeile, Kurzübersicht und Segment-Tabelle ohne `leicht`/`kein`; englisches Stufenwort in der Fußzeile (Ausblick-Zeile ausgenommen).
2. Alarm-Stundenzeile `en` (Klartext + HTML) im Modus simplified: Wind-/Regen-Adjektive englisch.
3. Alarm-Stundenzeile `en` mit Gewitter: englisches Stufenwort.
4. Gegenprobe `de`: byte-gleich (bestehende Goldens/Alarm-Tests).

Reihenfolge: RED-Tests → hours.py + render.py (Renderer-Gate: Modus-Matrix + Validator frisch grün) → narrow.py → Golden en geprüft nachziehen → Ratsche `tests/test_i18n_ratsche_narrow_telegram.py`, Modus-Matrix, Validator.

Nicht im Umfang: Ausblick-Gewitter Telegram (`thunder_cell_telegram`, #2665 bewusst deutsch, im Golden-Kommentar/Spec vermerken), `degrees_to_compass` (Produktfrage, de byte-gleich), Trend-Tabelle `helpers.py:938–952`.

### Dependencies
`fmt_val`, `thunder_label`, `format_wind_strength`, `format_precip_intensity` (alle lang-fähig). Direkte Testaufrufer von `_narrow_table`/`_overview_line`/`row_parts`/`format_cell` (z. B. `tests/tdd/test_telegram_felt_temperature_overview.py`) bleiben über Default `"de"` grün.

### Open Questions
- keine (Ausblick-Gewitter und Kompass sind frühere Entscheidungen, nicht neu vorzulegen)
