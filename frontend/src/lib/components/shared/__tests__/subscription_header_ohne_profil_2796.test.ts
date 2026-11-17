// TDD RED — Issue #2796 S4a (ADR-0108 P3): Profil-Auswahl im geteilten Kopf ist optional.
// Spec: docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md (AC-1, AC-2, AC-3)
//
// Der Orts-Vergleich übergibt keine Auswahlliste mehr: dann zeichnet der Baustein weder
// Desktop-Kacheln (`*-profil-option-*`) noch Handy-Knopf/-Auswahl (`*-profil-knopf`,
// `*-profil-auswahl`) noch „ · {Profil}" hinter der Region — und hinterlässt keine leeren
// Wrapper. Der Trip übergibt die Liste weiter und behält alles (AC-3).
//
// Echte Komponente, serverseitig gerendert (svelte/server) — kein Mock, kein Datei-Grep.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/subscription_header_ohne_profil_2796.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const PRUEFLING = path.join(FRONTEND, 'src/lib/components/shared/subscription-header/SubscriptionHeader.svelte');

async function html(props: Record<string, unknown>): Promise<string> {
	const K = (await import(pathToFileURL(PRUEFLING).href)).default;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return render(K as any, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
}
const testids = (b: string) => [...b.matchAll(/data-testid="([^"]+)"/g)].map((m) => m[1]);
const text = (b: string) => b.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
const metaOrte = createRawSnippet(() => ({ render: () => `<span data-testid="probe-meta">${' · '}3 Orte</span>` }));

/** Wie die Seite des Orts-Vergleichs nach S4a: keine Profil-Props. */
const VERGLEICH = {
	kind: 'vergleich',
	name: 'Dolomiten Süd',
	region: 'Ötztal',
	testidPrefix: 'compare-hub',
	onSaveField: async () => {}
};

describe('#2796 AC-1/AC-2: Orts-Vergleich ohne Auswahlliste — kein Profil im Kopf', () => {
	test('weder Kacheln noch Handy-Knopf noch Handy-Auswahl', async () => {
		const ids = testids(await html(VERGLEICH));
		assert.ok(ids.includes('compare-hub-region-edit-toggle'), `Messaufbau: Kopf gerendert? ${ids.join(', ')}`);
		const profil = ids.filter((i) => i.includes('-profil-'));
		assert.deepEqual(profil, [], `Profil-Bedienelemente trotz fehlender Auswahlliste: ${profil.join(', ')}`);
	});

	test('leere Auswahlliste wirkt wie keine (auch mit Profil und Label)', async () => {
		const b = await html({ ...VERGLEICH, profile: 'wandern', profileOptions: [], profileLabel: 'Wandern', meta: metaOrte });
		assert.deepEqual(testids(b).filter((i) => i.includes('-profil-')), []);
		assert.ok(!text(b).includes('Wandern'), `Profilname hinter der Region: ${text(b)}`);
		assert.match(text(b), /Ötztal · 3 Orte/, `Regionszeile mit Orte-Anzahl: ${text(b)}`);
	});

	test('keine leeren Wrapper an Stelle der entfallenen Profil-Zeile', async () => {
		const b = await html(VERGLEICH);
		const leer = [...b.matchAll(/<(div|span|section|p)(\s[^>]*)?>\s*<\/\1>/g)].map((m) => m[0]);
		assert.deepEqual(leer, [], `leere Wrapper: ${leer.join(' | ')}`);
	});
});

describe('#2796 AC-3: Trip übergibt die Auswahlliste — Chips und Knopf bleiben', () => {
	test('Kacheln, Handy-Knopf, Handy-Auswahl und Profilname hinter der Region', async () => {
		const b = await html({
			kind: 'trip', name: 'GR20', region: 'Korsika', testidPrefix: 'trip', onSaveField: async () => {},
			profile: 'trekking', profileLabel: 'Trekking',
			profileOptions: [{ value: 'trekking', label: 'Trekking' }, { value: 'skitour', label: 'Skitour' }]
		});
		const ids = testids(b);
		for (const id of ['trip-profil-option-trekking', 'trip-profil-option-skitour', 'trip-profil-knopf', 'trip-profil-auswahl']) {
			assert.ok(ids.includes(id), `${id} fehlt: ${ids.join(', ')}`);
		}
		assert.match(text(b), /Korsika · Trekking/);
	});
});
