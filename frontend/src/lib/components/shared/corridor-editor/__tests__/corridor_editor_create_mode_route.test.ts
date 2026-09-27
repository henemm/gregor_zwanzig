// TDD RED — Issue #2277 Scheibe S2a: CorridorEditor.svelte bekommt den Prop
// `createMode` (Muster AlarmeTab/WeatherMetricsTab, S1 #2426). Im Anlege-Modus
// (/trips/new, stubTrip mit Id "__new__") darf der Selbst-Speicher-Pfad
// (`saveController.schedule(buildSaveFn())` → PUT /api/trips/__new__) NIE
// feuern; stattdessen meldet der Editor jede gueltige Aenderung ueber
// `onCorridorsChange` nach oben. Zusaetzlich folgt das "+ Metrik"-Angebot
// (`poolLeft`) im Anlege-Modus der laufenden Wetter-Metriken-Auswahl, ohne
// bereits eingestellte Zeilen zu verlieren (AC-7).
//
// Spec: docs/specs/modules/fix_2277_s2a_wertebereiche_trip_anlegen.md
//       (AC-2, AC-3, AC-4-Positiv-Gegenprobe, AC-7)
//
// Wirkort-Pruefstand `svelteInstanzPruefstand.ts`: `add`/`patch`/`maybeSchedule`
// sind FunctionDeclarations des Instanz-Skripts und werden von `umgebungFuer()`
// direkt auf `u` gebunden — die Tests rufen die ECHTEN Editor-Funktionen auf,
// keine Nachbildung. Der Pool-Refresh liegt in einem `$effect` und wird ueber
// `effekteVon(…, 'createMode')` eingesammelt (einziger Effekt, der den Prop
// nennt — `'poolLeft'` wuerde auch die beiden Katalog-Lade-Effekte treffen).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/corridor-editor/__tests__/corridor_editor_create_mode_route.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, effekteVon, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { buildRoutePool, type CorridorRowState } from '../corridorEditorState.ts';
import { buildCreateTripPayload, type CreateTripState } from '../../../trip-new/tripNewLogic.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const EDITOR = join(HIER, '..', 'CorridorEditor.svelte');

/** Wetter-Metriken-Auswahl im Format von `trip.display_config.metrics`
 *  (`buildRoutePool` filtert auf `metric_id` + `enabled`). */
const NUR_BOEEN = [{ metric_id: 'gust', enabled: true }];
const BOEEN_UND_REGEN = [
	{ metric_id: 'gust', enabled: true },
	{ metric_id: 'precipitation', enabled: true }
];

interface Spione {
	schedule: unknown[][];
	setDirty: unknown[][];
	corridors: unknown[][];
	gebaut: unknown[][];
}

/** Saat des route-Zweigs, wie TripNewEditor ihn mountet. JEDE Prop steht
 *  explizit in der Saat (auch als `undefined`): eine fehlende Bindung laesst
 *  `with(u)` mit ReferenceError scheitern, und `umgebungFuer()` schluckt
 *  Deklarationsfehler still — `originalLevels` fehlte dann unbemerkt. */
function baueSaat(createMode: unknown, spione: Spione, metrics: unknown[] = NUR_BOEEN): Knoten {
	return {
		context: 'route',
		trip: { id: '__new__', display_config: { metrics } },
		createMode,
		onTripUpdate: undefined,
		saveController: {
			schedule: (...a: unknown[]) => spione.schedule.push(a),
			setDirty: (...a: unknown[]) => spione.setDirty.push(a)
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
		onCorridorsChange: (...a: unknown[]) => spione.corridors.push(a),
		onIdealRangesChange: undefined,
		onActiveMetricKeysChange: undefined,
		onMetricAlertLevelsChange: undefined,
		untrack: (fn: () => unknown) => fn(),
		// Transport neutralisiert: der route-PUT wird nur VORBEREITET (Spion),
		// nie abgeschickt.
		api: {},
		baueTripSpeicherung: (...a: unknown[]) => {
			spione.gebaut.push(a);
			return async () => {};
		}
	};
}

function neueSpione(): Spione {
	return { schedule: [], setDirty: [], corridors: [], gebaut: [] };
}

/** Baut die Umgebung, prueft den Messaufbau und legt den Pool so an, wie ihn
 *  der Lade-Effekt nach erfolgreichem Katalog-Laden setzt (ohne Netz). */
async function baueEditor(createMode: unknown, metrics: unknown[] = NUR_BOEEN) {
	const spione = neueSpione();
	const umgebung = await umgebungFuer(EDITOR, baueSaat(createMode, spione, metrics));
	const { u } = umgebung;
	assert.equal(typeof u.add, 'function', 'Messaufbau kaputt: `add` ist nicht auf u gebunden.');
	assert.equal(typeof u.patch, 'function', 'Messaufbau kaputt: `patch` ist nicht auf u gebunden.');
	assert.equal(typeof u.maybeSchedule, 'function', 'Messaufbau kaputt: `maybeSchedule` fehlt.');
	assert.ok(
		u.originalLevels !== undefined,
		'Messaufbau kaputt: `originalLevels` liess sich nicht herleiten (fehlende Saat-Bindung) — ' +
			'`buildSaveFn()` wuerde in der Positiv-Gegenprobe werfen statt zu zaehlen.'
	);
	const initial = buildRoutePool([], metrics as never, []);
	u.routeExtraDefs = [];
	u.rows = initial.rows;
	u.poolLeft = initial.poolLeft;
	u.routeUnknownCorridors = initial.unknownCorridors;
	assert.ok(
		(u.poolLeft as { metric: string }[]).some((d) => d.metric === 'wind_gust'),
		'Messaufbau kaputt: `wind_gust` steht nicht im Pool — `add("wind_gust")` waere ein Nulleffekt.'
	);
	return { ...umgebung, spione };
}

describe('AC-3: im Anlege-Modus bereitet der Editor NIE einen PUT vor', () => {
	test('createMode=true: add + patch → saveController.schedule 0×, setDirty 0×, kein PUT gebaut', async () => {
		const { u, spione } = await baueEditor(true);
		u.add('wind_gust');
		u.patch('wind_gust', { max: 80 });
		assert.equal(
			spione.schedule.length,
			0,
			'AC-3 FAIL: trotz createMode=true wurde saveController.schedule aufgerufen — ' +
				'/trips/new wuerde einen PUT auf /api/trips/__new__ einplanen.'
		);
		assert.equal(spione.gebaut.length, 0, 'AC-3 FAIL: trotz createMode=true wurde ein Trip-PUT gebaut.');
		assert.equal(spione.setDirty.length, 0, 'AC-3 FAIL: trotz createMode=true wurde setDirty aufgerufen.');
	});

	test('createMode=true: ungueltiger Zwischenstand (Min UND Max leer) → auch setDirty 0×', async () => {
		const { u, spione } = await baueEditor(true);
		u.add('wind_gust');
		u.patch('wind_gust', { max: 80 });
		u.patch('wind_gust', { max: null });
		assert.equal(
			spione.setDirty.length,
			0,
			'AC-3 FAIL: der createMode-Zweig schuetzt nur den schedule-Zweig — der dirty-Zweig ' +
				'ruft weiter saveController.setDirty auf.'
		);
		assert.equal(spione.schedule.length, 0, 'AC-3 FAIL: saveController.schedule wurde aufgerufen.');
		const letzter = spione.corridors.at(-1)?.[0];
		assert.deepEqual(
			letzter,
			[{ metric: 'wind_gust', range: [null, 80], notify: true, mark: false }],
			'AC-3 FAIL: nach einem ungueltigen Zwischenstand muss der zuletzt GUELTIGE Stand ' +
				'gemeldet bleiben (ungueltige Zwischenstaende werden nie nach oben gemeldet).'
		);
	});

	test('Positiv-Gegenprobe (AC-4): OHNE createMode bleibt der Hub-Speicherweg — schedule 1× je Aenderung, setDirty 1× bei ungueltig', async () => {
		const { u, spione } = await baueEditor(undefined);
		u.add('wind_gust');
		assert.equal(
			spione.schedule.length,
			1,
			'AC-4 FAIL: ohne createMode plant der route-Zweig keinen PUT mehr ein — der Trip-Hub ' +
				'(TripTabs.svelte) verliert seinen Speicherweg (Default von createMode falsch?).'
		);
		assert.equal(spione.gebaut.length, 1, 'AC-4 FAIL: ohne createMode wurde kein Trip-PUT gebaut.');
		u.patch('wind_gust', { max: null });
		assert.equal(spione.setDirty.length, 1, 'AC-4 FAIL: ohne createMode fehlt setDirty bei ungueltiger Zeile.');
		assert.equal(
			spione.corridors.length,
			0,
			'AC-4 FAIL: der Hub-Pfad (route, ohne createMode) meldet ploetzlich onCorridorsChange.'
		);
	});
});

describe('AC-2: echte Bedienung → onCorridorsChange → POST-Nutzlast', () => {
	test('add("wind_gust") + patch({max: 80}) → payload.corridors enthaelt exakt diesen Wertebereich', async () => {
		const { u, spione } = await baueEditor(true);
		u.add('wind_gust');
		u.patch('wind_gust', { max: 80 });
		assert.ok(
			spione.corridors.length >= 1,
			'AC-2 FAIL: im Anlege-Modus meldet der Editor keine Aenderung ueber onCorridorsChange — ' +
				'der eingestellte Wertebereich kaeme nie im POST an.'
		);
		const gemeldet = spione.corridors.at(-1)![0];
		const state: CreateTripState = {
			name: 'Karnischer Höhenweg',
			startDate: '2026-06-15',
			stages: [{ id: 1, name: 'Toblach → Helmhotel' }],
			channels: { email: true, telegram: false, sms: false },
			corridors: gemeldet
		} as CreateTripState;
		const payload = buildCreateTripPayload(state);
		assert.deepEqual(
			(payload as { corridors?: unknown }).corridors,
			[{ metric: 'wind_gust', range: [null, 80], notify: true, mark: false }],
			'AC-2 FAIL: der im Wertebereiche-Reiter eingestellte Wert steht nicht (exakt) im ' +
				'POST-Payload von /trips/new.'
		);
	});
});

describe('AC-7: Pool folgt der Wetter-Metriken-Auswahl, ohne eingestellte Zeilen zu verlieren', () => {
	async function poolRefresh(createMode: unknown) {
		const { ast, quelle, u } = await baueEditor(createMode, NUR_BOEEN);
		// bereits eingestellte Zeile — ueber die echte Pool-Logik gebaut, nicht von Hand
		const gesaet = buildRoutePool(
			[{ metric: 'wind_gust', range: [null, 80], notify: true, mark: false }],
			NUR_BOEEN as never,
			[]
		);
		u.rows = gesaet.rows;
		u.poolLeft = gesaet.poolLeft;
		const rowsVorher: CorridorRowState[] = structuredClone(gesaet.rows);
		const poolVorher = (u.poolLeft as { metric: string }[]).map((d) => d.metric);
		const effekte = effekteVon(ast, quelle, u, 'createMode');
		return { u, effekte, rowsVorher, poolVorher };
	}

	test('createMode=true: Regen neu aktiviert → poolLeft bietet precipitation_sum an, rows unveraendert', async () => {
		const { u, effekte, rowsVorher, poolVorher } = await poolRefresh(true);
		assert.ok(
			!poolVorher.includes('precipitation_sum'),
			'Messaufbau kaputt: precipitation_sum steht schon VOR der Aenderung im Pool.'
		);
		assert.equal(
			effekte.length,
			1,
			`AC-7 FAIL: ${effekte.length} $effect-Ruempfe nennen \`createMode\` (erwartet: genau einer — ` +
				'der Pool-Refresh im Anlege-Modus). Ohne ihn friert das "+ Metrik"-Angebot ein.'
		);
		(u.trip as Knoten).display_config = { metrics: BOEEN_UND_REGEN };
		effekte[0]();
		const pool = (u.poolLeft as { metric: string }[]).map((d) => d.metric);
		assert.ok(
			pool.includes('precipitation_sum'),
			'AC-7 FAIL: nach Aktivieren von Niederschlag im Wetter-Metriken-Reiter bietet das ' +
				'"+ Metrik"-Dropdown precipitation_sum nicht an.'
		);
		assert.ok(
			!pool.includes('wind_gust'),
			'AC-7 FAIL: wind_gust ist bereits eingestellt, erscheint aber wieder im Pool — der ' +
				'Refresh rechnet mit trip.corridors (im Anlege-Modus leer) statt mit den aktuellen rows.'
		);
		assert.deepEqual(
			u.rows,
			rowsVorher,
			'AC-7 FAIL (Datenverlust): der Pool-Refresh hat die bereits eingestellte Wertebereich-Zeile ' +
				'veraendert oder geloescht.'
		);
	});

	test('Gegenprobe: OHNE createMode laesst der Effekt poolLeft und rows unberuehrt', async () => {
		const { u, effekte, rowsVorher, poolVorher } = await poolRefresh(undefined);
		(u.trip as Knoten).display_config = { metrics: BOEEN_UND_REGEN };
		for (const e of effekte) e();
		assert.deepEqual(
			(u.poolLeft as { metric: string }[]).map((d) => d.metric),
			poolVorher,
			'AC-7 FAIL: ohne createMode (Trip-Hub) veraendert der neue Effekt den Pool.'
		);
		assert.deepEqual(u.rows, rowsVorher, 'AC-7 FAIL: ohne createMode veraendert der neue Effekt rows.');
	});
});
