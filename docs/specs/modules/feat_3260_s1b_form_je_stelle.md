---
entity_id: feat_3260_s1b_form_je_stelle
type: feature
created: 2026-11-21
updated: 2026-11-21
status: approved
version: "1.0"
tags: [issue-3260, issue-3255, adr-0127, adr-0124, metrik-katalog, metric-format, ausblick, stundenverlauf, schritt-1]
supersedes: [feat_3097_orte_stundenverlauf_darstellung (Einfachformen Regen), fix_2049_ausblick_darstellungsform (AC-6)]
---

# Schritt 1, Scheibe B: Form je Stelle im Katalog, eine Darstellungsfunktion, Tabellentest, HTML-Ampelpunkte

## Approval

- [x] Approved
- PO-Freigabe 2026-11-21, Issue #3260 (E1, E3; T1, T6; Pflicht-Nachtrag P1–P3). ACs AC-1.1, AC-1.2, AC-1.3, AC-1.8, AC-1.9 wörtlich aus dem Issue.

## Purpose

Der Katalog führt künftig nicht nur, OB eine Metrik an einer Stelle zwei Formen hat, sondern WELCHE Form je Stelle, Ausgabeart und Modus gilt. Ein einziges Verarbeitungsmodul macht daraus die Zelle. Ein Kern-Test rendert jede Zelle der freigegebenen Tabelle mit dem echten Renderer gegen eine von Hand abgeschriebene Erwartung. Die drei sichtbaren Abweichungen (#3255 Orte-Stundenverlauf, Ausblick in der HTML-Mail, `:partly_sunny:` in der Kompakt-Mail) laufen danach über Katalog und Modul, nicht als örtliche Ausnahme.

## Source

- **Katalog:** `src/app/metric_catalog.py` — neu `FormPaar`, `STELLEN_FORMEN`, `WORTSKALA`, `STUNDEN_MARKE`, `form(metric_id, stelle, ausgabeart, fmt)`; `STELLEN_ZWEI_FORMEN` wird daraus abgeleitet (nicht mehr von Hand).
- **Verarbeitung:** `src/output/metric_format.py` — neu `Zelle`, `darstellung(...)`, `stunden_marke_erlaubt(...)`; Punkt-Markup (`_ampel_dot_css`, `_AMPEL_DOT_COLORS`) zieht aus `email/helpers.py` hierher, helpers delegiert ohne eigene Logik.
- **Erste Aufrufer:** `compare_html._hour_einfach_text` (Orte-Stundenverlauf), Ausblick-Zeilenbau (`compare_outlook_metric_ids.py` `_outlook_row`) mit getrennten Werten je Ausgabeart für HTML (`outlook.py` `render_outlook_table`), Text (`render_outlook_plain`, `narrow` Ausblick) und ASCII (`email/compact.py`).
- Landkarte der Wege: `docs/context/3260/s1b_darstellungswege.md` (Abschnitte 1–6).

## Estimated Scope

- **LoC:** ~400 Produkt + ~400 Test (Override 500 nötig).

## Dependencies

- Scheibe A (Ratsche, `tests/unit/ein_katalog_ausnahmen.json`): Funde in berührten Dateien müssen sinken, nie steigen; die Liste wird in dieser Scheibe verkleinert.
- Abo-Ampel aus `resolve_ampel` (ADR-0106).

## Implementation Details

1. **Formtabelle.** Formen: `zahl | wort | symbol | ampelpunkt | kompass`. Ausgabearten: `html | text | ascii` (ascii = Kompakt-Mail; fehlt sie, gilt `text`). Inhalt nach Tabelle feat_3122 Teil A Nr. 4 und T1/T7:
   - Wind, Böen, Niederschlag, Regenwahrscheinlichkeit, an E-Mail, Telegram, Stundenverlauf, Ausblick: Roh `zahl`; Einfach `ampelpunkt` in html, `wort` in text/ascii.
   - Bewölkung (gesamt, tief, mittel, hoch), vier Stellen: Roh `zahl`; Einfach `symbol` in html/text, `wort` in ascii (Wortstufe aus dem Katalog, DE/EN über den i18n-Katalog; nie ein Emoji-Kurzname wie `:partly_sunny:`; nicht die SMS-Stufen CLR…OVC, die mit Schritt 5 entfallen).
   - Sonnenstunden (T7 „wie heute“): die Einfach-Form folgt der Wertart, nicht der Fläche: Stundenwert `symbol` (Trip-E-Mail, Trip-Telegram), Tageswert `wort` (Orte-Übersicht, Orte-Telegram, Ausblick); im Katalog als Wertart-Dimension (`FormPaar.tag`, `form(..., wertart)`); Stundenverlauf gesperrt.
   - Windrichtung: E-Mail, Telegram, Ausblick Roh `zahl` (Grad), Einfach `kompass`; Stundenverlauf immer `kompass`.
   - Gewitter: E-Mail html Einfach `ampelpunkt`, sonst überall `wort` (Stufenwort).
   - Alle übrigen: `zahl`, eine Form.
2. **`darstellung(metric_id, wert, *, stelle, ausgabeart, fmt, ampel, wertart="stunde", lang="de", …) -> Zelle(text, html, form, stufe)`** liest die Form aus dem Katalog, die Stufe aus der übergebenen Abo-Ampel (`severity_for`), das Wort über `WORTSKALA` aus den bestehenden Wortfunktionen, das Symbol aus `cloud_emoji`/`get_weather_emoji`, den Kompass aus `degrees_to_compass`, die Zahl aus `format_value`/Katalog-Einheit. Kein Aufrufer wählt die Form selbst.
3. **Orte-Stundenverlauf:** `_hour_einfach_text` ruft `darstellung(..., stelle="hourly")`; die feste ID-Liste (heute `compare_html.py:1160`) entfällt. HTML zeigt bei Niederschlag und Regenwahrscheinlichkeit auf Einfach den Ampelpunkt in der Farbe der Abo-Ampel, Nur-Text das Wort.
4. **Ausblick:** Der gemeinsame Zellenbau liefert je Zelle Rohwert und Metrik; HTML, Text und ASCII holen ihre Fassung über `darstellung`. HTML zeigt bei Wind, Böen, Niederschlag, Regenwahrscheinlichkeit auf Einfach den Ampelpunkt, kein Wort. Nur-Text, Kompakt und Telegram bleiben beim Wort.
5. **Kompakt-Mail, Ausblick, Bewölkung Einfach:** Wortstufe statt `:name:`.
6. **Kern-Tabellentest** `tests/tdd/test_feat_3260_tabelle_form_je_stelle.py`: rendert mit den echten Renderern (Versandweg über `placements`, Gerüste wie `tests/tdd/test_einstellung_gleich_mail_trip_tabelle.py` und `…_orte_tabelle.py`) jede Metrikgruppe × Stelle (E-Mail, Telegram, Stundenverlauf, Ausblick) × Roh/Einfach × HTML/Text × Trip/Orte und prüft die erwartete Form (Zahl, Wort, Symbol, Ampelpunkt mit Farbe, Kompass). Die Erwartung steht von Hand als Tabelle im Test und importiert nichts aus Katalog oder Renderer. Gesperrte Kombinationen werden als gesperrt geprüft (Metrik erscheint dort nicht). Wo die Altform einen bekannten Rest hat (Trip-Klartext ohne `placements`, Golden bis Migration B6), bleibt sie außerhalb des Tests; der Test nutzt `placements`.
7. **Überholt und zu markieren** (Kopf `superseded_by: feat_3260_s1b_form_je_stelle` bzw. Vermerk im Text): `feat_3097_orte_stundenverlauf_darstellung.md` (Einfachformen Regen), `fix_2049_ausblick_darstellungsform.md` (AC-6), `renderer_email_spec.md:321` (Ausblick-Regel), Kommentar „bleiben hier bewusst Wort" in `compare_html.py`.
8. **Umzuschreibende Tests** (auf die neue Form, nicht umgehen): `test_3097_stundenverlauf_darstellung.py:162-206`, `test_outlook_darstellungsform.py:109, 399, 593, 802, 834`, dazu weitere, die beim Lauf auffallen; jede Änderung im PR begründet.
9. **Ratsche:** Funde in berührten Dateien sinken; `tests/unit/ein_katalog_ausnahmen.json` wird entsprechend verkleinert (nie erhöht), `hoechststand` mitgesenkt.

## Expected Behavior

- **Input:** Abo mit `placements` (Formate je Stelle), Wetterdaten, Abo-Ampel.
- **Output:** HTML-, Nur-Text-, Kompakt-Mail und Telegram mit der Form, die die Tabelle verlangt.
- **Side effects:** keine Datenänderung.

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich mit Stundenverlauf und Niederschlag sowie Regenwahrscheinlichkeit auf Einfach / When die HTML-Mail erzeugt wird / Then zeigt jede Stundenzelle dieser beiden Spalten einen Ampelpunkt in der Farbe der Abo-Ampel und kein Wort, und die Nur-Text-Fassung zeigt weiter die Wortstufe. (AC-1.1)
- **AC-2:** Given ein Trip oder Orts-Vergleich mit Wind, Böen, Niederschlag und Regenwahrscheinlichkeit im 3-Tages-Ausblick auf Einfach / When die HTML-Mail erzeugt wird / Then zeigt jede dieser Zellen einen Ampelpunkt, während Nur-Text-Mail, Kompakt-Mail und Telegram unverändert die Wortstufe zeigen. (AC-1.2)
- **AC-3:** Given die freigegebene Tabelle „Roh/Einfach" / When der Kern-Test jede Metrikgruppe an jeder Stelle in Roh und Einfach, HTML und Text, für Trip und Orte mit dem echten Renderer rendert / Then entspricht jede Zelle der von Hand hinterlegten erwarteten Form, und eine absichtlich verfälschte Form an einer beliebigen Stelle macht den Test rot. (AC-1.3)
- **AC-4:** Given eine Kompakt-Mail mit Bewölkung auf Einfach im 3-Tages-Ausblick / When sie erzeugt wird / Then enthält sie keine Zeichenfolge der Art `:name:`. (AC-1.8)
- **AC-5:** Given zwei Nutzer mit je einem Orts-Vergleich, nur Nutzer A mit Niederschlag auf Einfach / When beide Mails erzeugt werden / Then zeigt nur die Mail von A den Ampelpunkt, und keiner sieht Daten des anderen. (AC-1.9)
- **AC-6:** Given der Katalog nach dieser Scheibe / When ein Renderer für Orte-Stundenverlauf oder Ausblick eine Zelle baut / Then kommt die Form allein aus `form()` des Katalogs über `darstellung()`, und die Ratsche zählt in den berührten Dateien weniger Funde als vorher. (P1/P2)

## Definition of Done

Alle ACs durch Kern-Tests belegt, umgeschriebene Alt-Tests grün, Ratsche grün mit verkleinerter Liste, Adversary mit Mutations-Gegenprobe gegen Epic-Issue #3260, Nachweis an echter Staging-Mail (Orts-Vergleich mit Stundenverlauf, Trip mit Ausblick).

## Test Plan

Kern: `test_feat_3260_tabelle_form_je_stelle.py`, umgeschriebene Alt-Tests, `test_katalog_stellen_formen.py`, Modus-Matrix `test_issue_811_mode_matrix.py`, Ratsche. Live: `/e2e-verify` mit Validatoren.

## Out of Scope

Kurz-Zusammenfassung, Orte-Telegram `@h` (Scheibe C); Validatoren und Prüfkatalog #3047 (Scheibe D); Trip-Klartext der Altform (B6/#3237).

## Affected Files

Siehe Source; Tests unter `tests/tdd/`, `tests/unit/`.

## Known Limitations

Sonnenstunden bleiben je Stelle verschieden (T7). Die Altform ohne `placements` behält ihren dokumentierten Rest bis zur Migration.

## Architektur-Entscheidung (ADR)

ADR-0127 (Umsetzung), ADR-0124 Nr. 4 (Tabelle).

## Changelog

- 2026-11-21: angelegt (Issue #3260 Schritt 1, Scheibe B).
- 2026-11-21: Tech-Lead-Entscheid bei der Umsetzung: Sonnenstunden-Form über die Wertart (Stundenwert Symbol, Tageswert Wort) statt je Fläche; Bewölkungs-Wortstufe DE/EN im Glossar; Ampelpunkt ohne Abo-Ampel scheitert laut.
