---
spec_file: docs/specs/modules/fix_2944_orts_nicht_im_briefing.md
spec_sha256: a06f5b109cf072559fbd855b362ca0d9c8328d050ac500449c9dea8831bc7551
spec_frozen_sha256: dbd31b103d31b92b87fb372bc4ea5aa845cfb0f19de0f465ebd0235bacbd401b
---

# PO-Briefing: fix-2944-orts-nicht-im-briefing

- **Spec:** docs/specs/modules/fix_2944_orts_nicht_im_briefing.md
- **Issue:** #2944
- **Erstellt:** 2026-11-15

## Was gebaut wird

Im Orts-Briefing bietet „Nicht im Briefing" nur noch Metriken an, die für Orte existieren, keine Gehzeit-Werte mehr.

## Definition of Done

Auf Staging zeigt „Nicht im Briefing" im Ort keine „(Gehzeit)"-Einträge, im Trip weiterhin alle Metriken; Prod-Deploy und Selbsttest sind erfolgreich.

## Wie geprüft wird

Automatische Tests prüfen Orts- und Trip-Angebot gegen den echten Katalog, ein Staging-Test das Anklicken; Gespeicherte Auswahlen werden nicht bereinigt.

## Kritische Anmerkungen

- Zusätzlich zu den Gehzeit-Werten verschwinden auch Nacht-Temperatur und gefühlte Nacht-Temperatur aus dem Orts-Angebot; das Ticket nannte nur Gehzeit.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
