---
entity_id: fix_2151_default_fallbacks_scheibe_b
type: bugfix
created: 2026-09-19
updated: 2026-09-19
status: implemented
workflow: fix-2151-b-go-store-failclosed
issue: 2151
---

# Scheibe B: Go-Store fail-closed bei fehlender Nutzerkennung (#2151)

## Approval

- [x] Approved — PO-Freigabe 2026-09-19

## Purpose

Der Go-Server darf, wie schon Scheibe A auf der Python-Seite, nie still auf das Konto
`"default"` zurückfallen (ADR-0003). Heute passiert das, weil die Konfiguration ohne gesetzte
Umgebungsvariable `GZ_USER_ID` automatisch den Wert `"default"` annimmt und der Basis-Store
diese Kennung anstandslos in Dateipfade einbaut. Diese Scheibe entfernt den Konfigurations-Default,
lässt den Store bei fehlender Nutzerkennung mit einem Fehler abbrechen statt einen Pfad zu bauen
(„fail-closed"), und stellt sicher, dass das Seed-Konto nur noch entsteht, wenn `GZ_USER_ID`
bewusst gesetzt ist. Ein Wächter-Test verhindert, dass künftige Store-Methoden diese Absicherung
vergessen.

## Source

- **File:** `internal/store/pathsafe.go`
- **Identifier:** `func (s *Store) requireUser() error` (neu)

> **Schicht:** Go-API (`internal/store/`, `internal/config/`, `cmd/server/`) — kein Python, kein
> Frontend in dieser Scheibe.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0003 (Multi-Tenant-Isolation) | ADR | Grundsatz: kein `"default"`-Rückfall in authentifiziertem Pfad |
| `internal/store/pathsafe.go` (`ValidUserID`, `ErrInvalidUserID`) | Bestandscode | Liefert bereits die Prüf-Logik; diese Scheibe nutzt sie zentral über `requireUser()` |
| `docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md` | Spec (PO-freigegeben) | PO-Entscheid „`default` bleibt gültiger Kontoname" gilt unverändert; diese Scheibe setzt nur den Rückfall-Stopp auf Go-Seite um |
| `docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md:125-130` | Spec | Dokumentiert `WithUser("")` als No-Op — bleibt so, nur die Prämisse „Basis-Store trägt echte Kennung" ändert sich (siehe Implementation Details Punkt 5) |
| `internal/handler/store_scope_guard_test.go` | Bestandscode | Erzwingt bereits heute, dass Handler `s.WithUser(middleware.UserIDFromContext(...))` verwenden — Beleg, dass kein Produktivpfad direkt auf dem Basis-Store nutzerbezogene Methoden aufruft |
| `frontend/e2e/ci-stack.sh:66` | Bestandscode | Einzige Stelle, die `GZ_USER_ID=admin` setzt (aus `ci.yml:372`) — lebender Beleg für AC-2 (Seed-Anlage bei gesetzter Kennung) |
| Scheibe A (vorgelagert, Python) | Vorgänger-Scheibe | Hat den analogen Rückfall in Python-Sende-/Lesepfaden bereits entfernt; diese Scheibe überträgt das Prinzip auf Go |
| Scheibe C (Folge-Workflow, Python) | Folgearbeit | Restliche Signatur-Defaults in `src/` — unabhängig von dieser Scheibe |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `internal/store/pathsafe.go` | MODIFY | Neue zentrale Prüfung `requireUser()` |
| `internal/store/location.go` | MODIFY | Guard am Anfang jeder error-liefernden, nutzerbezogenen Methode |
| `internal/store/metric_preset.go` | MODIFY | Guard, u.a. `SaveMetricPresets` |
| `internal/store/group.go` | MODIFY | Guard, u.a. `SaveGroup`/`DeleteGroup` |
| `internal/store/briefing_subscription.go` | MODIFY | Guard an nutzerbezogenen Methoden |
| `internal/store/trip.go` | MODIFY | Guard an nutzerbezogenen Methoden |
| `internal/store/compare_preset.go` | MODIFY | Guard, u.a. `SaveComparePresets` |
| `internal/store/briefing_fingerprint.go` | MODIFY | Guard an nutzerbezogenen Methoden |
| `internal/store/log.go` | MODIFY | Guard an `LoadBriefingLog`/`LoadAlertLog` und den Zähl-Methoden, die deren Fehler ein zweites Mal schlucken |
| `internal/store/store.go` | MODIFY | Kommentar zu `WithUser("")` nachziehen (Basis-Kennung ist jetzt leer statt „default") |
| `internal/store/user.go:308-309` | MODIFY | Kommentar nachziehen |
| `internal/config/config.go` | MODIFY | `default:"default"` am Feld `UserID` entfernen |
| `internal/config/config_test.go:28-29` | MODIFY | Erwartungswert von `"default"` auf leer umstellen |
| `cmd/server/main.go` | MODIFY | `seedAdminUser(s, cfg)` extrahieren; Seed nur bei gesetzter Kennung, Fehler wird geloggt statt verschluckt |
| `cmd/server/main_test.go` | MODIFY | Tests für die neue Seed-Logik (gesetzt/leer/Fehlschlag) |
| `internal/handler/data_export.go:19-24` | MODIFY | Kommentar nachziehen (Begründung nannte bisher den Config-Default) |
| `internal/handler/data_export_test.go:403-408` | MODIFY | Kommentar nachziehen |
| `internal/store/user_scope_guard_test.go` | CREATE | Reflection-Register-Wächter über alle exportierten `*Store`-Methoden |

**Nicht angefasst, mit Begründung:** `premium_sms_link_code.go`, `premium_sms_connect.go`,
`preview_proxy.go` — deren Kommentare beziehen sich nicht auf den entfallenden Config-Default und
brauchen keine Änderung. `internal/store/location.go` (`LocationsDir`), `metric_preset.go`
(`PresetsFile`), `briefing_subscription.go` (`briefingsDir`/`BriefingsDir`), `group.go`
(`groupsFile`) — diese Helfer liefern keinen Fehler zurück und bleiben unverändert (siehe
Implementation Details Punkt 1); sie werden im Wächter-Register als „exempt" mit Begründung
eingetragen, nicht umgebaut. `internal/store/briefing_lock.go` (`LockBriefing`) — baut keinen
Dateipfad, sondern nur einen In-Memory-Sperrschlüssel; „exempt". `cmd/migrate2154/main.go:19` —
Einmal-Migrationswerkzeug, Kennung dort produktiv ungenutzt (nur `ListUserIDs`/`LoadUser`/
`SaveUser` mit expliziter Kennung als Parameter). `internal/handler/cockpit.go`,
`archive_stats.go` — verschlucken Store-Fehler weiterhin, aber nur mit Auth erreichbar; Nacharbeit
im Sammel-Issue #1199.

### Estimated Changes
- Files: ~16 (davon 1 neue Testdatei)
- LoC: +245/-30 (grob), `loc_limit_override 500` gesetzt — der Wächter-Test wird bewusst nicht
  eingespart, obwohl er den größten Teil der LoC ausmacht

## Implementation Details

**1. Zentrale Prüfung `requireUser()`.** In `pathsafe.go` entsteht `func (s *Store) requireUser()
error`, das `ValidUserID(s.UserID)` prüft und sonst `ErrInvalidUserID` liefert. Jede
error-liefernde Store-Methode, die direkt oder transitiv einen Dateipfad aus `s.UserID` baut,
ruft `requireUser()` als erste Zeile. Die vier Helfer ohne Fehler-Rückgabe (`LocationsDir`,
`PresetsFile`, `briefingsDir`/`BriefingsDir`, `groupsFile`) bleiben unverändert — sie werden nie
direkt von außerhalb des Stores mit einer leeren Kennung aufgerufen (nur in 9 Handler-Testdateien
mit gesetzter Kennung), eine Signaturänderung würde unnötigen Test-Fan-out erzeugen. Wichtiger
Grund gegen eine Änderung an dieser Stelle: Methoden wie `LoadLocations`, `LoadTrips` oder
`LoadComparePresets` schlucken heute schon Fehler ihres internen Verzeichnis-Lesevorgangs und
liefern bei einem Problem „leere Liste, kein Fehler" zurück — ein Fehler aus dem Helfer würde dort
unsichtbar bleiben. Deshalb liegt die Absicherung bewusst am Anfang der aufrufenden,
error-liefernden Methode.

**2. Wächter gegen künftige Lücken.** `internal/store/user_scope_guard_test.go` führt ein
Verzeichnis (eine Liste im Test-Code), in dem jede exportierte Methode von `*Store` entweder als
„guarded" oder als „exempt mit Begründung" eingetragen sein muss. Der Test prüft „guarded"
Methoden per Reflection einzeln: Aufruf auf einem frisch mit `New(dir, "")` erzeugten Store muss
einen Fehler liefern, UND es darf danach keine Datei direkt unter `dir/users/` entstanden sein
(außerhalb eines konkreten Nutzerordners). Jede Methode wird für sich geprüft — die Annahme „ein
Lese-Guard deckt automatisch die zugehörige Schreib-Methode mit ab" wird damit gemessen, nicht nur
behauptet. Eine neue exportierte Methode ohne Eintrag im Verzeichnis lässt den Test fehlschlagen.

**3. Seed-Logik.** `seedAdminUser(s *store.Store, cfg *config.Config) error` wird aus `main()`
herausgezogen. Die Reihenfolge der Prüfung ist bewusst: zuerst `cfg.UserID != ""`, dann
`cfg.AuthPass != ""`, dann „Konto existiert noch nicht". Nur wenn alle drei zutreffen, wird
`SaveUser` aufgerufen. Der Rückgabewert von `SaveUser` wird geprüft: bei Erfolg wird „Seed user
'<id>' created" geloggt, bei einem Fehler wird der Fehler geloggt (kein Absturz des Servers, kein
„created" in der Logzeile). Das Bestandskonto `users/default/` auf Prod/Staging bleibt davon
unberührt, weil es schon existiert und die Existenzprüfung entsprechend früh greift.

**4. Konfiguration.** Das Feld `UserID` in `internal/config/config.go` verliert die
Tag-Angabe `default:"default"`. Ohne gesetzte Umgebungsvariable `GZ_USER_ID` ist `cfg.UserID`
danach ein leerer Text statt des Werts `"default"`.

**5. Bewusst nicht angefasst.** `WithUser("")` bleibt ein No-Op, wie in
`fix_2140_pfad_traversal_nutzer_kennung.md:125-130` beschrieben — an dieser Festlegung ändert sich
nichts. Was sich ändert, ist die Prämisse dahinter: Diese Spec dort ging davon aus, dass der
Basis-Store (vor einem `WithUser`-Aufruf) eine echte Kennung („default") trägt. Nach dieser
Scheibe trägt der Basis-Store eine leere Kennung, und `requireUser()` verweigert genau deshalb
jeden nutzerbezogenen Dateizugriff darauf. `LockBriefing` bleibt unverändert, weil es keinen
Dateipfad baut, sondern nur einen In-Memory-Sperrschlüssel, und produktiv immer erst nach einem
`WithUser`-Aufruf erreicht wird. `cmd/migrate2154` bleibt bei `"default"` stehen, weil die Kennung
dort für die genutzten Methoden (`ListUserIDs`, `LoadUser`, `SaveUser` mit expliziter Kennung als
Parameter) bedeutungslos ist. Die verschluckten Fehler in `cockpit.go`/`archive_stats.go` bleiben
offen, weil beide Handler nur mit gültiger Authentifizierung erreichbar sind — Nacharbeit läuft
über das Sammel-Issue #1199.

## Test Plan

Alle Tests sind Go-Tests (`t.TempDir()` + echter `store.New(dir, "")`/`New(dir, "admin")`),
ohne Mocks — es wird die tatsächliche Dateisystem-Wirkung geprüft (Fehler-Rückgabe UND Abwesenheit
einer Datei), nicht nur ein Rückgabewert isoliert. Tests werden nach Verhalten benannt.

| Test | Datei | Prüft |
|------|-------|-------|
| `TestSeedSkippedWithoutUserID` | `cmd/server/main_test.go` | AC-1 |
| `TestSeedCreatesAccountWhenUserIDSet` | `cmd/server/main_test.go` | AC-2 |
| `TestSeedFailureIsLoggedNotFatal` | `cmd/server/main_test.go` | AC-3 |
| `TestConfigUserIDDefaultsEmpty` | `internal/config/config_test.go` | AC-4 |
| `TestGuardedMethodsRejectEmptyUserID` | `internal/store/user_scope_guard_test.go` | AC-5 |
| `TestGuardedMethodsCreateNoFileOutsideUserDir` | `internal/store/user_scope_guard_test.go` | AC-5 |
| `TestNewExportedMethodWithoutRegisterEntryFails` (Mutations-Fixture) | `internal/store/user_scope_guard_test.go` | AC-6 |
| `TestStoreMethodsUnchangedForRealUser` | `internal/store/*_test.go` (bestehende Handler-/Store-Tests) | AC-7 |
| `TestSchedulerRunsWithEmptyBaseUserID` | `cmd/server/main_test.go` bzw. bestehender Scheduler-Test | AC-8 |

### Mutations-Gegenprobe (PFLICHT)

Nach Implementierung wird testweise ein einzelner `requireUser()`-Aufruf aus genau einer
Store-Methode entfernt (z. B. `SaveGroup` in `group.go`), außerhalb des Produktivcodes gesichert.
Der Wächter-Test `user_scope_guard_test.go` muss danach für **genau diese eine Methode** rot
werden — nicht für eine andere, nicht pauschal für das ganze Paket. Wird der Test bei dieser
gezielten Verfälschung nicht rot, ist der Wächter ein Finding (bewacht die Zusicherung nicht dort,
wo sie wirkt). Die Sicherungskopie wird danach zurückgespielt, kein `git checkout`/`stash`/`reset`.

**Nachtrag (Adversary, 2026-09-19):** `SaveGroup`/`DeleteGroup` (`group.go`) tragen zwar jeweils
einen eigenen direkten `requireUser()`-Aufruf, rufen intern aber zusätzlich `LoadGroups()` auf —
das selbst ebenfalls einen eigenen Guard trägt. Entfernt man testweise nur den direkten Aufruf in
`SaveGroup`/`DeleteGroup`, bleibt der Zugriff über den transitiven Guard in `LoadGroups()` trotzdem
verweigert: Der Wächter-Test wird zwar weiterhin für diese Methoden rot, aber die gezielte
Mutations-Gegenprobe zeigt dabei nicht, ob speziell der direkte Aufruf wirkt oder der transitive.
Das ist keine Schutzlücke — beide Wege verweigern korrekt —, aber für eine trennscharfe
Gegenprobe (F001, siehe Changelog) ungeeignet; mit PO-OK als gleichwertig akzeptiert. Für künftige
Mutations-Proben ist deshalb `SaveComparePreset` (Singular, `compare_preset.go`) das bessere
Referenzbeispiel — die Methode schreibt direkt über `briefingsDir()`/`writeFileLogged`, ohne
einen weiteren, selbst gegen `requireUser()` geprüften Lese- oder Schreib-Aufruf dazwischen.
Die Plural-Variante `SaveComparePresets` eignet sich dagegen NICHT als sauberes Beispiel, da
sie intern wieder `SaveComparePreset` aufruft und damit denselben Doppel-Guard-Effekt wie
`SaveGroup`/`DeleteGroup` hätte.

### Staging-Nachweis

Nach Deploy auf Staging wird der Startlog des Go-Dienstes (`gregor-api-staging`) geprüft: keine
Logzeile „Seed user '' created". Anschließend Login mit einem echten Testkonto und Abruf der
Trip-Liste — beide funktionieren unverändert (Beleg für AC-7/AC-8).

## Acceptance Criteria

- **AC-1:** Given der Server startet ohne gesetzte Umgebungsvariable `GZ_USER_ID`, aber mit gesetztem Anmelde-Passwort `GZ_AUTH_PASS` / When der Server hochfährt / Then wird kein neues Konto angelegt, es erscheint keine Logzeile „Seed user '' created", und ein bereits vorhandener Ordner `users/default/` bleibt unverändert.
- **AC-2:** Given die Umgebungsvariable `GZ_USER_ID` ist gesetzt (zum Beispiel `admin`, wie im Test-Aufbau der automatischen Prüfungen) und das entsprechende Konto existiert noch nicht / When der Server hochfährt / Then wird das Konto angelegt und die Logzeile „created" erscheint.
- **AC-3:** Given das Anlegen des Kontos schlägt aus einem technischen Grund fehl / When der Server hochfährt / Then wird der Fehler protokolliert, es wird nicht fälschlich „created" gemeldet, und der Server startet trotzdem vollständig weiter statt abzustürzen.
- **AC-4:** Given die Konfiguration wird ohne gesetzte Umgebungsvariable `GZ_USER_ID` geladen / When der Wert der Nutzerkennung ausgelesen wird / Then ist die Nutzerkennung ein leerer Text und nicht mehr automatisch der Wert „default".
- **AC-5:** Given ein Datenzugriffs-Objekt (Store) ohne gesetzte Nutzerkennung / When irgendeine nutzerbezogene Lese- oder Schreibfunktion darauf aufgerufen wird (zum Beispiel Gruppen speichern, Gruppen löschen, Vergleichs-Voreinstellungen speichern) / Then liefert die Funktion einen Fehler „ungültige Nutzerkennung" zurück und es entsteht keine Datei direkt unter dem Nutzer-Datenordner außerhalb eines konkreten Nutzer-Unterordners (zum Beispiel keine Datei `users/groups.json` oder `users/locations/…`).
- **AC-6:** Given im Code wird eine neue öffentlich aufrufbare Datenzugriffs-Funktion ergänzt, ohne sie in der Prüfliste des Wächter-Tests einzutragen / When der Wächter-Test läuft / Then schlägt genau dieser Test fehl und macht die fehlende Einordnung sichtbar.
- **AC-7:** Given ein angemeldeter Nutzer, auch das Bestandskonto „default" / When er wie bisher auf seine eigenen Daten zugreift (Trips, Orte, Gruppen, Voreinstellungen) / Then verhält sich der Zugriff exakt wie vor dieser Änderung — keine neuen Fehler, keine geänderten Ergebnisse.
- **AC-8:** Given der geplante Hintergrund-Versand (Scheduler) und der Programmstart / When beide mit der jetzt leeren Basis-Nutzerkennung laufen / Then funktionieren sie unverändert weiter, weil sie die Nutzerkennung ausschließlich aus den vorhandenen Nutzer-Ordnernamen ableiten und nie die leere Basis-Kennung selbst für einen Datenzugriff verwenden.

## Known Limitations

- Die vier Helfer ohne Fehler-Rückgabe (`LocationsDir`, `PresetsFile`, `briefingsDir`/
  `BriefingsDir`, `groupsFile`) werden nicht umgebaut und bleiben „exempt" im Wächter-Register —
  sie sind produktiv außerhalb des Stores nie mit leerer Kennung erreichbar, nur in Handler-Tests
  mit gesetzter Kennung.
- Die verschluckten Fehler in `internal/handler/cockpit.go` und `archive_stats.go` werden hier
  nicht behoben — beide Handler sind nur mit gültiger Authentifizierung erreichbar. Nacharbeit im
  Sammel-Issue #1199.
- `cmd/migrate2154/main.go` behält den hart codierten Wert `"default"` als Store-Kennung; das ist
  fachlich folgenlos, weil das Migrationswerkzeug ausschließlich Methoden mit expliziter Kennung
  als Parameter nutzt.
- Ob Prod/Staging `GZ_USER_ID` heute bereits gesetzt haben, ist nicht aus dem Repository ablesbar
  (Umgebungsdateien liegen nicht im Repo) — das Verhalten ist in beiden Fällen korrekt, nur der
  Seed-Logeintrag unterscheidet sich; wird beim Staging-Nachweis am Startlog gemessen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (Multi-Tenant-Isolation, bestehend)
- **Rationale:** Diese Scheibe überträgt den in Scheibe A für Python bereits umgesetzten
  Grundsatz auf die Go-Seite: kein automatischer Rückfall auf eine implizite Kennung bei fehlender
  Identität. Sie widerspricht nicht dem PO-Entscheid aus Scheibe A, dass `"default"` als
  expliziter, bewusst vergebener Kontoname gültig bleibt — hier geht es ausschließlich um den
  stillen, unbeabsichtigten Rückfall auf diesen Wert. Kein neues ADR nötig.

## Changelog

- 2026-09-19: Initial spec created (Scheibe B von #2151, Analyse aus
  `docs/context/fix-2151-b-go-store-failclosed.md`)
- 2026-09-19: Implementiert. Adversary-Verdict **AMBIGUOUS**, vom PO abgenommen:
  - **F001** (gleichwertige Mutation): `SaveGroup`/`DeleteGroup` tragen zwar einen eigenen
    direkten `requireUser()`-Aufruf, rufen intern aber zusätzlich das ebenfalls gegen
    `requireUser()` geprüfte `LoadGroups()` auf. Entfernt man testweise nur den direkten Aufruf,
    bleibt der Zugriff trotzdem über den transitiven Guard in `LoadGroups()` verweigert — die
    gezielte Mutations-Gegenprobe zeigt dort also nicht trennscharf, ob speziell der direkte
    Aufruf wirkt. PO-OK: als gleichwertig (keine Schutzlücke) akzeptiert, kein Nachzug nötig.
    Sauberes Referenzbeispiel ohne diesen Doppel-Guard-Effekt für künftige Proben:
    `SaveComparePreset` (Singular).
  - **F002:** behoben.

  Details: `docs/context/fix-2151-b-go-store-failclosed.md`.
