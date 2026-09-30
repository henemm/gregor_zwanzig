// Fix-Loop #2375 (Adversary F001, AC-10): eine ERFOLGREICHE PUT-Antwort wird
// im Hub (CompareTabs.svelte) als neue Basis `currentPreset` uebernommen.
//
// Die Zusicherung wirkt dort, wo die Basis GELESEN wird: die naechste
// Hydration/Nutzlast eines ANDEREN Reiters rechnet mit dem Serverstand, nicht
// mit der veralteten Prop. Gemessen wird deshalb der Reiter-Aufbau danach
// (`hydrateWetterMetrikenTab` liest `official_alerts_enabled` aus
// `currentPreset`). Der Server liefert einen gemergten Stand mit einem
// Fremdfeld-Wert (`official_alerts_enabled: false`), der von der Basis (true)
// abweicht.
//
// Drei Wirkstellen: uebernehmeHubAntwort (Reiter-Rueckmeldung),
// persistPickedIds (Orte), handleToggleActive (Status).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_hub_uebernimmt_serverantwort_als_basis.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	umgebungFuer,
	findeKomponenten,
	attributAusdruck,
	werte,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HUB = join(dirname(fileURLToPath(import.meta.url)), '..', 'CompareTabs.svelte');

function basisPreset(): Record<string, unknown> {
	return {
		id: 'p1',
		name: 'Start',
		location_ids: ['a'],
		display_config: {},
		schedule: 'daily',
		previous_schedule: 'daily',
		official_alerts_enabled: true
	};
}

/** Serverstand nach dem PUT: gemergt, mit abweichendem Fremdfeld. */
function serverstand(extra: Record<string, unknown> = {}): Record<string, unknown> {
	return { ...basisPreset(), official_alerts_enabled: false, ...extra };
}

async function hub(putAntwort: Record<string, unknown>) {
	const api = { put: async () => ({ ...putAntwort }) };
	const saveController = { setSaving() {}, setSaved() {}, setError() {}, flush: async () => {} };
	const wizardState: Knoten = {};
	const { u, ast, quelle } = await umgebungFuer(HUB, {
		preset: basisPreset(),
		locations: [],
		saveController,
		wizardState,
		api,
		onScheduleChange: undefined
	});
	return { u, wizardState, ast, quelle };
}

/** Der NAECHSTE Reiter-Aufbau liest die Basis — hier: Wetter-Metriken. */
async function naechsterReiterLiest(u: Knoten, wizardState: Knoten): Promise<unknown> {
	assert.strictEqual(
		typeof u.hydrateWetterMetrikenTab,
		'function',
		'Messaufbau: hydrateWetterMetrikenTab fehlt.'
	);
	await (u.hydrateWetterMetrikenTab as () => Promise<void>)();
	return wizardState.officialAlertsEnabled;
}

describe('#2375 AC-10: erfolgreiche PUT-Antwort wird Basis fuer die naechste Nutzlast', () => {
	test('Vorbedingung: ohne PUT rechnet der naechste Reiter mit der Ausgangsbasis', async () => {
		const { u, wizardState } = await hub(serverstand());
		assert.strictEqual(await naechsterReiterLiest(u, wizardState), true);
	});

	test('uebernehmeHubAntwort: der naechste Reiter rechnet mit der Serverantwort', async () => {
		const { u, wizardState } = await hub(serverstand());
		(u.uebernehmeHubAntwort as (p: unknown) => void)(serverstand());
		assert.strictEqual(
			await naechsterReiterLiest(u, wizardState),
			false,
			'uebernehmeHubAntwort muss currentPreset auf die Serverantwort setzen.'
		);
	});

	test('persistPickedIds: der naechste Reiter rechnet mit der Serverantwort', async () => {
		const { u, wizardState } = await hub(serverstand({ location_ids: ['a', 'b'] }));
		await (u.persistPickedIds as (ids: string[]) => Promise<void>)(['a', 'b']);
		assert.strictEqual(
			await naechsterReiterLiest(u, wizardState),
			false,
			'persistPickedIds muss currentPreset auf die Serverantwort setzen.'
		);
	});

	test('handleToggleActive: der naechste Reiter rechnet mit der Serverantwort', async () => {
		const { u, wizardState } = await hub(serverstand({ schedule: 'manual' }));
		const ok = await (u.handleToggleActive as () => Promise<boolean>)();
		assert.strictEqual(ok, true);
		assert.strictEqual(
			await naechsterReiterLiest(u, wizardState),
			false,
			'handleToggleActive muss currentPreset auf die Serverantwort setzen.'
		);
	});

	// Die Inline-Handler im Markup (`onCompareUpdate={(updated) => { currentPreset = updated; }}`)
	// stehen nicht im Instanz-Skript. Erreichbar sind sie ueber den AST: der
	// Attribut-Ausdruck der ECHTEN Einbettung wird gegen dieselbe Umgebung `u`
	// ausgewertet (Zuweisung an `currentPreset` landet in `u`) und dann so
	// aufgerufen, wie es der Reiter nach seinem erfolgreichen PUT tut.
	for (const komponente of ['AlarmeTab', 'VersandTab']) {
		test(`${komponente}-Einbettung: onCompareUpdate uebernimmt die Serverantwort als Basis`, async () => {
			const { u, wizardState, ast, quelle } = await hub(serverstand());
			const einbettungen = findeKomponenten(ast, komponente);
			assert.strictEqual(einbettungen.length, 1, `Messaufbau: genau eine ${komponente}-Einbettung erwartet.`);
			const ausdruck = attributAusdruck(einbettungen[0], quelle, 'onCompareUpdate');
			assert.ok(ausdruck, `Messaufbau: ${komponente} hat kein onCompareUpdate.`);
			const handler = werte(ausdruck as string, u) as (p: unknown) => void;
			assert.strictEqual(typeof handler, 'function');
			handler(serverstand());
			assert.strictEqual(
				await naechsterReiterLiest(u, wizardState),
				false,
				`onCompareUpdate der ${komponente}-Einbettung muss currentPreset auf die Serverantwort setzen.`
			);
		});
	}
});
