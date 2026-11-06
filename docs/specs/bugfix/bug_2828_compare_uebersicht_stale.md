---
entity_id: bug_2828_compare_uebersicht_stale
type: bugfix
created: 2026-11-05
updated: 2026-11-05
status: draft
version: "1.0"
workflow: fix-2828-compare-uebersicht-stale
tags: [epic-2345, trip-compare-teilung, hub-uebersicht, compare, bugfix, frontend-only, B1-46]
---

# Compare-Hub: Übersicht zeigt lebenden Stand (Issue #2828, B1-46, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich-Hub zeigt die Übersicht nach einer gespeicherten Änderung in einem anderen Reiter (Orte, Wertebereiche, Versand, Alarme) weiter den Stand vom Laden der Seite, bis neu geladen wird. Beim Trip gibt es das nicht. Das verletzt die Invariante „kein Verhaltensunterschied Trip/Vergleich" (P7, Epic #2345). Der Fix lässt die Übersicht den lebenden Stand lesen, den auch alle Reiter zum Speichern benutzen.

Hinweis zum Wort „Vorschau" im Issue: Den Reiter „Vorschau" gibt es seit #1743 nicht mehr (fünf Reiter, `shared/subscriptionTabs.ts`). Gemeint ist die Übersicht samt ihren Orte-, Wertebereiche- und Versand-Karten; der Nachweis prüft genau diese.

## Source

- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte`
- **Identifier:** `status` (`:218`), `currentPreset` (`:217`), Übergabe an `HubUebersicht` (`:695`), Kommentar „akzeptierte Stale-Anzeige" (`:213-216`)

**Ursache:** `CompareTabs` reicht die Seiten-Prop `preset` (eingefroren auf den Ladezeitpunkt) an `HubUebersicht` und leitet `status` ebenfalls daraus ab. Alle Reiter dagegen hydrieren und speichern über `currentPreset`, das nach jedem PUT aus der Antwort aufgefrischt wird. Nur die Orte sind schon live (`resolvedLocations`). Der Trip-Gegenpart `TripTabs.svelte:196` reicht den lebenden `trip`.

> **Schicht-Hinweis:** ausschließlich **Frontend** (SvelteKit). Kein Go-, kein Python-Code, kein neuer Endpunkt, kein neues Datenmodell.

> **Trip/Ortsvergleich-Teilung:** Der geteilte Baustein `shared/hub-uebersicht/HubUebersicht.svelte` (feat_2682) bleibt **unverändert**; korrigiert wird nur die Verdrahtung auf der Compare-Seite. Keine neue Compare-eigene Komponente.
> **Mandantentrennung:** Es bewegt sich keine neue Nutzerdaten-Strecke (kein neuer Endpunkt, keine neuen Daten); ein Zwei-Nutzer-Test ist nicht nötig.
> **Kanäle:** Keine Briefing- oder Alarm-Inhalte betroffen; angezeigt werden die bereits gespeicherten Kanäle (E-Mail, Telegram, SMS, Premium-SMS) gleichrangig, es wird nichts versendet.

## Scope

- **In:** `CompareTabs.svelte`: `HubUebersicht` bekommt `preset={currentPreset}`; `status` wird aus `currentPreset` (mit `localSchedule`-Override) abgeleitet; der Kommentar `:213-216` („bewusst … akzeptierte Stale-Anzeige") wird durch die neue Wirklichkeit ersetzt.
- **Out:** `HubUebersicht`, `hubUebersichtModell.ts`, Trip-Code, Header-Pille in `routes/compare/[id]/+page.svelte` (eigener Callback `onScheduleChange`), Reiter-Hydration, Speicherwege.
- **Doku:** `docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md` bekommt den Hinweis „Übersicht liest lebenden Stand (`currentPreset`)".

## Estimated Scope

- **LoC:** ca. +5/-5 Produktivcode
- **Files:** 1 Produktivdatei (plus Tests und ein Doku-Hinweis)
- **Effort:** low (Risiko niedrig)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `snapshotForRollback` | Funktion | Basis von `currentPreset`, unverändert |
| `deriveStatusWithScheduleOverride` | Funktion | Status aus Preset + lokalem Pausier-Override |
| `saveController.savedAt` | Store | „Nächster Versand" wird nach jedem Speichern neu geladen, unverändert |
| `hubPutQueue` | Queue | serialisiert Speicherungen (Read-Modify-Write), unverändert |

## Implementation Details

```
status = deriveStatusWithScheduleOverride(currentPreset, localSchedule)   // statt preset
<HubUebersicht context="vergleich" preset={currentPreset} {status} ... /> // statt {preset}
```

- Der Effekt `:648-664` reagiert nur auf die Prop `preset` und schreibt `currentPreset`; er liest `currentPreset` nicht. Die Umstellung löst ihn daher nicht neu aus, es entsteht keine Schleife.
- 412-Pfad: `currentPreset` wird lokal um die abgelehnte Nutzlast fortgeschrieben (Server ⊕ Eingabe). Die Übersicht zeigt dann den eingegebenen, noch ungespeicherten Stand, wie der Trip-Editor mit lokalem Stand; der Save-Chip signalisiert den Konflikt. Das ist bewusst so entschieden.

## Expected Behavior

- **Input:** Nutzer ändert und speichert etwas in einem Hub-Reiter und wechselt zur Übersicht.
- **Output:** Die Übersicht zeigt den neuen Stand, ohne die Seite neu zu laden.
- **Side effects:** keine; kein zusätzlicher Request.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich im Hub, When der Nutzer den Reiter Wertebereiche öffnet, Then ist er seit #2792 nur lesbar (kein Hinzufügen oder Ändern), und die Wertebereiche-Karte der Übersicht zeigt weiter den gespeicherten Stand des lebenden `currentPreset`; die Verdrahtung ist durch den Verdrahtungs-Test `compare_uebersicht_liest_lebenden_stand.test.ts` belegt.
  - Spec-Änderung 2026-11-06 nach #2792 / PR #2829: Ursprünglich verlangte AC-1 das Ändern eines Werts im Reiter Wertebereiche und die Anzeige in der Übersicht. Das ist durch die Sperre des Editors gegenstandslos; AC-1 wurde auf den lesenden Stand umgestellt.
- **AC-2:** Given ein Ortsvergleich im Hub, When der Nutzer im Reiter Orte einen Ort hinzufügt oder entfernt, speichert und zur Übersicht wechselt, Then zeigt die Orte-Karte der Übersicht die neue Ortsliste samt Anzahl ohne Neuladen.
- **AC-3:** Given ein Ortsvergleich im Hub, When der Nutzer im Reiter Versand Kanäle oder Briefing-Zeiten ändert, speichert und zur Übersicht wechselt, Then zeigen Versand-Karte und Kennzahlen (Kanäle, Briefings) die neuen Kanäle und Zeiten ohne Neuladen.
- **AC-4:** Given ein Ortsvergleich im Hub, When der Nutzer im Reiter Alarme eine Einstellung ändert und speichert, Then bleibt die Übersicht ohne Neuladen in sich stimmig (der Vergleichs-Kontext des Bausteins zeigt keine eigene Alarm-Angabe, `hubUebersichtModell.ts` kennt Alarme nur für den Trip), und ein erneutes Öffnen des Reiters Alarme zeigt den gespeicherten Wert; eine Alarm-Änderung setzt dabei keine anderen Übersichts-Werte zurück.
- **AC-5:** Given ein aktiver Ortsvergleich, When der Nutzer ihn pausiert (oder einen pausierten aktiviert), Then zeigt die Status-Kennzahl der Übersicht sofort den neuen Status, und der lokale Pausier-Override (`localSchedule`) gewinnt weiter vor dem gespeicherten Preset-Stand.
- **AC-6:** Given ein Ortsvergleich im Hub, When Reiter gewechselt und mehrere Änderungen nacheinander gespeichert werden, Then löst die Umstellung auf `currentPreset` den Prop-Wechsel-Effekt nicht erneut aus (kein zusätzlicher PUT, keine Schleife), und jeder Speichervorgang bleibt Read-Modify-Write ohne Verlust früher gespeicherter Felder.
- **AC-7:** Given ein Speichern wird mit 412 (Konflikt) abgelehnt, When der Nutzer zur Übersicht wechselt, Then zeigt die Übersicht den eingegebenen, noch ungespeicherten Stand wie der Trip-Editor, und der Save-Chip signalisiert weiterhin den Konflikt.
- **AC-8:** Given ein Trip im Hub, When der Nutzer dort Änderungen speichert und die Übersicht öffnet, Then verhält sich die Trip-Übersicht unverändert (Regression), und `HubUebersicht` ist unverändert und wird von beiden Arten weiter gemeinsam benutzt.

## Geplante Tests

Reihenfolge: zuerst rot aus Nutzersicht, dann der Fix.

1. **E2E (Nutzersicht, zuerst rot):** `frontend/e2e/compare-uebersicht-live.spec.ts`. Wert in einem Reiter ändern und speichern, zur Übersicht wechseln, neuen Wert sehen, ohne Reload (AC-2, AC-3, AC-5). Auf dem alten Code schlägt der Test fehl. Der Test zu AC-1 (Metrik im Reiter Wertebereiche hinzufügen) entfällt seit #2792, weil der Editor gesperrt ist; AC-1 ist stattdessen durch den Verdrahtungs-Test (Punkt 2) belegt.
2. **Verdrahtungs-Test (node --test, kein Mock-Theater):** unter `frontend/src/lib/components/shared/hub-uebersicht/__tests__/` bzw. im Compare-Testordner. Prüft am echten Quelltext der Verdrahtung (Doc-Compliance-Kennzeichnung nur, wo nötig), dass `HubUebersicht` `currentPreset` erhält und `status` daraus abgeleitet wird; ergänzend Modell-Test mit Preset-Wechsel (AC-6, AC-8).
3. **Regression:** bestehende Compare-Hub-E2E (`compare-hub-inline-edit.spec.ts`, `compare-hub-fidelity-s8c.spec.ts`) und Trip-Übersicht-Tests bleiben grün (AC-8).
4. **412-Fall (AC-7):** falls im E2E nicht sauber erzeugbar, über den vorhandenen 412-Test-Pfad des Save-Controllers prüfen; sonst Verdrahtung plus Review-Nachweis.

## Known Limitations

- AC-7 (412-Konflikt) ist im E2E ggf. nicht sauber erzeugbar; dann Nachweis über den vorhandenen 412-Pfad des Save-Controllers bzw. Verdrahtung plus Review.
- Die Vergleichs-Übersicht zeigt keine Alarm-Angabe; AC-4 sichert nur, dass eine Alarm-Änderung nichts anderes zurücksetzt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine. Reiner Frontend-Verdrahtungsfehler; die Entscheidung „Trip und Vergleich teilen Code, kein Verhaltensunterschied" (ADR-0097, Epic #2345) wird damit nur eingehalten, nicht geändert.

## Changelog

- 2026-11-05: Initial spec created (Issue #2828, B1-46)
- 2026-11-06: AC-1 geändert (Wertebereiche-Editor seit #2792 / PR #2829 gesperrt, Metrik-Hinzufügen nicht mehr möglich); Testplan angepasst, E2E-Test zu AC-1 entfällt
