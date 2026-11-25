---
spec_file: docs/specs/modules/feat_3351_altfelder_datenlauf.md
spec_sha256: e873e94424a167420df22341f657b23bb12d9e76d91db396af94b1558313e34e
spec_frozen_sha256: 93204bf605f040dd1f5fdb1d08be9da8334a6aa1275101ecd2df23072afd456f
---

# PO-Briefing: feat-3351-altfelder-datenlauf

- **Spec:** docs/specs/modules/feat_3351_altfelder_datenlauf.md
- **Issue:** #3351
- **Erstellt:** 2026-11-25

## Was gebaut wird

Ein einmaliges Aufräum-Programm entfernt die zehn veralteten, wirkungslosen Einstellungsfelder aus allen gespeicherten Trips und Ortsvergleichen, ohne sichtbare Änderung.

## Definition of Done

Nach dem Lauf auf Test- und Live-System zeigt die Nachzählung null Altfelder auf Live, mit Sicherung je Nutzer vorab.

## Wie geprüft wird

Automatische Tests mit echten Testdaten belegen Aufräumen, Sicherung, Wiederholbarkeit und Schutz; die Nachzählung auf Test- und Live-System ist nur manuell nachweisbar.

## Kritische Anmerkungen

- Test-System erreicht nicht null: Ein Abo ohne Tabelle bleibt bewusst unangetastet, das Issue verlangt wörtlich null.
- #3102 wird nicht abgeschlossen, nur kommentiert; das Issue sagt "Abschluss als Nachweis".
- Kein Dauerwächter gegen Wiederkehr; stattdessen Nachzählung nach einigen Tagen.

## Freigabe-Frage

Genügt es, dass auf dem Test-System ein Abo unbereinigt bleibt und #3102 offen bleibt?

## Ampel

Ampel: rot
