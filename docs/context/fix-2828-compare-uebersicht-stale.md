# Context: fix-2828-compare-uebersicht-stale

## Request Summary
Compare-Hub (Epic #2345, B1-46): Die Übersicht zeigt nach einer Änderung in einem anderen Reiter (Orte, Wertebereiche, Versand, Alarme) den Stand vom Laden der Seite, bis neu geladen wird. Beim Trip gibt es das nicht. Erwartung: gespeicherte Änderung sofort sichtbar, ohne Neuladen. Der Vorschau-Reiter wird beim Nachweis mitgeprüft.

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/compare/CompareTabs.svelte:695 | übergibt `{preset}` (Seiten-Prop, eingefroren) an `HubUebersicht` — Ursache |
| frontend/src/lib/components/compare/CompareTabs.svelte:217 | `currentPreset` = lebender Stand, aus jeder PUT-Antwort aufgefrischt |
| frontend/src/lib/components/compare/CompareTabs.svelte:198 | `status` wird aus `preset` + `localSchedule` abgeleitet (gleiche Stale-Quelle) |
| frontend/src/lib/components/compare/CompareTabs.svelte:213-216 | Kommentar „bewusst … akzeptierte Stale-Anzeige" — muss mit dem Fix entfallen |
| frontend/src/lib/components/compare/CompareTabs.svelte:648-664 | Effekt: `currentPreset = snapshotForRollback(preset)` bei echtem Prop-Wechsel |
| frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte:36-70 | geteilter Baustein; `deriveVergleichKennzahlen(preset, status, …)` |
| frontend/src/lib/components/trip-detail/TripTabs.svelte:196 | Trip-Gegenstück: reicht lebenden `trip` durch |
| frontend/src/lib/components/shared/subscriptionTabs.ts | Reiterliste (prüfen, ob/wo ein eigener Vorschau-Reiter existiert) |
| frontend/src/lib/components/shared/hub-uebersicht/__tests__/ | bestehende Tests (Modell, Verdrahtung) |
| frontend/e2e/compare-hub-inline-edit.spec.ts, compare-hub-fidelity-s8c.spec.ts | bestehende Compare-Hub-E2E, Vorlage für den roten Nachweis |
| docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md | Spec des geteilten Bausteins |
| docs/analysis/triage-1199-2026-09-08.md:92 | Triage-Eintrag B1-46 |

## Existing Patterns
- Trip: `TripTabs` reicht den lebenden `trip` an `HubUebersicht`; Reiter aktualisieren ihn per `onTripUpdate`.
- Compare: alle Reiter hydrieren und speichern über `currentPreset` (Read-Modify-Write-Baseline, `hubPutQueue`); nur Übersicht liest noch `preset`.
- Wahrscheinlicher Fix: `{preset}` → `preset={currentPreset}`, `status` aus `currentPreset` ableiten. Beachten: `localSchedule` wird beim Pausieren/Aktivieren lokal gesetzt.

## Dependencies
- Upstream: `snapshotForRollback`, `deriveStatusWithScheduleOverride`, `saveController`, `hubPutQueue`.
- Downstream: `HubUebersicht` (auch vom Trip genutzt, Parameter `context`), Status-Pille in `routes/compare/[id]/+page.svelte` (liest `data.preset`, eigener Callback `onScheduleChange`).

## Existing Specs
- `docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md`
- Hub-Specs feat_1273_s1/s2 (Save-Chip, Name/Region/Profil)

## Risks & Considerations
- Der Effekt bei 648-664 darf durch die Umstellung nicht neu auslösen (er reagiert nur auf `preset`, nicht auf `currentPreset`).
- 412-Pfad: `currentPreset` wird lokal um abgelehnte Nutzlast fortgeschrieben; Übersicht würde dann ungespeicherten Stand zeigen — in der Analyse bewerten.
- Vorschau-Reiter: existiert seit #1743 nicht mehr (subscriptionTabs.ts:7, fünf Reiter); „Vorschau" im Issue meint die Übersicht-Anzeige. In der Analyse bestätigen.
- Trip/Vergleich-Teilung ist Gate: Fix im geteilten Baustein bzw. in der Verdrahtung, keine Compare-eigene Komponente.
- Nachweis zuerst rot aus Nutzersicht (E2E: Wert ändern → Übersicht → neuer Wert), Zwei-Nutzer-Test nicht nötig (kein neuer Endpoint).

## Analysis

### Type
Bug (Frontend, Verdrahtung)

### Root Cause
`CompareTabs.svelte:695` gibt `{preset}` (eingefrorene Seiten-Prop) an `HubUebersicht`; `:198` leitet `status` ebenfalls aus `preset` ab. Alle Reiter schreiben/lesen `currentPreset` (`:217`, aus jeder PUT-Antwort aufgefrischt). Nur `orte` ist schon live (`resolvedLocations` aus `currentLocationIds`). Der Kommentar `:213-216` hat die Stale-Anzeige als „akzeptiert" festgeschrieben — das widerspricht P7 (#2345). Kein „Vorschau"-Reiter mehr (seit #1743, fünf Reiter): gemeint ist die Übersicht; Nachweis prüft Übersicht inkl. Versand-/Wertebereiche-Karten.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/compare/CompareTabs.svelte | MODIFY | `preset={currentPreset}` an HubUebersicht; `status` aus `currentPreset`; Kommentar :213-216 anpassen |
| frontend/e2e/compare-uebersicht-live.spec.ts (Name frei) | CREATE | Nutzersicht-Test: Wert in Reiter ändern → Übersicht → neuer Wert, ohne Reload (zuerst rot) |
| docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md | MODIFY | Hinweis: Übersicht liest lebenden Stand |

### Scope Assessment
- Files: 2–3 (Produktivcode nur 1)
- Estimated LoC: +~5/-~5 Code, Rest Test/Doku
- Risk Level: LOW

### Technical Approach
1. `HubUebersicht preset={currentPreset}`.
2. `status = deriveStatusWithScheduleOverride(currentPreset, localSchedule)` (localSchedule bleibt als Pausieren-Override; wird nach Toggle ohnehin aus der Antwort gesetzt).
3. Effekt :661 reagiert nur auf `preset` → löst durch die Umstellung nicht neu aus (kein Schleifenrisiko, da `currentPreset` nicht gelesen wird, nur geschrieben).
4. 412-Pfad: `currentPreset` = Server ⊕ abgelehnte Nutzlast. Übersicht zeigt dann den vom Nutzer eingegebenen (noch ungespeicherten) Wert — gleiches Verhalten wie Trip-Editor mit lokalem Stand; Konfliktanzeige des Save-Chips signalisiert den Zustand. Als akzeptiert bewertet, in Spec als AC festhalten.
5. Geteilter Baustein bleibt unverändert (Trip/Vergleich-Teilung gewahrt, keine Compare-eigene Komponente).

### Dependencies
`snapshotForRollback`, `deriveStatusWithScheduleOverride`, `saveController.savedAt` (Nächster Versand), Header-Pille in `routes/compare/[id]/+page.svelte` (eigener Callback, unberührt).

### Open Questions
- [ ] Keine für den PO. (Technisch entschieden: 412-Anzeige = Eingabestand.)
