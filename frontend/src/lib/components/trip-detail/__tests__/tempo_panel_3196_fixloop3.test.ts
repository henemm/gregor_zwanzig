// Fix-Loop 3 — Issue #3196, Adversary F-A2-1 (AC-4: „die Gehzeiten aller Etappen passen sich sofort an").
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md — AC-3, AC-4
//
// Gemessen am Wirkort: das ECHTE Etappen-Panel (EditStagesPanelNew), serverseitig gerendert mit dem
// Trip-Tempo als Prop. Zustaende, die das Panel erst per Klick/`$effect` setzt (offene Listenzeile,
// Handy-Ansicht, aufgeklappte Mobilkarte), kommen ueber den F8-Hook als `$state`-Startwert.
// Etappe: A (0 km, 1000 m) → B (4 km, 1600 m) → C (8 km, 1000 m), Start 08:00.
//   zu Fuss 4 km/h (DAV): 10:30, 12:12, Gehzeit 4:12
//   Rad 20 km/h (DAV):    09:06, 09:48, Gehzeit 1:48
//   zu Fuss 5 km/h (DAV): 10:00, 11:22, Gehzeit 3:22
// Dazu die Weitergabe des Tempos ans Panel im Anlege-Editor (TripNewEditor, Instanz-Pruefstand).
//
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/tempo_panel_3196_fixloop3.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const T = await import('./f9Pruefstand.ts');
const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const P = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const PANEL = path.join(T.KOMP, 'edit', 'EditStagesPanelNew.svelte');
const EDITOR = path.join(T.KOMP, 'trip-new', 'TripNewEditor.svelte');
const TEMPO_INHALT = path.join(T.KOMP, 'organisms', 'tempo-karte', 'TempoKarteInhalt.svelte');

const variante = async (ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(PANEL).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;

const OFFEN: [string, string] = ['let offeneEtappeId = $state<string | null>(null);', "let offeneEtappeId = $state<string | null>('s1');"];
const MOBIL: [string, string][] = [
	['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);'],
	['let expandedStageId = $state<string | null>(null);', "let expandedStageId = $state<string | null>('s1');"]
];

const etappe = () => [{
	id: 's1', name: 'Tag 1', date: '2026-07-01', start_time: '08:00',
	waypoints: [
		{ id: 'A', name: 'Alm', lat: 47, lon: 11, elevation_m: 1000, distance_from_start_km: 0 },
		{ id: 'B', name: 'Gipfel', lat: 47, lon: 11, elevation_m: 1600, distance_from_start_km: 4 },
		{ id: 'C', name: 'Huette', lat: 47, lon: 11, elevation_m: 1000, distance_from_start_km: 8 }
	]
}];

const kopf = () => createRawSnippet(() => ({ render: () => '<div data-testid="probe-kopf">Etappen</div>' }));
const ohneKommentare = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const html = (k: unknown, props: Record<string, unknown>) => ohneKommentare(render(k as any, { props }).body);

/** Inhalt des ersten Elements mit `data-testid` (bis zum naechsten Element gleichen Namens), als Text. */
function abschnitt(h: string, testid: string): string {
	const i = h.indexOf(`data-testid="${testid}"`);
	assert.ok(i >= 0, `[data-testid=${testid}] fehlt`);
	return h.slice(i, i + 4000).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
}

const FAELLE = [
	{ name: 'zu Fuss 4', tempo: { fortbewegung: 'fuss', grundtempo_kmh: 4 }, zeiten: ['10:30', '12:12'], gehzeit: '4:12' },
	{ name: 'Rad 20', tempo: { fortbewegung: 'rad', grundtempo_kmh: 20 }, zeiten: ['09:06', '09:48'], gehzeit: '1:48' },
	{ name: 'zu Fuss 5', tempo: { fortbewegung: 'fuss', grundtempo_kmh: 5 }, zeiten: ['10:00', '11:22'], gehzeit: '3:22' }
] as const;

describe('F-A2-1 (AC-4): das Etappen-Panel rechnet mit dem Trip-Tempo', () => {
	for (const f of FAELLE) {
		const andere = FAELLE.filter((g) => g !== f);
		const pruefe = (text: string, was: string, erwartet: readonly string[]) => {
			for (const z of erwartet) assert.ok(text.includes(z), `${f.name}: ${was} ohne ${z}: ${text.slice(0, 400)}`);
			for (const g of andere) for (const z of g.zeiten) assert.ok(!text.includes(z), `${f.name}: ${was} zeigt ${z} (${g.name})`);
		};

		test(`${f.name}: Gehzeit in der Listenzeile`, async () => {
			const h = html(await variante([]), { stages: etappe(), tripId: 't', showSave: false, tempo: f.tempo, kopf: kopf(), listeZuerst: true });
			const zeile = abschnitt(h, 'etappen-liste-zeile');
			assert.ok(zeile.includes(f.gehzeit), `${f.name}: Listenzeile ohne Gehzeit ${f.gehzeit}: ${zeile.slice(0, 300)}`);
			for (const g of andere) assert.ok(!zeile.slice(0, 300).includes(` ${g.gehzeit}`), `${f.name}: Listenzeile zeigt ${g.gehzeit}`);
		});

		test(`${f.name}: Ankunftszeiten der Wegpunkte im aufgeklappten Editor`, async () => {
			const h = html(await variante([OFFEN]), { stages: etappe(), tripId: 't', showSave: false, tempo: f.tempo, kopf: kopf(), listeZuerst: true });
			const text = h.replace(/<[^>]+>/g, ' ');
			pruefe(text, 'Editor', f.zeiten);
		});

		test(`${f.name}: Ankunftszeiten in der Mobilkarte (StageCardM)`, async () => {
			const h = html(await variante(MOBIL), { stages: etappe(), tripId: 't', showSave: false, tempo: f.tempo });
			pruefe(abschnitt(h, 'stage-cardm-wp-rows'), 'StageCardM', f.zeiten);
		});
	}
});

describe('F-A2-1: der Anlege-Editor reicht das gewaehlte Tempo ans Etappen-Panel', () => {
	test('Wahl Rad in der Karte ⇒ Panel bekommt tempo Rad 20', async () => {
		const { ast, quelle, u } = await P.umgebungFuer(EDITOR, { stateOverride: undefined, untrack: (fn: () => unknown) => fn() });
		const karte = P.findeKomponenten(ast, 'TempoKarte')[0];
		const rueckruf = P.werte(P.attributAusdruck(karte, quelle, 'onchange')!, u) as (t: unknown) => void;
		const { u: k } = await P.umgebungFuer(TEMPO_INHALT, { tempo: u.selectedTempo, onchange: rueckruf });
		k.waehle('rad');
		const panels = P.findeKomponenten(ast, 'EditStagesPanelNew');
		assert.ok(panels.length >= 1, 'Messaufbau: kein Etappen-Panel im Editor');
		for (const p of panels) {
			const a = P.attributAusdruck(p, quelle, 'tempo');
			assert.ok(a, 'Etappen-Panel im Anlegen ohne tempo');
			assert.deepEqual(P.werte(a, u) as Knoten, { fortbewegung: 'rad', grundtempo_kmh: 20 });
		}
	});
});
