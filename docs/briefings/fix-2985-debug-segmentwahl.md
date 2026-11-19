---
spec_file: docs/specs/fast/fix-2985-debug-segmentwahl.md
spec_sha256: c914da365abb6fce489c209345c67b93bd1429d596639b7ec43afc95d03b17a0
spec_frozen_sha256: 1d091cbf9f60118e090720749967b223cf3c8fa0095f6b127d176f99ff81e0d2
---

# PO-Briefing: fix-2985-debug-segmentwahl

- **Spec:** docs/specs/fast/fix-2985-debug-segmentwahl.md
- **Issue:** #2985
- **Erstellt:** 2026-11-19

## Was gebaut wird

Der Radar-Testalarm auf Staging wählt die Etappe jetzt mit demselben Baustein wie der echte Radar-Alarm.

## Definition of Done

Der Testalarm wählt dieselbe Etappe wie der echte Alarm, auch bei Ankunft nach Mitternacht; bei heute aktiver Etappe bleibt alles unverändert.

## Wie geprüft wird

Ein neuer Test mit echten Trips prüft drei Fälle, eine Gegenprobe beweist seine Wirksamkeit; Versand und Staging-Sperre prüft er nicht.

## Kritische Anmerkungen

- Bewusste Abweichung vom echten Alarm: Bei nur vergangenen Etappen greift ein Testrückfall auf die erste Etappe; in der Spec benannt.
- Der Fall „keine Etappe vorhanden" (Antwort no_segment) hat keine eigene Acceptance Criterion.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
