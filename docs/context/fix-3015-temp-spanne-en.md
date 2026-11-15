# Context: fix-3015-temp-spanne-en

## Request Summary
Englische Briefing-Mails zeigen im Metrik-Überblick bei Minusgraden „-3 bis 0°C“. Das Bindewort der
Temperaturspanne muss der Kontosprache folgen (en „to“, de „bis“) und aus dem i18n-Katalog kommen (ADR-0104).

## Related Files
| File | Relevance |
|------|-----------|
| src/output/renderers/email/helpers.py:1551 `format_temp_span()` | Ursache: Zeile 1566 `f"{lo} bis {hi}°C"` ohne Sprache |
| src/output/renderers/email/helpers.py:1569 `_aggregation_pill_text()` | ruft `format_temp_span` (Zeile 1592), hat kein `lang` |
| src/output/renderers/email/helpers.py:~1667 | Aufrufer von `_aggregation_pill_text`, hat `lang` im Scope |
| src/output/renderers/compact_summary.py:380 `_format_felt_temperature` | zweiter Aufrufer von `format_temp_span`, hat `lang` |
| src/i18n/messages/{de,en}/mail.json | Katalog, Muster `mail.pille.*` |
| tests/tdd/test_temperaturspanne_negative_werte.py | bestehende #2210-Tests (deutsch), bleiben gültig |

## Existing Patterns
- Nutzertexte über `t("<key>", lang, **params)` aus `i18n`; Parameter `lang: Lang = "de"` als Keyword.
- Ähnliche Spannen im Katalog: `mail.pille.feuchte_bereich` „{min}–{max}%“.
- Gedankenstrich-Variante „lo–hi°C“ ist sprachneutral und bleibt.

## Dependencies
- Upstream: `i18n.t`, `Lang`.
- Downstream: Vollmail-Kachelzeile (Metrik-Überblick) Trip-Briefing und Ortsvergleich, E-Mail-Kurzzusammenfassung (gefühlte Temperatur).

## Existing Specs
- docs/specs/modules/fix_2210_mail_renderfehler.md (C2-79: „bis“-Regel)
- docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md
- docs/reference/i18n_konventionen.md

## Risks & Considerations
- Deutsche Ausgabe muss zeichengleich bleiben (Renderer-Gate, #2210-Tests).
- Default `lang="de"` an neuen Parametern, damit unbekannte Aufrufer unverändert bleiben.
- Nebenbefund: `compact_summary._format_temperature` (Zeile ~341) baut die Lufttemperatur-Spanne selbst mit „–“
  und ohne Minus-Regel → bei Minusgraden „-12–-4°C“. Gehört thematisch dazu (gleiche Spannen-Formel), in Analyse entscheiden.
- Renderer-Commit-Gate verlangt frischen Modus-Matrix-Test + Mail-Validator.

## Analysis

### Type
Bug (i18n-Lücke, ADR-0104, Epic #2644)

### Root Cause
`format_temp_span()` (src/output/renderers/email/helpers.py:1551) baut den Minusgrad-Zweig (#2210 C2-79)
als fest deutsches f-String `f"{lo} bis {hi}°C"`; die Funktion kennt keine Sprache. Beide Aufrufer
haben `lang` im Scope (Kachelzeile via `_aggregation_pill_text` ← Aufrufer Zeile ~1667;
Kurzzusammenfassung `_format_felt_temperature`, compact_summary.py:380), reichen es aber nicht durch.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/email/helpers.py | MODIFY | `format_temp_span(..., lang: Lang = "de")`, Minus-Zweig über `t("mail.pille.temp_spanne_negativ", lang, min=lo, max=hi)`; `_aggregation_pill_text(..., lang="de")` reicht durch; Aufrufer Zeile ~1667 übergibt `lang` |
| src/output/renderers/compact_summary.py | MODIFY | `_format_felt_temperature` übergibt `lang`; `_format_temperature` bekommt `lang` und nutzt `format_temp_span` (Nebenbefund, s. u.); Aufrufer Zeile 188/199 übergeben `lang` |
| src/i18n/messages/de/mail.json | MODIFY | neuer Key `mail.pille.temp_spanne_negativ`: „{min} bis {max}°C“ |
| src/i18n/messages/en/mail.json | MODIFY | derselbe Key: „{min} to {max}°C“ |
| tests/tdd/test_temperaturspanne_en_3015.py | CREATE | RED-Tests: englische Kachelzeile + Kurzzusammenfassung bei Minusgraden „to“, deutsch unverändert „bis“, Lufttemperatur-Satz ohne „–-“ |

### Entscheidung Nebenbefund (Tech Lead)
`compact_summary._format_temperature` baut die Lufttemperatur-Spanne selbst (`f"{lo}–{hi}°C"`) ohne
Minus-Regel → „-12–-4°C“ in BEIDEN Sprachen. Gleiche Formel, gleicher Mailsatz, #1410 hatte die
geteilte Formel ausdrücklich gewollt („kein Nachbau“). **Wird mitbehoben**: Aufruf von
`format_temp_span(int(round(lo)), int(round(hi)), decimals=0, lang=lang)` (ganzzahlige Werte → kein „-0“).
Folge: bei gleichem Min/Max (gerundet) erscheint der Einzelwert statt „5–5°C“ — konsistent zur
Kachelzeile und zum gefühlten Teil; positive Spannen bleiben zeichengleich.

### Scope Assessment
- Files: 4 Source/Katalog + 1 Test
- Estimated LoC: +25/-6 (Source), Tests ~+80
- Risk Level: LOW — nur Minusgrad-Zweig und Sprachdurchreichung; Default `lang="de"` hält unbekannte Aufrufer stabil.

### Technical Approach
Sprache als Keyword-Parameter mit Default "de" durch die Kette reichen, Bindewort-Muster komplett
aus dem Katalog (ganzes Muster statt nur „bis“, damit Wortstellung je Sprache frei bleibt). Gedankenstrich-
Variante bleibt sprachneutral im Code. Bestehende #2210-Tests müssen grün bleiben. Renderer-Gate:
Modus-Matrix-Test + Mail-Validator (Trip-Briefing, englisch) vor Commit.

### Dependencies
`i18n.t`, `Lang`; Downstream: Vollmail-Kachelzeile (Trip-Briefing + Ortsvergleich teilen den Helper),
E-Mail-Kurzzusammenfassung (HTML + Plain). SMS/Telegram nutzen eigene Formate, nicht betroffen.

### Open Questions
- keine (keine Produktentscheidung offen; „to“ ist die etablierte englische Spannen-Form)
