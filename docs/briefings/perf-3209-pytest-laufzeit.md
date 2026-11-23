---
spec_file: docs/specs/modules/perf_3209_pytest_xdist_ci.md
spec_sha256: a4ef064003a2b56225b83b90771d019dcd3e97852d483a2e7e3b231e08e64e79
spec_frozen_sha256: bb7b6870709677349d365ae697cf37812c11f615011b07f6df69fe9e7320a81e
---

# PO-Briefing: perf-3209-pytest-laufzeit

- **Spec:** docs/specs/modules/perf_3209_pytest_xdist_ci.md
- **Issue:** #3209
- **Erstellt:** 2026-11-22

## Was gebaut wird

Der automatische Prüflauf der Python-Tests bei jeder Änderung läuft parallel und wird deutlich schneller.

## Definition of Done

Drei aufeinanderfolgende Prüfläufe sind grün, dauern deutlich unter den bisherigen 30 Minuten, und die Testzahl ist nachweislich nicht geschrumpft.

## Wie geprüft wird

Echte Testläufe belegen Schutzwächter, Netzsperre und Gruppierung; nicht belegt ist, dass jeder Wackeltest unter Parallelbetrieb stabil bleibt.

## Kritische Anmerkungen

- Ticket verlangte Einzeltests zu beschleunigen und lokalen 41-Minuten-Lauf zu senken; beides ausgelagert (#3279, #3278), lokal bleibt alles langsam.
- Zielwert "deutlich unter 30 Minuten" mit Richtwert 15 Minuten ist keine harte Schwelle.

## Freigabe-Frage

Genügt dir die Beschleunigung nur des automatischen Prüflaufs, während lokaler Lauf und Einzeloptimierung auf Folge-Tickets verschoben werden?

## Ampel

Ampel: rot
