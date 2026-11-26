---
entity_id: fix-3430-radar-ein-ort
type: bugfix
created: 2026-11-26
status: draft
workflow: fix-3430-radar-ein-ort
issue: 3430
---

# Mini-Spec: Radar-Regen-Text bei genau einem Ort (#3430)

Bezug: ADR-0124 Nr. 10 („Kein Text setzt mehrere Orte voraus“), Mockup Fassung 4 Z. 530, Abnahme #3037 Teil 2.

## Was ändert sich
- Neuer Katalogschlüssel `wetter.radar.dein_ort`: DE „deinen Ort“, EN „your location“.
- Reiter Wetter im Kontext Orte (`vergleich`): Der Radar-Regen-Hinweis nennt bei **genau einem** Ort
  „deinen Ort“ („Alarm, wenn in der nächsten Stunde Regen auf deinen Ort zukommt“), sonst wie bisher „deine Orte“.
  Die Ortszahl kommt aus derselben Quelle wie die Vorlagen-Bestätigung (#3111, `location_ids` des Abos).
- `RadarZiel` erweitert um `wetter.radar.dein_ort`; die Auswahl ist eine reine Funktion (ohne DOM prüfbar).
- Prüfnetz-Lücke geschlossen: die Ein-Ort-Prüfung der Abnahme-Spec (#3037 AC-2) verbietet zusätzlich
  „deine Orte“ / „your locations“.

## Was darf sich nicht ändern
- Trip-Kontext bleibt bei „deine Etappe“ / „your stage“ (#2800).
- Mehrere Orte (≥ 2) und unbekannte Ortszahl (z. B. Anlegen ohne Orte) bleiben bei „deine Orte“.
- Kein anderer Text, keine Speicherlogik, kein Backend.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Orte-Abo mit genau einem Ort, When er den Reiter Wetter auf Deutsch öffnet, Then lautet der Radar-Regen-Hinweis „Alarm, wenn in der nächsten Stunde Regen auf deinen Ort zukommt“ und der Text „deine Orte“ erscheint nicht.

- **AC-2:** Given dasselbe Abo mit Sprache Englisch, When der Reiter Wetter geöffnet wird, Then lautet der Hinweis „Alert when rain is coming towards your location within the next hour“ und „your locations“ erscheint nicht.

- **AC-3:** Given ein Orte-Abo mit zwei oder mehr Orten oder ohne bekannte Ortszahl, When der Reiter Wetter geöffnet wird, Then bleibt der Hinweis bei „deine Orte“ bzw. „your locations“.

- **AC-4:** Given ein Trip, When der Reiter Wetter geöffnet wird, Then bleibt der Hinweis bei „deine Etappe“ bzw. „your stage“, unabhängig von einer Ortszahl.

## Manuelle Test-Schritte
1. Staging, Prüfkonto, Orte-Abo mit einem Ort → Reiter Wetter → Radar-Zeile lesen (DE und EN).
2. Orte-Abo mit drei Orten → weiterhin „deine Orte“.
3. Trip → weiterhin „deine Etappe“.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Reine Auswahlfunktion: Kontext × Ortszahl (route/1, vergleich/0/1/2/undefined) → Schlüssel.
- [ ] Gerenderte Komponente mit einem Ort zeigt „deinen Ort“, mit drei Orten „deine Orte“ (DE/EN-Katalog).
- [ ] Staging-Abnahme-Spec: `VERBOTEN_EIN_ORT` enthält „deine Orte“ und „your locations“.
