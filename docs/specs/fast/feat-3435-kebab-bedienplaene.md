---
entity_id: feat-3435-kebab-bedienplaene
type: test-tooling
created: 2026-11-28
status: draft
workflow: feat-3435-kebab-bedienplaene
---

# Mini-Spec: feat-3435-kebab-bedienplaene

Issue #3435 (Epic #2913, Vorbedingung der Abnahme #3009). Nur Prüfwerkzeug (Elementlisten-Abgleich), kein Produktionscode.

## Ausgangslage
- Der Abgleich `--strict` meldete je Sprache 198 Einträge „nicht prüfbar“ in vier Script-Zuständen des Reiters Wetter
  (Trip und Orte, alle Zustände): `test-menue`, `kebab-menue`, `kebab-bestaetigung-archivieren`, `kebab-bestaetigung-loeschen`.
- `test-menue` hat seit #3440 (AC-17) einen Bedienplan. Offen sind die drei Kebab-Zustände (88 Einträge je Sprache).
- Die App hat seit #3442 die nötigen Haken: Kebab-Knopf `subscription-kebab`, Menübereich `data-abschnitt="kebab-menue"`,
  Einträge `subscription-action-archive` / `subscription-action-delete`, Rückfrage `data-abschnitt="kebab-bestaetigung-*"`
  mit Knöpfen `kebab-rueckfrage-bestaetigen` und `kebab-rueckfrage-abbrechen` (Abbrechen führt ins Menü zurück).

## Was ändert sich
In `bedienPlan` (`frontend/e2e/elementliste_abgleich_logik.ts`) drei neue Pläne, gleich für Trip und Orte:
- `kebab-menue`: Klick `subscription-kebab` · lesen · Escape.
- `kebab-bestaetigung-archivieren`: Klick `subscription-kebab` · Klick `subscription-action-archive` · lesen ·
  Klick `kebab-rueckfrage-abbrechen` · Escape.
- `kebab-bestaetigung-loeschen`: wie oben mit `subscription-action-delete`.
Die Bedienung läuft wie alle Bedienpläne auf dem kurzlebigen Wetter-Prüf-Datensatz (nie auf den Seed-Daten),
der Schreib-Tripwire bleibt scharf.

## Was darf sich nicht ändern
- Kein Plan klickt `kebab-rueckfrage-bestaetigen`, einen Kanal im Menü „Test schicken“ oder einen anderen
  Menüeintrag als Archivieren/Löschen: nichts wird verschickt, archiviert oder gelöscht.
- Bestehende Pläne (Grenzen, Vorlage-Dialoge, `test-menue`) bleiben unverändert; unbekannte `kebab-*`-Abschnitte
  bleiben „nicht herstellbar“ mit Grund.
- Produktionscode der App bleibt unverändert.

## Acceptance Criteria
**AC-1:** Given die drei Kebab-Zustände im Reiter Wetter (Trip und Orte), When der Bedienplan gebildet wird, Then ist jeder ein Plan mit genau einem Lese-Schritt, der über den Kebab-Knopf öffnet und mit Escape schließt (Bestätigungen vorher über „Abbrechen“).
**AC-2:** Given alle Bedienpläne aller Abschnitte der Elementliste, When ihre Schritte geprüft werden, Then klickt keiner `kebab-rueckfrage-bestaetigen` und keiner einen Versand-Kanal; nur Archivieren/Löschen öffnen eine Rückfrage, die immer abgebrochen wird.
**AC-3:** Given die Zuordnung der Abschnitte im Reiter Wetter, When `ordneAbschnitte` läuft, Then werden die drei Kebab-Zustände bedient (nicht mehr „nicht herstellbar“).
**AC-4:** Given der Staging-Lauf `--strict` in DE und EN, When die vier Zustände geprüft werden, Then ist keiner ihrer Einträge mehr „nicht prüfbar“ wegen fehlendem Bedienplan; echte Abweichungen stehen als „abweichend“ mit Besitzer-Issue im Bericht und der Schreib-Tripwire meldet nichts.

## Manuelle Test-Schritte
1. Kern-Tests `elementliste_abgleich_bedienplan.test.ts` grün.
2. Mutation: in einem Kebab-Plan `kebab-rueckfrage-abbrechen` → `kebab-rueckfrage-bestaetigen` → AC-2-Test rot; zurücksetzen.
3. Staging-Lauf `--strict` DE und EN; Bericht auf die vier Zustände prüfen.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] `frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts` (neue Fälle #3435)
