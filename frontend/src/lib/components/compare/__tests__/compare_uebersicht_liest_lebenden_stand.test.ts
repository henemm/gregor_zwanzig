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
	effekteVon,
	ohneTypen,
	werte,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';

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
	}, { jsAlsTs: true });
	const einbettungen = findeKomponenten(ast, 'HubUebersicht');
	assert.strictEqual(einbettungen.length, 1, 'Messaufbau: genau eine HubUebersicht-Einbettung erwartet.');
	const lies = (name: string): unknown => {
		const ausdruck = attributAusdruck(einbettungen[0], quelle, name);
		assert.ok(ausdruck, `Messaufbau: HubUebersicht hat kein Attribut ${name}.`);
		return werte(ausdruck as string, u);
	};
	// `$derived` ist im Pruefstand die Identitaet: `status` wird beim Aufbau EINMAL
	// berechnet. Damit die Status-Kennzahl nach einer Aktion messbar ist, wird die
	// ECHTE `status`-Deklaration des Instanz-Skripts erneut gegen die Umgebung
	// ausgewertet (wie Svelte sie bei Aenderung von currentPreset/localSchedule neu
	// berechnet) und dann das `status`-Attribut der HubUebersicht-Einbettung gelesen.
	const statusDecl = ((ast.instance?.content?.body as Knoten[]) ?? [])
		.filter((s) => s.type === 'VariableDeclaration')
		.flatMap((s) => s.declarations as Knoten[])
		.find((d) => d.id?.type === 'Identifier' && d.id.name === 'status');
	assert.ok(statusDecl?.init, 'Messaufbau: CompareTabs hat keine `status`-Deklaration.');
	const statusDerUebersicht = (): unknown => {
		u.status = werte(ohneTypen(quelle, statusDecl.init), u);
		return lies('status');
	};
	return { u: u as Knoten, lies, statusDerUebersicht, ast, quelle };
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

// Adversary F001/F002/F003 (fix-2828): die Status-Kennzahl der Uebersicht wird am
// ECHTEN `status`-Attribut der HubUebersicht-Einbettung gemessen, nach echter Aktion.
describe('#2828 AC-5/AC-6: Status-Kennzahl der Uebersicht folgt dem lebenden Stand', () => {
	test('Vorbedingung: ein aktiver Vergleich zeigt in der Uebersicht den Status active', async () => {
		const { statusDerUebersicht } = await hub();
		assert.strictEqual(statusDerUebersicht(), 'active');
	});

	test('AC-5: nach Pausieren zeigt die Status-Kennzahl der Uebersicht sofort paused', async () => {
		const { u, statusDerUebersicht } = await hub({ ...basisPreset(), schedule: 'manual' });
		assert.strictEqual(statusDerUebersicht(), 'active', 'Vorbedingung: vor dem Pausieren aktiv.');
		const ok = await (u.handleToggleActive as () => Promise<boolean>)();
		assert.strictEqual(ok, true);
		assert.strictEqual(
			u.localSchedule,
			'manual',
			'AC-5: handleToggleActive muss den lokalen Pausier-Override aus der Serverantwort setzen.'
		);
		assert.strictEqual(
			statusDerUebersicht(),
			'paused',
			'AC-5: HubUebersicht.status muss nach dem Pausieren paused zeigen (lebender Stand).'
		);
	});

	test('AC-5: Aktivieren eines pausierten Vergleichs zeigt in der Uebersicht wieder active', async () => {
		const { u, statusDerUebersicht } = await hub({ ...basisPreset(), schedule: 'manual' });
		const toggle = u.handleToggleActive as () => Promise<boolean>;
		await toggle();
		assert.strictEqual(statusDerUebersicht(), 'paused', 'Vorbedingung: pausiert.');
		// Zweiter Klick: der Server antwortet mit dem wiederhergestellten Rhythmus.
		u.api = { put: async () => ({ ...basisPreset(), schedule: 'daily', previous_schedule: 'daily' }) };
		assert.strictEqual(await toggle(), true);
		assert.strictEqual(statusDerUebersicht(), 'active', 'AC-5: nach Aktivieren muss die Uebersicht active zeigen.');
	});

	test('AC-5: die Status-Basis ist der lebende Stand (currentPreset), nicht die eingefrorene Prop', async () => {
		const { u, statusDerUebersicht } = await hub();
		// gespeicherter Stand ohne Orte ⇒ Entwurf; die Prop `preset` traegt weiter einen Ort.
		(u.uebernehmeHubAntwort as (p: unknown) => void)({ ...basisPreset(), location_ids: [] });
		assert.strictEqual(
			statusDerUebersicht(),
			'draft',
			'AC-5: status muss aus currentPreset abgeleitet werden (Prop `preset` ist eingefroren).'
		);
	});

	test('AC-5: der lokale Pausier-Override gewinnt vor dem gespeicherten Preset-Stand', async () => {
		const { u, statusDerUebersicht } = await hub();
		// gespeicherter Stand aktiv, lokaler Override pausiert
		u.localSchedule = 'manual';
		assert.strictEqual(statusDerUebersicht(), 'paused');
	});

	test('AC-6: der Prop-Wechsel-Effekt synchronisiert currentPreset, laesst localSchedule aber unberuehrt', async () => {
		const { u, ast, quelle, lies, statusDerUebersicht } = await hub();
		const effekte = effekteVon(ast, quelle, u, 'snapshotForRollback');
		assert.strictEqual(effekte.length, 1, 'Messaufbau: genau ein Prop-Wechsel-Effekt (snapshotForRollback) erwartet.');
		assert.strictEqual(u.localSchedule, 'daily', 'Vorbedingung: lokaler Rhythmus daily.');
		u.preset = { ...basisPreset(), name: 'Prop-Neu' };
		effekte[0]();
		assert.strictEqual((lies('preset') as Record<string, unknown>).name, 'Prop-Neu', 'Effekt muss currentPreset aus der Prop setzen.');
		assert.strictEqual(u.localSchedule, 'daily', 'AC-6: der Prop-Wechsel-Effekt darf localSchedule nicht schreiben.');
		assert.strictEqual(statusDerUebersicht(), 'active', 'AC-6: der Effekt darf den Status der Uebersicht nicht verfaelschen.');
	});
});

// Adversary F001 (fix-2828, AC-7): nach einem 412 schreibt der Hub sein currentPreset um
// die abgelehnte Nutzlast fort (registriereAbgelehnt). Gemessen am ECHTEN Controller
// (SaveStatus) und der ECHTEN Registrierung im CompareTabs-Skript: die Uebersicht zeigt
// danach den Eingabestand, nicht den Ladestand.
describe('#2828 AC-7: nach einem abgelehnten Speichern zeigt die Uebersicht den Eingabestand', () => {
	test('AC-7: abgelehnte Nutzlast (412) wird in das preset der Uebersicht fortgeschrieben', async () => {
		const { u, ast, quelle, lies } = await hub();
		const ctl = createController('p1');
		u.saveController = ctl;
		const effekte = effekteVon(ast, quelle, u, 'registriereAbgelehnt');
		assert.strictEqual(effekte.length, 1, 'Messaufbau: genau ein registriereAbgelehnt-Effekt erwartet.');
		effekte[0]();
		assert.strictEqual(typeof ctl.onAbgelehnt, 'function', 'Messaufbau: der Hub muss sich am Controller registrieren.');
		assert.strictEqual((lies('preset') as Record<string, unknown>).name, 'Start', 'Vorbedingung: Ladestand.');
		// So meldet der Controller bei einem 412 die abgelehnte Eigenfeld-Nutzlast.
		ctl.onAbgelehnt!({ name: 'Eingabe', display_config: { x: 1 } });
		const p = lies('preset') as Record<string, unknown>;
		assert.strictEqual(p.name, 'Eingabe', 'AC-7: HubUebersicht.preset muss die abgelehnte Eingabe zeigen, nicht den Ladestand.');
		assert.deepStrictEqual(p.display_config, { x: 1 });
		assert.deepStrictEqual(p.location_ids, ['a'], 'nicht gemeldete Felder bleiben erhalten.');
	});
});
