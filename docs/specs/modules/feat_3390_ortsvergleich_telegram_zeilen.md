---
entity_id: feat_3390_ortsvergleich_telegram_zeilen
type: test
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
tags: [einstellung-gleich-mail, was-steht-wo, telegram, ortsvergleich, fallliste]
---

# #3390 Ortsvergleich: Telegram „alle Zeilen“ wieder geprüft nachweisen

## Approval

- [ ] Approved

## Purpose

Die Fallliste „Einstellung = Mail“ führt die beiden Fälle `E-R8-F3N-VERSAND-ORTE-DE` und `-EN` („Telegram alle Zeilen“ beim Ortsvergleich) seit #3385 als `ausnahme`.

„Was steht wo“ zeigt beim Ortsvergleich bereits jede gewählte Metrik als „in Telegram“. Die echte Nachricht lässt nichts weg (`render_compare_telegram`, `src/output/renderers/comparison.py`; PO 16.11., #3047 B-K5/AC-24). Für diese Aussage gibt es Karten-Tests in DE und EN (Block `#3020 G49/G50` in `was_steht_wo_karte.test.ts`).

Die beiden Fälle werden auf diese Tests umgehängt und auf `gruen` gesetzt.

## Source

- Issue #3390; PO-Entscheidung 26.11.2026: Option „Reicht so, nur sauber nachweisen“, keine Marke „in Zeile 2“.
- Kontext: `docs/context/feat-3390-ortsvergleich-telegram-zeilen.md`.
- Die gesonderte Betrachtung der Telegram-Ausgabe ist ein eigenes Issue (#3404).

## Dependencies

- `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` (Fälle ORTE-DE `:1854`, ORTE-EN `:1868`)
- `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts` (Block `#3020 G49/G50`, Testtitel „Orte, de/en: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text“)
- Wächter `tests/tdd/test_einstellung_gleich_mail_fallliste.py` (Verweis muss existieren) und `tests/tdd/test_einstellung_gleich_mail_waechter_3020.py`

## Scope

- MODIFY `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json`:
  - ORTE-DE: `status` `gruen`, `test` auf den Titel mit `de`, `verweis` auf #3390 und die PO-Entscheidung.
  - ORTE-EN: dasselbe mit `en`.
  - Den `_hinweis` zu `E-R8-F3N-VERSAND-*` auf den aktuellen Stand bringen.
- MODIFY `tests/tdd/test_einstellung_gleich_mail_waechter_3020.py`: neuer Test, der sichert, dass beide Fälle `gruen` sind und auf genau diese beiden Karten-Testtitel verweisen.
- Keine Änderung an Produktionscode, Karte, Server oder Katalog.

## Estimated Scope

2 Dateien, unter 40 Zeilen. Reine Test- und Fixture-Änderung, kein Deploy nötig.

## Acceptance Criteria

- **AC-1:** Given die Fallliste nach der Änderung / When der Fall `E-R8-F3N-VERSAND-ORTE-DE` gelesen wird / Then steht er auf `gruen` und verweist auf den Karten-Test „Orte, de: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text“, der existiert und grün ist.
  - Test: `tests/tdd/test_einstellung_gleich_mail_waechter_3020.py` (neuer Test) und `test_einstellung_gleich_mail_fallliste.py`
- **AC-2:** Given die Fallliste nach der Änderung / When der Fall `E-R8-F3N-VERSAND-ORTE-EN` gelesen wird / Then steht er auf `gruen` und verweist auf den Karten-Test „Orte, en: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text“, der existiert und grün ist.
  - Test: wie AC-1
- **AC-3:** Given die Karte „Was steht wo“ beim Ortsvergleich mit neun Metriken / When sie in DE und EN gerendert wird / Then ist jede Metrik in der Telegram-Spalte „an“ (angehakt), ohne Marke und ohne Grenz-Text. Das entspricht der echten Nachricht, die keine Metrik weglässt.
  - Test: `was_steht_wo_karte.test.ts` Block `#3020 G49/G50` (bestehend, bleibt unverändert grün)
- **AC-4:** Given der Lieferstand / When der Diff geprüft wird / Then ist nur die Fallliste und der Wächter-Test geändert, nicht Produktionscode.
  - Test: Adversary-Prüfung des Diffs

## Definition of Done

- Der neue Wächter-Test ist zuerst rot (beide Fälle stehen noch auf `ausnahme`), danach grün.
- `test_einstellung_gleich_mail_fallliste.py`, `test_einstellung_gleich_mail_waechter_3020.py` und `was_steht_wo_karte.test.ts` sind grün.
- Mutations-Gegenprobe:
  - Ein Fall wieder auf `ausnahme` gesetzt muss rot werden.
  - Ein falscher Testtitel muss rot werden.
  - Eine Marke in der Orte-Telegram-Zelle muss in G49/G50 rot werden.

## Known Limitations

- Die Darstellung „ab Platz 8 in einer zweiten Zeile je Ort“ zeigt die Karte bewusst nicht (PO-Entscheidung 26.11.). Die fokussierte Prüfung der Telegram-Ausgabe läuft in #3404.

## Out of Scope

- Neue Marke oder neuer Katalogschlüssel in „Was steht wo“
- Änderungen an der Telegram-Nachricht (#3404)
- #3389 und #3374

## Test Plan

1. RED: neuer Test in `test_einstellung_gleich_mail_waechter_3020.py`, rot gegen den heutigen Stand (`ausnahme`).
2. GREEN: Fallliste anpassen; beide Python-Tests und `was_steht_wo_karte.test.ts` laufen.
3. Mutationen wie in der Definition of Done.

## ADR

Keine neue Entscheidung. ADR-0124 Nr. 3 bleibt gültig: Die Telegram-Schnittlinie in der Karte gilt nur für den Trip.

## Changelog

- 2026-11-26 v1.0: erstellt nach PO-Entscheidung.
