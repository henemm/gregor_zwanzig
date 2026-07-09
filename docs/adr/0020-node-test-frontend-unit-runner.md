# ADR-0020: node:test ist der kanonische Frontend-Unit-Test-Runner (kein vitest)

- **Status:** Akzeptiert
- **Datum:** 2026-07-02
- **Bezug:** GitHub-Issue #975, Spec `docs/specs/modules/fix_972_974_975_tooling.md`

## Kontext

Issue #975 meldete, die Frontend-Vitest-Suite melde „No test suite found" für alle 284
Test-Dateien bei Exit 1, obwohl die Tests real bestehen. Die Analyse ergab: **Das Projekt
hat nie vitest benutzt.** Die 163 Unit-Tests unter `frontend/src/**/*.test.ts` importieren
durchgehend den Node-eigenen Runner (`import { test } from 'node:test'`, Ausführung via
`node --experimental-strip-types --test`, dokumentiert u.a. in
`frontend/src/lib/contrast-audit.test.ts`); die 121 `e2e/**/*.spec.ts` gehören zu
Playwright. `npx vitest run` lud ein fremdes Ad-hoc-vitest, das in den node:test-Dateien
keine Suiten findet — während node:test die Tests beim Import selbst ausführte und so die
verwirrenden grünen TAP-Zeilen im selben Output erzeugte. Weil `package.json` kein
`"test"`-Script hatte, griffen Sessions immer wieder zum falschen Befehl; die Suite lief
nie routinemäßig und verrottete (128 Fehlschläge, aufgeräumt in diesem Workflow).

## Entscheidung

Wir verwenden **node:test** (Node ≥ 22, `node --import ./test-lib-loader.mjs
--experimental-strip-types --test`) als einzigen Runner für Frontend-Unit-Tests.
Der kanonische Aufruf ist `npm test` in `frontend/` (Script in `frontend/package.json`).
vitest wird **nicht** eingeführt; E2E bleibt bei Playwright (`e2e/**/*.spec.ts`,
eigene Configs).

## Verworfene Alternativen

- **vitest nachrüsten** (als Dependency installieren, Config anlegen, 163 Tests auf
  vitest-Imports umschreiben) — großer Umbau ohne funktionalen Gewinn; die bestehenden
  Tests brauchen weder jsdom noch Vite-Transformationen, und node:test läuft ohne
  `node_modules` mit Bordmitteln.
- **Kein `test`-Script definieren (Status quo)** — genau das führte zu #975: Ohne
  definierten Befehl greifen Menschen und Agenten zu `npx vitest` und misstrauen dann
  der „kaputten" Suite.

## Konsequenzen

- **Positiv:** `npm test` ist wieder ein verlässliches, schnelles Signal (~6 s, keine
  Installation nötig); Fehlbedienung per `npx vitest` ist durch dieses ADR und das
  Script ausgeschlossen.
- **Negativ / Preis:** node:test bietet kein Svelte-Komponenten-Rendering — Unit-Tests
  bleiben auf reine Funktionen/Helpers beschränkt; UI-Verhalten gehört in Playwright-E2E
  (das entspricht der Projektregel „echtes Verhalten statt Quelltext-Checks").
- **Folgepflichten:** Neue Frontend-Unit-Tests importieren `node:test`
  (nicht `vitest`); der `$lib`-Alias läuft über `frontend/test-lib-loader.mjs` —
  Änderungen an den Aliassen müssen dort nachgezogen werden. Vorschläge, vitest
  einzuführen, müssen dieses ADR ablösen.
