---
entity_id: passkey_konto_verwaltung
type: module
created: 2026-09-08
updated: 2026-09-08
status: draft
version: "1.0"
tags: [sveltekit, auth, webauthn, passkey, account, multi-user]
---

<!-- Issue #2246 — Scheibe 1 von #2199 (Epic „Passkey-UI wieder sichtbar machen") -->

# Passkey-Konto-Verwaltung

## Approval

- [x] Approved (PO, 2026-09-08)

## Purpose

Auf der Konto-Seite bekommt der Nutzer eine eigene Karte für seine Passkeys (Face ID, Touch
ID, Windows Hello, Sicherheitsschlüssel): er sieht dort, welche er schon hat, kann einen
neuen anlegen und einen bestehenden einzeln entfernen. Diese Karte existiert heute nicht —
ohne sie kann niemand überhaupt einen Passkey anlegen, egal was der Rest des Passkey-Systems
schon kann. Sie ist deshalb die Grundlage, auf der die spätere Passkey-Anmeldung (#2199,
Folge-Scheiben) erst aufbauen kann.

## Source

- **File:** `frontend/src/routes/account/+page.svelte` — neue Karte, eingefügt zwischen der
  bestehenden Karte „Kanäle" (endet Zeile 475) und der Karte „Passwort ändern" (beginnt
  Zeile 477)
- **Identifier:** neue `Card.Root`-Sektion mit `data-testid="passkeys-card"`

### Weitere betroffene Dateien

- **File:** `frontend/src/lib/passkey.ts` (MODIFY) — `RegisteredPasskey`-Interface um
  `authenticator_name` und `last_used_at` ergänzen; neuer Helfer zum Auflisten bzw. Nutzung
  des bereits vorhandenen `deletePasskey()` aus der neuen Karte heraus
- **File:** `frontend/e2e/passkey-konto.spec.ts` (CREATE) — oberflächenechter Nachweis mit
  virtuellem Authentifikator
- **File:** `frontend/e2e/run-passkey-konto.sh` (CREATE) — fährt die Prüfstrecke in **zwei**
  Playwright-Aufrufen mit Go-Neustart dazwischen. Grund (gemessen 2026-09-09): ein Lauf am
  Stück braucht 38 limitierte Passkey-Anfragen, erlaubt sind 30/Stunde je IP
  (`internal/router/router.go:94`) — 8 × HTTP 429, und der Fehlschlag zeigt sich
  irreführend als „Passkey erscheint nicht in der Liste" statt als Limit-Meldung. Vorbild
  für die Aufteilung: `bug-703-login-ratelimit.spec.ts`, das in der CI ebenfalls einen
  eigenen nachgelagerten Aufruf bekommt.

> **Schicht-Hinweis:** Diese Scheibe ist **ausschließlich Frontend-Arbeit**
> (`frontend/src/...`, SvelteKit). Es wird **kein** Go-Code (`internal/`, `cmd/`) und **kein**
> Python-Code (`api/`, `src/`) geändert — alle benötigten Endpunkte existieren bereits und
> sind seit #2130 in Produktion funktionsfähig. Bestätigt per Grep: `toProfileResponse`
> (`internal/handler/auth.go:602`) liefert die Passkey-Felder schon vollständig, der
> Delete-Handler (`internal/handler/passkey.go:372`) ist bereits verdrahtet
> (`internal/router/router.go:116`).

## Estimated Scope

- **LoC:** ~190–250
- **Files:** 2 MODIFY (`account/+page.svelte`, `lib/passkey.ts`) + 1–2 CREATE (Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/auth/profile` | Go-API-Endpoint (bereits vorhanden) | Liefert `has_passkey` und `passkeys[]` (`id`, `label`, `authenticator_name`, `created_at`, `last_used_at`) — einzige Datenquelle der Karte, kein neuer Lese-Endpoint nötig |
| `DELETE /api/auth/passkey/credentials/{id}` | Go-API-Endpoint (bereits vorhanden) | Entfernt genau das Credential mit der übergebenen `id` (identisch mit dem `id`-Feld aus der Profil-Antwort) |
| `POST /api/auth/passkey/register/begin` und `/finish` | Go-API-Endpoint (bereits vorhanden) | Zeremonie-Endpunkte für das Anlegen; werden bereits von `registerPasskey()` in `frontend/src/lib/passkey.ts:32` gekapselt |
| `frontend/src/lib/passkey.ts` | Frontend-Modul (bereits vorhanden, 155 Zeilen) | `isWebAuthnSupported()` und `registerPasskey(label)` sind fertig, haben aber heute null Aufrufer im gesamten Frontend — diese Scheibe verdrahtet sie erstmals |
| `@github/webauthn-json` | npm-Paket (bereits installiert) | Browser-WebAuthn-Wrapper, hinter `lib/passkey.ts` verborgen — die Karte ruft ihn nie direkt auf |
| IP-Rate-Limit Passkey-Routen (`internal/router/router.go:94`) | Bestehende Infrastruktur | 30 Anfragen/Stunde je IP über alle Passkey-Routen; bei wiederholten Testläufen gegen denselben lokalen Stack zu beachten (kein Änderungsbedarf dieser Scheibe, nur Nachweis-Risiko) |

## Implementation Details

Neue Karte nach dem Muster der Nachbarkarten (`Card.Root` / `Card.Header` / `Card.Title` /
`Card.Content`), `data-testid="passkeys-card"`, Reihenfolge: Titel, dann Liste (oder
Leerzustand-Hinweis), dann der Anlegen-Bereich.

**Datenquelle.** Die Passkey-Liste kommt aus `data.profile.passkeys` — das Profil wird auf
dieser Seite bereits geladen (`data.profile?.id`, `data.profile?.mail_to` etc. werden schon
verwendet, siehe Zeile 19 ff.). Kein zusätzlicher Fetch beim Laden der Seite nötig, nur nach
erfolgreichem Anlegen/Löschen ein erneuter Abruf (Muster: `invalidateAll()`, das die Seite
bereits importiert, siehe Zeile 7).

**Liste.** Pro Eintrag: als Bezeichnung das vom Nutzer vergebene `label`; zusätzlich —
falls vorhanden — der aus der AAGUID abgeleitete Gerätename `authenticator_name`
(Klarname, z.B. „iCloud Keychain"). Ist kein Label vergeben (es ist freiwillig), tritt
der Gerätename an dessen Stelle; fehlt auch der, steht dort ein neutraler Platzhalter.
Grund für diese Reihenfolge (nach TDD RED am laufenden Stack gemessen):
`authenticator_name` steht in der Profil-Antwort auf `omitempty`
(`internal/handler/auth.go:597`) und fehlt bei unbekannter oder Null-AAGUID vollständig —
als alleinige Bezeichnung wäre die Zeile dann namenlos. Zudem hätten zwei Passkeys
desselben Geräts denselben Gerätenamen und wären für den Nutzer nicht auseinanderzuhalten.
Weiter: Anlagedatum
über den vorhandenen `formatDate()`-Helfer (Zeile 189), sowie „zuletzt verwendet" — nur wenn
`last_used_at` gesetzt ist; fehlt das Feld (nie benutzter Passkey), erscheint dort kein
erfundenes Datum, sondern ein Platzhalter oder gar keine Zeile für „zuletzt verwendet".
Löschen je Eintrag über einen Button, der **zuerst eine Rückfrage** öffnet (Muster:
vorhandener `Dialog.Root` auf dieser Seite, wie beim Löschen eines Wetterprofils) und erst
nach Bestätigung `deletePasskey(id)` aus `lib/passkey.ts` aufruft und danach die Liste
aktualisiert (`invalidateAll()`). Grund (PO-Entscheid 2026-09-08): Das Entfernen eines
Passkeys ist nicht umkehrbar — der Nutzer muss ihn am Gerät neu anlegen —, und jede andere
destruktive Aktion auf dieser Seite fragt ebenfalls nach. Abbrechen lässt den Passkey
unangetastet, auch serverseitig.

**Leerzustand.** Hat der Nutzer keinen Passkey (`data.profile.passkeys` leer oder
`has_passkey === false`), erscheint statt der Liste ein kurzer erklärender Text, und der
Anlegen-Weg bleibt trotzdem sichtbar und bedienbar.

**Anlegen.** Ein Knopf öffnet — analog zum bestehenden Muster mit `Dialog.Root` auf dieser
Seite (bereits importiert, Zeile 3) — eine minimale Eingabe für ein Label (freiwillig, wie im
Backend vorgesehen) und ruft dann `registerPasskey(label)` auf. Der Dialog **bleibt während der
laufenden Zeremonie offen** und zeigt einen Wartezustand (Bestätigen-Knopf gesperrt,
erkennbarer Hinweis, dass die Bestätigung am Gerät aussteht); er schließt sich erst, wenn
die Zeremonie beendet ist — erfolgreich oder nicht. Grund (PO-Entscheid 2026-09-08): Ein
Dialog, der sich vor der Geräteabfrage schließt, wirkt, als sei nichts passiert.
Bei Erfolg: Liste aktualisiert
sich ohne Seiten-Neuladen (`invalidateAll()`, kein `window.location.reload()`), Erfolgstext im
bestehenden `successMsg`-Muster (lokaler `$state`-String, nach 4 Sekunden per `setTimeout`
zurückgesetzt, siehe `save()` Zeile 202–217). Bei Fehler (Abbruch, Zeitüberschreitung,
Server-Ablehnung): Fehlertext im bestehenden `errorMsg`-Muster, die Liste bleibt unverändert —
`registerPasskey()` wirft in jedem Fehlerfall, bevor irgendein Zustand auf der Seite verändert
wird.

**Kein WebAuthn.** `isWebAuthnSupported()` (bereits vorhanden in `lib/passkey.ts:17`) wird
beim Mounten geprüft (Muster: vorhandenes `onMount`, Zeile 274). Liefert sie `false`, entfällt
der Anlegen-Knopf; an seiner Stelle steht ein erklärender Hinweistext. Die Karte selbst bleibt
sichtbar — auch ohne WebAuthn-Unterstützung sieht der Nutzer, dass es Passkeys gibt und warum
er hier gerade keinen anlegen kann.

**Label-Änderung.** Nicht Teil dieser Scheibe — siehe „Known Limitations".

## Expected Behavior

- **Input:** Seitenaufruf `/account` (Profil bereits vom Server geladen); Klicks auf
  „Passkey hinzufügen" bzw. auf „Löschen" neben einem Eintrag; optionale Texteingabe für ein
  Label beim Anlegen.
- **Output:** Aktualisierte Liste der Passkeys direkt auf der Seite (kein Reload), deutsche
  Erfolgs-/Fehlermeldungen im bestehenden Muster, bei fehlendem WebAuthn ein Hinweistext statt
  des Anlegen-Knopfs.
- **Side effects:** Anlegen ruft `POST /api/auth/passkey/register/begin` und `/finish` auf und
  legt serverseitig ein neues Credential an; Löschen ruft
  `DELETE /api/auth/passkey/credentials/{id}` auf und entfernt es serverseitig — beides
  bestehende, unveränderte Endpunkte. Kein neuer Netzwerk-Aufruf beim bloßen Anzeigen der
  Karte über das ohnehin geladene Profil hinaus.

## Acceptance Criteria

- **AC-1:** Given der Nutzer öffnet `/account` / When die Seite geladen ist / Then erscheint
  zwischen der Karte „Kanäle" und der Karte „Passwort ändern" eine eigene Karte mit
  `data-testid="passkeys-card"`
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-1: Passkey-Karte steht zwischen den Karten Kanäle und Passwort ändern

- **AC-2:** Given der Nutzer hat zwei Passkeys, einen bereits benutzten und einen noch nie
  benutzten / When er die Konto-Seite öffnet / Then zeigt die Karte für den benutzten
  Passkey seine Bezeichnung, Anlagedatum und ein Datum der letzten Verwendung, und für den
  unbenutzten Passkey seine Bezeichnung und Anlagedatum, aber kein erfundenes Datum der
  letzten Verwendung
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-2: benutzter Passkey zeigt zuletzt verwendet, unbenutzter kein erfundenes Datum

- **AC-3:** Given der Nutzer hat noch keinen Passkey / When er die Konto-Seite öffnet / Then
  zeigt die Karte einen erklärenden Hinweis statt einer Liste, und der Weg zum Anlegen eines
  Passkeys ist trotzdem sichtbar und bedienbar
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-3: Leerzustand zeigt erklärenden Text, Anlegen bleibt bedienbar

- **AC-4:** Given der Nutzer klickt auf der Konto-Seite auf „Passkey hinzufügen" und
  bestätigt die Erstellung an einem (virtuellen) Authentifikator / When die Zeremonie
  erfolgreich abgeschlossen ist / Then erscheint der neue Passkey in der Liste, ohne dass die
  Seite neu geladen wird
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-4: neuer Passkey erscheint ohne Seiten-Neuladen

- **AC-5:** Given der Nutzer klickt auf der Konto-Seite neben einem bestehenden Passkey auf
  „Löschen" / When der Löschvorgang abgeschlossen ist / Then verschwindet der Eintrag aus der
  Liste UND ein anschließender Anmeldeversuch mit genau diesem Credential scheitert — das
  Credential ist nicht nur aus der Anzeige entfernt, sondern serverseitig wirkungslos
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-5: Löschen entfernt den Eintrag und macht das Credential serverseitig wirkungslos

- **AC-6:** Given der Browser des Nutzers unterstützt WebAuthn nicht (`isWebAuthnSupported()`
  liefert `false`) / When er die Konto-Seite öffnet / Then fehlt der Anlegen-Knopf, an seiner
  Stelle steht ein erklärender deutscher Hinweistext, und die Karte selbst bleibt sichtbar
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-6: ohne WebAuthn bleibt die Karte sichtbar, der Anlegen-Knopf entfällt

- **AC-7:** Given der Nutzer bricht die Anlegen-Zeremonie am Authentifikator ab oder sie läuft
  in eine Zeitüberschreitung / When er zuvor auf „Passkey hinzufügen" geklickt hatte / Then
  zeigt die Karte eine verständliche deutsche Fehlermeldung, die Liste bleibt unverändert, und
  es entsteht kein halber bzw. unvollständiger Eintrag
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-7: gescheiterte Zeremonie zeigt eine deutsche Fehlermeldung, die Liste bleibt unverändert

- **AC-8:** Given der Nutzer klickt neben einem bestehenden Passkey auf „Löschen" / When
  die Rückfrage erscheint und er sie abbricht / Then bleibt der Passkey in der Liste UND
  eine Anmeldung mit genau diesem Credential ist weiterhin möglich; erst das Bestätigen der
  Rückfrage entfernt ihn
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-8: Abbrechen der Rückfrage lässt den Passkey anmeldefähig, erst Bestätigen entfernt ihn

- **AC-9:** Given der Nutzer hat im Anlegen-Dialog bestätigt / When die Zeremonie am Gerät
  noch aussteht / Then bleibt der Dialog offen und zeigt einen Wartezustand (Bestätigen
  gesperrt); er schließt sich erst, wenn die Zeremonie beendet ist
  - Test: `frontend/e2e/passkey-konto.spec.ts` → AC-9: der Anlegen-Dialog bleibt während der Zeremonie offen und sperrt "Anlegen" (Schließen nach **erfolgreicher** Zeremonie: AC-4-Test, letzte Zusicherung)

## Known Limitations

- **Kein nachträgliches Umbenennen.** Ein einmal vergebenes Label lässt sich in dieser Scheibe
  nicht mehr ändern — das Backend bietet dafür keinen Endpunkt, und diese Scheibe baut keinen.
  Wer sich umentscheidet, muss den Passkey löschen und neu anlegen.
- **Staging-Nachweis ist eingeschränkt (#2200).** Die RP-ID leitet sich aus `GZ_PUBLIC_HOST`
  ab, das auf Staging nicht gesetzt ist — die echte Passkey-Zeremonie lässt sich dort von Hand
  nicht durchklicken. Der belastbare Nachweis für Anlegen und Löschen läuft deshalb gegen
  einen lokalen Aufbau (E2E mit virtuellem Authentifikator); die Staging-Runde vor dem
  Prod-Deploy darf nur „Karte ist sichtbar und bedienbar, Leerzustand korrekt" belegen, nicht
  „Anlegen funktioniert Ende-zu-Ende".
- **Kein Vor-Deploy-Schutz durch das Frontend-Browser-Gate.** `/account` gehört nicht zu den
  sechs Kernseiten, die dieses Gate automatisch lädt (`/`, `/trips`, `/trips/new`, `/compare`,
  `/compare/new`, `/locations`). Ein Fehler auf dieser Karte würde dort nicht auffallen — der
  in dieser Spec geforderte E2E-Test ist die einzige automatische Absicherung.
- **`frontend/e2e/passkey-regression.spec.ts` ist kein Vorbild für den Nachweis dieser
  Scheibe.** Er fährt die Zeremonie über `page.evaluate` + `fetch` und prüft damit die
  Schnittstelle, nicht die Bedienoberfläche. Für den Aufbau des virtuellen Authentifikators
  (`WebAuthn.enable`, `WebAuthn.addVirtualAuthenticator` mit `ctap2`/`internal`/
  `hasResidentKey`/`isUserVerified`) ist er dagegen brauchbar und sollte übernommen werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe trifft keine neue Grundsatzentscheidung — sie verdrahtet
  ausschließlich bereits gelieferte, dokumentierte Bausteine (Auth-Session-Cookie aus
  ADR-0030, dauerhafte Anmeldung/Widerrufsliste aus ADR-0060) und Endpunkte, die seit #2130
  in Produktion funktionsfähig sind (`docs/specs/modules/passkey_webauthn.md`,
  `docs/specs/modules/passkey_rp_konfiguration.md`). Es entsteht kein neuer Endpunkt, kein
  neues Datenfeld und keine neue Architekturentscheidung, die ein eigenes ADR rechtfertigen
  würde.

## Changelog

- 2026-09-08: Initial spec created — Scheibe 1 von #2199, Issue #2246
- 2026-09-08: Nach TDD RED präzisiert — Bezeichnung in der Liste ist das `label`, der
  Gerätename ergänzt es nur (gemessen: `authenticator_name` fehlt bei Null-AAGUID);
  AC-Test-Mapping auf `frontend/e2e/passkey-konto.spec.ts` eingetragen
- 2026-09-08: PO-Entscheid nach der GREEN-Vorlage — Löschen bekommt eine Rückfrage (AC-8),
  der Anlegen-Dialog bleibt während der Zeremonie mit Wartezustand offen (AC-9)
- 2026-09-09: Adversary Runde 1 (BROKEN) fand drei ungefangene Verfälschungen; dabei zeigte
  sich der `!passkeyBusy`-Wächter in `onOpenChange` als **wirkungslos** — Escape, Außenklick
  und das X schlossen den Anlegen-Dialog mitten in der Zeremonie. Behoben an der Quelle
  (`escapeKeydownBehavior`/`interactOutsideBehavior`/`showCloseButton`), je Weg einzeln
  gegengeprüft. Runde 2: VERIFIED. Lauf-Skript wegen des Rate-Limits ergänzt.
