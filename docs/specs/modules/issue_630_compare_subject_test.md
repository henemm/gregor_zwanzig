---
entity_id: issue_630_compare_subject_test
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [tests, compare, email, subject, refactor]
---

# #630 Compare-Betreff hermetisch testbar machen

## Approval

- [ ] Approved

## Purpose

`TestEmailSubject::test_subject_is_wetter_vergleich` ist fragil: Es prüft eine
reine Betreff-Konstante (`Wetter-Vergleich: …`) über den schweren, netzabhängigen
Voll-Vergleichspfad und scheitert ohne Orte an `ValueError`. Die Betreff-Erzeugung
wird in eine reine Funktion ausgelagert (additiv, Output identisch), die der Test
direkt hermetisch prüft.

## Source

- **File:** `src/services/compare_subscription.py` (reine Betreff-Funktion)
- **Identifier:** Betreff-Builder (von `run_comparison_for_subscription` genutzt)

## Estimated Scope

- **LoC:** ~10 produktiv (Funktion extrahieren) + Test-Anpassung
- **Files:** `compare_subscription.py`, `tests/tdd/test_sport_aware_scoring.py`
- **Effort:** low

## Acceptance Criteria

**AC-1:** Given die Betreff-Erzeugung des Compare-Briefings, When sie in eine reine
Funktion ausgelagert ist, Then liefert diese exakt `Wetter-Vergleich: <name> (<dd.mm.yyyy>)`
und `run_comparison_for_subscription` nutzt sie — der erzeugte Betreff ist
zeichengleich zum bisherigen Verhalten.

**AC-2:** Given der Test `test_subject_is_wetter_vergleich`, When er die reine
Funktion direkt aufruft, Then prüft er die Benennung (enthält `Wetter-Vergleich`,
enthält kein `Ski`) OHNE Netzaufruf, ohne geladene Orte und ohne `ValueError`.

**AC-3:** Given die Änderung, When die Suite läuft, Then ist der Test grün und es
gibt keine Verhaltensänderung am tatsächlich versendeten Betreff (keine andere
Compare-Mail-Logik berührt).

## Out of Scope

- Sonstige Compare-Pipeline-Logik, Scoring, Renderer.

## Test-Strategie

Mock-frei: reine Funktion mit echten Eingaben (Name + Datum) → echter String-Output,
direkte Assertion. Kein Mock, kein Netz.
