---
spec_file: docs/specs/modules/fix_2277_s1_alarme_tab_route.md
spec_sha256: 9619c6dbe3b29cbeb6388b2d189cf9eb43087635d714c386e02f76974d7c10cb
---

# PO-Briefing: fix-2277-s1-alarmetab-vier-kanaele

- **Spec:** docs/specs/modules/fix_2277_s1_alarme_tab_route.md
- **Issue:** #2277 (Scheibe S1, deckt AC-1; schließt #2229 mit)
- **Erstellt:** 2026-09-25

## Was gebaut wird

Der Alarme-Reiter beim Trip-Anlegen zeigt künftig dieselbe geteilte Oberfläche wie im Trip-Hub, inklusive Premium-SMS-Kanal.

## Definition of Done

Wer eine neue Tour anlegt, sieht im Alarme-Reiter denselben Baustein wie im Trip-Hub mit allen vier Kanälen, ohne versehentliche Zwischenspeicherung.

## Wie geprüft wird

Automatisierte Tests rendern die echte Anlege-Seite und prüfen Kanal-Anzeige, Speicher-Verhalten und Datenübernahme; ein echter Klick-Durchlauf folgt erst beim Staging-Deploy.

## Kritische Anmerkungen

- Telegram- und SMS-Kanal werden nicht einzeln geprüft — nur Premium-SMS und E-Mail haben einen eigenen Sichtbarkeits-Test.
- Metrik-Katalog-Ladefehler bleiben unbemerkt: Alarm-Metrikzeilen könnten leer erscheinen, kein Test in dieser Scheibe fängt das ab.
- Cooldown und Stille Stunden werden beim Anlegen bereits editierbar, obwohl ursprünglich nur ein Vorgabewert vorgesehen war.

## Freigabe-Frage

Ist die Umstellung auf den geteilten Alarme-Baustein beim Trip-Anlegen (inkl. Premium-SMS) freizugeben?
