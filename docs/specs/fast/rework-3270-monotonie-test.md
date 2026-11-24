---
entity_id: rework_3270_monotonie_test
type: fast
created: 2026-11-24
status: draft
---

# Mini-Spec: Monotonie-Regel der gemessenen Wegstrecke einzeln durch Tests bewachen

**Issue #3270** (Duplikat: #3271). Nebenbefund F001 aus #3208, Teil von #1196.

## Problem

`stage_measured_distances` (`src/services/trip_segments.py`) wertet eine Etappe als unvermessen,
sobald ein Kilometerwert nicht strikt steigt (`span <= 0`). Kein Test bemerkt, wenn diese Regel
entfällt: In allen Testfällen liegen die Wegpunkte an verschiedenen Orten, deshalb greift dort
immer auch die nachfolgende Plausibilitätsprüfung gegen die Luftlinie.

## Was ändert sich

- Nur `tests/tdd/test_gehzeit_etappenregel.py`: ein parametrisierter Test mit zwei Fällen
  (gleicher km-Wert; fallender km-Wert innerhalb der 10-m-Zugabe).
- Aufbau: G1 und G2 an identischer Position (Luftlinie 0), G3 an anderer Position mit plausibler
  gemessener Strecke von 2 x Luftlinie. G3 ist nötig: Mit G1 und G2 allein wäre die Gehzeit beim
  Fall „gleich" mit und ohne Regel dieselbe (0 min), der Test könnte dort nie rot werden.

## Was darf sich nicht ändern

- Kein Produktcode, kein Nutzerverhalten. Die Regel wirkt heute korrekt.
- Bestehende Tests bleiben unverändert; keine Mocks im neuen Test.

## Acceptance Criteria

- **AC-1:** Given eine Etappe, deren erste zwei Wegpunkte am selben Ort liegen und denselben km-Wert tragen, und ein dritter Wegpunkt mit doppelter Luftlinie als gemessener Strecke / When die Ankunftszeiten berechnet werden / Then folgt die Ankunft am dritten Wegpunkt der Luftlinie und nicht der gemessenen Strecke.
- **AC-2:** Given dieselbe Etappe, deren zweiter km-Wert um 5 m fällt (innerhalb der 10-m-Zugabe) / When die Ankunftszeiten berechnet werden / Then folgt die Ankunft am dritten Wegpunkt ebenfalls der Luftlinie.
- **AC-3:** Given die Mutation G1b-monotonie (Prüfung `span <= 0` abgeschaltet) / When die Testdatei läuft / Then werden beide neuen Fälle rot und alle bisherigen Fälle bleiben grün; nach Wiederherstellung ist die ganze Datei grün.
- **AC-4:** Given die abgeschwächte Regel `span < 0` statt `span <= 0` / When die Testdatei läuft / Then wird der Fall „gleich" rot.

## Automatisierte Prüfung

1. Testdatei auf unverändertem Code: grün.
2. Mutationen aus AC-3 und AC-4 per String-Ersetzung mit externer Sicherungskopie: die genannten
   Fälle rot, Wiederherstellung per Prüfsumme belegt. Protokoll unter
   `docs/artifacts/rework-3270-monotonie-test/`.

## Inline-Test

- [ ] `test_ac2b_nicht_steigend_am_selben_ort_faellt_zurueck` mit den Fällen `gleich` und `leicht-fallend`
