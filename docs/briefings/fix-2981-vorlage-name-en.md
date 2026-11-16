---
spec_file: docs/specs/modules/fix_2981_vorlage_name_en.md
spec_sha256: 766b27a8bdeb9ba4e3e57e74d6a97e009da9046d86eb1134944afd2272523598
spec_frozen_sha256: 4c8f2a3155501089c739201edcd4ab36a5c94421dc9b92aac6fce8815110d2d7
---

# PO-Briefing: fix-2981-vorlage-name-en

- **Spec:** docs/specs/modules/fix_2981_vorlage_name_en.md
- **Issue:** #2981
- **Erstellt:** 2026-11-16

## Was gebaut wird

Bei Sprache Englisch zeigen die sieben eingebauten Wetter-Vorlagen englische Namen, etwa „Hiking“ statt „Wandern“.

## Definition of Done

Auf der Testumgebung zeigen Vorlagenkarte, Auswahl, Rückfrage und Zurücksetzen-Knopf bei Englisch englische Namen, bei Deutsch unverändert deutsche, auch nach Sprachwechsel.

## Wie geprüft wird

Automatische Tests prüfen Namenszuordnung, Fallbacks und eigene Vorlagen; Karte, Sprachwechsel und alte Vorlagen-Leiste werden nur per Sichtprüfung auf der Testumgebung belegt.

## Kritische Anmerkungen

- Zusatz: Die alte Vorlagen-Leiste im Anlege-Editor wird mitgeändert, im Ticket nicht genannt; gleiche Ursache, gleiche Wirkung.
- Eigene Vorlagen dürfen nicht „Wandern“ heißen, auch nicht in Englisch; als gewollte Einschränkung dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
