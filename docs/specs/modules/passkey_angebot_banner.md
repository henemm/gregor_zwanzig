---
entity_id: passkey_angebot_banner
type: module
created: 2026-09-12
updated: 2026-09-12
status: draft
version: "1.0"
tags: [passkey, login, profil]
---

# Passkey-Angebot-Banner

## Approval

- [x] Approved (PO, 2026-09-12)

## Purpose

Wer sich mit Passwort anmeldet und noch keinen Passkey hinterlegt hat, bekommt einmalig das
Angebot, jetzt einen einzurichten. Das Angebot ist abweisbar über „Nicht jetzt"; die Abweisung
gilt geräteübergreifend, weil sie serverseitig im Nutzerprofil vermerkt wird, nicht im
Gerätespeicher. Wer bereits einen Passkey hat, sieht das Angebot nie.

## Source

- **File:** `frontend/src/routes/+layout.svelte`, `frontend/src/routes/login/+page.server.ts`,
  `internal/model/user.go`, `internal/handler/auth.go`
- **Identifier:** `passkeyAngebotFaellig`, `toProfileResponse`, `UpdateProfileHandler`

## Estimated Scope

- **LoC:** ~100-140
- **Files:** 7 (5 produktiv + Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| passkey_login_anordnung | module | Liefert `isWebAuthnSupported()` und `registerPasskey(label)` aus `frontend/src/lib/passkey.ts`, die dieses Modul wiederverwendet |
| user.go (PremiumSmsReplyAt) | reference-pattern | Vorbild für ein schlichtes `bool`-Feld mit `omitempty` neben bestehenden Profil-Feldern |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/user.go` | MODIFY | Neues Feld `PasskeyPromptDismissed bool` mit `omitempty`, JSON-Name `passkey_prompt_dismissed`, neben `PremiumSmsReplyAt` |
| `internal/handler/auth.go` | MODIFY | `toProfileResponse` gibt das Feld aus; `UpdateProfileHandler`/Update-Struct nimmt es als `*bool` entgegen (Muster `DisplayName`), Read-Modify-Write über `LoadUser`/`SaveUser` |
| `frontend/src/routes/login/+page.server.ts` | MODIFY | Nach erfolgreichem Passwort-Login wird an die Weiterleitungs-Adresse (nach `safeRedirectPath(...)`) ein Query-Marker angehängt |
| `frontend/src/routes/+layout.server.ts` | MODIFY | Reicht zusätzlich zu `displayName` auch `hasPasskey` und `passkeyPromptDismissed` aus dem bereits geladenen Profil weiter |
| `frontend/src/lib/passkeyAngebot.ts` | CREATE | Reine Entscheidungsfunktion `passkeyAngebotFaellig({ marker, hasPasskey, dismissed, webauthnFaehig })` |
| `frontend/src/routes/+layout.svelte` | MODIFY | Neues Banner (Muster: iOS-Installationshinweis Z. 180-201), zwei Aktionen „Jetzt einrichten"/„Nicht jetzt", außerhalb des Chrome-Blocks (#2128) |
| Tests (Go + `node --test` + Playwright) | CREATE | Siehe Test Plan |

## Implementation Details

**Backend (Go):** `internal/model/user.go` bekommt neben `PremiumSmsReplyAt` (Z. 37-38) ein
schlichtes `bool`-Feld mit `omitempty`, JSON-Name `passkey_prompt_dismissed`. „Feld fehlt" und
„false" bedeuten beide „nicht abgewiesen" — kein Zeitstempel-Nullwert-Problem, deshalb kein
Pointer im Modell. `toProfileResponse` (`auth.go:603`) gibt das Feld neben dem bereits
vorhandenen `has_passkey` (Z. 640) aus. `UpdateProfileHandler` (`auth.go:661`, Update-Struct ab
671) nimmt es als Pointer-Feld `*bool` entgegen, Muster `DisplayName`. Kein eigener Endpunkt —
`PUT /api/auth/profile` ist bereits Read-Modify-Write (`LoadUser` → nur gesetzte Felder ändern →
`SaveUser`, `internal/store/user.go:52/73`). `SaveUser` marshalt das gesamte Struct; ein Schlüssel
in `user.json`, den das Go-Struct nicht kennt, ginge beim Speichern verloren
(BUG-DATALOSS-GR221) — deshalb muss das Feld ins Struct, nicht als loses JSON mitgeführt werden.

**Frontend — Marker statt Cookie:** `frontend/src/routes/login/+page.server.ts:55` hängt bei
erfolgreichem Passwort-Login an die Weiterleitungs-Adresse einen Query-Marker an, nach dem
Aufruf von `safeRedirectPath(...)`. Der zurückgegebene Pfad kann bereits eine Query tragen —
beide Fälle (mit und ohne `?`) müssen korrekt zusammengesetzt werden. Ein Cookie scheidet aus:
`+layout.server.ts:10` läuft bei jeder Navigation und Invalidierung; ein dort gelöschtes Cookie
verbraucht der Ladelauf, der zufällig zuerst feuert — das „einmalig" hinge dann an der
Reihenfolge von Ladeläufen. Der Query-Parameter hat keine Reihenfolgen-Semantik.

**Frontend — der Marker bleibt in der Adresse stehen** (nachgetragen 2026-09-12, siehe
Changelog). Er wird nach der Anzeige **nicht** per `replaceState` abgestreift. Zwei Gründe:
Erstens liegt die Zusicherung „einmalig" am serverseitigen Vermerk, nicht an der Adress-Hygiene
— das Abstreifen wäre eine zweite, schwächere Quelle für dieselbe Aussage. Zweitens würde das
Abstreifen die Reload-Zusicherung aus AC-2 **trivial wahr** machen: ein Neuladen holte dann eine
markerfreie Adresse, und das Banner fehlte selbst dann, wenn der `PUT` nie stattgefunden hätte.
Bleibt der Marker stehen, prüft der Reload genau das Richtige — dass die Abweisung den Server
erreicht hat und beim nächsten Ladelauf von dort zurückgelesen wird. Wer vor der Entscheidung
neu lädt, sieht das Angebot erneut; das ist richtig, denn er hat es noch nicht beantwortet.

**Frontend — Profildaten:** `+layout.server.ts:10` lädt das Profil bereits zentral und reicht
bislang nur `displayName` weiter; es wird um `hasPasskey` und `passkeyPromptDismissed` erweitert,
ohne einen Zusatzabruf einzuführen.

**Frontend — Entscheidung:** Neues Modul `passkeyAngebot.ts` mit der reinen Funktion
`passkeyAngebotFaellig({ marker, hasPasskey, dismissed, webauthnFaehig })`. Die Funktion liest
nichts selbst — alle vier Eingaben kommen von außen, `dismissed` ausdrücklich aus `data` (also
vom Server). Nur so ist die Entscheidungstabelle unter `node --test` prüfbar und liegt in der
CI-Ampel.

**Frontend — Darstellung:** `+layout.svelte` bekommt das Banner nach dem Muster des
iOS-Installationshinweises (Z. 180-201) — fest positionierte Einblendung, `role="status"`,
eigener `data-testid`, außerhalb des Chrome-Blocks (#2128). Die Sichtbarkeit wird clientseitig
geschaltet (`if (browser)`, Muster `iosHinweisFaellig()` Z. 92-96), weil `isWebAuthnSupported()`
nur im Browser existiert und die Einblendung nicht am Layout-Ladelauf teilnimmt — anders als bei
#2247, wo der Einfüge-Sprung im Formularfluss das eigentliche Problem war. Der bestehende
`Toast`-Baustein (`$lib/components/mobile/Toast.svelte`) taugt hier nicht, weil er nur eine
Aktion kennt; dieses Banner braucht zwei („Jetzt einrichten" / „Nicht jetzt").

**Aktionen:** „Jetzt einrichten" ruft `registerPasskey(label)` aus
`frontend/src/lib/passkey.ts:37`. Das Banner blendet sich **sofort nach erfolgreicher
Registrierung** über den eigenen Sichtbarkeits-Zustand aus — es wartet nicht auf den nächsten
Ladelauf. Nötig ist das, weil der serverseitig geladene `hasPasskey`-Wert in diesem Moment
veraltet ist: er sagt weiterhin „kein Passkey", obwohl gerade einer entstanden ist. Ohne das
sofortige Ausblenden bliebe das Angebot nach seiner eigenen Erfüllung stehen.
„Nicht jetzt" schickt `PUT /api/auth/profile` mit ausschließlich dem eigenen Feld
(`{ passkey_prompt_dismissed: true }`). Grund für die enge Nutzlast: `auth.go:706-715` setzt
`email_verified_at` zurück, sobald ein abweichender `email`/`mail_to`-Wert mitkommt — nach #2271
(Login nur mit bestätigter Adresse) wäre eine zu großzügige Nutzlast eine Aussperr-Falle.
`api.put` ist ein dünner Helfer ohne Voll-Profil-Serialisierung, jede Aufrufstelle baut ihre
Nutzlast selbst (`account/+page.svelte:290`) — es gibt nichts zu erben.

## Expected Behavior

- **Input:** Passwort-Login eines Nutzers ohne hinterlegten Passkey; Klick auf „Jetzt
  einrichten" oder „Nicht jetzt"
- **Output:** Banner erscheint einmalig nach dem Login; bei „Nicht jetzt" verschwindet es und
  bleibt geräteübergreifend abgeschaltet; bei „Jetzt einrichten" verschwindet es nach
  erfolgreicher Passkey-Registrierung
- **Side effects:** „Nicht jetzt" löst einen `PUT /api/auth/profile`-Aufruf aus, der
  ausschließlich `passkey_prompt_dismissed` setzt; keine weiteren Profilfelder werden berührt

## Acceptance Criteria

- **AC-1:** Given ein Nutzer meldet sich mit Passwort an und hat noch keinen Passkey
  hinterlegt / When die Startseite nach dem Login lädt / Then erscheint das Passkey-Angebot mit
  den zwei Aktionen „Jetzt einrichten" und „Nicht jetzt"
  - Test: `frontend/e2e/passkey-angebot.spec.ts` → AC-1: Passwort-Login ohne Passkey zeigt das
    Banner mit beiden Aktionen

- **AC-2:** Given das Passkey-Angebot ist sichtbar / When der Nutzer auf „Nicht jetzt" klickt /
  Then verschwindet das Banner sofort und bleibt auch nach einem erneuten Laden der Seite auf
  demselben Gerät verschwunden
  - Test: `frontend/e2e/passkey-angebot.spec.ts` → AC-2: Klick auf „Nicht jetzt" blendet das
    Banner aus, Reload zeigt es nicht erneut

- **AC-3:** Given ein Nutzer hat die Abweisung auf einem Gerät ausgesprochen / When derselbe
  Nutzer sich in einem zweiten, unabhängigen Browser-Kontext anmeldet / Then bleibt das
  Passkey-Angebot auch dort verschwunden, weil die Abweisung serverseitig im Profil hinterlegt
  ist und nicht im Gerätespeicher
  - Test: `frontend/e2e/passkey-angebot.spec.ts` → AC-3: zweiter Browser-Kontext
    (`browser.newContext({ storageState: undefined })`, Muster
    `frontend/e2e/compare-cross-user-write-block.spec.ts:43-65`) mit derselben Anmeldung zeigt
    das Banner nicht erneut

- **AC-4:** Given ein Nutzer hat bereits einen Passkey hinterlegt / When er sich mit Passwort
  anmeldet / Then erscheint das Passkey-Angebot zu keinem Zeitpunkt
  - Test: `frontend/e2e/passkey-angebot.spec.ts` → AC-4: Passwort-Login mit vorhandenem Passkey
    zeigt das Banner nie

- **AC-5:** Given ein Nutzer klickt im Passkey-Angebot auf „Jetzt einrichten" und schließt die
  Zeremonie am virtuellen Authentifikator erfolgreich ab / When die Registrierung abgeschlossen
  ist / Then verschwindet das Banner von selbst, ohne dass „Nicht jetzt" geklickt wurde
  - Test: `frontend/e2e/passkey-angebot.spec.ts` → AC-5: erfolgreiche Passkey-Registrierung über
    virtuellen Authentifikator (Muster `frontend/e2e/passkey-login.spec.ts:273-275`) lässt das
    Banner verschwinden

- **AC-6:** Given ein `PUT /api/auth/profile` mit ausschließlich `passkey_prompt_dismissed` als
  Feld / When die Anfrage verarbeitet wird / Then ändert sich im gespeicherten Nutzerprofil nur
  dieses Feld — `display_name`, `mail_to`, `sms_to`, `tier`, `email_verified_at` und
  `passkey_credentials` bleiben unverändert
  - Test: Go-Unit-Test (neue Datei neben `internal/handler/auth_test.go`) → AC-6: Vorher/Nachher-
    Vergleich aller Nachbarfelder nach einem `PUT` mit nur `passkey_prompt_dismissed`, bestätigt
    Read-Modify-Write statt Replace

- **AC-7:** Given die vier Eingaben der Entscheidungsfunktion (Marker gesetzt oder nicht,
  Passkey vorhanden oder nicht, bereits abgewiesen oder nicht, Gerät WebAuthn-fähig oder nicht)
  / When alle relevanten Kombinationen durchlaufen werden / Then liefert die Funktion nur dann
  „Angebot zeigen", wenn Marker gesetzt, kein Passkey vorhanden, noch nicht abgewiesen und das
  Gerät fähig ist — in jeder anderen Kombination „nicht zeigen"
  - Test: `frontend/src/lib/passkeyAngebot.test.ts` (`node --test`) → AC-7: Entscheidungstabelle
    prüft alle Kombinationen, insbesondere die vier Einzel-Ausschlussfälle (kein Marker,
    `hasPasskey`, `dismissed`, `webauthnFaehig=false`) sowie den einen Erfolgsfall

- **AC-8:** Given eine Weiterleitungs-Adresse nach erfolgreichem Passwort-Login, einmal ohne und
  einmal bereits mit vorhandener Query / When der Login-Marker angehängt wird / Then ist die
  resultierende Adresse in beiden Fällen syntaktisch korrekt und enthält den Marker als
  eigenständigen Query-Parameter
  - Test: `frontend/src/lib/passkeyAngebot.test.ts` (`node --test`) → AC-8: die reine Hilfsfunktion
    `mitAngebotMarker(pfad)` aus `frontend/src/lib/passkeyAngebot.ts` wird mit einem Pfad ohne
    Query und einem mit bestehender Query aufgerufen; beide Ergebnisse werden über `new URL(...)`
    auf gültige Query-Syntax und den Marker als eigenständigen Parameter geprüft. Dass
    `+page.server.ts` diese Funktion auch tatsächlich aufruft, beweist erst AC-1 im Browser — die
    Ampel bewacht hier die Rechenregel, nicht die Verdrahtung

## Known Limitations

- Die E2E-Spec `frontend/e2e/passkey-angebot.spec.ts` wird nicht in
  `.github/ci_e2e_specs.txt` aufgenommen — `passkey-login.spec.ts` aus Scheibe 2 (#2247) steht
  dort ebenfalls nicht, und ein CDP-Virtual-Authenticator-Test in der Ampel wäre eine
  Flake-Haftung auf `main`.
- Daraus folgt die offen benannte Lücke: Würde jemand das Merken der Abweisung später von
  „serverseitig" auf `localStorage` umbauen, ginge nur der Zwei-Kontext-E2E (AC-3) rot — und der
  läuft erst bei `/e2e-verify`, nicht in der Ampel. Die Entscheidungstabelle (AC-7) fängt es
  nicht, weil sie `dismissed` als Parameter bekommt statt es selbst zu ermitteln. Bewusst in
  Kauf genommen: der Preis dafür, die Entscheidung überhaupt ampeltauglich zu machen.
- 🔴 **Das Angebot hängt daran, dass das Login-Formular klassisch absendet.** Der Marker wird in
  `+layout.svelte` einmalig beim Aufbau des Wurzel-Layouts aus der Adresse gelesen; das trägt nur,
  weil `frontend/src/routes/login/+page.svelte` **kein** `use:enhance` verwendet und die
  Weiterleitung deshalb ein vollständiges Dokument lädt. Rüstet jemand `use:enhance` nach — was
  naheliegt, weil die drei Nachbar-Formulare (`verify-email`, `reset-password`, `forgot-password`)
  es bereits verwenden —, läuft der Block nicht erneut und **das gesamte Angebot fällt still aus**,
  AC-1 bis AC-5. **Kein Test in der CI-Ampel wird davon rot.** Adversary-Finding F001 (MEDIUM,
  2026-09-13), gebucht in #1199. Wer das Login-Formular umbaut, muss diese Stelle mitziehen —
  entweder durch reaktives Lesen der Adresse oder durch einen Regressionstest.
- Schlägt der `PUT` beim „Nicht jetzt" fehl (Netzabbruch), verschwindet das Banner trotzdem
  sofort — die Abweisung ist dann aber nicht gespeichert und das Angebot kann bei der nächsten
  Anmeldung erneut erscheinen. Der Nutzer wird dafür nicht mit einer Fehlermeldung behelligt: ein
  abgelehntes Angebot ist kein Vorgang, dessen Scheitern er beheben müsste.
- E2E-Konten, die zur Laufzeit entstehen, brauchen nach #2271 eine bestätigte Adresse; auf
  Staging gibt es dafür `POST /api/auth/verify-email/staging-token` (#2304, nur bei
  `GZ_ENV == "staging"`, anmeldepflichtig).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Das Feld folgt bestehenden Mustern (`PremiumSmsReplyAt`-artiges `bool`-Feld,
  Read-Modify-Write-Endpunkt, Pointer-Update-Struct) und eröffnet keine neue Entscheidungsfläche
  im Sinne von Kanälen, Providern, Datenmodell-Paradigmen oder Auth-Verfahren.

## Changelog

- 2026-09-12: Initial spec created
- 2026-09-12: Nach der Freigabe nachgetragen — der Query-Marker wird nach der Anzeige **nicht**
  abgestreift. Ohne diese Festlegung wäre die Reload-Zusicherung in AC-2 trivial wahr geworden
  (Befund aus der RED-Phase). Die ACs selbst sind unverändert; festgeschrieben wurde eine im
  Kontext-Dokument noch offene Implementierungsfrage (dort Risiko 5).
