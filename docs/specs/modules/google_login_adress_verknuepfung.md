---
entity_id: google_login_adress_verknuepfung
type: module
created: 2026-09-15
updated: 2026-09-15
status: draft
version: "1.0"
workflow: fix-2147-c-google-verknuepfung
tags: [security, multi-user, auth, issue-2147, epic-2138]
---

# Google-Login: Verknüpfung statt Doppelkonto (Scheibe C)

## Approval

- [ ] Approved

## Purpose

Schließt den letzten offenen Schreibpfad für Doppel-Adressen (Issue #2147, Scheibe C, letzte
Scheibe nach A/B1/B2): Meldet sich ein unbekannter Google-`sub` mit einer E-Mail-Adresse an, die
bereits einem bestätigten Konto gehört, legt der Handler heute trotzdem ein zweites Konto an. Diese
Spec ersetzt das durch eine kontrollierte Verknüpfung (oder eine neutrale Ablehnung, je nach
Adresslage) und ergänzt einen rein numerischen Kollisionszähler für Bestandsduplikate.

## Source

- **File:** `internal/handler/auth_oauth.go` — **Identifier:** `GoogleOAuthCallbackHandlerWithEndpoints`
  (Callback-Logik Z. 81–239), `createOAuthUser` (Z. 210–239)
- **File:** `internal/store/address_owner.go` — **Identifier:** `NormalizeEmailAddress` (:21),
  `EffectiveContactAddress` (:29), `HasLoginCredentials` (:39), `forEachRealAccount` (:47),
  `ResolveAddressOwner` (:73), `IsAddressTakenByOtherAccount` (:115)
- **File:** `internal/store/address_lock.go` — **Identifier:** `LockEmailAddress` (:17)
- **File:** `internal/store/user.go` — **Identifier:** `FindUserByOAuthSub` (:449–464)

> **Schicht-Hinweis:** Go-API (`internal/handler/`, `internal/store/`, `cmd/server/`) für Callback,
> Verknüpfung, Zähler. Frontend (`frontend/src/routes/login/`) nur für die Fehleranzeige. Kein
> Python-Core betroffen.

## Estimated Scope

- **LoC:** Produktiv ~+180, Tests ~+400 — über dem Standard-Limit, `loc_limit_override 3000` gesetzt (RED-Tests allein erfahrungsgemäß weit über 500 Zeilen, vgl. B2)
  (Auth-Kernpfad, Entscheidungstabelle mit sechs Zweigen, Zwei-Nutzer-/Race-Nachweise je Zweig)
- **Files:** ~8 Produktiv + zugehörige Testdateien + 4 Doku-Dateien
- **Effort:** high (Risk Level HIGH — Auth, Kontozuordnung)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/address_lock.go` → `LockEmailAddress` | Store-Funktion | Prozessweiter Lock je normalisierter Adresse, wie in A/B1/B2 |
| `internal/store/address_owner.go` → `ResolveAddressOwner`, `IsAddressTakenByOtherAccount`, `EffectiveContactAddress`, `HasLoginCredentials`, `NormalizeEmailAddress`, `forEachRealAccount` | Store-Funktionen | Klassifikation der Adresslage, Kollisionszählung |
| `internal/store/user.go` → `FindUserByOAuthSub` | Store-Funktion | Bestandszweig-Erkennung, im Lock erneut aufgerufen (Race-Schutz) |
| `internal/handler/auth.go` → `hasVerifiedEmail`, `issueSession`, `dispatchVerificationMail`/Mail-Versandweg | Handler-Funktionen | Login-Gate (ADR 0066) nach Verknüpfung/Übernahme, Hinweis-Mail über bestehenden Versandweg |
| `docs/specs/modules/magic_link_adress_eindeutigkeit.md` (A) | Spec | Vorbild Übernahme unbestätigt+zugangslos, Out-of-Scope-Verweis auf C |
| `docs/specs/modules/adress_eindeutigkeit_schreibpfade.md` (B1) | Spec | Vorbild Lock+Re-Check-Schreibmuster |
| `docs/specs/modules/adresswechsel_nach_bestaetigung.md` (B2) | Spec | Pending-Adresse ist für Google-Callback unsichtbar (Free) |
| `docs/adr/0066-login-erfordert-bestaetigte-email-adresse.md` | ADR | Login-Gate, den Verknüpfung/Übernahme unverändert durchlaufen |

## Implementation Details

### Ablauf Callback, unbekannter `sub`

```
email_verified == false → oauth_failed (bestehende Sperre auth_oauth.go:150, VOR jeder Adressprüfung,
                          unverändert — gleicher Code für freie und belegte Adressen, kein Enumerations-Kanal)
normalize(email) → LockEmailAddress(normalized)
  → FindUserByOAuthSub(sub) ERNEUT unter Lock
      Treffer → Bestandszweig (unverändert: Login per sub, selfHealEmailVerification)
      kein Treffer → ResolveAddressOwner(normalized) klassifizieren:
        Free (auch: nur PendingContactAddress eines anderen Kontos)
          → createOAuthUser, Email/MailTo NORMALISIERT (nicht mehr roh)
        Owned bestätigt, kein OAuthSub
          → RMW: OAuthProvider/OAuthSub setzen, EmailVerifiedAt unverändert,
            kein ClearSessions, Hinweis-Mail an wirksame Adresse (fail-soft)
        Owned bestätigt, ANDERER OAuthSub bereits gesetzt
          → oauth_link_failed, nichts geschrieben
        Owned unbestätigt + zugangslos
          → frisch laden, Re-Check Zugangsdaten + wirksame Adresse,
            EmailVerifiedAt setzen, OAuthSub setzen, ClearSessions, KEINE Hinweis-Mail
            (es gibt keinen Vorbesitzer, der gewarnt werden müsste — analog Magic-Link A)
        Ambiguous (unbestätigt mit Zugangsdaten / Adresse nur im Nebenfeld / mehrere Inhaber)
          → oauth_link_failed, nichts geschrieben
      Lesefehler beim Scan → oauth_failed (fail-closed), nichts geschrieben
  → unlock
→ hasVerifiedEmail-Gate (ADR 0066) → issueSession
```

Alle inhaltlichen Ablehnungen laufen auf denselben Redirect-Code `oauth_link_failed` — keine
Enumeration, keine Aussage, ob die Adresse existiert. Logs enthalten ausschließlich
IDs-freie Zahlen/Kategorien, nie E-Mail-Adresse oder `user_id`. Das betrifft auch die geteilte
Logzeile für mehrdeutige Adressen in `internal/store/address_owner.go` (heute mit Konto-IDs): die
Zeile bleibt bestehen (Magic-Link-Test verlangt ein nicht-leeres Log), verliert aber die IDs und
nennt nur Anzahl/Kategorie. Einen Fehler des Mailversands nie roh loggen (kann die Adresse enthalten).

### Hinweis-Mail

Über den bestehenden Go-Mail-Versandweg der Auth-Mails (wie die Verifikationsmail in
`internal/handler/auth.go`) — kein neuer Python-Renderer, kein einlösbarer Token/Link. Inhalt
sinngemäß: „Google-Anmeldung wurde mit deinem Konto verknüpft; warst du das nicht, melde dich."
Versandfehler sind fail-soft: eine Logzeile ohne Adresse, Verknüpfung und Login bleiben bestehen.

### Kollisionszähler

Neue Store-Datei (z. B. `internal/store/address_collisions.go`), einmal beim Serverstart nach
`store.New` in `cmd/server/main.go` aufgerufen. Zählt normalisierte Adressen (kreuzweise über
`email`/`mail_to`), die von mehr als einem echten Konto gehalten werden (`forEachRealAccount`,
Testkonten ausgenommen). Loggt ausschließlich Zahlen (Anzahl betroffener Adressen, Anzahl
betroffener Konten) — keine Adressen, keine `user_id`. Fail-soft: ein Scan-Fehler loggt eine
Zeile, der Server startet trotzdem weiter. Nicht im öffentlichen Status-Endpoint. Löst
Bestandsduplikate nicht auf, misst nur.

### Frontend

`frontend/src/routes/login/+page.server.ts` und `+page.svelte` lesen `?error=` und zeigen für
`oauth_link_failed`, `oauth_failed`, `email_not_verified` je einen deutschen, neutralen Text ohne
Aussage über die Existenz der Adresse. Unbekannter Code → keine Meldung bzw. generischer Text.
Kontrast mindestens WCAG-AA.

## Expected Behavior

- **Input:** Google-OAuth-Callback (Userinfo mit `sub`, `email`, `email_verified`) für einen im
  Store noch nicht per `OAuthSub` bekannten Nutzer.
- **Output:** Je nach Adresslage entweder ein neues Konto, eine Verknüpfung mit einem bestehenden
  bestätigten Konto, eine Übernahme eines unbestätigten zugangslosen Kontos, oder ein neutraler
  Redirect `oauth_link_failed`/`oauth_failed` ohne Kontoänderung.
- **Side effects:** ggf. Versand einer Hinweis-Mail (Verknüpfungsfall), ggf. `ClearSessions`
  (Übernahmefall), Start-Log des Kollisionszählers (nur Zahlen).

## Acceptance Criteria

- **AC-1:** Given eine Google-Adresse ohne jeden Kontoinhaber / When ein unbekannter `sub` sich damit anmeldet / Then entsteht ein Neukonto mit normalisierter Email/MailTo.
  Nachweis: Kern (`oauthFakeServers`, `internal/handler/auth_oauth_test.go`)

- **AC-2:** Given die Google-Adresse ist nur als `PendingContactAddress` eines fremden Kontos gespeichert / When der unbekannte `sub` sich anmeldet / Then entsteht ein Neukonto, das fremde Konto bleibt unverändert.
  Nachweis: Kern (Fixture mit Pending-Adresse aus B2, `internal/handler/auth_oauth_test.go`)

- **AC-3:** Given ein bestätigtes Konto ohne `OAuthSub`, dessen wirksame Adresse der Google-Adresse entspricht, Google liefert `email_verified=true` / When der unbekannte `sub` sich anmeldet / Then wird `OAuthProvider/OAuthSub` gesetzt, `EmailVerifiedAt` bleibt unverändert, Sessions des Kontos bleiben bestehen, es entsteht kein Neukonto, eine Hinweis-Mail geht an die wirksame Adresse. Das gilt auch, wenn Google die Adresse in abweichender Groß-/Kleinschreibung oder mit Leerzeichen liefert.
  Nachweis: Kern (`oauthFakeServers`, Zwei-Session-Fixture, eine Variante mit `Foo@…` gegen gespeichertes `foo@…`, `internal/handler/auth_oauth_test.go`)

- **AC-4:** Given der Verknüpfungsfall aus AC-3, der Mailversand schlägt fehl / When der Callback trotzdem verarbeitet wird / Then gelingt der Login dennoch, das Log enthält keine E-Mail-Adresse.
  Nachweis: Kern (Mail-Sender-Stub liefert Fehler, `internal/handler/auth_oauth_test.go`)

- **AC-5:** Given ein bestätigtes Konto mit wirksamer Adresse gleich der Google-Adresse, aber bereits gesetztem ANDEREM `OAuthSub` / When der neue unbekannte `sub` sich mit dieser Adresse anmeldet / Then wird der Callback mit `oauth_link_failed` abgelehnt, das bestehende `OAuthSub` bleibt unverändert.
  Nachweis: Kern (`internal/handler/auth_oauth_test.go`)

- **AC-6:** Given ein unbestätigtes, zugangsloses Konto (kein Passwort, kein Passkey), dessen wirksame Adresse der Google-Adresse entspricht, Google liefert `email_verified=true` / When der unbekannte `sub` sich anmeldet / Then wird das Konto übernommen: `EmailVerifiedAt` gesetzt, `OAuthSub` gesetzt, `ClearSessions` ausgeführt, es geht KEINE Hinweis-Mail hinaus.
  Nachweis: Kern (Vorbild `resolveMagicLinkAccount`-Muster, `internal/handler/auth_oauth_test.go`)

- **AC-7:** Given ein unbestätigtes Konto MIT Zugangsdaten (Passwort oder Passkey), dessen wirksame Adresse der Google-Adresse entspricht / When der unbekannte `sub` sich anmeldet / Then wird der Callback mit `oauth_link_failed` abgelehnt, kein Feld des Kontos wird geschrieben.
  Nachweis: Kern (`internal/handler/auth_oauth_test.go`)

- **AC-8:** Given die Google-Adresse steht nur im Nebenfeld eines bestätigten Kontos (nicht als dessen wirksame Adresse) / When der unbekannte `sub` sich anmeldet / Then wird der Callback mit `oauth_link_failed` abgelehnt, kein Neukonto entsteht.
  Nachweis: Kern (`internal/handler/auth_oauth_test.go`)

- **AC-9:** Given Google liefert `email_verified=false`, einmal für eine freie und einmal für eine belegte Adresse (Owned bestätigt, Owned unbestätigt, Ambiguous) / When der unbekannte `sub` sich anmeldet / Then wird der Callback in ALLEN Fällen mit demselben Code `oauth_failed` abgelehnt (bestehende Sperre vor jeder Adressprüfung), kein Konto wird geschrieben oder verknüpft — der Antwortcode verrät nicht, ob die Adresse im System existiert.
  Nachweis: Kern (`oauthFakeServers`-Variante mit `email_verified=false`, `internal/handler/google_login_address_linking_test.go`; bestehender Test `auth_oauth_test.go:177` bleibt grün)

- **AC-10:** Given ein Lesefehler tritt beim Adress-Scan im Callback auf / When der unbekannte `sub` sich anmeldet / Then wird der Callback fail-closed mit `oauth_failed` abgelehnt, nichts wird geschrieben.
  Nachweis: Kern (echter Store mit einer unlesbaren Kontodatei im Test-Datenverzeichnis — kein Mock, Muster fail-closed aus `magic_link_address_ownership_test.go`, `internal/handler/auth_oauth_test.go`)

- **AC-11:** Given die inhaltlichen Ablehnungsgründe aus AC-5/7/8 / When jeweils der Redirect ausgelöst wird / Then ist der Redirect-Code in allen Fällen identisch `oauth_link_failed`, und das Log enthält weder Adresse noch `user_id`.
  Nachweis: Kern (vergleichender Test über alle vier Ablehnungsfälle, `internal/handler/auth_oauth_test.go`)

- **AC-12:** Given ein bereits bekannter `sub`, dessen Google-Adresse inzwischen einem anderen Konto gehört / When sich dieser `sub` anmeldet / Then läuft der Bestandszweig unverändert (Login per `sub`, `selfHealEmailVerification`), keine Verknüpfungslogik greift.
  Nachweis: Kern (Regressionstest, `internal/handler/auth_oauth_test.go`)

- **AC-13:** Given zwei parallele Callbacks mit gleicher Adresse (Race) / When beide gleichzeitig verarbeitet werden / Then trägt am Ende genau ein Konto die Adresse bzw. existiert der `sub` genau einmal — kein doppelter `sub`, kein Doppelkonto. Bei GLEICHEM `sub` (z. B. Doppelklick) enden beide Callbacks mit demselben Ergebnis wie ein einzelner Callback und keiner mit `oauth_link_failed`: im Verknüpfungsfall beide als Login auf das Inhaberkonto; bei freier Adresse beide am Login-Gate von ADR 0066 (das Neukonto ist noch unbestätigt, daher keine Session).
  Nachweis: Kern (Concurrency-Test mit `LockEmailAddress`, Vorbild `magic_link_address_ownership_test.go`)

- **AC-14:** Given ein Google-Callback läuft parallel zu einer Registrierung mit derselben Adresse / When beide gleichzeitig verarbeitet werden / Then trägt am Ende genau ein Konto die Adresse.
  Nachweis: Kern (Concurrency-Test, Vorbild `address_uniqueness_write_paths_test.go`)

- **AC-15:** Given zwei unterschiedliche Nutzerkonten A und B / When Konto A per Google-Verknüpfung (AC-3) verknüpft wird / Then bleibt Konto B in allen Feldern unverändert, die ausgestellte Session gehört zu Konto A.
  Nachweis: Kern (Zwei-Nutzer-Fixture, `internal/handler/auth_oauth_test.go`)

- **AC-16:** Given ein gemischter Bestand aus realen und Testkonten mit Adress-Duplikaten / When der Kollisionszähler beim Serverstart läuft / Then zählt er ausschließlich reale Konten (`forEachRealAccount`), liefert die korrekte Anzahl betroffener Adressen und Konten (Groß-/Kleinschreibung und `email`/`mail_to` kreuzweise berücksichtigt), gibt nur Zahlen aus, keine Adressen oder `user_id`.
  Nachweis: Kern (`internal/store/address_collisions_test.go`, Log-Ausgabe gegen die Fixture-Adressen geprüft) und Staging (Zähler-Logzeile im Journal von `gregor-api-staging` nach dem Deploy)

- **AC-17:** Given der Kollisionszähler stößt beim Scan auf eine unlesbare Kontodatei / When der Serverstart durchläuft / Then loggt der Zähler eine Fehlerzeile ohne Adresse und der Start bricht nicht ab (kein `log.Fatal`, kein Panic).
  Nachweis: Kern (echter Store mit unlesbarer Kontodatei, `internal/store/address_collisions_test.go`)

- **AC-18:** Given die drei Fehlercodes `oauth_link_failed`, `oauth_failed`, `email_not_verified` als `?error=`-Query-Parameter / When `/login` mit jeweiligem Code aufgerufen wird / Then zeigt die Seite den zugehörigen deutschen, neutralen Text in ausreichendem Kontrast (WCAG-AA), ein unbekannter Code zeigt keine bzw. eine generische Meldung.
  Nachweis: Staging (Browser, `/login?error=oauth_link_failed` etc.) und Kern (Frontend-Test `frontend/src/routes/login/`)

- **AC-19:** Given diese Spec und ADR 0067 sind angelegt / When der ADR-Index und `google_oauth_login.md` geprüft werden / Then ist ADR 0067 in `docs/adr/README.md` verzeichnet und `google_oauth_login.md` markiert die Aussage „kein Account-Linking in v1" an allen drei Stellen (Z. 41, Tabelle Z. 205, Z. 232) ausdrücklich als durch ADR 0067 abgelöst.
  Nachweis: Kern (`tests/test_adr_0067_adress_eindeutigkeit_doku.py` + `tests/test_adr_index_drift.py`)

## Known Limitations

- Ein Google-Workspace-Administrator kann `email_verified=true` für Domain-Adressen ausstellen, die
  er nicht selbst besitzt — akzeptierte Restlücke, gleiche Risikoklasse wie der heutige
  Neuanlagepfad; dokumentiert in ADR 0067.
- Bestandsduplikate (Adressen, die schon vor diesem Fix mehrfach vergeben waren) werden nur
  gemessen (Kollisionszähler), nicht aufgelöst. Auflösung ist eigenes Folge-Ticket, falls die Zahl
  nach Messung > 0 ist.
- Aus B2 bekannte Restlücken bleiben bestehen und gelten als LOW akzeptiert (ADR 0067 + Sammel-Issue
  #1199): Magic-Link sieht `PendingContactAddress` nicht; Seitenkanal-Information über
  `token expired`.
- Echter Google-Login ist auf Staging nicht automatisierbar — alle Callback-ACs sind ausschließlich
  im Kern mit Fake-Google-Servern nachweisbar (`oauthFakeServers`); nur die Fehlertext-Anzeige
  (AC-18) und die Zähler-Logzeile sind auf Staging beobachtbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0067 (neu, in diesem Workflow angelegt)
- **Rationale:** Fasst die vier Adress-Eindeutigkeits-Scheiben A/B1/B2/C zu einer übergreifenden
  Entscheidung „Adress-Eindeutigkeit" zusammen, dokumentiert akzeptierte Restlücken (Workspace-Admin,
  Bestandsduplikate, B2-Seitenkanal) und löst die veraltete Aussage „kein Account-Linking in v1" in
  `docs/specs/modules/google_oauth_login.md` (:41, :232) ab.

## Out of Scope

- Auflösung bestehender Adress-Duplikate im Datenbestand (nur Messung via Kollisionszähler).
- Eine Konto-Oberfläche zum Entkoppeln einer Google-Verknüpfung.
- Ein Feld für den Kollisionszähler im öffentlichen Status-Endpoint (`/api/scheduler/status`).
- Refactoring von `internal/handler/auth_magic.go` (Dopplung von ~15 Zeilen wird bewusst in Kauf
  genommen, da die Datei live und sicherheitskritisch ist).
- Datenmigration von Bestandsdaten (z. B. rückwirkendes Normalisieren roh gespeicherter
  `createOAuthUser`-Adressen).

## Test Plan

- Kern: `internal/handler/auth_oauth_test.go` (alle sechs Entscheidungstabellen-Zweige, Bestandszweig-
  Regression, Ablehnungs-Code-Vergleich, Mail-Fehlerfall, Zwei-Nutzer-Isolation, Race gegen
  Registrierung/parallelen Callback) mit `oauthFakeServers`/`GoogleOAuthCallbackHandlerWithEndpoints`.
- Kern: `internal/store/address_collisions_test.go` (Zählung, Testkonten-Ausschluss, fail-soft bei
  Lesefehler).
- Kern: Frontend-Test für `frontend/src/routes/login/` (drei Fehlertexte, unbekannter Code).
- Kern: `tests/test_adr_index_drift.py` (ADR-Index-Konsistenz für ADR 0067).
- Staging: `/login?error=oauth_link_failed`, `?error=oauth_failed`, `?error=email_not_verified` im
  Browser prüfen; Zähler-Logzeile im Staging-Journal nach Serverstart.

## Changelog

- 2026-09-15: Initial spec created (Scheibe C, Issue #2147)
- 2026-09-15 (nach Freigabe, RED-Befund): AC-9 korrigiert — `email_verified=false` bleibt die bestehende
  Sperre vor jeder Adressprüfung mit `oauth_failed` für freie UND belegte Adressen. Die freigegebene
  Fassung (`oauth_link_failed` nur bei belegter Adresse) hätte über den Antwortcode verraten, ob eine
  Adresse registriert ist, und damit AC-11 widersprochen. Präzisiert: AC-6 ohne Hinweis-Mail, AC-11
  ohne AC-9, AC-13 Doppelklick gleicher `sub` endet in Login, AC-19 drei Fundstellen, Logzeile
  mehrdeutiger Adressen ohne IDs.
