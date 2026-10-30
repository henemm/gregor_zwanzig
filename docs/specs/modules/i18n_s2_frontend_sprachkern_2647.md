---
entity_id: i18n_s2_frontend_sprachkern_2647
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2647, frontend, model-sonnet]
---

# i18n S2: Frontend-Sprachkern (Katalog je Bereich, `t()`/`tn()`/`tr()`, Spracherkennung, `<html lang>`)

**Issue:** #2647 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt 1, 2, 3

## Approval

- [ ] Approved

## Purpose

Wer die Seite auf Englisch öffnet (Nutzereinstellung, Cookie oder Browsersprache), bekommt `<html lang="en">` und englische Texte; alle anderen bleiben bei Deutsch, byte-gleich zu heute. Dieses Paket baut dafür den Sprachkern: einen zweisprachigen Katalog, der in Bereichsdateien geschnitten ist, damit die späteren Migrationspakete F1 bis F11 parallel arbeiten, ohne einander in dieselbe Datei zu schreiben. Die 112 bestehenden Textschlüssel des Katalogs aus #2520 ziehen dafür in die Bereichsdateien um und erhalten englische Entsprechungen.

## Source

- **File:** `frontend/src/lib/i18n/index.ts`, `locale.ts`, `translate.ts`, `format.ts`, `resolveLang.ts` (neu bzw. neu geschnitten), `frontend/src/lib/i18n/messages/{de,en}/*.json` und `index.ts`, `frontend/src/hooks.server.ts`, `frontend/src/routes/+layout.server.ts`, `frontend/src/routes/+layout.svelte`, `frontend/src/app.html`, `frontend/src/app.d.ts`
- **Identifier:** `Lang`, `MessageKey`, `locale`, `t`, `tn`, `tr`, `trFor`, `translate`, `resolveLang`, `fmtDate`, `fmtTime`, `fmtWeekday`, `fmtRelativeMinutes`, `handle` (erweitert), `load` in `+layout.server.ts` (erweitert)

> **Schicht-Hinweis:** Reines SvelteKit-Frontend (`frontend/src/...`) plus eine Anpassung an einem bestehenden Leser des alten Katalogs (ein Python-Drift-Test liest die Katalogdatei als Daten). Keine neue Abhängigkeit, kein Paraglide. Das Nutzerprofil kommt aus dem bereits vorhandenen Abruf `GET /api/auth/profile` im Layout-Loader (Paket #2646 liefert dort `language`); ein Endpunkt `/api/me` existiert nicht.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/<bereich>.json` und `.../en/<bereich>.json` für die 17 Bereiche `start`, `auth`, `nav`, `home`, `listen`, `konto`, `admin`, `wertebereiche`, `versand`, `alarme`, `layout`, `trip`, `vergleich`, `aktionen`, `bausteine`, `fehler`, `hilfe` | CREATE (34 Dateien) | Alle Bereichsdateien werden angelegt; leere Bereiche enthalten `{}`. Gefüllt werden `start`, `nav`, `hilfe`, `bausteine`, `home` (Bestand) und `aktionen` (3 Zeitschlüssel) |
| `frontend/src/lib/i18n/messages/de/index.ts`, `.../en/index.ts` | CREATE | Je Sprache alle 17 Dateien importieren und zu einem Objekt `de` bzw. `en` vereinigen (Importe mit Endung `.json`) |
| `frontend/src/lib/i18n/messages/de.json` | DELETE | Ersetzt durch die Bereichsdateien (Inhalt vorher als Fixture sichern, siehe `deutsch_unveraendert.test.ts`) |
| `frontend/src/lib/i18n/translate.ts` | CREATE | Reiner Kern `translate(katalog, lang, key, params)` und `translatePlural(...)`: Platzhalter, Plural, Fallback auf `de` mit einmaligem `console.warn("i18n fallback: <key>")` |
| `frontend/src/lib/i18n/locale.ts` | CREATE | `export const locale: Writable<Lang>` (Start `de`), Typ `Lang = 'de' \| 'en'` |
| `frontend/src/lib/i18n/index.ts` | MODIFY | Exporte `t`, `tn` (Readable), `tr`, `trFor`, `MessageKey`, `Lang`, `locale`; bindet `translate.ts` an die echten Kataloge |
| `frontend/src/lib/i18n/resolveLang.ts` | CREATE | `resolveLang({ cookie, acceptLanguage }): Lang` (Cookie > Accept-Language > `de`); `parseAcceptLanguage` |
| `frontend/src/lib/i18n/format.ts` | CREATE | `fmtDate`, `fmtTime`, `fmtWeekday`, `fmtRelativeMinutes` ohne `Intl`-Abkürzungen (eigene Tabellen) |
| `frontend/src/hooks.server.ts` | MODIFY | `event.locals.lang` setzen; `transformPageChunk` ersetzt `%lang%` (liest `event.locals.lang` erst beim Ersetzen) in allen drei `resolve`-Aufrufen |
| `frontend/src/app.d.ts` | MODIFY | `Locals.lang: 'de' \| 'en'`, `PageData.lang` |
| `frontend/src/app.html` | MODIFY | `<html lang="%lang%">` statt `lang="de"` |
| `frontend/src/routes/+layout.server.ts` | MODIFY | `lang` aus Profil (`de`/`en`, sonst `locals.lang`), schreibt `locals.lang` zurück, gibt `lang` zurück |
| `frontend/src/routes/+layout.svelte` | MODIFY | `locale.set(data.lang)` im Skript-Kopf (synchron, wirkt beim Serverrendern) plus `$effect.pre` für Client-Navigationen |
| `frontend/src/routes/_start/Startseite.svelte`, `routes/+page.svelte`, `routes/hilfe/+page.svelte`, `routes/_home/StartklarCheckliste.svelte`, `routes/_home/EmptyKachel.svelte`, `lib/components/ui/sidebar/Sidebar.svelte`, `lib/components/ui/sidebar/KontoSheet.svelte`, `lib/components/shared/StandardwerteSpeichernKnopf.svelte`, `lib/components/shared/TelegramKurzstilToggle.svelte`, `lib/components/molecules/BegriffErklaerung.svelte`, `lib/components/molecules/Infobox.svelte` (alle unter `frontend/src/`) | MODIFY (11) | Aufrufe `t('…')` → `$t('…')`; Konstanten, die beim Skriptstart Texte lesen (`bilder` in `Startseite.svelte`, `ariaLabel`/`erklaerung` in `BegriffErklaerung.svelte`), werden `$derived`. `hilfe/+page.svelte` importiert `de` aus `messages/de/index` statt aus `de.json` und trägt den Kommentar `// i18n-dynamic: hilfe.befehle.` |
| `frontend/src/lib/components/shared/infoboxKeys.ts` | prüfen | Nur Typimport `MessageKey`, bleibt unverändert |
| `frontend/src/lib/i18n/__tests__/textkatalog.test.ts`, `onboarding_textkatalog.test.ts`, `standardwerte_hilfe_textkatalog.test.ts`, `frontend/src/lib/components/molecules/begriff_erklaerung_infobox_bausteine.test.ts`, `frontend/src/lib/components/shared/__tests__/infobox_standards_stimmen_mit_den_quellen.test.ts`, `standardwerte_knopf_geteilt.test.ts`, `telegram_kurzstil_shared_toggle.test.ts`, `frontend/src/routes/__tests__/onboardingSsr.ts` | MODIFY (8) | Statt `messages/de.json` die vereinigte `de`-Exportkarte lesen; `t(` → `tr(`; Regexe, die `{t('…')}` im Quelltext suchen, auf `{$t('…')}` anpassen |
| `frontend/src/hooks.server.test.ts`, `hooks.server.oeffentliche_startseite.test.ts`, `hooks.server.hilfe_nur_eingeloggt.test.ts`, `hooks.server.failfast.test.ts` | MODIFY (4) | Das Ereignis erhält `request: new Request(url)` (für `Accept-Language`) und `cookies.get` liefert auch `gz_lang` |
| `tests/test_hilfe_befehle_drift.py` | MODIFY | `KATALOG_DATEI` zeigt auf `frontend/src/lib/i18n/messages/de/hilfe.json`; Rest unverändert |
| `frontend/src/lib/i18n/__tests__/paritaet_de_en.test.ts` | CREATE | Schlüsselmenge und Platzhaltermenge je Bereichsdatei gleich |
| `frontend/src/lib/i18n/__tests__/sprachaufloesung.test.ts` | CREATE | Cookie > Accept-Language > `de` |
| `frontend/src/lib/i18n/__tests__/platzhalter_plural_fallback.test.ts` | CREATE | `{name}`, `.one`/`.other`, Fallback-Warnung einmalig |
| `frontend/src/lib/i18n/__tests__/format_datum_zeit.test.ts` | CREATE | Formate in beiden Sprachen |
| `frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts` und `fixtures/de_katalog_vor_i18n.json` | CREATE | Golden: die 112 deutschen Texte sind byte-gleich zum Stand vor diesem Paket |
| `frontend/src/lib/i18n/__tests__/en_katalog_regeln.test.ts` | CREATE | Glossar- und Stilregeln der englischen Texte, Typfehler bei unbekanntem Schlüssel |
| `frontend/src/routes/__tests__/sprache_je_anfrage_ssr.test.ts` | CREATE | `<html lang>`, Startseite englisch, zwei Anfragen/Nutzer hintereinander |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** Der Kern ist für beide Kontexte gleich. Texte, die auf Trip- und Ortsvergleich-Flächen identisch sind, gehören später nach `aktionen.*` (Konventionen Abschnitt 2); dieses Paket legt dafür nur die Datei und die drei Zeitschlüssel an. Eine einseitige Neuanlage gibt es nicht.
- **Mandantentrennung:** Die Sprache kommt aus dem Profil der eigenen Sitzung (`locals.userId`, Cookie `gz_session`); es gibt keinen Fallback auf einen anderen Nutzer. Das serverseitige Rendern setzt `locale` synchron zu Beginn des Layouts; ein Test rendert Anfragen mit verschiedener Sprache nacheinander (AC-6).
- **Kanäle:** Briefing- und Alarm-Inhalt ist nicht berührt. Die Startseite nennt weiterhin E-Mail als Hauptkanal und SMS/Satellit nur mit dem Zusatz „in Arbeit/auf Anfrage" (englisch: „in progress"/„on request").

## Estimated Scope

- **LoC:** ca. 330-380 Code ohne Katalogdaten und Tests (Kern ca. 200, Aufrufstellen-Umstellung ca. 80, Hooks/Layout ca. 50). Das überschreitet das Workflow-Limit von 250: `loc_limit_override 500` einplanen.
- **Files:** ca. 60 (34 Katalogdateien, 2 Index-Dateien, 7 neue Module/Tests, 25 geänderte Dateien)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2646 (S1) | package | `GET /api/auth/profile` liefert `language` (`de`/`en`, bei fehlendem Feld `de`) |
| #2645 (S0) | package | Glossar bindend für die englischen Texte |
| `svelte/store` (`writable`, `derived`, `get`) | module | `locale`, `t`, `tn` |
| `$lib/auth.js`, `hooks.server.ts` (`handle`) | module | Bestehende Sitzungsprüfung bleibt unverändert |
| `frontend/test-lib-loader.mjs` / `test-lib-hooks.mjs` | tooling | Testlauf mit `node:test` (siehe unten); löst `$lib/` und Importe ohne Endung auf |
| `frontend/src/routes/__tests__/layout-ssr-hooks.mjs`, `onboardingSsr.ts` | tooling | Vorhandener SSR-Aufbau für Render-Tests |
| ADR-0104, ADR-0095 | adr | Sprache am Nutzer; jede Fläche liefert denselben Inhalt |

## Implementation Details

**Test-Werkzeug (Annahme zur Konvention):** Die Konventionen sprechen von Vitest. Das Frontend nutzt tatsächlich `node:test` (`npm test -- <datei>`, Aufruf `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test <datei>`); es gibt keine Vitest-Abhängigkeit. Alle neuen Tests folgen dem vorhandenen Stil (`import { test } from 'node:test'`), `locale.set('en')` bzw. `trFor('en', …)` statt Literalen.

**Katalog.** Der Bestand (112 Schlüssel) zieht ohne Umbenennung um, weil Tests und Komponenten die Schlüssel kennen. Zuordnung: `start.*` (30) → `start.json`; `nav.hilfe` (1) → `nav.json`; `hilfe.*` (42) → `hilfe.json`; `info.*` (9), `tip.*` (8), `telegram_kurzstil.*` (2), `standardwerte.knopf` (1) → `bausteine.json` (20); `onboarding.*` (19) → `home.json`. Der Schlüssel-Präfix muss deshalb nicht dem Dateinamen entsprechen; Parität gilt je Dateiname. Alle 112 Schlüssel erhalten Englisch (nach Glossar), damit der Paritätstest vom ersten Tag an grün ist. Neu in `aktionen.json` (für `fmtRelativeMinutes`): `aktionen.zeit.vor_minuten.one`/`.other` (de `vor {count} Min`, en `{count} min ago`) und `aktionen.zeit.gerade_eben` (de `gerade eben`, en `just now`); sie haben ihren Verwender in `format.ts`.

**Schnittstelle (aus Konventionen Abschnitt 3, unverändert):**

```ts
export type Lang = 'de' | 'en';
export type MessageKey = keyof typeof de;                       // Vereinigung aller Bereichsdateien
export const locale: Writable<Lang>;
export const t: Readable<(key: MessageKey, params?: Record<string, string | number>) => string>;
export const tn: Readable<(key: string, count: number, params?) => string>;
export function tr(key: MessageKey, params?): string;           // get(locale)
```

**Zusatz (additiv, Annahme):** `export function trFor(lang: Lang | undefined, key: MessageKey, params?): string`. Serverseitige Actions und Loader kennen die Sprache aus `locals.lang` und dürfen sich nicht auf den gemeinsamen Store verlassen; `undefined` ergibt `de` (Unit-Tests rufen Actions ohne `locals.lang` auf). `tr(key)` ist `trFor(get(locale), key)`.

**Kern `translate.ts`:** ersetzt `{name}` durch `String(params[name])`; ein fehlender Parameter bleibt als `{name}` sichtbar (kein Absturz). `translatePlural` wählt `<key>.one` bei `count === 1`, sonst `<key>.other`, und stellt `{count}` implizit bereit. Fehlt der englische Wert, wird der deutsche ausgegeben und je Schlüssel und Prozess einmal `console.warn('i18n fallback: <key>')` geschrieben. Tests übergeben einen kleinen echten Katalog als Argument.

**Auflösung.** `resolveLang` nimmt den Cookiewert `gz_lang`, sonst den ersten unterstützten Eintrag von `Accept-Language` (Hauptsprache vor `-`/`;`, `en-GB` → `en`, `fr-FR` → weiter, kein Treffer → `de`). In `hooks.server.ts` zu Beginn von `handle`: `event.locals.lang = resolveLang({ cookie: event.cookies.get('gz_lang'), acceptLanguage: event.request.headers.get('accept-language') })`. Alle drei Aufrufe `resolve(event)` werden zu `resolve(event, { transformPageChunk: ({ html }) => html.replace('%lang%', event.locals.lang) })` (der Wert wird beim Ersetzen gelesen, damit der Layout-Loader ihn für angemeldete Nutzer noch überschreiben kann).

**Layout-Loader.** In `+layout.server.ts` wird `profile?.language` übernommen, wenn es `'de'` oder `'en'` ist; sonst bleibt `locals.lang` (Profil nicht ladbar oder Abruf scheitert). Danach `locals.lang = lang` und `return { …, lang }`. Beispiel vorher → nachher (`+layout.server.ts:30-37`): `return { userId: locals.userId, … onboarding: … };` → dasselbe Objekt plus `lang`.

**Beispiel-Umstellung (Aufrufstelle, `frontend/src/routes/_start/Startseite.svelte:25`):** `<h1>{t('start.hero.title')}</h1>` → `<h1>{$t('start.hero.title')}</h1>`; und `frontend/src/routes/_start/Startseite.svelte:8-12` `const bilder = [ { src: t('start.mail.src'), … } ]` → `const bilder = $derived([ { src: $t('start.mail.src'), … } ])`.

**Beispiel-Schlüssel (de / en, Glossar):**

| Schlüssel | de | en |
|---|---|---|
| `start.cta.register` | Registrieren | Sign up |
| `start.cta.login` | Anmelden | Sign in |
| `start.hero.title` | Das Wetter für deine Etappe, dort wo du bist. | The weather for your stage, right where you are. |
| `nav.hilfe` | Hilfe | Help |
| `standardwerte.knopf` | Mit Standardwerten speichern | Save as defaults |
| `onboarding.willkommen.neuer_trip` | + Neuer Trip | + New trip |
| `start.ankommt.kanaele` (Auszug) | …SMS oder Satelliten-Messenger mit Rückkanal sind in Arbeit bzw. auf Anfrage. | …SMS or satellite messenger with a return channel are in progress or available on request. |

**Formate** (`format.ts`, arbeitet auf den lokalen Bestandteilen des übergebenen `Date`; die Zeitzonenwahl liegt beim Aufrufer, siehe #1727 S5e): `fmtDate(d,'de','kurz')` = `Fr 30.10.`, `(…,'en','kurz')` = `Fri 30 Oct`, `lang`: `Freitag, 30. Oktober 2026` bzw. `Friday, 30 October 2026`; `fmtTime` = `14:30` (24 h); `fmtWeekday(d,'de')` = `Fr`, `'en'` = `Fri`; `fmtRelativeMinutes(3,'de')` = `vor 3 Min`, `'en'` = `3 min ago` (`tn`; kleiner als eine Minute → `gerade eben`/`just now`). Der 30.10.2026 ist ein Freitag (die Beispielzeile `Do 30.10.` in den Konventionen ist nur eine Format-Illustration).

**Allowlist-Eintrag:** keiner (die Ratsche entsteht erst in #2649). **Golden:** `fixtures/de_katalog_vor_i18n.json` entsteht aus der alten `de.json` VOR dem Löschen, byte-gleiche Werte. **Validator/Token-Wächter:** nicht berührt.

## Expected Behavior

- **Input:** Seitenanfrage mit/ohne Sitzung, Cookie `gz_lang`, Header `Accept-Language`; Profil mit `language`.
- **Output:** HTML mit `<html lang="de|en">`; `data.lang`; Texte der Startseite und aller bereits katalogisierten Flächen in der gewählten Sprache; Deutsch unverändert.
- **Side effects:** Keine Schreibzugriffe. `console.warn` einmal je fehlendem Schlüssel.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer, dessen Profil `language: "en"` liefert, ohne Cookie und ohne `Accept-Language` / When die Startseite `/` serverseitig gerendert wird / Then lautet das Wurzelelement `<html lang="en">` und die Startseite zeigt die englischen Katalogtexte (zum Beispiel „Sign up" und „Sign in").
  - Test: frontend/src/routes/__tests__/sprache_je_anfrage_ssr.test.ts — echter Layout-Loader und `handle` mit `transformPageChunk`, SSR-Render der Seite, Prüfung von `lang` und sichtbarem Text.

- **AC-2:** Given ein Besucher ohne Anmeldung / When die Sprache aufgelöst wird / Then gilt: `Accept-Language: en-GB` ergibt `en`, `fr-FR` ergibt `de`, Cookie `de` mit `Accept-Language: en` ergibt `de`, Cookie `xx` (ungültig) fällt auf den Header zurück, und ohne Cookie und Header ergibt sich `de`.
  - Test: frontend/src/lib/i18n/__tests__/sprachaufloesung.test.ts — fünf Fälle gegen `resolveLang` und gegen das echte `handle` (`locals.lang`).

- **AC-3:** Given ein Schlüssel fehlt in einer englischen Bereichsdatei oder hat andere Platzhalter als der deutsche / When der Paritätstest läuft / Then ist er rot und nennt Bereich und Schlüssel; mit den echten Dateien ist er grün.
  - Test: frontend/src/lib/i18n/__tests__/paritaet_de_en.test.ts — echte Prüffunktion mit absichtlich kaputten Katalog-Objekten (rot mit Schlüsselname) und mit den echten 17 Bereichspaaren (grün). `# doc-compliance-test` (Paritätstest).

- **AC-4:** Given ein Katalog mit `{name}`-Platzhalter, `.one`/`.other`-Plural und fehlendem englischem Eintrag / When übersetzt wird / Then ersetzt `t` den Platzhalter in beiden Sprachen, `tn` wählt `.one` bei 1 und `.other` bei 0 und 2, `{count}` ist verfügbar, und der Fallback gibt den deutschen Text aus und warnt je Schlüssel genau einmal.
  - Test: frontend/src/lib/i18n/__tests__/platzhalter_plural_fallback.test.ts — echte `translate`-Funktion mit kleinem Katalog; `console.warn` wird mitgezählt.

- **AC-5:** Given der Stand vor diesem Paket / When die deutschen Texte aus den neuen Bereichsdateien mit der gesicherten alten Katalogdatei verglichen werden / Then sind alle 112 Schlüssel und Werte identisch, und kein deutscher Text hat sich verändert.
  - Test: frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts — vergleicht die vereinigte `de`-Karte mit `fixtures/de_katalog_vor_i18n.json` (Golden, byte-gleich).

- **AC-6:** Given drei Anfragen mit verschiedener Sprache (Nutzer A mit Profil `en`, danach Nutzer B mit Profil `de`, danach ein Besucher mit Header `en`) / When sie nacheinander serverseitig gerendert werden / Then trägt jede Antwort ihre eigene Sprache in `data.lang`, `<html lang>` und Text, und keine Anfrage übernimmt den Zustand der vorigen.
  - Test: frontend/src/routes/__tests__/sprache_je_anfrage_ssr.test.ts — drei Renderläufe mit echtem Layout-Loader (Profilabruf über das übliche Test-`fetch`), Vergleich je Lauf.

- **AC-7:** Given feste Zeitpunkte / When `fmtDate`, `fmtWeekday`, `fmtTime` und `fmtRelativeMinutes` aufgerufen werden / Then liefern sie `Fr 30.10.` / `Fri 30 Oct`, `Freitag, 30. Oktober 2026` / `Friday, 30 October 2026`, `Fr` / `Fri`, `14:30` in beiden Sprachen, `vor 3 Min` / `3 min ago` und `vor 1 Min` / `1 min ago`.
  - Test: frontend/src/lib/i18n/__tests__/format_datum_zeit.test.ts — lokale `Date`-Objekte (zeitzonenunabhängig), Erwartungen mit berechneten Wochentagen.

- **AC-8:** Given die englischen Texte / When die Regeln geprüft werden / Then enthält kein englischer Wert „tour", jeder englische `start.*`-Wert mit „SMS" oder „satellite" enthält „in progress" und „on request", Fachbegriffe folgen dem Glossar (zum Beispiel „stage", „location comparison", „target ranges"), und `t('start.unbekannt')` ist ein Typfehler (`@ts-expect-error`).
  - Test: frontend/src/lib/i18n/__tests__/en_katalog_regeln.test.ts — liest die englischen Werte als Daten (`# doc-compliance-test`), plus Typprüfung über `@ts-expect-error`; `npm run check` (svelte-check) bleibt grün.

## Known Limitations

- Annahme: Die Konventionen und das Issue nennen Vitest und „112 `start.*`-Schlüssel". Tatsächlich laufen die Frontend-Tests mit `node:test`, und die 112 Bestandsschlüssel verteilen sich auf `start`, `nav`, `hilfe`, `info`, `tip`, `telegram_kurzstil`, `standardwerte`, `onboarding`. Dieses Paket übersetzt alle 112, damit die Parität sofort gilt; Paket #2651 (F2) prüft die Texte von `hilfe`, `bausteine` und `home` zusätzlich gegen das Glossar.
- Annahme: Die Bestandspräfixe `info`, `tip`, `telegram_kurzstil`, `standardwerte`, `onboarding` werden nicht umbenannt (Tests und Komponenten referenzieren sie); neue Schlüssel folgen `bereich.gruppe.element` mit dem Bereichsnamen als Präfix.
- Annahme: Beim Serverrendern ist der Store `locale` ein gemeinsamer Zustand; das Rendern ist synchron und `locale.set` steht vor dem ersten Kind. Server-Actions und -Loader nutzen `trFor(locals.lang, …)`, nie `tr`.
- Die Antwort variiert mit Cookie und `Accept-Language`, trägt aber keinen `Vary`-Header; HTML-Antworten sind ohnehin `no-cache` und der Service Worker legt `/` nie ab.
- Die Texte in `+layout.svelte` (Update-Hinweis, iOS-Hinweis, Passkey-Angebot) bleiben deutsch. Kein Paket des Epics ist dafür ausdrücklich zuständig; sie stehen in der Allowlist (#2649) und werden als Nebenbefund an Paket #2653 (F4) gemeldet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (Nr. 1, 3, 6, 9)
- **Rationale:** Eine Technik für alle Schichten: flacher, typisierter Katalog je Bereich ohne neue Abhängigkeit und eine einzige Auflösungsstelle je Anfrage.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
