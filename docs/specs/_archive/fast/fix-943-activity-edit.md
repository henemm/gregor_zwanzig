# Mini-Spec: fix-943-activity-edit

## Was ändert sich
- Neuen `$state`-Wert `activityType` (initialisiert aus `trip.activity`) in `TripEditView.svelte`
- `Select`-Dropdown für Aktivitätstyp in der Stats-Karte einfügen (gleiche Optionen wie Create-Pfad)
- `activity: activityType` im `api.put`-Aufruf ergänzen
- `activityType={activityType}` statt `activityType={trip.activity}` an `EditStagesPanelNew` übergeben

## Was darf sich nicht ändern
- Keine anderen Felder (name, stages, report_config, alert_rules) umbauen
- Backend-Handler (`trip.go`) bleibt unberührt

## Manuelle Test-Schritte
1. Tour im Edit-Modus öffnen
2. Aktivitätstyp auf „Fahrrad (20 km/h)" wechseln
3. Speichern → Tour erneut öffnen → Dropdown zeigt „Fahrrad (20 km/h)"
4. Auf Etappen-Tab wechseln → Ankunftszeiten zeigen Fahrrad-Geschwindigkeit

## Inline-Test
- [ ] Playwright-Test: Activity-Dropdown im Edit-Modus ändern, speichern, neu laden → persistierter Wert korrekt

## Acceptance Criteria

**AC-1:** Given eine bestehende Tour im Edit-Modus, When der Nutzer die Seite öffnet, Then ist ein Aktivitätstyp-Dropdown (`data-testid="edit-activity-dropdown"`) sichtbar mit dem aktuell gespeicherten Wert vorausgewählt.

**AC-2:** Given das Aktivitätstyp-Dropdown im Edit-Modus, When der Nutzer einen anderen Aktivitätstyp wählt und auf Speichern klickt, Then wird der neue Wert persistiert und beim nächsten Öffnen der Edit-Seite korrekt vorausgewählt.

**AC-3:** Given eine Änderung des Aktivitätstyps im Edit-Modus, When der Nutzer auf den Etappen-Tab wechselt, Then werden die Ankunftszeiten der Etappen sofort mit dem neuen Aktivitätsprofil neu berechnet (reaktiv, ohne Seitenneuladen).
