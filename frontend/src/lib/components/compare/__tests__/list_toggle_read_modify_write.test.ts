// TDD RED — Issue #1259.
//
// Spec: docs/specs/modules/issue_1259_compare_list_toggle_rmw.md
//
// Der Kebab-Toggle "Pausieren/Aktivieren" in der Vergleichs-LISTEN-Ansicht
// (`/compare`, seit Issue #1277 die geteilte ListTable/ListActionsMenu in
// `routes/compare/+page.svelte`) baut seinen PUT-Body heute aus dem beim
// Seitenaufruf geladenen, potenziell veralteten Listen-Snapshot per
// Voll-Spread (`{ ...preset, ...next }`). Sind Liste und Detail-Hub
// desselben Vergleichs gleichzeitig in zwei Browser-Tabs offen und aendert
// der Hub den Vergleich zwischenzeitlich, ueberschreibt der Listen-Toggle
// diese Aenderung mit dem veralteten Listen-Snapshot — stiller
// Server-Datenverlust ohne Fehlermeldung.
//
// Dieser Test ist ROT, weil `buildFreshTogglePutPayload` noch nicht in
// `compareHubWizardBridge.ts` existiert (Phase 6 fuehrt ihn ein: GET-vor-PUT
// Read-Modify-Write, analog `buildToggleActivePutPayload`/`computePauseToggle`,
// aber mit injizierbarem `getPreset` statt stale Prop). Einziger erwarteter
// Fehlgrund: der Import scheitert / der Named Export ist `undefined`.
//
// `simulatedPut` modelliert das reale Backend-Merge-Verhalten fuer einen
// Voll-Spread-Body (analog `kebab_toggle_delegation.test.ts`): vorhandene
// Felder im Body ueberschreiben den Server-Stand vollstaendig.

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import { buildFreshTogglePutPayload } from '../compareHubWizardBridge.ts'; // NEU — existiert noch nicht → RED

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1',
		name: 'Test',
		location_ids: ['a', 'b'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['x@y.de'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		previous_schedule: 'daily',
		corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
		display_config: {},
		...overrides
	};
}

describe('Issue #1259: Listen-Kebab-Toggle liest frischen Server-Stand vor dem PUT (Read-Modify-Write)', () => {
	test('AC-1: Multi-Tab-Datenverlust verhindert — Hub-Edit ueberlebt den Listen-Toggle', async () => {
		// Given: der Server haelt bereits eine FRISCHE Hub-Aenderung (Korridor +
		// Rhythmus), die veraltete Listen-Prop (`stalePreset`) kennt diese noch
		// nicht.
		let serverPreset: ComparePreset = makePreset({
			corridors: [{ metric: 'snow_depth_cm', range: [50, null], notify: true, mark: true, prio: 'hoch' }],
			schedule: 'daily',
			previous_schedule: 'daily'
		});
		const stalePreset: ComparePreset = makePreset({
			id: serverPreset.id,
			corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
			schedule: 'daily',
			previous_schedule: 'daily'
		});

		function simulatedPut(body: ComparePreset): void {
			serverPreset = { ...serverPreset, ...body };
		}

		const getPreset = async (_id: string): Promise<ComparePreset> => structuredClone(serverPreset);

		// When: der Listen-Kebab "Pausieren" wird fuer die veraltete Zeile
		// ausgeloest.
		const { url, body } = await buildFreshTogglePutPayload(stalePreset.id, getPreset);
		simulatedPut(body);

		// Then: der frische Hub-Korridor bleibt erhalten (NICHT der veraltete
		// Listen-Wert 20) und der Toggle hat pausiert.
		assert.strictEqual(
			serverPreset.corridors![0].range[0],
			50,
			'Regression #1259: Listen-Toggle darf den frischen Hub-Korridor NICHT mit dem veralteten Listen-Snapshot ueberschreiben'
		);
		assert.strictEqual(serverPreset.schedule, 'manual', 'Toggle muss pausiert haben');
		assert.strictEqual(url, `/api/compare/presets/${serverPreset.id}`);
	});

	test('AC-2: Ein-Tab-Rhythmus unveraendert (#631) — zweimal togglen kehrt zum Ausgangszustand zurueck', async () => {
		// Given: nur die Liste ist offen, kein zweiter Tab mit Aenderungen
		// dazwischen.
		let serverPreset: ComparePreset = makePreset({ schedule: 'daily', previous_schedule: 'daily' });

		function simulatedPut(body: ComparePreset): void {
			serverPreset = { ...serverPreset, ...body };
		}
		const getPreset = async (_id: string): Promise<ComparePreset> => structuredClone(serverPreset);

		// When: 1. Klick pausiert.
		const first = await buildFreshTogglePutPayload(serverPreset.id, getPreset);
		simulatedPut(first.body);
		assert.strictEqual(serverPreset.schedule, 'manual');

		// When: 2. Klick aktiviert wieder.
		const second = await buildFreshTogglePutPayload(serverPreset.id, getPreset);
		simulatedPut(second.body);

		// Then: schedule UND previous_schedule entsprechen wieder dem
		// Ausgangszustand.
		assert.strictEqual(serverPreset.schedule, 'daily');
		assert.strictEqual(serverPreset.previous_schedule, 'daily');
	});

	test('AC-3: Fehlerpfad propagiert — GET-Fehler liefert keinen Payload, sondern eine geworfene Exception', async () => {
		// Given: der GET-Aufruf des Toggle-Flows schlaegt fehl (z.B.
		// Netzwerkfehler).
		const getPreset = async (_id: string): Promise<ComparePreset> => {
			throw new Error('network');
		};

		// When/Then: der Helper propagiert den Fehler, statt einen (teilweisen)
		// Payload zurueckzugeben.
		await assert.rejects(() => buildFreshTogglePutPayload('cmp-1', getPreset));
	});

	test('F001: Reaktivieren eines manual-Presets ohne previous_schedule schreibt keinen "manual"-Rhythmus', async () => {
		// Given: der Server-Stand ist bereits pausiert (schedule='manual') UND
		// kennt keinen previous_schedule (z.B. seit Erstellung nie aktiv
		// gewesen). Adversary-Befund F001: der alte Fallback
		// `next.previous_schedule ?? fresh.schedule` haette hier `fresh.schedule`
		// ('manual') als previous_schedule in den PUT-Body geschrieben — ein
		// semantisch ungueltiger "Rhythmus-zum-Wiederherstellen".
		let serverPreset: ComparePreset = makePreset({
			schedule: 'manual',
			previous_schedule: undefined
		});

		function simulatedPut(body: ComparePreset): void {
			serverPreset = { ...serverPreset, ...body };
		}
		const getPreset = async (_id: string): Promise<ComparePreset> => structuredClone(serverPreset);

		// When: der Listen-Kebab "Aktivieren" wird ausgeloest.
		const { body } = await buildFreshTogglePutPayload(serverPreset.id, getPreset);
		simulatedPut(body);

		// Then: die Reaktivierung stellt einen sinnvollen Rhythmus her, und
		// previous_schedule ist NIE 'manual'.
		assert.strictEqual(
			body.schedule,
			'daily',
			'Reaktivierung ohne previous_schedule muss einen gueltigen Rhythmus herstellen'
		);
		assert.notStrictEqual(body.previous_schedule, 'manual', 'Regression F001: previous_schedule darf niemals "manual" sein');
		assert.strictEqual(serverPreset.previous_schedule, 'daily');
		assert.notStrictEqual(serverPreset.previous_schedule, 'manual');
	});
});
