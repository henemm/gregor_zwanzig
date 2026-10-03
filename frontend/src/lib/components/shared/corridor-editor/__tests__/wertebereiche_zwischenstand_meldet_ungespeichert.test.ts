// TDD RED — Issue #2215 (AC-9, Familie Wertebereiche): ein ungültiger Zwischenstand
// (Min UND Max leer) nach einem gültigen Schritt muss über den Weg „offener
// Zwischenstand" gemeldet werden (`saveController.setUnsavedInput()`), NICHT über
// `setDirty()` — sonst überschreibt der vorgemerkte Save die Anzeige mit „Gespeichert".
//
// Spec: docs/specs/modules/fix_2215_unsaved_input_marker.md
// Wirkort-Prüfstand `svelteInstanzPruefstand.ts`: die ECHTEN Editor-Funktionen
// `add`/`patch` laufen, der Controller zeichnet auf, welcher Meldeweg gerufen wird.
// Nur `context="route"` erreicht diese Zeilen; der Vergleich-Zweig speichert über
// `vergleichSpeicherung` und kennt keinen `setDirty`-Pfad.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/corridor-editor/__tests__/wertebereiche_zwischenstand_meldet_ungespeichert.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { addRow, buildRoutePool, patchRow, ROUTE_CTX_DEFAULTS } from '../corridorEditorState.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const METRIKEN = [{ metric_id: 'gust', enabled: true }];

interface Aufrufe {
	schedule: number;
	setDirty: number;
	setUnsavedInput: number;
}

function baueSaat(aufrufe: Aufrufe, mitCreateMode: boolean, kontext: 'route' | 'vergleich' = 'route'): Knoten {
	const saat: Knoten = {
		context: kontext,
		trip: { id: 'gr20', display_config: { metrics: METRIKEN } },
		onTripUpdate: undefined,
		saveController: {
			schedule: () => aufrufe.schedule++,
			setDirty: () => aufrufe.setDirty++,
			setUnsavedInput: () => aufrufe.setUnsavedInput++
		},
		preset: undefined,
		enqueueHubWrite: undefined,
		onCompareUpdate: undefined,
		corridors: undefined,
		idealRanges: undefined,
		activeMetricKeys: undefined,
		metricAlertLevels: undefined,
		isEditMode: undefined,
		activityProfile: undefined,
		onCorridorsChange: undefined,
		onIdealRangesChange: undefined,
		onActiveMetricKeysChange: undefined,
		onMetricAlertLevelsChange: undefined,
		untrack: (fn: () => unknown) => fn(),
		api: {},
		baueTripSpeicherung: () => async () => {}
	};
	if (mitCreateMode) saat.createMode = false;
	return saat;
}

async function pruefe(datei: string, mitCreateMode: boolean) {
	const aufrufe: Aufrufe = { schedule: 0, setDirty: 0, setUnsavedInput: 0 };
	const { u } = await umgebungFuer(join(HIER, '..', datei), baueSaat(aufrufe, mitCreateMode));
	assert.equal(typeof u.add, 'function', 'Messaufbau kaputt: `add` nicht gebunden.');
	assert.equal(typeof u.patch, 'function', 'Messaufbau kaputt: `patch` nicht gebunden.');
	const pool = buildRoutePool([], METRIKEN as never, []);
	u.routeExtraDefs = [];
	u.rows = pool.rows;
	u.poolLeft = pool.poolLeft;
	u.routeUnknownCorridors = pool.unknownCorridors;
	u.add('wind_gust');
	u.patch('wind_gust', { max: 80 }); // gültiger Schritt → schedule
	assert.equal(aufrufe.schedule >= 1, true, 'Messaufbau kaputt: der gültige Schritt hat keinen Save vorgemerkt.');
	u.patch('wind_gust', { max: null }); // Min UND Max leer → ungültiger Zwischenstand
	return aufrufe;
}

describe('#2215 AC-9: Wertebereiche meldet den ungültigen Zwischenstand als „offener Zwischenstand"', () => {
	test('CorridorEditor (Desktop, route)', async () => {
		const a = await pruefe('CorridorEditor.svelte', true);
		assert.equal(a.setUnsavedInput, 1, 'der ungültige Zwischenstand muss setUnsavedInput() melden');
		assert.equal(a.setDirty, 0, 'setDirty() lässt den vorgemerkten Save „Gespeichert" melden (#2215)');
	});

	test('CorridorEditorMobile (route)', async () => {
		const a = await pruefe('CorridorEditorMobile.svelte', false);
		assert.equal(a.setUnsavedInput, 1, 'der ungültige Zwischenstand muss setUnsavedInput() melden');
		assert.equal(a.setDirty, 0, 'setDirty() lässt den vorgemerkten Save „Gespeichert" melden (#2215)');
	});
});

// F001 (Adversary, Fix-Loop 1): im Ortsvergleich meldete der vergleich-Zweig den ungültigen
// Zwischenstand gar nicht; der vorgemerkte Save der Orchestrierung (derselbe saveController)
// meldete danach „Gespeichert". Der Hub reicht denselben Controller an die Orchestrierung durch.
async function pruefeVergleich(datei: string, mitCreateMode: boolean) {
	const aufrufe: Aufrufe = { schedule: 0, setDirty: 0, setUnsavedInput: 0 };
	const { u } = await umgebungFuer(join(HIER, '..', datei), baueSaat(aufrufe, mitCreateMode, 'vergleich'));
	assert.equal(typeof u.add, 'function', 'Messaufbau kaputt: `add` nicht gebunden.');
	const pool = buildRoutePool([], METRIKEN as never, []);
	u.routeExtraDefs = [];
	u.rows = pool.rows;
	u.poolLeft = pool.poolLeft;
	u.routeUnknownCorridors = pool.unknownCorridors;
	// Der Vergleich-`add` braucht den geladenen Vergleichs-Katalog; der Zeilenstand wird daher
	// mit den Zustandsfunktionen vorbereitet (gültiger Stand), erst `patch` läuft im Editor.
	const gueltig = addRow(pool.rows, pool.poolLeft as never, 'wind_gust', ROUTE_CTX_DEFAULTS);
	u.rows = patchRow(gueltig.rows, 'wind_gust', { max: 80 });
	u.patch('wind_gust', { max: null }); // Min UND Max leer → ungültiger Zwischenstand
	return aufrufe;
}

describe('#2215 AC-9: Wertebereiche im Ortsvergleich (context="vergleich") meldet den Zwischenstand', () => {
	test('CorridorEditor (Desktop, vergleich)', async () => {
		const a = await pruefeVergleich('CorridorEditor.svelte', true);
		assert.equal(a.setUnsavedInput, 1, 'vergleich-Zweig muss den ungültigen Zwischenstand melden');
		assert.equal(a.setDirty, 0);
	});

	test('CorridorEditorMobile (vergleich)', async () => {
		const a = await pruefeVergleich('CorridorEditorMobile.svelte', false);
		assert.equal(a.setUnsavedInput, 1, 'vergleich-Zweig muss den ungültigen Zwischenstand melden');
		assert.equal(a.setDirty, 0);
	});
});
