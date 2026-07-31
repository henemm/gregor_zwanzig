---
entity_id: issue_1395_s6_ortsvergleich_etag
type: module
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [go, compare-preset, briefing-subscription, concurrency, etag, if-match, frontend]
---

<!-- Issue #1395 Scheibe S6 — Nebenlaeufigkeitsschutz: ETag/If-Match auf Ortsvergleich-Schreibpfaden inkl. Umgehungsweg -->

# Issue #1395 Scheibe S6 — ETag/If-Match fuer Ortsvergleich (Compare-Preset) inkl. Umgehungsweg

## Approval

- [ ] Approved

## Purpose

S2 hat dem Trip-Speichern (`/api/trips/{id}`) einen vollstaendigen Nebenlaeufigkeitsschutz
gegeben: Fingerabdruck als `ETag`, `If-Match`-Pruefung, serverseitige Sperre je
`user_id+id`. Der Ortsvergleich (Compare-Preset) teilt sich dieselbe Datei-Ebene
(`briefings/<id>.json`, `kind=vergleich`) und denselben Fingerabdruck-Mechanismus
(S1 deckt beide Ressourcenarten bereits ab), hat aber **keinen** der uebrigen
Bausteine — weder serverseitig (Sperre, If-Match) noch clientseitig (ETag-Erfassung,
Schreib-Warteschlange). Es kommt hinzu, dass es **zwei unabhaengige HTTP-Schreibwege**
auf dieselbe Datei gibt (`PUT /api/compare/presets/{id}` UND
`PUT /api/briefings/{id}?kind=vergleich`) — nur einen davon abzusichern liesse den
anderen als "Umgehungsweg" offen. Diese Scheibe schliesst beide.

## Source

- **File:** `internal/handler/compare_preset.go` — `UpdateComparePresetHandler`
  (Lock + If-Match + ETag), `GetComparePresetHandler` (Lock + ETag),
  `CreateComparePresetHandler`, `DeleteComparePresetHandler`,
  `UpdateComparePresetStateHandler` (Lock, kein If-Match — analog Trip-PATCH/DELETE)
- **File:** `internal/handler/briefing_subscription.go` — `UpdateBriefingHandler`s
  `kind=vergleich`-Zweig (Z.193-244, der "Umgehungsweg": Lock + If-Match + ETag),
  `GetBriefingHandler`s `kind=vergleich`-Zweig (Z.66-77: Lock + ETag)
- **File:** `internal/handler/etag.go` — unveraendert wiederverwendet
  (`ifMatchAllows`, `setETagHeader`, `writePreconditionFailed`, `preconditionFailedDetail`)
- **File:** `internal/store/briefing_lock.go` — `LockBriefing` unveraendert
  wiederverwendet (ID-agnostisch, kein Kind-Bewusstsein noetig)
- **File:** `frontend/src/lib/etagRegistry.ts` — `TRIP_PATH_RE`/`extractTripId`
  generalisiert auf `/api/compare/presets/{id}` zusaetzlich zu `/api/trips/{id}`
  (+`/weather-config`)
- **File:** `frontend/src/lib/api.ts` — keine funktionale Aenderung, `tripId`
  bleibt eine opake Ressourcen-ID
- **File:** `frontend/src/lib/__tests__/fakeTripServer.ts` — Pfad-Regex
  analog generalisiert (Testdoppel muss denselben Vertrag abbilden)
- **Identifier:** `store.BriefingFingerprint`, `store.LockBriefing` (beide S1,
  unveraendert), `handler.ifMatchAllows`/`handler.setETagHeader` (beide S2,
  unveraendert)

## Estimated Scope

- **LoC:** Produktivcode ~150-230 (Backend ~120-180, Frontend ~30-50); mit
  vollstaendigen gespiegelten Tests (S2-Erfahrung: Tests rissen dort die
  Schaetzung um Faktor ~2.5, weil jeder Nachweis die Datei auf Platte
  vorher/nachher prueft statt nur den Statuscode) realistisch **700-1000**.
  **`loc_limit_override` wird wahrscheinlich noetig — PO-Anfrage vorbereiten,
  Scope nicht kuenstlich kappen** (der doppelte Backend-Schreibweg ist nicht
  teilbar, siehe Dependencies).
- **Files:** 8 (4 Produktivdateien Backend/Frontend geaendert, 2 neue
  Go-Testdateien, 1 bestehende Frontend-Testdatei erweitert, 1 Test-Doppel
  erweitert)
- **Effort:** medium-high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `store.BriefingFingerprint` (S1) | Go-Funktion | Fingerabdruck deckt laut Docstring bereits Trip UND Ortsvergleich ab — kein Ausbau noetig |
| `store.LockBriefing` (S1) | Go-Funktion | Sperre ist ID-agnostisch, gilt fuer Preset-IDs (`cp-`-Praefix) genauso wie fuer Trip-IDs |
| `internal/handler/etag.go` (`ifMatchAllows`, `setETagHeader`, `writePreconditionFailed`) (S2) | Go-Funktionen | Wiederverwendet ohne Aenderung — kein neuer Mechanismus |
| `docs/specs/modules/issue_1395_s2_etag_ifmatch.md` | Spec | Vorbild-Muster fuer Backend-Sequenz und Testaufbau, warnt explizit vor der Reentrancy-Falle (Abschnitt „Offene Punkte") |
| `docs/specs/modules/issue_1395_s3_etag_registry.md` | Spec | Vorbild-Muster fuer Frontend-Registry/Warteschlange |
| `frontend/src/lib/__tests__/apiTripEtagHeaders.test.ts:136-151` | Test | `test_nonTripPaths_completelyUnaffected` markiert compare/presets-Pfade ausdruecklich mit Kommentar `→ S6` — diese Scheibe muss dort eine positive Gegenprobe ergaenzen |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/handler/compare_preset.go` | MODIFY | `UpdateComparePresetHandler`: Lock + Fingerabdruck-vorher + `ifMatchAllows` + 412 + `setETagHeader`. `GetComparePresetHandler`: Lock + `setETagHeader` (kein If-Match, reiner Lesevorgang, analog `TripHandler`). `CreateComparePresetHandler`: Lock um den Schreibvorgang (Symmetrie zu Trip, siehe „Analyse: Create-Sperre" unten), kein ETag in der Antwort. `DeleteComparePresetHandler`, `UpdateComparePresetStateHandler`: Lock, kein If-Match (analog `DeleteTripHandler`/`UpdateTripStateHandler`). Zusaetzlich alle 6 Handler `s = s.WithUser(...)` → `s := s.WithUser(...)` (schliesst denselben Closure-Datenwettlauf, den S2 in `trip.go` behoben hat — hier direkt sicherheitsrelevant, weil der neue Sperrschluessel von `s.UserID` abhaengt, siehe „Implementation Details") |
| `internal/handler/briefing_subscription.go` | MODIFY | `UpdateBriefingHandler`: Lock + Fingerabdruck + `ifMatchAllows` + 412 + `setETagHeader`, **ausschliesslich im `kind=vergleich`-Zweig NACH dem `kind=route`-Dispatch** (Reentrancy-Falle, siehe unten). `GetBriefingHandler`: Lock + `setETagHeader` im `kind=vergleich`-Zweig. `s = s.WithUser(...)` → `s := s.WithUser(...)` in `GetBriefingHandler`, `ListBriefingsHandler`, `UpdateBriefingHandler` (3 Stellen, gleicher Grund wie oben) |
| `internal/handler/compare_preset_etag_ifmatch_test.go` | CREATE | Testfaelle fuer Compare-Preset-GET/PUT/POST/DELETE/PATCH — analog `trip_etag_ifmatch_test.go` |
| `internal/handler/briefing_subscription_vergleich_etag_test.go` | CREATE | Umgehungsweg-Nachweis (Cross-Path-Schutz) + Reentrancy-Nachweis (`kind=route` bleibt unversehrt) |
| `frontend/src/lib/etagRegistry.ts` | MODIFY | `TRIP_PATH_RE` → generalisierter Regex, der zusaetzlich `/api/compare/presets/{id}` matcht. Kommentar/Doku-String angepasst (nennt jetzt beide Ressourcenarten). Kein zweiter paralleler Satz an Maps — dieselbe `knownEtags`/`writeQueues`/`etagVersions`-Registry traegt beide, ID-Kollision durch `cp-`-Praefix ausgeschlossen. Exportierte Funktionsnamen (`extractTripId`, `enqueueTripWrite` etc.) bleiben unveraendert benannt — Umbenennen auf ressourcenneutrale Namen wuerde alle Aufrufer anfassen (`api.ts`, mehrere Tests) fuer reinen Kosmetik-Gewinn, siehe „Known Limitations" |
| `frontend/src/lib/api.ts` | KEINE Aenderung | `request()`/`send()` behandeln `tripId` bereits als opake Ressourcen-ID (verifiziert: kein Trip-spezifischer Code in diesen Funktionen) |
| `frontend/src/lib/__tests__/fakeTripServer.ts` | MODIFY | `TRIP_PATH_RE` (Zeile 39) analog generalisiert, damit das Testdoppel denselben erweiterten Vertrag abbildet wie der echte Server — sonst koennten Frontend-Tests fuer Compare-Presets gruen sein, obwohl der echte Server anders reagiert |
| `frontend/src/lib/__tests__/apiTripEtagHeaders.test.ts` | MODIFY | Neuer `describe`-Block „Trichter: Ortsvergleich (S6)" mit den positiven Gegenstuecken zu den bestehenden Trip-Tests (GET setzt Stempel, PUT traegt ihn automatisch, neuer Stempel nach PUT). `test_nonTripPaths_completelyUnaffected` bleibt fuer `/api/locations/...` unveraendert gueltig (Orte sind weiterhin NICHT betroffen); der Kommentar „→ S6" an der Compare-Preset-Zeile wird durch einen Verweis auf den neuen Block ersetzt |
| Compare-Editor-Komponenten (`CompareTabs.svelte`, `compareWizardState.svelte.ts`, ...) | **KEINE Aenderung** | Verifiziert: beide Schreib-Aufrufstellen (`compareWizardState.svelte.ts:147` POST, PUT-Aufrufstelle) laufen bereits ueber `api.post`/`api.put` → `request()`/`send()`, profitieren automatisch |
| `openapi.yaml` | **KEINE Aenderung** | Verifiziert: `/api/compare/presets/*` ist dort bereits vollstaendig undokumentiert (0 Treffer) — anders als bei Trip (S2 ergaenzte eine BESTEHENDE Dokumentation), gibt es hier keinen bestehenden Vertrag, der falsch wuerde. Ergaenzen waere ein separater Dokupflege-Auftrag, kein Korrektheitsthema dieser Scheibe (siehe „Known Limitations") |

### Estimated Changes

- Files: 8 (4 Produktiv, 2 neue Go-Tests, 2 erweiterte Frontend-Tests/-Doppel)
- LoC: siehe „Estimated Scope"

## Implementation Details

### Ablauf in `UpdateComparePresetHandler` (Haupt-Schreibweg)

Identische Reihenfolge wie `UpdateTripHandler` (S2), auf die bestehende
`LoadComparePresets()`+`findComparePresetIdx`-Struktur aufgesetzt (kein
Umbau auf `LoadComparePreset(id)` singular — das waere ein groesserer,
unbeauftragter Refactor):

1. `s := s.WithUser(...)` (korrigiert von `=`), `id := chi.URLParam(r, "id")`
2. `defer s.LockBriefing(id)()`
3. `oldFp, fpErr := s.BriefingFingerprint(id)` — Fehler → `500 store_error`
4. `presets, err := s.LoadComparePresets()` (unveraendert), `idx := findComparePresetIdx(...)` — nicht gefunden → `404`
5. `original := presets[idx]`
6. **NEU, vor dem Dekodieren des Rumpfes:** `ifMatchAllows(r.Header.Get("If-Match"), oldFp)`
   prüfen — bei Ablehnung `writePreconditionFailed` (`412`), Funktion endet, nichts wird
   geschrieben
7. Rumpf dekodieren, Merge-Logik wie bisher (server-verwaltete Felder erhalten,
   `NormalizeComparePreset`, `ClampComparePresetDayWindow`, `validateComparePreset`) — **unveraendert**
8. `s.SaveComparePreset(updated)` — wie bisher
9. **NEU:** `newFp, newFpErr := s.BriefingFingerprint(id)`, `setETagHeader(w, newFp, newFpErr)`
10. Antwort wie bisher (`200`, `updated`)

### Ablauf in `GetComparePresetHandler`

Wie `TripHandler` (S2): `defer s.LockBriefing(id)()` VOR dem Laden (sonst
koennte ein gleichzeitiger PUT zwischen Fingerabdruck-Lesen und
Rumpf-Serialisierung dazwischenfunken — der ausgelieferte `ETag` muss zur
ausgelieferten Fassung passen). Nach dem Laden: `fp, fpErr :=
s.BriefingFingerprint(id)`, `setETagHeader(w, fp, fpErr)`, dann Antwort wie
bisher.

**Bewusste Abweichung von der Aufgabenbeschreibung:** `ListComparePresetsHandler`
bekommt **keinen** ETag-Header (nicht: „ETag-Header setzen" wie urspruenglich
skizziert). Begruendung: Trips `TripsHandler` (die Liste) traegt seit S2
ebenfalls keinen ETag — eine Liste hat keinen einzelnen Fingerabdruck, auf den
ein `If-Match` sich sinnvoll beziehen koennte. Echte Parität zu Trip bedeutet
hier, die Liste GENAUSO auszulassen wie beim Vorbild, nicht sie abweichend zu
behandeln. `s = s.WithUser(...)` → `s := s.WithUser(...)` bleibt trotzdem
bestehen (Korrektheitsfix unabhaengig vom Lock).

### Ablauf in `CreateComparePresetHandler`, `DeleteComparePresetHandler`, `UpdateComparePresetStateHandler`

`defer s.LockBriefing(id)()` (bei Create: `preset.ID`, erst nach dessen
Generierung verfuegbar — Lock direkt vor `SaveComparePreset`, analog
`CreateTripHandler`). Kein `If-Match` (analog Trip-PATCH/DELETE, AC-15-Muster).
Create liefert weiterhin **keinen** ETag (Client holt nach dem Anlegen frisch).

**Analyse: Ist die Create-Sperre notwendig?** Preset-IDs sind
kryptographisch-zufaellig (`newComparePresetID()`, 8 zufaellige Bytes = 64 Bit
Entropie) — eine ID-Kollision zwischen zwei gleichzeitigen `CreateComparePresetHandler`-Aufrufen
ist praktisch ausgeschlossen, anders als bei Trip (dort kann die ID
theoretisch client-beeinflusst sein). Die Sperre wird trotzdem aufgenommen,
nicht weil ein konkretes Race behoben wird, sondern fuer **strukturelle
Parität**: jeder HTTP-Pfad, der `briefings/<id>.json` schreibt, nimmt die
Sperre — die Lehre aus dem Loeschpfad-Nachtrag in S2 (dort fehlte sie an
`DeleteTripHandler` und ermoeglichte ein Wiederauferstehen geloeschter Touren).
Kosten ist eine Zeile, der Nutzen ist eine geschlossene Invariante statt einer
Ausnahme, die zukuenftig erneut uebersehen werden kann.

### Ablauf im Umgehungsweg — `UpdateBriefingHandler`s `kind=vergleich`-Zweig

**KRITISCH (verifiziert am Code):** Die Sperre gehoert AUSSCHLIESSLICH in den
`kind=vergleich`-Zweig, NACH der `if kind == briefingKindRoute { ...; return }`-Weiche
(aktuell Zeile 189-192). `store.LockBriefing` ist eine `sync.Mutex`-basierte
Sperre, NICHT wiedereintrittsfaehig. `kind=route` reicht per `ServeHTTP` an
`UpdateTripHandler` durch, der fuer dieselbe `<Nutzer, ID>` bereits dieselbe
Sperre nimmt (S2) — eine zweite Sperre VOR der Weiche wuerde jeden
`kind=route`-Aufruf sicher selbst blockieren (Deadlock). Reihenfolge:

1. `if kind == briefingKindRoute { UpdateTripHandler(s).ServeHTTP(w, r); return }` — **unveraendert, keine Sperre hier**
2. `s := s.WithUser(...)` (korrigiert von `=`), `id := chi.URLParam(r, "id")`
3. **NEU:** `defer s.LockBriefing(id)()` — ab hier, nicht frueher
4. **NEU:** `oldFp, fpErr := s.BriefingFingerprint(id)` — Fehler → `500`
5. `patch, err := io.ReadAll(r.Body)` (Position relativ zu 3/4 unerheblich — Rohbytes lesen veraendert nichts)
6. `presets, err := s.LoadComparePresets()`, `idx := findComparePresetIdx(...)` — nicht gefunden → `404`
7. `original := presets[idx]`
8. **NEU, vor `mergeBriefingPatch`:** `ifMatchAllows(r.Header.Get("If-Match"), oldFp)` pruefen — bei Ablehnung `412`, nichts wird geschrieben
9. `mergeBriefingPatch`, Unmarshal, server-verwaltete Felder restaurieren, `MaterializePausedAt`, `NormalizeComparePreset`, `validateComparePreset` — **unveraendert**
10. `s.SaveComparePreset(preset)` — wie bisher
11. **NEU:** `newFp, newFpErr := s.BriefingFingerprint(id)`, `setETagHeader(w, newFp, newFpErr)`
12. Antwort wie bisher (`200`, `preset`)

### Ablauf in `GetBriefingHandler`s `kind=vergleich`-Zweig

`s := s.WithUser(...)` (Fix gilt fuer BEIDE Zweige, da vor der `kind`-Weiche
plaziert). Im `vergleich`-Zweig zusaetzlich `defer s.LockBriefing(id)()` vor
`s.LoadComparePreset(id)`, danach `fp, fpErr := s.BriefingFingerprint(id)`,
`setETagHeader(w, fp, fpErr)`. Der `route`-Zweig bleibt unveraendert (die
Trip-Sperre existiert dort bereits seit S2, `TripHandler` wird aber hier gar
nicht aufgerufen — der `route`-Zweig von `GetBriefingHandler` laedt selbst per
`s.LoadTrip`, ohne Sperre; das ist **vorbestehender** Zustand, siehe „Known
Limitations", NICHT Teil dieser Scheibe).

### `s = s.WithUser(...)` → `s := s.WithUser(...)` — warum hier PFLICHT, nicht optional

S2 hat denselben Closure-Datenwettlauf in `trip.go`/`weather_config.go`
behoben (Issue #1396, siehe dortiges „Known Limitations": 26 weitere Stellen
bleiben offen). Alle sechs Handler in `compare_preset.go` und drei Stellen in
`briefing_subscription.go` (`GetBriefingHandler`, `ListBriefingsHandler`,
`UpdateBriefingHandler`) tragen denselben Fehler (verifiziert per grep:
ausschliesslich `s = s.WithUser(...)`, keine einzige `:=`-Stelle in beiden
Dateien). Das ist hier nicht nur ein allgemeiner Nebenbefund: **der neue
Sperrschluessel (`LockBriefing`, `store.go`: `s.UserID + "\x00" + id`) haengt
direkt von `s.UserID` ab.** Ueberschreibt eine gleichzeitige Anfrage die von
der Closure geteilte Variable, bevor `LockBriefing(id)` sie liest, sperrt der
Handler unter der FALSCHEN `UserID` — ein Mandantentrennungs-Risiko, das genau
in den Zeilen entsteht, die diese Scheibe neu einfuehrt. Der Fix wird daher
NICHT als eigener Nebenbefund ausgelagert, sondern hier miterledigt, exakt wie
S2 es fuer `trip.go` getan hat. `ListBriefingsHandler` bekommt keinen Lock,
der Fix dort laeuft trotzdem mit (gleiche Datei, gleicher Fehler, keine
Mehrkosten). Alle uebrigen Stellen ausserhalb dieser zwei Dateien bleiben
unter #1396 offen — unveraendert durch diese Scheibe.

### Frontend — `etagRegistry.ts`

`TRIP_PATH_RE` wird generalisiert, um zusaetzlich `/api/compare/presets/{id}`
zu erkennen (kein `/weather-config`-Aequivalent bei Compare-Presets, also
schlichter zweiter Alternationszweig):

```
const RESOURCE_PATH_RE =
  /^\/api\/(?:trips\/([^/?#]+)(?:\/weather-config)?|compare\/presets\/([^/?#]+))(?:[?#]|$)/;
```

`extractTripId` (Name unveraendert, siehe Begruendung im Affected-Files-Eintrag)
liefert `match[1] ?? match[2]`, decodiert wie bisher. Der Rest des Moduls
(`knownEtags`, `writeQueues`, `etagVersions`, `enqueueTripWrite`, ...) bleibt
unveraendert — er behandelt die ID bereits als opaken String, keine
Trip-spezifische Logik darin. ID-Kollision zwischen Trip- und Preset-IDs ist
durch das `cp-`-Praefix der Preset-IDs ausgeschlossen (verifiziert:
`newComparePresetID()`, `compare_preset.go:80-86`).

### Frontend — `fakeTripServer.ts` (Testdoppel)

`TRIP_PATH_RE` (Zeile 39) analog generalisiert. Der Rest des Doppels
(Fingerabdruck-Simulation, `ifMatchAllows`-Spiegel, `412`-Antwort) ist bereits
ressourcen-neutral (arbeitet mit einer generischen `tripId`-Variable als
Schluessel) und braucht keine weitere Anpassung.

## Expected Behavior

- **Input:** `GET /api/compare/presets/{id}` → Antwort traegt `ETag: "<Fingerabdruck>"`,
  sofern das Preset existiert
- **Input:** `PUT /api/compare/presets/{id}` ohne `If-Match` → wie bisher angenommen
- **Input:** `PUT /api/compare/presets/{id}` mit veraltetem `If-Match` → `412`,
  Datei nachweislich unveraendert
- **Input:** `PUT /api/briefings/{id}?kind=vergleich` verhaelt sich in allen drei
  Punkten identisch — UND die Vorbedingung greift ueber BEIDE Pfade hinweg
  gemeinsam (derselbe Fingerabdruck, dieselbe Sperre)
- **Input:** `PUT /api/briefings/{id}?kind=route` funktioniert nach der Aenderung
  unveraendert (kein Selbstblockierer)
- **Output:** jeder erfolgreiche `PUT` auf beiden Compare-Pfaden liefert den
  NEUEN `ETag`
- **Side effects:** keine — Sperre ist prozessintern (S1), kein neuer
  Persistenz-Zustand

## Testplan

Alle Go-Tests in `internal/handler/`, echte Dateien via `t.TempDir()`-Store
(Bestandsmuster), kein Mock. Frontend-Tests via `node:test` + `fakeTripServer.ts`
(kein Mock im verbotenen Sinn — echter Ersatz-Fetch mit echtem Vertrag).

### `internal/handler/compare_preset_etag_ifmatch_test.go`

| Test | Deckt |
|---|---|
| `TestGetComparePresetHandler_ReturnsETag` | AC-1 |
| `TestGetComparePresetHandler_ETagStableAcrossReads` | AC-2 |
| `TestUpdateComparePresetHandler_NoIfMatch_Accepted` | AC-3 |
| `TestUpdateComparePresetHandler_MatchingIfMatch_Accepted` | AC-4 |
| `TestUpdateComparePresetHandler_StaleIfMatch_Returns412_FileUnchanged` | AC-5 |
| `TestUpdateComparePresetHandler_ReturnsNewETag_SecondPutSucceeds` | AC-6 |
| `TestUpdateComparePresetHandler_ConcurrentWrites_SecondWithStaleETagLoses` | AC-7 |
| `TestUpdateComparePresetHandler_TenantIsolation_ETagNotSharedAcrossUsers` | AC-12 |
| `TestUpdateComparePresetHandler_IfMatchWildcard_Accepted` | AC-13 |
| `TestCreateComparePresetHandler_NoETagInResponse_TakesLock` | AC-14 |
| `TestDeleteComparePresetHandler_WaitsForBriefingLock_NoIfMatchCheck` | AC-15 |
| `TestUpdateComparePresetStateHandler_NoIfMatchCheck_LockOnly` | AC-15 |
| `TestExistingComparePresetTests_StillGreen` (Regressionsvermerk, s. „Was nicht kaputtgehen darf") | AC-16 |

### `internal/handler/briefing_subscription_vergleich_etag_test.go`

| Test | Deckt |
|---|---|
| `TestGetBriefingHandler_Vergleich_ReturnsETag_MatchesComparePresetETag` | AC-10 |
| `TestUpdateBriefingHandler_Vergleich_NoIfMatch_Accepted` | AC-8 |
| `TestUpdateBriefingHandler_Vergleich_StaleIfMatch_Returns412_FileUnchanged` | AC-8 |
| `TestUpdateBriefingHandler_Vergleich_ReturnsNewETag` | AC-8 |
| `TestCrossPath_WriteViaComparePresetsThenStaleWriteViaBriefingsVergleich_Returns412` | AC-9 (Kern) |
| `TestCrossPath_WriteViaBriefingsVergleichThenStaleWriteViaComparePresets_Returns412` | AC-9 (Kern) |
| `TestUpdateBriefingHandler_Route_StillWorks_NoDeadlock` | AC-11 (Reentrancy) |

### `frontend/src/lib/__tests__/apiTripEtagHeaders.test.ts` (erweitert)

Neuer Block „Trichter: Ortsvergleich (S6)":

| Test | Deckt |
|---|---|
| `test_get_capturesEtagFromComparePresetResponse` | AC-17 |
| `test_put_attachesIfMatch_whenComparePresetStampKnown` | AC-17 |
| `test_put_omitsIfMatch_whenComparePresetStampUnknown` | AC-17 |
| `test_tripAndComparePresetStamps_doNotCollide_evenWithSameSuffix` | AC-17 (Namensraum-Trennung) |

## Acceptance Criteria

- **AC-1:** Given ein gespeichertes Compare-Preset existiert / When `GET /api/compare/presets/{id}` aufgerufen wird / Then traegt die Antwort einen `ETag`-Header mit dem Fingerabdruck des aktuellen Standes
  - Test: `TestGetComparePresetHandler_ReturnsETag` — echter HTTP-Response-Header

- **AC-2:** Given ein Preset wurde seit dem letzten Lesen nicht veraendert / When zweimal hintereinander `GET` aufgerufen wird / Then sind beide `ETag`-Werte identisch
  - Test: `TestGetComparePresetHandler_ETagStableAcrossReads`

- **AC-3:** Given ein Client sendet KEINEN `If-Match`-Header / When er `PUT /api/compare/presets/{id}` aufruft / Then wird der Schreibvorgang wie bisher angenommen
  - Test: `TestUpdateComparePresetHandler_NoIfMatch_Accepted`

- **AC-4:** Given ein Client sendet den zuletzt erhaltenen `ETag`-Wert als `If-Match` / When er `PUT` aufruft / Then wird der Schreibvorgang angenommen
  - Test: `TestUpdateComparePresetHandler_MatchingIfMatch_Accepted`

- **AC-5:** Given ein Client sendet einen veralteten `If-Match`-Wert / When er `PUT` aufruft / Then antwortet der Server mit `412` und die gespeicherte Datei ist nachweislich unveraendert (Dateiinhalt vorher/nachher verglichen)
  - Test: `TestUpdateComparePresetHandler_StaleIfMatch_Returns412_FileUnchanged`

- **AC-6:** Given ein erfolgreicher `PUT` liefert einen neuen `ETag` / When derselbe Client sofort einen zweiten `PUT` mit genau diesem neuen `ETag` sendet / Then wird auch dieser zweite Schreibvorgang angenommen
  - Test: `TestUpdateComparePresetHandler_ReturnsNewETag_SecondPutSucceeds`

- **AC-7:** Given zwei Clients haben denselben Ausgangsstand gelesen / When Client A zuerst erfolgreich schreibt und Client B danach mit dem inzwischen veralteten `If-Match`-Wert schreiben will / Then verliert Client B mit `412`, Client A's Aenderung bleibt erhalten
  - Test: `TestUpdateComparePresetHandler_ConcurrentWrites_SecondWithStaleETagLoses`

- **AC-8:** Given der Umgehungsweg `PUT /api/briefings/{id}?kind=vergleich` unterliegt derselben Vorbedingungs-Logik wie der dedizierte Preset-Endpunkt / When ohne, mit passendem oder mit veraltetem `If-Match` aufgerufen wird / Then verhaelt er sich analog AC-3/AC-4/AC-5
  - Test: `TestUpdateBriefingHandler_Vergleich_NoIfMatch_Accepted`, `TestUpdateBriefingHandler_Vergleich_StaleIfMatch_Returns412_FileUnchanged`, `TestUpdateBriefingHandler_Vergleich_ReturnsNewETag`

- **AC-9 (Kern der Scheibe):** Given ein Preset wurde ueber EINEN der beiden Schreibwege zuletzt geschrieben / When ein Client mit einem inzwischen veralteten `If-Match`-Wert ueber den JEWEILS ANDEREN Schreibweg schreiben will / Then wird dieser Schreibvorgang ebenfalls mit `412` abgelehnt (in BEIDEN Richtungen: Preset→Briefings und Briefings→Preset) — kein Weg bleibt eine Umgehung des anderen
  - Test: `TestCrossPath_WriteViaComparePresetsThenStaleWriteViaBriefingsVergleich_Returns412`, `TestCrossPath_WriteViaBriefingsVergleichThenStaleWriteViaComparePresets_Returns412`

- **AC-10:** Given `GET /api/briefings/{id}?kind=vergleich` liefert denselben Fingerabdruck wie `GET /api/compare/presets/{id}` (dieselbe Datei) / When beide GET-Aufrufe fuer dasselbe Preset hintereinander erfolgen / Then sind beide `ETag`-Werte identisch
  - Test: `TestGetBriefingHandler_Vergleich_ReturnsETag_MatchesComparePresetETag`

- **AC-11 (Reentrancy):** Given `UpdateBriefingHandler` reicht `kind=route` per `ServeHTTP` an `UpdateTripHandler` durch, der bereits dieselbe Sperre nimmt / When nach dieser Aenderung `PUT /api/briefings/{id}?kind=route` aufgerufen wird / Then antwortet der Server weiterhin normal (kein Deadlock, keine Zeitueberschreitung) — die neue Sperre im `vergleich`-Zweig wird fuer `kind=route`-Aufrufe NIE genommen
  - Test: `TestUpdateBriefingHandler_Route_StillWorks_NoDeadlock` — Aufruf mit `context.WithTimeout` oder Erfolgsnachweis innerhalb kurzer Frist

- **AC-12:** Given zwei verschiedene Nutzer haben je ein eigenes Compare-Preset mit derselben Preset-ID / When Nutzer A einen `ETag` erhaelt und diesen als `If-Match` gegen Nutzer B's Preset sendet / Then greift die Pruefung nicht ueber die Mandantengrenze
  - Test: `TestUpdateComparePresetHandler_TenantIsolation_ETagNotSharedAcrossUsers` — zwei `Store`-Instanzen mit unterschiedlicher `UserID`

- **AC-13:** Given ein Preset existiert / When ein Client `If-Match: *` sendet / Then wird der Schreibvorgang unabhaengig vom konkreten Fingerabdruck angenommen
  - Test: `TestUpdateComparePresetHandler_IfMatchWildcard_Accepted`

- **AC-14:** Given ein Client legt ein neues Compare-Preset an / When `POST /api/compare/presets` antwortet / Then traegt die Antwort KEINEN `ETag`-Header, UND der Schreibvorgang lief innerhalb der Briefing-Sperre (nachweisbar durch einen konkurrierenden Aufruf, der auf die Freigabe wartet)
  - Test: `TestCreateComparePresetHandler_NoETagInResponse_TakesLock`

- **AC-15:** Given `DELETE /api/compare/presets/{id}` und `PATCH /api/compare/presets/{id}/state` nehmen dieselbe Sperre wie der PUT-Pfad / When dort ein `If-Match`-Header mitgeschickt wird / Then wird er ignoriert — die Anfrage wird unabhaengig vom Header-Wert angenommen, solange das Preset existiert
  - Test: `TestDeleteComparePresetHandler_WaitsForBriefingLock_NoIfMatchCheck`, `TestUpdateComparePresetStateHandler_NoIfMatchCheck_LockOnly`

- **AC-16:** Given alle bestehenden Compare-Preset-Schreibtests senden heute keinen `If-Match`-Header / When diese Scheibe implementiert ist / Then bleiben alle diese Tests unveraendert gruen (siehe „Was nicht kaputtgehen darf")
  - Test: bestehende Suiten laufen unveraendert mit; kein neuer Testkoerper

- **AC-17 (Frontend):** Given ein Compare-Preset wurde per `GET /api/compare/presets/{id}` ueber den Frontend-Trichter geladen / When derselbe Client danach `PUT /api/compare/presets/{id}` ueber `api.put` aufruft / Then traegt die Anfrage den zuvor erhaltenen Stempel automatisch als `If-Match`-Header — ohne dass die aufrufende Komponente (Compare-Editor) davon etwas weiss. Zusaetzlich: ein Trip- und ein Compare-Preset-Stempel mit numerisch aehnlichem Suffix kollidieren in der Registry nicht
  - Test: `test_get_capturesEtagFromComparePresetResponse`, `test_put_attachesIfMatch_whenComparePresetStampKnown`, `test_tripAndComparePresetStamps_doNotCollide_evenWithSameSuffix`

## Was nicht kaputtgehen darf

Alle folgenden Bestandstests senden heute KEINEN `If-Match`-Header und muessen
unveraendert gruen bleiben:

- `internal/handler/compare_preset_test.go`
- `internal/handler/compare_preset_511_test.go`
- `internal/handler/compare_preset_day_window_test.go`
- `internal/handler/compare_preset_detail_test.go`
- `internal/handler/compare_preset_hourly_enabled_test.go`
- `internal/handler/compare_preset_hourly_roundtrip_test.go`
- `internal/handler/compare_preset_official_alerts_test.go`
- `internal/handler/compare_preset_official_warnings_test.go`
- `internal/handler/compare_preset_outlook_enabled_test.go`
- `internal/handler/compare_preset_prev_schedule_test.go`
- `internal/handler/compare_preset_radar_alert_enabled_test.go`
- `internal/handler/compare_preset_response_null_fields_test.go`
- `internal/handler/compare_preset_send_test.go`
- `internal/handler/compare_preset_slot_hour_normalization_test.go`
- `internal/handler/compare_preset_slot_schedule_test.go`
- `internal/handler/compare_preset_state_test.go`
- `internal/router/briefing_subscription_test.go`
- `frontend/src/lib/__tests__/apiTripEtagHeaders.test.ts` (bestehende Trip-Faelle unveraendert)

## Known Limitations

- **Mandantentrennung:** kurz geprueft — alle betroffenen Handler reichen
  `middleware.UserIDFromContext(r.Context())` bereits korrekt durch
  `s.WithUser(...)` durch (kein `"default"`-Fallback gefunden); der einzige
  Mangel war die Closure-Variable (`=` statt `:=`), der in dieser Scheibe
  behoben wird. Kein neuer Test fuer die Durchreichung selbst noetig, AC-12
  deckt die Konsequenz (ETag/Sperre nicht nutzergrenzenuebergreifend
  wirksam) ab.
- `GetBriefingHandler`s `route`-Zweig laedt weiterhin ohne eigene Sperre
  direkt per `s.LoadTrip` (nicht ueber `TripHandler`, das die Sperre seit S2
  haelt) — **vorbestehender Zustand, nicht Teil dieser Scheibe.** Ein
  gleichzeitiger `PUT /api/trips/{id}` koennte dort theoretisch zwischen
  Fingerabdruck-Aequivalent (hier: keiner) und Serialisierung dazwischenfunken;
  betrifft aber keinen `ETag`-Vertrag, da dieser Pfad ohnehin keinen setzt.
  Eigenes Ticket, falls relevant — nicht in dieser Scheibe.
- `openapi.yaml` dokumentiert `/api/compare/presets/*` weiterhin gar nicht
  (vorbestehender Zustand, durch diese Scheibe nicht verschlechtert) — eine
  vollstaendige Dokumentation dieser Pfade waere ein eigener, unabhaengiger
  Dokupflege-Auftrag.
- `frontend/src/lib/etagRegistry.ts` behaelt die Namen `extractTripId`,
  `enqueueTripWrite`, `getKnownEtag`/`tripId`-Parameter trotz jetzt zwei
  Ressourcenarten — ein Umbenennen auf ressourcenneutrale Namen wurde bewusst
  NICHT gemacht, um den Diff auf alle Aufrufer (`api.ts`, mehrere
  Testdateien) zu vermeiden, der keinen Verhaltensgewinn brachte. Rein
  kosmetisch, kann bei naechster inhaltlicher Aenderung an der Datei
  nachgezogen werden.
- Der bestehende Doppel-Queue-Zustand in `CompareTabs.svelte`/
  `compareHubWizardBridge.ts` (`hubPutQueue`) und `WeatherMetricsTab`
  (context="vergleich", `saveController.schedule()`) wird durch die neue
  globale HTTP-Layer-Queue in `api.ts` automatisch mit-entschaerft, aber NICHT
  aktiv angefasst — Nebeneffekt, kein Auftrag dieser Scheibe.
- `s = s.WithUser(...)` bleibt an **allen uebrigen Stellen** in
  `internal/handler/*.go` unveraendert (Issue #1396, urspruenglich 26 offene
  Stellen dokumentiert in S2) — diese Scheibe schliesst nur die 9 Stellen in
  `compare_preset.go` (6) und `briefing_subscription.go` (3), weil sie in den
  hier ohnehin geaenderten Dateien liegen und der neue Sperrschluessel direkt
  von der korrigierten Variable abhaengt. Der verbleibende Zaehler unter
  #1396 reduziert sich entsprechend, wird aber nicht als eigener Schritt
  dieser Scheibe nachgefuehrt.
- Kein Frontend-Zwang: fehlt `If-Match`, verhaelt sich jeder Aufruf exakt wie
  vor dieser Scheibe (Rollout-Politik wie S2/S3) — die Frontend-Registry
  schaltet automatisch scharf, sobald ein Compare-Preset einmal per `GET`
  geladen wurde.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0036 gilt bereits)
- **Rationale:** ADR-0036 hat die Entscheidung „Inhalts-Fingerabdruck statt
  Versionsfeld" bereits getroffen und wurde am Beispiel Trip (S2) umgesetzt.
  Diese Scheibe wendet dieselbe Entscheidung nur auf eine zweite,
  bereits vom Fingerabdruck (S1) abgedeckte Ressourcenart an — kein neuer
  Systemteil, kein neuer Cross-Language-Vertrag, keine neue schwer
  umkehrbare Wahl. Ein neues ADR waere hier reine Wiederholung.

## Changelog

- 2026-07-31: Initial spec erstellt — Issue #1395 Scheibe S6, aufbauend auf S1/S2/S3 (alle live)
