---
entity_id: sprachumschalter_angemeldet_3337
type: bugfix
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: fix-3337-sprachumschalter-angemeldet
tags: [i18n, frontend, funktionen]
---

# Sprach-Umschalter für Angemeldete ausblenden, Hinweis aufs Konto (Bug #3337)

## Approval

- [ ] Approved

## Purpose

Auf den öffentlichen Funktionsseiten (`/funktionen`, `/funktionen/<thema>`) sehen Angemeldete einen Sprach-Umschalter `DE | EN`, der nichts bewirkt, weil bei Angemeldeten die im Konto gespeicherte Sprache vor das Cookie gestellt wird. Nach PO-Entscheidung (Option c, 2026-11-24) zeigt die Seite Angemeldeten stattdessen einen kurzen Hinweis mit Link zur Sprachwahl im Konto; Besucher ohne Anmeldung behalten den Umschalter unverändert.

## Source

- **File:** `frontend/src/lib/components/organisms/funktionen/FunktionenKopf.svelte`
- **Identifier:** Kopfbereich `FunktionenKopf` (Umschalter oder Hinweis, je nach `page.data.userId`)

> **Schicht-Hinweis:** Reines SvelteKit-Frontend (`frontend/src/...`). Go-API, Python-Core und die Funktions-Loader bleiben unberührt.
>
> **Querschnitt:** Trip/Ortsvergleich-Pendant: keins (öffentliche Doku-Seiten). Mandantentrennung: es werden keine Nutzerdaten bewegt, nur der Anmeldestatus aus den Layout-Daten gelesen; getestet wird dennoch mit zwei Zuständen (angemeldet/abgemeldet). Kanäle: nicht betroffen.

## Estimated Scope

- **LoC:** Code ca. +20, Tests ca. +90
- **Files:** 7
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$app/state` (`page.data.userId`) | module | Anmeldestatus aus den Layout-Daten (`+layout.server.ts`), ohne Nutzerdaten in den Funktions-Loadern |
| `$lib/i18n` (`t`) | module | Hinweistext und Linktext aus dem Katalog |
| `SprachUmschalter.svelte` | component | bleibt unverändert, nur noch für Abgemeldete im Kopf |
| `SpracheAuswahl.svelte` | component | Ankerziel: Select `id="sprache"` auf `/account` |
| `oeffentliche_doku_3319` | spec | AC-4 (Loader ohne Nutzerdaten), AC-6/AC-11 (Umschalter) werden präzisiert |
| `i18n_s3_sprachumschalter_konto_2648` | spec | Umschalter für Besucher, Sprache im Konto |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/organisms/funktionen/FunktionenKopf.svelte` | MODIFY | `page.data.userId` lesen: angemeldet → Hinweis `data-testid="sprach-hinweis"` mit Link `/account#sprache`; abgemeldet → `<SprachUmschalter />` wie bisher; Kopfkommentar anpassen |
| `frontend/src/lib/i18n/messages/de/konto.json` | MODIFY | neue Schlüssel `konto.sprache.hinweis_angemeldet`, `konto.sprache.hinweis_link` |
| `frontend/src/lib/i18n/messages/en/konto.json` | MODIFY | dieselben zwei Schlüssel auf Englisch (Parität) |
| `frontend/src/lib/components/organisms/funktionen/__tests__/funktionen_kopf_sprache.test.ts` | CREATE | SSR-Matrix-Test 2×2 (angemeldet/abgemeldet × DE/EN) mit `$app/state`-Stub (Vorbild `frontend/src/routes/__tests__/layout-ssr-hooks.mjs`, Seitendaten über `globalThis`) |
| `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts` | MODIFY | `$app/state`-Stub registrieren, da Übersicht und Unterseite den Kopf rendern |
| `frontend/e2e/funktionen-oeffentlich.staging.spec.ts` | MODIFY | Fälle für Angemeldete auf `/funktionen` und `/funktionen/trips` (Prüfkonto-Login) |
| `docs/specs/modules/oeffentliche_doku_3319.md` | MODIFY (Doku) | AC-6 und AC-11: „Sprachumschalter“ nur für Besucher ohne Anmeldung; Verweis auf diese Spec |

### Estimated Changes

- Files: 7
- LoC: +110/-5

## Implementation Details

Technischer Ansatz: Verifiziert ist, dass `hooks.server.ts` auf den Funktionsseiten (keine `publicPaths`) `locals.userId` setzt und `+layout.server.ts` die `userId` als Layout-Daten ausgibt. `FunktionenKopf.svelte` liest `page.data.userId` aus `$app/state`; die Funktions-Loader bleiben unverändert und liefern weiter keine Nutzerdaten (Spec 3319 AC-4). Der Zustand ist beim Server-Rendern und beim Hydrieren identisch.

Wortlaut (Duzen wie im übrigen Konto-Katalog, Sentence case im Englischen, kein Ausrufezeichen), zur Freigabe:

| Schlüssel | DE | EN |
|-----------|----|----|
| `konto.sprache.hinweis_angemeldet` | Die Sprache stellst du in deinem Konto ein. | You set your language in your account. |
| `konto.sprache.hinweis_link` | Zum Konto | Go to account |

Der Hinweistext steht als Satz, der Link `Zum Konto` / `Go to account` zeigt auf `/account#sprache`. Texte kommen ausschließlich über `$t(...)`. Der Hinweis liegt im `<header>` außerhalb der `main`-Kontrastmessung; deshalb wird ein kontraststarkes Text-Token (Primärtext, nicht gedämpft) und für den Link ein unterstrichener Link in Textfarbe gewählt (WCAG-AA, Design-Leitprinzip hoher Kontrast).

Ausdrücklich unverändert (Befund, nicht Teil der Änderung):

- `/` zeigt Angemeldeten nie die öffentliche Startseite; dort gibt es für sie keinen Umschalter.
- `/login` und `/register` sind `publicPaths` (Sitzung wird nicht gelesen), das Cookie wirkt, der Umschalter funktioniert.
- `SprachUmschalter.svelte`, `+layout.server.ts`, die Funktions-Loader.

## Expected Behavior

- **Input:** Aufruf von `/funktionen` oder `/funktionen/<thema>`, angemeldet oder nicht, Sprache DE oder EN.
- **Output:** Angemeldet: Hinweis in der Profilsprache mit Link zum Konto, kein Umschalter. Abgemeldet: Umschalter `DE | EN`, kein Hinweis.
- **Side effects:** keine.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN angemeldet, Sprache DE / WHEN `FunktionenKopf` gerendert wird / THEN kein Umschalter, Hinweis auf Deutsch mit Link `/account#sprache`
- [ ] Test 2: GIVEN angemeldet, Sprache EN / WHEN gerendert / THEN kein Umschalter, Hinweis auf Englisch mit Link `/account#sprache`
- [ ] Test 3: GIVEN abgemeldet, DE und EN / WHEN gerendert / THEN Umschalter `DE | EN` vorhanden, kein Hinweis
- [ ] Test 4: GIVEN Seitenliste der Funktionsseiten / WHEN Übersicht und jede Unterseite für beide Zustände gerendert werden / THEN Verhalten wie Test 1 bis 3
- [ ] Test 5: GIVEN Katalog / WHEN Paritätstest und Hardcode-Ratsche laufen / THEN beide neuen Schlüssel in DE und EN, keine festen Texte im Kopf
- [ ] Test 6 (Staging, Prüfkonto): GIVEN angemeldet / WHEN `/funktionen` und `/funktionen/trips` geöffnet und der Link angeklickt wird / THEN kein Umschalter, Seite `/account#sprache`, Select `#sprache` sichtbar
- [ ] Test 7 (Staging, Prüfkonto): GIVEN angemeldet auf `/funktionen` / WHEN Hinweis- und Linkfarbe gegen den Kopfhintergrund gemessen und per Tab-Taste fokussiert wird / THEN Kontrast mindestens 4,5 : 1, Link unterstrichen und per Tastatur erreichbar (AC-6)

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer mit Profilsprache Deutsch / When er `/funktionen` oder `/funktionen/trips` öffnet / Then sieht er im Seitenkopf keinen Sprach-Umschalter `DE | EN`, sondern den deutschen Hinweis „Die Sprache stellst du in deinem Konto ein.“ mit dem Link „Zum Konto“.
  - Test: SSR-Render der Kopfzeile mit angemeldetem Zustand und DE (Übersicht und Unterseite); Staging-Seitentest mit Prüfkonto findet keinen Umschalter und den Hinweis.

- **AC-2:** Given ein angemeldeter Nutzer mit Profilsprache Englisch / When er `/funktionen` oder `/funktionen/trips` öffnet / Then sieht er keinen Umschalter, sondern den englischen Hinweis „You set your language in your account.“ mit dem Link „Go to account“.
  - Test: SSR-Render der Kopfzeile mit angemeldetem Zustand und EN; Staging-Test mit dem englischen Prüfkonto.

- **AC-3:** Given ein angemeldeter Nutzer sieht den Hinweis auf einer Funktionsseite / When er auf den Link klickt / Then landet er auf `/account#sprache` und die Sprachauswahl (Select `#sprache`) ist sichtbar.
  - Test: Staging-E2E mit Prüfkonto: Klick auf den Link, URL endet auf `/account#sprache`, Select `#sprache` ist sichtbar.

- **AC-4:** Given ein Besucher ohne Anmeldung / When er `/funktionen` oder `/funktionen/trips` öffnet und im Umschalter die andere Sprache wählt / Then sieht er den Umschalter, keinen Hinweis, und die Seite erscheint in der gewählten Sprache wie bisher.
  - Test: SSR-Render abgemeldet in DE und EN (Umschalter da, kein Hinweis); Staging-Test ohne Cookie: Klick auf `EN` wechselt die Seitensprache.

- **AC-5:** Given Besucher ohne Anmeldung auf `/`, `/login` und `/register` / When sie den Umschalter benutzen / Then funktioniert er unverändert wie bisher, und diese Seiten zeigen den Konto-Hinweis nicht; Angemeldete sehen auf `/` weiterhin nie die öffentliche Startseite.
  - Test: bestehende Tests `sprachwechsel.spec.ts` und der Umschalter-Darstellungstest bleiben unverändert grün; Seitentest prüft, dass `sprach-hinweis` dort nicht vorkommt.

- **AC-6:** Given der Hinweistext im Seitenkopf / When ein Nutzer ihn liest / Then ist er mit hohem Kontrast (WCAG-AA, mindestens 4,5 : 1) lesbar, und der Link ist erkennbar unterstrichen und per Tastatur erreichbar.
  - Test: Playwright-Kontrastprüfung der Hinweis- und Linkfarbe gegen den Kopfhintergrund; Tab-Taste fokussiert den Link.

- **AC-7:** Given die Texte des Hinweises / When der Katalog geprüft wird / Then stehen beide Schlüssel in Deutsch und Englisch im Katalog (`konto.sprache.hinweis_angemeldet`, `konto.sprache.hinweis_link`) und im Kopf steht kein fest eingetragener Text.
  - Test: Paritätstest `paritaet_de_en.test.ts` und Hardcode-Ratsche bleiben grün; Render in EN zeigt den englischen Katalogtext.

- **AC-8:** Given ein Aufruf der Funktionsseiten / When die Seitendaten geladen werden / Then liefern die Funktions-Loader weiterhin keine Nutzerdaten und rufen die Go-API nicht auf; der Anmeldestatus kommt nur aus den Layout-Daten.
  - Test: bestehender Hook-/Loader-Test aus Spec 3319 AC-4 bleibt grün; Staging ohne Cookie liefert 200 und keinen Aufruf an `/api`.

- **AC-9:** Given zwei Zustände, ein angemeldeter und ein abgemeldeter Nutzer, jeweils in Deutsch und Englisch / When die Funktionsseiten für alle vier Kombinationen gerendert werden / Then zeigt jede Kombination genau das erwartete Element (angemeldet: Hinweis, abgemeldet: Umschalter) und nie beides oder keines.
  - Test: SSR-Matrix-Test 2×2 mit `$app/state`-Stub, getrennte Seitendaten je Zustand, keine Übernahme von Zustand zwischen den Fällen.

## Definition of Done

- AC-1, AC-2, AC-4, AC-7 und AC-9 durch den SSR-Matrix-Test 2×2 und den Paritätstest (node --test) belegt, Kern-Schicht grün; Pflicht-Mutationen (Bedingung umgedreht, Linkziel falsch, Hinweis fest eingetragen) werden gefangen
- AC-3 und AC-6 auf Staging mit Prüfkonto belegt (Link führt zu `/account#sprache`, Select sichtbar, Kontrast mindestens 4,5 : 1, Link per Tastatur erreichbar)
- AC-5 und AC-8: bestehende Umschalter-, Sprachwechsel- und Loader-Tests unverändert grün
- Nachtrag in `oeffentliche_doku_3319.md` (AC-6/AC-11: Umschalter nur ohne Anmeldung)
- Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Known Limitations

- Angemeldete bekommen keinen Direktwechsel auf den Funktionsseiten; die Sprache ändern sie im Konto (PO-Entscheidung Option c).
- Der Hinweis ist nur im Kopf der Funktionsseiten vorgesehen; weitere öffentliche Seiten zeigen Angemeldeten keinen Umschalter.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (folgt ADR-0104: Sprache am Nutzer, Besucher über Cookie)
- **Rationale:** reine Darstellungsänderung in einer Komponente, keine neue Entscheidungsfläche; ADR-0104 wird weder geändert noch abgelöst.

## Changelog

- 2026-11-24: Initial spec created (Bug #3337, PO-Entscheidung Option c)
