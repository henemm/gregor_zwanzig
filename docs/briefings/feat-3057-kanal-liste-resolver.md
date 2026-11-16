---
spec_file: docs/specs/modules/feat_3057_kanal_liste_resolver.md
spec_sha256: a266190c9f44e909bf898b7e2af34fb41fdc64a6317a2a70ecc868c78934120f
spec_frozen_sha256: a4911aa3b3693a0e4866c778722266a81b5d92906ad6f5c891cfc26d7145b074
---

# PO-Briefing: feat-3057-kanal-liste-resolver

- **Spec:** docs/specs/modules/feat_3057_kanal_liste_resolver.md
- **Issue:** #3057
- **Erstellt:** 2026-11-16

## Was gebaut wird

Trip und Orts-Vergleich bekommen intern eine gemeinsame Kanal-Liste, aus der später Editor und Mail lesen; die Mail bleibt unverändert.

## Definition of Done

Alle neun Kriterien sind durch grüne Tests belegt, und die zugestellte Staging-Mail ist in jedem Kanal zeichengleich zu vorher.

## Wie geprüft wird

Tests vergleichen neue und alte Auflösung in allen Kombinationen und prüfen Alarme und Mails; nicht geprüft werden Ausblick, Stundenverlauf und Editor.

## Kritische Anmerkungen

- Das Ticket verlangt Migration der Bestandsdaten und Lesen durch Editor und Renderer; die Spec verschiebt beides auf spätere Schritte.
- Ausblick, Stundenverlauf und Lese-Schnittstelle für den Editor fehlen hier, sie sind in eigene Tickets abgespalten.

## Freigabe-Frage

Ist es für dich in Ordnung, dass Datenmigration und Umstellung von Editor und Mail erst später kommen?

## Ampel

Ampel: rot
