# Kontext: #3260 Schritt 1, Scheibe C – Kurz-Zusammenfassung und Orte-Telegram

## Request Summary

Auftrag #3260 (PO-freigegeben 2026-11-21, autark), Schritt 1. Scheiben A (Ratsche, ADR-0127, PR #3262)
und B (Form je Stelle im Katalog, `metric_format.darstellung`, PR #3274) sind gemergt und in Produktion
(Prod-Commit c1d098484 enthält 43a5c0df1). Diese Scheibe deckt:

- **AC-1.5** Gewitter in der Kurz-Zusammenfassung: dasselbe Stufenwort in HTML- und Nur-Text-Mail,
  unabhängig vom E-Mail-Umschalter Roh/Einfach.
- **AC-1.6** Windrichtung in der Kurz-Zusammenfassung erscheint bei Wind auf Roh genauso wie auf Einfach.
- **AC-1.7** Orte-Telegram (Vorlage Radtour): Windrichtung trägt keine Stunden-Marke `@h`.

Nicht in dieser Scheibe: Mail-Validatoren/Prüfkatalog/Modus-Matrix für Orte (AC-1.4, Scheibe D);
Wind-Wortskala der Kurz-Zusammenfassung (15/35/60 + „Sturm“ → T2-Skala) ist AC-3.5 in Schritt 3.

## Related Files

| Datei | Stelle | Befund |
|---|---|---|
| `src/output/renderers/compact_summary.py` | :243-253 | Wind-Umschalter (`friendly`) wird an `_format_wind` gereicht |
| `src/output/renderers/compact_summary.py` | :555 | `if wind_dir_enabled and ... and friendly:` → Kompass hängt am Wind-Umschalter (AC-1.6) |
| `src/output/renderers/compact_summary.py` | :255-256, :588-666 | `_format_thunder(hourly, friendly)`: MED/HIGH → `gewitter_symbol` („⚡ möglich“) bzw. `gewitter_moeglich` („Gewitter möglich“) je Umschalter, **kein Stufenwort** (AC-1.5). LOW-Zweig (`thunder_low_statement_sentence`) bleibt. |
| `src/output/renderers/compact_summary.py` | :545-552 | eigene Wind-Wortskala 15/35/60 (Ratschen-Ausnahme, Schritt 3) |
| `src/output/metric_format.py` | :423 `darstellung`, :457 `stunden_marke_erlaubt` | die EINE Darstellung; Gewitter Text-Form = Stufenwort (`thunder_label`) über WORTSKALA „gewitter“ |
| `src/app/metric_catalog.py` | :1265 `WORTSKALA`, :1291 `STUNDEN_MARKE` | `STUNDEN_MARKE` = wind, gust, precipitation, rain_probability – heute **ohne Leser** |
| `src/output/renderers/comparison.py` | :670 `_ampel_stunde`, :698 `_plain_metric_cell` (:726) | Marke bei `friendly` für jede Größe mit `ampel_seite` ≠ None; Radtour hat Ampel für `wind_direction` (Gegenwind) → `SW@hh` (AC-1.7). Fix: zusätzlich `stunden_marke_erlaubt(catalog_id)`. |
| `src/app/thunder_scale.py` | :301-322 | `THUNDER_LABEL_DE/EN`, `thunder_label` |
| `src/i18n/messages/{de,en}/mail.json` | :173-174 | `mail.zusammenfassung.gewitter_moeglich`, `gewitter_symbol` |

## Existing Patterns

- Darstellung immer über `metric_format.darstellung(metric_id, wert, stelle=, ausgabeart=, fmt=, ampel=)`;
  `ampel=None` erlaubt für reine Textfassung. Für Gewitter liefert Text-Form bei raw und simplified „wort“.
- Stunden-Marke: Katalog-Prädikat `stunden_marke_erlaubt` (Scheibe B vorbereitet, Leser ab Scheibe C laut Landkarte).
- Testhelfer (Landkarte `docs/context/3260/s1b_darstellungswege.md`): Kurz-Zusammenfassung über
  `test_gewitter_zelle_zusammenfassung_sprache._satz(lang, hourly, friendly=)`; Orte über
  `preset(...)`/`senden(mit, p)` (Schlüssel html, plain, telegram, sms, premium_sms).
- Tabellentest `tests/tdd/test_feat_3260_tabelle_form_je_stelle.py` (echte Renderer, handgeschriebenes Soll).
- Ratsche `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`: Ausnahmeliste darf nicht wachsen.

## Dependencies / Dependents

- Kurz-Zusammenfassung erscheint in HTML-Kopf und Nur-Text der Trip-Mail und in der Telegram-Kurzfassung
  (`trip_report._generate_compact_summary`), Orte über `format_location_summary` (gleicher Kern).
- SMS/Premium-SMS lesen den Text nicht (eigenes `TH:`-Token) – unberührt.
- Goldens mit „⚡ möglich“/„Gewitter möglich“: `tests/golden/email/*`, `tests/fixtures/golden_3237/*`,
  `einstellung_gleich_mail/*`, `renderer_nachzug_3156/*`, `befehl_antwortzeit/golden_berichte.json`,
  `feat_3373/versand_referenz.json`, `trip_outlook_reference/telegram_bubble.txt` – nachzuziehen, wo MED/HIGH-Gewitter vorkommt.

## Existing Specs

- `docs/specs/modules/feat_3260_s1b_form_je_stelle.md` (Vorgänger, Landkarte Nr. 3-5)
- `docs/specs/modules/feat_3122_was_steht_wo.md` Teil A Nr. 4 (Tabelle, T1)
- Umzuschreibende Tests laut Issue: `test_gewitter_zelle_zusammenfassung_sprache.py`, `test_trip_summary_text.py:118`.

## Risks

- Goldens-Churn durch neuen Gewitter-Wortlaut (nur Fälle mit MED/HIGH).
- Wortlaut-Entscheidung (Tech Lead): „Gewitter {stufe} 14:00–17:00“ (EN „thunderstorms {stufe}“), Stufe aus
  `darstellung("thunder", max_lvl, stelle="email", ausgabeart="text", ...)` – kein Symbol, damit HTML und Text gleich.
- Kompass jetzt auch bei Roh: Trips mit Wind roh + Windrichtung bekommen den Kompass zusätzlich (gewollt, AC-1.6).
- Orte-Telegram: Prüfen, dass Marke an Wind/Böen/Niederschlag/Regen-W. bleibt (nur Windrichtung entfällt).
- Zwei-Nutzer-Test (Pflicht für datenbewegende Pfade) bei Orte-Telegram.

## Analysis

**Type:** Feature/Korrektur (Auftrag #3260, Schritt 1 Scheibe C). Kombinierter Durchgang Kontext+Analyse (Intake-Summe 3).

### Affected Files (Change Type)

| Datei | Change | Inhalt |
|---|---|---|
| `src/output/renderers/compact_summary.py` | MODIFY | `_format_thunder` ohne `friendly`; MED/HIGH: `t("mail.zusammenfassung.gewitter_stufe", stufe=darstellung("thunder", max_lvl, stelle="email", ausgabeart="text", fmt=None, ampel=None).text)`; Aufruf :256 ohne Umschalter. `_format_wind`: Kompass nur noch an `wind_dir_enabled` (Parameter `friendly` entfällt), Kompass über `darstellung("wind_direction", deg, stelle="email", ausgabeart="text", fmt="simplified", ampel=None).text` |
| `src/output/renderers/comparison.py` | MODIFY | `_plain_metric_cell`: Marke nur bei `friendly and stunden_marke_erlaubt(catalog_id)` (catalog_id aus `_CV2_BY_KEY`) |
| `src/i18n/messages/{de,en}/mail.json` | MODIFY | neu `mail.zusammenfassung.gewitter_stufe` („Gewitter {stufe}“ / „Thunderstorm {stufe}“); `gewitter_symbol`, `gewitter_moeglich` entfernen, falls keine weiteren Leser (Prüfung: nur compact_summary) |
| Tests | MODIFY/CREATE | neuer RED-Test `tests/tdd/test_feat_3260_s1c_zusammenfassung_telegram.py` (AC-1.5/1.6/1.7 + zwei Nutzer); umschreiben `test_gewitter_zelle_zusammenfassung_sprache.py`, `test_trip_summary_text.py` und weitere, die „⚡ möglich“/„Gewitter möglich“ der Zusammenfassung festschreiben; Goldens nachziehen |

### Scope / Risk

- Produktcode ~30–50 LoC in 3 Quell-/2 Katalogdateien; Tests ~120 LoC; Goldens regeneriert (nur Fixtures).
- Risiko mittel: jede Trip-Mail mit MED/HIGH-Gewitter erhält neuen Wortlaut; Kompass erscheint neu bei Wind roh. Kanäle SMS/Premium-SMS unberührt (eigenes TH-Token).
- Ratsche: keine neue Ausnahme; `friendly`-Abhängigkeit entfällt; Wind-Wortskala-Schwellen (15/35/60) bleiben als Ausnahme bis Schritt 3 (AC-3.5) – bewusst nicht hier, weil Schritt 3 sie samt Goldens umstellt.

### Technical Approach

1. RED: Test rendert über den echten `CompactSummaryFormatter` (DE/EN) mit MED-Gewitter-Stunden einmal `use_friendly_format=True`, einmal `False` → gleicher Text, enthält Stufenwort („mittel“/„medium“), kein „⚡ möglich“. Wind roh + `wind_direction` → Kompass vorhanden, gleich wie Einfach. Orte-Telegram Vorlage radtour, Windrichtung 225°, Einfach → kein `@` an der Windrichtung, Wind-Zelle mit gelber Stufe behält `@hh`; zwei Nutzer (A radtour/Einfach, B andere Vorlage) ohne Querdaten.
2. GREEN: Änderungen wie oben, keine örtliche Ausnahme: Form/Wort über `darstellung`, Marke über Katalog-Prädikat.
3. Goldens/alte Tests nachziehen; Spec-Verweis auf überholte Stellen (Docstring-Kommentar „BEIDE Schreibweisen“).

### Dependencies

`format_weather_summary` → Trip-Mail (HTML/Plain), Telegram-Kurzfassung, Orte-Zusammenfassung (`format_location_summary`), Vorschau. `_plain_metric_cell` → nur Orte-Telegram.

### Open Questions

Keine Produktfrage offen: Wortlaut „Gewitter {Stufenwort}“ folgt E1 (Wörter beschreiben) und T1 (Gewitter in jedem Text das Stufenwort); Tech-Lead-Entscheidung.
