---
spec_file: docs/specs/fast/rework-3270-monotonie-test.md
spec_sha256: 9b94fb184a822b6fd1444d673124e1a5d4185c70e5f0f3b985e5d8bf7e2fa219
spec_frozen_sha256: 6a40a6e5227addb2063fe902a8ce8d5631097ca2dc036a34802865fffa678c55
---

# PO-Briefing: rework-3270-monotonie-test

- **Spec:** docs/specs/fast/rework-3270-monotonie-test.md
- **Issue:** #3270
- **Erstellt:** 2026-11-24

## Was gebaut wird

Ein neuer automatischer Test sichert die Regel ab, dass nicht steigende Kilometerwerte bei der Gehzeit zur Luftlinie zurückfallen.

## Definition of Done

Der neue Test ist grün, und wird die Regel testweise abgeschaltet, schlagen genau die neuen Fälle fehl, alle alten bleiben grün.

## Wie geprüft wird

Zwei Testfälle (gleicher und leicht fallender Kilometerwert) plus gezielte Gegenprobe durch Regel-Abschaltung; Produktverhalten wird nicht berührt und nicht neu geprüft.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
