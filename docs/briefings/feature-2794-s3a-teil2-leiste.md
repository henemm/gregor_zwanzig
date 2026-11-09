---
spec_file: docs/specs/modules/feat_2794_s3a_teil2_leiste.md
spec_sha256: 3f39d337ceda375d0110fcde38d9c9a43bfd1246e86bd1d1f100a194f944e096
spec_frozen_sha256: 94d028bf95f68f736e39b5550e0047cfde6293c108c5ee80974524d8850c3cd9
---

# PO-Briefing: feature-2794-s3a-teil2-leiste

- **Spec:** docs/specs/modules/feat_2794_s3a_teil2_leiste.md
- **Issue:** #2794
- **Erstellt:** 2026-11-09

## Was gebaut wird

Trip und Orts-Briefing bekommen die vier Reiter Übersicht, Etappen/Orte, Wetter und Zustellung; alte Lesezeichen und Anlege-Schritte folgen.

## Definition of Done

Beide Hubs zeigen die vier Reiter mit neuer Leiste, alte Adressen führen richtig weiter, und kein bisheriges Bedienelement oder gespeicherter Wert geht verloren.

## Wie geprüft wird

Automatische Tests und Staging-Läufe mit zwei Konten prüfen Reiter, Umleitungen, Speicherung und Überschriftgröße; das Aussehen gegen die Soll-Bilder bleibt Sichtprüfung.

## Kritische Anmerkungen

- AC-36 wurde gegenüber der Gesamt-Spec korrigiert: Desktop-Überschrift ist bereits 38 px; Akzeptanzbereich 30–38 px bleibt gleich.
- Start der Umsetzung hängt an zwei noch ungemergten Vorarbeiten (#2871, #2872); reine Reihenfolge, keine Entscheidung.
- Zustellung bleibt vorerst Übergangsreiter; Alarm-Teile wandern erst später nach Wetter (dokumentierte Einschränkung).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
