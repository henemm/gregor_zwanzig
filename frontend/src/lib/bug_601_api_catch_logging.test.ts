// TDD RED: Bug #601 — Frontend API-catch-Blöcke müssen console.error(e) enthalten
//
// Spec: docs/specs/modules/bug_601_round_trip_catchblocks.md
//
// Source-Inspection-Test (Pattern wie contrast-audit.test.ts): liest die echten
// .svelte/.ts-Quelldateien und prüft, dass jeder API-catch-Block console.error(e)
// enthält. Keine Mocks, kein node_modules — nur Node-Bordmittel.
//
// RED: Die 5 betroffenen catch-Blöcke haben noch kein console.error(e)
//      → alle 5 Asserts FAIL.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/bug_601_api_catch_logging.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

// Jeder Eintrag beschreibt einen API-catch-Block der console.error braucht.
// catchLine: 1-basierte Zeilennummer des "} catch {" (entspricht grep-Output)
// window: wie viele Zeilen nach dem catch wir prüfen
const API_CATCHES = [
  {
    file: 'lib/components/compare/compareWizardState.svelte.ts',
    catchLine: 82,
    label: 'compareWizardState PUT /api/subscriptions/{id}',
    window: 5,
  },
  {
    file: 'routes/trips/[id]/+page.svelte',
    catchLine: 133,
    label: 'trips/[id] POST /api/scheduler/trip-reports',
    window: 5,
  },
  {
    file: 'lib/components/compare/CompareTabs.svelte',
    catchLine: 42,
    label: 'CompareTabs GET /api/auth/profile',
    window: 5,
  },
  {
    file: 'lib/components/trip-detail/WeatherMetricsTab.svelte',
    catchLine: 364,
    label: 'WeatherMetricsTab GET /api/metrics',
    window: 5,
  },
  {
    file: 'lib/components/trip-wizard/steps/Step3Weather.svelte',
    catchLine: 91,
    label: 'Step3Weather GET /api/metrics',
    window: 5,
  },
];

describe('Bug #601: API-catch-Blöcke müssen console.error(e) enthalten (AC-1)', () => {
  for (const { file, catchLine, label, window } of API_CATCHES) {
    test(`${label} [${file}:${catchLine}]`, () => {
      const fullPath = join(SRC, file);
      const content = readFileSync(fullPath, 'utf-8');
      const lines = content.split('\n');

      // Verifiziere dass an catchLine - 1 (0-indexiert) tatsächlich "catch {" steht
      const catchIdx = catchLine - 1;
      const catchLineContent = lines[catchIdx] ?? '';
      assert.ok(
        catchLineContent.includes('catch'),
        `Zeile ${catchLine} enthält kein "catch": "${catchLineContent.trim()}"`
      );

      // Prüfe die nächsten `window` Zeilen auf console.error
      const block = lines.slice(catchIdx, catchIdx + window).join('\n');
      assert.ok(
        block.includes('console.error'),
        `Fehlend: console.error(e) in catch-Block bei ${file}:${catchLine}\n` +
        `Gefundener Block:\n${block}`
      );
    });
  }
});
