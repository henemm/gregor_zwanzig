---
entity_id: fix_2140_pfad_traversal_nutzer_kennung
type: bug
created: 2026-09-06
updated: 2026-09-06
status: draft
version: "1.0"
tags: [security, path-traversal, multi-tenant, auth]
---

# Pfad-Traversal-Sperre für Nutzer-Kennungen (Scheibe 1 von 2)

## Approval

- [x] Approved — PO-Freigabe 2026-09-06

## Purpose

Die vier öffentlichen Auth-Routen (`login`, `password-forgot`, `password-reset`, `verify-email`)
reichen die vom Client gesetzte Nutzer-Kennung (`username`/`user`) ungeprüft an
`Store.UserDir(id)` durch, das sie roh mit `filepath.Join` verbindet. Weil `filepath.Join`
`..`-Sequenzen normalisiert, kann eine Kennung wie `../marker` oder `../bob/x` aus dem eigenen
Nutzerverzeichnis ausbrechen. Laufzeit-Nachweis am unveränderten Stand: `POST
/api/password-forgot` mit `username="../marker"` antwortet **200** und schreibt einen
Passwort-Reset-Token **außerhalb** des Nutzerbaums (Log: „token written but not sent"). Existiert
das Zielverzeichnis eines echten zweiten Nutzers, schreibt derselbe Mechanismus in dessen
Verzeichnis hinein — bis zum Überschreiben von dessen `user.json`, wonach das fremde Konto nicht
mehr anmeldbar ist.

Diese Spec schließt die Lücke für die Nutzer-Achse (Achse A): eine kanonische Go-Prüfung am
Pfadbau in `internal/store` plus flächengerechte Ablehnung an den vier öffentlichen Routen, ohne
das bestehende Antwortverhalten (insbesondere den Enumerationsschutz von `password-forgot`) zu
verändern.

## Source

- **File:** `internal/store/pathsafe.go` (NEU)
- **Identifier:** `ValidUserIDRe`, `ValidUserID()`
- **File:** `internal/store/user.go`
- **Identifier:** `LoadUser`, `SaveUser`, `DeleteUser`, `ProvisionUserDirs`, `SaveResetToken`,
  `LoadResetToken`, `DeleteResetToken`, `SaveVerificationToken`, `LoadVerificationToken`,
  `DeleteVerificationToken`, `UserExists`
- **File:** `internal/store/sessions.go`
- **Identifier:** `LoadSessions`, `HasSession`, `AddSession`, `RemoveSession`, `ClearSessions`
- **File:** `internal/handler/auth.go`
- **Identifier:** `LoginHandler`, `ForgotPasswordHandler`, `ResetPasswordHandler`,
  `VerifyEmailHandler`
- **File:** `internal/handler/passkey.go`
- **Identifier:** `validUsernameRe`
- **File:** `tests/unit/test_user_id_pattern_parity.py`
- **Identifier:** `test_python_muster_ist_deckungsgleich_mit_go` (Bestand, `# doc-compliance-test`)

**Schicht:** Go-API (`internal/store`, `internal/handler`) plus der bestehende
Python↔Go-Paritätstest in `tests/unit/`, der auf die verschobene Go-Quelle umgehängt wird.

## Estimated Scope

- **LoC:** ~105 produktiv, ~115 Tests (~220 gesamt)
- **Files:** 8 (2 neu, 6 geändert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/middleware.UserIDFromContext` | go function | Liefert die Session-Nutzer-ID (Achse C, HMAC-signiertes Cookie) — bleibt in dieser Spec unangetastet |
| `src/app/loader.VALID_USER_ID_RE` | python constant | Referenzmuster, gegen das der bestehende Paritätstest `ValidUserIDRe` abgleicht |
| ADR-0003 | adr | Konsequente Mandantentrennung, Zwei-Nutzer-Pflichttest — diese Spec setzt sie auf der Go-Seite durch |
| `internal/handler/passkey.go::validUsernameRe` | go var | Bisherige alleinige Quelle des Musters; wird auf `store.ValidUserIDRe` umgehängt statt verdoppelt |

## Implementation Details

1. **`internal/store/pathsafe.go` (neu)** — kanonische Go-Quelle des Musters:
   ```go
   var ValidUserIDRe = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

   func ValidUserID(id string) bool {
       return ValidUserIDRe.MatchString(id)
   }
   ```
   Importzyklusfrei: `handler` importiert `store`, `store` importiert `handler` nicht.

2. **`internal/store/user.go`** — jede der 11 Methoden prüft `ValidUserID(id)` (bzw. den
   jeweiligen ID-Parameter) als erste Anweisung, vor jedem `filepath.Join`/`os.MkdirAll`/
   `os.ReadFile`/`os.RemoveAll`. Alle betroffenen Methoden geben bereits `error` zurück — **keine
   Signaturänderung**. `UserExists` gibt `bool` zurück und liefert bei ungültiger Kennung schlicht
   `false`, ohne `os.Stat` aufzurufen. `DeleteUser` ist die schärfste Stelle (`os.RemoveAll`,
   `user.go:172`) — ohne Prüfung würde eine Traversal-Kennung dort ein fremdes Verzeichnis löschen.

3. **`internal/store/sessions.go`** — `sessionsPath(userId)` (`:41`) ist die gemeinsame Engstelle
   für alle fünf Einstiege (`LoadSessions`, `HasSession`, `AddSession`, `RemoveSession`,
   `ClearSessions`); die Prüfung sitzt dort einmal, nicht fünfmal dupliziert. `HasSession` liefert
   bei ungültiger `userId` `(false, error)` statt `(false, nil)` — bewusst unterscheidbar vom
   „Kennung ist syntaktisch gültig, aber es gibt keine Session"-Fall, damit der Aufrufer eine
   Traversal-Kennung nicht mit einer schlicht abgemeldeten Sitzung verwechseln kann.

4. **`internal/handler/auth.go`** — an allen vier öffentlichen Routen eine explizite
   Vorprüfung, **bevor** der erste Store-Aufruf erfolgt (Schicht 1 in `internal/store` hält
   bereits, diese Schicht dient der lesbaren Absicht und der flächengerechten Antwort):
   - `LoginHandler` (`:148`): `req.Username` gegen `store.ValidUserID` prüfen → bei Fehltreffer
     identisch zum bestehenden „Nutzer nicht gefunden"-Zweig antworten: 401
     `{"error":"invalid credentials"}`.
   - `ForgotPasswordHandler` (`:217`): bei Fehltreffer **200** `{"status":"ok"}`, sofort
     zurückkehren — identischer Code- und Antwortpfad wie der bestehende
     „`user == nil`"-Zweig (`:233`), damit der Enumerationsschutz der Route erhalten bleibt.
   - `ResetPasswordHandler` (`:322`): bei Fehltreffer 400 `{"error":"invalid token"}` — identisch
     zum bestehenden Zweig bei fehlendem/ungültigem Reset-Token.
   - `VerifyEmailHandler` (`:403`): bei Fehltreffer 400 `{"error":"invalid token"}` — identisch
     zum bestehenden Zweig bei fehlendem/ungültigem Verifikations-Token.
   - Bei jeder abgelehnten Kennung zusätzlich ein serverseitiger `log.Printf`-Eintrag (Route +
     abgelehnte Kennung, **nicht** im Response-Body) — analog zum bestehenden
     `log.Printf("login: user.json unreadable/corrupt for %s: %v", ...)`-Muster (`:160`).

5. **`internal/handler/passkey.go:23`** — `validUsernameRe` wird zu `store.ValidUserIDRe`
   umgehängt (kein eigenes Regex-Literal mehr). Die beiden Aufrufstellen `auth.go:46`
   (`RegisterHandler`) und `passkey.go:462` bleiben unverändert, da sie bereits über den Namen
   `validUsernameRe` auf das Paket-Level-Var zugreifen.

6. **`tests/unit/test_user_id_pattern_parity.py`** — `_PASSKEY_GO` zeigt künftig auf
   `internal/store/pathsafe.go`, die Regex-Suche im Test auf den Variablennamen
   `ValidUserIDRe\s*=\s*regexp\.MustCompile`. Dieser Test wird beim reinen Verschieben des
   Musters zwischenzeitlich rot (Variable existiert noch nicht in `pathsafe.go`) — das ist
   erwartet und gehört als solches ins RED-Artefakt, nicht als „vorbestehend rot" verbucht.

**Achse C wird nicht angefasst:** `s.UserID` stammt ausschließlich aus dem HMAC-signierten
Session-Cookie (`internal/middleware/auth.go:74,86,98`), ist nicht client-steuerbar und damit
kein offener Vektor. `WithUser("")` ist ein dokumentierter No-op (`store.go:16-19`) — dort ergänzt
diese Spec lediglich einen klarstellenden Kommentar, dass der leere String bewusst NICHT über
`ValidUserID` läuft (er würde sonst fälschlich als „ungültig" statt als „No-op" behandelt und
bestehendes Verhalten kippen).

## Expected Behavior

- **Input:** Client-gesetzte Nutzer-Kennung in `username` (Login, Forgot, Reset) bzw. `user`
  (Verify-Email) im JSON-Request-Body der vier öffentlichen Auth-Routen.
- **Output:** Für eine Kennung, die nicht `^[a-zA-Z0-9_-]+$` entspricht, antwortet jede Route mit
  demselben Statuscode und Body, den sie heute bereits für „Nutzer/Token existiert nicht" liefert
  (siehe Implementation Details Punkt 4) — kein neuer Statuscode, keine neue Fehlerform. Für eine
  gültige Kennung ändert sich nichts am bestehenden Verhalten.
- **Side effects:** Bei ungültiger Kennung entsteht **keine** Datei-, Verzeichnis- oder
  Lösch-Operation außerhalb bzw. innerhalb irgendeines Nutzerverzeichnisses — insbesondere kein
  Reset-Token, kein Verifikations-Token, keine Session-Datei. Zusätzlich ein Log-Eintrag
  serverseitig.

## Acceptance Criteria

- **AC-1:** Given eine Pfad-Traversal-Kennung wie `../marker` im `username`-Feld / When `POST
  /api/auth/login` damit aufgerufen wird / Then antwortet die Route mit 401
  `{"error":"invalid credentials"}` — demselben Body wie bei einem schlicht unbekannten Nutzer.
  - Test: `POST /api/auth/login` mit `{"username":"../marker","password":"x"}`; Statuscode und
    Response-Body mit dem Aufruf für einen garantiert unbekannten, aber syntaktisch gültigen
    Nutzernamen vergleichen — beide identisch.

- **AC-2:** Given ein real registrierter Nutzer mit korrektem Passwort / When `POST
  /api/auth/login` aufgerufen wird / Then meldet sich der Nutzer weiterhin erfolgreich an
  (Positivkontrolle).
  - Test: Test-Nutzer anlegen, `POST /api/auth/login` mit dessen echten Zugangsdaten aufrufen,
    200 und Session-Cookie prüfen.

- **AC-3:** Given eine Pfad-Traversal-Kennung wie `../marker` im `username`-Feld / When `POST
  /api/password-forgot` damit aufgerufen wird / Then antwortet die Route mit 200
  `{"status":"ok"}`, und es entsteht **keine** `password_reset.json` außerhalb des
  Nutzerverzeichnis-Baums (Kern des Laufzeit-Nachweises: heute landet dort ein Token).
  - Test: `POST /api/password-forgot` mit `{"username":"../marker"}`; danach das Dateisystem
    oberhalb von `data/users/` nach einer neu entstandenen `password_reset.json` durchsuchen —
    keine gefunden.

- **AC-4:** Given eine Pfad-Traversal-Kennung UND eine syntaktisch gültige, aber unbekannte
  Kennung / When beide nacheinander gegen `POST /api/password-forgot` aufgerufen werden / Then
  sind Statuscode und Response-Body für beide Fälle identisch — die Route bleibt gegen
  Konto-Enumeration ununterscheidbar.
  - Test: Zwei Aufrufe von `POST /api/password-forgot`, einmal mit `"../marker"`, einmal mit
    `"garantiert-unbekannt-xyz"`; beide Antworten byte-genau vergleichen.

- **AC-5:** Given ein real registrierter Nutzer mit hinterlegter E-Mail-Adresse / When `POST
  /api/password-forgot` mit dessen echter Kennung aufgerufen wird / Then wird für ihn weiterhin
  ein Reset-Token geschrieben (Positivkontrolle).
  - Test: Test-Nutzer mit `MailTo`/`Email` anlegen, `POST /api/password-forgot` mit dessen
    Kennung aufrufen, danach `password_reset.json` im eigenen Nutzerverzeichnis vorfinden.

- **AC-6:** Given eine Pfad-Traversal-Kennung im `username`-Feld / When `POST
  /api/password-reset` damit aufgerufen wird / Then antwortet die Route mit 400
  `{"error":"invalid token"}`, und kein `PasswordHash` irgendeines Nutzers wird verändert.
  - Test: `POST /api/password-reset` mit `{"username":"../bob","token":"x","new_password":"12345678"}`;
    Statuscode/Body prüfen und den `PasswordHash` in Bobs `user.json` vor/nach dem Aufruf
    byte-genau vergleichen.

- **AC-7:** Given ein real registrierter Nutzer mit gültigem, ungelaufenem Reset-Token / When
  `POST /api/password-reset` mit dessen echter Kennung und dem passenden Token aufgerufen wird /
  Then wird das Passwort weiterhin erfolgreich zurückgesetzt (Positivkontrolle).
  - Test: Reset-Token für einen Test-Nutzer erzeugen, `POST /api/password-reset` mit korrekten
    Werten aufrufen, 200 erhalten und den neuen Login mit dem neuen Passwort erfolgreich
    durchführen.

- **AC-8:** Given eine Pfad-Traversal-Kennung im `user`-Feld / When `POST /api/verify-email`
  damit aufgerufen wird / Then antwortet die Route mit 400 `{"error":"invalid token"}`, und
  `EmailVerifiedAt` keines Nutzers wird gesetzt.
  - Test: `POST /api/verify-email` mit `{"user":"../bob","token":"x"}`; Statuscode/Body prüfen
    und Bobs `user.json` vor/nach byte-genau vergleichen.

- **AC-9:** Given ein real registrierter Nutzer mit gültigem, ungelaufenem
    Verifikations-Token / When `POST /api/verify-email` mit dessen echter Kennung und dem
    passenden Token aufgerufen wird / Then wird `EmailVerifiedAt` weiterhin gesetzt
    (Positivkontrolle).
  - Test: Verifikations-Token für einen Test-Nutzer erzeugen, `POST /api/verify-email` mit
    korrekten Werten aufrufen, 200 erhalten und `EmailVerifiedAt` im neu geladenen Nutzerobjekt
    gesetzt vorfinden.

- **AC-10:** Given zwei real angelegte Nutzer / When gegen den ersten Nutzer ein
    Traversal-Angriff über `password-forgot` mit einer auf das Verzeichnis des zweiten Nutzers
    zielenden Kennung (`../users/<zweiter-nutzer>` — trifft das Verzeichnis des realen zweiten
    Nutzers; das kürzere `../<zweiter-nutzer>` landet dagegen neben `users/` und ist als
    eigenständiger Ausbruch-aus-dem-Baum-Fall ebenfalls abgedeckt) gefahren wird / Then bleibt das Verzeichnis
    des zweiten Nutzers byte-identisch (Inhalt und Änderungszeit jeder Datei unverändert) — der
    Zwei-Nutzer-Nachweis nach ADR-0003.
  - Test: `internal/store/pathsafe_test.go`, zwei Test-Nutzer `alice`/`bob` anlegen, Inhalt und
    `mtime` von Bobs `user.json` vor dem Angriff sichern, `POST /api/password-forgot` mit
    `{"username":"../bob"}` aufrufen, danach Inhalt und `mtime` erneut lesen und vergleichen.

- **AC-11:** Given eine Pfad-Traversal-Kennung wie `../bob` / When `Store.LoadUser`,
    `Store.SaveUser` oder `Store.DeleteUser` direkt mit dieser Kennung aufgerufen werden / Then
    liefert jeder Aufruf einen Fehler, und es entsteht/verändert/verschwindet keine Datei
    außerhalb des Verzeichnisses der aufrufenden Kennung.
  - Test: `internal/store/pathsafe_test.go`, drei Aufrufe (`LoadUser`, `SaveUser`, `DeleteUser`)
    mit `"../bob"`; jeweils `err != nil` prüfen und danach Bobs realen Nutzerordner unverändert
    vorfinden.

- **AC-12:** Given eine Pfad-Traversal-`userId` wie `../bob` / When `Store.AddSession`,
    `Store.RemoveSession`, `Store.HasSession` oder `Store.ClearSessions` direkt damit aufgerufen
    werden / Then liefern sie einen Fehler (`HasSession`: `(false, error)`), und es entsteht
    keine `sessions.json` außerhalb des Nutzerverzeichnis-Baums.
  - Test: `internal/store/pathsafe_test.go`, alle vier Methoden mit `"../bob"` aufrufen; Fehler
    prüfen und das Dateisystem oberhalb von `data/users/` nach einer neuen `sessions.json`
    durchsuchen — keine gefunden.

- **AC-13:** Given die real im Bestand vorkommenden Nutzer-Kennungen (`default`, `henning`,
    `steffi`, `validator-issue110`) / When sie gegen `store.ValidUserID` geprüft werden / Then
    liefert jede `true` — der Bestand bleibt vollständig funktionsfähig.
  - Test: `internal/store/pathsafe_test.go`, `store.ValidUserID` für jede der vier Kennungen
    aufrufen und `true` erwarten.

- **AC-14:** Given der bestehende Python↔Go-Paritätstest / When er nach dem Umzug des Musters
    auf `internal/store/pathsafe.go` läuft / Then bleibt er grün — `VALID_USER_ID_RE` (Python)
    und `ValidUserIDRe` (Go, `pathsafe.go`) sind weiterhin deckungsgleich.
  - Test: `tests/unit/test_user_id_pattern_parity.py::test_python_muster_ist_deckungsgleich_mit_go`
    (Bestand, `# doc-compliance-test`, Pfad/Variablenname umgehängt).

- **AC-15:** Given eine der vier öffentlichen Auth-Routen wird mit einer ungültigen Kennung
    aufgerufen / When die Anfrage verarbeitet wird / Then entsteht serverseitig ein Log-Eintrag,
    der die Ablehnung und die Route erkennen lässt — unabhängig vom (unveränderten)
    Response-Body.
  - Test: `internal/handler/auth_traversal_test.go`, Log-Output (z.B. via `log.SetOutput` auf
    einen `bytes.Buffer`) während eines Aufrufs mit `"../marker"` einfangen und auf einen
    Treffer für die abgelehnte Kennung prüfen.

## Known Limitations

- **Scheibe 2 (Entitäts-IDs) ist bewusst nachgelagert.** Trip-, Location-, ComparePreset- und
  Briefing-IDs (Achse B) bleiben in dieser Spec ungeprüft und folgen in einem eigenen Vorgang.
  Begründung: Scheibe 2 trägt ein Bestandsdaten-Regressionsrisiko, das Scheibe 1 nicht hat — im
  Prod-Bestand liegen sechs Orte mit Diakritika (`pollença`, `hochfügen`, `mühlbach` u.a.), für
  die ein zu strenges Muster (wie es das Ticket wörtlich für „alle IDs" verlangt) den
  Editier-/Lösch-Zugriff des PO stillschweigend brechen würde; die richtige Regel dafür ist eine
  Pfadsegment-Prüfung statt des Nutzer-Kennung-Musters und braucht einen eigenen
  Regressionstest. Zusätzlich setzt Achse B ein angemeldetes Konto voraus, während die vier
  Routen dieser Spec die einzige Fläche sind, die ganz ohne Anmeldung erreichbar ist — die
  dringlichere Fläche zuerst.
- Die Reaktion des Frontends auf eine neue Ablehnung wurde nicht untersucht — für die vier
  betroffenen Routen ändert sich weder Statuscode noch Response-Form gegenüber dem bestehenden
  „Nutzer/Token unbekannt"-Zweig, ein Frontend-Effekt ist daher nicht zu erwarten, wurde aber
  nicht durch UI-Tests belegt.
- `internal/router` (Weiterleitung an den Python-Kern) wurde nicht daraufhin angesehen, ob dort
  Nutzer-Kennungen in URLs zusammengebaut werden, die von dieser Prüfung nicht erfasst wären.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (Konsequente Mandantentrennung, kein `"default"`-Fallback)
- **Rationale:** Diese Spec trifft keine neue Grundsatzentscheidung, sondern setzt eine bereits
  getroffene (ADR-0003: Isolation pro Nutzer unter `data/users/<user_id>/`, Pflicht zum
  Zwei-Nutzer-Test) auf einem bislang übersehenen Pfad durch — der Go-Seite fehlte die
  zentrale Pfad-Absicherung, die die Python-Seite seit #1364 bereits kennt (`app.loader.get_data_dir`).
  Ein eigenes ADR ist nicht nötig, weil weder eine neue Alternative abgewogen noch eine
  bestehende Entscheidung geändert wird.

## Changelog

- 2026-09-06: Initial spec (Issue #2140, Scheibe 1 von 2)
