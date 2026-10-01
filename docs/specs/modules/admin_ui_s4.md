---
entity_id: admin_ui_s4
type: module
created: 2026-09-30
updated: 2026-09-30
status: draft
version: "1.0"
tags: [admin, frontend, sveltekit, tier, kontosperre, navigation, epic-2138]
---

# Admin-Rolle S4: Minimal-UI `/admin` (Nutzerliste, Tier, Konto sperren)

## Approval

- [ ] Approved

## Purpose

Die Admin-API (S3) ist live, aber ein Admin kann sie nur per Kommandozeile bedienen. Diese
Scheibe liefert die Oberfläche dazu: eine Seite `/admin` mit Nutzerliste, Tier-Auswahl
(Freigabe offener Tier-Anträge ist der Hauptanlass) und Konto sperren/entsperren, dazu einen
Navigationseintrag „Admin", der nur für Admins sichtbar ist. Scheibe S4 von vier in Issue
#2155 (Epic #2138); reine Frontend-Arbeit, das Backend bleibt unverändert und ist weiterhin
die eigentliche Sperre.

## Source

- **File:** `frontend/src/routes/admin/+page.server.ts` (neu),
  `frontend/src/routes/admin/+page.svelte` (neu), `frontend/src/lib/admin.ts` (neu),
  `frontend/src/routes/+layout.server.ts`, `frontend/src/routes/+layout.svelte`,
  `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`,
  `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte`,
  `frontend/src/routes/account/+page.svelte`, `frontend/src/lib/types.ts`
- **Identifier:** `load` (Admin-Seite, neu), `isAdmin` (Layout-Daten, neu), Typ `AdminUser`
  (neu), `TIER_LABELS` (zentral, neu in `lib/admin.ts`), `adminErrorText` (neu)

> **Schicht-Hinweis:** Nur Frontend (SvelteKit). Kein Eingriff in Go-API oder Python-Core.
> Die Seite ruft die drei Routen aus S3 (`docs/reference/api_contract.md`, Abschnitt
> „Admin-API Nutzerverwaltung") und liest die Rolle aus `GET /api/auth/profile` (Feld `role`,
> S1). Keine Persistenzänderung, daher kein Schema-Backup-Hook.

## Scope

### Ziele

- Admin sieht den Eintrag „Admin" in der Navigation (Desktop: Sidebar; mobil: Konto-Sheet,
  weil die Tabbar voll ist); Nicht-Admins sehen ihn nicht.
- `/admin` zeigt die Nutzerliste mit den DTO-Feldern, hebt einen offenen Tier-Antrag hervor
  und erlaubt Tier ändern sowie Sperren/Entsperren.
- Direktaufruf von `/admin` durch einen Nicht-Admin wird serverseitig abgewiesen; Go bleibt
  die echte Sperre (Frontend-Prüfung ist Komfort, kein Schutz).
- Fehler (403, 404, 409 `cannot_disable_self`, 400) erscheinen in Klartext, nie still.
- Tier-Bezeichnungen kommen aus EINER zentralen Konstante.

### Nicht-Ziele

- **Keine Backend-Änderungen** (Go/Python), keine neuen Endpunkte.
- Kein Nutzer anlegen, kein Nutzer löschen, kein Passwort-Reset.
- Kein Entziehen oder Vergeben von Adminrechten (`GZ_ADMIN_USER_IDS` bleibt Betriebskonfiguration, ADR-0078).
- Keine Anzeige über die DTO-Felder hinaus (keine Hashes, Tokens, Passkeys).
- Keine Suche, Sortierung, Paginierung (Minimal-UI).
- **Betriebshinweis, kein Code:** Auf Produktion ist `GZ_ADMIN_USER_IDS` derzeit leer, dort
  sieht also niemand den Eintrag oder die Seite. Das Setzen der Variable ist eine
  Betriebsaufgabe des PO und nicht Teil dieser Scheibe. Auf Staging ist das Konto
  `gz-staging-admin` Admin (`.claude/staging_admin.env`).

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `frontend/src/routes/+layout.server.ts` | MODIFY | `isAdmin` aus `profile.role === 'admin'` im vorhandenen Profil-Abruf, kein Zusatzabruf |
| `frontend/src/routes/+layout.svelte` | MODIFY | `isAdmin` an Sidebar und KontoSheet weiterreichen |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | MODIFY | Nav-Eintrag „Admin" nur bei `isAdmin` (Desktop) |
| `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte` | MODIFY | Link „Admin" nur bei `isAdmin` (mobil; `BottomNav.svelte` bleibt unverändert) |
| `frontend/src/routes/admin/+page.server.ts` | CREATE | Load: Rolle prüfen, Nicht-Admin abweisen, Nutzerliste holen |
| `frontend/src/routes/admin/+page.svelte` | CREATE | Liste, Tier-Dropdown, Sperren/Entsperren mit ConfirmDialog, Fehleranzeige |
| `frontend/src/lib/admin.ts` | CREATE | Reine Helfer: `TIER_LABELS`, `adminErrorText`, Zeilen-Ersetzung |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Lokale `TIER_LABELS` (Z. 124) durch die zentrale Konstante ersetzen |
| `frontend/src/lib/types.ts` | MODIFY | Typ `AdminUser` (neben `UserTier`, Z. 712) |
| `frontend/src/routes/admin/__tests__/admin_seite_zugriff.test.ts` | CREATE | `node --test`: Load Admin vs. Nicht-Admin |
| `frontend/src/routes/admin/__tests__/admin_hilfen.test.ts` | CREATE | `node --test`: reine Helfer aus `lib/admin.ts` |
| `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts` (+ Config/Setup nach Bestandsmuster `konto-naechste-pruefung.*`) | CREATE | Playwright gegen Staging mit `gz-staging-admin` |
| `docs/specs/modules/admin_ui_s4.md` | CREATE | diese Spec |

### Estimated Changes

- Files: ca. 10 produktiv plus Tests
- LoC: ca. +350/-5; das Limit von 250 wird voraussichtlich überschritten ⇒
  `workflow.py set-field loc_limit_override 500`; `docs/`/`*.md` zählen nicht.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Admin-API S3 (`internal/handler/admin_users.go`, Routen `internal/router/router.go`) | dependency | Liste, Tier, Sperre; Fehlercodes und DTO laut `api_contract.md` |
| `GET /api/auth/profile` (`profileRole`, `internal/handler/auth.go`) | dependency | Feld `role` ⇒ `isAdmin` |
| `frontend/src/routes/api/[...path]/+server.ts` | dependency | Proxy, reicht 403/404/409/400 unverändert durch |
| `frontend/src/lib/server/apiBase.ts` (`apiBase`) | dependency | Go-Basisadresse im Server-Load |
| `frontend/src/routes/account/+page.server.ts` | reference-pattern | `load({cookies})` mit Cookie `gz_session` |
| `frontend/src/lib/components/atoms` (`Switch`, `Pill`, `Btn`, `Card`, `PageHeader`, `Dot`) | dependency | Bauteile der Seite |
| `frontend/src/lib/components/molecules/ConfirmDialog.svelte` | dependency | Bestätigung vor dem Sperren |
| `frontend/src/lib/components/ui/select/Select.svelte` | dependency | Tier-Auswahl, nur über atoms/molecules eingebunden, falls dort gekapselt (Import-Guard) |
| `issue_470_atom_import_guard.test.ts` | dependency | Import-Guard: Seiten importieren nicht direkt aus `ui/` |
| `frontend/src/routes/account/__tests__/premium_sms_link_code_load.test.ts`, `server-load-resolve.hooks.mjs` | reference-pattern | Vorlage für Load-Tests mit `node --test` |
| `.claude/staging_admin.env`, `tests/helpers/staging_admin_session.py` | reference-pattern | Staging-Admin `gz-staging-admin` |
| ADR-0078 (Admin-Rolle), ADR-0080 (Kontosperre) | reference-pattern | Begriffe, Reichweite der Sperre |

## Implementation Details

1. **Layout-Daten.** `+layout.server.ts` liest `role` aus demselben Profil-Abruf wie
   `displayName` und `hasPasskey` und liefert `isAdmin: profile?.role === 'admin'`. Fehlt das
   Profil, ist `isAdmin` `false` (fail-closed für die Sichtbarkeit).
2. **Navigation.** `Sidebar.svelte` hängt an das feste `navItems` einen Eintrag „Admin"
   (`/admin`) nur bei `isAdmin` an. Mobil bekommt `KontoSheet.svelte` einen zusätzlichen Link
   nur bei `isAdmin`; `BottomNav.svelte` bleibt unverändert, weil sie voll ist.
3. **Zugriffsschutz.** `admin/+page.server.ts` holt mit Cookie `gz_session` das Profil und
   weist bei `role !== 'admin'` mit 403 ab, ohne die Nutzerliste zu laden. Antwortet Go auf die
   Liste mit 401/403, wird ebenfalls abgewiesen. Das ist Komfort und verhindert eine leere
   Seite; die eigentliche Sperre bleibt `requireAdmin` in Go.
4. **Liste.** Der Load liefert `{users: AdminUser[]}` aus `GET /api/admin/users`. Die Seite
   zeigt je Zeile: Anzeigename/Kennung, E-Mail, Tier (Bezeichnung aus `TIER_LABELS`), offenen
   Antrag (`requested_tier` mit `requested_at`) deutlich hervorgehoben, Sperrstatus, Testnutzer-
   Markierung, letzten Trip-Report-Lauf (`last_trip_report_run`, `null` ⇒ „kein Lauf"). Nur
   DTO-Felder, nichts darüber hinaus.
5. **Mutationen im Client** (Projektmuster, keine Form-Actions): `fetch` auf
   `/api/admin/users/{id}/tier` bzw. `/disabled` mit `PUT`. Die Antwort (`AdminUser`) ersetzt
   die Zeile per reinem Helfer; es gibt kein Neuladen der ganzen Liste und keine optimistische
   Anzeige vor der Antwort. Bei Fehler bleibt die Zeile unverändert und der Fehlertext steht
   sichtbar an der Zeile.
6. **Sperren mit Bestätigung.** Sperren öffnet `ConfirmDialog` mit Hinweis, dass alle
   Sitzungen des Kontos enden; Entsperren braucht keine Bestätigung. Für das eigene Konto wird
   das Sperren nicht angeboten bzw. ist deaktiviert; kommt trotzdem 409 `cannot_disable_self`,
   erscheint die Klartext-Meldung.
7. **Fehlertexte.** `adminErrorText(status, code)` bildet ab: 403 `forbidden` („Keine
   Berechtigung"), 404 `not_found` („Nutzer nicht gefunden"), 409 `cannot_disable_self`
   („Das eigene Konto kann nicht gesperrt werden"), 400 `invalid_tier`/`invalid_request`
   („Ungültige Eingabe"), sonst eine allgemeine Meldung.
8. **Zentrale Tier-Konstante.** `TIER_LABELS` (`free`, `standard`, `premium`) liegt in
   `lib/admin.ts`; `account/+page.svelte` importiert sie und verliert die lokale Kopie. Kein
   Verhaltenswechsel dort (gleiche Bezeichnungen, gleicher Fallback „Free").
9. **Bauteile und Import-Guard (#470).** Die Seite nutzt nur atoms/molecules; kein direkter
   Import aus `ui/`. Kein Compare-/Trip-Pendant betroffen (Verwaltungsseite, kein Editor).
10. **Keine Svelte-Render-Umgebung im Test.** Logik (Zeilenersetzung, Fehlertexte, Labels) steht
    in `lib/admin.ts` und wird dort per `node --test` geprüft; das Zusammenspiel im Browser
    deckt die Playwright-Spec ab.

## Test Plan

Keine Mocks, die nur die eigene Annahme spiegeln; der Load-Test nutzt einen fetch-Ersatz nach
Muster `premium_sms_link_code_load.test.ts`, der das Go-Verhalten nachstellt (Admin-Profil
mit Liste, Nicht-Admin-Profil). Testdateien nach Verhalten benannt.

| Testdatei | Art | Deckt |
|-----------|-----|-------|
| `frontend/src/routes/admin/__tests__/admin_seite_zugriff.test.ts` | Kern, `node --test`, zwei Nutzer | AC-2, AC-3 (Datenform) |
| `frontend/src/routes/admin/__tests__/admin_hilfen.test.ts` | Kern, `node --test` | AC-4, AC-6, AC-7 |
| Bestehender Import-Guard `issue_470_atom_import_guard.test.ts` | Kern | AC-8 |
| `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts` | Live-E2E gegen Staging | AC-1, AC-2, AC-4, AC-5, AC-6, AC-9 |

### Automated Tests (TDD RED)

- [ ] GIVEN zwei Nutzer, Profil A mit `role: "admin"`, Profil B mit `role: "user"` WHEN der Load
  der Admin-Seite für B läuft THEN wird mit 403 abgewiesen und die Liste wird nicht abgerufen;
  für A liefert er die Nutzerliste.
- [ ] GIVEN eine Liste mit Nutzer X und Y WHEN die Antwort `AdminUser` für X eingeht THEN
  ersetzt der Helfer nur die Zeile von X und Y bleibt identisch.
- [ ] GIVEN die Fehlerfälle 403, 404, 409 `cannot_disable_self` und 400 WHEN `adminErrorText`
  aufgerufen wird THEN liefert er je einen eigenen Klartext und nie den rohen Code.
- [ ] GIVEN die Werte `free`, `standard`, `premium` WHEN `TIER_LABELS` gelesen wird THEN
  stimmen die Bezeichnungen mit der bisherigen Konto-Seite überein.
- [ ] GIVEN Staging mit `gz-staging-admin` WHEN die Seite bedient wird THEN gelten die ACs 1, 4,
  5, 6 und 9 im Browser.

**Mutations-Gegenprobe (Pflicht für den Adversary):** `isAdmin`-Ableitung auf `true` fest ⇒
AC-1/AC-2 rot; Rollenprüfung im Load entfernt ⇒ AC-2 rot; Zeilenersetzung ersetzt alle Zeilen
⇒ AC-4 rot; 409-Text entfernt ⇒ AC-6 rot; lokale `TIER_LABELS` wieder eingeführt ⇒ AC-7 rot
(Test prüft, dass `account/+page.svelte` die zentrale Konstante importiert, als
`# doc-compliance-test`). Mutation nur per String-Ersetzung mit externer Sicherungskopie.

**Staging-Nachweis:** Playwright mit `gz-staging-admin` und einem Nicht-Admin-Konto
(Zwei-Nutzer-Test). Der Staging-Datenbestand ist für `hem` nicht lesbar; nicht Messbares wird
als `NOT_MEASURABLE_ON_STAGING` gemeldet, kein PASS erfunden. Gesperrt wird nur ein
Test-Konto, nie ein echter Nutzer.

## Expected Behavior

- **Input:** Admin-Sitzung bzw. Nicht-Admin-Sitzung; Klicks auf Tier-Auswahl,
  Sperren/Entsperren.
- **Output:** Nav-Eintrag nur für Admins; `/admin` mit Liste; aktualisierte Zeile aus der
  Serverantwort; Klartext-Fehler.
- **Side effects:** Nur die der S3-Endpunkte (Tier gesetzt, Antrag gelöscht; Flag gesetzt und
  Sitzungen geleert). Das Frontend schreibt nichts selbst.

## Acceptance Criteria

- **AC-1:** Given ein Admin und ein Nicht-Admin, jeweils angemeldet / When beide die App am
  Desktop öffnen und der Admin zusätzlich das Konto-Sheet auf dem Smartphone öffnet / Then
  sieht der Admin den Eintrag „Admin" in der Seitenleiste und im Konto-Sheet, der Nicht-Admin
  sieht ihn an keiner der beiden Stellen, und die Tabbar ist unverändert.
  - Test: `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts`

- **AC-2:** Given ein Admin und ein Nicht-Admin / When der Nicht-Admin `/admin` direkt in der
  Adresszeile aufruft / Then wird er serverseitig mit 403 abgewiesen und sieht keine
  Nutzerdaten, während der Admin dieselbe Adresse mit der Nutzerliste sieht; die Go-API
  antwortet dem Nicht-Admin auf `/api/admin/users` weiterhin selbst mit 403.
  - Test: `frontend/src/routes/admin/__tests__/admin_seite_zugriff.test.ts` (Zwei-Nutzer-Test),
    `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts`

- **AC-3:** Given eine Nutzerliste, in der ein Nutzer einen Tier-Antrag (`requested_tier`)
  offen hat / When der Admin `/admin` öffnet / Then zeigt jede Zeile Kennung, E-Mail, Tier,
  Sperrstatus und letzten Trip-Report-Lauf aus den DTO-Feldern, der offene Antrag ist deutlich
  hervorgehoben, und es erscheint kein Feld außerhalb des DTO (kein Hash, kein Token).
  - Test: `frontend/src/routes/admin/__tests__/admin_seite_zugriff.test.ts`,
    `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts`

- **AC-4:** Given ein Nutzer mit Tier `free` und offenem Antrag auf `premium` / When der Admin
  im Tier-Dropdown `premium` wählt / Then wird `PUT /api/admin/users/{id}/tier` gesendet, die
  Zeile wird durch die Antwort (`AdminUser`) ersetzt und zeigt `premium` ohne Antrag, und alle
  anderen Zeilen bleiben unverändert; scheitert der Aufruf, bleibt die Zeile unverändert und
  der Fehler steht sichtbar an der Zeile.
  - Test: `frontend/src/routes/admin/__tests__/admin_hilfen.test.ts`,
    `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts`

- **AC-5:** Given ein aktives Test-Konto in der Liste / When der Admin „Sperren" klickt / Then
  öffnet sich zuerst ein Bestätigungsdialog, erst nach Bestätigung geht
  `PUT /api/admin/users/{id}/disabled` mit `{"disabled":true}` ab und die Zeile zeigt „gesperrt";
  „Entsperren" setzt `{"disabled":false}` ohne Dialog, und Abbrechen im Dialog sendet nichts.
  - Test: `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts`

- **AC-6:** Given die Fehlerantworten 403, 404, 409 `cannot_disable_self` und 400 der Admin-API
  / When die Seite eine davon erhält / Then zeigt sie einen eigenen verständlichen deutschen
  Text (nie den rohen Fehlercode), und will der Admin sein eigenes Konto sperren, wird dies
  nicht angeboten bzw. mit der Meldung „Das eigene Konto kann nicht gesperrt werden"
  sichtbar abgelehnt.
  - Test: `frontend/src/routes/admin/__tests__/admin_hilfen.test.ts`,
    `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts`

- **AC-7:** Given die Tier-Bezeichnungen `free`, `standard`, `premium` / When Konto-Seite und
  Admin-Seite sie anzeigen / Then stammen beide aus EINER zentralen Konstante `TIER_LABELS`
  in `frontend/src/lib/admin.ts`, `account/+page.svelte` enthält keine eigene Kopie mehr, und
  die Bezeichnungen auf der Konto-Seite sind unverändert.
  - Test: `frontend/src/routes/admin/__tests__/admin_hilfen.test.ts`

- **AC-8:** Given die neue Admin-Seite und die geänderten Navigationsbauteile / When der
  Import-Guard `issue_470_atom_import_guard.test.ts` läuft / Then ist er grün, weil die Seite
  nur Bauteile aus atoms/molecules importiert und nichts direkt aus `ui/`.
  - Test: `frontend/src/lib/issue_470_atom_import_guard.test.ts` (Bestand)

- **AC-9:** Given der Staging-Stand dieser Scheibe / When die Playwright-Spec mit dem Konto
  `gz-staging-admin` und einem Nicht-Admin-Konto läuft / Then bestehen Nav-Sichtbarkeit,
  Direktaufruf-Abweisung, Liste, Tier ändern, Sperren mit Dialog und Entsperren eines
  Test-Kontos, und nicht Messbares ist als `NOT_MEASURABLE_ON_STAGING` benannt.
  - Test: `frontend/e2e/admin-nutzerverwaltung.staging.spec.ts` (Nachweis im Deploy-Schritt `/e2e-verify`)

## Known Limitations

- **Frontend-Sichtbarkeit ist kein Schutz.** Wer die Adresse kennt, wird serverseitig
  abgewiesen; die Daten schützt `requireAdmin` in Go.
- **Lost Update bei Sperre/Tier** (S3, ADR-0080): Die Liste zeigt den Ist-Zustand der Antwort;
  geht eine Sperre durch parallele Profil-Schreiber verloren, sieht der Admin das und wiederholt.
- **Produktion:** `GZ_ADMIN_USER_IDS` ist leer, die Seite ist dort für niemanden erreichbar, bis
  der PO die Variable setzt (Betriebsaufgabe).
- **Issue #2155** schließt mit S4 erst nach Staging-Nachweis, Prod-Deploy und Selftest Exit 0.

## Changelog

- 2026-09-30: Initial spec created (#2155 S4)
