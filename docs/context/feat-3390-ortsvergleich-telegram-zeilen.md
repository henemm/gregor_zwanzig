# Kontext: #3390 Ortsvergleich, „Was steht wo“ und die Telegram-Zeilen

## Request Summary

Beim Ortsvergleich landen in der Telegram-Nachricht alle gewählten Zeilen. Bis #3385 stand das im alten Versand-Baustein: „Telegram alle Zeilen (ab Platz {platz} in einer zweiten Zeile je Ort)“. Seitdem führt die Fallliste die Fälle `E-R8-F3N-VERSAND-ORTE-DE/-EN` als `ausnahme` (Verweis #3390).

## Befund (gelesen, Datei:Zeile)

- Die Karte rendert nur die Zellen, die der Server liefert. Zellenbau: `src/services/placements_view_service.py:315-327` (`_zelle`). Die Marke `NUR_TAGESWERT` gibt es nur beim Trip (`_trip_muster` → `_trip_nur_tageswert`, `:490`, `:613-626`). `_orte_muster` (`:776-810`) setzt keine Telegram-Marke. Go reicht die Antwort nur durch (`internal/handler/placements.go:84-106`).
- Die echte Orte-Telegram-Nachricht ist `render_compare_telegram` (`src/output/renderers/comparison.py:822ff`, Block `:928`, `:955-970`). Je Ort stehen in Zeile 1 die ersten 7 Metriken, alle weiteren in Zeile 2 desselben Orts. Es fällt keine Metrik weg (PO-Entscheidung 16.11., #3047 B-K5/AC-24). Im Kurzstil ist Telegram gleich SMS, und die Telegram-Spalte ist gesperrt (`_spalten` `rests="kurzstil"`).
- Die Karte zeigt beim Ortsvergleich heute schon jede gewählte Metrik als „an“ in der Telegram-Spalte (angehakt, ohne Marke). Belegt ist das durch die Tests in `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts`, Block `#3020 G49/G50`: „Orte, de/en: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text“.
- Die Aussage „alle Zeilen landen in Telegram“ zeigt die Karte also schon, in DE und EN. Nicht gezeigt wird nur die Darstellungsdetail-Angabe „ab Platz 8 in einer zweiten Zeile je Ort“.
- Die Fallliste (`tests/fixtures/einstellung_gleich_mail/fallliste_editor.json`, ORTE-DE `:1854`, ORTE-EN `:1868`) verweist heute auf Tests, die Telegram nicht prüfen (Orte-Spaltenkopf bzw. EN-Texte).

## Related Files

| Datei | Rolle |
|---|---|
| `src/services/placements_view_service.py` | Zellenbau, Muster Trip/Orte |
| `src/output/renderers/comparison.py` | echte Orte-Telegram-Nachricht |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts` | Marken-Abbildung `MARKE` |
| `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts` | Karten-Tests, G49/G50 |
| `tests/tdd/test_placements_tabelle_endpoint.py` | Endpunkt-Tests, `test_ac17_*` als Vorlage für den Abgleich mit der echten Nachricht |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py`, `test_einstellung_gleich_mail_waechter_3020.py` | Wächter für die Fallliste |
| `docs/adr/0124-was-steht-wo-eine-tabelle.md`, `docs/specs/modules/feat_3122_was_steht_wo.md` | Vorgaben (Marke „nur Tageswert“ nur beim Trip) |

## Existing Patterns

- Der Server rechnet, die Karte zeigt nur an. Marken werden aus derselben Berechnung abgeleitet wie die echte Nachricht.
- Jeder Fall in der Fallliste verweist auf einen existierenden Test. Eine `ausnahme` braucht einen Verweis.

## Risks & Considerations

- Ob die Karte zusätzlich eine Marke „in Zeile 2“ ab Platz 8 zeigen soll, ist eine Produktentscheidung (siehe Issue #3390).
  - Ohne Marke reicht es, die Fallliste auf die G49/G50-Tests umzuhängen.
  - Mit Marke sind nötig:
    - Server-Berechnung aus dem Renderer
    - neuer Katalogschlüssel (de/en)
    - G49/G50 neu fassen
    - ein Python-Abgleich mit der echten Nachricht
- Für den Kurzstil darf keine Marke berechnet werden.
