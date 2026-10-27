---
spec_file: docs/specs/modules/fix_2277_s2a_wertebereiche_trip_anlegen.md
spec_sha256: e2aa30884805d9d784b71416fd4874b68dc49f47bb332fd337bab3a0e5a022aa
---

# PO-Briefing: feature-2277-s2-anlege-editor

- **Spec:** docs/specs/modules/fix_2277_s2a_wertebereiche_trip_anlegen.md
- **Issue:** #2277 (Epic #2345)
- **Erstellt:** 2026-09-27

## Was gebaut wird

Beim Anlegen eines neuen Trips lassen sich künftig auch Wetter-Wertebereiche einstellen, wie im Ortsvergleich.

## Definition of Done

Beim Anlegen eines Trips erscheint ein neuer Reiter „Wertebereiche"; gespeicherte Werte sind danach im angelegten Trip vorhanden.

## Wie geprüft wird

Automatisierte Tests prüfen Reiterfolge und dass bestehende Funktionen unverändert bleiben; die tatsächliche Speicherung wird erst beim Ausrollen einmal von Hand geprüft.

## Kritische Anmerkungen

- Deckt nur einen der beiden vom PO genannten Punkte ab; die Ortsvergleich-Angleichung folgt in einem späteren Paket.
- Eine unvollständig ausgefüllte Wertebereich-Zeile wird beim Speichern ohne Hinweis stillschweigend weggelassen (seltener Fall).

## Freigabe-Frage

Soll beim Trip-Anlegen ein Reiter „Wertebereiche" kommen, der vor dem Zeitplan-Schritt einmal geöffnet werden muss, wie beim Ortsvergleich?
