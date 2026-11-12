// Issue #2347 S4 (AC-20, Race „Standardwerte-Trip vs. durchgeklickter Trip"):
// der Standardwerte-Knopf im Trip-Anlegen wurde allein ueber `catalogLoaded`
// (Wetter-Metriken-Katalog) freigegeben. Die Wertebereiche-Vorbelegung wartet
// aber zusaetzlich auf den Zusatz-Katalog — ein frueher Klick schickte
// `corridors: []`, der durchgeklickte Trip dagegen die Vorbelegung.
//
// #2794 S3a Teil-PR 4a (AC-43/AC-45): die Vorbelegung lief bisher in einem
// unsichtbar gemounteten CorridorEditor (Rueckrufe `onCorridorsChange`/
// `onVorbelegungFertig` an zwei Einbettungen, Desktop und mobil). Sie ist jetzt
// EIN `$effect` im TripNewEditor (`vorbelegungsLauf`, reine Funktion aus
// shared/wetter-tab/anlegeVorbelegung.ts). Gemessen wird weiter an der
// WIRKSTELLE (standardwerteEditorPruefstand.ts): `enabled` der ECHTEN
// <StandardwerteSpeichernKnopf>-Einbettungen, der echte Klick-Handler und der
// ECHTE Vorbelegungs-Effekt des Editors. Die reine Funktion selbst prueft
// shared/wetter-tab/__tests__/anlege_vorbelegung.test.ts.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/standardwerte_wartet_auf_wertebereiche_vorbelegung.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { effekteVon, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	TRIP_EDITOR,
	editorUmgebung,
	derivedNeu,
	ruhe,
	knopfEinbettungen,
	knopfAttribut,
	type EditorUmgebung
} from '../../shared/__tests__/standardwerteEditorPruefstand.ts';

const GPX = { file: 'a.gpx', km: 10, asc: 500 };
const AUSWAHL = [{ metric_id: 'gust', enabled: true }];
// Was der fruehere CorridorEditor fuer die Auswahl „Boeen" meldete (PO-freigegebener Startwert).
const VORBELEGUNG = [{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false }];

interface Lauf {
	e: EditorUmgebung;
	posts: Array<{ url: string; body: Knoten }>;
}

/** Pflicht erfuellt, Wetter-Metriken-Katalog geladen, Auswahl gemeldet — nur die
 *  Vorbelegung der Wertebereiche steht (je nach Saat) noch aus. */
async function trip(saat: Knoten = {}): Promise<Lauf> {
	const posts: Lauf['posts'] = [];
	const e = await editorUmgebung(TRIP_EDITOR, {
		stateOverride: {},
		name: 'Trip X',
		startDate: '2026-07-01',
		stages: [1, 2].map((id) => ({ id, name: `E${id}`, gpx: GPX, waypoints: [] })),
		catalogLoaded: true,
		weatherMetrics: AUSWAHL,
		api: { post: async (url: string, body: Knoten) => (posts.push({ url, body }), { id: 'neu-1' }), get: async () => ({}) },
		...saat
	});
	assert.equal(e.u.ready, false, 'Messaufbau: Bestandsknopf muss gesperrt sein (Reiter nie besucht)');
	return { e, posts };
}

function knoepfeAktiv(e: EditorUmgebung): boolean[] {
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(knoepfe.length >= 2, `Messaufbau: ${knoepfe.length} Standardwerte-Knoepfe (erwartet Desktop + mobil)`);
	return knoepfe.map((k) => Boolean(knopfAttribut(k, e, 'enabled')));
}

function knoepfeGesperrt(e: EditorUmgebung): boolean {
	return knoepfeAktiv(e).every((a) => a === false);
}

/** Der ECHTE Vorbelegungs-Effekt des Editors (AST-Auswahl ueber den Lauf-Bezeichner). */
function vorbelegungsEffekt(e: EditorUmgebung): () => void {
	const effekte = effekteVon(e.ast, e.quelle, e.u, 'vorbelegungsLauf');
	assert.equal(effekte.length, 1, `Messaufbau: ${effekte.length} Vorbelegungs-Effekte im TripNewEditor (erwartet genau 1)`);
	return effekte[0];
}

describe('AC-20 Race: Standardwerte-Knopf (Trip) wartet auf die Wertebereiche-Vorbelegung', () => {
	test('Katalog geladen, Zusatz-Katalog der Vorbelegung ausstehend ⇒ alle Knoepfe gesperrt, ein Klick speichert nichts', async () => {
		const { e, posts } = await trip({ routeExtraDefs: null });
		vorbelegungsEffekt(e)();
		derivedNeu(e);
		assert.ok(knoepfeGesperrt(e), 'Race FAIL: Knopf frei, bevor die Wertebereiche vorbelegt sind');
		await (knopfAttribut(knopfEinbettungen(e.ast)[0], e, 'onclick') as () => unknown)();
		assert.deepEqual(posts, [], 'Race FAIL: Klick vor der Vorbelegung hat gespeichert (corridors: [])');
	});

	for (const [wo, mobil] of [['Desktop', false], ['mobil', true]] as const) {
		test(`Vorbelegung gelaufen (${wo}) ⇒ frei, der POST traegt die vorbelegten Korridore`, async () => {
			const { e, posts } = await trip({ routeExtraDefs: [], isMobileViewport: mobil });
			assert.ok(knoepfeGesperrt(e), 'Messaufbau: vor dem Effekt muss der Knopf gesperrt sein');
			vorbelegungsEffekt(e)();
			derivedNeu(e);
			assert.deepEqual(e.u.corridors, VORBELEGUNG, 'AC-43 FAIL: der Effekt hat die Wertebereiche nicht vorbelegt');
			assert.deepEqual(knoepfeAktiv(e), knoepfeAktiv(e).map(() => true), 'Race FAIL: nach der Vorbelegung bleibt der Knopf gesperrt');
			await (knopfAttribut(knopfEinbettungen(e.ast)[0], e, 'onclick') as () => unknown)();
			assert.equal(posts.length, 1, 'Messaufbau: genau ein POST erwartet');
			assert.deepEqual(posts[0].body.corridors, VORBELEGUNG, 'Race FAIL: Standardwerte-POST ohne die Vorbelegung');
		});
	}

	test('AC-45: der Effekt laeuft erneut (z. B. Breitenwechsel) ⇒ keine zweite Vorbelegung, Nutzerwert bleibt', async () => {
		const { e } = await trip({ routeExtraDefs: [] });
		const effekt = vorbelegungsEffekt(e);
		effekt();
		const eigen = [{ metric: 'wind_gust', range: [null, 40], notify: true, mark: false }];
		e.u.corridors = eigen;
		effekt();
		effekt();
		assert.deepEqual(e.u.corridors, eigen, 'AC-45 FAIL: ein erneuter Effekt-Lauf hat die Wertebereiche erneut vorbelegt');
	});

	test('keine aktive Metrik (nichts vorzubelegen) ⇒ frei ohne Meldung — kein Deadlock', async () => {
		const { e } = await trip({ weatherMetrics: [] });
		assert.ok(knoepfeAktiv(e).every((a) => a === true), 'Race FAIL (Deadlock): ohne Metrik bleibt der Knopf gesperrt');
	});

	test('nur Metriken ohne Startwert ⇒ Fertig-Signal trotzdem, Knopf frei, corridors leer', async () => {
		const { e } = await trip({ routeExtraDefs: [], weatherMetrics: [{ metric_id: 'thunder', enabled: true }] });
		vorbelegungsEffekt(e)();
		derivedNeu(e);
		assert.deepEqual(e.u.corridors, [], 'nichts vorzubelegen — es darf nichts erfunden werden');
		assert.ok(knoepfeAktiv(e).every((a) => a === true), 'Race FAIL: ohne Vorbelegung bleibt der Knopf fuer immer gesperrt');
	});

	// Fix-Loop 1 F002: der Effekt laeuft mehrfach — zuerst nur Metriken ohne Startwert (Lauf fertig,
	// nichts vorbelegt), danach waehlt der Nutzer eine Metrik MIT Startwert. Der eine Lauf je
	// Editor-Instanz ist fertig: kein zweites Fertig-Signal, keine nachtraegliche Vorbelegung.
	test('F002: erneuter Effekt nach Metrik-Wechsel ⇒ Fertig-Signal bleibt bei 1, keine zweite Vorbelegung', async () => {
		const { e } = await trip({ routeExtraDefs: [], weatherMetrics: [{ metric_id: 'thunder', enabled: true }] });
		const effekt = vorbelegungsEffekt(e);
		effekt();
		assert.equal(e.u.wertebereicheVorbelegt, true, 'Messaufbau: der erste Lauf muss fertig melden');
		assert.deepEqual(e.u.corridors, [], 'Messaufbau: ohne Startwert nichts vorbelegt');
		// Fertig-Signal zuruecksetzen: kommt es ein zweites Mal, steht es danach wieder auf true.
		e.u.wertebereicheVorbelegt = false;
		e.u.weatherMetrics = AUSWAHL;
		effekt();
		assert.equal(e.u.wertebereicheVorbelegt, false, 'F002 FAIL: zweites Fertig-Signal nach erneutem Effekt-Lauf');
		assert.deepEqual(e.u.corridors, [], 'F002 FAIL: der erneute Effekt-Lauf hat nachtraeglich vorbelegt');
	});

	// Fix-Loop 1 F004: vorab gesetzte Wertebereiche (z. B. aus einer Vorlage) bleiben unangetastet.
	test('F004: vorab gesetzte corridors bleiben nach dem Effekt unveraendert, Fertig-Signal kommt', async () => {
		const vorlage = [{ metric: 'wind_gust', range: [null, 40], notify: false, mark: true }];
		const { e } = await trip({ routeExtraDefs: [], corridors: JSON.parse(JSON.stringify(vorlage)) });
		vorbelegungsEffekt(e)();
		assert.deepEqual(e.u.corridors, vorlage, 'F004 FAIL: die Vorbelegung hat vorhandene Wertebereiche ueberschrieben');
		assert.equal(e.u.wertebereicheVorbelegt, true, 'F004 FAIL: ohne Fertig-Signal bliebe Standardwerte gesperrt');
	});

	test('Wetter-Metriken-Katalog gescheitert ⇒ gesperrt, auch wenn die Vorbelegung gelaufen ist (Bestand AC-3)', async () => {
		const { e } = await trip({ catalogLoaded: false, routeExtraDefs: [] });
		vorbelegungsEffekt(e)();
		derivedNeu(e);
		assert.equal(e.u.wertebereicheVorbelegt, true, 'Messaufbau: die Vorbelegung muss gelaufen sein');
		assert.ok(knoepfeGesperrt(e), 'Race FAIL: Vorbelegung ersetzt den geladenen Metrik-Katalog');
	});
});

// Fix-Loop 1 F005: der Zusatz-Katalog (GET /api/compare/metrics) scheitert im Netz. Der echte
// onMount des Editors laedt ihn ueber den echten Loader; nur die Netzgrenze (fetch) antwortet 500.
// Erwartet: Rueckfall auf die fest verdrahteten Startwerte (`routeExtraDefs = []`), Vorbelegung
// aus der Auswahl, genau ein Fertig-Signal, Standardwerte-Knopf frei — kein Haengenbleiben.
describe('F005: Zusatz-Katalog scheitert ⇒ Rueckfall auf Startwerte, Knopf frei', () => {
	let originalFetch: typeof globalThis.fetch;
	before(() => {
		originalFetch = globalThis.fetch;
		globalThis.fetch = (async (input: unknown) => {
			const url = String(input);
			if (url.includes('/api/compare/metrics')) return new Response('kaputt', { status: 500 });
			return new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } });
		}) as typeof globalThis.fetch;
	});
	after(() => {
		globalThis.fetch = originalFetch;
	});

	test('Katalog-Abruf abgelehnt ⇒ routeExtraDefs = [], corridors vorbelegt, Fertig-Signal genau einmal, Knopf frei', async () => {
		const { e, posts } = await trip({});
		assert.equal(e.u.routeExtraDefs, null, 'Messaufbau: vor dem Mount ist der Zusatz-Katalog nicht geladen');
		assert.ok(e.mounts.length >= 1, 'Messaufbau: kein onMount im TripNewEditor gefunden');
		for (const fn of e.mounts) {
			try {
				fn();
			} catch {
				/* Browser-API fehlt serverseitig */
			}
		}
		await ruhe();
		assert.deepEqual(e.u.routeExtraDefs, [], 'F005 FAIL: abgelehnter Katalog-Abruf setzt keinen Rueckfall — Vorbelegung haengt');
		const effekt = vorbelegungsEffekt(e);
		effekt();
		derivedNeu(e);
		assert.deepEqual(e.u.corridors, VORBELEGUNG, 'F005 FAIL: ohne Zusatz-Katalog nicht aus den Startwerten vorbelegt');
		assert.equal(e.u.wertebereicheVorbelegt, true, 'F005 FAIL: kein Fertig-Signal');
		e.u.wertebereicheVorbelegt = false;
		effekt();
		assert.equal(e.u.wertebereicheVorbelegt, false, 'F005 FAIL: Fertig-Signal mehr als einmal');
		e.u.wertebereicheVorbelegt = true;
		derivedNeu(e);
		assert.ok(knoepfeAktiv(e).every((a) => a === true), 'F005 FAIL: Standardwerte-Knopf bleibt gesperrt');
		await (knopfAttribut(knopfEinbettungen(e.ast)[0], e, 'onclick') as () => unknown)();
		assert.equal(posts.length, 1, 'Messaufbau: genau ein POST erwartet');
		assert.deepEqual(posts[0].body.corridors, VORBELEGUNG, 'F005 FAIL: Standardwerte-POST ohne Vorbelegung');
	});
});
