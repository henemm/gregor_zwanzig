---
entity_id: session_allowlist
type: module
created: 2026-09-05
updated: 2026-09-05
status: draft
version: "1.0"
tags: [auth, session, security]
---

# Session-Allowlist — dauerhafte Anmeldung mit widerrufbarem Anmelde-Merkmal

## Approval

- [x] Approved — PO (Henning), 2026-09-05

## Purpose

Löst die heutige 24-Stunden-Ablauffrist der Anmeldung ab: Anmeldungen gelten fortan unbefristet, bis sie aktiv widerrufen werden. Dafür führt jeder Nutzer eine eigene Gästeliste gültiger Anmeldungen; ein Anmelde-Merkmal ist nur gültig, solange seine Anmelde-Kennung auf dieser Liste steht — Widerruf (einzelnes Gerät oder „alle Geräte") entfernt den Eintrag und wirkt dauerhaft, auch über einen Dienst-Neustart hinweg.

## Source

- **File:** `internal/store/sessions.go` **(CREATE)**
- **Identifier:** Gästeliste lesen/hinzufügen/entfernen/leeren (atomare Persistenz je Nutzer)
- **File:** `internal/store/sessions_lock.go` **(CREATE)**
- **Identifier:** Pro-Nutzer-Sperre nach Vorbild `internal/store/briefing_lock.go`
- **File (Prüfstelle):** `internal/middleware/auth.go` **(MODIFY)**
- **Identifier:** Anmelde-Merkmal zerlegen, Format-Weiche altes/neues Anmelde-Merkmal, Gästelisten-Abgleich

> **Schicht-Hinweis:** Diese Scheibe betrifft ausschließlich die Go-API (`internal/`) und das SvelteKit-Frontend (`frontend/src/lib/auth.ts`, `frontend/src/hooks.server.ts`, `frontend/src/routes/...`). Kein Python-Core-Code betroffen.

## Estimated Scope

- **LoC:** +450 bis +600 (reißt das 250er-Limit, Override gesetzt)
- **Files:** ~18 (davon 2 neue Code-Dateien, 1 neues ADR)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `logout_session_blacklist` | module (Spec) | Wird durch diese Scheibe abgelöst: die heutige prozesslokale Sperrliste für einzelne Anmelde-Merkmale entfällt zugunsten der dateibasierten Gästeliste; die Spec wird auf den neuen Stand aktualisiert. |
| `user_auth_endpoints` | module (Spec) | Bekommt einen neuen Endpunkt „auf allen Geräten abmelden" in die Endpunkt-Liste aufgenommen. |
| `change_password` | module (Spec) | Der Passwortwechsel-Endpunkt meldet den Nutzer ab dieser Scheibe zusätzlich auf allen Geräten ab (bislang keine Session-Wirkung). |
| `passkey_webauthn` | module (Spec) | Alle drei Passkey-Anmeldewege (Login, Login ohne Kennungseingabe, Registrierung) stellen künftig das vierteilige Anmelde-Merkmal aus und tragen die Anmeldung in die Gästeliste ein. |
| `google_oauth_login` | module (Spec) | Die Google-Anmeldung stellt künftig das vierteilige Anmelde-Merkmal aus und trägt die Anmeldung in die Gästeliste ein. |
| `sveltekit_login_refactor` | module (Spec) | Die Frontend-eigene Anmelde-Merkmal-Prüfung (`auth.ts`, `hooks.server.ts`) muss das neue Format identisch zum Go-Dienst zerlegen; Cookie-Lebensdauer wird unbefristet gesetzt. |

## Implementation Details

Zwei Anmelde-Merkmal-Formate laufen befristet nebeneinander: das alte dreiteilige (Nutzerkennung, Zeitstempel, Signatur — bleibt mit seiner bestehenden 24-Stunden-Grenze gültig) und das neue vierteilige (Nutzerkennung, Anmelde-Kennung, Zeitstempel, Signatur — unbefristet, solange die Anmelde-Kennung auf der Gästeliste steht). Beide Prüfstellen (Go-Dienst und Frontend-Server) zerlegen von rechts, damit eine Nutzerkennung mit Punkt nicht zu unterschiedlichen Ergebnissen führt. Ein gültiges altes Merkmal wird beim nächsten Aufruf still durch ein neues ersetzt (neuer Eintrag in der Gästeliste, neues Cookie im Antwort-Header) — ohne dass sich der Nutzer erneut anmelden muss.

Die Gästeliste liegt in einer eigenen Datei `data/users/<user_id>/sessions.json`, getrennt vom Nutzer-Datensatz: ein gleichzeitiger Schreibvorgang auf den Nutzer-Datensatz (der stets das ganze Objekt zurückschreibt) kann so einen Widerruf nicht überschreiben, und das Anlegen einer Anmeldung löst nicht bei jedem Login den Schema-Backup-Hook für `model.User` aus. Eine Pro-Nutzer-Sperre (Mutex-Pool mit Referenzzählung, Vorbild `briefing_lock.go`) serialisiert Lesen-Ändern-Schreiben auf dieser Datei je Nutzer.

Kein Zwischenspeicher: jede authentifizierte Anfrage liest die Gästeliste direkt von der Platte. Begründung: real existierende Nutzer-Datensätze sind wenige hundert Byte groß, der Lesevorgang aus dem Betriebssystem-Cache fällt gegenüber allem anderen in der Anfrage nicht ins Gewicht — ein Zwischenspeicher wäre ein zweiter Zustandsbehälter, der genau die Widerrufs-Zusicherung tragen müsste, auf der die unbefristete Anmeldung beruht, und der billigste Weg, ihn nie falsch werden zu lassen, ist, ihn nicht zu haben.

## Expected Behavior

- **Input:** Anmeldung über einen der sechs Anmeldewege (Passwort, Magic-Link, Google, Passkey-Login, Passkey-Login ohne Kennungseingabe, Passkey-Registrierung); Abmelde-Aufruf (ein Gerät oder alle Geräte); Passwortwechsel oder Passwort-Zurücksetzen; jede authentifizierte Anfrage mit einem Anmelde-Merkmal im Cookie.
- **Output:** Erfolgreiche Anmeldung liefert ein vierteiliges Anmelde-Merkmal im `Set-Cookie`-Header. Eine authentifizierte Anfrage mit gültigem, gelistetem Merkmal liefert den regulären Antwortcode; mit widerrufenem, manipuliertem oder abgelaufenem Alt-Merkmal liefert sie 401.
- **Side effects:** Jede Anmeldung schreibt einen neuen Eintrag in `data/users/<user_id>/sessions.json`. Abmelden (ein Gerät) entfernt genau diesen Eintrag. „Auf allen Geräten abmelden", Passwortwechsel und Passwort-Zurücksetzen leeren die gesamte Liste des Nutzers. Diese Effekte überstehen einen Dienst-Neustart, weil sie dateibasiert sind, nicht prozesslokal.

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

- **AC-10:** Given ein Nutzer besitzt noch ein gültiges Anmelde-Merkmal im alten dreiteiligen Format / When er damit einen Request stellt / Then wird der Request angenommen und er erhält im selben Zug ein neues vierteiliges Anmelde-Merkmal, ohne sich neu anmelden zu müssen.
  - Test: Request mit einem gültigen dreiteiligen Alt-Cookie an einen geschützten Endpunkt → 200 und Antwort enthält einen neuen `Set-Cookie`-Header mit vierteiligem Anmelde-Merkmal; kein Sprung auf die Anmelde-Seite.

- **AC-11:** Given ein Anmelde-Merkmal im alten Format ist älter als 24 Stunden / When damit ein Request gestellt wird / Then wird er abgewiesen.
  - Test: Request mit einem dreiteiligen Alt-Cookie, dessen Zeitstempel mehr als 24 Stunden zurückliegt, an geschützten Endpunkt → 401.

- **AC-12:** Given ein Anmelde-Merkmal wurde verändert oder trägt eine Anmelde-Kennung, die nicht auf der Gästeliste steht / When damit ein Request gestellt wird / Then wird er in beiden Fällen abgewiesen.
  - Test: (a) Request mit einem Cookie, dessen Signatur-Segment einzeln verändert wurde → 401. (b) Request mit einem korrekt signierten Cookie, dessen Anmelde-Kennung nicht in der Gästeliste des Nutzers enthalten ist → 401.

- **AC-13:** Given ein Nutzer meldet sich über einen der sechs Anmeldewege an (Passwort, Magic-Link, Google, Passkey-Login, Passkey-Login ohne Kennungseingabe, Passkey-Registrierung) / When die Anmeldung abgeschlossen ist / Then besteht das jeweils ausgestellte Anmelde-Merkmal die eigene Prüfung.
  - Test: Für jeden der sechs Wege einzeln: Anmeldung über den jeweiligen Endpunkt auslösen, danach mit dem ausgestellten Cookie einen geschützten Endpunkt aufrufen → 200 in allen sechs Fällen.

- **AC-14:** Given ein Anmelde-Merkmal, dessen Nutzerkennung einen Punkt enthält / When der Go-Dienst und der Frontend-Server dasselbe Merkmal zerlegen / Then lesen beide dieselbe Nutzerkennung heraus und weisen es beide nicht ab.
  - Test: Ein Konto mit einer Kennung wie `alice.smith` direkt im Datenbestand anlegen (die Registrierung lässt Punkte nicht zu, die Zerlegungsregel muss trotzdem auf beiden Seiten gleich sein), dafür ein Merkmal ausstellen und dasselbe Merkmal beiden Prüfstellen vorlegen → beide liefern `alice.smith`, keine weist ab. Heute liefert die Go-Seite hier eine Ablehnung.

- **AC-15:** Given mehrere Änderungen an den Anmeldungen desselben Nutzers laufen gleichzeitig / When sie parallel abgesetzt werden / Then geht keine davon verloren.
  - Test: (a) Zwei Anmeldungen desselben Kontos parallel auslösen → danach sind **beide** Merkmale gültig (keins hat das andere aus der Gästeliste verdrängt). (b) „Alle abmelden" parallel zu einer Profiländerung desselben Nutzers → danach ist das vorher gültige Merkmal abgewiesen **und** die Profiländerung ist gespeichert.

- **AC-16:** Given ein Nutzer ist angemeldet / When sein Konto gelöscht wird / Then wird sein Anmelde-Merkmal ungültig und bleibt es auch nach einem echten Dienst-Neustart.
  - Test: Login (Cookie A), Konto-Löschung auslösen, Request mit Cookie A → 401; Dienst real neu starten; Request mit Cookie A erneut → weiterhin 401.

- **AC-17:** Given ein angemeldeter Nutzer ist auf der Konto-Seite / When er „Auf allen Geräten abmelden" anklickt und den Bestätigungsschritt bestätigt / Then wird er auf die Anmelde-Seite geleitet.
  - Test: Browser-Test — Klick auf den Button öffnet einen Bestätigungsdialog; nach Bestätigen landet die Seite auf der Anmelde-Route.

- **AC-18:** Given ein Nutzer meldet sich an / When das Cookie im Browser gesetzt wird / Then bleibt es über das Schließen des Browsers hinaus gespeichert und trägt eine Lebensdauer, die die alte 24-Stunden-Grenze deutlich übersteigt.
  - Test: Der `Set-Cookie`-Header **jeder** der sechs Anmeldewege trägt eine Lebensdauer von mindestens einem Jahr. Der bisherige Wert (24 Stunden) darf diesen Nachweis nicht bestehen — ein Test, der jede beliebige Lebensdauer durchgehen lässt, prüft nichts.

## Known Limitations

- Der Frontend-Server prüft weiterhin nur Signatur und Format des Anmelde-Merkmals, nicht die Gästeliste (er hat keinen Zugriff auf den Nutzer-Datenbestand). Nach einem Widerruf entsteht dadurch ein kurzes Fenster: die Seite lädt, die Daten fehlen (die Ladefunktion bekommt vom Go-Dienst 401 und liefert leere Daten), bis der nächste Klick den harten Sprung auf die Anmelde-Seite auslöst. Keine Umleitungsschleife — entspricht dem heutigen Verhalten der bestehenden Sperrliste.
- Ein Nutzer, der 24 Stunden lang ausschließlich Seiten betrachtet und nie eine Aktion auslöst, behält bis dahin sein altes dreiteiliges Anmelde-Merkmal: das neue Cookie erreicht den Browser nur bei Antworten, die er direkt erhält, nicht bei Ladefunktionen, die der Frontend-Server im Hintergrund stellt. Danach muss er sich einmalig neu anmelden — genau wie heute auch.
- Keine Geräteliste in dieser Scheibe (kein „angemeldet auf 3 Geräten seit …" in der Oberfläche). Die Gästeliste macht das später ohne Umbau möglich.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0060
- **Rationale:** Löst ADR-0030 ab, weil eine unbefristete Anmeldung ohne wirksamen, neustart-festen Widerruf ein unbegrenzt gültiges, einmal abgegriffenes Cookie bedeuten würde. Eine dateibasierte Gästeliste je Nutzer (statt eines reinen Generationszählers) ist die einzige der zwei geprüften Varianten, die sowohl „ein Gerät abmelden" als auch „alle Geräte abmelden" ohne zwei parallele Mechanismen abdeckt.

## Changelog

- 2026-09-05: Initial spec created (#2129)
