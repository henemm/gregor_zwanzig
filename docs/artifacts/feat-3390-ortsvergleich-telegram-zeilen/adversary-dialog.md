# Adversary Dialog — feat-3390-ortsvergleich-telegram-zeilen
Spec: docs/specs/modules/feat_3390_ortsvergleich_telegram_zeilen.md
Datum: 2026-11-26 09:06

## Checkliste
- [x] **AC-1:** Given die Fallliste nach der Änderung / When der Fall `E-R8-F3N-VERSAND-ORTE-DE` gelesen wird / Then steht er auf `gruen` und verweist auf den Karten-Test „Orte, de: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text“, der existiert und grün ist.
- [x] **AC-2:** Given die Fallliste nach der Änderung / When der Fall `E-R8-F3N-VERSAND-ORTE-EN` gelesen wird / Then steht er auf `gruen` und verweist auf den Karten-Test „Orte, en: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text“, der existiert und grün ist.
- [x] **AC-3:** Given die Karte „Was steht wo“ beim Ortsvergleich mit neun Metriken / When sie in DE und EN gerendert wird / Then ist jede Metrik in der Telegram-Spalte „an“ (angehakt), ohne Marke und ohne Grenz-Text. Das entspricht der echten Nachricht, die keine Metrik weglässt.
- [x] **AC-4:** Given der Lieferstand / When der Diff geprüft wird / Then ist nur die Fallliste und der Wächter-Test geändert, nicht Produktionscode.

## Dialog

### Runde 1
**Adversary:** Schwerpunkt 1 (Stimmt die Aussage?): `render_compare_telegram` baut je Ort `_telegram_location_block` (src/output/renderers/comparison.py:928). Die ersten Plätze laut Layout bilden Zeile 1, `zweite = [mid for mid in available_ids if mid not in erste]` geht als Zeile 2 in denselben Ortsblock, und es gibt keinen Kappungshinweis. Der bestehende Test `test_ac24_telegram_zeilen_ab_8_in_zweiter_zeile` (tests/tdd/test_3047_runde7_orte_kanaele.py:264) rendert 10 Metriken in DE und EN: Zeilen 7 plus 3, Folge vollständig, kein Hinweis. Die Aussage „keine Metrik fällt weg“ stimmt, der Fall ist berechtigt grün. Schwerpunkt 2: Der Karten-Test (was_steht_wo_karte.test.ts:613-650, `orteOhneMarke(NEUN)`) prüft für alle 9 Metriken in DE und EN `data-zustand=on`, `checked`, nicht `disabled`, keine `et-marke` und keinen Grenz-Text, dazu die Zeilenfolge. Das ist genau „alle neun, ohne Marke“. Schwäche: Der Antwort-Mock stammt aus dem Test selbst; die echte Server-Antwort liegt außerhalb dieser Scheibe (#3020/#3404). Schwerpunkt 4 (AC-4): Gestaged sind nur Fallliste und Testprotokoll, der RED-Commit trägt nur Wächter-Test und RED-Ausgabe. Kein Produktionscode.
**Implementierer:** keine Antwort (Adversary-Lauf).

### Runde 2
**Adversary:** Mutationen (Sicherung im Scratchpad, per cmp identisch zurück): M1 ORTE-DE auf `ausnahme` ⇒ Wächter rot (1 failed). M2 EN-Titel verfälscht ⇒ rot (3 failed). M3 DE-Titel auf den alten Spaltenkopf-Test umgehängt ⇒ rot (1 failed). M4a Marke `nur_tageswert` in der Telegram-Zelle des Karten-Mocks ⇒ Karten-Test rot (4 fail). M4b Telegram-Zelle auf `off` ⇒ rot (5 fail). M5 an der Wirkstelle (Produktion `EinstellTabelle.svelte`, Marke bei `zustand=on` anzeigen, danach zurückgenommen) ⇒ rot (44 fail). Jede geforderte Mutation wird gefangen. Tests: pytest 68 passed; node 49 pass, 0 fail, 3 todo (vorbestehend). Einschränkung (kein Befund): Die Fallliste hängt am Titelverweis; den Inhalt der Nachricht schützt der Python-Test aus Runde 1.
**Implementierer:** keine Antwort.

## Findings

Keine.

## Confirmations

Confirmation: C1
  AC: AC-1
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:1854
  Evidence: ORTE-DE steht auf gruen und verweist auf den DE-Karten-Test. Wächter grün, Mutationen M1 und M3 rot.
  Status: CONFIRMED

Confirmation: C2
  AC: AC-2
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:1868
  Evidence: ORTE-EN steht auf gruen und verweist auf den EN-Karten-Test. Mutation M2 rot.
  Status: CONFIRMED

Confirmation: C3
  AC: AC-3
  Code reference: frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts:635
  Evidence: Je Metrik on, checked, nicht disabled, keine Marke, kein Grenz-Text in DE und EN. Nachricht lässt laut comparison.py:928 und test_ac24 nichts weg. M4a, M4b, M5 rot.
  Status: CONFIRMED

Confirmation: C4
  AC: AC-4
  Code reference: tests/tdd/test_einstellung_gleich_mail_waechter_3020.py:207
  Evidence: Diff berührt nur Fallliste und Wächter-Test plus Artefakte, kein Produktionscode.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

VERDICT: VERIFIED

Tests: 68 pytest passed, 49 node pass, 0 failed. Mutationen M1-M5 alle rot. Regressions: none. Checklist: 4/4 points proven.

## Geprüfte Dateien

- sha256:07360e1df36a2bc55275dc85be4ce889dfaa2de833833b9785b626dd3142030d  frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts
- sha256:792c614e9110e4c381e2604fdcd13b1519b09bc19780107c5d79ffe452d3c3fa  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- sha256:3503a2258c32203128869f606ca5ece979e9b0ccfdcec9d4932452c7e7603373  tests/tdd/test_einstellung_gleich_mail_waechter_3020.py

## Prüfbasis

- base: d23a265f9bcfc01f050c1ae86a4d7910a64cc623
- blob:38eba5775bd19776ded232240be95554f7dde843  frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts
- blob:f1bd1901ccf6fe545597ea0eb223bcc441b25709  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- blob:2a5c9d641114afc5a770325c8ba07accb331cc91  tests/tdd/test_einstellung_gleich_mail_waechter_3020.py
