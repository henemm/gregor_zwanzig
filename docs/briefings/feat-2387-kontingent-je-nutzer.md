---
spec_file: docs/specs/modules/forecast_budget_je_nutzer.md
spec_sha256: f1082e8ed3e2b4251587ea5f757cddeed1c30af1ecb484229ebeca819d569038
---

# PO-Briefing: feat-2387-kontingent-je-nutzer

- **Spec:** docs/specs/modules/forecast_budget_je_nutzer.md
- **Issue:** #2387
- **Erstellt:** 2026-09-20

## Was gebaut wird

Jeder Nutzer bekommt einen eigenen Tages-Zähler für Wetterabrufe, damit ein Vielnutzer nicht fremde Alarme abschaltet.

## Definition of Done

Verbraucht ein Nutzer viel, laufen Alarme anderer weiter — außer wenn alle Nutzer zusammen das Tageslimit ausschöpfen.

## Wie geprüft wird

Automatisierte Tests im Python-Kern prüfen zwei Nutzer gleichzeitig, Migrationsbestand und Ausfallsicherheit; echtes Mehrnutzer-Verhalten wird nicht beobachtet.

## Kritische Anmerkungen

- Ab 100% Gesamtverbrauch (nicht mehr ab 95%) wird der unbeteiligte Nutzer wieder gedrosselt — Kernproblem bleibt am oberen Rand.
- Der faire Anteil schwankt im Tagesverlauf und kann sinken, sobald weitere Nutzer aktiv werden — keine feste Zusage.
- Ein Abrufpfad zählt weiterhin nur im gemeinsamen Topf, nie im Topf eines Nutzers.

## Freigabe-Frage

Ist es akzeptabel, dass bei vollem Tageslimit weiterhin auch unbeteiligte Nutzer gedrosselt statt geschützt bleiben?
