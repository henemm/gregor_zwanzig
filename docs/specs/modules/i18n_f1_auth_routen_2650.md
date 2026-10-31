---
entity_id: i18n_f1_auth_routen_2650
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2650, frontend, model-haiku]
---

# i18n F1: Katalog-Migration der Auth-Routen (Anmelden, Registrieren, Passwort, Anmeldelink, E-Mail-Bestätigung)

**Issue:** #2650 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt 2, 3

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer sich auf Englisch anmeldet, registriert, sein Passwort zurücksetzt oder einen Anmeldelink anfordert, sieht jede Beschriftung, jeden Hinweis und jede Fehlermeldung der Seite auf Englisch; auf Deutsch bleibt alles Wort für Wort wie heute. Dazu wandern alle Nutzertexte der sechs Auth-Routen in den Katalogbereich `auth` und werden über `$t(...)` bzw. in den Server-Actions über `trFor(locals.lang, ...)` ausgegeben. Meldungen, die die Go-API selbst liefert, bleiben unverändert (Paket G2).

## Source

- **File:** `frontend/src/routes/login/+page.svelte`, `login/+page.server.ts`, `register/+page.svelte`, `register/+page.server.ts`, `forgot-password/+page.svelte`, `forgot-password/+page.server.ts`, `reset-password/+page.svelte`, `reset-password/+page.server.ts`, `magic-link/+page.svelte`, `magic-link/+page.server.ts`, `magic-link/verify/+page.svelte`, `magic-link/verify/+page.server.ts`, `verify-email/+page.svelte`, `verify-email/+page.server.ts`, `frontend/src/lib/i18n/messages/{de,en}/auth.json`
- **Identifier:** `GOOGLE_FEHLERTEXTE` (Map in `login/+page.svelte`), `actions` in den `+page.server.ts`, Schlüsselbereich `auth.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Kein Go-, kein Python-Code. Die Pfade heißen im Repo `routes/login`, `routes/register`, `routes/forgot-password`, `routes/reset-password`, `routes/magic-link` (mit `verify`) und `routes/verify-email`; ein Verzeichnis `routes/(auth)` gibt es nicht. `routes/logout` hat keine Oberfläche und bleibt unberührt.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/routes/login/+page.svelte` | MODIFY | Markup, `title`/`aria-label`/`placeholder`, Passkey- und Google-Fehlertexte aus dem Katalog |
| `frontend/src/routes/login/+page.server.ts` | prüfen | Die Fehlerwerte `Invalid credentials`, `Rate limit exceeded`, `Username and password required`, `email_not_verified` sind Codes, keine Texte; sie bleiben (ein Test erwartet `Invalid credentials`). Die Seite bildet sie auf Katalogtexte ab |
| `frontend/src/routes/register/+page.svelte` | MODIFY | Markup, Einladungs-Hinweise (mit Platzhalter `{level}`), Datenschutz-Hinweis |
| `frontend/src/routes/register/+page.server.ts` | MODIFY | Fehlertexte der Action über `trFor(locals.lang, …)` |
| `frontend/src/routes/forgot-password/+page.svelte`, `+page.server.ts` | MODIFY | Markup und Fehlertext (`Username required` → Katalog) |
| `frontend/src/routes/reset-password/+page.svelte`, `+page.server.ts` | MODIFY | Markup, Fehlertexte „Alle Felder sind erforderlich" und „Passwort muss mindestens 8 Zeichen haben" |
| `frontend/src/routes/magic-link/+page.svelte`, `+page.server.ts`, `magic-link/verify/+page.svelte`, `+page.server.ts` | MODIFY | Markup, Fehlertexte „E-Mail-Adresse erforderlich", „E-Mail und Code erforderlich" |
| `frontend/src/routes/verify-email/+page.svelte`, `+page.server.ts` | MODIFY | Markup, Fehlertexte „Ungültiger Bestätigungslink." und „Diese Adresse gehört inzwischen zu einem anderen Konto …" |
| `frontend/src/lib/i18n/messages/de/auth.json`, `.../en/auth.json` | MODIFY | Neuer Bereich `auth` (einzige Katalogdatei dieses Pakets) |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `routes/login/`, `routes/register/`, `routes/forgot-password/`, `routes/reset-password/`, `routes/magic-link/`, `routes/verify-email/` streichen (soweit die Messung aus #2649 sie enthält) |
| `docs/reference/i18n_glossar.md` | MODIFY | Neue Zeilen (Tabelle unten) VOR dem Katalog |
| `frontend/src/routes/login/__tests__/auth_login_zweisprachig.test.ts` | CREATE | Seite in `de`/`en`, Codes → Texte |
| `frontend/src/routes/register/__tests__/auth_register_zweisprachig.test.ts` | CREATE | Seite und Action in beiden Sprachen |
| `frontend/src/routes/__tests__/auth_seiten_zweisprachig.test.ts` | CREATE | Passwort, Anmeldelink, E-Mail-Bestätigung: Seite und Action in beiden Sprachen, Restwort-Prüfung |
| bestehende Tests der Auth-Routen (`login/__tests__/*`, `register/__tests__/*`, `verify-email/*.test.ts`) | MODIFY | Prüfung über `trFor`-/`tr`-Werte statt über deutsche Literale, soweit sie Texte betreffen |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** nicht berührt; die Auth-Seiten kennen weder Trip noch Ortsvergleich. Texte, die später auch anderswo vorkommen (zum Beispiel „Speichern"), werden hier nicht erfunden, sondern bleiben dem Bereich `aktionen` vorbehalten.
- **Mandantentrennung:** Die Seiten bewegen keine Nutzerdaten. Die Sprache je Anfrage kommt aus `locals.lang`; zwei gleichzeitige Anfragen verschiedener Sprache dürfen sich nicht vermischen (AC-5). Der Einladungs-Check aus #2519 bleibt unverändert.
- **Kanäle:** nicht berührt (keine Briefing- oder Alarm-Inhalte).

## Estimated Scope

- **LoC:** ca. 220 Code-Änderungen (ersetzte Textstellen in 13 Dateien; Katalogdaten zählen nicht)
- **Files:** ca. 24
- **Effort:** medium (viele Dateien, mechanisch). Bei mehr als 250 geänderten Zeilen `loc_limit_override 500` einplanen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2647 (S2) | package | `$t`, `trFor`, `Lang`, Bereichsdatei `auth.json` (leer angelegt) |
| #2649 (S4) | package | Ratsche und Allowlist; hier werden die Einträge der sechs Verzeichnisse gestrichen |
| #2645 (S0) | package | Glossar mit „Konto und Anmeldung" (sign in, sign up, password, username, email, test email) |
| `$lib/admin` (`TIER_LABELS`) | module | Liefert die Level-Bezeichnung für den Einladungs-Hinweis; bleibt deutsch bis Paket #2653 (F4) |
| Wordmark-Komponente (`$lib/components/ui/wordmark/Wordmark.svelte`) | component | Markentext „Gregor" ist Eigenname und wird nicht übersetzt |
| ADR-0104, ADR-0095 | adr | Sprache am Nutzer; Eigennamen bleiben |

## Implementation Details

**Vorgehen (Standard der F-Pakete).** (1) Texte extrahieren zu Schlüsseln `auth.<seite>.<element>`, Platzhalter statt Konkatenation. (2) Englisch nach Glossar (`docs/reference/i18n_glossar.md`); das im Glossar verbotene Produktwort ist untersagt. (3) Den Allowlist-Eintrag entfernen; Paritäts- und Ratschen-Test müssen grün sein. (4) Bestehende Tests über Katalogwerte prüfen. (5) Nur `messages/{de,en}/auth.json` anfassen, keine anderen Bereichsdateien, keine Schlüssel umbenennen, deutsche Texte nicht „verbessern", keine neuen Abhängigkeiten.

**Glossar-Ergänzung VOR dem Katalog** (Abschnitt „Konto und Anmeldung" aus #2645 erweitern): Passwort vergessen → forgot password · Passwort zurücksetzen → reset password · Bestätigungslink → confirmation link · Anmeldelink → sign-in link · E-Mail-Code → email code · Einladung → invitation · Konto erstellen → create account.

**Beispiel-Schlüssel (de / en):**

| Schlüssel | de | en |
|---|---|---|
| `auth.register.titel` | Konto erstellen | Create account |
| `auth.register.untertitel` | Benutzerdaten eingeben | Enter your details |
| `auth.register.passwoerter_ungleich` | Passwörter stimmen nicht überein | Passwords do not match |
| `auth.register.einladung_gueltig` | Du wurdest eingeladen — Level: {level} | You have been invited — level: {level} |
| `auth.fehler.zu_viele_versuche` | Zu viele Versuche — bitte in einigen Minuten erneut versuchen. | Too many attempts. Please try again in a few minutes. |
| `auth.login.ungueltige_daten` | Benutzername oder Passwort nicht korrekt. | Username or password is incorrect. |
| `auth.login.pflichtfelder` | Bitte Benutzername und Passwort eingeben. | Please enter your username and password. |

`auth.fehler.zu_viele_versuche` wird von Login (`Rate limit exceeded` → Text) und Registrierung (HTTP 429) gemeinsam benutzt: ein Text, ein Schlüssel.

**Beispiel-Umstellungen (Datei:Zeile, Stand heute):**

- `frontend/src/routes/register/+page.svelte:26` `<h1 class="text-2xl font-bold">Konto erstellen</h1>` → `<h1 class="text-2xl font-bold">{$t('auth.register.titel')}</h1>`.
- `frontend/src/routes/register/+page.svelte:38` `Du wurdest eingeladen — Level: {tierLabel}` → `{$t('auth.register.einladung_gueltig', { level: tierLabel })}`.
- `frontend/src/routes/register/+page.server.ts:56` `return fail(400, { error: 'Passwörter stimmen nicht überein', username, email });` → `return fail(400, { error: trFor(locals.lang, 'auth.register.passwoerter_ungleich'), username, email });` (die Action erhält dazu `locals`).
- `frontend/src/routes/login/+page.svelte:204` (verschachtelte Zeichenkettenkette für `Rate limit exceeded` / `Invalid credentials` / `Username and password required`) → eine Abbildung `Code → Schlüssel` (`const FEHLER_SCHLUESSEL = { 'Rate limit exceeded': 'auth.fehler.zu_viele_versuche', … }`) und `{$t(FEHLER_SCHLUESSEL[form.error] ?? …)}`; unbekannte Werte zeigt die Seite wie heute unverändert an.
- `frontend/src/routes/login/+page.svelte:18-28` `GOOGLE_FEHLERTEXTE` (Map Code → Text) → Map Code → Schlüssel; der Text entsteht mit `$t(...)` bei der Anzeige. Die Map bleibt eine `Map`, damit ein Code wie `constructor` nichts trifft.

**Wichtig für die Server-Actions.** `locals.lang` fehlt in Unit-Tests der Actions; `trFor(undefined, …)` liefert Deutsch (siehe #2647). Nie `tr()` oder den Store `locale` in einer Action benutzen. Meldungen aus der Go-API (`msg` aus dem Antwortrumpf, etwa in `verify-email/+page.server.ts:51` und `reset-password/+page.server.ts:38`) werden unverändert durchgereicht.

**Allowlist-Eintrag, der entfernt wird:** `routes/login/`, `routes/register/`, `routes/forgot-password/`, `routes/reset-password/`, `routes/magic-link/`, `routes/verify-email/` (Das Issue nennt `routes/(auth)`; maßgeblich sind die Einträge der Messung aus #2649). **Golden-Fixture:** vor der Umstellung die deutsche Seiten-Ausgabe je Route (leerer Zustand, Fehlerzustand) als `fixtures/<route>.de.html` neben die Tests schreiben und nach der Umstellung byte-gleich vergleichen. **Validator, Token-Wächter:** nicht berührt.

## Expected Behavior

- **Input:** Aufruf der sechs Auth-Routen und ihrer Formular-Actions mit `locals.lang` = `de` oder `en`.
- **Output:** Alle Frontend-eigenen Texte in der Sprache der Anfrage; Deutsch byte-gleich zu heute.
- **Side effects:** Keine neuen. Codes der Actions (`Invalid credentials`, `email_not_verified`) und Weiterleitungen bleiben.

## Acceptance Criteria

- **AC-1:** Given ein Besucher mit englischer Sprache / When `/login` gerendert wird (leerer Zustand, mit Fehlern `Invalid credentials`, `Rate limit exceeded`, `Username and password required`, `email_not_verified` und mit den Google-Fehlercodes) / Then sind alle sichtbaren Texte englisch und es bleibt kein deutsches Restwort übrig (Eigenname „Gregor" ausgenommen).
  - Test: frontend/src/routes/login/__tests__/auth_login_zweisprachig.test.ts — SSR-Render je Zustand; nach Abzug aller englischen `auth.*`-Katalogwerte und der dynamischen Werte bleibt kein Wort übrig (Restwort-Prüfung wie im Onboarding-Test).

- **AC-2:** Given dieselben Zustände auf Deutsch / When die Seiten gerendert werden / Then ist das HTML byte-gleich zur Ausgabe vor der Umstellung (Golden).
  - Test: frontend/src/routes/login/__tests__/auth_login_zweisprachig.test.ts und frontend/src/routes/register/__tests__/auth_register_zweisprachig.test.ts — Vergleich mit den vor der Umstellung geschriebenen Fixtures `*.de.html`.

- **AC-3:** Given ein Besucher mit Sprache `en` / When er Registrierung (mit gültiger, ungültiger und unsicherer Einladung), Passwort vergessen, Passwort zurücksetzen, Anmeldelink und E-Mail-Bestätigung durchläuft / Then erscheinen Seitentexte und Fehlermeldungen der Actions englisch, mit Platzhalter für das Einladungs-Level, und kein deutsches Restwort.
  - Test: frontend/src/routes/register/__tests__/auth_register_zweisprachig.test.ts und frontend/src/routes/__tests__/auth_seiten_zweisprachig.test.ts — Render und echte Actions mit nachgestellter Go-Antwort (`fetch`), Restwort-Prüfung.

- **AC-4:** Given die Registrierung antwortet mit 429, 409 `email_taken`, 400 `invite_invalid`, 400 `invalid_email` oder 500 / When die Action auf Deutsch läuft / Then lauten die Fehlertexte exakt wie vor der Umstellung, und der zugehörige englische Text ist ein anderer, nicht leerer Katalogwert.
  - Test: frontend/src/routes/register/__tests__/auth_register_zweisprachig.test.ts — fünf Antworten gegen die echte Action; Soll-Texte über `trFor('de'|'en', …)`; bestehende `register_email_taken.test.ts` und `register_einladung.test.ts` bleiben grün.

- **AC-5:** Given zwei Anfragen mit verschiedener Sprache (`locals.lang = "en"` und `"de"`) werden nacheinander und verschränkt ausgeführt / When beide Actions denselben Fehlerfall auslösen / Then erhält jede ihre eigene Sprache, ohne dass die eine die andere beeinflusst.
  - Test: frontend/src/routes/register/__tests__/auth_register_zweisprachig.test.ts — zwei Aufrufe der echten Action mit `Promise.all`.

- **AC-6:** Given die Allowlist ohne die sechs Verzeichnisse und die Ratsche aus #2649 / When die Tests laufen / Then ist die Ratsche grün (kein hartkodierter Text mehr in den Auth-Routen), und der Paritätstest für `auth.json` ist grün.
  - Test: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts und frontend/src/lib/i18n/__tests__/paritaet_de_en.test.ts (bestehend) — Ratschen-/Paritätstest, `# doc-compliance-test`.

## Known Limitations

- Annahme: Die Codes `Invalid credentials`, `Rate limit exceeded`, `Username and password required` bleiben als Fehlerwerte der Login-Action bestehen (ein vorhandener Test erwartet sie); nur die Anzeige wird katalogisiert.
- Annahme: Die Level-Bezeichnungen im Einladungs-Hinweis (`TIER_LABELS`) bleiben deutsch bis Paket #2653; der Hinweis ist dadurch in `en` gemischt („level: Free" bleibt je nach Label deutsch).
- Annahme: Der Seitentitel (`<svelte:head><title>`) der Auth-Seiten wird mitmigriert, falls vorhanden, ebenso `aria-label`-Texte der Passkey-Knöpfe.
- Fehlermeldungen aus der Go-API (zum Beispiel „Bestätigungslink abgelaufen") bleiben bis Paket #2676 (G2) deutsch.
- Die Passkey-Bibliothek (`$lib/passkey`) und der Hinweis „Dieses Gerät" in `+layout.svelte` sind nicht Teil dieses Pakets.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Frontend-eigene Texte der Einstiegsseiten gehören in den Katalog, damit die erste Begegnung mit dem Produkt in der Sprache des Nutzers stattfindet.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
