---
spec_file: docs/specs/modules/fix_2047_s2_ci_prod_gate.md
spec_sha256: ee34b50459154f6fc02fd703b1d4d56aedcb28216c01bfa69befe670f47275a7
---

# PO-Briefing: fix-2047-s2-prod-gate

- **Spec:** docs/specs/modules/fix_2047_s2_ci_prod_gate.md
- **Issue:** #2047
- **Erstellt:** 2026-10-06

## Was gebaut wird

Die automatische Auslieferung nach Produktion stellt sich keine Freigabe mehr selbst aus, sondern wartet auf die echte Verhaltensprüfung.

## Definition of Done

Nach einem Merge liefert die Automatik nur mit echtem Prüfnachweis aus, sonst meldet sie offen "nicht ausgeliefert" und bleibt grün.

## Wie geprüft wird

Tests belegen Warte-Verhalten und Doppel-Auslieferungsschutz an Wegwerf-Kopien; echte Produktion und Meldungstexte werden nicht automatisch getestet.

## Kritische Anmerkungen

- Ohne Nachweis wird still nicht ausgeliefert (grün statt rot); Auslieferung läuft im Normalfall weiter über die Session.
- Keine Tests für Meldungstexte, Selbsttest nach Auslieferung, Rot-nur-bei-Fehler, Doku-Angaben und Lieferreihenfolge.
- Änderung am Deploy-Skript im Infra-Repo ist sofort live, vor dem eigentlichen Umbau nötig.

## Freigabe-Frage

Ist es für dich in Ordnung, dass die Automatik ohne echten Nachweis nur meldet und Auslieferung meist per Session erfolgt?
