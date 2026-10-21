# ADR-0093: Das Confidence-Token `C+`/`C~`/`C?` in der SMS entfällt

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — gelebter Stand seit Commit `6924df6ec`, PO-Entscheid 2026-09-08, Issue #2233)
- **Datum:** 2026-10-21
- **Bezug:** Issue #2233, Commit `6924df6ec` („Confidence-Token C+/C~/C? aus SMS-Vertrag streichen"), `docs/reference/sms_format.md` §3.4b (v2.34), CLAUDE.md §„Confidence — NICHT wählbar als Metrik"; löst ADR-0005 Entscheidung Punkt 2 ab

## Kontext

ADR-0005 (2026-06-10) erlaubt `confidence_pct` an genau drei Stellen, darunter als
**SMS-Token** `C+`/`C~`/`C?` (ADR-0005:21). Das Token stammt aus dem SMS-Vertrag v2.1
(Issue #121). Laut Commit `6924df6ec` wurde es **nie im Builder erzeugt** — der Vertrag
versprach etwas, das der Code nicht lieferte. Das SMS-Zeichenbudget (≤ 160 Zeichen) ist knapp.

Am 2026-09-08 hat der PO entschieden, das Token nicht nachzurüsten (#2233). Der Commit
`6924df6ec` hat es aus `sms_format.md` und CLAUDE.md gestrichen. In ADR-0005 stand die Erlaubnis
aber weiter. Das war eine stille Rücknahme: Die Regel „Abweichung ⇒ neues ADR" war verletzt
(Doku-Audit 2026-10, Punkt 1a).

## Entscheidung

1. **Es gibt kein Confidence-Token in SMS oder Premium-SMS.** `C+`/`C~`/`C?` gehören nicht
   zum SMS-Wire-Vertrag (`sms_format.md` §3.4b: „entfallen (v2.34, Issue #2233)").
2. `confidence_pct` darf damit nur noch an **zwei** Stellen erscheinen: (1) als
   Verlässlichkeits-Hinweis im E-Mail-Textblock und (2) in der internen Aggregation bzw. im
   Scoring. So steht es in CLAUDE.md.
3. Der Rest von ADR-0005 gilt unverändert. Confidence ist keine pro Etappe wählbare Metrik.
   Es bleibt bei `selectable=false`, beim Filter in `GET /api/metrics` und dabei, dass
   Render-Pfade Alt-Trips still ignorieren.
4. Das Debug-Token `DBG[{provider} {confidence}]` (`sms_format.md`) ist **nicht** betroffen. Dort
   meint „confidence" die Sicherheit der Provider-Auswahl, nicht `confidence_pct`.

## Verworfene Alternativen

- **Token im Builder nachrüsten, um den Vertrag zu erfüllen:** verworfen durch den PO-Entscheid
  2026-09-08. Es kostet SMS-Zeichen für eine Meta-Aussage. Zudem steht es der Linie von
  ADR-0005/#710 entgegen, Confidence nicht wie einen Wetterwert neben lokale Größen zu stellen.
- **ADR-0005 still lassen, nur `sms_format.md` korrigieren:** Das war der Ist-Zustand bis zu
  diesem ADR. Verworfen, weil ADR-0005 damit weiter etwas erlaubte, das es nicht gibt. Ein
  späterer Fix hätte sich darauf berufen können. Das ist genau das Regress-Muster, gegen das
  ADR-0005 geschrieben wurde.

## Konsequenzen

- **Positiv:** Vertrag, ADR und Code stimmen überein. Kein SMS-Zeichen geht an eine Meta-Aussage.
- **Negativ / Preis:** SMS- und Premium-SMS-Leser bekommen keinen Verlässlichkeits-Hinweis. Er
  steht nur in der E-Mail. Das reibt sich mit der Kanal-Parität (ADR-0095: jeder Kanal beantwortet
  jede Frage). Es ist hier als bewusster Zuschnitt des PO festgehalten, nicht als gelöst.
- **Folgepflichten:** Specs, die das Token noch als Soll führen, sind veraltet
  (`forecast_confidence.md`, `warn_unavailable_hint.md`, Doku-Audit 2026-10 Punkt 4). Eine
  Wiedereinführung braucht ein neues ADR.
