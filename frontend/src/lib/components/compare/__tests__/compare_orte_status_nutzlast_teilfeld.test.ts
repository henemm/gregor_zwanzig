// TDD RED — Issue #2375 (Epic #2345): Orte-Speichern und Pausieren/Aktivieren
// senden nur ihre eigenen Felder — kein Voll-Spread der (womöglich veralteten)
// Basis, der den Namen oder Reiter-Werte eines anderen Tabs zurückschreibt.
//
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
//   Test 4 / AC-9 — Orte: Body exakt { location_ids };
//                   Status: Body exakt { schedule, previous_schedule } (kein paused_at)
//   AC-6          — Pausieren auf der Listenseite `/compare` (roher fetch) ebenso
//
// Wo die Zusicherung wirkt: `persistPickedIds`/`handleToggleActive` stehen in
// `CompareTabs.svelte`, `togglePause` in `routes/compare/+page.svelte`. Beide
// werden als ECHTER Instanz-Code ausgeführt (svelteInstanzPruefstand.ts);
// zusätzlich die Bausteine `buildToggleActivePutPayload`/`buildFreshTogglePutPayload`
// direkt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_orte_status_nutzlast_teilfeld.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { buildFreshTogglePutPayload, buildToggleActivePutPayload } from '../compareHubPersistenz.ts';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { createGoMergeServer, vollerVergleich } from '../../shared/__tests__/goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const HUB = join(HIER, '..', 'CompareTabs.svelte');
const LISTE = join(FRONTEND, 'src/routes/compare/+page.svelte');

register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const ID = 'cp-2375-orte-status';
const voll = () => vollerVergleich(ID) as unknown as ComparePreset;

/** Aufzeichnendes `api` (nur `put`), antwortet mit dem Gesamtstand. */
function aufzeichnendesApi() {
	const puts: Array<{ url: string; body: Record<string, unknown> }> = [];
	return {
		puts,
		api: {
			put: async (url: string, body: unknown) => {
				puts.push({ url, body: body as Record<string, unknown> });
				return { ...vollerVergleich(ID), ...(body as Record<string, unknown>) };
			}
		}
	};
}

const saveController: Knoten = {
	setSaving: () => {},
	setSaved: () => {},
	setError: () => {},
	flush: async () => {}
};

describe('Test 4 / AC-9: Status-Bausteine liefern nur { schedule, previous_schedule }', () => {
	test('buildToggleActivePutPayload: Body exakt { schedule, previous_schedule }', () => {
		const { url, body } = buildToggleActivePutPayload(voll(), 'manual', 'daily');
		assert.equal(url, `/api/compare/presets/${ID}`);
		assert.deepEqual(body, { schedule: 'manual', previous_schedule: 'daily' });
	});

	test('buildFreshTogglePutPayload (Listen-Kebab): Body exakt { schedule, previous_schedule }', async () => {
		const { body } = await buildFreshTogglePutPayload(ID, async () => voll());
		assert.deepEqual(body, { schedule: 'manual', previous_schedule: 'daily' });
	});
});

describe('Test 4 / AC-9: der Hub (CompareTabs) sendet für Orte und Status nur die eigenen Felder', () => {
	async function hub(api: Knoten): Promise<Knoten> {
		const { u } = await umgebungFuer(HUB, { preset: voll(), locations: [], saveController, api, onScheduleChange: undefined });
		assert.equal(typeof u.persistPickedIds, 'function', 'Messaufbau: persistPickedIds nicht herleitbar');
		assert.equal(typeof u.handleToggleActive, 'function', 'Messaufbau: handleToggleActive nicht herleitbar');
		return u;
	}

	test('persistPickedIds (Ort entfernt): PUT-Rumpf exakt { location_ids }', async () => {
		const { api, puts } = aufzeichnendesApi();
		const u = await hub(api);
		await (u.persistPickedIds as (ids: string[]) => Promise<void>)(['loc-a', 'loc-c']);
		assert.equal(puts.length, 1, `Messaufbau: genau EIN PUT erwartet, gesehen ${puts.length}`);
		assert.deepEqual(puts[0].body, { location_ids: ['loc-a', 'loc-c'] });
	});

	test('handleToggleActive (Pausieren): PUT-Rumpf exakt { schedule, previous_schedule }, kein paused_at', async () => {
		const { api, puts } = aufzeichnendesApi();
		const u = await hub(api);
		const ok = await (u.handleToggleActive as () => Promise<boolean>)();
		assert.equal(ok, true, 'Messaufbau: Pausieren muss erfolgreich zurückmelden');
		assert.equal(puts.length, 1);
		assert.deepEqual(puts[0].body, { schedule: 'manual', previous_schedule: 'daily' });
	});
});

describe('AC-6: Listenseite /compare — Kebab „Pausieren" sendet nur den Status', () => {
	test('togglePause: PUT-Rumpf exakt { schedule, previous_schedule }; Name eines anderen Tabs bleibt', async () => {
		clearEtagRegistry();
		const server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
		server.install();
		try {
			const { u } = await umgebungFuer(LISTE, { data: { presets: [voll()] } });
			assert.equal(typeof u.togglePause, 'function', 'Messaufbau: togglePause nicht herleitbar');
			assert.equal(typeof u.buildFreshTogglePutPayload, 'function', 'Messaufbau: buildFreshTogglePutPayload fehlt in der Umgebung');
			server.fremdSchreiben(ID, { name: 'Fremd von A' });
			await (u.togglePause as (p: ComparePreset) => Promise<void>)(voll());
			assert.equal(u.error, null, `Messaufbau: togglePause meldet Fehler ${String(u.error)}`);
			const ruempfe = server.putRuempfe();
			assert.equal(ruempfe.length, 1);
			assert.deepEqual(ruempfe[0], { schedule: 'manual', previous_schedule: 'daily' });
			const stand = server.stand(ID);
			assert.equal(stand.name, 'Fremd von A');
			assert.equal(stand.schedule, 'manual');
		} finally {
			server.restore();
		}
	});
});
