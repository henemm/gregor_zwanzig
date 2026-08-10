# Context: fix-1517-validator-register-order

## Request Summary

Issue #1517: Der Staging-Validator-Nutzer (`data/users/validator-issue110/user.json`) hatte
weder `id` noch `password_hash` — Login strukturell unmöglich, `scripts/setup-validator-user.sh`
scheitert seit #1226 still. Ursache lokalisiert: `RegisterHandler` prüft das seit #1226
pflichtige `email`-Feld VOR der Existenz-Prüfung des Usernamens. Ein idempotenter
Register-Aufruf ohne `email` gegen einen bereits existierenden Nutzer liefert dadurch
**400 "validation failed"** statt der von `setup-validator-user.sh` erwarteten **409 "user
already exists"** — der Login-Verifikationspfad des Scripts wird nie erreicht.

Scope dieses Workflows: NUR der `gregor_zwanzig`-Anteil (Reihenfolge-Fix + Regressionstest).
Der zweite Issue-Punkt (`henemm-infra/scripts/sync-staging-validator-creds.sh` fehlt
App-Layer-Passwort-Sync) liegt in einem anderen Repo/Zuständigkeitsbereich — per MQ an die
`infra`-Instanz gemeldet (Nachricht 61815), nicht Teil dieses Workflows.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/auth.go` | `RegisterHandler` (Zeile 30-107): Validierungsreihenfolge — `email`-Pflichtprüfung (Zeile 64-70, #1226) sitzt vor `s.UserExists` (Zeile 76) |
| `internal/handler/auth_test.go` | Bestehende Tests zu `RegisterHandler`; `TestRegisterHandlerDuplicateUser` (Zeile 82) sendet immer ein `email`-Feld — die Lücke (existierender User OHNE email) ist unbelegt |
| `scripts/setup-validator-user.sh` | Sendet beim Register-Call nie `email` (Zeile 20-22) — bewusst so belassen (Script ist reiner Konsument, Reihenfolge-Fix reicht) |

## Existing Patterns

- Alle anderen 400-Validierungen in `RegisterHandler` (Username-Länge, Regex, Passwort-Länge,
  Zeile 39-59) laufen ebenfalls VOR der Existenz-Prüfung — die #1226-E-Mail-Prüfung reiht sich
  nur unglücklich in dieselbe Reihenfolge ein. Die Korrektur ist NICHT „alle Validierungen nach
  hinten schieben" (würde User-Enumeration über Fehlercode-Timing/-Text ermöglichen, siehe
  Risks), sondern gezielt die Existenz-Prüfung VOR die E-Mail-Pflichtprüfung ziehen.
- `s.UserExists(req.Username)` (Zeile 76) ist bereits die kanonische Existenzprüfung, die
  reine Format-Validierungen (Username-Länge/-Regex, Passwort-Länge) nutzt sie aktuell NICHT
  vorgeschaltet — nur E-Mail soll das betreffen, weil das der einzige Fall ist, der einen
  belegten Idempotenz-Bruch verursacht (#1517).

## Dependencies

- `store.Store.UserExists` — unverändert, wird nur früher aufgerufen
- Keine Migration nötig (reine Handler-Logik, kein Datenmodell-Wechsel)

## Risks & Considerations

- **User-Enumeration:** Existenzprüfung vor Format-Validierung heißt: ein Angreifer kann durch
  Weglassen der E-Mail herausfinden, ob ein Username existiert (409 statt 400). Das ist bereits
  heute der Fall für gültige, vollständige Requests (409 bei Duplikat ist ohnehin sichtbar) —
  die Änderung verschiebt die Grenze nur für den E-Mail-Check, kein neues Informationsleck
  gegenüber dem Status quo (Username-Länge/-Regex/Passwort-Länge bleiben VOR der
  Existenzprüfung, dort ist das Verhalten unverändert).
- **Reihenfolge NICHT einfach umdrehen (alle Checks nach UserExists):** würde
  `TestRegisterHandlerShortUsername`/`TestRegisterHandlerShortPassword` (400 erwartet)
  brechen, wenn zufällig ein bereits vergebener Username mit ungültigem Passwort kommt — bewusst
  NICHT im Scope, nur die E-Mail-Prüfung wandert.
- Bug-Nachweis-Pflicht (Testpolitik): Kern-Test reproduziert das Symptom aus Nutzersicht
  (Register ohne email gegen existierenden User → muss 409 sein, nicht 400) — rot vor Fix, grün
  danach.

## Analysis

### Type
Bug

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `internal/handler/auth.go` | MODIFY | `s.UserExists`-Prüfung (aktuell Zeile 76) vor die E-Mail-Pflichtprüfung (aktuell Zeile 64-70) ziehen; bei Treffer weiterhin 409 |
| `internal/handler/auth_test.go` | MODIFY | Neuer Test: existierender User, Register-Request OHNE `email` → 409 (nicht 400) |

### Scope Assessment
- Files: 2
- Estimated LoC: ~10 (Produktivcode, reine Umstellung) + ~25 (Test)
- Risk Level: LOW (lokale Reihenfolgeänderung in einem Handler, keine neuen Abhängigkeiten, kein Datenmodell-Wechsel)

### Technical Approach
In `RegisterHandler` die `s.UserExists(req.Username)`-Prüfung direkt nach den reinen
Format-Validierungen (Username-Länge/-Regex, Passwort-Länge) und VOR die E-Mail-Pflichtprüfung
ziehen. Bei existierendem User weiterhin 409 zurückgeben, sonst wie bisher weiter zur
E-Mail-Prüfung. Kein Eingriff an `dispatchVerificationMail`, `s.SaveUser`, `s.ProvisionUserDirs`.

### Dependencies
Keine neuen. `store.Store.UserExists` bleibt unverändert (nur früherer Aufrufzeitpunkt).

### Open Questions
Keine.
