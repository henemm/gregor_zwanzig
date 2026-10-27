# Context: fix-2110-gui-gpx-km

## Request Summary
GUI zeigt Etappen-Distanz als reine Haversine-Summe (Luftlinie zwischen Wegpunkten) statt der
echten, aus GPX-Tracks vermessenen Distanz (`distance_from_start_km`, Backend). PO-Beispiel: Etappe
„03: Porzehütte → Hochweißsteinhaus" zeigt 12,8 km, real 17,7 km.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/email-preview/headerStats.ts` | **Kanonische Quelle des vom PO gemeldeten Werts.** `computeHeaderStats()` + `haversineKm()` — reine Haversine-Summe über `stage.waypoints`. Wird direkt von `StageDetailRow.svelte` importiert (das die „Distanz"-Kachel rendert, die der PO sah). |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | Zeile 104: `{stats.distanceKm.toFixed(1)} km` — der exakte Anzeigepunkt des PO-Befunds. `stats = computeHeaderStats(stage)`. |
| `frontend/src/lib/utils/tripStats.ts` | `computeTripStats()` summiert `computeHeaderStats(stage).distanceKm` über alle Etappen für den Trip-Gesamtwert. Nutzt dieselbe Quelle — profitiert automatisch von einem Fix in `headerStats.ts`. |
| `frontend/src/routes/_home/cockpitHelpers.ts` | Cockpit-Dashboard nutzt ebenfalls `computeHeaderStats()` für die km-Anzeige der aktiven Etappe. Gleiche Quelle. |
| `frontend/src/lib/components/email-preview/EmailPreviewHeader.svelte` + `index.ts` | E-Mail-Vorschau im Editor nutzt ebenfalls `computeHeaderStats()`. |
| `frontend/src/lib/utils/naismith.ts` | **Bereits DRY:** importiert `haversineKm` explizit aus `headerStats.ts` statt einer eigenen Kopie (Kommentar: „gemeinsame haversineKm aus headerStats.ts (DRY, kein eigener Haversine)"). Berechnet aber **selbst** Distanz pro Segment für die live Editor-Ankunftszeiten-Vorschau (`computeArrivalTimes`), nicht über `computeHeaderStats`. |
| `frontend/src/lib/utils/fullProfile.ts` | **Zweite, unabhängige Haversine-Implementierung** (eigene Kopie von `haversineKm`, nicht DRY zu `headerStats.ts`). Nutzt sie in `buildProfilePoints()` (Profil-Chart x-Achse) und `computeStageBoundaries()` (xStart/xEnd je Etappe). `computeStageBoundaries` wird in `StageList.svelte` aufgerufen, aber **nur `.code` wird angezeigt** (Etappen-Kürzel wie „T03"), xStart/xEnd fließen nicht in eine sichtbare km-Zahl — nur in die Profil-Chart-Skalierung (`FullProfile.svelte`). |
| `frontend/src/lib/types.ts` | `Waypoint`-Interface (Zeile 32-48) kennt `distance_from_start_km` **nicht** — muss ergänzt werden, um das Feld überhaupt nutzen zu können. |
| `docs/reference/api_contract.md` (Zeile 1022, 1026-1028) | Backend-DTO (Go **und** Python) führt `distance_from_start_km` bereits, `omitempty`/`Optional`. `nil`/`None` heißt „nicht gemessen" — der Fallback-Fall ist im Contract bereits als regulärer Zustand vorgesehen. |

## Existing Patterns

- **DRY-Präzedenzfall vorhanden:** `naismith.ts` importiert `haversineKm` statt eigener Kopie zu
  pflegen — genau das Muster, das für `fullProfile.ts` fehlt (dort existiert eine eigene Kopie).
- **Optional-Feld-Fallback ist Backend-Konvention:** `distance_from_start_km: nil` bedeutet
  „nicht gemessen", kein Fehlerzustand — das Backend-Contract sieht Konsumenten explizit vor, die
  bei fehlendem Wert selbst zurückfallen müssen.
- **Bereits gelöst auf Backend-Seite:** #2042 (Ankunftszeiten) und #2082 (Go-Gehzeit) haben exakt
  dasselbe Muster (Luftlinie statt Wegstrecke) im Backend bereits behoben — dort ist die Präferenz-
  Regel „echter Wert wenn vorhanden, sonst Haversine-Fallback" der etablierte Ansatz.

## Dependencies

- **Upstream:** Backend liefert `distance_from_start_km` je Wegpunkt über die Trip-API, sobald
  `resolve_stage_track_km()`/`backfill_stage_distances()` gelaufen sind (Python) bzw. äquivalent
  in Go. **Zuverlässigkeit dieser Datenquelle hängt an #2109** (offen, in Arbeit bei einer
  Parallel-Sitzung — Datenverlust-Bug, der genau dieses Feld bei manchen Etappen leert). Ohne
  #2109-Fix fällt die GUI bei betroffenen Etappen weiterhin auf Haversine zurück — technisch
  korrektes Verhalten, aber der PO-Fall selbst bleibt bis zum #2109-Merge unverändert 12,8 km
  zeigen (die Etappe hat aktuell 0/7 Wegpunkte mit `distance_from_start_km`, siehe #2109-Kommentar
  von heute 13:28 Uhr).
- **Downstream:** `tripStats.ts` (Trip-Summe), `cockpitHelpers.ts` (Dashboard), E-Mail-Vorschau —
  alle drei hängen an `headerStats.ts` und werden durch einen Fix dort automatisch mitkorrigiert,
  ohne eigene Änderung.

## Existing Specs

- Keine Spec zu `headerStats.ts` selbst gefunden (Issue #183 referenziert, keine Datei unter
  `docs/specs/modules/` mit diesem Namen — vermutlich vor der Spec-Pflicht entstanden).
- `docs/specs/modules/issue_296_fe_profile_editor.md` — betrifft `naismith.ts`, nicht direkt
  Ziel dieses Fixes.

## Risks & Considerations

- **Teilweise vermessene Etappen (Kernfrage):** Eine Etappe kann Wegpunkte mit UND ohne
  `distance_from_start_km` gemischt enthalten (z.B. nach nur teilweise gelungenem GPX-Match).
  Entscheidung nötig: pro Segment (Wegpunkt-Paar) mischen — echten Wert nehmen, wenn BEIDE
  Endpunkte ihn tragen, sonst Haversine für dieses Segment — oder pro Etappe ganz auf Haversine
  zurückfallen, sobald auch nur ein Wegpunkt den Wert nicht trägt. Segmentweises Mischen ist näher
  an der Wahrheit, aber ein Etappen-km-Wert, der teils gemessen/teils geschätzt ist, könnte
  Nutzer verwirren, wenn sie das nicht erkennen können.
- **Kein Anzeige-Hinweis heute:** Weder Backend noch Frontend markieren aktuell sichtbar, ob eine
  km-Zahl gemessen oder geschätzt ist (vgl. #2073 — „Fehlschlag ist STILL"). Für diesen Fix stellt
  sich dieselbe Frage nur risikoärmer, weil hier nicht komplett verworfen wird, sondern zwischen
  zwei Werten gewählt wird.
- **#2109-Abhängigkeit ist eine Holschuld, kein Blocker:** Der Fix hier ist unabhängig von #2109
  entwickelbar und testbar (Fixture mit/ohne `distance_from_start_km`), liefert dem PO aber erst
  sichtbaren Nutzen für seinen konkreten Fall, sobald #2109 gemergt ist.

## PO-Entscheide (2026-08-23, vor Spec-Erstellung)

- **Scope: alle drei Stellen.** `headerStats.ts` (km-Anzeige/Trip-Summe/Cockpit/E-Mail-Vorschau),
  `fullProfile.ts` (Profil-Chart-Skalierung) UND `naismith.ts` (Editor-Live-Vorschau der
  Ankunftszeiten) werden in diesem Ticket umgestellt — kein Nebenbefund, kein Folge-Ticket.
- **Fallback-Regel: Etappen-weise, nicht segmentweise.** Trägt auch nur EIN Wegpunkt der Etappe
  kein `distance_from_start_km`, fällt die GESAMTE Etappe auf die bisherige Haversine-Berechnung
  zurück — kein Mischen aus echten und geschätzten Segmenten innerhalb derselben Etappe. Das
  betrifft `computeHeaderStats()`, `buildProfilePoints()`/`computeStageBoundaries()` und
  `computeArrivalTimes()` gleichermaßen: pro Etappe prüfen, ob ALLE Wegpunkte den echten Wert
  tragen, sonst komplett Haversine für diese Etappe.
