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
// `effekteVon(…, 'buildRoutePool')` eingesammelt (einziger Effekt, der den
// Pool direkt neu rechnet — `'poolLeft'` wuerde auch die beiden Katalog-Lade-
// Effekte treffen, `'createMode'` seit #2347 S4 AC-20 auch den Vorbelegungs-
// Effekt, der unten ueber `'routePrefillDone'` eigens geprueft wird).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/corridor-editor/__tests__/corridor_editor_create_mode_route.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, effekteVon, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { buildRoutePool, buildCorridorSavePayload, type CorridorRowState } from '../corridorEditorState.ts';
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
	/** #2347 S4 (Race): Aufrufe von onVorbelegungFertig. */
	fertig: number;
	/** Reihenfolge der Meldungen nach oben ('corridors' | 'fertig'). */
	folge: string[];
}

/** Sentinel: `createMode` fehlt in der Saat GANZ — Aequivalent zum Trip-Hub-
 *  Mount (`TripTabs.svelte:229`), der die Prop gar nicht setzt. Unterscheidet
 *  sich bewusst von einer expliziten `createMode: undefined`-Bindung: nur bei
 *  einem GANZ fehlenden Schluessel bindet `umgebungFuer()` den echten
 *  Quelltext-Default `createMode = false` (Adversary F001-Fix,
 *  `svelteInstanzPruefstand.ts`). */
const CREATE_MODE_FEHLT = Symbol('createMode-fehlt-in-der-saat');

/** Saat des route-Zweigs, wie TripNewEditor ihn mountet. JEDE Prop steht
 *  explizit in der Saat (auch als `undefined`): eine fehlende Bindung laesst
 *  `with(u)` mit ReferenceError scheitern, und `umgebungFuer()` schluckt
 *  Deklarationsfehler still — `originalLevels` fehlte dann unbemerkt.
 *  AUSNAHME `createMode`: steht NUR in der Saat, wenn der Aufrufer nicht
 *  `CREATE_MODE_FEHLT` uebergibt — siehe Sentinel oben. */
function baueSaat(createMode: unknown, spione: Spione, metrics: unknown[] = NUR_BOEEN): Knoten {
	const saat: Knoten = {
		context: 'route',
		trip: { id: '__new__', display_config: { metrics } },
		onTripUpdate: undefined,
		saveController: {
			schedule: (...a: unknown[]) => spione.schedule.push(a),
			setUnsavedInput: (...a: unknown[]) => spione.setDirty.push(a)
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
		onCorridorsChange: (...a: unknown[]) => {
			spione.corridors.push(a);
			spione.folge.push('corridors');
		},
		onIdealRangesChange: undefined,
		onActiveMetricKeysChange: undefined,
		onMetricAlertLevelsChange: undefined,
		onVorbelegungFertig: () => {
			spione.fertig++;
			spione.folge.push('fertig');
		},
		untrack: (fn: () => unknown) => fn(),
		// Transport neutralisiert: der route-PUT wird nur VORBEREITET (Spion),
		// nie abgeschickt.
		api: {},
		baueTripSpeicherung: (...a: unknown[]) => {
			spione.gebaut.push(a);
			return async () => {};
		}
	};
	if (createMode !== CREATE_MODE_FEHLT) saat.createMode = createMode;
	return saat;
}

function neueSpione(): Spione {
	return { schedule: [], setDirty: [], corridors: [], gebaut: [], fertig: 0, folge: [] };
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

	test('Positiv-Gegenprobe (AC-4): OHNE createMode-Prop (Trip-Hub-Mount-Aequivalent) bleibt der Hub-Speicherweg — schedule 1× je Aenderung, setDirty 1× bei ungueltig', async () => {
		const { u, spione } = await baueEditor(CREATE_MODE_FEHLT);
		assert.equal(
			u.createMode,
			false,
			'Messaufbau kaputt: `createMode` fehlte in der Saat, aber `umgebungFuer()` hat den ' +
				'Quelltext-Default `createMode = false` nicht gebunden — dieser Test misst dann ' +
				'nichts ueber den echten Default (F001).'
		);
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
		const effekte = effekteVon(ast, quelle, u, 'buildRoutePool');
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
			`AC-7 FAIL: ${effekte.length} $effect-Ruempfe nennen \`buildRoutePool\` (erwartet: genau einer — ` +
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

	// Adversary F002 (Fix-Loop 1): die obige Zeile (`wind_gust`) uebersteht den
	// Roundtrip rows -> corridorsNow -> rebuilt.rows verlustfrei bit-identisch
	// (buildRoutePool baut sie aus dem PRAESENTEN Katalog-Eintrag neu auf) — die
	// Mutation `rows = rebuilt.rows` war dort ein struktureller Nulleffekt.
	// Eine Zeile, deren Metrik-ID im (Basis- + Zusatz-)Katalog dieses
	// Messaufbaus GAR NICHT vorkommt (`u.routeExtraDefs` ist hier bewusst leer,
	// wie es das Rezept oben schon seed­et), landet beim Rebuild dagegen in
	// `unknownCorridors` statt in `rows` — der Roundtrip ist fuer sie NICHT
	// verlustfrei. Der korrekte Effekt (nur `poolLeft` ueberschreiben) laesst
	// `u.rows` unangetastet; der mutierte Effekt (`rows = rebuilt.rows`) wuerde
	// sie stillschweigend aus `u.rows` entfernen.
	test('createMode=true: Zeile mit einer Metrik-ID ausserhalb des (Basis- + Zusatz-)Katalogs bleibt in u.rows erhalten', async () => {
		const { u, ast, quelle } = await baueEditor(true, NUR_BOEEN);
		const unbekannteZeile: CorridorRowState = {
			metric: 'thunder_level_max',
			label: 'Gewitter',
			unit: '',
			scale: [0, 2],
			step: 1,
			min: 1,
			max: 2,
			notify: true,
			mark: false,
			kind: 'ordinal'
		};
		u.rows = [unbekannteZeile];
		u.poolLeft = [];
		const rowsVorher: CorridorRowState[] = structuredClone(u.rows as CorridorRowState[]);

		// Vorbedingung (Nachweis, dass dieser Test nicht leer laeuft): der reine
		// Roundtrip ueber buildRoutePool() verliert die Zeile TATSAECHLICH aus
		// `rows` (sie landet in `unknownCorridors`) — ohne diesen Beleg waere
		// jede weitere Assertion unten bedeutungslos (Mutation 6 aus Runde 2
		// blieb genau deshalb unbemerkt: die dort gesaete Zeile ueberstand den
		// Roundtrip verlustfrei).
		const corridorsNowVorab = buildCorridorSavePayload(u.rows as CorridorRowState[], {}, []).corridors;
		const probe = buildRoutePool(corridorsNowVorab, NUR_BOEEN as never, []);
		assert.notDeepEqual(
			probe.rows,
			rowsVorher,
			'Messaufbau kaputt: der reine Roundtrip verliert die Zeile NICHT — die Vorbedingung fuer ' +
				'diesen Test greift nicht (die Katalog-Annahme "unbekannte Metrik-ID" stimmt hier nicht), ' +
				'jede weitere Assertion liefe leer.'
		);
		assert.ok(
			probe.unknownCorridors.some((c) => c.metric === 'thunder_level_max'),
			'Messaufbau kaputt: die Zeile landet nicht wie erwartet in unknownCorridors.'
		);

		const effekte = effekteVon(ast, quelle, u, 'buildRoutePool');
		assert.equal(
			effekte.length,
			1,
			`AC-7 FAIL: ${effekte.length} $effect-Ruempfe nennen \`buildRoutePool\` (erwartet: genau einer).`
		);
		(u.trip as Knoten).display_config = { metrics: BOEEN_UND_REGEN };
		effekte[0]();

		assert.deepEqual(
			u.rows,
			rowsVorher,
			'AC-7 FAIL (Datenverlust): der Pool-Refresh hat die Zeile mit der katalogfremden Metrik-ID ' +
				'aus u.rows verloren — ein reiner Ueberschreib-Effekt darf NUR poolLeft neu berechnen.'
		);
	});
});

// Issue #2347 S4 (AC-20, E2E AN-6 route „Wertebereiche fehlen im POST"): der
// Vergleich belegt beim frischen Anlegen Wertebereiche vor (isFreshCompareCreate
// -> syncToWizard). Das Trip-Pendant ist ein $effect im ECHTEN Instanz-Skript
// (Wirkort), eingesammelt ueber den nur von ihm genannten Bezeichner
// `routePrefillDone`: sobald Zusatz-Katalog UND Wetter-Metriken-Auswahl da
// sind, belegt er die Zeilen der aktiven Metriken vor und meldet sie GENAU
// EINMAL ueber onCorridorsChange — nur im Anlege-Modus, nie bei Bestand.
describe('AC-20: frisches Trip-Anlegen belegt Wertebereiche vor und meldet sie einmal', () => {
	const ERWARTET = [
		{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false },
		{ metric: 'precipitation_sum', range: [null, 5], notify: true, mark: false }
	];

	async function vorbelegung(createMode: unknown, metrics: unknown[] = BOEEN_UND_REGEN) {
		const ed = await baueEditor(createMode, metrics);
		const effekte = effekteVon(ed.ast, ed.quelle, ed.u, 'routePrefillDone');
		assert.equal(effekte.length, 1, `Messaufbau: ${effekte.length} Effekte nennen routePrefillDone (erwartet 1).`);
		return { ...ed, lauf: effekte[0] };
	}

	test('createMode=true: aktive Metriken ⇒ Zeilen mit Startwerten, genau EINE Meldung nach oben', async () => {
		const { u, spione, lauf } = await vorbelegung(true);
		lauf();
		assert.deepEqual(
			(u.rows as CorridorRowState[]).map((r) => [r.metric, r.min, r.max]),
			[['wind_gust', null, 70], ['precipitation_sum', null, 5]],
			'AC-20 FAIL: der Reiter Wertebereiche startet beim Trip-Anlegen nicht mit den aktiven Metriken.'
		);
		assert.equal(spione.corridors.length, 1, 'AC-20 FAIL: die Vorbelegung wurde nicht genau einmal gemeldet.');
		assert.deepEqual(spione.corridors[0][0], ERWARTET, 'AC-20 FAIL: gemeldete Korridore weichen ab.');
		const payload = buildCreateTripPayload({
			name: 'Karnischer Höhenweg',
			startDate: '2026-06-15',
			stages: [{ id: 1, name: 'Toblach → Helmhotel' }],
			channels: { email: true, telegram: false, sms: false },
			corridors: spione.corridors[0][0]
		} as CreateTripState);
		assert.deepEqual((payload as { corridors?: unknown }).corridors, ERWARTET, 'AC-20 FAIL: Vorbelegung fehlt im POST.');

		// Einmaligkeit: spaeteres Umschalten der Metriken belegt nicht erneut vor.
		(u.trip as Knoten).display_config = { metrics: NUR_BOEEN };
		u.rows = [];
		lauf();
		assert.equal(spione.corridors.length, 1, 'AC-20 FAIL: zweite Vorbelegung nach Metrik-Umschalten.');
		assert.deepEqual(u.rows, [], 'AC-20 FAIL: zweite Vorbelegung ueberschreibt den Nutzerstand.');
	});

	test('wartet auf die Wetter-Metriken-Auswahl statt leer zu melden', async () => {
		const { u, spione, lauf } = await vorbelegung(true);
		// Wetter-Metriken-Reiter hat noch nichts gemeldet (stubTrip startet mit metrics: []).
		(u.trip as Knoten).display_config = { metrics: [] };
		lauf();
		assert.deepEqual(u.rows, [], 'AC-20 FAIL: ohne gemeldete Metrik-Auswahl wurden Zeilen gesetzt.');
		assert.equal(spione.corridors.length, 0, 'AC-20 FAIL: ohne Metrik-Auswahl wurde gemeldet.');
		(u.trip as Knoten).display_config = { metrics: BOEEN_UND_REGEN };
		lauf();
		assert.deepEqual(spione.corridors.at(-1)?.[0], ERWARTET, 'AC-20 FAIL: nach eintreffender Auswahl keine Vorbelegung.');
	});

	test('wartet auf den Zusatz-Katalog (routeExtraDefs === null)', async () => {
		const { u, spione, lauf } = await vorbelegung(true);
		u.routeExtraDefs = null;
		lauf();
		assert.equal(spione.corridors.length, 0, 'AC-20 FAIL: Vorbelegung vor dem Katalog-Laden.');
	});

	test('Gegenprobe Trip-Hub (ohne createMode): keine Vorbelegung, keine Meldung', async () => {
		const { u, spione, lauf } = await vorbelegung(CREATE_MODE_FEHLT);
		lauf();
		assert.deepEqual(u.rows, [], 'AC-20 FAIL: im Trip-Hub wurden Wertebereiche vorbelegt.');
		assert.equal(spione.corridors.length + spione.schedule.length, 0, 'AC-20 FAIL: im Trip-Hub wurde gemeldet/gespeichert.');
	});

	test('Bestandsdaten bleiben: vorhandene trip.corridors bzw. schon eingestellte Zeilen ⇒ unberuehrt', async () => {
		const bestand = await vorbelegung(true);
		(bestand.u.trip as Knoten).corridors = [{ metric: 'snow_line', range: [1800, null], notify: false, mark: false }];
		bestand.lauf();
		assert.deepEqual(bestand.u.rows, [], 'AC-20 FAIL: Trip mit Korridoren wurde vorbelegt.');
		assert.equal(bestand.spione.corridors.length, 0);

		// Remount (Desktop <-> Mobil an der 900-px-Grenze): die neue Instanz bekommt
		// den oben gehaltenen Stand als `corridors` und darf ihn nicht ueberschreiben.
		const remount = await vorbelegung(true);
		remount.u.corridors = [{ metric: 'wind_gust', range: [null, 90], notify: true, mark: false }];
		remount.lauf();
		assert.deepEqual(remount.u.rows, [], 'AC-20 FAIL: Remount belegt trotz gehaltenem Stand vor.');
		assert.equal(remount.spione.corridors.length, 0, 'AC-20 FAIL: Remount ueberschreibt den gehaltenen Stand.');

		const eingestellt = await vorbelegung(true);
		eingestellt.u.add('wind_gust');
		const vorher = structuredClone(eingestellt.u.rows);
		const meldungen = eingestellt.spione.corridors.length;
		eingestellt.lauf();
		assert.deepEqual(eingestellt.u.rows, vorher, 'AC-20 FAIL: die Vorbelegung ueberschreibt eine eingestellte Zeile.');
		assert.equal(eingestellt.spione.corridors.length, meldungen, 'AC-20 FAIL: zusaetzliche Meldung trotz Nutzerstand.');
	});
});

// Issue #2347 S4 (AC-20, Race „Standardwerte-Trip vs. durchgeklickter Trip"): der
// Standardwerte-Knopf im Trip-Anlegen darf erst freigeben, wenn die Vorbelegung
// gelaufen ist. Der Editor meldet das ueber onVorbelegungFertig — GENAU EINMAL,
// auf JEDEM Ausgang (sonst bleibt der Knopf dauerhaft gesperrt), und erst NACH
// der Korridor-Meldung (sonst geht `corridors: []` raus).
describe('AC-20 Race: Vorbelegung meldet „fertig" einmal, auf jedem Ausgang, nach den Korridoren', () => {
	async function vorbelegung(metrics: unknown[] = BOEEN_UND_REGEN) {
		const ed = await baueEditor(true, metrics);
		const effekte = effekteVon(ed.ast, ed.quelle, ed.u, 'routePrefillDone');
		assert.equal(effekte.length, 1, `Messaufbau: ${effekte.length} Effekte nennen routePrefillDone (erwartet 1).`);
		return { ...ed, lauf: effekte[0] };
	}

	test('mit vorbelegten Zeilen: erst Korridore, dann „fertig" — und nur einmal', async () => {
		const { spione, lauf } = await vorbelegung();
		lauf();
		assert.deepEqual(spione.folge, ['corridors', 'fertig'], 'Race FAIL: „fertig" nicht nach der Korridor-Meldung.');
		lauf();
		assert.equal(spione.fertig, 1, 'Race FAIL: „fertig" mehrfach gemeldet.');
	});

	test('Vorbelegung ergibt keine Zeile (Metrik abgewaehlt) ⇒ trotzdem „fertig", keine Korridore', async () => {
		const { u, spione, lauf } = await vorbelegung();
		(u.trip as Knoten).display_config = { metrics: [{ metric_id: 'gust', enabled: false }] };
		lauf();
		assert.equal(spione.corridors.length, 0, 'Messaufbau: Vorbelegung haette leer sein muessen.');
		assert.equal(spione.fertig, 1, 'Race FAIL (Deadlock): leere Vorbelegung meldet nie „fertig".');
	});

	test('Bestand bzw. gehaltener Stand (Remount) ⇒ trotzdem „fertig", keine Korridore', async () => {
		const bestand = await vorbelegung();
		(bestand.u.trip as Knoten).corridors = [{ metric: 'snow_line', range: [1800, null], notify: false, mark: false }];
		bestand.lauf();
		assert.equal(bestand.spione.fertig, 1, 'Race FAIL (Deadlock): Bestand meldet nie „fertig".');
		const remount = await vorbelegung();
		remount.u.corridors = [{ metric: 'wind_gust', range: [null, 90], notify: true, mark: false }];
		remount.lauf();
		assert.equal(remount.spione.fertig, 1, 'Race FAIL (Deadlock): Remount meldet nie „fertig".');
		assert.equal(remount.spione.corridors.length, 0);
	});

	test('Zusatz-Katalog gescheitert (Rueckfall routeExtraDefs = []) ⇒ Vorbelegung laeuft, „fertig" kommt', async () => {
		// baueEditor setzt routeExtraDefs = [] — genau der Wert, den der catch-Zweig
		// des Lade-Effekts nach einem Fehlschlag setzt.
		const { u, spione, lauf } = await vorbelegung();
		assert.deepEqual(u.routeExtraDefs, []);
		lauf();
		assert.equal(spione.fertig, 1, 'Race FAIL (Deadlock): Katalog-Fehler blockiert „fertig".');
		assert.equal(spione.corridors.length, 1);
	});

	test('vor Katalog bzw. vor der Metrik-Auswahl: KEIN „fertig"', async () => {
		const ohneKatalog = await vorbelegung();
		ohneKatalog.u.routeExtraDefs = null;
		ohneKatalog.lauf();
		assert.equal(ohneKatalog.spione.fertig, 0, 'Race FAIL: „fertig" vor dem Zusatz-Katalog.');
		const ohneAuswahl = await vorbelegung();
		(ohneAuswahl.u.trip as Knoten).display_config = { metrics: [] };
		ohneAuswahl.lauf();
		assert.equal(ohneAuswahl.spione.fertig, 0, 'Race FAIL: „fertig" vor der Metrik-Auswahl.');
	});
});
