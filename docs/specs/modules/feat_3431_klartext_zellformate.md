---
entity_id: feat_3431_klartext_zellformate
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: feat-3431-klartext-zellformate
tags: [compare, renderer, plaintext, telegram, i18n]
---

# Vergleichsmail Klartext-Übersicht: Zellformate an HTML angleichen (#3431)

## Approval

- [ ] Approved

## Purpose

Die Übersicht im Klartext-Teil der Vergleichsmail zeigt Windrichtung, Sonnenstunden und Wolkenschichten anders als der HTML-Teil derselben Mail (ungerundet, ohne Leerzeichen) und nutzt für fehlende Werte ein anderes Zeichen. Nach dieser Änderung zeigt jeder Kanal pro Größe dasselbe Format aus einer Quelle, dem zentralen Format-Katalog (Folge zu #3425, Kanal-Parität ADR-0095, Anti-Duplikat #1481, Platzhalter #1670).

## Source

- **File:** `src/output/renderers/comparison.py`
- **Identifier:** `_PLAIN_FMT` (Einträge `wind_direction_avg`, `sunny_hours`, `cloud_low_avg`, `cloud_mid_avg`, `cloud_high_avg`) und Klartext-Übersichtsschleife (Platzhalter)

> Schicht: Python-Core (`src/output/renderers/`). Kein Frontend, keine Go-API.
> Trip/Compare-Teilung: nicht berührt (reiner Renderer-Pfad). Mandantentrennung: keine Nutzerdaten bewegt.
> Kanäle: E-Mail-Klartext, Telegram-Vergleich und Kompakt-Vergleichsmail teilen `_PLAIN_ROWS` und ziehen bewusst mit; SMS unberührt (Token-Zeile, #3172); Premium-SMS unberührt.

## Estimated Scope

- **LoC:** ~10 Produktivcode, ~60 Tests/Goldens
- **Files:** 4 plus Goldens
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_format.format_value` | function | Katalog-Formatierung (`style="plain"`), liefert bereits die HTML-Zelle |
| `metric_format.NO_VALUE` | constant | Einheitlicher Platzhalter „–" (U+2013, #1670) |
| `src/output/renderers/email/compare_html.py` (`_fmt_metric`) | function | HTML-Referenz für Paritätstest |
| `src/output/renderers/email/compact_compare.py` | module | nutzt `_PLAIN_ROWS_BY_ID`, zieht mit |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/comparison.py` | MODIFY | 5 Lambdas auf `format_value(..., style="plain")`; Platzhalter `"-"` auf `NO_VALUE`; Kommentar aktualisieren |
| `tests/unit/test_compare_plaintext_html_rows_one_list.py` | MODIFY | `_FORMAT_SNAPSHOT` auf `4.0 h`, `213 °` |
| `tests/unit/test_compare_text_html_bausteine.py` | MODIFY | AC-6-Guard: Übersichtsformate jetzt gleich statt verschieden |
| `tests/golden/vergleichs_mail/*.txt` | MODIFY | Goldens neu (u. a. `Sonne 4.0 h`) |
| `tests/unit/test_feat_3431_klartext_zellformate.py` | CREATE | TDD-Test Parität Klartext == HTML je CV2-Zeile, Platzhalter |

## Implementation Details

Die fünf handgetippten Formate in `_PLAIN_FMT` werden durch den Katalog-Formatierer ersetzt, wie es für Temperatur, Wind, Wolken gesamt und Schnee schon geschieht. Der Platzhalter für fehlende Übersichtswerte wird `NO_VALUE`. Da `_PLAIN_ROWS` geteilt ist, erhalten Telegram-Vergleich und Kompakt-Vergleichsmail dieselben Formate (Variante A, eine Quelle; Variante B mit Parallel-Logik verworfen, verstößt #1481).

Designentscheidung Leerzeichen: Das Leerzeichen vor der Einheit (`213 °`, `4.0 h`) folgt dem zentralen Format-Katalog, den das HTML bereits nutzt (Regel: Leerzeichen vor Einheit, außer `°C` und `%`). Es ist keine neue Produktregel, der Klartext weicht nur durch Handkopien ab.

Renderer-Commit-Gate: Modus-Matrix-Test und `email_spec_validator.py` müssen frisch grün sein.

## Expected Behavior

- **Input:** Orts-Vergleich mit Werten, z. B. Windrichtung 213.4, Sonnenstunden 4.0, Wolken tief 40.3.
- **Output:** Klartext-Übersicht, Telegram-Vergleich und Kompaktmail zeigen `213 °`, `4.0 h`, `40%`; fehlender Wert als „–".
- **Side effects:** Sichtbare Formatänderung in jeder Klartext-Vergleichsmail, im Telegram-Vergleich und in der Kompakt-Vergleichsmail.

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich mit Windrichtung 213.4 Grad / When die Klartext-Übersicht der Vergleichsmail gerendert wird / Then steht dort `213 °` (gerundet, mit Leerzeichen), identisch zur HTML-Zelle derselben Mail
  - Test: Leser der Klartext-Mail sieht dieselbe Windrichtung wie im HTML-Teil, ohne Nachkommastelle.

- **AC-2:** Given ein Orts-Vergleich mit 4.0 Sonnenstunden / When die Klartext-Übersicht gerendert wird / Then steht dort `4.0 h` (mit Leerzeichen), identisch zur HTML-Zelle
  - Test: Leser sieht in Klartext und HTML dieselbe Sonnenstunden-Angabe.

- **AC-3:** Given Wolkenanteile tief/mittel/hoch mit Nachkommastellen (z. B. 40.3) / When die Klartext-Übersicht gerendert wird / Then zeigen die drei Zeilen gerundete Werte wie `40%`, identisch zum HTML
  - Test: Leser sieht keine Dezimalstellen bei den drei Wolkenschichten, Klartext gleich HTML.

- **AC-4:** Given ein Ort ohne Messwert für eine Übersichtszeile / When Klartext-Teil und HTML-Teil der Vergleichsmail gerendert werden / Then steht in beiden als Platzhalter „–" (U+2013), nicht „-"
  - Test: Leser sieht in der leeren Zelle in beiden Teilen dasselbe Zeichen.

- **AC-5:** Given derselbe Orts-Vergleich / When der Telegram-Vergleich und die Kompakt-Vergleichsmail gerendert werden / Then zeigen sie für Windrichtung, Sonnenstunden und Wolkenschichten dasselbe Format wie die Klartext-Mail
  - Test: Leser in Telegram und Kompaktmail sieht `213 °`, `4.0 h`, `40%` (Kanal-Parität).

- **AC-6:** Given ein Orts-Vergleich mit Testwerten für alle übrigen Übersichtszeilen (Temperatur, Wind, Böen, Schnee, Wolken gesamt u. a.) / When die Klartext-Übersicht gerendert wird / Then sind diese Zeilen zeichengleich zum bisherigen Stand und weiterhin gleich zum HTML
  - Test: Leser sieht bei allen anderen Zeilen keine Änderung.

- **AC-7:** Given ein Nutzer mit `language=en` / When die Vergleichsmail im Klartext gerendert wird / Then gelten dieselben Zellformate (`213 °`, `4.0 h`, `40%`, „–") wie auf Deutsch, nur die Beschriftungen sind englisch
  - Test: Englischer Leser sieht dieselben Werte-Formate wie der deutsche.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN CV2-Zeilen mit Testwerten inkl. Nachkommastellen WHEN Klartext-Zelle und HTML-Zelle gebildet werden THEN gleich, je Zeile (rot vor Fix für 5 Zeilen)
- [ ] Test 2: GIVEN fehlender Wert WHEN Klartext und HTML gerendert werden THEN beide `NO_VALUE`
- [ ] Test 3: GIVEN Telegram-Vergleich und Kompaktmail WHEN gerendert THEN Formate wie Klartext
- [ ] Test 4: GIVEN lang=en WHEN gerendert THEN gleiche Zellformate
- [ ] Angepasst: `_FORMAT_SNAPSHOT`, AC-6-Guard, Goldens; Modus-Matrix-Test und `email_spec_validator.py` grün

## Definition of Done

- [ ] Spec freigegeben (`approved`), Tests 1–4 rot vor Umsetzung, danach grün
- [ ] `_FORMAT_SNAPSHOT`, AC-6-Guard und Goldens bewusst nachgezogen; Modus-Matrix-Test und `email_spec_validator.py` frisch grün
- [ ] Mutationsprobe: eine der fünf Zeilen zurück auf Handformat färbt Test 1 rot
- [ ] PR mit allen 6 CI-Checks grün, Staging-E2E, Prod-Deploy, Selftest Exit 0

## Known Limitations

- Weitere Tests mit `°`/`h`-Formaten (z. B. `test_feat_3228_windrichtung_mail.py`, `test_compare_mail_labels_from_register.py`) sind in der Implementierung auf Betroffenheit zu prüfen.
- SMS und Premium-SMS bleiben unverändert (Token-Zeile).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Umsetzung bestehender Entscheidungen (ADR-0095 Kanal-Parität, #1481 eine Quelle, #1670 ein Platzhalter); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-27: Initial spec created
