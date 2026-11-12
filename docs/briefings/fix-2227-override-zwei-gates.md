---
spec_file: docs/specs/modules/fix_2227_override_zwei_gates.md
spec_sha256: 51945d5fecb1156fc89b1ff8cc2fabbb88502ca42ea13b49a64b88a7c2a826e1
spec_frozen_sha256: 131ffbba77e137ee6ec22729b99d5e436127632b228b501157f7ab76ca9630c6
---

# PO-Briefing: fix-2227-override-zwei-gates

- **Spec:** docs/specs/modules/fix_2227_override_zwei_gates.md
- **Issue:** #2227
- **Erstellt:** 2026-11-12

## Was gebaut wird

Dein Freigabe-Wort „override" öffnet die Sperre gegen ungeschützte Komplett-Testläufe nicht mehr.

## Definition of Done

Ein Komplett-Testlauf wird auch nach „override" blockiert, während benannte Tests, reine Auflistung und der sichere Offline-Lauf weiter funktionieren.

## Wie geprüft wird

Automatische Tests starten die Sperre echt, mit und ohne Freigabe; nicht geprüft wird die Versand-Sperre, nur ein Hinweis im Folgeticket.

## Kritische Anmerkungen

- Das Ticket nennt zwei Sperren; die Spec behebt nur eine. Die Versand-Sperre bleibt mit „override" offen, geklärt erst in #2125.

## Freigabe-Frage

Soll das Ticket als erledigt gelten, obwohl die Versand-Sperre weiterhin durch „override" geöffnet werden kann und erst in #2125 folgt?

## Ampel

Ampel: rot
