# Context: fix-1396-store-race-handler

Issue: [#1396](https://github.com/henemm/gregor_zwanzig/issues/1396) — `priority:critical`, `bug`

## Request Summary

25 HTTP-Handler in `internal/handler/` schreiben mit `s = s.WithUser(...)` in eine
Variable, die sich **alle gleichzeitigen Anfragen dieser Route teilen**. Zwei
parallele Anfragen verschiedener Nutzer können sich damit gegenseitig den Store
überschreiben — Datenwettlauf im Sinne des Go-Speichermodells und potenzielles
Cross-User-Datenleck, weil `Store.UserID` das Datenverzeichnis
`data/users/<user_id>/` bestimmt.

## Ist-Stand (nachgezählt, nicht aus dem Issue übernommen)

Das Issue nennt 26 offene Stellen. Es sind **25 Code-Stellen** — der 26. Treffer
(`internal/handler/trip.go:20`) ist der Erklärkommentar aus #1395 S2.

| Datei | Stellen | Betroffene Handler |
|---|---|---|
| `internal/handler/compare_preset.go` | 6 | `List`/`Create`/`Update`/`Delete`/`UpdateState`/`Get` ComparePreset |
| `internal/handler/location.go` | 6 | `Locations`, `CreateLocation`, `UpdateLocation`, `PatchLocation`, `Location`, `DeleteLocation` |
| `internal/handler/group.go` | 4 | `Groups`, `CreateGroup`, `UpdateGroup`, `DeleteGroup` |
| `internal/handler/metric_preset.go` | 4 | `ListMetricPresets`, `CreateMetricPreset`, `DeleteMetricPreset`, `PatchMetricPreset` |
| `internal/handler/briefing_subscription.go` | 3 | `GetBriefing`, `ListBriefings`, `UpdateBriefing` |
| `internal/handler/weather_config.go` | 2 | `GetLocationWeatherConfig`, `PutLocationWeatherConfig` |

Bereits repariert (#1395 S2): `trip.go` (7 Handler) sowie in `weather_config.go`
die beiden **Trip**-Varianten. Offen bleiben dort die **Orts**-Varianten.

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/store/store.go:16` | `WithUser` — Kopie des Stores mit gesetzter `UserID`; **`userId == ""` gibt `s` unverändert zurück** |
| `internal/handler/trip.go:10-28` | Erklärkommentar aus #1395 S2: warum `:=` und nicht `=`. Vorlage für die Begründung |
| `internal/handler/trip_etag_ifmatch_test.go:390` | `TestUpdateTripHandler_ConcurrentWritesWithoutIfMatch_FileStaysValid` — 12 parallele Goroutinen, Vorbild für den Nachweis |
| `internal/handler/trip_etag_ifmatch_test.go:236` | `TestUpdateTripHandler_TenantIsolation_ETagNotSharedAcrossUsers` — Vorbild für Zwei-Nutzer-Aufbau |
| `internal/handler/user_scoped_test.go` | Bestehende Zwei-Nutzer-Tests (`alice`/`bob`), Hilfsfunktion `addUserToContext` |
| `internal/mail/recipient_parity_test.go` | Einziger vorhandener Ratschen-Test in Go — Vorbild für den Wächter |
| `internal/router/router.go` | Routen-Registrierung; jeder Handler wird **einmal** registriert, die Closure lebt für die Lebensdauer des Prozesses |

## Existing Patterns

Die Codebasis kennt bereits **drei** korrekte Schreibweisen — es muss nichts erfunden werden:

- `s := s.WithUser(middleware.UserIDFromContext(r.Context()))` — 11 Stellen, u.a. `trip.go` (Ergebnis von #1395 S2)
- `us := s.WithUser(userID)` — `cockpit.go:19`, `archive_stats.go:18`
- `s.WithUser(userID).LoadX()` ohne Zwischenvariable — `briefing_history.go:25`

Außerhalb von `internal/handler/` gibt es **keine** Zuweisung an eine geteilte
`WithUser`-Variable. Das Problem ist auf dieses Paket begrenzt.

## Dependencies

- **Upstream:** `middleware.UserIDFromContext` (liefert die Nutzerkennung aus dem Anfrage-Kontext), `store.Store.WithUser`
- **Downstream:** alle Lese-/Schreibwege unter `data/users/<user_id>/` — Orte, Gruppen, Orts-Vergleiche, Metrik-Vorlagen, Briefing-Abos, Wetter-Einstellungen

## Existing Specs

- Kein eigener Spec-Eintrag zum Handler-Muster vorhanden.
- `CLAUDE.md`, Abschnitt „Multi-User-Produkt": Isolation **konsequent** über
  `s.WithUser(middleware.UserIDFromContext(r.Context()))`, **niemals** Rückfall
  auf `"default"`; jeder datenbewegende Endpoint MUSS mit zwei verschiedenen
  Nutzern getestet werden.
- `docs/specs/modules/` — kein Modul-Spec betroffen; die Reparatur ändert kein
  Verhalten und kein Datenschema.

## Baseline (gemessen am 2026-07-31, vor jeder Änderung)

```
go test -race -count=1 ./internal/handler/...
ok  github.com/henemm/gregor-api/internal/handler  29.906s
```

**Grün.** Der Wettlauf-Detektor schweigt heute nicht, weil der Fehler weg wäre,
sondern weil kein Test einen der 25 betroffenen Handler nebenläufig aufruft.
Für die RED-Phase muss dieser Test also erst entstehen.

## Risks & Considerations

1. **Der schlimmere Fall ist kein Wettlauf, sondern deterministisch.**
   `WithUser("")` gibt den Store **unverändert** zurück. Sobald eine Anfrage von
   Nutzer A die geteilte Variable auf A gesetzt hat, bleibt sie dort stehen.
   Eine spätere Anfrage **ohne** Nutzerkennung im Kontext bekommt dann A's Store
   — ohne jede Gleichzeitigkeit. Zu klären in der Analyse: Sind alle betroffenen
   Routen durch die Anmeldeprüfung gedeckt, oder gibt es einen Weg, sie ohne
   Nutzerkennung zu erreichen?

2. **Der Wächter darf nicht am Argument hängen.**
   `compare_preset.go:183` schreibt `s = s.WithUser(userID)` — eine Zwischen-
   variable statt des Aufrufs. Eine Prüfung auf
   `s = s.WithUser(middleware.` würde diese Stelle übersehen. Das Muster ist
   die **Zuweisung an den äußeren Parameter**, nicht die Herkunft des Arguments.

3. **Änderungsbudget.** 25 Einzeltests (einer je Handler) sprengen das Limit von
   250 geänderten Zeilen. Der Nachweis muss über eine gemeinsame, listen-
   getriebene Konstruktion laufen, nicht über 25 Kopien desselben Tests.

4. **Kein Verhaltenswechsel, kein Datenschema.** Die Reparatur ist je Stelle ein
   Zeichen. Es gibt nichts zu migrieren und nichts an Bestandsdaten zu retten —
   die Pflicht „Read-Modify-Write mit Merge" ist hier nicht berührt.

5. **Regressionsrisiko gering, aber nicht null.** Wo im Handler nach der
   Zuweisung noch auf den *äußeren* Store zugegriffen würde, änderte `:=` die
   Bedeutung. In `trip.go` trat das nicht auf; für die 6 verbleibenden Dateien
   ist es je Handler zu prüfen, nicht zu unterstellen.

---

## Analysis

### Type

**Bug** — `priority:critical`. Kein Agent dispatcht: Die Ursache ist bereits
nachgewiesen (Wettlauf-Detektor an konkreter Zeile, #1395 S2), nicht zu
ermitteln. Zu klären war ausschließlich die Bemessung — das ist unten belegt.

### Klärung der offenen Fragen aus dem Kontext

**(1) Ist der deterministische Fall (`WithUser("")`) erreichbar? — Nein.**

- Alle 25 betroffenen Routen liegen hinter `authmw.AuthMiddleware`
  (`internal/router/router.go:37`, global via `r.Use`).
- Keine der Ausnahmen (`/api/health`, `/api/auth/*`, `/api/internal/*`,
  `/api/debug/*`, `/api/webhooks/telegram/*`) registriert einen der betroffenen
  Handler — geprüft, Trefferliste leer.
- `validateSession` (`internal/middleware/auth.go:98`) lehnt eine leere
  Nutzerkennung explizit ab → 401, der Handler wird nie erreicht.

**Folge:** Es bleibt der echte Wettlauf zwischen zwei *angemeldeten* Nutzern.
Der bleibt ein Fehler — aber er braucht zwei gleichzeitige Anfragen
verschiedener Nutzer auf **dieselbe** Route innerhalb weniger Mikrosekunden.
Bei heutigem Nutzungsstand ist die Auslösung unwahrscheinlich; als undefiniertes
Verhalten im Sinne des Go-Speichermodells ist sie trotzdem nicht tolerierbar,
und sie wächst mit jedem weiteren Nutzer.

**(2) Ändert `:=` irgendwo die Sichtbarkeit? — Nein.**

- Alle 25 Stellen stehen auf **zwei Tabs** Einrückung, also unmittelbar im
  Rumpf der zurückgegebenen Closure — nicht in einem `if`/`for`-Block, wo `:=`
  eine blocklokale Variable anlegen und außerhalb still weiterwirken würde.
- Jeder betroffene Handler hat **genau eine** Zuweisung (geprüft je Datei).

Damit ist die Reparatur exakt das, was #1395 S2 in `trip.go` vorgemacht hat.

**(3) Wie beweist man 25 Stellen ohne 25 Tests?** Durch Arbeitsteilung:

| Nachweis | Beweist | Umfang |
|---|---|---|
| Verhaltenstest, listengetrieben, **eine repräsentative Route je Datei** (6) | dass `:=` unter echter Gleichzeitigkeit zweier Nutzer trägt | 6 Einträge, ein Testrumpf |
| Wächter über `internal/handler/` | dass **keine** Stelle vergessen ist und keine neue entsteht | eine Prüfung |

25 Verhaltenstests wären 25 Kopien desselben Beweises. Der Wächter leistet die
Vollständigkeit strukturell — dort gehört sie hin.

### Affected Files (with changes)

| Datei | Change Type | Description |
|---|---|---|
| `internal/handler/compare_preset.go` | MODIFY | 6× `=` → `:=` |
| `internal/handler/location.go` | MODIFY | 6× `=` → `:=` |
| `internal/handler/group.go` | MODIFY | 4× `=` → `:=` |
| `internal/handler/metric_preset.go` | MODIFY | 4× `=` → `:=` |
| `internal/handler/briefing_subscription.go` | MODIFY | 3× `=` → `:=` |
| `internal/handler/weather_config.go` | MODIFY | 2× `=` → `:=` (Orts-Varianten) |
| `internal/handler/store_scope_race_test.go` | CREATE | Zwei-Nutzer-Parallel-Nachweis, listengetrieben |
| `internal/handler/store_scope_guard_test.go` | CREATE | Wächter (Scheibe 2) |

### Scope Assessment

- Dateien: 6 MODIFY + 2 CREATE
- Geschätzte LoC (added+deleted, wie das Gate zählt):
  - Reparatur 25 Zeilen → ~50
  - Erklärverweise in den 6 Dateien → ~30
  - Verhaltenstest → ~160
  - Wächter → ~110
  - **Summe ~350** — über dem Limit von 250
- Risiko: **LOW** für die Reparatur (mechanisch, kein Verhaltenswechsel, kein
  Datenschema, kein Migrationsbedarf), **MEDIUM** für die Aussagekraft des
  Wächters (zu eng gefasst ⇒ falsche Sicherheit, siehe Risiko 2 oben)

### Technical Approach

**Empfehlung: zwei Scheiben — damit entfällt der Bedarf an einer Budget-Ausnahme.**

**S1 — Reparatur + Verhaltensnachweis (~240 LoC)**
1. RED: `store_scope_race_test.go` — je eine Route aus den 6 Dateien, N Goroutinen
   wechselweise als `alice` und `bob`, Prüfung dass jede Antwort zum eigenen
   Nutzer gehört. Muss unter `-race` **rot** werden (Baseline ist grün, weil
   dieser Test heute fehlt — siehe oben).
2. GREEN: 25× `=` → `:=`; je Datei ein Kurzverweis auf den Erklärkommentar in
   `trip.go:10-28`, statt ihn sechsmal zu wiederholen.
3. Nachweis: `go test -race -count=1 ./internal/handler/...` grün.

**S2 — Wächter (~110 LoC)**
Ein Go-Test, der `internal/handler/*.go` über `go/parser`+`go/ast` liest und
jede **Zuweisung** (`=`, nicht `:=`) an einen Bezeichner meldet, der Parameter
der äußeren Funktion ist und innerhalb eines `FuncLit` steht. Bewusst **nicht**
als Textsuche nach `s = s.WithUser(middleware.` — das übersähe
`compare_preset.go:183` (`s = s.WithUser(userID)`) und griffe bei anderem
Variablennamen oder anderer Methode gar nicht. Nach S1 ist er sofort grün und
hält den Stand.

Regel-Budget (CLAUDE.md): S2 ist ein neuer Pflicht-Wächter ⇒ **Prüfdatum
2026-10-29** (+90 Tage) in die Spec.

### Dependencies

- Keine. Weder Reihenfolge-Abhängigkeit zu anderen offenen Issues noch
  Frontend-Beteiligung. Reiner Go-Backend-Eingriff, kein Deploy-Sonderfall.
- Bezug: #1395 (dort gefunden, `trip.go` bereits repariert).

### Open Questions

- [x] Ist der Leerfall erreichbar? → **Nein**, alle Routen sind angemelde-
      pflichtig, leere Kennung wird abgelehnt.
- [x] Ändert `:=` irgendwo die Sichtbarkeit? → **Nein**, alle Stellen im
      Closure-Rumpf, je Handler genau eine.
- [x] Wie ohne 25 Tests beweisen? → Verhalten repräsentativ, Vollständigkeit
      über den Wächter.
- [ ] **Für den PO:** zwei Scheiben (Empfehlung, kein Override nötig) oder ein
      Zug mit Budget-Ausnahme auf 400?
