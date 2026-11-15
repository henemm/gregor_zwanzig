# Context: fix-3014-zt-kopf-sprache

## Request Summary
Issue #3014 (Epic #2644, ADR-0104): Der Kopf der Zeitspalte in der schmalen Telegram-Segmenttabelle
(`render_telegram_bubbles`) ist fest `Zt`, auch bei `lang="en"`. Er soll der Kontosprache folgen; das
englische Startseiten-Bild `frontend/static/landing/en/briefing-telegram.png` wird danach neu erzeugt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/narrow.py:122-155` | `_narrow_table(..., lang)` setzt `headers = ["Zt"] + compact_labels`; `lang` liegt schon an |
| `src/output/renderers/narrow.py:925` | einziger Aufrufer (Segment-/Ziel-Bubbles), reicht `lang` durch |
| `src/i18n/messages/{de,en}/telegram.json` | Katalog-Bereich für Telegram-Texte (`telegram.kopf.*`, `telegram.fuss.*`) |
| `src/i18n/messages/{de,en}/vergleich.json` | Vorbild: `vergleich.stunden.zeit` = Zeit/Time (Ortsvergleich-Stundentabelle) |
| `scripts/landing_screenshots.py` | erzeugt `landing/en/briefing-telegram.png` (`telegram_html()`, Spec `startseite_en_bilder_2777.md`) |
| `docs/reference/telegram_format.md:90` | Abschnitt Stufenwörter #2784, nennt Kürzel TH/VS/FZ als sprachneutral |
| `tests/tdd/test_2784_skalenwoerter_lang.py:62` | prüft EN-Kopf `["Zt","T","W",...]` (hält heute den Fehler fest, muss mit) |

## Existing Patterns
- Render-Funktionen nehmen `lang`, Texte über `t(key, lang)` aus dem Katalog; Deutsch bleibt byte-gleich (Golden-Tests).
- Spaltenköpfe der Metriken sind `compact_label` (Protokoll-Token, eingefroren in `tests/fixtures/metric_tokens_frozen.json`, nie übersetzt). Diese Kürzel sind englisch geprägt (T, W, G, R, TH, VS, FZ). `Zt` ist keine Metrik und nicht im Register, sondern ein fest verdrahtetes deutsches Wortkürzel → Nutzertext, kein Protokoll-Token.
- Tabellenbreite: Spaltenbreite = max(Kopf, Zellen); Zellen der Zeitspalte sind 2-stellig („08“). Ein 2-Zeichen-Kopf ändert das Layout nicht; „Time“ würde die Spalte um 2 Zeichen verbreitern (Umbruchgefahr bei `_TG_TABLE_WIDTH`).

## Dependencies
- Upstream: `src/i18n.t`, Katalog `telegram`.
- Downstream: Telegram-Briefing (rich), Befehls-Antworten mit Segmenttabellen (Golden `tests/fixtures/befehl_antwortzeit/golden_berichte.json`, deutsch), Tests mit `startswith("Zt ")` (alle deutsch, bleiben gültig), Startseiten-Bild EN.

## Existing Specs
- `docs/specs/modules/i18n_skalenwoerter_lang_2784.md` (Vorgänger, nannte `Zt` noch als Kürzel)
- `docs/specs/modules/startseite_en_bilder_2777.md` (Bild-Erzeugung)

## Risks & Considerations
- Deutsch muss byte-gleich `Zt` bleiben (Golden-Fixture, viele Tests).
- Englische Form: 2 Zeichen (`Hr`), damit Breite/Umbruch unverändert bleibt; ADR-0104: „wo wenig Platz ist, steht die englische Fachkurzform“.
- Test aus #2784 Zeile 63 erwartet `Zt` im EN-Kopf → anpassen.
- Doku telegram_format.md und Spec #2784 erwähnen `Zt` als Kürzel → richtigstellen.
- Katalog-Paritätstest: Schlüssel in de und en.

## Analysis

### Type
Bug (Nutzertext nicht übersetzt, ADR-0104 Nr. 5: Telegram-Normalstil folgt der Kontosprache)

### Einordnung „Zt" — Nutzertext, kein Protokoll-Token
- `Zt` steht nicht in `tests/fixtures/metric_tokens_frozen.json` und ist keine Metrik.
- ADR-0104 Präzisierung 2026-10-31: sprachfest ist nur die Kurzform (SMS, Premium-SMS, Telegram-Kurzstil
  via `report.sms_text`, läuft nie durch `narrow.py`). Die Segmenttabelle ist Telegram-Normalstil, deren
  Nachbartexte (`Segment`, `Finish`, `Summary`) sind bereits übersetzt → `Zt` ist Nutzertext.
- Einzige Fundstelle in `src/`: `narrow.py:131`.

### Breitenbefund (entscheidet die englische Form)
`_TG_TABLE_WIDTH = 32`. EN-Golden-Zeile `12 12.0 22 32 0.2 none  15 2800` ist 31 Zeichen lang.
`Time` (+2 Zeichen) → 33 > 32 → harter Umbruch mitten in der Datenzeile. Daher **2-Zeichen-Form `Hr`**
(Zeitzellen sind 2-stellig „08", Spaltenbreite bleibt 2, Layout byte-gleich bis auf den Kopf).
`Hr` kollidiert mit keinem `compact_label` (HU, HP, TH …). `h` verworfen: wirkt wie Einheit, nicht wie Spaltenname.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/narrow.py` | MODIFY | `headers = [t("telegram.tabelle.zeit", lang)] + …` |
| `src/i18n/messages/de/telegram.json` | MODIFY | `"telegram.tabelle.zeit": "Zt"` |
| `src/i18n/messages/en/telegram.json` | MODIFY | `"telegram.tabelle.zeit": "Hr"` |
| `tests/tdd/test_2784_skalenwoerter_lang.py` | MODIFY | EN-Kopf-Erwartung `Zt` → `Hr` |
| `tests/golden/telegram_briefing/briefing_normalstil.en.txt` | MODIFY | zwei Kopfzeilen `Zt` → `Hr` |
| `tests/tdd/test_3014_zt_kopf_sprache.py` | CREATE | RED: EN-Kopf beginnt mit `Hr`, DE bleibt `Zt`, Zeile ≤ 32 |
| `frontend/static/landing/en/briefing-telegram.png` | MODIFY | neu erzeugt mit `scripts/landing_screenshots.py` |
| `docs/reference/telegram_format.md` | MODIFY | Zeitspalten-Kopf als sprachabhängig dokumentieren |
| `docs/specs/modules/i18n_skalenwoerter_lang_2784.md` | MODIFY | Hinweis: `Zt` war fälschlich als Kürzel geführt, s. #3014 |

Unverändert gültig (alle deutsch): DE-Golden, `golden_berichte.json`, `einstellung_auslieferung_orakel.py`
(`startswith("Zt ")`), `test_telegram_kuerzel_folgt_register.py:212`, übrige `Zt`-Tests. Im Developer-Lauf
per gezieltem Testlauf bestätigen, dass keiner davon mit `lang="en"` läuft.

### Scope Assessment
- Dateien: ~9 (davon 1 Code-Zeile, 2 Katalogzeilen, Rest Tests/Doku/Bild)
- Estimated LoC: +40/-5
- Risk Level: LOW — eine Zeile im Renderer, Deutsch byte-gleich, Breite unverändert

### Technical Approach
Katalogschlüssel `telegram.tabelle.zeit` (de `Zt`, en `Hr`), in `_narrow_table` über `t(key, lang)`
auflösen (`lang` liegt schon an). Katalog-Paritätstest deckt beide Sprachen. EN-Golden und #2784-Test
nachziehen, Startseiten-Bild EN neu erzeugen, Doku richtigstellen. Kein Kanal außer Telegram-Normalstil
betroffen (E-Mail hat eigene Stundentabelle, SMS/Premium/Kurzstil laufen nicht durch `narrow.py`).

### Dependencies
`src/i18n.t`, Katalog `telegram`; Downstream nur Telegram-Normalstil (Briefing + Befehlsantworten mit Segmenttabelle).

### Open Questions
- keine (Form `Hr` technisch durch die Breitengrenze bestimmt)
