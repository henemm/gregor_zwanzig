// Issue #2347 S4 (AC-20, Race „Standardwerte-Trip vs. durchgeklickter Trip"):
// der Standardwerte-Knopf im Trip-Anlegen wurde allein ueber `catalogLoaded`
// (Wetter-Metriken-Katalog) freigegeben. Die Wertebereiche-Vorbelegung des
// CorridorEditors wartet aber zusaetzlich auf dessen eigenen Katalog-Abruf —
// ein frueher Klick schickte `corridors: []`, der durchgeklickte Trip dagegen die
// Vorbelegung (E2E standardwerte-und-hilfe AC-6 kann flaken).
//
// Gemessen an der WIRKSTELLE (standardwerteEditorPruefstand.ts): `enabled` der
// ECHTEN <StandardwerteSpeichernKnopf>-Einbettungen, der echte Klick-Handler und
// der Rueckruf `onVorbelegungFertig` der ECHTEN <CorridorEditor>-Einbettungen
// (Desktop UND mobil). Das Gegenstueck im Editor (Meldung auf jedem Ausgang)
// prueft corridor_editor_create_mode_route.test.ts.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/standardwerte_wartet_auf_wertebereiche_vorbelegung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { findeKomponenten, attributAusdruck, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	TRIP_EDITOR,
	editorUmgebung,
	derivedNeu,
	knopfEinbettungen,
	knopfAttribut,
	type EditorUmgebung
} from '../../shared/__tests__/standardwerteEditorPruefstand.ts';

const GPX = { file: 'a.gpx', km: 10, asc: 500 };
const AUSWAHL = [{ metric_id: 'gust', enabled: true }];
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

function corridorEinbettungen(e: EditorUmgebung): Knoten[] {
	const ed = findeKomponenten(e.ast, 'CorridorEditor');
	assert.equal(ed.length, 2, `Messaufbau: ${ed.length} CorridorEditor-Einbettungen (erwartet Desktop + mobil)`);
	return ed;
}

function rueckruf(einbettung: Knoten, e: EditorUmgebung, name: string): (...a: unknown[]) => unknown {
	const ausdruck = attributAusdruck(einbettung, e.quelle, name);
	assert.ok(ausdruck, `Race FAIL: CorridorEditor-Einbettung ohne \`${name}\` — die Vorbelegung meldet nie nach oben.`);
	const fn = werte(ausdruck, e.u);
	assert.equal(typeof fn, 'function', `Messaufbau: \`${name}\` ist keine Funktion`);
	return fn as (...a: unknown[]) => unknown;
}

describe('AC-20 Race: Standardwerte-Knopf (Trip) wartet auf die Wertebereiche-Vorbelegung', () => {
	test('Katalog geladen, Vorbelegung ausstehend ⇒ alle Knoepfe gesperrt, ein Klick speichert nichts', async () => {
		const { e, posts } = await trip();
		assert.ok(knoepfeGesperrt(e), 'Race FAIL: Knopf frei, bevor die Wertebereiche vorbelegt sind');
		await (knopfAttribut(knopfEinbettungen(e.ast)[0], e, 'onclick') as () => unknown)();
		assert.deepEqual(posts, [], 'Race FAIL: Klick vor der Vorbelegung hat gespeichert (corridors: [])');
	});

	for (const [i, wo] of ['Desktop', 'mobil'].entries()) {
		test(`Vorbelegung gemeldet (${wo}er CorridorEditor) ⇒ frei, der POST traegt die vorbelegten Korridore`, async () => {
			const { e, posts } = await trip();
			const ed = corridorEinbettungen(e)[i];
			rueckruf(ed, e, 'onCorridorsChange')(VORBELEGUNG);
			derivedNeu(e);
			assert.ok(knoepfeGesperrt(e), 'Race FAIL: Korridor-Meldung allein gibt frei (fertig fehlt noch)');
			rueckruf(ed, e, 'onVorbelegungFertig')();
			derivedNeu(e);
			assert.deepEqual(knoepfeAktiv(e), knoepfeAktiv(e).map(() => true), 'Race FAIL: nach der Vorbelegung bleibt der Knopf gesperrt');
			await (knopfAttribut(knopfEinbettungen(e.ast)[0], e, 'onclick') as () => unknown)();
			assert.equal(posts.length, 1, 'Messaufbau: genau ein POST erwartet');
			assert.deepEqual(posts[0].body.corridors, VORBELEGUNG, 'Race FAIL: Standardwerte-POST ohne die Vorbelegung');
		});
	}

	test('keine aktive Metrik (nichts vorzubelegen) ⇒ frei ohne Meldung — kein Deadlock', async () => {
		const { e } = await trip({ weatherMetrics: [] });
		assert.ok(knoepfeAktiv(e).every((a) => a === true), 'Race FAIL (Deadlock): ohne Metrik bleibt der Knopf gesperrt');
	});

	test('Wetter-Metriken-Katalog gescheitert ⇒ gesperrt, auch wenn die Vorbelegung gemeldet hat (Bestand AC-3)', async () => {
		const { e } = await trip({ catalogLoaded: false });
		rueckruf(corridorEinbettungen(e)[0], e, 'onVorbelegungFertig')();
		derivedNeu(e);
		assert.ok(knoepfeGesperrt(e), 'Race FAIL: Vorbelegung ersetzt den geladenen Metrik-Katalog');
	});
});

function knoepfeGesperrt(e: EditorUmgebung): boolean {
	return knoepfeAktiv(e).every((a) => a === false);
}
