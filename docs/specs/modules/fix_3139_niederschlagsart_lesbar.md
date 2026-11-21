---
entity_id: fix_3139_niederschlagsart_lesbar
type: bugfix
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: fix-3139-niederschlagsart-lesbar
tags: [i18n, telegram, email, trip-briefing, precip_type]
---

# Niederschlagsart lesbar in Trip-Briefings (Bugfix #3139)

## Approval

- [ ] Approved

## Purpose

Im Trip-Briefing (Telegram, Trip-Mail HTML, Trip-Mail Text) erscheint die Metrik Niederschlagsart als Programmname (`PrecipType.RAIN`). Der Fix zeigt stattdessen das lesbare Wort in der Nutzersprache (DE/EN) aus dem vorhandenen Katalog, mit derselben Wortquelle wie der Orts-Vergleich.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `fmt_val` (neuer Zweig `precip_type`), neue Funktion `precip_type_label` in `src/output/metric_format.py`

Schicht: Python-Core (`src/output/`). Kein Go-/Frontend-Anteil.

Querschnitts-Prüfpunkte:

- **Trip/Ortsvergleich-Teilung:** Eine gemeinsame Wortquelle (`precip_type_label`) fuer Trip und Vergleich; `_fmt_precip_type` im Vergleich delegiert, es entsteht kein Duplikat.
- **Mandantentrennung:** Keine Nutzerdaten werden bewegt, reine Darstellung; nicht betroffen.
- **Kanaele:** Betroffen sind E-Mail (HTML und Text) und Telegram (gleicher Inhalt, kanalgerechte Form). SMS und Premium-SMS verwenden das Protokollkuerzel und bleiben unveraendert.

## Estimated Scope

- **LoC:** ca. +25/-10 Produktiv, +40 bis 60 Test
- **Files:** 3 Produktiv + 1 Test
- **Effort:** low

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/output/metric_format.py | MODIFY | neue `precip_type_label(v, *, lang)` + `_PRECIP_TYPE_KEYS` (Katalog `vergleich.niederschlagsart.*`, None/unbekannt → `NO_VALUE`) |
| src/output/renderers/email/compare_html.py | MODIFY | `_fmt_precip_type` bleibt echte `def` und delegiert an `precip_type_label` |
| src/output/renderers/email/helpers.py | MODIFY | `fmt_val`: Zweig `precip_type` direkt nach dem `thunder`-Zweig |
| tests/tdd/test_fix_3139_niederschlagsart_lesbar.py | CREATE | RED-Tests aus Nutzersicht (Telegram DE/EN, Trip-Mail HTML/Text, Grenzfälle) |

### Out of Scope

- Konsolidierung der drei Wortquellen für Niederschlagsart (siehe Known Limitations).
- SMS-/Premium-SMS-Protokollkürzel.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `t()` (i18n) | function | Katalogtext je Sprache |
| `PrecipType` (`src/app/models.py`) | enum (str-Enum, Name == Wert) | Werte RAIN/SNOW/MIXED/FREEZING_RAIN |
| `src/i18n/messages/{de,en}/vergleich.json` | catalog | Schluessel `vergleich.niederschlagsart.*` (Regen/Schnee/Mischniederschlag/Eisregen bzw. Rain/Snow/Mixed precipitation/Freezing rain) |
| `NO_VALUE` (`metric_format.py`) | constant | Platzhalter "–" |
| `fmt_val` Zweig `thunder` | pattern | Vorlage fuer den Wortzweig |
| `render_telegram_bubbles`, `narrow.py::_cell` | renderer | Telegram-Ausgabe, ruft `fmt_val` mit `lang` |
| `email/html.py`, `email/plain.py` | renderer | Trip-Mail, rufen `fmt_val` |
| `tests/helpers/telegram_briefing_fixture.py` | test helper | Golden-Fixture fuer das Telegram-Briefing |

## Implementation Details

Ursache: `fmt_val` hat keinen Zweig fuer `precip_type` und endet bei `str(val)`.

Ansatz (eine Wortquelle):

1. `src/output/metric_format.py`: neue `precip_type_label(v, *, lang)` mit Schluesseltabelle `_PRECIP_TYPE_KEYS`. Der Koerper stammt aus `_fmt_precip_type` (Katalog `vergleich.niederschlagsart.*`). Enum und String werden per `.upper()` normalisiert; `None` oder unbekannter Wert liefert `NO_VALUE`. Neutrales Modul, damit kein Import-Zirkel helpers <-> compare_html entsteht.
2. `src/output/renderers/email/compare_html.py`: `_fmt_precip_type` bleibt eine echte `def` und delegiert an `precip_type_label` (Identitaetsvergleich `fmt is _fmt_precip_type` und bestehende Importe bleiben gueltig).
3. `src/output/renderers/email/helpers.py`: in `fmt_val` direkt nach dem `thunder`-Zweig (nach dem None-Check, vor Ampel-/Modus-Code) `if key == "precip_type": return precip_type_label(val, lang=lang)`. Wirkt fuer Telegram, Trip-Mail HTML und Trip-Mail Text.

Keine Ampel fuer Niederschlagsart; auch im Modus `raw` kommt das Wort. Keine neuen Katalogschluessel (i18n-Konvention: nie zwei Schluessel fuer denselben Text). Katalogtexte enthalten keine HTML-Sonderzeichen.

Vor dem Fix: `grep -rn "PrecipType\.\(RAIN\|SNOW\)" tests` auf Erwartungstexte, die den Programmnamen festschreiben, und diese korrigieren.

## Expected Behavior

- **Input:** Zeilenwert `precip_type` (Enum, oder String nach Snapshot-Roundtrip, oder `None`) plus Nutzersprache.
- **Output:** DE: Regen / Schnee / Mischniederschlag / Eisregen. EN: Rain / Snow / Mixed precipitation / Freezing rain. Fehlend oder unbekannt: "–".
- **Side effects:** Keine. Der Orts-Vergleich bleibt in seiner Ausgabe identisch.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_fix_3139_niederschlagsart_lesbar.py`. Nachweis ueber die echte Render-Kette, kein Mock-Theater.

- [ ] Telegram DE: GIVEN Golden-Fixture mit Niederschlagsart Regen / WHEN `render_telegram_bubbles` (de) / THEN Ausgabe enthaelt "Regen", nicht "PrecipType"
- [ ] Telegram EN: wie oben mit "Rain"
- [ ] Trip-Mail HTML: GIVEN Trip-Report mit `precip_type` / WHEN HTML gerendert / THEN Zelle zeigt das Wort
- [ ] Trip-Mail Text: dito Plain
- [ ] Alle vier Werte in DE und EN ueber `fmt_val`
- [ ] Grenzfaelle: `None`, String "RAIN" und "rain", unbekannter String "FOO" liefern Wort bzw. "–", nie "PrecipType"
- [ ] Modus `raw`: Wort statt Programmname
- [ ] Orts-Vergleich: Ausgabe unveraendert; Regression ueber `tests/test_vergleichs_mail_zweisprachig.py`
- [ ] SMS: Protokollkuerzel unveraendert; Regression ueber bestehende SMS-Trip-Tests
- [ ] Regressionslauf: `tests/tdd/test_metric_format.py`, `test_issue_811_mode_matrix.py`, `tests/unit/test_compare_metric_parity.py`, `test_outlook_metric_ampelfarben.py`, `test_thunder_origin_compare.py`, `test_adhoc_metrik_formatierung.py`

Renderer-Commit-Gate greift (Trip-Mail-Inhalt): Modus-Matrix-Test und `briefing_mail_validator.py` muessen frisch gruen sein.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Deutsch und einem Trip-Briefing, dessen Metrik Niederschlagsart "Regen" liefert / When das Telegram-Briefing erzeugt wird / Then steht in der Niederschlagsart-Zeile das Wort "Regen" und nirgends "PrecipType" oder "RAIN".
  - Test: Telegram-Briefing ueber die echte Render-Kette mit Golden-Fixture, Sprache de.

- **AC-2:** Given ein Nutzer mit Sprache Englisch und demselben Briefing / When das Telegram-Briefing erzeugt wird / Then steht dort "Rain" (bei Mischniederschlag "Mixed precipitation") und kein Programmname.
  - Test: Telegram-Briefing mit Sprache en, Werte RAIN und MIXED.

- **AC-3:** Given ein Trip-Report mit Niederschlagsart "Schnee" / When die Trip-Mail als HTML erzeugt wird / Then zeigt die Zelle der Niederschlagsart das Wort "Schnee" in der Nutzersprache, ohne Programmnamen und ohne unmaskierte Sonderzeichen.
  - Test: HTML-Rendering des Trip-Reports, Zelle der Spalte Niederschlagsart gelesen.

- **AC-4:** Given derselbe Trip-Report / When die Trip-Mail als Text-Variante erzeugt wird / Then enthaelt die Zeile der Niederschlagsart das Wort (DE "Schnee", EN "Snow") und keinen Programmnamen.
  - Test: Plain-Rendering des Trip-Reports in beiden Sprachen.

- **AC-5:** Given alle vier Niederschlagsarten Regen, Schnee, Mischniederschlag und Eisregen / When sie in Telegram oder Trip-Mail dargestellt werden / Then erscheint jeweils der passende Katalogtext der Nutzersprache, auch wenn der Darstellungsmodus "raw" gewaehlt ist (keine Ampel).
  - Test: Rendering aller vier Werte in de und en, Modus raw und Standard.

- **AC-6:** Given ein Orts-Vergleich mit Niederschlagsart / When die Vergleichs-Mail erzeugt wird / Then ist die Darstellung exakt dieselbe wie vor der Aenderung (gleiche Woerter, gleiche Sprache).
  - Test: bestehende Vergleichs-Mail-Tests (zweisprachig) bleiben gruen, Vorher-Nachher-Vergleich der Zelle.

- **AC-7:** Given eine fehlende Niederschlagsart (kein Wert) / When Telegram oder Trip-Mail erzeugt wird / Then steht dort der Platzhalter "–" und kein Programmname.
  - Test: Rendering mit Wert None.

- **AC-8:** Given die Niederschlagsart liegt als Text vor (etwa "RAIN" oder "rain" nach dem Speichern und Laden) / When das Briefing erzeugt wird / Then erscheint dasselbe Wort wie bei der Enum-Variante.
  - Test: Rendering mit String-Werten in Gross- und Kleinschreibung.

- **AC-9:** Given ein unbekannter Niederschlagswert (etwa "FOO") / When das Briefing erzeugt wird / Then steht dort "–", es erscheint weder der Rohwert noch ein Programmname und es entsteht kein Fehler.
  - Test: Rendering mit unbekanntem String.

- **AC-10:** Given ein Trip mit Niederschlagsart, dessen Briefing per SMS oder Premium-SMS versendet wird / When die Nachricht erzeugt wird / Then bleibt das Protokollkuerzel unveraendert und wird nicht uebersetzt.
  - Test: bestehende SMS-Trip-Tests bleiben gruen, Kuerzel im Ergebnis geprueft.

## Definition of Done

- AC-1 bis AC-10 durch Tests in `tests/tdd/test_fix_3139_niederschlagsart_lesbar.py` über die echte Render-Kette belegt, vorher rot, danach grün; Kern-Schicht grün
- Regressionstests aus dem Test Plan grün, Orts-Vergleich-Ausgabe unverändert
- Renderer-Gate (Modus-Matrix-Test, `briefing_mail_validator.py` gegen echt zugestellte Staging-Mail) frisch grün
- Staging-E2E: Trip-Briefing per Telegram und Mail zeigt das Wort (DE und EN) statt Programmname
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Known Limitations

- Out of Scope (Nebenbefund): Es gibt drei Wortquellen fuer Niederschlagsart: `PRECIP_TYPE_LABEL_DE` (`metric_format.py`, Ad-hoc-Abruf), `inbound.niederschlagsart.*` (Befehlsantworten, Satzmitte klein, "Schneeregen"/"sleet") und `vergleich.niederschlagsart.*` (Zellen). Die Konsolidierung ist nicht Teil von #3139 und wird als Nebenbefund-Issue gefuehrt.
- Lange Woerter ("Mischniederschlag", "Mixed precipitation") brechen in Telegram ueber den vorhandenen `_wrap` um (Spaltenbreite 35); der Test prueft das mit.
- Weitere Enum-Felder in `str(val)`: keine (`thunder_level` hat einen eigenen Zweig).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (beruehrt ADR-0104 Zweisprachigkeit und ADR-0095 Kanal-Paritaet, ohne sie zu aendern)
- **Rationale:** Bugfix auf bestehender Katalogstruktur; Wortquelle wird nur in ein neutrales Modul gehoben, keine neue Entscheidungsflaeche.

## Changelog

- 2026-11-21: Initial spec created
