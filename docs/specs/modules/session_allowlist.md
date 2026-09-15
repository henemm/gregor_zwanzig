---
entity_id: session_allowlist
type: module
created: 2026-09-05
updated: 2026-09-15
status: draft
version: "1.1"
tags: [auth, session, security]
---

# Session-Allowlist — dauerhafte Anmeldung mit widerrufbarem Anmelde-Merkmal

## Approval

- [x] Approved — PO (Henning), 2026-09-05
- [ ] Approved — Revision 1.1 (#2262)

## Purpose

Löst die heutige 24-Stunden-Ablauffrist der Anmeldung ab: Anmeldungen gelten fortan unbefristet, bis sie aktiv widerrufen werden. Dafür führt jeder Nutzer eine eigene Gästeliste gültiger Anmeldungen; ein Anmelde-Merkmal ist nur gültig, solange seine Anmelde-Kennung auf dieser Liste steht — Widerruf (einzelnes Gerät oder „alle Geräte") entfernt den Eintrag und wirkt dauerhaft, auch über einen Dienst-Neustart hinweg.

**Seit Revision 1.1 (#2262) gibt es nur noch EIN Anmelde-Merkmal-Format**, das vierteilige (`{userId}.{sessionId}.{ts}.{hmacSig}`). Der befristete Übergangs-Zweig für das alte dreiteilige Merkmal (`{userId}.{ts}.{hmacSig}`, 24h-Ablauf), den ADR-0060 für die Zeit unmittelbar nach dem Deploy vom 2026-09-06 vorgesehen hatte, ist nach Ablauf der genannten 24h-Frist ersatzlos entfernt — laut ADR-0060 selbst „kann der Legacy-Zweig danach ersatzlos entfallen". Ein Anmelde-Merkmal, das dieses alte Format hat oder eine Anmelde-Kennung ohne Gästelisten-Eintrag trägt, wird ab dieser Revision wie jedes andere unbekannte Cookie behandelt: Ablehnung mit 401, keine stille Hebung mehr.

## Source

- **File:** `internal/store/sessions.go` **(MODIFY, #2262)**
- **Identifier:** Feld `LegacyRevokedAt` in `sessionFile` (Zeile ~37), Methode `LegacyRevokedAt(userId)` (Zeile ~103), Methode `RevokeLegacySessions` (Zeile ~114), das Schreiben von `LegacyRevokedAt` in `ClearSessions` (Zeile ~204) — alle vier entfallen ersatzlos.
- **File:** `internal/middleware/auth.go` **(MODIFY, #2262)**
- **Identifier:** Konstante `legacyMaxAgeSeconds` (Zeile 30), `SessionStore`-Interface-Methode `LegacyRevokedAt` (Zeile 41), der `isNew`-Verzweigungspunkt in `AuthMiddleware` (Zeilen 79–101, insbesondere die `else`/`else if`-Zweige ab Zeile 96), Funktion `legacySessionValid` (Zeile 121), Funktion `upgradeLegacySession` (Zeile 143), Funktion `SignSession` — die alte Signierfunktion für das dreiteilige Format (Zeile 176), der Alt-Format-Zweig in `validateSession` (`len(parts) >= 3`, Zeilen 262–280) — alle entfallen; `validateSession` liefert danach kein `isNew` mehr, da es nur noch ein Format gibt (Signaturvereinfachung, siehe Implementation Details).
- **File:** `internal/handler/auth.go` **(MODIFY, #2262)**
- **Identifier:** `LogoutHandler` (Zeile 658), der `else`-Zweig auf `RevokeLegacySessions` bei leerer `sessionId` (Zeile 667) entfällt — nach dem Rückbau liefert `SessionFromCookie` für jedes gültige Merkmal eine nicht-leere `sessionId`, der Zweig ist dann unerreichbar und muss mit entfernt werden, nicht nur totgelegt.
- **File:** `frontend/src/lib/auth.ts` **(MODIFY, #2262)**
- **Identifier:** `verifySession` (Zeile 36) — der `parts.length >= 3`-Zweig fürs alte Format (Zeilen 61–73) entfällt, der Parameter `maxAge` (Standardwert `LEGACY_MAX_AGE_SECONDS`, Zeile 39) entfällt mit ihm, da er nur für das alte Format gebraucht wurde (Aufrufer `frontend/src/hooks.server.ts:41` ruft bereits nur zweistellig auf, ist also unberührt); Konstante `LEGACY_MAX_AGE_SECONDS` (Zeile 14) entfällt; Funktion `signSession` (Zeile 16, mintet das alte dreiteilige Format) entfällt — sie hat im Produktivcode keinen Aufrufer mehr (nur in Tests referenziert, siehe unten), war aber nie Teil des Ausstellungspfads.
- **File:** `frontend/src/lib/session_format.test.ts` **(MODIFY, #2262 — Nebenbefund, nicht im Issue-Text, aber direktes Gegenstück zu `internal/middleware/session_allowlist_test.go`)**
- **Identifier:** `legacyCookie`-Helfer (Zeile 27) und die drei Tests, die ihn nutzen — `AC-10` (Zeile 63), `AC-11` (Zeile 72), der Alt-Format-Teil von `AC-14` (Zeilen 113–117) — entfallen; der Neu-Format-Teil von `AC-14` bleibt.
- **File:** `frontend/src/lib/auth_oauth.test.ts` **(MODIFY, #2262 — Nebenbefund)**
- **Identifier:** Der einzige Test, der die echte `auth.ts`-Funktion importiert (Zeile 98–109), erzeugt sein Test-Cookie über den lokalen `signSession`-Helfer im ALTEN Format (Zeile 16–20, Kopie der jetzt entfallenden `auth.ts`-Funktion). Muss auf einen Aufbau im neuen vierteiligen Format umgestellt werden, sonst schlägt der einzige Verhaltens-Test dieser Datei nach dem Rückbau grundlos fehl. Die beiden reinen Format-Vergleichstests (Zeile 55, 72), die ausschließlich mit lokal nachgebauten `verifySessionCurrent`/`verifySessionFixed`-Kopien arbeiten (kein Aufruf der echten `auth.ts`), sind historische Dokumentation eines 2025er-Bugfix (#425) und bleiben unverändert — sie prüfen nicht den entfallenden Zweig.
- **File:** `internal/middleware/sign_session_test.go` **(DELETE, #2262)**
- **Identifier:** Alle drei Tests (`TestSignSessionFormat`, `TestSignSessionValidateRoundtrip`, `TestSignSessionInvalidWithWrongSecret`) prüfen ausschließlich `SignSession` und den `isNew=false`-Rückgabewert von `validateSession` für das Alt-Format — verifiziert durch Lesen der Datei, kein anderer Prüfling steckt darin. Beides entfällt vollständig mit dem Rückbau, die Datei hat danach keinen Prüfling mehr und wird komplett gelöscht (keine Teilrettung nötig).
- **File:** `internal/handler/logout_revocation_test.go` **(MODIFY, #2262)**
- **Identifier:** Die Alt-Merkmal-Widerruf-Fälle (Zeilen 575, 610, 642 — `RevokeLegacySessions`-Pfad) entfallen; die Fälle für das neue Format bleiben unverändert.
- **File:** `internal/middleware/session_allowlist_test.go` **(MODIFY, #2262)**
- **Identifier:** Der Testteil, der `isNew=false` für ein Alt-Format-Merkmal erwartet, entfällt; `TestDottedUserID_SplitFromTheRight` (referenziert von AC-14, siehe `session_format.test.ts:104`) bleibt für den Neu-Format-Fall bestehen, ihr Alt-Format-Fall entfällt.
- **File:** `internal/router/legacy_subscription_routes_removed_test.go` **(MODIFY, #2262)**
- **Identifier:** Zeile 77 nutzt `SignSession` nur als bequemen Weg zu einem gültigen Cookie, nicht um Legacy-Verhalten zu testen — Umstellung auf `SignSessionWithID` + `AddSession` (neues Format), sonst grundloser Ausfall.
- **File:** `internal/router/briefing_subscription_test.go` **(MODIFY, #2262)**
- **Identifier:** Zeile 104, gleiche Lage wie oben — Umstellung auf `SignSessionWithID` + `AddSession`.
- **File:** `docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md` **(MODIFY, #2262)**
- **Identifier:** Vermerk „Übergangsabschnitt erledigt am 2026-09-15 (#2262)" ergänzen.
- **File:** `docs/reference/api_contract.md` **(MODIFY, #2262)**
- **Identifier:** Zeile 2381 (verifiziert: „`legacy_revoked_at`: Abmelden mit einem Alt-Merkmal setzt den Zeitstempel, und…") — als entfernt/historisch markieren, kein API-Vertrag mehr, da das Feld nicht mehr geschrieben/gelesen wird.

> **Schicht-Hinweis:** Diese Revision betrifft ausschließlich die Go-API (`internal/`) und das SvelteKit-Frontend (`frontend/src/lib/auth.ts` und die zugehörigen Tests). Kein Python-Core-Code betroffen.

## Estimated Scope

- **LoC:** -80 bis -30 (überwiegend Löschungen: Legacy-Funktionen, Legacy-Feld, Legacy-Testdatei; die Test-Umstellungen auf `SignSessionWithID` fügen vereinzelt Zeilen hinzu, das Delta bleibt netto negativ oder klein positiv)
- **Files:** ~12 (davon 1 komplett gelöschte Testdatei, 2 Doku-Dateien)
- **Effort:** medium (kein neuer fachlicher Code, aber zwei getrennte Prüfstellen und mehrere Testdateien synchron zu halten)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `logout_session_blacklist` | module (Spec) | Bereits durch Revision 1.0 dieser Spec (#2129) vollständig abgelöst — die frühere prozesslokale Sperrliste existiert im Code nicht mehr. Mit Revision 1.1 entfällt zusätzlich der letzte Rest des Übergangs (`RevokeLegacySessions`), der diese Ablösung noch für Alt-Merkmale nachgebildet hatte; die Ablösung ist damit vollständig, keine offene Restabhängigkeit mehr. |
| `user_auth_endpoints` | module (Spec) | Unverändert — der Endpunkt „auf allen Geräten abmelden" bleibt wie in Revision 1.0 beschrieben. |
| `change_password` | module (Spec) | Unverändert. |
| `passkey_webauthn` | module (Spec) | Unverändert — alle drei Passkey-Wege stellten schon in Revision 1.0 ausschließlich das vierteilige Merkmal aus. |
| `google_oauth_login` | module (Spec) | Unverändert. |
| `sveltekit_login_refactor` | module (Spec) | Unverändert. |

Keine neuen Abhängigkeiten durch Revision 1.1.

## Implementation Details

**Vor Revision 1.1** liefen zwei Anmelde-Merkmal-Formate befristet nebeneinander (siehe unten, historisch). **Ab Revision 1.1** gibt es nur noch das vierteilige Format (Nutzerkennung, Anmelde-Kennung, Zeitstempel, Signatur — unbefristet, solange die Anmelde-Kennung auf der Gästeliste steht). Beide Prüfstellen (Go-Dienst `internal/middleware/auth.go` und Frontend-Server `frontend/src/lib/auth.ts`) zerlegen weiterhin von rechts, damit eine Nutzerkennung mit Punkt nicht zu unterschiedlichen Ergebnissen führt — das bleibt unverändert, betrifft aber jetzt nur noch einen Zweig statt zwei.

`validateSession` (Go) und `verifySession` (Frontend) verlieren mit dem Alt-Format-Zweig auch dessen Signatur-Anteil: `validateSession` muss kein `isNew` mehr zurückliefern (es gibt nur noch ein Format, die Unterscheidung entfällt), `verifySession` verliert den `maxAge`-Parameter (der nur für das befristete Alt-Format einen Sinn hatte — das neue Format kennt keinen zeitbasierten Ablauf, dafür steht die Gästeliste). Aufrufer beider Funktionen müssen entsprechend angepasst werden (`AuthMiddleware` in `auth.go`, `hooks.server.ts` im Frontend).

Ein Alt-Format-Cookie (drei Segmente, oder vier Segmente ohne gültige Signatur für das neue Format) fällt nach dem Rückbau in denselben Ablehnungspfad wie jedes andere unbekannte oder manipulierte Cookie — 401, kein Sonderfall mehr. Nach dem Rückbau stellt kein Ausstellungsweg mehr ein Alt-Format-Cookie aus (der Aussteller `SignSession` ist gelöscht); ein Nachweis dieses Verhaltens muss das Cookie daher im Test von Hand nachbauen (siehe AC-19).

**Bestandsdaten:** `sessions.json`-Dateien, die noch `legacy_revoked_at` tragen, brauchen kein Migrationsskript und keine eigene Prüfung. Go's `encoding/json`-Unmarshal (ohne `DisallowUnknownFields`, siehe `internal/store/sessions.go:68`) ignoriert unbekannte Felder beim Lesen unabhängig davon, ob `LegacyRevokedAt` noch im Struct steht — das war schon vor dieser Revision so und ändert sich durch den Rückbau nicht. Sobald das Feld aus dem Go-Struct entfernt ist, schreibt kein Code-Pfad es beim nächsten Speichern der Datei mehr zurück (Read-Modify-Write bleibt gewahrt). Es gibt an dieser Stelle keinen beobachtbaren Verhaltensunterschied vor/nach dem Rückbau, den ein Test sinnvoll rot/grün zeigen könnte — deshalb enthält diese Spec dafür bewusst KEINE eigene Acceptance Criterion (ein Test, der so oder so grün wäre, wäre das in CLAUDE.md verbotene Mock-Theater).

**Historisch (Revision 1.0, überholt):** Zwei Anmelde-Merkmal-Formate liefen befristet nebeneinander: das alte dreiteilige (blieb mit seiner bestehenden 24-Stunden-Grenze gültig) und das neue vierteilige. Ein gültiges altes Merkmal wurde beim nächsten Aufruf still durch ein neues ersetzt. Dieser Absatz ist mit Revision 1.1 nicht mehr aktuell, bleibt hier zur Nachvollziehbarkeit stehen.

Die Gästeliste selbst (Datei `data/users/<user_id>/sessions.json`, Pro-Nutzer-Sperre, kein Zwischenspeicher) ist von Revision 1.1 nicht betroffen — diese Mechanik bleibt unverändert bestehen.

## Expected Behavior

- **Input:** Anmeldung über einen der fünf ausstellenden Anmeldewege (Passwort, Magic-Link, Google, Passkey-Login, Passkey-Login ohne Kennungseingabe — siehe AC-13-Fortschreibung unten); Abmelde-Aufruf (ein Gerät oder alle Geräte); Passwortwechsel oder Passwort-Zurücksetzen; jede authentifizierte Anfrage mit einem Anmelde-Merkmal im Cookie.
- **Output:** Erfolgreiche Anmeldung liefert ein vierteiliges Anmelde-Merkmal im `Set-Cookie`-Header. Eine authentifizierte Anfrage mit gültigem, gelistetem Merkmal liefert den regulären Antwortcode; mit widerrufenem, manipuliertem, unbekanntem oder im alten (nicht mehr unterstützten) Format vorliegendem Merkmal liefert sie 401 — ab Revision 1.1 ohne Unterscheidung zwischen diesen Fällen.
- **Side effects:** Wie Revision 1.0. Zusätzlich: Nach Revision 1.1 löst ein Alt-Format-Cookie keine stille Hebung mehr aus — es gibt keinen Seiteneffekt mehr auf ein Alt-Format-Merkmal, außer der Ablehnung selbst.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer meldet sich frisch an / When die Anmeldung erfolgreich ist / Then enthält seine Gästeliste einen neuen Eintrag und das ausgestellte Anmelde-Merkmal besteht aus vier durch Punkt getrennten Teilen.
  - Test: Login-Request gegen den echten Anmelde-Endpunkt, anschließend das ausgestellte Cookie am `.`-Zeichen aufsplitten (4 Segmente) und mit demselben Cookie einen geschützten Endpunkt aufrufen → 200.

- **AC-2:** Given eine Anmeldung wurde soeben ausgestellt / When der Dienst einen echten Neustart durchläuft / Then bleibt das Anmelde-Merkmal gültig.
  - Test: Login, Dienst-Prozess real beenden und neu starten, danach mit demselben Cookie einen geschützten Endpunkt aufrufen → weiterhin 200.

- **AC-3:** Given eine Anmeldung wurde ausgestellt / When seither mehr als 24 Stunden vergangen sind (mit vorgestellter Systemuhr geprüft) / Then bleibt das neue Anmelde-Merkmal gültig, obwohl es nach der alten Regel bereits abgelaufen wäre.
  - Test: Login, Testuhr um mehr als 25 Stunden vorstellen, Request mit demselben Cookie an geschützten Endpunkt → 200.

- **AC-4:** Given ein Nutzer ist auf einem Gerät angemeldet / When er sich auf diesem Gerät abmeldet / Then wird sein Anmelde-Merkmal sofort ungültig und bleibt es auch nach einem echten Dienst-Neustart.
  - Test: Login (Cookie A), Abmelde-Aufruf mit Cookie A, Request mit Cookie A → 401; Dienst real neu starten; Request mit demselben Cookie A erneut → 401.

- **AC-5:** Given ein Nutzer ist auf zwei Geräten angemeldet / When er sich nur auf einem der beiden abmeldet / Then bleibt die Anmeldung des anderen Geräts gültig.
  - Test: Zwei Logins desselben Kontos (Cookie A, Cookie B), Abmelden mit Cookie A. Request mit Cookie B → 200, Request mit Cookie A → 401.

- **AC-6:** Given ein Nutzer ist auf mehreren Geräten angemeldet / When er „auf allen Geräten abmelden" auslöst / Then werden alle seine Anmeldungen ungültig, auch nach einem echten Dienst-Neustart.
  - Test: Zwei Logins desselben Kontos (Cookie A, B), Aufruf des Endpunkts „alle abmelden" mit einem der beiden Cookies. Requests mit A und B → beide 401; Dienst neu starten; beide Requests erneut → weiterhin 401.

- **AC-7:** Given zwei verschiedene, echte Nutzerkonten sind angemeldet / When „auf allen Geräten abmelden" bei Nutzer 1 ausgelöst wird / Then bleiben die Anmeldungen von Nutzer 2 unberührt.
  - Test: Login Nutzer 1 und Nutzer 2 (getrennte Konten), „alle abmelden" bei Nutzer 1. Request mit Nutzer 1s Cookie → 401, Request mit Nutzer 2s Cookie → weiterhin 200.

- **AC-8:** Given ein Nutzer ist angemeldet / When er sein Passwort über den Passwortwechsel-Endpunkt ändert / Then wird sein zuvor gültiges Anmelde-Merkmal ungültig.
  - Test: Login (Cookie A), Passwortwechsel-Endpunkt aufrufen. Request mit Cookie A an geschützten Endpunkt → 401.

- **AC-9:** Given ein Nutzer ist angemeldet / When er sein Passwort über den „Passwort vergessen"-Ablauf zurücksetzt / Then wird sein zuvor gültiges Anmelde-Merkmal ungültig.
  - Test: Login (Cookie A), Passwort-Zurücksetzen-Ablauf bis zum Einlösen des Reset-Tokens durchlaufen. Request mit dem alten Cookie A → 401.

- **AC-10:** ~~Given ein Nutzer besitzt noch ein gültiges Anmelde-Merkmal im alten dreiteiligen Format / When er damit einen Request stellt / Then wird der Request angenommen und er erhält im selben Zug ein neues vierteiliges Anmelde-Merkmal, ohne sich neu anmelden zu müssen.~~
  - 🔴 **Entfällt 2026-09-15 durch Issue #2262 (Rückbau nach ADR-0060):** Der Übergangs-Zweig, der ein Alt-Merkmal noch annahm und still hob, ist ersatzlos entfernt. Das hier beschriebene Verhalten gilt nicht mehr — siehe stattdessen AC-19 (Alt-Format wird jetzt wie ein unbekanntes Cookie abgelehnt). Der zugehörige Test (`internal/middleware/sign_session_test.go`) ist gelöscht.

- **AC-11:** ~~Given ein Anmelde-Merkmal im alten Format ist älter als 24 Stunden / When damit ein Request gestellt wird / Then wird er abgewiesen.~~
  - 🔴 **Entfällt 2026-09-15 durch Issue #2262:** Gegenstandslos, da es kein Alt-Format mehr gibt, das eine eigene 24h-Regel bräuchte — jedes Alt-Format-Merkmal wird jetzt unabhängig vom Alter abgewiesen (AC-19). Der zugehörige Test (`session_format.test.ts:72`, `internal/middleware/sign_session_test.go`) entfällt.

- **AC-12:** Given ein Anmelde-Merkmal wurde verändert oder trägt eine Anmelde-Kennung, die nicht auf der Gästeliste steht / When damit ein Request gestellt wird / Then wird er in beiden Fällen abgewiesen.
  - Test: (a) Request mit einem Cookie, dessen Signatur-Segment einzeln verändert wurde → 401. (b) Request mit einem korrekt signierten Cookie, dessen Anmelde-Kennung nicht in der Gästeliste des Nutzers enthalten ist → 401.

- **AC-13:** Given ein Nutzer meldet sich über einen der **fünf ausstellenden** Anmeldewege an (Passwort, Magic-Link, Google, Passkey-Login, Passkey-Login ohne Kennungseingabe) / When die Anmeldung abgeschlossen ist / Then besteht das jeweils ausgestellte Anmelde-Merkmal die eigene Prüfung.
  - Test: Für jeden der fünf Wege einzeln: Anmeldung über den jeweiligen Endpunkt auslösen, danach mit dem ausgestellten Cookie einen geschützten Endpunkt aufrufen → 200 in allen fünf Fällen.
  - 🔴 **Fortgeschrieben 2026-09-12 durch Issue #2271 / [ADR-0066](../../adr/0066-login-erfordert-bestaetigte-email-adresse.md):** Die ursprüngliche Fassung sagte „alle **sechs** Anmeldewege stellen ein Merkmal aus". Seit der Scharfschaltung des E-Mail-Gates gilt das nur noch für fünf Wege, und drei davon nur bedingt: Passwort-Login und die beiden Passkey-Login-Wege stellen ausschließlich bei **bestätigter** Adresse aus, Magic-Link und Google, sobald die Adresse bestätigt ist oder sich im selben Request selbst heilt. Der sechste Weg — die **öffentliche Passkey-Registrierung** — stellt gar kein Merkmal mehr aus (201 ohne Cookie, `status: verification_pending`). Die vier Verweigerungsfälle sind in `email_verify_scharfschaltung_2271.md` AC-7 eigenständig abgedeckt; im Test trägt jede Gruppe einen **eigenen** Zähler, damit ein zwischen den Gruppen verschobener Weg auffällt.

- **AC-14:** Given ein Anmelde-Merkmal, dessen Nutzerkennung einen Punkt enthält / When der Go-Dienst und der Frontend-Server dasselbe Merkmal zerlegen / Then lesen beide dieselbe Nutzerkennung heraus und weisen es beide nicht ab.
  - Test: Ein Konto mit einer Kennung wie `alice.smith` direkt im Datenbestand anlegen (die Registrierung lässt Punkte nicht zu, die Zerlegungsregel muss trotzdem auf beiden Seiten gleich sein), dafür ein Merkmal im (einzigen, vierteiligen) Format ausstellen und dasselbe Merkmal beiden Prüfstellen vorlegen → beide liefern `alice.smith`, keine weist ab.
  - 🔴 **Fortgeschrieben 2026-09-15 durch Issue #2262:** Der ursprüngliche Test deckte diese Zusicherung für BEIDE Formate ab (`session_format.test.ts:104-118`, `internal/middleware/session_allowlist_test.go` `TestDottedUserID_SplitFromTheRight`). Mit dem Rückbau des Alt-Formats bleibt nur noch der Neu-Format-Fall zu prüfen; der Alt-Format-Teil beider Tests entfällt ersatzlos, da es nichts mehr gibt, das er noch belegen könnte.

- **AC-15:** Given mehrere Änderungen an den Anmeldungen desselben Nutzers laufen gleichzeitig / When sie parallel abgesetzt werden / Then geht keine davon verloren.
  - Test: (a) Zwei Anmeldungen desselben Kontos parallel auslösen → danach sind **beide** Merkmale gültig (keins hat das andere aus der Gästeliste verdrängt). (b) „Alle abmelden" parallel zu einer Profiländerung desselben Nutzers → danach ist das vorher gültige Merkmal abgewiesen **und** die Profiländerung ist gespeichert.

- **AC-16:** Given ein Nutzer ist angemeldet / When sein Konto gelöscht wird / Then wird sein Anmelde-Merkmal ungültig und bleibt es auch nach einem echten Dienst-Neustart.
  - Test: Login (Cookie A), Konto-Löschung auslösen, Request mit Cookie A → 401; Dienst real neu starten; Request mit Cookie A erneut → weiterhin 401.

- **AC-17:** Given ein angemeldeter Nutzer ist auf der Konto-Seite / When er „Auf allen Geräten abmelden" anklickt und den Bestätigungsschritt bestätigt / Then wird er auf die Anmelde-Seite geleitet.
  - Test: Browser-Test — Klick auf den Button öffnet einen Bestätigungsdialog; nach Bestätigen landet die Seite auf der Anmelde-Route.

- **AC-18:** Given ein Nutzer meldet sich an / When das Cookie im Browser gesetzt wird / Then bleibt es über das Schließen des Browsers hinaus gespeichert und trägt eine Lebensdauer, die die alte 24-Stunden-Grenze deutlich übersteigt.
  - Test: Der `Set-Cookie`-Header **jeder** der fünf ausstellenden Anmeldewege trägt eine Lebensdauer von mindestens einem Jahr. Der bisherige Wert (24 Stunden) darf diesen Nachweis nicht bestehen — ein Test, der jede beliebige Lebensdauer durchgehen lässt, prüft nichts.
  - 🔴 **Fortgeschrieben 2026-09-12 durch Issue #2271 / [ADR-0066](../../adr/0066-login-erfordert-bestaetigte-email-adresse.md):** „sechs" → „fünf ausstellende". Die öffentliche Passkey-Registrierung setzt kein Cookie mehr und hat damit keinen `Set-Cookie`-Header, an dem eine Lebensdauer zu messen wäre. Die `Secure`-Flag- und Lebensdauer-Prüfungen dieses Weges sind ersatzlos entfallen (`passkey_public_test.go`); die Cookie-Form bleibt über den Passkey-**Login**-Pfad bewacht.

- **AC-19:** Given ein Anmelde-Merkmal liegt im alten dreiteiligen Format vor (gültig signiert, jünger als 24 Stunden — also nach der VORHERIGEN Regel akzeptiert worden) / When damit ein Request an eine geschützte Route gestellt wird / Then wird er an BEIDEN Prüfstellen abgewiesen, ohne Sonderbehandlung.
  - Test: Kein Ausstellungsweg erzeugt nach dem Rückbau noch ein dreiteiliges Cookie (`SignSession` ist gelöscht) — der Testaufbau baut es deshalb von Hand nach: `{userId}.{ts}.HMAC-SHA256("{userId}:{ts}", secret)`. (a) Go-Dienst: HTTP-Request mit diesem handgebauten Cookie an einen geschützten Endpunkt → 401, keine `Set-Cookie`-Hebung in der Antwort. Positivkontrolle: ein per echtem Login ausgestelltes vierteiliges Cookie wird am selben Endpunkt angenommen (200) — ohne diese Kontrolle bewiese ein 401 nur einen kaputten Endpunkt, nicht die gezielte Ablehnung des Alt-Formats. (b) Frontend-Server: `verifySession(<dasselbe handgebaute Cookie>, secret)` unter `node --test` (kein Vitest, echte HMAC, kein Mock) → liefert `null`; dieselbe Positivkontrolle mit einem vierteiligen Cookie → liefert `{userId}`.

- **AC-20:** Given der Rückbau ist abgeschlossen / When der Produktivcode nach den Legacy-Bezeichnern durchsucht wird / Then liefert die Suche keinen Treffer außerhalb von Tests und historischen Doku-Vermerken.
  - Test (`# doc-compliance-test`): `grep -rn "LegacyRevokedAt\|legacy_revoked_at\|legacyMaxAgeSeconds\|LEGACY_MAX_AGE_SECONDS\|legacySessionValid\|upgradeLegacySession\|RevokeLegacySessions" internal/ frontend/src/` liefert null Treffer außerhalb von Testdateien, die den historischen Fall dokumentieren (z. B. ein erklärender Kommentar mit Verweis auf #2262), und außerhalb dieser Spec-Datei selbst. Bewusst NICHT der pauschale Suchbegriff `legacy` — der träfe auch unabhängige Vorkommen wie `legacy_subscription_routes_removed_test.go`, die mit diesem Rückbau nichts zu tun haben.

- **AC-21:** Given alle fünf ausstellenden Anmeldewege sind unverändert im Einsatz / When ein Nutzer sich über jeden einzeln anmeldet / Then funktioniert jeder Weg unverändert wie vor dem Rückbau (keine Regression).
  - Test: Kurzer Smoke-Test je Anmeldeweg (Passwort, Magic-Link, Google, Passkey-Login, Passkey-Login ohne Kennungseingabe): Anmeldung auslösen, mit dem ausgestellten Cookie einen geschützten Endpunkt aufrufen → 200. Deckt sich mit AC-13, hier explizit als Regressions-Nachweis NACH dem Rückbau geführt. Nur der Passwort-Weg ist auf Staging live messbar; Magic-Link, Google und beide Passkey-Wege werden über die bestehende Go-Testsuite (AC-13) abgedeckt, nicht zusätzlich als Staging-Smoke-Test verlangt.

- **AC-22:** Given der Rückbau ist committet / When die volle Testsuite läuft / Then sind sowohl die Go-Tests als auch die Frontend-Tests grün, ohne dass ein Test wegen des entfallenen Legacy-Zweigs grundlos rot wird.
  - Test: `go test ./...` (mit `PATH=$PATH:/usr/local/go/bin`) und `cd frontend && npm test` laufen jeweils ohne Fehlschlag durch; insbesondere `internal/router/legacy_subscription_routes_removed_test.go` und `internal/router/briefing_subscription_test.go` (umgestellt auf `SignSessionWithID`+`AddSession`) bestehen weiterhin.

- **AC-23:** Given der Übergangszeitraum aus ADR-0060 ist verstrichen und der Rückbau ist durchgeführt / When das ADR-Dokument gelesen wird / Then trägt es einen sichtbaren Vermerk, dass der Übergangsabschnitt erledigt ist, mit Datum und Issue-Nummer.
  - Test: `docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md` enthält nach dem Rückbau die Zeile „Übergangsabschnitt erledigt am 2026-09-15 (#2262)" oder eine sinngemäß gleichwertige Formulierung mit Datum und Issue-Bezug.

## Known Limitations

- Der Frontend-Server prüft weiterhin nur Signatur und Format des Anmelde-Merkmals, nicht die Gästeliste (er hat keinen Zugriff auf den Nutzer-Datenbestand). Nach einem Widerruf entsteht dadurch ein kurzes Fenster: die Seite lädt, die Daten fehlen (die Ladefunktion bekommt vom Go-Dienst 401 und liefert leere Daten), bis der nächste Klick den harten Sprung auf die Anmelde-Seite auslöst. Keine Umleitungsschleife — entspricht dem heutigen Verhalten der bestehenden Sperrliste.
- ~~Ein Nutzer, der 24 Stunden lang ausschließlich Seiten betrachtet und nie eine Aktion auslöst, behält bis dahin sein altes dreiteiliges Anmelde-Merkmal...~~ 🔴 **Gegenstandslos seit #2262:** Es gibt kein altes Format mehr, das ein Nutzer „behalten" könnte — jede Anmeldung ist von Anfang an vierteilig. Diese Einschränkung entfällt ersatzlos.
- Keine Geräteliste in dieser Scheibe (kein „angemeldet auf 3 Geräten seit …" in der Oberfläche). Die Gästeliste macht das später ohne Umbau möglich.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0060
- **Rationale:** Löst ADR-0030 ab, weil eine unbefristete Anmeldung ohne wirksamen, neustart-festen Widerruf ein unbegrenzt gültiges, einmal abgegriffenes Cookie bedeuten würde. Eine dateibasierte Gästeliste je Nutzer (statt eines reinen Generationszählers) ist die einzige der zwei geprüften Varianten, die sowohl „ein Gerät abmelden" als auch „alle Geräte abmelden" ohne zwei parallele Mechanismen abdeckt. Der befristete Übergangs-Zweig für das alte Format war von ADR-0060 selbst als vorübergehend markiert und wird mit Issue #2262 planmäßig entfernt — keine neue Architektur-Entscheidung nötig, nur der im ADR bereits vorgesehene Abschluss.

## Changelog

- 2026-09-05: Initial spec created (#2129)
- 2026-09-12: AC-13, AC-18 fortgeschrieben durch #2271 / ADR-0066 (E-Mail-Bestätigungspflicht)
- 2026-09-15: Revision 1.1 — Rückbau des Alt-Format-Übergangs-Zweigs nach ADR-0060 (#2262). AC-10, AC-11 entfallen; AC-14 auf den Neu-Format-Fall verengt; AC-19 bis AC-23 neu ergänzt (Ablehnung des Alt-Formats an beiden Prüfstellen mit Positivkontrolle, enger Grep-Nachweis auf die enumerierten Alt-Bezeichner statt des pauschalen Begriffs „legacy", Regressionsfreiheit mit Staging-Scoping-Hinweis, Testsuite grün, ADR-Vermerk). Bewusst KEINE eigene AC für Bestandsdaten mit `legacy_revoked_at`: Go's `encoding/json` ignoriert unbekannte Felder unabhängig von dieser Änderung, es gibt keinen testbaren Verhaltensunterschied (siehe Implementation Details). Status bleibt `draft` bis PO-Freigabe der Revision.
