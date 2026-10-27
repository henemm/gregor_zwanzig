---
spec_file: docs/specs/modules/rework_2276_s6g_wetter_metriken_wertprops.md
spec_sha256: 62f5b123df59a22edd48726ea059548a03b7f6a4265f6fa7b2771a13ad286f6b
---

# PO-Briefing: refactor-2276-s6g-wmt-wertprops

- **Spec:** docs/specs/modules/rework_2276_s6g_wetter_metriken_wertprops.md
- **Issue:** #2276
- **Erstellt:** 2026-09-24

## Was gebaut wird

Der Wetter-Metriken-Reiter im Orts-Vergleich wird intern umgebaut — für Nutzer ändert sich nichts sichtbar.

## Definition of Done

Alle Bedienelemente im Wetter-Metriken-Reiter (Hub und Neuanlegen) funktionieren wie zuvor, bestätigt durch Tests und einen Staging-Durchlauf.

## Wie geprüft wird

Automatisierte Tests prüfen den Umbau und die bestehende Speicherfunktion; die Anlege-Seite wird zusätzlich nur manuell durchgeklickt.

## Kritische Anmerkungen

- Diese Scheibe schließt Issue #2276 nicht ab — die verlangte Gesamtbilanz aller Kanal-Verzweigungen folgt erst in Scheibe S6h.
- Die Anlege-Seite für neue Vergleiche wird nur einmalig manuell geprüft, nicht durch einen automatischen Test dauerhaft abgesichert.
- Der geschätzte Umfang überschreitet das übliche 250-Zeilen-Limit deutlich — die Erlaubnis dafür muss vorher eingeholt werden.

## Freigabe-Frage

Reicht es, wenn dieser Teil ohne die vollständige Kanal-Bilanz freigegeben wird, der Rest folgt in einer Folge-Scheibe?
