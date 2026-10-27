# Context: fix-2140-pfad-traversal-id-validierung

## Request Summary

Issue #2140 (priority:critical, Blocker, Teil von Epic #2138 Multi-User-Readiness): Client-gesetzte
Entitäts-IDs (Trip, Ort, ComparePreset, Briefing) und Benutzernamen auf öffentlichen Auth-Routen
gehen ungeprüft in `filepath.Join(...)` der Go-Seite. Weil `filepath.Join` `..`-Sequenzen
normalisiert, kann eine ID wie `../../bob/user` aus dem eigenen Nutzerverzeichnis ausbrechen und in
fremden Verzeichnissen lesen oder schreiben — bis hin zum Überschreiben von `bob`s `user.json`
(Ziel endet immer auf `.json`), wonach das fremde Konto nicht mehr anmeldbar ist.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/store/user.go:45` | `UserDir(id)` joint die Nutzer-Kennung roh — Wurzel aller nutzerbezogenen Pfade |
| `internal/store/user.go:49,78,101,105,121,142,146` | `LoadUser`, `SaveUser`, Reset-/Verification-Token-Pfade über `UserDir(id)` |
| `internal/store/sessions.go:41` | Session-Datei über `UserDir(userId)` |
| `internal/store/trip.go:258` | `SaveTrip`: `filepath.Join(dir, trip.ID+".json")` — Schreib-Pfad mit Client-ID |
| `internal/store/trip.go:176,263` | `LoadTrip`/`DeleteTrip` über `briefingsDir()` + `id` |
| `internal/store/location.go:91` | `SaveLocation`: `filepath.Join(dir, loc.ID+".json")` |
| `internal/store/location.go:62,95` | `LoadLocation`/`DeleteLocation` |
| `internal/store/compare_preset.go:214` | `SaveComparePreset`: Schreib-Pfad mit Client-ID |
| `internal/store/compare_preset.go:140,241` | Load/Delete-Pendants |
| `internal/store/briefing_subscription.go:64` | `SaveBriefing`: Schreib-Pfad mit Client-ID |
| `internal/store/briefing_subscription.go:32` | Load-Pendant |
| `internal/store/briefing_fingerprint.go:28` | Liest über `briefingsDir()` + `id` |
| `internal/handler/trip.go:180` | `CreateTripHandler` → `SaveTrip`, ID aus Request-Body, `validateTrip` prüft nur Leerstring |
| `internal/handler/location.go:107,160` | Location-Anlage/Update mit Client-ID |
| `internal/handler/auth.go:46` | Registrierung prüft bereits `validUsernameRe` — Login/Forgot/Reset/Verify NICHT |
| `internal/handler/passkey.go:23` | `validUsernameRe = ^[a-zA-Z0-9_-]+$` — vorhandenes Muster, kanonische Go-Quelle |
| `internal/handler/group.go:203` | Weiterer `SaveLocation`-Aufrufer (Dependent, oft übersehen) |
| `internal/handler/weather_config.go:111,186` | Weitere `SaveTrip`/`SaveLocation`-Aufrufer |
| `internal/handler/compare_preset.go:271,521,616` | Weitere `SaveComparePreset`-Aufrufer |
| `internal/handler/briefing_subscription.go:276` | Weiterer `SaveComparePreset`-Aufrufer |
| `src/app/loader.py:1150,1165` | Python-Vorbild: `VALID_USER_ID_RE`, erzwungen zentral in `get_data_dir()` |
| `tests/unit/test_user_id_pattern_parity.py` | Bestehender Paritäts-Test Python↔Go (`# doc-compliance-test`) |

## Existing Patterns

- **Zentrale Durchsetzung am Pfadbau (Python, Vorbild):** `app.loader.get_data_dir()` wirft
  `ValueError` bei einer Kennung, die nicht auf `^[a-zA-Z0-9_-]+$` passt — laut Kommentar bewusst
  „zentral hier, damit alle Aufrufer gedeckt sind". Historie: #1352 (am GPX-Endpoint praktisch
  vorgeführt) → #1364 (zentrale Prüfung). **Die Go-Seite hat diesen Schritt nie bekommen.**
- **Muster-Parität ist bereits geregelt:** `tests/unit/test_user_id_pattern_parity.py` hält
  `VALID_USER_ID_RE` (Python) und `validUsernameRe` (Go, `passkey.go`) deckungsgleich. Ein neues
  Go-Regex-Literal an anderer Stelle würde diese Paritäts-Kette still umgehen — der Fix sollte
  `validUsernameRe` wiederverwenden bzw. eine gemeinsame Go-Quelle etablieren, nicht ein zweites
  Literal einführen.
- **Handler-Fehlerform:** Handler nutzen `bailIf(w, cond, http.StatusBadRequest, "…")`-Muster
  (z.B. `briefing_subscription.go:276`) — neue 400er sollten sich daran anlehnen.
- **Store-Scoping:** `Store` trägt `UserID`; Verzeichnis-Helfer (`LocationsDir()`, `briefingsDir()`,
  `UserDir(id)`) sind die Engstellen, durch die praktisch jeder Pfad läuft.

## Dependencies

- **Upstream:** `internal/model` (Entity-Structs mit `ID`-Feld), `internal/middleware`
  (`UserIDFromContext`), JSON-Decoding der Request-Bodies in den Handlern.
- **Downstream:** Alle Handler, die `Save*`/`Load*`/`Delete*` des Stores aufrufen — mehr als im
  Ticket aufgezählt: zusätzlich `group.go`, `weather_config.go`, `compare_preset.go`,
  `briefing_subscription.go`. Ebenso der Scheduler und der Proxy zum Python-Core, die über
  denselben Store gehen.

## Existing Specs

- `docs/adr/0003-multi-tenant-isolation.md` — konsequente Mandantentrennung, kein `"default"`-Fallback;
  fordert Zwei-Nutzer-Isolationstest, `"default"`-Fallback im authentifizierten Pfad ist Blocker
- `docs/specs/modules/issue_1352_gpx_user_isolation.md` — der direkte Präzedenzfall auf der Python-Seite
- `docs/specs/modules/user_scoped_store.md` — nutzerbezogene Store-Schnittstelle
- `docs/specs/modules/user_auth_endpoints.md` — Auth-Routen (Login/Reset/Verify)
- `docs/specs/modules/passkey_webauthn.md` — Herkunft von `validUsernameRe`

## Risks & Considerations

- **Nur-Handler-Fix greift zu kurz:** Es gibt deutlich mehr Store-Aufrufer als die im Ticket
  genannten. Wird nur am Handler-Eingang geprüft, öffnet der nächste neue Aufrufer die Lücke erneut.
  Die Prüfung gehört an die Wirkstelle (Pfadbau im Store), analog zum Python-Vorbild.
- **Bestandsdaten:** Existieren real bereits IDs, die dem Muster nicht entsprechen (z.B. mit Punkt
  oder Leerzeichen), würde eine harte Store-Prüfung sie unlesbar machen. Vor der Implementierung ist
  der Ist-Bestand unter `data/users/` (und Prod: `/var/lib/gregor`) zu prüfen — sonst droht ein
  stiller Datenverlust-Effekt statt eines Sicherheitsgewinns.
- **Regex-Dopplung:** Ein neues Literal in `internal/store` würde am bestehenden Paritäts-Test
  (`test_user_id_pattern_parity.py`, liest gezielt `passkey.go`) vorbeilaufen. Entweder gemeinsame
  Go-Konstante oder Paritäts-Test mitziehen.
- **Öffentliche Routen sind der heikelste Teil:** Login/Forgot/Reset/Verify sind ohne Anmeldung
  erreichbar; dort entscheidet die Prüfung, ob ein Unangemeldeter überhaupt einen Pfad beeinflussen
  kann. Reihenfolge zwingend: validieren **vor** jedem `Load*`/`Save*`.
- **Fehlerform darf nichts verraten:** Bei Forgot-Password/Login darf die neue Ablehnung keine
  Aussage über Existenz eines Kontos erzeugen (User-Enumeration) — dieselbe generische Antwort wie
  bisher.
- **Kein Laufzeit-Nachweis im Ticket:** Der Befund ist am Code eindeutig, wurde aber laut Issue nie
  laufend reproduziert (Go-Toolchain in der Audit-Sitzung nicht ladbar). Ein reproduzierender Test
  (RED) ist deshalb Teil des Nachweises, nicht Kür.

---

# Analysis

## Type

**Bug** — Sicherheitsdefekt (Pfad-Traversal), priority:critical, Blocker.

## Laufzeit-Nachweis (erbracht — schließt die Lücke des Tickets)

Go 1.25.0 liegt unter `/usr/local/go/bin/go` (nicht im PATH — daher die Fehlannahme
„Toolchain nicht verfügbar"). `go build ./internal/...` läuft grün. Ein Testlauf gegen den
**unveränderten** Stand zeigt den Traversal real:

| Aufruf | Beobachtet |
|---|---|
| `POST /api/trips` mit `id="../../bob/briefings/bobs-trip"` | **201 Created** — Trip landet in Bobs Verzeichnis |
| `POST /api/password-forgot` mit `username="../marker"` | **200** + Log „token written but not sent" — Reset-Token außerhalb geschrieben |
| `POST /api/locations` / `POST /api/trips` mit `id="../../bob/evil"` | 500 `store_error` — **nur** weil Bobs Verzeichnis im Testaufbau fehlte; existiert der fremde Nutzer, greift der Angriff durch |

Damit ist der Befund nicht mehr nur hergeleitet, sondern gemessen.

## Drei Achsen — eine davon ist entwarnt

| Achse | Wert kommt aus | Client-steuerbar | Konsequenz |
|---|---|---|---|
| **A — Nutzer-Kennung** | Request-Body der öffentlichen Auth-Routen | **ja, roh** | absichern |
| **B — Entitäts-ID** | Body oder URL-Parameter | **ja, roh** | absichern |
| **C — `s.UserID`** | `WithUser(middleware.UserIDFromContext(...))` | **nein** — HMAC-signiertes Cookie (`internal/middleware/auth.go:74,86,98`) | **nicht anfassen** |

Achse C umfasst 8 rohe `s.UserID`-Joins, die an `UserDir()` vorbeilaufen
(`briefing_subscription.go:20`, `location.go:15`, `group.go:15,135`, `metric_preset.go:15,131`,
`log.go:24,64`). Sie sind kein offener Vektor. Zusätzlich: `WithUser("")` ist ein dokumentierter
No-op (`store.go:15-22`) — eine Prüfung dort würde Bestandsverhalten kippen.

## 🔴 Zentrale Korrektur an der Ticket-Vorgabe

Das Ticket verlangt **ein** Muster `^[a-zA-Z0-9_-]+$` für alle IDs. **Das würde produktive Daten
des PO unbrauchbar machen.** Im Prod-Bestand (`/var/lib/gregor/users/henning/locations/`) liegen
sechs Orte mit Diakritika: `pollença`, `hochfügen`, `mühlbach`, `übergangsjoch-zillertal-arena`,
`berstation-hochfügen`, `serfaus-schöngamp-berg`. Mit dem strengen Muster wären sie per
`PUT`/`DELETE /api/locations/{id}` nicht mehr editier- oder löschbar — und der Ausfall wäre
**still**, weil `LoadLocations` das Verzeichnis scannt (`location.go:21`) statt IDs zu joinen.

**Deshalb zwei Regeln statt einer:**

| Fläche | Regel | Begründung |
|---|---|---|
| Nutzer-IDs | `^[a-zA-Z0-9_-]+$` | Python-Parität (`src/app/loader.py:1150`), Bestand vollständig konform (`default`, `henning`, `steffi`, `validator-issue110`), Generatoren erzeugen nur Sauberes |
| Entitäts-IDs | Pfadsegment-Regel: nicht leer, nicht `.`/`..`, kein `/`, kein `\`, kein NUL, kein führender Punkt, ≤128 Zeichen | blockt jede Traversal, lässt `pollença` unangetastet |

Der führende Punkt ist ausgeschlossen, weil `writeFileAtomic` Temp-Dateien als
`"."+Base+".tmp-*"` anlegt (`internal/store/write.go:37`) — Namensraum-Kollision.

## Affected Files (with changes)

### Scheibe 1 — Nutzer-Achse + öffentliche Auth-Routen

| File | Change Type | Description |
|---|---|---|
| `internal/store/pathsafe.go` | CREATE | `ValidUserIDRe`, `ValidUserID()` — kanonische Go-Quelle des Musters |
| `internal/store/user.go` | MODIFY | 11 Methoden prüfen die Kennung vor dem Pfadbau (alle geben bereits `error` zurück — keine Signaturänderung) |
| `internal/store/sessions.go` | MODIFY | 5 Einstiege (`LoadSessions`, `HasSession`, `AddSession`, `RemoveSession`, `ClearSessions`) |
| `internal/handler/auth.go` | MODIFY | 4 öffentliche Routen: flächengerechte Ablehnung vor jedem Store-Zugriff |
| `internal/handler/passkey.go` | MODIFY | `validUsernameRe` zieht die Konstante aus `store` — **kein zweites Literal** |
| `internal/handler/auth_traversal_test.go` | CREATE | Ablehnung je Route + Nachweis, dass die Fremddatei unberührt bleibt |
| `internal/store/pathsafe_test.go` | CREATE | Store-Ebene, Zwei-Nutzer-Isolation (ADR-0003) |
| `tests/unit/test_user_id_pattern_parity.py` | MODIFY | Pfad + Variablenname auf `pathsafe.go` umhängen |

### Scheibe 2 — Entitäts-Achse

| File | Change Type | Description |
|---|---|---|
| `internal/store/pathsafe.go` | MODIFY | `ValidEntityID()` (Pfadsegment-Regel) ergänzen |
| `internal/store/trip.go` · `location.go` · `compare_preset.go` · `briefing_subscription.go` | MODIFY | je 3 Methoden (Load/Save/Delete) |
| `internal/store/briefing_fingerprint.go` | MODIFY | 1 Lesemethode |
| `internal/handler/location.go` | MODIFY | Prüfung **nach** `toKebab` (`:70`), sonst rutscht die leere Auto-ID durch |
| Traversal-Tests je Entitätstyp | CREATE | 4 Typen |
| Regressionstest Umlaut-Ort | CREATE | `pollença` muss speicher- und löschbar bleiben |

## Scope Assessment

- **Scheibe 1:** ~105 LoC produktiv + ~115 LoC Tests = **~220** → unter dem Limit 250
- **Scheibe 2:** ~59 LoC produktiv + ~85 LoC Tests = **~144** → unter dem Limit 250
- In einem Workflow: ~364 LoC → Override auf 500 nötig
- **Risk Level: HIGH** (Auth-Fläche, Multi-User-Isolation, Bestandsdaten-Regressionsrisiko in S2)

## Technical Approach

**Zwei Schichten, zwei Muster, zwei Scheiben.**

1. **Tragende Schicht: die öffentlichen Store-Methoden.** Alle betroffenen Methoden geben bereits
   `error` zurück — die Prüfung kostet keine einzige Signaturänderung. Das folgt dem Python-Vorbild
   (`src/app/loader.py:1165`: „Zentral hier, damit alle Aufrufer gedeckt sind"), das die Lehre aus
   #1352/#1364 trägt.
2. **Zweite Schicht: Handler-Vorprüfung nur auf den vier öffentlichen Auth-Routen** — nicht wegen
   der Sicherheit (Schicht 1 hält), sondern damit die Ablehnung flächengerecht antwortet und die
   Absicht im Code lesbar bleibt.
3. **Konstanten in `internal/store/pathsafe.go`** — importzyklusfrei (`handler` → `store` → `model`,
   `store` importiert `handler` nicht), von `handler` und `middleware` nutzbar.

**Fehlerantwort — bewusst NICHT einheitlich.** Eine ungültige ID wird exakt so behandelt wie
„diesen Nutzer gibt es nicht", kein neuer Statuscode, kein neuer Antwortpfad:

| Route | Antwort |
|---|---|
| `POST /api/auth/login` | 401 `{"error":"invalid credentials"}` — identischer Body wie heute |
| `POST /api/password-forgot` | **200 `{"status":"ok"}`, still abbrechen** — die Route antwortet heute bewusst immer 200 gegen Konto-Enumeration (`auth.go:231`); ein unterscheidbarer zweiter Antwortpfad wäre eine Härtungs-Regression |
| `POST /api/password-reset` | 400 `{"error":"invalid token"}` |
| `POST /api/verify-email` | 400 `{"error":"invalid token"}` |
| authentifizierte Entitäts-Endpunkte | 400 `{"error":"validation failed"}` — Nutzer ist angemeldet, es gibt nichts zu enumerieren |

**Verworfen (mit Begründung):** `writeFileLogged` als tragende Sperre (sieht die ID nicht mehr,
deckt weder Lese- noch Löschpfade — insbesondere nicht `os.RemoveAll` in `DeleteUser:172` — und
kein `os.MkdirAll`); `UserDir()` auf `(string, error)` umbauen (12 Aufrufer, deckt trotzdem nur
Achse A); ein zweites Regex-Literal in Go (liefe an der Paritätskette vorbei).

## Dependencies

- **Upstream:** `internal/model`, `internal/middleware` (Session-Auflösung), JSON-Decoding in den Handlern
- **Downstream:** alle Store-Aufrufer — über das Ticket hinaus auch `group.go:203`,
  `weather_config.go:111,186`, `compare_preset.go:271,521,616`, `briefing_subscription.go:276`;
  Scheduler nur über `tier_request_health.go:36` (`uid` stammt aus `os.ReadDir`, nicht vom Client)
- **Reihenfolge:** S1 zuerst — einzige Fläche ohne Anmeldung. S2 danach, weil sie das
  Bestandsdaten-Regressionsrisiko trägt und ein angemeldetes Konto voraussetzt.

## Geprüft und für unkritisch befunden

- `alert_state/` und `compare_weather_snapshots/` tragen krumme Namen (Doppelpunkte, Umlaute),
  werden aber **ausschließlich vom Python-Kern** geschrieben — Go fasst sie nicht an
- Bestehende Go-Tests: keine krummen ID-Literale gefunden
- `LockBriefing`/`lockSessions` sind In-Memory, kein Pfadbau
- `toKebab("❄️")` → `""` erzeugt heute eine Datei namens `.json` — bereits jetzt defekt; die neue
  Regel macht daraus ein sauberes 400

## Open Questions

- [ ] Keine für den PO. Die einzige echte Weggabelung — striktes Muster (Ticket-Wortlaut) vs.
      Pfadsegment-Regel für Entitäts-IDs — ist durch den Prod-Bestand entschieden: der Ticket-Wortlaut
      würde sechs Orte des PO unbrauchbar machen und ist damit keine Option.
- [ ] Offen für die Spec (technisch, in S2 zu klären): Reaktion des Frontends auf ein neues 400 bei
      `PUT`/`DELETE /api/locations/{id}`; Weiterleitung an den Python-Kern (`internal/router`) wurde
      nicht daraufhin angesehen, ob dort IDs in URLs zusammengebaut werden.
