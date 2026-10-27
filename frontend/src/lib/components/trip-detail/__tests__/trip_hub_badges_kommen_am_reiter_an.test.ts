// Feature #2287 (Adversary F001): die Badge-Schluessel des Trip-Hubs sind die neuen
// Reiter-Kennungen. Ein Badge-Wert, der unter der Kennung eines Reiters uebergeben
// wird (oder automatisch aus dem Trip abgeleitet ist), muss an GENAU diesem Reiter
// der Reiterleiste (MTabBar-Items) ankommen. Vor diesem Test liess die Mutation
// `wertebereiche: badgesProp.wertebereiche ??` → `alerts: …` alle Tests gruen, waehrend
// der Zaehler am Reiter Wertebereiche verschwand.
//
// Messweise: das ECHTE Instanz-Skript von TripTabs.svelte wird gegen gesaete Props
// ausgewertet (`svelteInstanzPruefstand.ts`); gemessen werden die Items, die der Hub
// an MTabBar reicht (gefunden ueber ihre testid-Form, nicht ueber den Variablennamen).
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/trip_hub_badges_kommen_am_reiter_an.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { subscriptionTabs } from '../../shared/subscriptionTabs.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const TRIP_HUB = join(HIER, '..', 'TripTabs.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

type Item = { value: string; badge?: number; testid: string };

async function reiterItems(badgesProp: Knoten, trip: Knoten | undefined): Promise<Item[]> {
	// `badges` wird bewusst NICHT gesaet — die echte `$derived`-Abbildung
	// badgesProp → badges muss laufen.
	const { u } = await umgebungFuer(TRIP_HUB, { badgesProp, trip, initialTab: 'uebersicht' }, { jsAlsTs: true });
	const items = Object.values(u).find(
		(v) =>
			Array.isArray(v) &&
			v.length > 0 &&
			v.every((i) => i && typeof i.testid === 'string' && i.testid.startsWith('trip-detail-tab-'))
	) as Item[] | undefined;
	assert.ok(Array.isArray(items), 'Item-Liste der Reiterleiste nicht auswertbar');
	return items;
}

const KENNUNGEN = subscriptionTabs('trip').map((t) => t.id);

describe('F001: ein unter der neuen Kennung uebergebener Badge kommt an genau diesem Reiter an', () => {
	// Je Reiter ein eigener, eindeutiger Wert (11, 12, …) — vertauschte oder verlorene
	// Schluessel fallen sofort auf.
	const werte: Record<string, number> = Object.fromEntries(KENNUNGEN.map((id, i) => [id, 11 + i]));

	for (const id of KENNUNGEN) {
		test(`badges['${id}'] = ${werte[id]} → Item trip-detail-tab-${id} traegt badge ${werte[id]}`, async () => {
			const items = await reiterItems({ ...werte }, { stages: [], alert_rules: [] });
			const item = items.find((i) => i.value === id);
			assert.ok(item, `Reiter '${id}' fehlt in der Reiterleiste`);
			assert.equal(item.badge, werte[id], `Badge am Reiter '${id}' kommt nicht an (Schluessel veraltet?)`);
		});
	}

	test('ein einzelner Badge erscheint NUR an seinem Reiter', async () => {
		for (const id of KENNUNGEN) {
			const items = await reiterItems({ [id]: 5 }, { stages: [], alert_rules: [] });
			const mitBadge = items.filter((i) => i.badge !== undefined).map((i) => i.value);
			assert.deepEqual(mitBadge, [id], `badges['${id}'] landet an ${JSON.stringify(mitBadge)}`);
		}
	});
});

describe('F001: automatisch abgeleitete Badges (Etappen, Wertebereiche) kommen am richtigen Reiter an', () => {
	test('3 Etappen + 2 aktive Regeln → etappen=3, wertebereiche=2', async () => {
		const trip = {
			stages: [{}, {}, {}],
			alert_rules: [{ enabled: true }, { enabled: true }, { enabled: false }]
		};
		const items = await reiterItems({}, trip);
		const badge = (id: string) => items.find((i) => i.value === id)?.badge;
		assert.equal(badge('etappen'), 3);
		assert.equal(badge('wertebereiche'), 2);
		for (const id of KENNUNGEN.filter((k) => k !== 'etappen' && k !== 'wertebereiche')) {
			assert.equal(badge(id), undefined, `unerwarteter Badge am Reiter '${id}'`);
		}
	});
});
