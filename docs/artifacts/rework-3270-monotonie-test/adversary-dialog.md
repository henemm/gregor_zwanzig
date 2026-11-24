# Adversary Dialog — rework-3270-monotonie-test
Spec: docs/specs/fast/rework-3270-monotonie-test.md
Datum: 2026-11-24

## Checkliste
- [x] **AC-1:** Given eine Etappe, deren erste zwei Wegpunkte am selben Ort liegen und denselben km-Wert tragen, und ein dritter Wegpunkt mit doppelter Luftlinie als gemessener Strecke / When die Ankunftszeiten berechnet werden / Then folgt die Ankunft am dritten Wegpunkt der Luftlinie und nicht der gemessenen Strecke.
- [x] **AC-2:** Given dieselbe Etappe, deren zweiter km-Wert um 5 m fällt (innerhalb der 10-m-Zugabe) / When die Ankunftszeiten berechnet werden / Then folgt die Ankunft am dritten Wegpunkt ebenfalls der Luftlinie.
- [x] **AC-3:** Given die Mutation G1b-monotonie (Prüfung `span <= 0` abgeschaltet) / When die Testdatei läuft / Then werden beide neuen Fälle rot und alle bisherigen Fälle bleiben grün; nach Wiederherstellung ist die ganze Datei grün.
- [x] **AC-4:** Given die abgeschwächte Regel `span < 0` statt `span <= 0` / When die Testdatei läuft / Then wird der Fall „gleich" rot.

## Dialog

### Runde 1
**Adversary:** Frischer Lauf der Testdatei: 11 passed (docs/artifacts/rework-3270-monotonie-test/adversary-test-output.txt). Mutationen M1 (Prüfung aus) und M2 (span < 0) selbst nachgebaut: M1 rot genau in ac2b[gleich] und ac2b[leicht-fallend], alle 9 übrigen grün; M2 rot genau in ac2b[gleich]. Sha256 nach Restore identisch (0a25a3fe...b19e). Frage: Hält die Monotonie-Regel die neuen Fälle wirklich allein? Unter M9/M10 (Plausibilität aus bzw. continue) bleiben ac2b-Fälle grün und nur ac1 wird rot, also trägt die Plausibilitätsprüfung die neuen Fälle nicht. Gegenfrage: Wirkt die Zusicherung dort, wo sie wirkt? Der Test ruft compute_stage_arrivals (Nutzerpfad der Ankunftszeit), nicht stage_measured_distances direkt, und prüft die Ankunft an G3.
**Implementierer:** (Beweis vom Adversary selbst erhoben, Herkunft: eigener Lauf adversary-mutations.txt M1, M2, M9, M10.) Aufbau G1=G2 am selben Ort, G3 mit 2 x Luftlinie bestätigt: ohne Regel würde G3 der gemessenen Strecke folgen und der Test rot werden (M1).

### Runde 2
**Adversary:** Randfälle und eigene Verfälschungen (adversary-mutations.txt). Gefangen: M3 continue statt return None (4 rot), M4/M5 Toleranz -0.01 (beide neuen Fälle rot, da -0.005 darunter fällt), M8 nur letztes Paar geprüft, M11 Monotonie nur bei Luftlinie > 0, M13 span == 0 (leicht-fallend rot), M15 immer None (ac4, ac8 rot). Überlebt: M6 (span <= 0.001, Toleranz auf der steigenden Seite), M7 (Monotonie nur am ersten Paar), M12 (Zugabe 10 m auf 100 m), M14 (keine Normierung auf Etappenstart), M16 (Reihenfolge Monotonie/Plausibilität vertauscht). Einordnung: M16 ist ein äquivalenter Mutant (beide Zweige geben None zurück). M12/M14 liegen außerhalb der Spec (Plausibilitätszugabe, Normierung, nicht Monotonie). M6 betrifft winzig steigende Werte, die Spec behandelt nur nicht steigende (AC-1/2). M7: die neuen Fälle verletzen nur das erste Paar, ein später verletztes Paar wird allein durch die Monotonie-Regel von keinem Test gehalten; das liegt außerhalb der vier ACs (diese verlangen nur erstes Paar), ist aber eine Restlücke. Keine Mocks im neuen Test (nur bestehender ac5 nutzt monkeypatch, unverändert). Bestehende Tests: git diff HEAD~1 für tests zeigt 23 Einfügungen, keine Löschungen; src unverändert.
**Implementierer:** (Beweis vom Adversary selbst erhoben, Herkunft: eigener git diff und Mutationsläufe.) Überlebende sind ausdrücklich außerhalb des Umfangs von AC-1 bis AC-4; M7 als LOW-Hinweis festgehalten.

## Findings und Confirmations

Confirmation: AC-1
Code reference: tests/tdd/test_gehzeit_etappenregel.py:118
Evidence: Fall gleich, G3 mit 2 x Luftlinie; Regel aus (M1) macht ihn rot, Plausibilität aus (M9) nicht, also hält ihn allein die Monotonie. Status: CONFIRMED

Confirmation: AC-2
Code reference: src/services/trip_segments.py:147
Evidence: Fall leicht-fallend (-0.005 km) wird nur von span <= 0 gefangen; M1, M2? (M2 fängt ihn nicht, korrekt), M4, M5, M13 prüfen die Grenze. Status: CONFIRMED

Confirmation: AC-3
Code reference: tests/tdd/test_gehzeit_etappenregel.py:111
Evidence: M1 rot genau in beiden ac2b-Fällen, 9 andere grün, Restore per Prüfsumme identisch. Status: CONFIRMED

Confirmation: AC-4
Code reference: src/services/trip_segments.py:147
Evidence: M2 span < 0 rot genau in ac2b[gleich]. Status: CONFIRMED

Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: src/services/trip_segments.py:145
  Description: Mutant M7 (Monotonie nur am ersten Paar) überlebt, weil die neuen Fälle nur das erste Paar verletzen.
  Spec requirement: außerhalb AC-1 bis AC-4
  Conflict: Keine Spec-Verletzung, nur Restlücke für spätere Paare ohne Luftlinien-Hilfe.
  Remediation: Optional Folge-Fall mit verletztem zweiten Paar.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: src/services/trip_segments.py:147
  Description: Mutant M6 (span <= 0.001) überlebt; winzig steigende Werte sind ungetestet.
  Spec requirement: außerhalb AC-1 bis AC-4
  Conflict: Keine Spec-Verletzung.
  Remediation: Nur bei Bedarf.

## Herkunft der Vorbedingungen

- precondition_origins.default_lang: kein Sprachprofil konfiguriert

## Verdict

**VERIFIED**

## Geprüfte Dateien

- sha256:0a25a3feeedb8f2c24eb71442d8137ff7226938b997ad784d2d576e5f4b1b19e  src/services/trip_segments.py
- sha256:f22dc8a55da6b02b41faca0dc9aad201c48c0b08083ad19ebfa3d50413b6da42  tests/tdd/test_gehzeit_etappenregel.py

## Prüfbasis

- base: 74afd33915a6660d88bd22816a381259b395fc8e
- blob:3b5bbd798cad4095e3965ac9c6cffa5ebda5a546  src/services/trip_segments.py
- blob:ba08a120c453fadb5b0cd240e75c185eb6cceb27  tests/tdd/test_gehzeit_etappenregel.py
