// Issue #2828 (B1-46, Epic #2345): Die Uebersicht im Compare-Hub zeigt den LEBENDEN Stand.
//
// Wirkstelle: die ECHTE HubUebersicht-Einbettung in CompareTabs.svelte. Ihr `preset`-
// und `status`-Attribut werden gegen die Instanz-Umgebung ausgewertet, nachdem ein
// Reiter erfolgreich gespeichert hat (uebernehmeHubAntwort / persistPickedIds /
// handleToggleActive). Auf dem alten Code bleiben beide auf der Seiten-Prop `preset`
// (Ladezeitpunkt) stehen.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_uebersicht_liest_lebenden_stand.test.ts

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

async function hub(putAntwort: Record<string, unknown> = basisPreset()) {
	const api = { put: async () => ({ ...putAntwort }) };
	const saveController = { setSaving() {}, setSaved() {}, setError() {}, flush: async () => {} };
	const { u, ast, quelle } = await umgebungFuer(HUB, {
		preset: basisPreset(),
		locations: [],
		saveController,
		wizardState: {},
		api,
		onScheduleChange: undefined
	});
	const einbettungen = findeKomponenten(ast, 'HubUebersicht');
	assert.strictEqual(einbettungen.length, 1, 'Messaufbau: genau eine HubUebersicht-Einbettung erwartet.');
	const lies = (name: string): unknown => {
		const ausdruck = attributAusdruck(einbettungen[0], quelle, name);
		assert.ok(ausdruck, `Messaufbau: HubUebersicht hat kein Attribut ${name}.`);
		return werte(ausdruck as string, u);
	};
	return { u: u as Knoten, lies };
}

describe('#2828: Uebersicht liest currentPreset statt der eingefrorenen Prop', () => {
	test('Vorbedingung: ohne Speichern zeigt die Uebersicht den Ausgangsstand', async () => {
		const { lies } = await hub();
		assert.strictEqual((lies('preset') as Record<string, unknown>).name, 'Start');
	});

	test('AC-1/AC-3: nach erfolgreichem Speichern zeigt die Uebersicht die Serverantwort', async () => {
		const { u, lies } = await hub();
		(u.uebernehmeHubAntwort as (p: unknown) => void)({
			...basisPreset(),
			name: 'Neu',
			schedule: 'weekly'
		});
		const p = lies('preset') as Record<string, unknown>;
		assert.strictEqual(p.name, 'Neu', 'HubUebersicht.preset muss currentPreset sein.');
		assert.strictEqual(p.schedule, 'weekly');
	});

	test('AC-2: nach Orte-Speichern zeigt die Uebersicht die neuen Orte-IDs', async () => {
		const { u, lies } = await hub({ ...basisPreset(), location_ids: ['a', 'b'] });
		await (u.persistPickedIds as (ids: string[]) => Promise<void>)(['a', 'b']);
		assert.deepStrictEqual((lies('preset') as Record<string, unknown>).location_ids, ['a', 'b']);
	});

	// Hinweis: `status` ist ein $derived-Wert und im Instanz-Pruefstand nicht auswertbar;
	// seine Ableitung aus currentPreset (AC-5) deckt die E2E-Verifikation auf Staging ab.
	test('AC-5: Pausieren zeigt sofort den neuen Stand im preset der Uebersicht', async () => {
		const { u, lies } = await hub({ ...basisPreset(), schedule: 'manual' });
		const ok = await (u.handleToggleActive as () => Promise<boolean>)();
		assert.strictEqual(ok, true);
		assert.strictEqual((lies('preset') as Record<string, unknown>).schedule, 'manual');
	});

	test('AC-6: eine spaetere Alarm-Aenderung setzt fruehere Uebersichts-Werte nicht zurueck', async () => {
		const { u, lies } = await hub();
		const uebernehme = u.uebernehmeHubAntwort as (p: unknown) => void;
		uebernehme({ ...basisPreset(), name: 'Neu' });
		uebernehme({ ...basisPreset(), name: 'Neu', official_alerts_enabled: false });
		const p = lies('preset') as Record<string, unknown>;
		assert.strictEqual(p.name, 'Neu');
		assert.strictEqual(p.official_alerts_enabled, false);
	});
});
