# Context: #1395 S6 — Ortsvergleich inkl. Umgehungsweg

## Request Summary
S1–S5 haben dem Trip-Speichern (`/api/trips/{id}`) einen vollständigen
Nebenläufigkeitsschutz gegeben: Inhalts-Fingerabdruck als ETag, `If-Match`-Prüfung,
serverseitige Sperre je `user_id+id`, Frontend-Schreib-Warteschlange. Der
Ortsvergleich (Compare-Presets) teilt sich dieselbe Datei-Ebene
(`briefings/<id>.json`) und denselben Fingerabdruck-Mechanismus (S1 deckt beide
ab), hat aber **keinen** der übrigen Bausteine — weder serverseitig (Sperre,
If-Match) noch clientseitig (ETag-Erfassung, Warteschlange). S6 schließt diese
Lücke, inklusive eines zweiten, bisher unabgesicherten Schreibwegs
("Umgehungsweg").

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/briefing_subscription.go:182-244` (`UpdateBriefingHandler`) | Dispatcht nach `kind`; bei `kind=route` Delegation an `UpdateTripHandler` (nimmt dort bereits die Sperre); bei `kind=vergleich` (Z.193-244) direkter RMW-Merge + `SaveComparePreset`, OHNE Sperre/If-Match — der im S3-Kommentar erwähnte "Umgehungsweg" |
| `internal/handler/compare_preset.go:262-459` (`UpdateComparePresetHandler`) | Dedizierter Compare-Preset-Handler, eigener RMW-Merge, ebenfalls OHNE Sperre/If-Match |
| `internal/handler/etag.go:41-65` (`ifMatchAllows`, `setETagHeader`) | Bestehende Bausteine, bisher nur in `trip.go`/`weather_config.go` genutzt — für S6 wiederverwendbar, kein neuer Mechanismus nötig |
| `internal/store/briefing_lock.go:26-58` (`LockBriefing`) | Sperre je `UserID + "\x00" + id`, prozessintern, NICHT reentrant. Gilt für Trip- wie Preset-IDs gleichermassen (Schlüssel ist die rohe ID, kein Kind-Bewusstsein) |
| `internal/store/briefing_fingerprint.go:10-37` (`BriefingFingerprint`) | SHA256 über Rohbytes, deckt laut Docstring bereits „Trip UND Ortsvergleich" ab (S1) — kein Ausbau nötig |
| `frontend/src/lib/etagRegistry.ts:14,41` (`TRIP_PATH_RE`, Write-Queues) | Regex matched ausschliesslich `/api/trips/{id}` (+`/weather-config`); Warteschlangen sind nach `tripId` benannt — beides muss auf Compare-Presets erweitert werden |
| `frontend/src/lib/api.ts` (`request()`/`send()`) | Zentrale Stelle, die `enqueueTripWrite`/`getKnownEtag`/`setKnownEtag` aufruft — Erweiterung hier wirkt automatisch für alle Aufrufer, analog zum Trip-Fall in S3 |
| `frontend/src/lib/components/.../compareWizardState.svelte.ts:147,194` | Zwei der Compare-Schreib-Aufrufstellen (POST `/api/compare/presets`, PUT `/api/compare/presets/{id}`) |

## Existing Patterns

- **Server-Pattern aus S2 direkt übertragbar:** `trip.go`/`weather_config.go`
  zeigen exakt die Reihenfolge, die für `compare_preset.go` und den
  `kind=vergleich`-Zweig von `briefing_subscription.go` übernommen werden kann:
  `LockBriefing(id)` (defer unlock) → `BriefingFingerprint(id)` lesen →
  `ifMatchAllows(r, fingerprint)` prüfen (fehlend = annehmen) → bei Ablehnung
  412 → sonst RMW-Merge → `SaveComparePreset` → neuen Fingerabdruck lesen →
  `setETagHeader(w, ...)`.
- **Frontend-Pattern aus S3 direkt übertragbar:** `api.ts`s `request()`/`send()`
  sind bereits generisch genug, um eine zweite Ressourcen-Art (Compare-Presets)
  neben Trips zu tragen — die Erweiterung ist eine Frage der
  Pfad-Erkennung (`extractTripId` → generischer `extractResourceId`), nicht
  einer neuen Architektur.

## Dependencies

- **Upstream:** S1 (Fingerabdruck+Sperre-Fundament, deckt Compare-Presets
  bereits ab), S2 (ETag/If-Match-Vertrag am Beispiel Trip), S3 (Frontend-ETag-
  Registry + Warteschlange am Beispiel Trip) — alle live.
- **Downstream:** Kein Feature hängt von S6 ab; S6 schliesst eine bekannte
  Lücke (Cross-Write-Race bei gleichzeitigem Bearbeiten eines Ortsvergleichs),
  die bisher unbehoben ist.

## Existing Specs

- `docs/specs/modules/issue_1395_s2_etag_ifmatch.md` — Vertrag für Trip, als
  Vorbild für Compare-Presets
- `docs/specs/modules/issue_1395_s3_etag_registry.md` — Frontend-Warteschlange
  für Trip, als Vorbild; nennt S6 bereits explizit als Folgearbeit inkl. der
  Reentrancy-Warnung
- ADR: `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md`

## Risks & Considerations

1. **Reentrancy-Falle (verifiziert, entschärft):** Eine Sperre am Anfang von
   `UpdateBriefingHandler` würde den `kind=route`-Pfad blockieren (der intern
   `UpdateTripHandler` aufruft, der dieselbe, nicht-reentrante Sperre nimmt).
   Die neue Sperre gehört **ausschliesslich** in den `kind=vergleich`-Zweig
   (nach dem `if kind == route`-Dispatch, Zeile 193+), nicht vor den Dispatch.
2. **Zwei unabhängige Schreibwege auf dieselbe Datei:** `PUT
   /api/briefings/{id}?kind=vergleich` (via `UpdateBriefingHandler`) UND `PUT
   /api/compare/presets/{id}` (via `UpdateComparePresetHandler`) schreiben
   beide `briefings/<id>.json` über `SaveComparePreset`. **Beide** brauchen
   Sperre + If-Match — sonst bleibt der jeweils andere Weg der
   "Umgehungsweg", den der Issue-Kommentar explizit als Lücke benennt.
3. **ID-Namensraum:** Preset-IDs tragen ein `cp-`-Präfix
   (`compare_preset.go:80-86`, `"cp-" + hex(...)`), Trip-IDs sind
   präfixlose 8-Hex-Strings oder client-gewählt. Die Sperre schlüsselt auf die
   **exakte** ID (`briefing_lock.go:33`), keine Kollisionsgefahr zwischen den
   beiden ID-Räumen unter der Sperre selbst — unabhängig vom Präfix, da
   `LockBriefing` ID-agnostisch ist und nie zwei verschiedene IDs auf denselben
   Schlüssel abbildet.
4. **Frontend-Erweiterung ist Ausbau, keine Neuentwicklung:** `etagRegistry.ts`
   braucht einen zweiten Pfad-Regex (oder einen generalisierten), die
   Warteschlangen-Map muss auch für Compare-Preset-IDs funktionieren (aktuell
   nach `tripId` benannt — Umbenennung zu einem ressourcen-neutralen Namen
   erwägen, oder als zweite parallele Map für Presets, je nachdem was den
   Bestandscode am wenigsten anfasst).
5. **LoC-Rahmen:** 600 Zeilen/Scheibe (PO-Entscheidung), S1-S4 lagen zwischen
   135 und ~1529 Zeilen (letztere wegen umfangreicher Nachweise). S6 hat
   voraussichtlich mehr Produktivcode als S5 (zwei Go-Handler + Frontend-
   Registry-Ausbau + ~11 Aufrufstellen), realistisch im mittleren
   dreistelligen Bereich für Produktivcode, plus Nachweise.
6. **Kein neues sichtbares Verhalten für den Normalfall:** Wie bei S2 wird ein
   fehlender `If-Match` angenommen — bestehende Aufrufer bleiben zunächst
   unverändert lauffähig, bis das Frontend (diese Scheibe) den Header aktiv
   mitschickt. Der scharfe Umschaltpunkt liegt in derselben Scheibe wie bei
   Trip (S2+S3 waren dort getrennt) oder wird hier bewusst zusammengelegt —
   Entscheidung gehört in die Analyse-Phase.

## Analysis

### Type
Feature-Erweiterung (Nebenläufigkeitsschutz), analog #1395 S1-S5, auf zwei
Ressourcenarten (Compare-Presets, Umgehungsweg) übertragen.

### Affected Files

| Datei | Aktion | Grund |
|---|---|---|
| `internal/handler/compare_preset.go` | MODIFY | `UpdateComparePresetHandler` (Z.262) braucht Lock+If-Match wie `UpdateTripHandler`; `GetComparePresetHandler`/`ListComparePresetsHandler` fehlt ETag-Header (Trip-GET setzt ihn seit S2); `Create`/`Delete`/`UpdateComparePresetStateHandler` fehlt Lock (Trip-Pendants haben ihn seit S2, Symmetrie-Grund: Race gegen gleichzeitigen PUT) |
| `internal/handler/briefing_subscription.go` | MODIFY | `UpdateBriefingHandler` vergleich-Zweig (Z.193-244, der "Umgehungsweg") + `GetBriefingHandler` vergleich-Zweig (Z.66-77) analog |
| `internal/handler/compare_preset_etag_ifmatch_test.go` | CREATE | analog `trip_etag_ifmatch_test.go` |
| `internal/handler/briefing_subscription_etag_test.go` (o.ä.) | CREATE | Umgehungsweg-Nachweis |
| `frontend/src/lib/etagRegistry.ts` | MODIFY | `TRIP_PATH_RE` → generischer Regex/Funktion (`extractResourceId`), Registry/Queue-Naming ressourcen-neutral |
| `frontend/src/lib/api.ts` | MODIFY | minimal — `tripId`-Parameter ist bereits eine opake Ressourcen-ID |
| `frontend/src/lib/__tests__/etagRegistryQueue.test.ts` | MODIFY | Compare-Fälle ergänzen |
| Compare-Editor-Komponenten (`CompareTabs.svelte`, `compareWizardState.svelte.ts`, `compareEditorSave.ts`, ...) | **KEINE Änderung** | profitieren automatisch über `api.ts` — alle Compare-Schreib-Aufrufstellen laufen bereits durch `request()`/`send()` |

### Scope Assessment
- Files: ~7 (4 Produktivcode, 2-3 Tests)
- Estimated LoC: Produktivcode ~150-300; mit vollständigen gespiegelten Tests
  (S2-Vorbild) realistisch über 600 — `loc_limit_override` wahrscheinlich
  nötig (PO-Anfrage vorbereiten, nicht Scope künstlich kappen — der doppelte
  Backend-Schreibweg ist nicht teilbar, siehe Dependencies)
- Risk Level: MEDIUM (Reentrancy-Falle bereits entschärft/verifiziert;
  verbleibendes Risiko ist Vollständigkeit — beide Schreibwege UND alle
  CRUD-Handler brauchen Parität, sonst bleibt eine Lücke offen)

### Technical Approach

**Backend — Duplikation, kein neuer Helper.** Verifiziert am Bestandscode:
`trip.go`/`weather_config.go` wiederholen die Sequenz Lock→Fingerprint→
`ifMatchAllows`→Save→`setETagHeader` bereits zweimal inline, ohne
gemeinsamen Wrapper — nur die Low-Level-Bausteine aus `etag.go` werden
wiederverwendet. Gleiches Muster für `UpdateComparePresetHandler` und den
`kind=vergleich`-Zweig von `UpdateBriefingHandler` fortsetzen, keine neue
Abstraktion einführen.

**Frontend — generalisierte Registry (nicht zwei parallele).**
`extractTripId`/`writeQueues`/`knownEtags` behandeln die ID bereits als
opaken String — die Erweiterung ist Regex+Umbenennung, keine neue
Architektur. ID-Kollision ausgeschlossen (`cp-`-Präfix). Eine zweite,
parallele Registry würde Zustand und Tests duplizieren (Verstoß gegen das
Trip/Compare-Teilungsprinzip). **Fund:** Der Umgehungsweg `/api/briefings/{id}
?kind=vergleich` wird vom Frontend nirgends aufgerufen (0 Treffer) — reine
Server-Härtung, der Frontend-Regex muss nur `/api/compare/presets/{id}`
matchen.

**Scheiben-Zuschnitt: EINE Scheibe**, nicht S6a/S6b. Anders als bei Trip
(S2/S3 trennten, weil S3 die Registry-Infrastruktur NEU baute) baut S6 nur
eine bestehende Infrastruktur aus — der Frontend-Teil ist klein. Eine
Trennung erzeugte zwei dünne Scheiben mit doppeltem
Spec-/Adversary-/Staging-Aufwand ohne sichtbaren Zwischenstand.

**Bonus-Fund (kein neues Risiko, Zusatznutzen):** `CompareTabs.svelte` hat
seit #1256 eine eigene lokale Queue (`hubPutQueue`,
`compareHubWizardBridge.ts:407`), das eingebettete `WeatherMetricsTab`
(context="vergleich") läuft separat über `saveController.schedule()` — zwei
unkoordinierte lokale Queues auf derselben Preset-ID. S6s globale
HTTP-Layer-Queue in `api.ts` schließt diese Lücke automatisch mit,
ohne dass diese Komponenten angefasst werden müssen.

### Dependencies
Kein Frontend→Backend-Dependency (fail-open bei fehlendem `If-Match`, wie
S2). Aber: **beide Backend-Schreibwege müssen in derselben Scheibe landen**
— nur einen abzusichern ließe den anderen als Umgehungsweg offen (genau die
Lücke, die S6 laut Issue schließen soll).

### Open Questions
- [x] Create/Delete/State-Lock-Nachrüstung: Teil von S6 (Vollständigkeits-
  Parität zu Trip/S2) — entschieden, mit rein.
- [ ] Falls LoC trotz schlankerer Tests über 600 bleibt: PO-Override
  anfragen (nicht Scope künstlich kappen, Backend-Doppelweg nicht teilbar).
