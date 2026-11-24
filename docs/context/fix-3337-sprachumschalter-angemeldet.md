# Context: fix-3337-sprachumschalter-angemeldet

## Request Summary
Issue #3337 (Bug, PO-Entscheidung Option c): Angemeldete sehen auf den öffentlichen
Funktionsseiten den Sprach-Umschalter DE|EN, der wirkungslos ist (Profilsprache
überschreibt das Cookie). Für Angemeldete ausblenden, stattdessen kurzer Hinweis
(DE/EN aus dem Katalog) mit Link zur Sprachwahl im Konto. Ohne Anmeldung unverändert.

## Befund zum tatsächlichen Wirkort
- `/` zeigt Angemeldeten NIE die öffentliche Startseite (`routes/+page.svelte:195`,
  `routes/+layout.svelte:219`): dort ist kein Umschalter für Angemeldete → nichts zu tun.
- `/login`, `/register` sind `publicPaths` in `hooks.server.ts:49`: dort wird die Sitzung
  nicht gelesen, `locals.userId` bleibt leer, die Cookie-Sprache wirkt → Umschalter funktioniert,
  nicht betroffen.
- Betroffen sind allein `/funktionen` und `/funktionen/[thema]`: beide rendern
  `FunktionenKopf.svelte` (über `FunktionenUebersicht` / `FunktionenUnterseite`), und dort
  läuft `+layout.server.ts` mit `locals.userId` → `lang = profile.language`.

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/organisms/funktionen/FunktionenKopf.svelte | einziger Ort der Änderung: Umschalter vs. Hinweis |
| frontend/src/lib/components/ui/SprachUmschalter.svelte | bleibt unverändert |
| frontend/src/routes/+layout.server.ts | liefert `userId` und `lang` (Profil > Cookie) als Layout-Daten |
| frontend/src/routes/funktionen/+page.server.ts, [thema]/+page.server.ts | Loader bewusst OHNE userId (Spec 3319 AC-4) → Anmeldestatus aus Layout-Daten (`page.data.userId`) lesen, Loader nicht ändern |
| frontend/src/lib/components/account/SpracheAuswahl.svelte | Sprachwahl im Konto, Select mit `id="sprache"` → Linkziel `/account#sprache` |
| frontend/src/lib/i18n/messages/{de,en}/konto.json | Katalog `konto.sprache.*` → neuer Schlüssel für den Hinweis |
| frontend/src/lib/components/ui/__tests__/sprach_umschalter_darstellung.test.ts | SSR-Render-Test des Umschalters (Muster für den neuen Test) |
| frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts | SSR-Render der Funktionsseiten DE/EN |
| frontend/e2e/funktionen-oeffentlich.staging.spec.ts, e2e/sprachwechsel.spec.ts | Staging-/E2E-Prüfungen |

## Existing Patterns
- Anmeldestatus in Komponenten: Layout-Daten `data.userId` (`+layout.svelte`); in Organismen
  über `page.data` aus `$app/state`.
- Texte nur über Katalog `$t(...)`, DE und EN je Schlüssel (ADR-0104, i18n_konventionen.md).
- SSR-Render-Tests mit `node --test` + Hook-Stubs für `$app/*`.

## Dependencies
- Upstream: `$app/state` (page.data), `$lib/i18n`.
- Downstream: FunktionenUebersicht, FunktionenUnterseite.

## Existing Specs
- `docs/specs/modules/i18n_s3_sprachumschalter_konto_2648.md` (Umschalter, Konto-Sprache)
- `docs/specs/modules/oeffentliche_doku_3319.md` (Funktionsseiten, AC-4 Loader ohne Nutzerdaten, AC-11 Kopf)

## Risks & Considerations
- Spec 3319 AC-4: Loader darf keine Nutzerdaten liefern → Status aus Layout-Daten lesen.
- Bausteine-Wächter (`bausteine_waechter_regeln.ts`) kennt SprachUmschalter-Verwendungsorte.
- Hardcode-Wächter: keine festen Texte, alles aus dem Katalog.
- Kontrast WCAG-AA für den Hinweistext.

## Analysis

### Type
Bug (Lösung nach PO-Entscheidung Option c, 24.11.2026)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/organisms/funktionen/FunktionenKopf.svelte | MODIFY | `page.data.userId` (`$app/state`) lesen: angemeldet → Hinweis `data-testid="sprach-hinweis"` mit Link `/account#sprache`; abgemeldet → `<SprachUmschalter />` wie bisher. Kopfkommentar anpassen. |
| frontend/src/lib/i18n/messages/de/konto.json, en/konto.json | MODIFY | neue Schlüssel `konto.sprache.hinweis_angemeldet` + `konto.sprache.hinweis_link` (DE/EN-Parität) |
| frontend/src/lib/components/organisms/funktionen/__tests__/ (neu) oder lib/i18n/__tests__/ | CREATE | SSR-Matrix-Test 2×2 (angemeldet/abgemeldet × DE/EN) |
| `$app/state`-Stub für SSR-Tests | CREATE/MODIFY | Vorbild `src/routes/__tests__/layout-ssr-hooks.mjs` (liefert schon `$app/state`, Pfad über globalThis) → um `page.data` erweitern bzw. eigenen Stub mit `globalThis.__pageData`; auch in `funktionen_seite.test.ts` registrieren, da Übersicht/Unterseite den Kopf rendern und sonst brechen |
| frontend/e2e/funktionen-oeffentlich.staging.spec.ts (oder neue eingeloggte Staging-Spec) | MODIFY/CREATE | angemeldet: kein Umschalter auf `/funktionen` und `/funktionen/trips`, Link führt zu `/account#sprache`, Select `#sprache` sichtbar |
| docs/specs/modules/oeffentliche_doku_3319.md | MODIFY (Doku) | AC-6/AC-11 „Sprachumschalter“ auf „nur ohne Anmeldung“ präzisieren |

Unverändert: `SprachUmschalter.svelte` (Startseite/Login/Register zeigen ihn nur Abgemeldeten), Funktions-Loader (Spec 3319 AC-4: keine Nutzerdaten), `+layout.server.ts`.

### Scope Assessment
- Dateien: ~5–6
- Geschätzte LoC: Code +20, Tests ~+90
- Risiko: LOW (eine Darstellungskomponente, nur Kopfbereich zweier öffentlicher Seiten)

### Technical Approach
Verifiziert: `hooks.server.ts` setzt `locals.userId` auch auf den Funktionsseiten (keine publicPaths), `+layout.server.ts` gibt `userId` aus → `page.data.userId` ist dort korrekt und hydriert ohne Abweichung. Bedingung in `FunktionenKopf`; Text nur über Katalog; Farbe über vorhandenes Text-/Muted-Token mit WCAG-AA (Hinweis liegt im `<header>`, außerhalb der `main`-Kontrastmessung → Token bewusst kontraststark wählen). Bausteine-Wächter neutral (SprachUmschalter-Bestand unverändert).

### Dependencies
`$app/state` (page.data), `$lib/i18n` (`t`), Konto-Select `id="sprache"` in `SpracheAuswahl.svelte` als Ankerziel (Konto-Seite ohne Reiter, Anker scrollt direkt).

### Open Questions
- keine (PO-Entscheidung liegt vor; Hinweistext-Wortlaut wird in der Spec zur Freigabe vorgelegt)
