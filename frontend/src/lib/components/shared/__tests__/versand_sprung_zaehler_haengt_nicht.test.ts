// Issue #1743 (S2-Nacharbeit): der Sprung-Zaehler `versandSprung` der Hubs darf nicht
// „haengen bleiben". War er einmal > 0, liess jeder spaetere Remount des Bausteins
// WetterMetrikenVersandPanel (Reiter weg und zurueck) die Seite erneut zu `#versand`
// scrollen. Soll: jeder Reiterwechsel OHNE Anker setzt den Zaehler auf 0; nur ein
// Sprung mit Anker erhoeht ihn. Startwert: Alt-Kennung mit Anker oder Adresse `#versand`.
//
// Messweise (Wirkort): das ECHTE Instanz-Skript von TripTabs/CompareTabs
// (svelteInstanzPruefstand), der echte `handleValueChange`; nur Adresszeile/goto sind
// Aufzeichnungs-Attrappen. Rot ohne Fix: der alte Handler zaehlte nur hoch (`+= 1`),
// nach Reiter weg und zurueck stand der Zaehler weiter auf 1.

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { umgebungFuer, type Knoten } from './svelteInstanzPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const SRC = join(FRONTEND, 'src');
const TRIP_HUB = join(SRC, 'lib/components/trip-detail/TripTabs.svelte');
const VERGLEICH_HUB = join(SRC, 'lib/components/compare/CompareTabs.svelte');

register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const TRIP: Knoten = {
	id: 't-1',
	name: 'Testtrip',
	stages: [{ id: 's1', name: 'E1', date: '2026-10-23', waypoints: [] }],
	report_config: {},
	display_config: {}
};

const globaleAlt = { window: (globalThis as Knoten).window, history: (globalThis as Knoten).history };
afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

function adresszeile(pfad: string, tab: string, hash = ''): void {
	const location: Knoten = { href: `http://localhost${pfad}?tab=${tab}${hash}`, search: `?tab=${tab}`, pathname: pfad, hash };
	(globalThis as Knoten).window = {
		location,
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = { state: null, replaceState() {}, pushState() {} };
}
const gotoAttrappe = () => Promise.resolve();

async function tripHub(tab: string, hash = ''): Promise<Knoten> {
	adresszeile('/trips/t-1', tab, hash);
	return umgebungFuer(
		TRIP_HUB,
		{ initialTab: tab, goto: gotoAttrappe, page: { url: new URL(`http://localhost/trips/t-1?tab=${tab}${hash}`) }, badges: {}, trip: TRIP, saveController: { hasPending: false, flush: async () => {} } },
		{ jsAlsTs: true }
	);
}

async function vergleichHub(tab: string, hash = ''): Promise<Knoten> {
	adresszeile('/compare/c-1', tab, hash);
	return umgebungFuer(
		VERGLEICH_HUB,
		{
			initialTab: tab,
			preset: vollerVergleich('c-1'),
			locations: [],
			orteCount: 3,
			goto: gotoAttrappe,
			page: { url: new URL(`http://localhost/compare/c-1?tab=${tab}${hash}`) }
		},
		{ jsAlsTs: true }
	);
}

const HUBS: Array<[string, (tab: string, hash?: string) => Promise<Knoten>]> = [
	['Trip-Hub', tripHub],
	['Ortsvergleich-Hub', vergleichHub]
];

for (const [name, hubAus] of HUBS) {
	describe(`#1743 ${name}: Sprung-Zaehler versandSprung haengt nicht`, () => {
		test('Sprung mit Anker → >0; Reiter weg und ohne Anker zurueck → 0 (Remount scrollt nicht)', async () => {
			const hub = await hubAus('uebersicht');
			const wechsel = hub.u.handleValueChange as (v: string, a?: 'versand' | null) => Promise<void>;
			assert.equal(hub.u.versandSprung, 0, 'Startwert ohne Anker ist nicht 0');
			await wechsel('wetter-metriken', 'versand');
			assert.ok((hub.u.versandSprung as number) > 0, 'Sprung mit Anker erhoeht den Zaehler nicht');
			await wechsel('alarme');
			await wechsel('wetter-metriken');
			assert.equal(hub.u.versandSprung, 0, 'Zaehler bleibt nach Reiterwechsel ohne Anker haengen — Remount scrollt erneut zu #versand');
		});

		test('erneuter Sprung nach Reset erhoeht wieder', async () => {
			const hub = await hubAus('uebersicht');
			const wechsel = hub.u.handleValueChange as (v: string, a?: 'versand' | null) => Promise<void>;
			await wechsel('wetter-metriken', 'versand');
			await wechsel('uebersicht');
			await wechsel('wetter-metriken', 'versand');
			assert.ok((hub.u.versandSprung as number) > 0);
		});

		test('Startwert: direkter Link ?tab=wetter-metriken#versand → 1', async () => {
			const hub = await hubAus('wetter-metriken', '#versand');
			assert.equal(hub.u.versandSprung, 1, 'Direktlink mit #versand setzt den Startwert nicht');
		});

		test('Startwert: Alt-Kennung ?tab=versand → 1', async () => {
			const hub = await hubAus('versand');
			assert.equal(hub.u.versandSprung, 1);
		});
	});
}
