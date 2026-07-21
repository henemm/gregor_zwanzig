# Mini-Spec: Etappenname editierbar (#910)

## Was ändert sich

- `EditStagesPanelNew.svelte` Zeile 316: der `<p>` mit dem Etappennamen bekommt ein kleines Stift-Icon daneben
- Klick auf das Icon öffnet `prompt('Neuer Name:', aktuellerName)` — gleiches Muster wie `makeRenameHandler` für Wegpunkte
- Nach Bestätigung: `stages`-State aktualisieren + `scheduleSave()` / `save()` aufrufen (AC: API-Call)
- Leereingabe (Trim → '') wird ignoriert (`if (!newName.trim()) return`)

## Was darf sich nicht ändern

- Kein Umbau des EtappenStrip oder der Wegpunkt-Umbenennung
- Kein neuer API-Endpoint — der bestehende PUT `/api/trips/{tripId}` (mit `{ stages }`) wird genutzt
- Kein eigenes Input-Field im DOM (nur browser-nativer `prompt()` wie bei Wegpunkten)

## Manuelle Test-Schritte

1. Trip im Editor öffnen → Etappe anklicken → Stift-Icon neben Etappenname sehen
2. Icon anklicken → `prompt` erscheint mit aktuellem Namen vorausgefüllt
3. Namen ändern, bestätigen → Name ändert sich sofort im Header
4. Seite neu laden → geänderter Name bleibt erhalten (API-Call hat gespeichert)
5. Leeres Feld bestätigen → Name bleibt unverändert (kein API-Call)

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Playwright: Klick auf Stift-Icon → prompt-mock → neuer Name in Header sichtbar
