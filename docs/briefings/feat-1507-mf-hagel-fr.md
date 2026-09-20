---
spec_file: docs/specs/modules/feat_1507_s5c_hagel_mf_fr.md
spec_sha256: ba2238df24995abb1dadfd48024c5cbff0fb30e17db54109af300c4ce804ecae
---

# PO-Briefing: feat-1507-mf-hagel-fr

- **Spec:** docs/specs/modules/feat_1507_s5c_hagel_mf_fr.md
- **Issue:** #1507
- **Erstellt:** 2026-09-20

## Was gebaut wird

Für Frankreich und Korsika wird zusätzlich ein echter Hagel-Messwert von Météo-France erfasst, bislang unsichtbar für Nutzer.

## Definition of Done

Ein Test zeigt, dass für einen Ort in Frankreich/Korsika ein echter Hagel-Messwert gespeichert wird, ohne die Hagel-Warnung zu verändern.

## Wie geprüft wird

Ein Live-Test bestätigt Abrufname und Bedeutung beim Anbieter, weitere Tests prüfen Ausfallverhalten und Zeitbudget — nicht die Vorhersagegüte.

## Kritische Anmerkungen

- Die im Issue vorgesehene Ableitung der Hagel-Warnung aus dem neuen Wert entfällt vollständig — auch bei geklärter Einheit.
- Der neue Wert bleibt in dieser Scheibe für Nutzer komplett unsichtbar, in keinem Kanal angezeigt.
- Bleibt die Bedeutung des Zahlenwerts ungeklärt, wird nur ein nicht interpretierbarer Rohwert gespeichert.

## Freigabe-Frage

Ist es für dich in Ordnung, dass diese Scheibe die Hagel-Warnung nicht verbessert, sondern nur einen unsichtbaren Messwert sammelt?
