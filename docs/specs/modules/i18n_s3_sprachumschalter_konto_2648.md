---
entity_id: i18n_s3_sprachumschalter_konto_2648
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2648, frontend, model-haiku]
---

# i18n S3: Sprachumschalter für Besucher und Spracheinstellung im Konto

**Issue:** #2648 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt 1, 3

## Approval

- [ ] Approved

## Purpose

Besucher ohne Konto wählen die Sprache mit einem Umschalter `DE | EN` auf Startseite, Anmeldung und Registrierung; die Wahl bleibt als Cookie erhalten. Angemeldete Nutzer stellen die Sprache einmal im Konto ein, sie wird in ihrem Profil gespeichert und gilt danach auf allen Geräten und in allen Nachrichten. Neue Konten übernehmen die Sprache, die der Besucher beim Registrieren gerade sah.

## Source

- **File:** `frontend/src/routes/lang/+server.ts` (neu), `frontend/src/lib/components/ui/SprachUmschalter.svelte` (neu), `frontend/src/lib/components/account/SpracheAuswahl.svelte` (neu), `frontend/src/routes/account/+page.svelte`, `frontend/src/routes/_start/Startseite.svelte`, `frontend/src/routes/login/+page.svelte`, `frontend/src/routes/login/+page.server.ts`, `frontend/src/routes/register/+page.svelte`, `frontend/src/routes/register/+page.server.ts`, `frontend/src/hooks.server.ts`
- **Identifier:** `POST` in `routes/lang/+server.ts`, `SprachUmschalter`, `SpracheAuswahl`, `actions.login` (Cookie-Weitergabe), `actions.default` in `register/+page.server.ts` (Feld `language`), `publicPaths` in `handle`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Die Go-API (Profil-`PUT`, Cookie `gz_lang`) liefert Paket #2646; der Sprachkern (`locale`, `$t`, `trFor`, `resolveLang`) Paket #2647. Der Besucher-Umschalter ist ein Endpunkt des Frontends (`POST /lang`), nicht der Go-API. Das Issue spricht von einer Form-Action `?/lang`; maßgeblich sind die Konventionen (Abschnitt 1): eigener Endpunkt `routes/lang/+server.ts`.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/routes/lang/+server.ts` | CREATE | `POST`: Formfeld `lang` (`de`/`en`) → Cookie `gz_lang`, danach 303 zurück auf den `Referer` (nur gleicher Ursprung, sonst `/`) |
| `frontend/src/hooks.server.ts` | MODIFY | `'/lang'` in `publicPaths`, damit Ausgeloggte den Endpunkt erreichen |
| `frontend/src/lib/components/ui/SprachUmschalter.svelte` | CREATE | Formular `method="POST" action="/lang"` mit zwei Knöpfen `DE`/`EN`, der aktive trägt `aria-current="true"` |
| `frontend/src/lib/components/account/SpracheAuswahl.svelte` | CREATE | Auswahl „Sprache / Language" im Konto; speichert über `api.put('/api/auth/profile', { language })` und setzt danach `locale` |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Bindet `SpracheAuswahl` im Konto-Bereich ein (nur das Feld `language`, nie zusammen mit Adressfeldern) |
| `frontend/src/routes/_start/Startseite.svelte`, `routes/login/+page.svelte`, `routes/register/+page.svelte` (unter `frontend/src/`) | MODIFY (3) | `SprachUmschalter` einbinden (je einmal, oben auf der Seite) |
| `frontend/src/routes/register/+page.server.ts` | MODIFY | `default`-Action erhält `locals`; Request-Body um `language: locals.lang` ergänzen |
| `frontend/src/routes/login/+page.server.ts` | MODIFY | `login`-Action reicht `gz_lang` aus der Set-Cookie-Antwort der Go-API an den Browser weiter (wie `gz_session`) |
| `frontend/src/lib/i18n/messages/de/konto.json`, `.../en/konto.json` | MODIFY (2) | Sechs Schlüssel `konto.sprache.*` (Tabelle unten) |
| `frontend/src/routes/lang/__tests__/sprachumschalter_cookie.test.ts` | CREATE | Endpunkt: Cookie, Validierung, Rückleitung |
| `frontend/src/lib/components/ui/__tests__/sprach_umschalter_darstellung.test.ts` | CREATE | Darstellung, aktiver Zustand, nicht in der angemeldeten Shell |
| `frontend/src/routes/account/__tests__/sprache_im_konto.test.ts` | CREATE | Speichern, Fehler, zwei Nutzer |
| `frontend/src/routes/register/__tests__/register_sendet_sprache.test.ts` | CREATE | Registrierung sendet `language` |
| `frontend/src/routes/login/__tests__/login_reicht_sprach_cookie_weiter.test.ts` | CREATE | Login-Action setzt `gz_lang` im Browser |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** Kein Trip- oder Compare-Pendant. Der Umschalter ist ein allgemeiner UI-Baustein unter `ui/`, die Konto-Auswahl gehört zur Konto-Seite; beide kennen keinen `context`.
- **Mandantentrennung:** Das Profil wird ausschließlich über die eigene Sitzung geschrieben (`api.put` gegen `/api/auth/profile`; `user_id` kommt in Go aus dem Auth-Kontext). Die Registrierung liest `locals.lang` der eigenen Anfrage. Getestet mit zwei Nutzern (AC-3).
- **Kanäle:** Die gespeicherte Sprache steuert später alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS); dieses Paket ändert noch keinen Kanalinhalt.

## Estimated Scope

- **LoC:** ca. 150 Code (Endpunkt ca. 30, Umschalter ca. 35, Konto-Auswahl ca. 45, Anbindungen ca. 40), Tests zusätzlich
- **Files:** 17
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2646 (S1) | package | `PUT /api/auth/profile` nimmt `language`; Go setzt `gz_lang` bei Login, Registrierung und Profil-Update |
| #2647 (S2) | package | `locale`, `$t`, `trFor`, `resolveLang`, `locals.lang`, Layout-Loader mit Profilsprache |
| `safeRedirectPath` (`$lib/utils/safeRedirect.ts`) | function | Verhindert offene Weiterleitungen beim Zurückleiten |
| `api` (`$lib/api.js`) | module | `api.put` wie im Konto üblich |
| `invalidateAll` (`$app/navigation`) | function | Lädt nach dem Speichern den Layout-Loader neu, damit `data.lang` stimmt |
| ADR-0104 | adr | Nr. 1 und 2: Sprache am Nutzer, Besucher über Cookie |

## Implementation Details

**Endpunkt `routes/lang/+server.ts`** (Skizze, unter 30 Zeilen):

```ts
export const POST: RequestHandler = async ({ request, cookies, url }) => {
	const lang = (await request.formData()).get('lang')?.toString();
	if (lang === 'de' || lang === 'en') {
		cookies.set('gz_lang', lang, { path: '/', maxAge: 31536000, sameSite: 'lax',
			secure: url.protocol === 'https:', httpOnly: false });
	}
	const ref = request.headers.get('referer');
	let ziel = '/';
	try { const r = new URL(ref ?? ''); if (r.origin === url.origin) ziel = safeRedirectPath(r.pathname + r.search); } catch {}
	redirect(303, ziel);
};
```

Ein ungültiger Wert ändert das Cookie nicht; die Rückleitung erfolgt trotzdem. Der Endpunkt schreibt keine Nutzerdaten (nur Besucher-Cookie).

**Umschalter.** `SprachUmschalter.svelte` rendert `<form method="POST" action="/lang">` mit zwei `<button type="submit" name="lang" value="de|en">`. Der sichtbare Text ist der Ausdruck `{l.toUpperCase()}` (kein Literal, sonst schlägt die Ratsche aus #2649 an); der Gruppenname kommt aus `$t('konto.sprache.umschalter_label')`. Der Knopf der aktuellen Sprache (`$locale`) trägt `aria-current="true"`. Platzierung: oben auf `Startseite.svelte` neben dem `Wordmark`, oben in `login/+page.svelte` und `register/+page.svelte`. In `+layout.svelte`, `Sidebar` und `KontoSheet` kommt **kein** Umschalter hinzu (eine Stelle für Angemeldete: das Konto).

**Konto-Auswahl.** `SpracheAuswahl.svelte` zeigt Titel `$t('konto.sprache.titel')` und eine Auswahl mit den Optionen `konto.sprache.option_de` (Deutsch) und `konto.sprache.option_en` (English); beim Ändern:

```ts
try { await api.put('/api/auth/profile', { language: neu }); locale.set(neu); await invalidateAll(); meldung = $t('konto.sprache.gespeichert'); }
catch { fehler = $t('konto.sprache.fehler'); }   // locale bleibt unverändert
```

Es wird **nur** `{ language }` gesendet (wie das Passkey-Angebot nur sein eigenes Feld sendet), damit keine Adressänderung und keine Bestätigungsmail mitläuft. Der Fehlertext steht sichtbar (`role="alert"`).

**Registrierung und Login.** In `register/+page.server.ts` wird die Action zu `default: async ({ request, locals })`, der JSON-Body zu `{ username, password, email, language: locals.lang, ...(invite && { invite }) }`. In `login/+page.server.ts` nach dem Setzen von `gz_session`: `const lang = setCookie?.match(/gz_lang=([^;]+)/); if (lang) cookies.set('gz_lang', lang[1], { path: '/', maxAge: 31536000, sameSite: 'lax', secure: env.NODE_ENV === 'production', httpOnly: false });`.

**Beispiel-Umstellung (aus dem Kern-Paket #2647):** `{t('start.cta.login')}` → `{$t('start.cta.login')}`; der Umschalter zeigt `{l.toUpperCase()}` statt eines Textes.

**Neue Katalogschlüssel (Bereich `konto`, de / en):**

| Schlüssel | de | en |
|---|---|---|
| `konto.sprache.titel` | Sprache / Language | Sprache / Language |
| `konto.sprache.option_de` | Deutsch | Deutsch |
| `konto.sprache.option_en` | English | English |
| `konto.sprache.gespeichert` | Sprache gespeichert | Language saved |
| `konto.sprache.fehler` | Die Sprache konnte nicht gespeichert werden. Bitte versuche es noch einmal. | The language could not be saved. Please try again. |
| `konto.sprache.umschalter_label` | Sprache wählen | Choose language |

Titel und Optionsnamen sind in beiden Sprachen gleich (Eigennamen der Sprachen, zweisprachiger Titel).

**Allowlist-Eintrag:** keiner (S3 fügt nur katalogisierte Texte hinzu; `routes/account/` bleibt bis Paket #2653 in der Allowlist). **Golden/Validator/Token-Wächter:** nicht berührt.

## Expected Behavior

- **Input:** `POST /lang` mit `lang`; Auswahl im Konto; Registrierungs- und Login-Formular.
- **Output:** Cookie `gz_lang` (1 Jahr, `Path=/`, `SameSite=Lax`, `Secure` bei https); 303-Rückleitung; Profil mit neuer Sprache; Registrierung mit `language`.
- **Side effects:** Besucher: nur Cookie. Angemeldet: `user.json` des eigenen Nutzers (per Merge in Go), Store `locale`, Neuladen der Layout-Daten.

## Acceptance Criteria

- **AC-1:** Given ein Besucher ohne Anmeldung auf der Startseite / When er `EN` wählt / Then setzt der Endpunkt das Cookie `gz_lang=en` mit `Path=/`, `Max-Age=31536000`, `SameSite=Lax` ohne `HttpOnly`, leitet mit 303 auf dieselbe Seite zurück, und beim nächsten Aufruf ohne weitere Aktion trägt die Seite `lang="en"` und zeigt die englischen Startseitentexte.
  - Test: frontend/src/routes/lang/__tests__/sprachumschalter_cookie.test.ts — echter `POST`-Handler, danach echtes `handle` und SSR-Render mit dem gesetzten Cookie.

- **AC-2:** Given ein Besucher / When der Endpunkt einen ungültigen Wert (`fr`) oder einen fremden `Referer` (`https://boese.example/x`) erhält / Then bleibt das Cookie unverändert und die Rückleitung führt auf `/` statt auf die fremde Adresse.
  - Test: frontend/src/routes/lang/__tests__/sprachumschalter_cookie.test.ts — zwei Negativfälle gegen den echten Handler.

- **AC-3:** Given Nutzer A wählt im Konto Englisch / When danach Nutzer B (anderes Profil mit `de`) die Seite lädt / Then sendet die Konto-Auswahl von A genau `{"language":"en"}` an `PUT /api/auth/profile`, A sieht danach englische Texte, und B erhält vom Layout-Loader weiterhin `lang: "de"`.
  - Test: frontend/src/routes/account/__tests__/sprache_im_konto.test.ts — Komponente und echter Layout-Loader; das Test-`fetch` stellt die Go-API je Nutzer nach; geprüft werden gesendeter Body und `data.lang` beider Nutzer.

- **AC-4:** Given das Speichern der Sprache scheitert (Status 400 oder 500) / When der Nutzer eine Sprache wählt / Then erscheint der Fehlertext `konto.sprache.fehler` sichtbar, und die Oberfläche bleibt in der bisherigen Sprache.
  - Test: frontend/src/routes/account/__tests__/sprache_im_konto.test.ts — Komponente mit fehlschlagendem `api.put`; Text und unveränderter Store.

- **AC-5:** Given ein Besucher mit `locals.lang = "en"` / When er die Registrierung absendet / Then enthält der Request an `POST /api/auth/register` das Feld `"language":"en"` (bei `de` entsprechend `"de"`), und die übrigen Felder sowie der Einladungstoken bleiben unverändert.
  - Test: frontend/src/routes/register/__tests__/register_sendet_sprache.test.ts — echte Action, das Test-`fetch` fängt den Request-Body der Go-API ab (vorhandenes Muster aus `register_einladung.test.ts`).

- **AC-6:** Given die Go-API antwortet beim Login mit `Set-Cookie` für `gz_session` und `gz_lang=en` / When die Login-Action läuft / Then setzt sie beide Cookies im Browser, und ohne `gz_lang` in der Antwort wird kein Sprach-Cookie gesetzt.
  - Test: frontend/src/routes/login/__tests__/login_reicht_sprach_cookie_weiter.test.ts — echte Action mit nachgestellter Go-Antwort.

- **AC-7:** Given die Startseite, die Anmeldung, die Registrierung und die angemeldete Shell / When sie gerendert werden / Then enthalten die ersten drei genau einen Umschalter mit `DE` und `EN` (der aktuelle Knopf mit `aria-current`), die Seitenleiste und das geöffnete Konto-Menü keinen.
  - Test: frontend/src/lib/components/ui/__tests__/sprach_umschalter_darstellung.test.ts — SSR-Render der drei Seiten, von `Sidebar` und `KontoSheet`; Suche nach dem Test-Merkmal des Umschalters.

## Known Limitations

- Annahme: Bis die Migrationspakete F1 bis F4 durch sind, wechseln auf Login- und Registrierungsseite nur `lang`-Attribut und Umschalter-Zustand, die Seitentexte bleiben deutsch (Paket #2650 migriert sie). Die Startseite wechselt vollständig.
- Annahme: Die Login-Action reicht `gz_lang` aus der Antwort der Go-API weiter, weil das Frontend sonst nur `gz_session` an den Browser gibt (Konventionen Abschnitt 1: „Go setzt es bei Login"). Der Cookie der Registrierung wird nicht weitergereicht; er ist dort identisch zum bereits vorhandenen Besucher-Cookie.
- Annahme: Die Konto-Auswahl speichert sofort beim Ändern (kein eigener Speichern-Knopf), weil sie ein einzelnes Feld mit Sofortrückmeldung ist.
- Ein angemeldeter Nutzer ohne gespeicherte Sprache sieht im Konto `Deutsch` (wirksame Sprache aus #2646).
- Ändert ein Nutzer seine Sprache in einem Tab, aktualisieren andere offene Tabs sie erst bei der nächsten Navigation.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (Nr. 1 und 2)
- **Rationale:** Besucher wählen per Cookie, Angemeldete im Konto mit Speicherung am Nutzer; es gibt je Zielgruppe genau einen Ort der Auswahl.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
