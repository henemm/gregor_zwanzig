// Issues #477 + #486 — Atomic-Design-Migration der Trip-Liste (Stand nach #2278).
//
// Spec: docs/specs/modules/trips_atomic_kebab.md
// Route: /trips  →  frontend/src/routes/trips/+page.svelte
//
// Source-Inspection-Tests (analog zu issue_402.test.ts). Mit #2278 abgeschafft und hier gestrichen:
//   AC-4 (Primaer-Button-Labels "Archivieren"/"Fertigstellen": toter Code entfernt, Liste blendet Archiviertes aus),
//   AC-5 ("Pausieren" im Kebab: kommt jetzt aus subscriptionActions, bewacht in subscriptionActions.test.ts),
//   AC-6 (ReportConfigDialog/TestReportDialog: geloescht, ersetzt durch SendConfirmDialog und Hub-Reiter
//         "Alarme"/"Wetter-Metriken"; Abwesenheit bewacht versand_speichern_erhaelt_report_config.test.ts),
//   Kebab-Label "Alerts justieren" (Aktion "Alert-Konfiguration" existiert nicht mehr).
//
// Ausführung:
//   cd frontend && npm test -- src/routes/trips/issue_477_486.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const TRIPS_DIR = dirname(fileURLToPath(import.meta.url));
const PAGE_SVELTE = join(TRIPS_DIR, '+page.svelte');

function readPage(): string {
	return readFileSync(PAGE_SVELTE, 'utf-8');
}

// ── AC-1: Keine ui/-Importe mehr in +page.svelte ─────────────────────────────

describe('AC-1: Keine direkten ui/-Importe in +page.svelte', () => {
	for (const [id, modul] of [
		['AC-1a', 'ui/table'],
		['AC-1b', 'ui/dialog'],
		['AC-1c', 'ui/checkbox'],
		['AC-1d', 'ui/select'],
		['AC-1e', 'ui/empty-state']
	]) {
		test(`${id}: kein ${modul}-Import`, () => {
			assert.ok(!readPage().includes(modul), `Import aus '$lib/components/${modul}' noch vorhanden`);
		});
	}
});

// ── Status-Caption: mono-Kürzel neben Trip-Name ──────────────────────────────
// Issue #1277: Die Desktop-Tabelle rendert die Namensspalte über das geteilte
// ListNameCell-Organism; die Trip-Übersicht gibt dem Namen einen Status-Label mit.
describe('Status-Caption neben Trip-Name (geteilte ListNameCell)', () => {
	test('status-caption CSS-Klasse in ListNameCell vorhanden', () => {
		const nameCell = join(TRIPS_DIR, '..', '..', 'lib', 'components', 'organisms', 'ListNameCell.svelte');
		assert.match(readFileSync(nameCell, 'utf-8'), /status-caption/, '"status-caption" fehlt in ListNameCell');
	});

	test('trips/+page.svelte übergibt der Namensspalte einen statusLabel', () => {
		assert.match(readPage(), /statusLabel/, 'trips/+page.svelte gibt der Namensspalte keinen statusLabel mit');
	});
});
